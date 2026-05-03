"""
backend/services/advisor.py
────────────────────────────
Advisor (investor memo) service — uses the central LLM client.
"""
from __future__ import annotations

from typing import Any

from backend.config import settings
from backend.llm.client import call_llm


def _local_reasoning(
    budget:          float,
    risk:            str,
    horizon:         str,
    analysis_summary: str,
    allocation:      list[dict[str, Any]],
) -> str:
    ranked  = sorted(allocation, key=lambda x: x.get("value", 0), reverse=True)
    lead    = ranked[0]   if ranked       else {"label": "Portfolio", "value": 100}
    support = ranked[1]   if len(ranked) > 1 else lead

    cadence       = "monthly" if horizon == "Short" else "quarterly"
    tranche_count = 6 if horizon == "Short" else 12 if horizon == "Medium" else 18
    tranche_value = max(1_000, round(budget / tranche_count / 1_000) * 1_000)

    return "\n".join([
        analysis_summary,
        "",
        (
            f"The allocation leans on {lead['label']} at {lead['value']}% "
            f"and {support['label']} at {support['value']}% — consistent with a "
            f"{risk.lower()}-risk, {horizon.lower()}-horizon profile."
        ),
        "",
        (
            f"Suggested deployment pace: ~Rs\u00a0{tranche_value:,.0f} per tranche, "
            f"reviewed {cadence} with a rebalance trigger at ±5% drift."
        ),
        "",
        "This output is educational and must be reviewed before executing any investment.",
    ])


async def generate_advisor_reasoning(
    budget:           float,
    risk:             str,
    horizon:          str,
    analysis_summary: str,
    allocation:       list[dict[str, Any]],
) -> dict[str, Any]:
    fallback_text = _local_reasoning(budget, risk, horizon, analysis_summary, allocation)

    if not settings.OPENROUTER_API_KEY:
        return {"reasoning": fallback_text, "source": "local-fallback"}

    messages = [
        {
            "role": "system",
            "content": (
                "You are the FlowVest AI advisor agent. "
                "Convert the provided market analysis and asset allocation into a clear investor memo. "
                "≤160 words. Include one rebalance cue and one short disclaimer."
            ),
        },
        {
            "role": "user",
            "content": (
                f"Budget=Rs {budget:,.0f}. Risk={risk}. Horizon={horizon}. "
                f"Analysis={analysis_summary}. Allocation={allocation}. "
                "Return plain text only."
            ),
        },
    ]

    result = await call_llm(
        messages=messages,
        max_tokens=settings.LLM_MAX_TOKENS_ADVISOR,
        temperature=settings.LLM_TEMPERATURE_ADVISOR,
        purpose="advisor_memo",
    )

    content = result.get("content") or fallback_text
    source  = result.get("source", "local-fallback") if result.get("content") else "local-fallback"

    return {
        "reasoning": content,
        "source":    source,
        "model":     result.get("model", ""),
        "cached":    result.get("cached", False),
        "cost_usd":  result.get("estimated_cost", 0.0),
    }
