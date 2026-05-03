"""
backend/orchestrator/orchestrator.py  (v2 — DAG-aware, crash-resumable)
─────────────────────────────────────────────────────────────────────────
Design principles:
  1. State lives in PostgreSQL (Execution.partial_state) — not in memory.
  2. Agents whose AgentRun row already shows status='success' are SKIPPED
     on resume — giving idempotent crash recovery.
  3. The PlannerAgent returns a DAG (`plan_dag`); stages with multiple
     agents in the same stage are run with asyncio.gather (parallel).
  4. Each agent result is immediately flushed to the DB so partial progress
     is never lost.
  5. Execution metadata (timings, agent sources, versions) is accumulated
     and written to Execution.metadata_ at the end.
"""
from __future__ import annotations

import asyncio
import logging
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from backend.agents.advisor_agent    import AdvisorAgent
from backend.agents.allocation_agent import AllocationAgent
from backend.agents.analysis_agent   import AnalysisAgent
from backend.agents.base             import AgentError
from backend.agents.market_agent     import MarketAgent
from backend.agents.validator_agent  import ValidatorAgent
from backend.config                  import settings

logger = logging.getLogger(__name__)


class Orchestrator:
    """
    DAG-aware multi-agent orchestrator.

    Usage (inside Celery task):
        orc = Orchestrator(execution_id=eid, db=db_session)
        final_state = await orc.run(input_data)
    """

    def __init__(
        self,
        execution_id: Optional[str] = None,
        db           = None,   # SQLAlchemy Session (injected by Celery task)
    ) -> None:
        self.execution_id = execution_id or str(uuid.uuid4())
        self.db           = db

        # Shared mutable state across all agents in this run
        self.state: Dict[str, Any] = {}

        # Metadata accumulated during execution (written to DB at end)
        self.metadata: Dict[str, Any] = {
            "execution_id":   self.execution_id,
            "start_time":     None,
            "end_time":       None,
            "status":         "pending",
            "agents_executed": [],
            "errors":         [],
            "model_version":        settings.MODEL_VERSION,
            "prompt_version":       settings.PROMPT_VERSION,
            "allocation_version":   settings.ALLOCATION_VERSION,
        }

        # Agent registry
        self.agents: Dict[str, Any] = {
            "market":     MarketAgent(),
            "analysis":   AnalysisAgent(),
            "allocation": AllocationAgent(),
            "advisor":    AdvisorAgent(),
            "validator":  ValidatorAgent(),
        }

        # Optional PlannerAgent
        self._planner: Any = None
        try:
            from backend.agents.planner_agent import PlannerAgent
            self._planner = PlannerAgent()
            logger.info("Orchestrator: PlannerAgent v2 loaded")
        except ImportError:
            logger.info("Orchestrator: PlannerAgent not available — using default DAG")

        # Default sequential plan (fallback if planner is absent)
        self._default_plan: List[str] = [
            "market", "analysis", "allocation", "advisor", "validator"
        ]

    # ── Resume support ────────────────────────────────────────────────────────

    def _load_completed_agents(self) -> set[str]:
        """
        Query AgentRun table for already-completed agents in this execution.
        Returns a set of agent names that can be safely skipped.
        """
        if not self.db:
            return set()
        try:
            from backend.models.schemas import AgentRun
            rows = (
                self.db.query(AgentRun)
                .filter(
                    AgentRun.execution_id == self.execution_id,
                    AgentRun.status == "success",
                )
                .all()
            )
            completed = {row.agent_name for row in rows}
            if completed:
                logger.info(
                    "Orchestrator: resuming — already completed: %s", completed
                )
            return completed
        except Exception as exc:
            logger.warning("Could not load completed agents: %s", exc)
            return set()

    def _persist_agent_run(
        self,
        agent_name: str,
        status:     str,
        output:     Dict[str, Any],
        error:      Optional[str],
        elapsed:    float,
        attempt:    int,
        start:      datetime,
    ) -> None:
        """Upsert an AgentRun row so the run is recoverable."""
        if not self.db:
            return
        try:
            from backend.models.schemas import AgentRun

            existing = (
                self.db.query(AgentRun)
                .filter(
                    AgentRun.execution_id == self.execution_id,
                    AgentRun.agent_name   == agent_name,
                )
                .first()
            )
            now = datetime.now(timezone.utc)
            if existing:
                existing.status          = status
                existing.output_state    = _sanitise(output)
                existing.error           = error
                existing.elapsed_seconds = elapsed
                existing.attempt         = attempt
                existing.end_time        = now
            else:
                row = AgentRun(
                    execution_id    = self.execution_id,
                    agent_name      = agent_name,
                    status          = status,
                    input_state     = _sanitise(self.state),
                    output_state    = _sanitise(output),
                    error           = error,
                    elapsed_seconds = elapsed,
                    attempt         = attempt,
                    start_time      = start,
                    end_time        = now,
                )
                self.db.add(row)
            self.db.commit()
        except Exception as exc:
            logger.warning("Could not persist AgentRun for %s: %s", agent_name, exc)

    def _flush_partial_state(self) -> None:
        """Write current shared state to Execution.partial_state."""
        if not self.db:
            return
        try:
            from backend.models.schemas import Execution
            row = self.db.query(Execution).filter(Execution.id == self.execution_id).first()
            if row:
                row.partial_state = _sanitise(self.state)
                row.updated_at    = datetime.now(timezone.utc)
                self.db.commit()
        except Exception as exc:
            logger.warning("Could not flush partial state: %s", exc)

    # ── Planning ──────────────────────────────────────────────────────────────

    async def _build_plan(self, input_data: Dict[str, Any]) -> List[List[str]]:
        """
        Returns a list of stages, each stage is a list of agent names.
        Sequential stages must complete in order; agents within a stage run in parallel.
        """
        if self._planner:
            try:
                result = await self._planner.execute_with_retry(input_data, self.state)
                dag    = result.get("plan_dag")
                if dag:
                    self.state.update(result)   # store planning_context etc.
                    stages = [stage["agents"] for stage in dag]
                    logger.info("Orchestrator: planner DAG: %s", stages)
                    return stages
            except Exception as exc:
                logger.warning("Planner failed (%s) — falling back to default plan", exc)

        # Default sequential plan (each agent is its own stage)
        plan = self._default_plan[:]
        if input_data.get("skip_validation") and "validator" in plan:
            plan.remove("validator")
        stages = [[agent] for agent in plan]
        logger.info("Orchestrator: default plan: %s", stages)
        return stages

    # ── Single-agent execution ────────────────────────────────────────────────

    async def _run_agent(
        self,
        agent_name:        str,
        input_data:        Dict[str, Any],
        completed_agents:  set[str],
    ) -> Dict[str, Any]:
        """Execute one agent, skip if already completed (resume path)."""
        if agent_name in completed_agents:
            logger.info("Orchestrator: SKIP %s (already completed in prior run)", agent_name)
            # Restore its output from the DB if available
            saved_output = self._load_agent_output(agent_name)
            if saved_output:
                self.state.update(saved_output)
            return {}

        if agent_name not in self.agents:
            raise ValueError(f"Unknown agent: {agent_name}")

        agent     = self.agents[agent_name]
        start     = datetime.now(timezone.utc)
        start_ts  = time.time()

        logger.info("Orchestrator: RUNNING agent '%s'", agent_name)

        try:
            result  = await agent.execute_with_retry(input_data, self.state)
            elapsed = time.time() - start_ts

            self.metadata["agents_executed"].append({
                "agent":          agent_name,
                "status":         "success",
                "elapsed_seconds": round(elapsed, 3),
                "timestamp":      datetime.now(timezone.utc).isoformat(),
            })

            attempt = result.pop("_metadata", {}).get("attempt", 1)
            self._persist_agent_run(agent_name, "success", result, None, elapsed, attempt, start)

            logger.info("Orchestrator: agent '%s' done in %.2fs", agent_name, elapsed)
            return result

        except (AgentError, Exception) as exc:
            elapsed = time.time() - start_ts
            error_msg = str(exc)
            self.metadata["errors"].append({
                "agent":     agent_name,
                "error":     error_msg,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })
            self._persist_agent_run(agent_name, "failed", {}, error_msg, elapsed, 1, start)
            logger.error("Orchestrator: agent '%s' FAILED: %s", agent_name, exc)
            raise AgentError(f"Agent '{agent_name}' failed: {exc}") from exc

    def _load_agent_output(self, agent_name: str) -> Optional[Dict[str, Any]]:
        if not self.db:
            return None
        try:
            from backend.models.schemas import AgentRun
            row = (
                self.db.query(AgentRun)
                .filter(
                    AgentRun.execution_id == self.execution_id,
                    AgentRun.agent_name   == agent_name,
                    AgentRun.status       == "success",
                )
                .first()
            )
            return row.output_state if row else None
        except Exception:
            return None

    # ── Main run ──────────────────────────────────────────────────────────────

    async def run(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        logger.info("Orchestrator: starting execution %s", self.execution_id)

        self.metadata["start_time"] = datetime.now(timezone.utc).isoformat()
        self.metadata["status"]     = "running"

        # Initialise shared state with user input + versioning
        self.state.update(input_data)
        self.state["execution_id"]       = self.execution_id
        self.state["model_version"]      = settings.MODEL_VERSION
        self.state["prompt_version"]     = settings.PROMPT_VERSION
        self.state["allocation_version"] = settings.ALLOCATION_VERSION

        # Load partial state from DB if this is a resume
        self._restore_partial_state()
        completed_agents = self._load_completed_agents()

        # Determine execution plan (DAG)
        stages = await self._build_plan(input_data)

        try:
            pipeline_failed = False

            for stage_agents in stages:
                if len(stage_agents) == 1:
                    # Sequential single-agent stage
                    agent_name = stage_agents[0]
                    try:
                        result = await self._run_agent(agent_name, input_data, completed_agents)
                        self.state.update(result)
                        self._flush_partial_state()
                    except AgentError:
                        pipeline_failed = True
                        break
                else:
                    # Parallel stage — gather results, then merge into state
                    tasks = [
                        self._run_agent(name, input_data, completed_agents)
                        for name in stage_agents
                    ]
                    results = await asyncio.gather(*tasks, return_exceptions=True)

                    for name, res in zip(stage_agents, results):
                        if isinstance(res, Exception):
                            self.metadata["errors"].append({
                                "agent":     name,
                                "error":     str(res),
                                "timestamp": datetime.now(timezone.utc).isoformat(),
                            })
                            pipeline_failed = True
                        else:
                            self.state.update(res)

                    self._flush_partial_state()
                    if pipeline_failed:
                        break

            # Final status
            if pipeline_failed:
                self.metadata["status"] = "failed"
            elif self.state.get("validation_passed") is False:
                self.metadata["status"] = "completed_with_errors"
            else:
                self.metadata["status"] = "completed"

        except Exception as exc:
            self.metadata["status"] = "failed"
            logger.error("Orchestrator: pipeline error: %s", exc)
            raise
        finally:
            self.metadata["end_time"] = datetime.now(timezone.utc).isoformat()
            self.state["_execution_metadata"] = self.metadata
            elapsed = (
                datetime.now(timezone.utc) -
                datetime.fromisoformat(self.metadata["start_time"])
            ).total_seconds()
            logger.info(
                "Orchestrator: execution %s → %s in %.2fs",
                self.execution_id, self.metadata["status"], elapsed,
            )

        return self.state

    def _restore_partial_state(self) -> None:
        """Load Execution.partial_state (if any) into self.state for resume."""
        if not self.db:
            return
        try:
            from backend.models.schemas import Execution
            row = self.db.query(Execution).filter(Execution.id == self.execution_id).first()
            if row and row.partial_state:
                self.state.update(row.partial_state)
                logger.info("Orchestrator: restored partial state from DB (%d keys)", len(row.partial_state))
        except Exception as exc:
            logger.warning("Could not restore partial state: %s", exc)

    def get_state(self)    -> Dict[str, Any]: return self.state
    def get_metadata(self) -> Dict[str, Any]: return self.metadata


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _sanitise(obj: Any) -> Any:
    """
    Recursively remove un-serialisable objects from dicts / lists
    so the result can be stored as JSONB.
    """
    if isinstance(obj, dict):
        return {k: _sanitise(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_sanitise(i) for i in obj]
    if isinstance(obj, (str, int, float, bool, type(None))):
        return obj
    return str(obj)
