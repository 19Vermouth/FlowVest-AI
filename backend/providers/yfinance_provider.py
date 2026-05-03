"""
backend/providers/yfinance_provider.py
────────────────────────────────────────
Tertiary (fallback) market-data provider: yfinance (Yahoo Finance).

yfinance is reliable for daily OHLCV but subject to rate-limiting.
It is intentionally the last provider in the failover chain.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from backend.providers.base import (
    BaseMarketProvider,
    MarketPayload,
    ProviderError,
    derive_trend,
    inr_per_10g,
    pct_change,
)

logger = logging.getLogger(__name__)

NIFTY_SYMBOL  = "^NSEI"
SENSEX_SYMBOL = "^BSESN"
GOLD_SYMBOL   = "GC=F"   # Gold futures (USD/oz)


class YFinanceProvider(BaseMarketProvider):
    name: str = "yfinance"

    def _fetch_price_and_change(self, symbol: str) -> tuple[float, float]:
        """Synchronous yfinance call — run in a thread if needed."""
        try:
            import yfinance as yf
        except ImportError as exc:
            raise ProviderError("yfinance is not installed") from exc

        hist = yf.Ticker(symbol).history(period="5d", interval="1d", auto_adjust=False)
        closes = hist["Close"].dropna().tolist()

        if not closes:
            raise ProviderError(f"yfinance returned no data for {symbol}")

        current  = float(closes[-1])
        previous = float(closes[-2]) if len(closes) > 1 else current
        return current, pct_change(current, previous)

    async def fetch_market_data(self) -> MarketPayload:
        """
        yfinance is synchronous.  We call it directly here;
        in a Celery task context this runs in a thread pool via Celery's
        own executor, so it won't block the async event loop.
        """
        try:
            nifty,  nifty_change  = self._fetch_price_and_change(NIFTY_SYMBOL)
            sensex, sensex_change = self._fetch_price_and_change(SENSEX_SYMBOL)
            gold_usd, gold_change = self._fetch_price_and_change(GOLD_SYMBOL)
        except ProviderError:
            raise
        except Exception as exc:
            raise ProviderError(f"yfinance error: {exc}") from exc

        gold  = inr_per_10g(gold_usd)
        trend = derive_trend(nifty_change, sensex_change, gold_change)

        logger.info(
            "yfinance fetched: nifty=%.2f sensex=%.2f gold=%.2f trend=%s",
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
