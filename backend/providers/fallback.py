"""
backend/providers/fallback.py
──────────────────────────────
Last-resort deterministic fallback when ALL live providers fail.

Generates plausible prices using a time-based sinusoidal function.
Clearly marked source="fallback" so downstream agents / dashboards can warn.
"""
from __future__ import annotations

import logging
import math
from datetime import datetime, timezone

from backend.providers.base import BaseMarketProvider, MarketPayload, derive_trend

logger = logging.getLogger(__name__)


class FallbackProvider(BaseMarketProvider):
    name: str = "fallback"

    async def fetch_market_data(self) -> MarketPayload:
        now   = datetime.now(timezone.utc)
        phase = (now.hour * 60 + now.minute) / 18.0   # 0–80 over 24 h

        nifty  = 24_780 + math.sin(phase) * 140
        sensex = 81_320 + math.cos(phase / 1.7) * 520
        gold   = 69_740 + math.sin(phase / 2.3) * 180

        nifty_change  = round(math.sin(phase) * 0.34, 4)
        sensex_change = round(math.cos(phase / 1.4) * 0.28, 4)
        gold_change   = round(math.sin(phase / 1.8) * 0.19, 4)

        logger.warning("Using deterministic fallback market data — all providers failed")

        return {
            "nifty":        round(nifty, 2),
            "sensex":       round(sensex, 2),
            "gold":         round(gold, 2),
            "niftyChange":  nifty_change,
            "sensexChange": sensex_change,
            "goldChange":   gold_change,
            "trend":        derive_trend(nifty_change, sensex_change, gold_change),
            "updatedAt":    now.isoformat(),
            "source":       self.name,
        }
