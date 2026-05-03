"""
backend/agents/planner_agent.py  (v2 — Real Decision Engine)
──────────────────────────────────────────────────────────────
The PlannerAgent produces an ordered DAG execution plan by inspecting:

  ● Input constraints (risk, horizon, budget)
  ● Current shared state (cached market data, prior errors)
  ● Input flags   (skip_validation, force_refresh, rerun_agents)

DAG format returned in `plan_dag`:
  [
    {"stage": 1, "agents": ["market"]},          # must complete before stage 2
    {"stage": 2, "agents": ["analysis"]},         # depends on market
    {"stage": 3, "agents": ["allocation"]},       # depends on analysis
    {"stage": 4, "agents": ["advisor"]},          # depends on allocation
    {"stage": 5, "agents": ["validator"]},        # depends on advisor
  ]

The `plan` flat list is kept for backward-compat with the linear Orchestrator.
When the DAG-aware Orchestrator is used, it reads `plan_dag` instead.

Branching rules (examples):
  ● If market_data is already in state → skip MarketAgent (stage 1 absent)
  ● If risk == "High" → insert a dedicated "sensitivity_check" stage (future)
  ● If skip_validation is set → omit ValidatorAgent
  ● Budget buckets alter downstream agent weighting hints attached to state
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List

from backend.agents.base import BaseAgent

logger = logging.getLogger(__name__)

# Budget tiers — written to state so AllocationAgent can tune accordingly
_BUDGET_TIER_SMALL  = 100_000
_BUDGET_TIER_LARGE  = 750_000


def _budget_tier(budget: float) -> str:
    if budget < _BUDGET_TIER_SMALL:
        return "small"
    if budget > _BUDGET_TIER_LARGE:
        return "large"
    return "medium"


class PlannerAgent(BaseAgent):
    name:        str = "planner_agent"
    timeout:     int = 5
    max_retries: int = 0   # Planning must not retry — deterministic

    async def run(
        self,
        input_data: Dict[str, Any],
        state:      Dict[str, Any],
    ) -> Dict[str, Any]:
        logger.info("PlannerAgent v2: building execution DAG...")

        risk            = input_data.get("risk")  or state.get("risk", "Medium")
        horizon         = input_data.get("horizon") or state.get("horizon", "Long")
        budget          = input_data.get("budget") or state.get("budget", 0)
        skip_validation = input_data.get("skip_validation", False)
        force_refresh   = input_data.get("force_refresh", False)
        market_in_state = "market_data" in state and not force_refresh

        # ── Build ordered stages ──────────────────────────────────────────
        stages: List[Dict[str, Any]] = []

        # Stage 1 — Market data (skip if already cached in state)
        if market_in_state:
            logger.info("PlannerAgent v2: market_data in state → skipping MarketAgent")
        else:
            stages.append({"stage": 1, "agents": ["market"], "depends_on": []})

        # Stage 2 — Analysis (LLM — always runs)
        analysis_stage = len(stages) + 1
        stages.append({"stage": analysis_stage, "agents": ["analysis"], "depends_on": [s["stage"] for s in stages]})

        # Stage 3 — Allocation (rule-based — always runs)
        alloc_stage = len(stages) + 1
        stages.append({"stage": alloc_stage, "agents": ["allocation"], "depends_on": [analysis_stage]})

        # Stage 4 — Advisor (LLM — always runs)
        advisor_stage = len(stages) + 1
        stages.append({"stage": advisor_stage, "agents": ["advisor"], "depends_on": [alloc_stage]})

        # Stage 5 — Validator (skip only if explicitly requested)
        if not skip_validation:
            validator_stage = len(stages) + 1
            stages.append({"stage": validator_stage, "agents": ["validator"], "depends_on": [advisor_stage]})
        else:
            logger.info("PlannerAgent v2: skip_validation=True → ValidatorAgent omitted")

        # ── Flat plan (backward-compat with linear orchestrator) ──────────
        flat_plan: List[str] = []
        for stage in stages:
            flat_plan.extend(stage["agents"])

        # ── Planning hints written back to state ───────────────────────────
        planning_context = {
            "budget_tier":  _budget_tier(budget),
            "risk_profile": risk,
            "horizon":      horizon,
        }

        logger.info(
            "PlannerAgent v2: plan=%s  budget_tier=%s  stages=%d",
            flat_plan, planning_context["budget_tier"], len(stages),
        )

        return {
            "plan":             flat_plan,
            "plan_dag":         stages,
            "planning_strategy": "dag-v2",
            "planning_context": planning_context,
        }
