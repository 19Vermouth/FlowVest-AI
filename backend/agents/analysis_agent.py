from __future__ import annotations

import logging
from typing import Any, Dict

from backend.agents.base import BaseAgent
from backend.services.analysis import generate_market_analysis

logger = logging.getLogger(__name__)


class AnalysisAgent(BaseAgent):
    """Agent responsible for analyzing market data against user profile."""
    
    name: str = "analysis_agent"
    timeout: int = 45  # LLM calls may take longer
    
    async def run(self, input_data: Dict[str, Any], state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Analyze market conditions based on user's risk profile and market data.
        
        Args:
            input_data: Should contain 'risk' and 'horizon'
            state: Should contain 'market_data'
            
        Returns:
            Dict with 'analysis' key containing analysis summary
        """
        logger.info("AnalysisAgent: Starting market analysis...")
        
        # Extract required data
        risk = input_data.get("risk") or state.get("risk")
        horizon = input_data.get("horizon") or state.get("horizon")
        market_data = state.get("market_data")
        
        if not risk or not horizon:
            raise ValueError("AnalysisAgent requires 'risk' and 'horizon' in input or state")
        
        if not market_data:
            raise ValueError("AnalysisAgent requires 'market_data' in state")
        
        # Generate analysis (this calls LLM via OpenRouter or falls back to local)
        analysis_result = await generate_market_analysis(
            market_data, risk, horizon
        )
        
        logger.info(
            f"AnalysisAgent: Generated analysis (source: {analysis_result.get('source', 'unknown')})"
        )
        
        return {
            "analysis": analysis_result.get("summary", ""),
            "analysis_source": analysis_result.get("source", "unknown"),
            "analysis_full": analysis_result  # Keep full result for debugging
        }
