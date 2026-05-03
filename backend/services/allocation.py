from __future__ import annotations

from typing import Any


ALLOCATION_LABELS = [
    "Debt / liquid reserve",
    "Gold ETF",
    "Large-cap core",
    "Flexi-cap blend",
    "Mid and small-cap growth",
]

ALLOCATION_COLORS = ["#38bdf8", "#8b5cf6", "#10b981", "#f59e0b", "#f97316"]

ALLOCATION_NOTES = [
    "Keeps short-term volatility under control.",
    "Adds a defensive hedge when equity risk rises.",
    "Anchors the portfolio with quality compounding.",
    "Allows the model to rotate across opportunities.",
    "Captures higher beta when the horizon allows it.",
]

RISK_BLUEPRINTS = {
    "Low": [38, 18, 24, 14, 6],
    "Medium": [24, 12, 30, 22, 12],
    "High": [12, 8, 30, 24, 26],
}

HORIZON_BLUEPRINTS = {
    "Short": [10, 5, -4, -4, -7],
    "Medium": [0, 0, 0, 0, 0],
    "Long": [-6, -4, 4, 3, 3],
}


def normalize_percentages(weights: list[int]) -> list[int]:
    safe_weights = [max(4, weight) for weight in weights]
    total = sum(safe_weights)
    raw = [(weight / total) * 100 for weight in safe_weights]
    floors = [int(value) for value in raw]
    remainder = 100 - sum(floors)

    ordering = sorted(
        enumerate(raw),
        key=lambda item: item[1] - floors[item[0]],
        reverse=True,
    )

    for index in range(remainder):
        floors[ordering[index % len(ordering)][0]] += 1

    return floors


def build_allocation(budget: float, risk: str, horizon: str) -> dict[str, Any]:
    budget_blueprint = [0, 0, 0, 0, 0]
    if budget < 100000:
        budget_blueprint = [8, 4, -2, -3, -7]
    elif budget > 750000:
        budget_blueprint = [-3, -2, 3, 2, 0]

    weights = [
        RISK_BLUEPRINTS[risk][index] + HORIZON_BLUEPRINTS[horizon][index] + budget_blueprint[index]
        for index in range(len(ALLOCATION_LABELS))
    ]

    values = normalize_percentages(weights)

    allocation = [
        {
            "label": ALLOCATION_LABELS[index],
            "value": values[index],
            "color": ALLOCATION_COLORS[index],
            "note": ALLOCATION_NOTES[index],
        }
        for index in range(len(ALLOCATION_LABELS))
    ]

    cadence = "Monthly" if horizon == "Short" else "Quarterly"
    summary = f"{risk} risk, {horizon} horizon"

    return {
        "allocation": allocation,
        "cadence": cadence,
        "summary": summary,
    }
