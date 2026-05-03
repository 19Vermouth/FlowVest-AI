"""
backend/config.py
─────────────────
Single source of truth for every environment variable in the system.
Use `from backend.config import settings` anywhere.
"""
from __future__ import annotations

from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── Application ───────────────────────────────────────────────────────────
    APP_VERSION: str = "2.0.0"
    APP_NAME: str = "FlowVest AI"
    APP_URL: str = "http://localhost:3000"
    CORS_ORIGINS: str = "*"
    DEBUG: bool = False

    # ── Database ──────────────────────────────────────────────────────────────
    DATABASE_URL: str = "sqlite:///./flowvest.db"
    DB_POOL_SIZE: int = 5
    DB_MAX_OVERFLOW: int = 10

    # ── Redis / Celery ────────────────────────────────────────────────────────
    REDIS_URL: str = "redis://localhost:6379/0"
    CELERY_BROKER_URL: str = "redis://localhost:6379/0"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/1"
    CELERY_TASK_SOFT_TIME_LIMIT: int = 300   # seconds — warn at 5 min
    CELERY_TASK_TIME_LIMIT: int = 360        # hard kill at 6 min

    # ── Firebase ──────────────────────────────────────────────────────────────
    FIREBASE_PROJECT_ID: str = ""
    # Optional: path to a service-account JSON file.
    # If unset, the SDK tries Application Default Credentials (ADC).
    GOOGLE_APPLICATION_CREDENTIALS: str = ""
    # Set to "true" in development to skip token verification entirely.
    AUTH_DISABLED: bool = False

    # ── OpenRouter / LLM ──────────────────────────────────────────────────────
    OPENROUTER_API_KEY: str = ""
    OPENROUTER_MODEL: str = "deepseek/deepseek-chat-v3-0324"
    OPENROUTER_FALLBACK_MODEL: str = "openai/gpt-4o-mini"
    LLM_MAX_TOKENS_ANALYSIS: int = 220
    LLM_MAX_TOKENS_ADVISOR: int = 280
    LLM_TEMPERATURE_ANALYSIS: float = 0.4
    LLM_TEMPERATURE_ADVISOR: float = 0.45
    LLM_CACHE_TTL: int = 600       # seconds — cache identical prompts for 10 min

    # ── Market data providers ────────────────────────────────────────────────
    ALPHA_VANTAGE_API_KEY: str = ""
    FMP_API_KEY: str = ""
    MARKET_CACHE_TTL: int = 300    # seconds — 5 min

    # ── Rate limiting ────────────────────────────────────────────────────────
    RATE_LIMIT_PER_MINUTE: int = 10          # per user, POST endpoints
    RATE_LIMIT_GLOBAL_PER_MINUTE: int = 200  # entire API

    # ── Versioning / audit ────────────────────────────────────────────────────
    MODEL_VERSION: str = "v2"
    PROMPT_VERSION: str = "v1"
    ALLOCATION_VERSION: str = "v1"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()


# Module-level singleton so `from backend.config import settings` just works.
settings = get_settings()
