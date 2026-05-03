# ═══════════════════════════════════════════════════════════════════════════════
# FlowVest AI Backend — Production Dockerfile (v2.0)
# ═══════════════════════════════════════════════════════════════════════════════
# Multi-stage build for minimal image size.
# Supports: FastAPI backend, Celery worker, Flower monitoring UI
#
# Usage:
#   docker build -f backend/Dockerfile -t flowvest-backend .
#   docker run -p 8000:8000 --env-file .env flowvest-backend
# ═══════════════════════════════════════════════════════════════════════════════

# ── Stage 1: Build Dependencies ────────────────────────────────────────────────
FROM python:3.11-slim as builder

WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy and install Python dependencies
COPY backend/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r /tmp/requirements.txt

# ── Stage 2: Production Image ─────────────────────────────────────────────────
FROM python:3.11-slim as production

WORKDIR /app

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONFAULTHANDLER=1 \
    PATH="/app/venv/bin:$PATH"

# Install runtime dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    curl \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --create-home --shell /bin/bash app \
    && chown -R app:app /app

# Copy virtual environment from builder
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy application code
COPY --chown=app:app backend /app/backend

# Switch to non-root user
USER app

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Expose port
EXPOSE 8000

# Default command (override in docker-compose or k8s)
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]

# ═══════════════════════════════════════════════════════════════════════════════
# Alternative Commands (set via docker-compose or k8s):
#
# FastAPI Backend:
#   CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
#
# Celery Worker:
#   CMD ["celery", "-A", "backend.tasks.celery_app", "worker", "--loglevel=info", "--concurrency=4"]
#
# Flower Monitoring:
#   CMD ["celery", "-A", "backend.tasks.celery_app", "flower", "--port=5555", "--basic_auth=admin:flower123"]
#
# Alembic Migrations:
#   CMD ["alembic", "upgrade", "head"]
# ═══════════════════════════════════════════════════════════════════════════════
