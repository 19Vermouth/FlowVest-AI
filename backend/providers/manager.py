"""
backend/providers/manager.py
─────────────────────────────
MarketDataManager — failover + TTL cache + observability.

Priority chain:
  1. AlphaVantage  (primary   — requires ALPHA_VANTAGE_API_KEY)
  2. FMP           (secondary — requires FMP_API_KEY)
  3. yfinance      (tertiary  — no key needed but rate-limited)
  4. FallbackProvider (guaranteed, deterministic, never raises)

Caching:
  • An in-process dict cache with a 300-second TTL avoids hammering the
    providers for every portfolio request.
  • In a multi-worker Celery deployment, each worker process has its own
    cache.  A Redis cache (optional) can replace it for cross-worker sharing.

Observability:
  • Every provider attempt, failure, cache hit, and miss is logged at the
    appropriate level so the operations team can monitor data reliability.
"""
from __future__ import annotations

import asyncio
import logging
import time
from typing import Optional

from backend.config import settings
from backend.providers.alpha_vantage import AlphaVantageProvider
from backend.providers.base import BaseMarketProvider, MarketPayload
from backend.providers.fallback import FallbackProvider
from backend.providers.fmp import FMPProvider
from backend.providers.yfinance_provider import YFinanceProvider

logger = logging.getLogger(__name__)

# ─── Per-provider failure counters ────────────────────────────────────────────
_provider_failures: dict[str, int] = {}

# ─── In-process TTL cache ─────────────────────────────────────────────────────
_cache: Optional[MarketPayload] = None
_cache_ts: float = 0.0

_MAX_RETRIES_PER_PROVIDER = 2
_RETRY_BACKOFF_SECONDS     = [1, 2]   # wait 1s then 2s before giving up


async def _try_provider(provider: BaseMarketProvider, max_retries: int = _MAX_RETRIES_PER_PROVIDER) -> Optional[MarketPayload]:
    """
    Attempt to fetch from a single provider with exponential backoff.
    Returns None on failure instead of raising, so the manager can continue.
    """
    last_exc: Optional[Exception] = None

    for attempt in range(max_retries + 1):
        try:
            data = await provider.fetch_market_data()
            logger.info(
                "Market data SUCCESS | provider=%s attempt=%d",
                provider.name, attempt + 1,
            )
            _provider_failures[provider.name] = 0   # reset counter on success
            return data
        except Exception as exc:
            last_exc = exc
            _provider_failures[provider.name] = _provider_failures.get(provider.name, 0) + 1
            logger.warning(
                "Market data FAILURE | provider=%s attempt=%d/%d error=%s "
                "total_failures=%d",
                provider.name, attempt + 1, max_retries + 1, exc,
                _provider_failures[provider.name],
            )
            if attempt < max_retries:
                backoff = _RETRY_BACKOFF_SECONDS[min(attempt, len(_RETRY_BACKOFF_SECONDS) - 1)]
                logger.info("Retrying %s in %ds...", provider.name, backoff)
                await asyncio.sleep(backoff)

    logger.error(
        "Market data EXHAUSTED | provider=%s after %d attempts. Last error: %s",
        provider.name, max_retries + 1, last_exc,
    )
    return None


class MarketDataManager:
    """
    Manages the full provider failover chain.

    Instantiate once per Celery task (lightweight — no persistent connections).
    """

    def __init__(self) -> None:
        # Build priority-ordered provider list
        # Providers without configured API keys are still included but will
        # raise ProviderError immediately, which triggers the next provider.
        self._providers: list[BaseMarketProvider] = [
            AlphaVantageProvider(),
            FMPProvider(),
            YFinanceProvider(),
            # FallbackProvider is the guaranteed last resort
        ]
        self._fallback = FallbackProvider()
        self._ttl = settings.MARKET_CACHE_TTL

    def _cache_fresh(self) -> bool:
        return _cache is not None and (time.time() - _cache_ts) < self._ttl

    def _update_cache(self, data: MarketPayload) -> None:
        global _cache, _cache_ts
        _cache    = data
        _cache_ts = time.time()

    async def get_market_data(self, force_refresh: bool = False) -> MarketPayload:
        """
        Return market data.

        1. Cache hit  → return immediately.
        2. Cache miss → try each live provider in order.
        3. All fail   → return FallbackProvider output.
        """
        if not force_refresh and self._cache_fresh():
            logger.info(
                "Market cache HIT | age=%.1fs ttl=%ds source=%s",
                time.time() - _cache_ts, self._ttl, _cache.get("source"),
            )
            return dict(_cache)   # shallow copy so callers can't mutate cache

        logger.info("Market cache MISS | force_refresh=%s — fetching from providers", force_refresh)

        for provider in self._providers:
            result = await _try_provider(provider)
            if result is not None:
                self._update_cache(result)
                return result

        # All live providers failed — use deterministic fallback
        logger.error(
            "ALL live market providers failed. "
            "Failure counts: %s. Returning deterministic fallback.",
            _provider_failures,
        )
        fallback_data = await self._fallback.fetch_market_data()
        self._update_cache(fallback_data)
        return fallback_data

    @staticmethod
    def get_failure_stats() -> dict[str, int]:
        """Expose cumulative failure counters for the health endpoint."""
        return dict(_provider_failures)


# ─── Module-level singleton ───────────────────────────────────────────────────
market_manager = MarketDataManager()
