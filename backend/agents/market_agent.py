"""
backend/agents/market_agent.py  (v2)
──────────────────────────────────────
Fully decoupled from yfinance — delegates to MarketDataManager which handles
multi-provider failover, retries, and TTL caching.
"""
from __future__ import annotations

import logging
from typing import Any, Dict

from backend.agents.base import BaseAgent
from backend.providers.manager import market_manager

logger = logging.getLogger(__name__)


class MarketAgent(BaseAgent):
    name:        str = "market_agent"
    timeout:     int = 20   # MarketDataManager has its own per-provider timeouts
    max_retries: int = 1    # One re-attempt at the agent level (manager already retries)

    async def run(
        self,
        input_data: Dict[str, Any],
        state:      Dict[str, Any],
    ) -> Dict[str, Any]:
        logger.info("MarketAgent v2: fetching via MarketDataManager...")

        force_refresh = input_data.get("force_refresh", False)

        # Honour cached data already present in shared state (e.g. PlannerAgent
        # may decide to reuse market data from a previous execution in the same run)
        if "market_data" in state and not force_refresh:
            logger.info("MarketAgent v2: using market_data already in shared state")
            return {
                "market_data":   state["market_data"],
                "market_source": state["market_data"].get("source", "state-cache"),
                "market_cache_hit": True,
            }

        snapshot = await market_manager.get_market_data(force_refresh=force_refresh)

        logger.info(
            "MarketAgent v2: fetched | source=%s nifty=%.2f sensex=%.2f gold=%.2f",
            snapshot.get("source"), snapshot.get("nifty"), snapshot.get("sensex"), snapshot.get("gold"),
        )

        return {
            "market_data":   snapshot,
            "market_source": snapshot.get("source", "unknown"),
            "market_cache_hit": False,
        }
