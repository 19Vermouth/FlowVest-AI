"""
backend/providers/alpha_vantage.py
────────────────────────────────────
Primary market-data provider: Alpha Vantage

Fetches:
  • NIFTY 50   via GLOBAL_QUOTE symbol "^NSEI"
  • SENSEX     via GLOBAL_QUOTE symbol "^BSESN"
  • Gold (XAU) via CURRENCY_EXCHANGE_RATE XAU→INR, then converted to INR/10g

Alpha Vantage free tier: 25 requests/day, 5 requests/min.
The MarketDataManager's cache (TTL=300s) prevents hitting that limit for
normal traffic patterns.

API docs: https://www.alphavantage.co/documentation/
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
    pct_change,
)

logger = logging.getLogger(__name__)

AV_BASE = "https://www.alphavantage.co/query"


class AlphaVantageProvider(BaseMarketProvider):
    name: str = "alpha_vantage"

    def __init__(self) -> None:
        self._api_key = settings.ALPHA_VANTAGE_API_KEY

    async def _fetch_global_quote(self, client: httpx.AsyncClient, symbol: str) -> tuple[float, float]:
        """Return (price, day_pct_change) for the given symbol."""
        resp = await client.get(
            AV_BASE,
            params={
                "function": "GLOBAL_QUOTE",
                "symbol": symbol,
                "apikey": self._api_key,
            },
            timeout=12.0,
        )
        resp.raise_for_status()
        data = resp.json()

        quote = data.get("Global Quote", {})
        price_str = quote.get("05. price")
        change_pct_str = quote.get("10. change percent", "0%").replace("%", "")

        if not price_str:
            raise ProviderError(f"Alpha Vantage returned empty quote for {symbol}: {data}")

        return float(price_str), float(change_pct_str)

    async def _fetch_gold_inr(self, client: httpx.AsyncClient) -> tuple[float, float]:
        """Return gold price in INR/10g and approximate day-change %."""
        # Alpha Vantage does not have a direct INR gold quote on free tier.
        # We fetch XAU/USD and then convert using a fixed FX rate.
        resp = await client.get(
            AV_BASE,
            params={
                "function": "CURRENCY_EXCHANGE_RATE",
                "from_currency": "XAU",
                "to_currency": "USD",
                "apikey": self._api_key,
            },
            timeout=12.0,
        )
        resp.raise_for_status()
        data = resp.json()

        rate_info = data.get("Realtime Currency Exchange Rate", {})
        rate_str = rate_info.get("5. Exchange Rate")

        if not rate_str:
            raise ProviderError(f"Alpha Vantage XAU/USD exchange rate missing: {data}")

        xau_usd = float(rate_str)
        gold_inr = inr_per_10g(xau_usd)

        # Alpha Vantage free tier does not return 24h gold change — approximate 0
        return gold_inr, 0.0

    async def fetch_market_data(self) -> MarketPayload:
        if not self._api_key:
            raise ProviderError("ALPHA_VANTAGE_API_KEY is not configured")

        async with httpx.AsyncClient() as client:
            nifty, nifty_change = await self._fetch_global_quote(client, "^NSEI")
            sensex, sensex_change = await self._fetch_global_quote(client, "^BSESN")
            gold, gold_change = await self._fetch_gold_inr(client)

        trend = derive_trend(nifty_change, sensex_change, gold_change)
        logger.info(
            "AlphaVantage fetched: nifty=%.2f sensex=%.2f gold=%.2f trend=%s",
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
