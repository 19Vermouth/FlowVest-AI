from __future__ import annotations

import logging
from typing import Any, Dict

from backend.agents.base import BaseAgent
from backend.services.advisor import generate_advisor_reasoning

logger = logging.getLogger(__name__)


class AdvisorAgent(BaseAgent):
    """Agent responsible for generating human-readable investment reasoning."""
    
    name: str = "advisor_agent"
    timeout: int = 45  # LLM calls may take longer
    
    async def run(self, input_data: Dict[str, Any], state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate investor memo based on allocation and analysis.
        
        Args:
            input_data: May contain additional context
            state: Should contain 'budget', 'risk', 'horizon', 'analysis', 'allocation'
            
        Returns:
            Dict with 'reasoning' and related fields
        """
        logger.info("AdvisorAgent: Generating investment reasoning...")
        
        # Extract required data from state
        budget = state.get("budget")
        risk = state.get("risk")
        horizon = state.get("horizon")
        analysis_summary = state.get("analysis", "")
        allocation = state.get("allocation", [])
        
        if not all([budget, risk, horizon, allocation]):
            raise ValueError("AdvisorAgent requires budget, risk, horizon, analysis, and allocation in state")
        
        # Generate reasoning (calls LLM via OpenRouter or falls back to local)
        advisor_result = await generate_advisor_reasoning(
            budget=budget,
            risk=risk,
            horizon=horizon,
            analysis_summary=analysis_summary,
            allocation=allocation,
        )
        
        logger.info(
            f"AdvisorAgent: Generated reasoning (source: {advisor_result.get('source', 'unknown')})"
        )
        
        return {
            "reasoning": advisor_result.get("reasoning", ""),
            "reasoning_source": advisor_result.get("source", "unknown"),
            "reasoning_full": advisor_result  # Keep full result for debugging
        }
