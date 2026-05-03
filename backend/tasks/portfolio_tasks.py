"""
backend/tasks/portfolio_tasks.py
──────────────────────────────────
Celery tasks for portfolio generation pipeline.

This module contains the main task that executes the multi-agent orchestrator
in a crash-resilient manner. If the worker crashes mid-execution, the task
can be resumed from the last completed agent.

Usage:
  from backend.tasks.portfolio_tasks import run_portfolio_pipeline

  # Enqueue task (returns AsyncResult)
  result = run_portfolio_pipeline.delay(
      execution_id="exec_123",
      input_data={"budget": 250000, "risk": "Medium", "horizon": "Long"},
      user_id="user_456",
  )

  # Get result (blocking)
  final_state = result.get(timeout=300)

  # Check status (non-blocking)
  print(result.status)  # PENDING, STARTED, SUCCESS, FAILURE, RETRY
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any, Dict

from celery import Task

from backend.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)


# ── Base Task Class with DB Session ───────────────────────────────────────────
class DBTask(Task):
    """
    Base Celery task that provides a database session.

    The session is automatically committed on success and rolled back on failure.
    """

    _db = None

    @property
    def db(self):
        """Lazy-load DB session."""
        if self._db is None:
            from backend.db.database import SessionLocal

            self._db = SessionLocal()
        return self._db

    def after_return(self, *args, **kwargs):
        """Cleanup DB session after task completes."""
        if self._db is not None:
            try:
                self._db.close()
            except Exception as exc:
                logger.warning("Failed to close DB session: %s", exc)
            finally:
                self._db = None


# ── Main Portfolio Pipeline Task ──────────────────────────────────────────────
@celery_app.task(
    bind=True,
    base=DBTask,
    name="backend.tasks.portfolio_tasks.run_portfolio_pipeline",
    autoretry_for=(Exception,),
    retry_backoff=2,
    retry_backoff_max=600,
    max_retries=3,
    acks_late=True,
    reject_on_worker_lost=True,
)
def run_portfolio_pipeline(
    self,
    execution_id: str,
    input_data: Dict[str, Any],
    user_id: str,
) -> Dict[str, Any]:
    """
    Execute the multi-agent portfolio generation pipeline.

    This task is crash-resilient:
    - State is persisted to DB after each agent
    - On retry/resume, completed agents are skipped
    - Final result is stored in Execution.final_state and Portfolio table

    Args:
        execution_id: Unique execution identifier (UUID)
        input_data: User inputs (budget, risk, horizon)
        user_id: Firebase user ID (from JWT)

    Returns:
        Final pipeline state (allocation, reasoning, scores, etc.)
    """
    from backend.models.schemas import Execution, Portfolio
    from backend.orchestrator.orchestrator import Orchestrator

    db = self.db
    start_time = datetime.now(timezone.utc)

    logger.info(
        "Celery task started | execution_id=%s attempt=%d max_retries=%d",
        execution_id,
        self.request.retries,
        self.max_retries,
    )

    try:
        # ── Update Execution Status ────────────────────────────────────────
        execution = (
            db.query(Execution)
            .filter(Execution.id == execution_id)
            .first()
        )

        if not execution:
            raise ValueError(f"Execution {execution_id} not found in database")

        execution.celery_task_id = self.request.id
        execution.status = "running"
        execution.retry_count = self.request.retries
        execution.updated_at = datetime.now(timezone.utc)
        db.commit()

        logger.info(
            "Execution status updated to RUNNING | execution_id=%s celery_task_id=%s",
            execution_id,
            self.request.id,
        )

        # ── Run Orchestrator ───────────────────────────────────────────────
        orchestrator = Orchestrator(execution_id=execution_id, db=db)
        final_state = asyncio.run(orchestrator.run(input_data))

        # ── Update Execution with Final State ──────────────────────────────
        execution.status = orchestrator.get_metadata().get("status", "completed")
        execution.final_state = _sanitise_for_json(final_state)
        execution.metadata_ = orchestrator.get_metadata()
        execution.updated_at = datetime.now(timezone.utc)
        db.commit()

        logger.info(
            "Execution completed | execution_id=%s status=%s duration=%.2fs",
            execution_id,
            execution.status,
            (datetime.now(timezone.utc) - start_time).total_seconds(),
        )

        # ── Create Portfolio Record ────────────────────────────────────────
        portfolio = Portfolio(
            user_id=user_id,
            budget=input_data.get("budget", 0),
            risk=input_data.get("risk", "Medium"),
            horizon=input_data.get("horizon", "Long"),
            status="completed",
            allocation=final_state.get("allocation"),
            reasoning=final_state.get("reasoning"),
            analysis_summary=final_state.get("analysis"),
            market_data=final_state.get("market_data"),
            steps_data=final_state.get("_execution_metadata", {}).get("agents_executed", []),
            cadence=final_state.get("cadence"),
            # Audit fields
            model_version=final_state.get("model_version"),
            prompt_version=final_state.get("prompt_version"),
            allocation_version=final_state.get("allocation_version"),
            # Risk scores
            portfolio_score=final_state.get("portfolio_score"),
            diversification_score=final_state.get("diversification_score"),
            volatility_score=final_state.get("volatility_score"),
            validation_errors=final_state.get("validation_errors"),
            validation_warnings=final_state.get("validation_warnings"),
        )
        db.add(portfolio)
        db.commit()
        db.refresh(portfolio)

        # ── Link Execution to Portfolio ────────────────────────────────────
        execution.portfolio_id = portfolio.id
        db.commit()

        logger.info(
            "Portfolio created | execution_id=%s portfolio_id=%s user_id=%s",
            execution_id,
            portfolio.id,
            user_id,
        )

        return {
            "execution_id": execution_id,
            "portfolio_id": portfolio.id,
            "status": execution.status,
            "final_state": _sanitise_for_json(final_state),
        }

    except Exception as exc:
        logger.exception(
            "Pipeline failed | execution_id=%s attempt=%d error=%s",
            execution_id,
            self.request.retries,
            exc,
        )

        # ── Update Execution Status on Failure ─────────────────────────────
        try:
            execution = (
                db.query(Execution)
                .filter(Execution.id == execution_id)
                .first()
            )
            if execution:
                execution.status = "failed"
                execution.error = str(exc)
                execution.updated_at = datetime.now(timezone.utc)
                db.commit()
        except Exception as db_exc:
            logger.error("Failed to update execution status: %s", db_exc)

        # ── Re-raise to trigger Celery retry ───────────────────────────────
        raise self.retry(exc=exc)


# ── Helper Functions ──────────────────────────────────────────────────────────

def _sanitise_for_json(obj: Any) -> Any:
    """
    Recursively convert objects to JSON-serialisable types.
    Removes unserialisable objects (datetime, Decimal, etc.).
    """
    if isinstance(obj, dict):
        return {k: _sanitise_for_json(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_sanitise_for_json(i) for i in obj]
    if isinstance(obj, (str, int, float, bool, type(None))):
        return obj
    if isinstance(obj, datetime):
        return obj.isoformat()
    return str(obj)


# ── Utility Tasks (Optional) ──────────────────────────────────────────────────

@celery_app.task(bind=True, base=DBTask, name="backend.tasks.portfolio_tasks.cleanup_old_executions")
def cleanup_old_executions(self, days: int = 30) -> Dict[str, int]:
    """
    Delete executions and agent_runs older than N days.

    Run this periodically (e.g., daily at 3 AM) to prevent database bloat.

    Args:
        days: Delete records older than this many days

    Returns:
        Dict with counts of deleted records
    """
    from backend.models.schemas import Execution, AgentRun
    from datetime import timedelta

    cutoff = datetime.now(timezone.utc) - timedelta(days=days)

    # Delete agent_runs first (foreign key constraint)
    agent_runs_deleted = (
        self.db.query(AgentRun)
        .join(Execution, AgentRun.execution_id == Execution.id)
        .filter(Execution.created_at < cutoff)
        .delete(synchronize_session=False)
    )

    # Delete executions
    executions_deleted = (
        self.db.query(Execution)
        .filter(Execution.created_at < cutoff)
        .delete(synchronize_session=False)
    )

    self.db.commit()

    logger.info(
        "Cleanup completed | executions_deleted=%d agent_runs_deleted=%d cutoff=%s",
        executions_deleted,
        agent_runs_deleted,
        cutoff.isoformat(),
    )

    return {
        "executions_deleted": executions_deleted,
        "agent_runs_deleted": agent_runs_deleted,
    }
