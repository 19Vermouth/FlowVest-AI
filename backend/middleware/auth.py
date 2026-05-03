"""
backend/middleware/auth.py
──────────────────────────
Production JWT authentication via Firebase Admin SDK.

• Verifies every incoming Firebase ID-token (Bearer <token>).
• Extracts the verified uid and attaches it to request.state.user_id.
• Raises HTTP 401 for missing / invalid / expired tokens.
• Can be disabled via AUTH_DISABLED=true (local dev only — NEVER production).

Usage in a route:
    @router.post("/create")
    async def create(user_id: str = Depends(get_current_user_id)):
        ...
"""
from __future__ import annotations

import logging
from functools import lru_cache
from typing import Optional

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from backend.config import settings

logger = logging.getLogger(__name__)

_bearer = HTTPBearer(auto_error=False)


# ── Firebase Admin SDK initialisation (lazy, singleton) ───────────────────────

@lru_cache(maxsize=1)
def _get_firebase_app():
    """
    Initialise Firebase Admin SDK once.
    Returns None if SDK is unavailable or project-id is not configured.
    """
    try:
        import firebase_admin
        from firebase_admin import credentials

        if firebase_admin._apps:
            return firebase_admin.get_app()

        if settings.GOOGLE_APPLICATION_CREDENTIALS:
            cred = credentials.Certificate(settings.GOOGLE_APPLICATION_CREDENTIALS)
        else:
            # Application Default Credentials (works on GCP, Cloud Run, etc.)
            cred = credentials.ApplicationDefault()

        return firebase_admin.initialize_app(
            cred,
            {"projectId": settings.FIREBASE_PROJECT_ID or None},
        )
    except Exception as exc:
        logger.warning(
            "Firebase Admin SDK could not be initialised (%s). "
            "Set GOOGLE_APPLICATION_CREDENTIALS or use AUTH_DISABLED=true "
            "for local development.",
            exc,
        )
        return None


def _verify_firebase_token(token: str) -> dict:
    """
    Verify a Firebase ID-token and return the decoded claims dict.
    Raises ValueError on any verification failure.
    """
    try:
        from firebase_admin import auth as firebase_auth

        _get_firebase_app()  # ensure app is initialised
        decoded = firebase_auth.verify_id_token(token, check_revoked=True)
        return decoded
    except Exception as exc:
        raise ValueError(f"Token verification failed: {exc}") from exc


# ── Public FastAPI dependency ──────────────────────────────────────────────────

async def get_current_user_id(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_bearer),
) -> str:
    """
    FastAPI dependency that returns the verified Firebase uid.

    Priority order:
    1. AUTH_DISABLED=true  → trust 'x-demo-user' header (dev only)
    2. Bearer <firebase-id-token> → verify with Firebase Admin SDK
    3. No token / bad token → HTTP 401
    """
    # ── Developer bypass (never use in production) ─────────────────────────
    if settings.AUTH_DISABLED:
        demo_uid = (
            request.headers.get("x-demo-user")
            or request.headers.get("x-user-id")
            or "dev-user"
        )
        logger.warning(
            "AUTH_DISABLED=true — skipping token verification. uid=%s", demo_uid
        )
        request.state.user_id = demo_uid
        return demo_uid

    # ── Require Bearer token ───────────────────────────────────────────────
    if not credentials or not credentials.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authentication token.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    raw_token = credentials.credentials

    try:
        claims = _verify_firebase_token(raw_token)
    except ValueError as exc:
        logger.warning("JWT verification failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired authentication token.",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    uid: str = claims.get("uid") or claims.get("sub", "")
    if not uid:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token does not contain a user identifier.",
        )

    request.state.user_id = uid
    logger.debug("Authenticated user uid=%s", uid)
    return uid
