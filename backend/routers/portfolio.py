from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from backend.db.database import SessionLocal, get_db
from backend.models.schemas import (
    DeleteResponse,
    Execution,
    Portfolio,
    PortfolioCreateRequest,
    PortfolioResponse,
)
from backend.orchestrator.orchestrator import Orchestrator

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/portfolio", tags=["portfolio"])

# In-memory store for orchestrator instances (for MVP)
# In production, use Redis or similar
orchestrator_store: Dict[str, Orchestrator] = {}


def _request_user_id(request: Request) -> str:
    return (
        request.headers.get("x-user-id")
        or request.headers.get("x-clerk-user-id")
        or request.headers.get("x-demo-user")
        or "demo-user"
    )


async def _run_pipeline(
    execution_id: str,
    input_data: Dict[str, Any],
    user_id: str,
) -> None:
    """
    Run the orchestrator pipeline and update DB records.
    This function is called as a background task.
    Creates its own DB session.
    """
    db = SessionLocal()
    try:
        # Create orchestrator
        orchestrator = Orchestrator(execution_id=execution_id)
        orchestrator_store[execution_id] = orchestrator
        
        # Update execution status to running
        execution = db.query(Execution).filter(Execution.id == execution_id).first()
        if execution:
            execution.status = "running"
            execution.updated_at = datetime.now(timezone.utc)
            db.commit()
        
        # Run pipeline
        logger.info(f"Starting pipeline execution {execution_id}")
        final_state = await orchestrator.run(input_data)
        
        # Update execution with final state
        if execution:
            execution.status = orchestrator.get_metadata().get("status", "completed")
            execution.final_state = final_state
            execution.metadata_ = orchestrator.get_metadata()
            execution.updated_at = datetime.now(timezone.utc)
            db.commit()
        
        # Create Portfolio record from final state
        portfolio = Portfolio(
            user_id=user_id,
            budget=input_data.get("budget", 0),
            risk=input_data.get("risk", "Medium"),
            horizon=input_data.get("horizon", "Long"),
            status="completed",
            allocation=final_state.get("allocation"),
            reasoning=final_state.get("reasoning"),
            analysis_summary=final_state.get("analysis"),
            market_data=final_state.get("market_data"),
            steps_data=final_state.get("_execution_metadata", {}).get("agents_executed", []),
            cadence=final_state.get("cadence"),
        )
        db.add(portfolio)
        db.commit()
        db.refresh(portfolio)
        
        # Link execution to portfolio
        if execution:
            execution.portfolio_id = portfolio.id
            db.commit()
        
        logger.info(f"Pipeline {execution_id} completed. Portfolio created: {portfolio.id}")
        
        # Cleanup orchestrator from memory
        if execution_id in orchestrator_store:
            del orchestrator_store[execution_id]
            
    except Exception as e:
        logger.error(f"Pipeline {execution_id} failed: {str(e)}")
        # Update execution status to failed
        try:
            db = SessionLocal()  # New session in case the first one closed
            execution = db.query(Execution).filter(Execution.id == execution_id).first()
            if execution:
                execution.status = "failed"
                execution.error = str(e)
                execution.updated_at = datetime.now(timezone.utc)
                db.commit()
        except Exception as db_error:
            logger.error(f"Failed to update execution status: {str(db_error)}")
        raise
    finally:
        db.close()


@router.get("/list", response_model=List[PortfolioResponse])
def list_portfolios(request: Request, db: Session = Depends(get_db)) -> List[PortfolioResponse]:
    user_id = _request_user_id(request)
    records = (
        db.query(Portfolio)
        .filter(Portfolio.user_id == user_id)
        .order_by(Portfolio.created_at.desc())
        .all()
    )
    return [PortfolioResponse.model_validate(record) for record in records]


@router.get("/{portfolio_id}", response_model=PortfolioResponse)
def get_portfolio(portfolio_id: str, request: Request, db: Session = Depends(get_db)) -> PortfolioResponse:
    user_id = _request_user_id(request)
    record = (
        db.query(Portfolio)
        .filter(Portfolio.id == portfolio_id, Portfolio.user_id == user_id)
        .first()
    )
    
    if not record:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Portfolio not found")
    
    return PortfolioResponse.model_validate(record)


@router.post("/create", status_code=status.HTTP_202_ACCEPTED)
async def create_portfolio(
    payload: PortfolioCreateRequest,
    background_tasks: BackgroundTasks,
    request: Request,
    db: Session = Depends(get_db),
):
    """Create a new portfolio using the multi-agent orchestrator (async)."""
    user_id = _request_user_id(request)
    execution_id = str(uuid.uuid4())
    
    # Create Execution record
    execution = Execution(
        id=execution_id,
        user_id=user_id,
        status="pending",
        input_data=payload.model_dump(),
    )
    db.add(execution)
    db.commit()
    
    # Start background task
    input_data = payload.model_dump()
    background_tasks.add_task(_run_pipeline, execution_id, input_data, user_id)
    
    return {"execution_id": execution_id, "status": "pending"}


@router.get("/execution/{execution_id}")
def get_execution(execution_id: str, request: Request, db: Session = Depends(get_db)):
    """Get execution status and state."""
    user_id = _request_user_id(request)
    execution = (
        db.query(Execution)
        .filter(Execution.id == execution_id, Execution.user_id == user_id)
        .first()
    )
    
    if not execution:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Execution not found")
    
    # If orchestrator is still running, get live state
    if execution_id in orchestrator_store:
        live_state = orchestrator_store[execution_id].get_state()
        return {
            "execution_id": execution_id,
            "status": "running",
            "live_state": live_state,
            "metadata": orchestrator_store[execution_id].get_metadata(),
        }
    
    # Return stored state
    return {
        "execution_id": execution_id,
        "status": execution.status,
        "portfolio_id": execution.portfolio_id,
        "final_state": execution.final_state,
        "metadata": execution.metadata_,
        "error": execution.error,
        "created_at": execution.created_at,
        "updated_at": execution.updated_at,
    }


@router.delete("/{portfolio_id}", response_model=DeleteResponse)
def delete_portfolio(portfolio_id: str, request: Request, db: Session = Depends(get_db)) -> DeleteResponse:
    user_id = _request_user_id(request)
    record = (
        db.query(Portfolio)
        .filter(Portfolio.id == portfolio_id, Portfolio.user_id == user_id)
        .first()
    )
    
    if not record:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Portfolio not found")
    
    db.delete(record)
    db.commit()
    return DeleteResponse(detail=f"Deleted portfolio {portfolio_id}")
