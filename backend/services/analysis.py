"""
backend/services/analysis.py
─────────────────────────────
Market analysis service — uses the central LLM client.
"""
from __future__ import annotations

from typing import Any

from backend.config import settings
from backend.llm.client import call_llm


def _local_analysis(market: dict[str, Any], risk: str, horizon: str) -> str:
    trend         = market.get("trend", "Flat")
    nifty_change  = market.get("niftyChange", 0)
    sensex_change = market.get("sensexChange", 0)
    gold_change   = market.get("goldChange", 0)

    tone = {
        "Up":   "Risk appetite is constructive across Indian equities.",
        "Down": "Markets are defensive — capital protection takes priority.",
        "Flat": "The tape is balanced — disciplined construction is key.",
    }.get(trend, "Market regime is unclear.")

    risk_line = {
        "Low":    "Low risk prioritises drawdown control and stability.",
        "Medium": "Medium risk targets balanced compounding with manageable volatility.",
        "High":   "High risk can absorb more growth exposure and interim swings.",
    }.get(risk, "")

    horizon_line = {
        "Short":  "A short horizon demands liquidity and lower equity concentration.",
        "Medium": "A medium horizon permits selective growth while preserving flexibility.",
        "Long":   "A long horizon supports patient accumulation and broader equity exposure.",
    }.get(horizon, "")

    return (
        f"{tone} Nifty {nifty_change:+.2f}%, Sensex {sensex_change:+.2f}%, "
        f"Gold {gold_change:+.2f}% on latest read. {risk_line} {horizon_line}"
    )


async def generate_market_analysis(
    market:  dict[str, Any],
    risk:    str,
    horizon: str,
) -> dict[str, str]:
    fallback_text = _local_analysis(market, risk, horizon)

    if not settings.OPENROUTER_API_KEY:
        return {"summary": fallback_text, "source": "local-fallback"}

    messages = [
        {
            "role": "system",
            "content": (
                "You are the FlowVest AI market analysis agent. "
                "Write a concise, jargon-free market note (≤110 words) for an Indian retail investor. "
                "Cover market tone, risk posture implications, and avoid naming individual stocks."
            ),
        },
        {
            "role": "user",
            "content": (
                f"Market snapshot: {market}. "
                f"Investor profile: risk={risk}, horizon={horizon}. "
                "Return a single short paragraph."
            ),
        },
    ]

    result = await call_llm(
        messages=messages,
        max_tokens=settings.LLM_MAX_TOKENS_ANALYSIS,
        temperature=settings.LLM_TEMPERATURE_ANALYSIS,
        purpose="market_analysis",
    )

    content = result.get("content") or fallback_text
    source  = result.get("source", "local-fallback") if result.get("content") else "local-fallback"

    return {
        "summary": content,
        "source":  source,
        "model":   result.get("model", ""),
        "cached":  result.get("cached", False),
        "cost_usd": result.get("estimated_cost", 0.0),
    }
