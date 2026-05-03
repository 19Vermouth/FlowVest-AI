"""
backend/providers/fmp.py
──────────────────────────
Secondary market-data provider: Financial Modeling Prep (FMP)

FMP free tier offers stock quotes. We use:
  • /v3/quote/^NSEI   – Nifty 50
  • /v3/quote/^BSESN  – Sensex
  • /v3/quote/XAUUSD  – Gold USD/oz (converted to INR/10g)

API docs: https://financialmodelingprep.com/developer/docs/
Free plan: 250 requests/day, no per-minute hard limit published.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

import httpx

from backend.config import settings
from backend.providers.base import (
    BaseMarketProvider,
    MarketPayload,
    ProviderError,
    derive_trend,
    inr_per_10g,
)

logger = logging.getLogger(__name__)

FMP_BASE = "https://financialmodelingprep.com/api/v3/quote"


class FMPProvider(BaseMarketProvider):
    name: str = "fmp"

    def __init__(self) -> None:
        self._api_key = settings.FMP_API_KEY

    async def _fetch_quote(self, client: httpx.AsyncClient, symbol: str) -> dict:
        resp = await client.get(
            f"{FMP_BASE}/{symbol}",
            params={"apikey": self._api_key},
            timeout=12.0,
        )
        resp.raise_for_status()
        data = resp.json()

        if not data or not isinstance(data, list):
            raise ProviderError(f"FMP returned unexpected payload for {symbol}: {data}")

        return data[0]

    async def fetch_market_data(self) -> MarketPayload:
        if not self._api_key:
            raise ProviderError("FMP_API_KEY is not configured")

        async with httpx.AsyncClient() as client:
            nifty_q   = await self._fetch_quote(client, "^NSEI")
            sensex_q  = await self._fetch_quote(client, "^BSESN")
            gold_q    = await self._fetch_quote(client, "XAUUSD")

        nifty        = float(nifty_q.get("price", 0) or 0)
        nifty_change = float(nifty_q.get("changesPercentage", 0) or 0)

        sensex        = float(sensex_q.get("price", 0) or 0)
        sensex_change = float(sensex_q.get("changesPercentage", 0) or 0)

        gold_usd     = float(gold_q.get("price", 0) or 0)
        gold_change  = float(gold_q.get("changesPercentage", 0) or 0)
        gold         = inr_per_10g(gold_usd)

        if nifty == 0 or sensex == 0:
            raise ProviderError("FMP returned zero prices — response may be malformed")

        trend = derive_trend(nifty_change, sensex_change, gold_change)
        logger.info(
            "FMP fetched: nifty=%.2f sensex=%.2f gold=%.2f trend=%s",
            nifty, sensex, gold, trend,
        )

        return {
            "nifty":        round(nifty, 2),
            "sensex":       round(sensex, 2),
            "gold":         round(gold, 2),
            "niftyChange":  round(nifty_change, 4),
            "sensexChange": round(sensex_change, 4),
            "goldChange":   round(gold_change, 4),
            "trend":        trend,
            "updatedAt":    datetime.now(timezone.utc).isoformat(),
            "source":       self.name,
        }
