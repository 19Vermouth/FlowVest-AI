"""
backend/agents/validator_agent.py  (v2 — Risk Engine)
──────────────────────────────────────────────────────
Full compliance and risk-engine validation.

Checks performed:
  1. Required field presence
  2. Budget positive and above minimum
  3. Allocation sum = 100 % (strict ±1 % tolerance)
  4. No negative or >100 % individual slices
  5. Max single-asset concentration cap  (dynamic: High→45 %, Medium→50 %, Low→55 %)
  6. Minimum diversification: at least 3 non-zero slices
  7. Risk–equity consistency (High risk → equity ≥50 %)
  8. Volatility proxy check  (Mid+SmallCap ≤ 40 % for Low risk)
  9. Reasoning quality (minimum 50 chars)

Result keys added to state:
  validation_passed      bool
  validation_errors      list[str]
  validation_warnings    list[str]
  validation_summary     "PASSED" | "FAILED"
  portfolio_score        float   0–100  (higher = better diversification + compliance)
  diversification_score  float   0–100
  volatility_score       float   0–100  (lower = more volatile, higher = more stable)
"""
from __future__ import annotations

import logging
from typing import Any, Dict

from backend.agents.base import BaseAgent

logger = logging.getLogger(__name__)

# ── Equity-like sleeve labels ──────────────────────────────────────────────────
EQUITY_LABELS = frozenset({"Large-cap core", "Flexi-cap blend", "Mid and small-cap growth"})
HIGH_VOL_LABELS = frozenset({"Mid and small-cap growth"})

# Max single-asset concentration per risk profile
MAX_CONCENTRATION: dict[str, float] = {
    "Low":    55.0,
    "Medium": 50.0,
    "High":   45.0,
}

# Minimum equity exposure per risk profile
MIN_EQUITY: dict[str, float] = {
    "Low":    0.0,
    "Medium": 30.0,
    "High":   50.0,
}

# Max high-volatility sleeve for Low-risk portfolios
MAX_HIGH_VOL_FOR_LOW_RISK = 15.0


