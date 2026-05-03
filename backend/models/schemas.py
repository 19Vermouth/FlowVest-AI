"""
backend/models/schemas.py
──────────────────────────
SQLAlchemy ORM models (tables) + Pydantic request/response models.

New in v2:
  ● Execution.celery_task_id   – links DB row → Celery task (resumable)
  ● Execution.model_version / prompt_version / allocation_version – audit trail
  ● RateLimitLog               – per-user rate-limit counters
  ● AgentRun persists partial pipeline state for crash-resumption
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import DateTime, Float, Index, Integer, JSON, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from backend.db.database import Base


# ─── Type aliases ─────────────────────────────────────────────────────────────
RiskLevel      = Literal["Low", "Medium", "High"]
HorizonLevel   = Literal["Short", "Medium", "Long"]
PortfolioStatus = Literal["running", "completed", "failed", "completed_with_errors"]
Trend          = Literal["Up", "Flat", "Down"]


# ═══════════════════════════════════════════════════════════════════════════════
# ORM MODELS
# ═══════════════════════════════════════════════════════════════════════════════

class Portfolio(Base):
    __tablename__ = "portfolios"

    id:               Mapped[str]                      = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id:          Mapped[str]                      = mapped_column(String(255), index=True, nullable=False)
    budget:           Mapped[float]                    = mapped_column(Float, nullable=False)
    risk:             Mapped[str]                      = mapped_column(String(20), nullable=False)
    horizon:          Mapped[str]                      = mapped_column(String(20), nullable=False)
    status:           Mapped[str]                      = mapped_column(String(30), nullable=False, default="completed")
    allocation:       Mapped[list[dict[str, Any]] | None] = mapped_column(JSON, nullable=True)
    reasoning:        Mapped[str | None]               = mapped_column(Text, nullable=True)
    analysis_summary: Mapped[str | None]               = mapped_column(Text, nullable=True)
    market_data:      Mapped[dict[str, Any] | None]    = mapped_column(JSON, nullable=True)
    steps_data:       Mapped[list[dict[str, Any]]]     = mapped_column(JSON, nullable=False, default=list)
    cadence:          Mapped[str | None]               = mapped_column(String(100), nullable=True)
    # ── Audit / versioning ─────────────────────────────────────────────────
    model_version:      Mapped[str | None]             = mapped_column(String(20), nullable=True)
    prompt_version:     Mapped[str | None]             = mapped_column(String(20), nullable=True)
    allocation_version: Mapped[str | None]             = mapped_column(String(20), nullable=True)
    # ── Risk-engine scores ────────────────────────────────────────────────
    portfolio_score:      Mapped[float | None]         = mapped_column(Float, nullable=True)
    diversification_score: Mapped[float | None]        = mapped_column(Float, nullable=True)
    volatility_score:     Mapped[float | None]         = mapped_column(Float, nullable=True)
    validation_errors:    Mapped[list[dict] | None]    = mapped_column(JSON, nullable=True)
    validation_warnings:  Mapped[list[dict] | None]    = mapped_column(JSON, nullable=True)
    created_at:         Mapped[datetime]               = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class Execution(Base):
    """
    Tracks one full pipeline run.

    The celery_task_id column links this DB row to a Celery task so:
      • Status can always be recovered from DB (no in-memory dict needed)
      • A crashed worker can re-hydrate and continue from the last agent
    """
    __tablename__ = "executions"
    __table_args__ = (
        Index("ix_executions_user_status", "user_id", "status"),
    )

    id:             Mapped[str]                      = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    portfolio_id:   Mapped[str | None]               = mapped_column(String(36), nullable=True)
    user_id:        Mapped[str]                      = mapped_column(String(255), index=True, nullable=False)
    celery_task_id: Mapped[str | None]               = mapped_column(String(255), index=True, nullable=True)
    status:         Mapped[str]                      = mapped_column(String(30), default="pending")
    input_data:     Mapped[dict[str, Any] | None]    = mapped_column(JSON, nullable=True)
    # partial_state allows a restarted worker to skip already-done agents
    partial_state:  Mapped[dict[str, Any] | None]    = mapped_column(JSON, nullable=True)
    final_state:    Mapped[dict[str, Any] | None]    = mapped_column(JSON, nullable=True)
    metadata_:      Mapped[dict[str, Any] | None]    = mapped_column(JSON, nullable=True, name="metadata")
    error:          Mapped[str | None]               = mapped_column(Text, nullable=True)
    retry_count:    Mapped[int]                      = mapped_column(Integer, default=0)
    # ── Audit ─────────────────────────────────────────────────────────────
    model_version:      Mapped[str | None]           = mapped_column(String(20), nullable=True)
    prompt_version:     Mapped[str | None]           = mapped_column(String(20), nullable=True)
    allocation_version: Mapped[str | None]           = mapped_column(String(20), nullable=True)
    created_at:     Mapped[datetime]                 = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at:     Mapped[datetime | None]          = mapped_column(DateTime(timezone=True), nullable=True)


class AgentRun(Base):
    """
    Persists the output of each agent inside a pipeline run.
    Enables crash recovery: if execution restarts, agents whose rows already
    exist with status='success' are skipped.
    """
    __tablename__ = "agent_runs"
    __table_args__ = (
        Index("ix_agent_runs_exec_agent", "execution_id", "agent_name"),
    )

    id:           Mapped[int]                      = mapped_column(Integer, primary_key=True, autoincrement=True)
    execution_id: Mapped[str]                      = mapped_column(String(36), index=True, nullable=False)
    agent_name:   Mapped[str]                      = mapped_column(String(60), nullable=False)
    status:       Mapped[str]                      = mapped_column(String(20), nullable=False)  # success / failed
    input_state:  Mapped[dict[str, Any] | None]    = mapped_column(JSON, nullable=True)
    output_state: Mapped[dict[str, Any] | None]    = mapped_column(JSON, nullable=True)
    error:        Mapped[str | None]               = mapped_column(Text, nullable=True)
    attempt:      Mapped[int]                      = mapped_column(Integer, default=1)
    start_time:   Mapped[datetime | None]          = mapped_column(DateTime(timezone=True), nullable=True)
    end_time:     Mapped[datetime | None]          = mapped_column(DateTime(timezone=True), nullable=True)
    elapsed_seconds: Mapped[float | None]          = mapped_column(Float, nullable=True)


class RateLimitLog(Base):
    """Per-user sliding-window counter, also used by slowapi Redis backend."""
    __tablename__ = "rate_limit_logs"

    id:        Mapped[int]    = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id:   Mapped[str]   = mapped_column(String(255), index=True, nullable=False)
    endpoint:  Mapped[str]   = mapped_column(String(120), nullable=False)
    hit_at:    Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


# ═══════════════════════════════════════════════════════════════════════════════
# PYDANTIC REQUEST / RESPONSE MODELS
# ═══════════════════════════════════════════════════════════════════════════════

class MarketSnapshot(BaseModel):
    nifty:        float
    sensex:       float
    gold:         float
    trend:        Trend
    niftyChange:  float
    sensexChange: float
    goldChange:   float
    updatedAt:    str
    source:       str = "fallback"


class AllocationSlice(BaseModel):
    label: str
    value: int
    color: str
    note:  str


class PipelineStep(BaseModel):
    agent:  str
    status: str
    detail: str


class PortfolioCreateRequest(BaseModel):
    budget:  float = Field(gt=0, description="Investment corpus in INR")
    risk:    RiskLevel
    horizon: HorizonLevel


class PortfolioResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id:                str
    user_id:           str
    budget:            float
    risk:              RiskLevel
    horizon:           HorizonLevel
    status:            PortfolioStatus
    allocation:        list[AllocationSlice]            = Field(default_factory=list)
    reasoning:         str | None                       = None
    analysis_summary:  str | None                       = None
    market_data:       MarketSnapshot | dict[str, Any] | None = None
    steps_data:        list[PipelineStep | dict[str, Any]]    = Field(default_factory=list)
    cadence:           str | None                       = None
    portfolio_score:   float | None                     = None
    # Audit fields
    model_version:     str | None                       = None
    prompt_version:    str | None                       = None
    allocation_version: str | None                      = None
    created_at:        datetime


class ExecutionStatusResponse(BaseModel):
    execution_id: str
    status:       str
    portfolio_id: str | None         = None
    celery_task_id: str | None       = None
    retry_count:  int                = 0
    final_state:  dict[str, Any] | None = None
    metadata:     dict[str, Any] | None = None
    error:        str | None         = None
    created_at:   datetime | None    = None
    updated_at:   datetime | None    = None


class DeleteResponse(BaseModel):
    detail: str


class HealthResponse(BaseModel):
    status:     str
    database:   str
    redis:     str | None = None
    celery:    str | None = None
    openrouter: str
    model:     str
    timestamp: str
