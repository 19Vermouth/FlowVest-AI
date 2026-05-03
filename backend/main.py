from __future__ import annotations

import os
from datetime import datetime, timezone

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from backend.db.database import Base, SessionLocal, engine
from backend.models.schemas import HealthResponse
from backend.routers.portfolio import router as portfolio_router


APP_VERSION = "1.0.0"
OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL", "deepseek/deepseek-chat-v3-0324")


def _allowed_origins() -> list[str]:
    raw = os.getenv("CORS_ORIGINS", "*")
    if raw.strip() == "*":
        return ["*"]
    return [origin.strip() for origin in raw.split(",") if origin.strip()]


app = FastAPI(
    title="FlowVest AI Backend",
    description="FastAPI backend for FlowVest AI portfolio generation.",
    version=APP_VERSION,
)

origins = _allowed_origins()
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=origins != ["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def on_startup() -> None:
    Base.metadata.create_all(bind=engine)


@app.get("/")
def root() -> dict:
    return {
        "name": "FlowVest AI Backend",
        "version": APP_VERSION,
        "docs": "/docs",
        "health": "/health",
    }


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    database_status = "offline"

    try:
        with SessionLocal() as session:
            session.execute(text("SELECT 1"))
        database_status = "online"
    except Exception:
        database_status = "offline"

    return HealthResponse(
        status="healthy" if database_status == "online" else "degraded",
        database=database_status,
        openrouter="configured" if os.getenv("OPENROUTER_API_KEY") else "not-configured",
        model=OPENROUTER_MODEL,
        timestamp=datetime.now(timezone.utc).isoformat(),
    )


app.include_router(portfolio_router)
