"""
backend/providers/base.py
──────────────────────────
Abstract interface every market-data provider must implement.

Normalised output format (MarketPayload):
{
    "nifty":        float,   # Nifty 50 index level
    "sensex":       float,   # BSE Sensex level
    "gold":         float,   # Gold price in INR per 10g
    "niftyChange":  float,   # Day % change
    "sensexChange": float,   # Day % change
    "goldChange":   float,   # Day % change
    "trend":        "Up" | "Flat" | "Down",
    "updatedAt":    str,     # ISO-8601 UTC timestamp
    "source":       str,     # provider name
}
"""
from __future__ import annotations

import abc
import logging
from typing import Any

logger = logging.getLogger(__name__)

# Type alias for the normalised market payload
MarketPayload = dict[str, Any]

# INR conversion constants
USDINR_FX: float = 83.0          # approximate; real systems would fetch live FX
TROY_OZ_PER_10G: float = 10 / 31.1035


def inr_per_10g(usd_per_oz: float) -> float:
    """Convert gold price from USD/troy-oz → INR/10g."""
    return usd_per_oz * USDINR_FX * TROY_OZ_PER_10G


def pct_change(current: float, previous: float) -> float:
    if not previous:
        return 0.0
    return round(((current - previous) / previous) * 100, 4)


def derive_trend(*changes: float) -> str:
    avg = sum(changes) / max(len(changes), 1)
    if avg > 0.05:
        return "Up"
    if avg < -0.05:
        return "Down"
    return "Flat"


class ProviderError(Exception):
    """Raised when a provider cannot return data."""


class BaseMarketProvider(abc.ABC):
    """Abstract base for all market data providers."""

    #: Unique identifier used in the 'source' field and log messages.
    name: str = "base"

    @abc.abstractmethod
    async def fetch_market_data(self) -> MarketPayload:
        """
        Fetch and return normalised market data.

        Must raise ProviderError (or any Exception) on failure so the
        MarketDataManager can failover to the next provider.
        """
        ...
