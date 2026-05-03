from __future__ import annotations

import logging
from typing import Any, Dict

from backend.agents.base import BaseAgent
from backend.services.allocation import build_allocation

logger = logging.getLogger(__name__)


class AllocationAgent(BaseAgent):
    """Agent responsible for rule-based asset allocation."""
    
    name: str = "allocation_agent"
    timeout: int = 10
    
    async def run(self, input_data: Dict[str, Any], state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Calculate portfolio allocation based on user inputs and analysis.
        
        Args:
            input_data: Should contain 'budget', 'risk', 'horizon'
            state: May contain 'analysis' for context
            
        Returns:
            Dict with 'allocation', 'cadence', 'summary', etc.
        """
        logger.info("AllocationAgent: Calculating portfolio allocation...")
        
        # Extract required data
        budget = input_data.get("budget") or state.get("budget")
        risk = input_data.get("risk") or state.get("risk")
        horizon = input_data.get("horizon") or state.get("horizon")
        
        if budget is None or not risk or not horizon:
            raise ValueError("AllocationAgent requires 'budget', 'risk', and 'horizon'")
        
        # Build allocation using rule-based engine
        allocation_result = build_allocation(budget, risk, horizon)
        
        logger.info(
            f"AllocationAgent: Generated allocation with {len(allocation_result.get('allocation', []))} slices"
        )
        
        return {
            "allocation": allocation_result.get("allocation", []),
            "cadence": allocation_result.get("cadence", "Quarterly"),
            "portfolio_summary": allocation_result.get("summary", ""),
        }
