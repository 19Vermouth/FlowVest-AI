"""
backend/middleware/rate_limit.py
─────────────────────────────────
Per-user + global rate limiting backed by Redis (via slowapi + limits).

• Per-user:  RATE_LIMIT_PER_MINUTE requests/min on protected POST endpoints
• Global:    RATE_LIMIT_GLOBAL_PER_MINUTE requests/min across entire API

Usage:
    from backend.middleware.rate_limit import limiter, per_user_limit

    # In main.py:
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

    # In a route:
    @router.post("/create")
    @limiter.limit(per_user_limit)
    async def create(request: Request, ...):
"""
from __future__ import annotations

import logging

from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from backend.config import settings
from backend.middleware.auth import get_current_user_id   # noqa: F401 — re-export

logger = logging.getLogger(__name__)


def _key_from_user_id_or_ip(request) -> str:
    """
    Rate-limit key:
    • Authenticated requests → keyed on Firebase uid (attached to request.state)
    • Unauthenticated requests → fall back to IP (for health / docs endpoints)
    """
    uid = getattr(getattr(request, "state", None), "user_id", None)
    if uid:
        return f"user:{uid}"
    return f"ip:{get_remote_address(request)}"


limiter = Limiter(
    key_func=_key_from_user_id_or_ip,
    storage_uri=settings.REDIS_URL,
    default_limits=[f"{settings.RATE_LIMIT_GLOBAL_PER_MINUTE}/minute"],
)

# Convenience string used in route decorators
per_user_limit: str = f"{settings.RATE_LIMIT_PER_MINUTE}/minute"

__all__ = [
    "limiter",
    "per_user_limit",
    "RateLimitExceeded",
    "_rate_limit_exceeded_handler",
]
