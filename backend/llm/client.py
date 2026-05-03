"""
backend/llm/client.py
──────────────────────
Central LLM wrapper for all OpenRouter calls.

Features:
  ● Prompt-level in-process caching (SHA-256 key, configurable TTL)
  ● Token counting (estimated) + per-call cost tracking
  ● Per-model max_token enforcement
  ● Retry with exponential backoff
  ● Automatic fallback to a secondary model on 429 / 5xx
  ● Structured result: {content, model, prompt_tokens, estimated_cost, cached, source}
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import time
from typing import Any, Optional

import httpx

from backend.config import settings

logger = logging.getLogger(__name__)

# ─── Cost table (USD per 1k tokens) ──────────────────────────────────────────
# Update when model pricing changes. All approximate.
_COST_PER_1K_TOKENS: dict[str, float] = {
    "deepseek/deepseek-chat-v3-0324": 0.00014,
    "openai/gpt-4o-mini":             0.00015,
    "openai/gpt-4o":                  0.005,
    "default":                         0.00020,
}

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"

# ─── In-process prompt cache ─────────────────────────────────────────────────
_prompt_cache: dict[str, tuple[dict, float]] = {}   # key → (result, timestamp)

# ─── Cumulative cost tracker ──────────────────────────────────────────────────
_total_tokens_used: int  = 0
_total_cost_usd: float   = 0.0


def _cache_key(messages: list[dict], model: str, max_tokens: int, temperature: float) -> str:
    payload = json.dumps(
        {"messages": messages, "model": model, "max_tokens": max_tokens, "temperature": temperature},
        sort_keys=True,
    )
    return hashlib.sha256(payload.encode()).hexdigest()


def _estimate_tokens(text: str) -> int:
    """Rough approximation: 1 token ≈ 4 characters."""
    return max(1, len(text) // 4)


def _compute_cost(model: str, total_tokens: int) -> float:
    rate = _COST_PER_1K_TOKENS.get(model, _COST_PER_1K_TOKENS["default"])
    return round((total_tokens / 1000) * rate, 8)


def _update_totals(tokens: int, cost: float) -> None:
    global _total_tokens_used, _total_cost_usd
    _total_tokens_used += tokens
    _total_cost_usd    += cost


def get_cost_summary() -> dict[str, Any]:
    return {
        "total_tokens_used": _total_tokens_used,
        "total_cost_usd":    round(_total_cost_usd, 6),
        "cache_entries":     len(_prompt_cache),
    }


async def _call_openrouter(
    messages:    list[dict],
    model:       str,
    max_tokens:  int,
    temperature: float,
) -> Optional[str]:
    """
    Single OpenRouter HTTP call.
    Returns the content string on success, None on non-retryable error.
    Raises httpx.HTTPStatusError for retryable statuses (429, 5xx).
    """
    if not settings.OPENROUTER_API_KEY:
        return None

    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(
            OPENROUTER_URL,
            headers={
                "Authorization": f"Bearer {settings.OPENROUTER_API_KEY}",
                "Content-Type":  "application/json",
                "HTTP-Referer":  settings.APP_URL,
                "X-Title":       settings.APP_NAME,
            },
            json={
                "model":       model,
                "messages":    messages,
                "temperature": temperature,
                "max_tokens":  max_tokens,
            },
        )
        resp.raise_for_status()
        data    = resp.json()
        content = data["choices"][0]["message"]["content"].strip()

        usage  = data.get("usage", {})
        tokens = usage.get("total_tokens") or _estimate_tokens(" ".join(m.get("content", "") for m in messages))
        cost   = _compute_cost(model, tokens)
        _update_totals(tokens, cost)

        logger.info(
            "LLM call OK | model=%s tokens=%d cost_usd=%.6f", model, tokens, cost
        )
        return content


async def call_llm(
    messages:    list[dict[str, str]],
    max_tokens:  int,
    temperature: float,
    purpose:     str = "generic",          # used only for log context
) -> dict[str, Any]:
    """
    Main entry point for all LLM calls.

    Returns:
        {
            "content":         str,
            "model":           str,
            "cached":          bool,
            "prompt_tokens":   int,
            "estimated_cost":  float,
            "source":          "openrouter" | "fallback",
        }
    """
    primary_model  = settings.OPENROUTER_MODEL
    fallback_model = settings.OPENROUTER_FALLBACK_MODEL

    key = _cache_key(messages, primary_model, max_tokens, temperature)

    # ── Cache check ────────────────────────────────────────────────────────
    if key in _prompt_cache:
        cached_result, cached_at = _prompt_cache[key]
        age = time.time() - cached_at
        if age < settings.LLM_CACHE_TTL:
            logger.info(
                "LLM cache HIT | purpose=%s age=%.1fs", purpose, age
            )
            return {**cached_result, "cached": True}
        else:
            del _prompt_cache[key]

    logger.info("LLM cache MISS | purpose=%s model=%s", purpose, primary_model)

    # ── Try primary model with retries ────────────────────────────────────
    content: Optional[str] = None
    used_model = primary_model

    for attempt, model in enumerate([primary_model, fallback_model]):
        for retry in range(3):
            try:
                content = await _call_openrouter(messages, model, max_tokens, temperature)
                used_model = model
                break
            except httpx.HTTPStatusError as exc:
                if exc.response.status_code in (429, 500, 502, 503, 504):
                    wait = 2 ** retry
                    logger.warning(
                        "LLM HTTP %d | model=%s retry=%d waiting=%ds",
                        exc.response.status_code, model, retry + 1, wait,
                    )
                    await asyncio.sleep(wait)
                else:
                    logger.error("LLM non-retryable HTTP error: %s", exc)
                    break   # move to fallback model
            except Exception as exc:
                logger.warning("LLM error | model=%s attempt=%d: %s", model, retry + 1, exc)
                await asyncio.sleep(2 ** retry)
        if content:
            break

    # ── Build result ──────────────────────────────────────────────────────
    if content:
        prompt_tokens = _estimate_tokens(" ".join(m.get("content", "") for m in messages))
        result = {
            "content":        content,
            "model":          used_model,
            "cached":         False,
            "prompt_tokens":  prompt_tokens,
            "estimated_cost": _compute_cost(used_model, prompt_tokens),
            "source":         "openrouter",
        }
        _prompt_cache[key] = (result, time.time())
        return result

    # ── All LLM attempts failed → caller will use local fallback ──────────
    logger.error("All LLM attempts failed | purpose=%s", purpose)
    return {
        "content":        "",
        "model":          "",
        "cached":         False,
        "prompt_tokens":  0,
        "estimated_cost": 0.0,
        "source":         "fallback",
    }
