from __future__ import annotations

import abc
import logging
import time
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class AgentError(Exception):
    """Custom exception for agent execution errors."""
    pass


class BaseAgent(abc.ABC):
    """Abstract base class for all agents in the orchestration system."""
    
    name: str = "base_agent"
    timeout: int = 30  # seconds
    max_retries: int = 2
    
    @abc.abstractmethod
    async def run(self, input_data: Dict[str, Any], state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute the agent's logic.
        
        Args:
            input_data: The input specific to this agent
            state: Shared state across all agents in the pipeline
            
        Returns:
            Dict containing the agent's output to be merged into the state
        """
        pass
    
    async def execute_with_retry(
        self, input_data: Dict[str, Any], state: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Execute the agent with retry logic and timeout handling.
        
        Returns:
            Agent output
            
        Raises:
            AgentError: If all retries fail
        """
        import asyncio
        
        last_error = None
        
        for attempt in range(self.max_retries + 1):
            try:
                start_time = time.time()
                logger.info(f"Agent {self.name} starting (attempt {attempt + 1})")
                
                # Execute with timeout
                try:
                    result = await asyncio.wait_for(
                        self.run(input_data, state),
                        timeout=self.timeout
                    )
                except asyncio.TimeoutError:
                    raise TimeoutError(f"Agent {self.name} timed out after {self.timeout}s")
                
                elapsed = time.time() - start_time
                logger.info(f"Agent {self.name} completed in {elapsed:.2f}s")
                
                # Add metadata to result
                if isinstance(result, dict):
                    result["_metadata"] = {
                        "agent": self.name,
                        "attempt": attempt + 1,
                        "elapsed_seconds": elapsed,
                        "status": "success",
                        "timeout_seconds": self.timeout
                    }
                return result
                
            except Exception as e:
                last_error = e
                elapsed = time.time() - start_time if 'start_time' in locals() else 0
                logger.warning(
                    f"Agent {self.name} failed (attempt {attempt + 1}): {str(e)}"
                )
                
                if attempt < self.max_retries:
                    wait_time = 2 ** attempt  # Exponential backoff
                    logger.info(f"Retrying in {wait_time}s...")
                    await asyncio.sleep(wait_time)
                    
        # All retries failed
        error_msg = f"Agent {self.name} failed after {self.max_retries + 1} attempts: {str(last_error)}"
        logger.error(error_msg)
        raise AgentError(error_msg) from last_error
