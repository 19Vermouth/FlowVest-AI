"""
backend/services/market.py
───────────────────────────
Thin service shim that delegates to the MarketDataManager.
Kept for backward-compat with any caller that imports fetch_market_snapshot.
"""
from __future__ import annotations

import asyncio


def fetch_market_snapshot(force_refresh: bool = False) -> dict:
    """
    Synchronous wrapper used by Celery task code.
    Runs the async manager in a new event-loop slice.
    """
    from backend.providers.manager import market_manager
    return asyncio.run(market_manager.get_market_data(force_refresh=force_refresh))


async def afetch_market_snapshot(force_refresh: bool = False) -> dict:
    """Async version for use inside async contexts (tests, ASGI endpoints)."""
    from backend.providers.manager import market_manager
    return await market_manager.get_market_data(force_refresh=force_refresh)