class ValidatorAgent(BaseAgent):
    name:        str = "validator_agent"
    timeout:     int = 10
    max_retries: int = 0   # Validation is deterministic — no point retrying

    async def run(
        self,
        input_data: Dict[str, Any],
        state:      Dict[str, Any],
    ) -> Dict[str, Any]:
        logger.info("ValidatorAgent v2 (Risk Engine): starting compliance check...")

        errors:   list[str] = []
        warnings: list[str] = []

        allocation = state.get("allocation", [])
        budget     = state.get("budget")
        risk       = state.get("risk", "Medium")
        reasoning  = state.get("reasoning", "")

        # ── 1. Required fields ─────────────────────────────────────────────
        for field in ("budget", "risk", "horizon", "allocation", "reasoning"):
            if field not in state:
                errors.append(f"Missing required pipeline field: '{field}'")

        # ── 2. Budget sanity ───────────────────────────────────────────────
        if budget is not None:
            if budget <= 0:
                errors.append(f"Budget must be positive; got {budget}")
            elif budget < 10_000:
                warnings.append(f"Budget Rs\u00a0{budget:,.0f} is very low — consider raising it above Rs\u00a010,000.")

        # ── 3. Allocation sum ──────────────────────────────────────────────
        if allocation:
            total = sum(s.get("value", 0) for s in allocation)
            if abs(total - 100) > 1:
                errors.append(f"Allocation sums to {total}% — must equal 100%.")

            # ── 4. Per-slice bounds ────────────────────────────────────────
            for s in allocation:
                val   = s.get("value", 0)
                label = s.get("label", "unknown")
                if val < 0:
                    errors.append(f"Negative weight ({val}%) in slice '{label}'.")
                if val > 100:
                    errors.append(f"Single-slice weight > 100% ({val}%) in '{label}'.")

            # ── 5. Concentration cap ───────────────────────────────────────
            cap = MAX_CONCENTRATION.get(risk, 50.0)
            for s in allocation:
                if s.get("value", 0) > cap:
                    errors.append(
                        f"'{s.get('label')}' at {s.get('value')}% exceeds the "
                        f"{risk}-risk concentration cap of {cap}%."
                    )

            # ── 6. Minimum diversification ─────────────────────────────────
            non_zero = [s for s in allocation if s.get("value", 0) > 0]
            if len(non_zero) < 3:
                warnings.append(
                    f"Only {len(non_zero)} non-zero allocation slice(s) — "
                    "a minimum of 3 is recommended for meaningful diversification."
                )

            # ── 7. Equity floor ────────────────────────────────────────────
            equity_total = sum(s.get("value", 0) for s in allocation if s.get("label") in EQUITY_LABELS)
            min_eq = MIN_EQUITY.get(risk, 0.0)
            if equity_total < min_eq:
                warnings.append(
                    f"{risk}-risk portfolio has {equity_total}% equity "
                    f"(recommended minimum: {min_eq}%)."
                )

            # ── 8. High-volatility cap (Low risk) ─────────────────────────
            if risk == "Low":
                hv_total = sum(s.get("value", 0) for s in allocation if s.get("label") in HIGH_VOL_LABELS)
                if hv_total > MAX_HIGH_VOL_FOR_LOW_RISK:
                    warnings.append(
                        f"Low-risk portfolio has {hv_total}% in high-volatility sleeves "
                        f"(recommended max: {MAX_HIGH_VOL_FOR_LOW_RISK}%)."
                    )

        # ── 9. Reasoning quality ───────────────────────────────────────────
        if len(reasoning) < 50:
            warnings.append("Reasoning memo is very short — may not be helpful to the investor.")

        # ── Scoring ───────────────────────────────────────────────────────
        diversification_score = _score_diversification(allocation)
        volatility_score      = _score_volatility(allocation, risk)
        portfolio_score       = round((diversification_score * 0.5 + volatility_score * 0.5), 2)

        validation_passed = len(errors) == 0

        if validation_passed:
            logger.info(
                "ValidatorAgent v2: PASSED | score=%.1f diversification=%.1f volatility=%.1f",
                portfolio_score, diversification_score, volatility_score,
            )
        else:
            logger.error(
                "ValidatorAgent v2: FAILED | errors=%s", errors
            )
        if warnings:
            logger.warning("ValidatorAgent v2: %d warning(s): %s", len(warnings), warnings)

        return {
            "validation_passed":     validation_passed,
            "validation_errors":     errors,
            "validation_warnings":   warnings,
            "validation_summary":    "PASSED" if validation_passed else "FAILED",
            "portfolio_score":       portfolio_score,
            "diversification_score": diversification_score,
            "volatility_score":      volatility_score,
        }


# ─── Scoring helpers ──────────────────────────────────────────────────────────

def _score_diversification(allocation: list[dict[str, Any]]) -> float:
    """
    Score 0–100: higher → better spread.
    Uses Herfindahl–Hirschman Index (HHI) inverted.
    HHI = sum(weight_i²); lower HHI = better diversification.
    """
    if not allocation:
        return 0.0
    weights = [s.get("value", 0) / 100.0 for s in allocation]
    hhi     = sum(w ** 2 for w in weights)
    n       = len(weights)
    # Normalise: perfect equal-weight gives HHI=1/n; single-asset gives HHI=1
    min_hhi = 1.0 / n if n else 1.0
    score   = max(0.0, (1.0 - hhi) / (1.0 - min_hhi)) * 100 if (1.0 - min_hhi) != 0 else 100.0
    return round(score, 2)


def _score_volatility(allocation: list[dict[str, Any]], risk: str) -> float:
    """
    Score 0–100: higher → more stable (less high-volatility weight).
    Penalises high-vol sleeves. Scales differently by risk tier.
    """
    if not allocation:
        return 0.0
    hv_weight = sum(s.get("value", 0) for s in allocation if s.get("label") in HIGH_VOL_LABELS)
    # Low risk: penalise hard. High risk: tolerate more.
    tolerance = {"Low": 15, "Medium": 30, "High": 50}.get(risk, 30)
    score     = max(0.0, (1.0 - min(hv_weight / tolerance, 1.0))) * 100
    return round(score, 2)
