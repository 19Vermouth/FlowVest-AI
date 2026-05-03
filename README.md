# FlowVest AI 🚀

**Production-Grade Multi-Agent Portfolio Generator for Indian Retail Investors**

FlowVest AI is an orchestrated multi-agent system that generates personalized investment portfolios. The v2.0 architecture features:

- **Celery + Redis job queue** for crash-resilient async execution
- **Firebase Admin SDK JWT verification** for secure authentication
- **Multi-provider market data layer** (Alpha Vantage → FMP → yfinance → fallback)
- **DAG-aware orchestrator** supporting parallel agent execution and crash recovery
- **Risk-engine validator** with concentration caps, diversification scoring, and volatility checks
- **Central LLM wrapper** with prompt caching, token tracking, and cost estimation
- **Per-user rate limiting** backed by Redis

---

## 📋 Table of Contents

- [Architecture](#architecture)
- [Tech Stack](#tech-stack)
- [Project Structure](#project-structure)
- [Quick Start](#quick-start)
- [Development](#development)
- [API Reference](#api-reference)
- [Multi-Agent Pipeline](#multi-agent-pipeline)
- [Authentication](#authentication)
- [Deployment](#deployment)
- [License](#license)

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        FlowVest AI v2.0                         │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌────────────────┐  REST   ┌────────────────┐  SQL  ┌───────┐ │
│  │   React SPA    │◄──────►│    FastAPI      │◄─────►│ PgSQL │ │
│  │ Firebase Auth  │        │  Orchestrator   │       │  15   │ │
│  │  Port 3000     │        │  Port 8000      │       │ 5432  │ │
│  └────────────────┘        └───────┬────────┘       └───────┘ │
│                                    │                            │
│                    ┌───────────────┼───────────────┐           │
│                    ▼               ▼               ▼           │
│             ┌──────────┐   ┌────────────┐   ┌──────────┐      │
│             │  Celery  │   │   Redis    │   │ Firebase │      │
│             │  Worker  │   │  Cache+Q   │   │   Auth   │      │
│             └──────────┘   └────────────┘   └──────────┘      │
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │              Market Data Provider Chain                 │   │
│  │  AlphaVantage → FMP → yfinance → Deterministic Fallback │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │              LLM Abstraction Layer                      │   │
│  │  OpenRouter (DeepSeek) + Prompt Cache + Cost Tracking   │   │
│  └─────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

### Multi-Agent Pipeline Flow (DAG-aware)

```
POST /portfolio/create (JWT required)
         │
         ▼
┌─────────────────────────────────────────────────────┐
│  Celery Task: run_portfolio_pipeline                │
│  (survives worker crashes, resumable)               │
├─────────────────────────────────────────────────────┤
│                                                     │
│  ┌──────────────────────────────────────────────┐  │
│  │  Stage 1: MarketAgent (parallel-capable)     │  │
│  │  Multi-provider failover + 300s TTL cache    │  │
│  └──────────────────────────────────────────────┘  │
│                    │                                │
│                    ▼                                │
│  ┌──────────────────────────────────────────────┐  │
│  │  Stage 2: AnalysisAgent (LLM via wrapper)    │  │
│  │  Prompt cache + fallback to local analysis   │  │
│  └──────────────────────────────────────────────┘  │
│                    │                                │
│                    ▼                                │
│  ┌──────────────────────────────────────────────┐  │
│  │  Stage 3: AllocationAgent (rule engine)      │  │
│  │  Risk/horizon/budget → 5-sleeve weights      │  │
│  └──────────────────────────────────────────────┘  │
│                    │                                │
│                    ▼                                │
│  ┌──────────────────────────────────────────────┐  │
│  │  Stage 4: AdvisorAgent (LLM via wrapper)     │  │
│  │  Investor memo generation                    │  │
│  └──────────────────────────────────────────────┘  │
│                    │                                │
│                    ▼                                │
│  ┌──────────────────────────────────────────────┐  │
│  │  Stage 5: ValidatorAgent (Risk Engine)       │  │
│  │  Concentration caps, HHI diversification,    │  │
│  │  volatility scoring, equity floor checks     │  │
│  └──────────────────────────────────────────────┘  │
│                    │                                │
│                    ▼                                │
│         Persist to PostgreSQL                       │
│  (portfolios + executions + agent_runs)             │
└─────────────────────────────────────────────────────┘
```

---

## 🛠️ Tech Stack

### Backend
| Layer | Technology | Version | Purpose |
|-------|-----------|---------|---------|
| **Web Framework** | FastAPI | 0.109.0 | Async REST API |
| **Task Queue** | Celery | 5.3.6 | Crash-resilient background jobs |
| **Message Broker** | Redis | 7.x | Celery broker + rate-limit store |
| **ORM** | SQLAlchemy | 2.0.25 | Database abstraction |
| **Database** | PostgreSQL | 15.x | Persistent storage |
| **Auth** | Firebase Admin SDK | 6.4.0 | JWT verification |
| **Rate Limiting** | slowapi + limits | 0.1.9 + 3.8.0 | Per-user + global limits |
| **LLM Client** | httpx + custom wrapper | 0.26.0 | OpenRouter calls with caching |
| **Market Data** | Alpha Vantage, FMP, yfinance | - | Multi-provider failover |
| **Logging** | structlog | 24.1.0 | Structured JSON logs |

### Frontend
| Layer | Technology | Version |
|-------|-----------|---------|
| **UI Framework** | React | 19.x |
| **Build Tool** | Vite | 7.x |
| **Styling** | TailwindCSS | 4.1.x |
| **Auth** | Firebase Web SDK | 10.x |
| **State** | React Context + localStorage | - |

---

## 📂 Project Structure

```
FlowVest-AI/
├── backend/
│   ├── main.py                    # FastAPI entry + middleware wiring
│   ├── config.py                  # Centralised env-var settings (pydantic-settings)
│   ├── requirements.txt           # All Python deps (Celery, Firebase, slowapi, etc.)
│   ├── Dockerfile                 # Production container
│   ├── db/
│   │   └── database.py           # SQLAlchemy engine + session factory
│   ├── models/
│   │   └── schemas.py            # ORM tables + Pydantic models (v2: versioning, audit)
│   ├── routers/
│   │   └── portfolio.py          # API endpoints (v2: JWT-protected, rate-limited)
│   ├── orchestrator/
│   │   └── orchestrator.py       # DAG-aware, crash-resumable orchestrator
│   ├── agents/
│   │   ├── base.py               # BaseAgent (retry + timeout)
│   │   ├── market_agent.py       # v2: uses MarketDataManager
│   │   ├── analysis_agent.py     # LLM market analysis
│   │   ├── allocation_agent.py   # Rule-based allocation
│   │   ├── advisor_agent.py      # LLM investor memo
│   │   ├── validator_agent.py    # v2: Risk Engine (HHI, concentration caps)
│   │   └── planner_agent.py      # v2: DAG decision engine
│   ├── services/
│   │   ├── market.py             # Shim for MarketDataManager
│   │   ├── analysis.py           # Uses central LLM client
│   │   ├── allocation.py         # Deterministic rule engine
│   │   └── advisor.py            # Uses central LLM client
│   ├── providers/                # NEW: Market data abstraction
│   │   ├── base.py               # BaseMarketProvider interface
│   │   ├── alpha_vantage.py      # Primary provider
│   │   ├── fmp.py                # Secondary provider
│   │   ├── yfinance_provider.py  # Tertiary fallback
│   │   ├── fallback.py           # Deterministic last resort
│   │   └── manager.py            # Failover chain + TTL cache
│   ├── llm/                      # NEW: LLM abstraction
│   │   └── client.py             # OpenRouter wrapper + prompt cache + cost tracking
│   ├── middleware/               # NEW: Cross-cutting concerns
│   │   ├── auth.py               # Firebase JWT verification
│   │   └── rate_limit.py         # Redis-backed rate limiting
│   └── tasks/                    # NEW: Celery tasks
│       ├── celery_app.py         # Celery configuration
│       └── portfolio_tasks.py    # run_portfolio_pipeline task
├── frontend/                     # Frontend mirror structure
│   ├── index.html
│   └── src/
│       ├── App.tsx
│       ├── main.tsx
│       └── index.css
├── src/                          # Active frontend source
│   ├── App.tsx                   # Full SPA (Landing, Auth, Dashboard, Studio)
│   ├── main.tsx
│   └── index.css
├── dist/                         # Production single-file build
│   └── index.html                # ~290KB standalone app
├── docker-compose.yml            # Postgres + Redis + Backend + Celery + Flower
├── .env.example                  # All env vars documented
├── package.json
├── PRD.md
└── ScratchPad.md
```

---

## 🚀 Quick Start

### 1. Docker Compose (Recommended — Full Stack)

```bash
# Clone and navigate
cd FlowVest-AI

# Copy environment template
cp .env.example .env

# Edit .env with your keys:
#   - OPENROUTER_API_KEY (https://openrouter.ai)
#   - ALPHA_VANTAGE_API_KEY (https://www.alphavantage.co)
#   - FMP_API_KEY (https://financialmodelingprep.com)
#   - FIREBASE_PROJECT_ID + GOOGLE_APPLICATION_CREDENTIALS (optional for local dev)

# Start all services
docker-compose up --build

# Access points:
#   Frontend:    http://localhost:3000
#   Backend API: http://localhost:8000
#   Swagger UI:  http://localhost:8000/docs
#   Flower UI:   http://localhost:5555  (Celery monitoring)
#   Redis:       localhost:6379
#   PostgreSQL:  localhost:5432
```

### 2. Local Development (Backend Only)

```bash
cd backend

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Start Redis (required for Celery + rate limiting)
# macOS: brew install redis && redis-server
# Linux: sudo systemctl start redis
# Docker: docker run -d -p 6379:6379 redis:7

# Start PostgreSQL
# Docker: docker run -d -p 5432:5432 -e POSTGRES_DB=flowvest \
#         -e POSTGRES_USER=flowvest -e POSTGRES_PASSWORD=flowvest123 postgres:15

# Set environment
export DATABASE_URL="postgresql://flowvest:flowvest123@localhost:5432/flowvest"
export REDIS_URL="redis://localhost:6379/0"
export OPENROUTER_API_KEY="sk-or-v1-xxxxx"
export AUTH_DISABLED=true  # Local dev only — skips JWT verification

# Run Celery worker (separate terminal)
celery -A backend.tasks.celery_app worker --loglevel=info --pool=solo

# Run Celery Flower (optional monitoring)
celery -A backend.tasks.celery_app flower --port=5555

# Run FastAPI backend
uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
```

### 3. Frontend Development

```bash
# Install Node dependencies
npm install

# Run Vite dev server
npm run dev

# Build production single-file bundle
npm run build

# Output: dist/index.html (~290KB, fully self-contained)
```

---

## 🔐 Authentication

### Production Mode (JWT Verification)

All protected endpoints require a Firebase ID token in the `Authorization: Bearer <token>` header.

```bash
curl -X POST http://localhost:8000/portfolio/create \
  -H "Authorization: Bearer eyJhbGciOiJSUzI1NiIsImtpZCI6Ij..." \
  -H "Content-Type: application/json" \
  -d '{"budget": 250000, "risk": "Medium", "horizon": "Long"}'
```

The `backend/middleware/auth.py` module:
1. Extracts the Bearer token
2. Verifies it using Firebase Admin SDK (`verify_id_token` with `check_revoked=True`)
3. Attaches `request.state.user_id` for downstream use
4. Returns HTTP 401 on any verification failure

### Development Mode (`AUTH_DISABLED=true`)

For local testing without Firebase setup:

```bash
export AUTH_DISABLED=true

curl -X POST http://localhost:8000/portfolio/create \
  -H "x-demo-user: dev-user-123" \
  -H "Content-Type: application/json" \
  -d '{"budget": 250000, "risk": "Medium", "horizon": "Long"}'
```

⚠️ **NEVER** use `AUTH_DISABLED=true` in production.

---

## 📊 API Reference

| Method | Endpoint | Auth | Rate Limit | Description |
|--------|----------|------|------------|-------------|
| GET | `/` | ❌ | Global | API metadata |
| GET | `/health` | ❌ | Global | Health check (DB, Redis, Celery, OpenRouter) |
| POST | `/portfolio/create` | ✅ | 10/min/user | Enqueue portfolio generation (returns `execution_id`) |
| GET | `/portfolio/execution/{execution_id}` | ✅ | 30/min/user | Poll execution status (Celery task state) |
| GET | `/portfolio/list` | ✅ | 30/min/user | List user's portfolios |
| GET | `/portfolio/{id}` | ✅ | 30/min/user | Get single portfolio |
| DELETE | `/portfolio/{id}` | ✅ | 10/min/user | Delete portfolio |

### Example: Create Portfolio (Async Flow)

```bash
# 1. Submit request (returns immediately with execution_id)
$ curl -X POST http://localhost:8000/portfolio/create \
  -H "Authorization: Bearer <firebase-token>" \
  -H "Content-Type: application/json" \
  -d '{"budget": 500000, "risk": "High", "horizon": "Long"}'

# Response (HTTP 202 Accepted):
{
  "execution_id": "exec_7a3b9c12-4f8e-4d2a-9b1c-8e7f6a5d4c3b",
  "status": "pending",
  "celery_task_id": "task_9f8e7d6c-5b4a-3210-fedc-ba9876543210"
}

# 2. Poll status (every 2-3 seconds until status != "running")
$ curl -X GET http://localhost:8000/portfolio/execution/exec_7a3b9c12... \
  -H "Authorization: Bearer <firebase-token>"

# Final Response (HTTP 200 OK):
{
  "execution_id": "exec_7a3b9c12...",
  "status": "completed",
  "portfolio_id": "port_1a2b3c4d...",
  "celery_task_id": "task_9f8e7d6c...",
  "retry_count": 0,
  "final_state": {
    "allocation": [...],
    "reasoning": "...",
    "portfolio_score": 87.5,
    "validation_passed": true
  },
  "metadata": {
    "agents_executed": [
      {"agent": "market", "status": "success", "elapsed_seconds": 1.23},
      {"agent": "analysis", "status": "success", "elapsed_seconds": 3.45},
      ...
    ],
    "model_version": "v2",
    "prompt_version": "v1",
    "allocation_version": "v1"
  }
}
```

---

## 🧠 Multi-Agent Pipeline (v2 Features)

### Agent Responsibilities

| Agent | Timeout | Retries | Key Upgrade in v2 |
|-------|---------|---------|-------------------|
| **MarketAgent** | 20s | 1 | Multi-provider failover (Alpha Vantage → FMP → yfinance → fallback) + 300s TTL cache |
| **AnalysisAgent** | 45s | 2 | Uses central LLM client (prompt cache, cost tracking, fallback model) |
| **AllocationAgent** | 10s | 2 | Unchanged (deterministic rule engine) |
| **AdvisorAgent** | 45s | 2 | Uses central LLM client |
| **ValidatorAgent** | 10s | 0 | **Risk Engine**: HHI diversification score, concentration caps, volatility scoring, equity floor checks |
| **PlannerAgent** | 5s | 0 | **DAG decision engine**: returns `plan_dag` for parallel execution, budget-tier hints |

### Crash Recovery Flow

1. Celery task starts → creates `Execution` row with `status="pending"`
2. Orchestrator loads `Execution.partial_state` (if resuming after crash)
3. Orchestrator queries `AgentRun` table for already-completed agents
4. Skips completed agents, resumes from last failed stage
5. After each agent, flushes `partial_state` to DB
6. On final completion, writes `final_state` and links to `Portfolio`

### DAG Execution Example

```python
# PlannerAgent returns:
{
  "plan_dag": [
    {"stage": 1, "agents": ["market"]},
    {"stage": 2, "agents": ["analysis"]},
    {"stage": 3, "agents": ["allocation"]},
    {"stage": 4, "agents": ["advisor"]},
    {"stage": 5, "agents": ["validator"]}
  ]
}

# Orchestrator executes:
# Stage 1: market (single agent — sequential)
# Stage 2: analysis (single agent — sequential)
# Stage 3: allocation (single agent — sequential)
# Stage 4: advisor (single agent — sequential)
# Stage 5: validator (single agent — sequential)

# Future extension (parallel):
# Stage 2: ["analysis", "macro_sentiment"]  # ← runs in parallel via asyncio.gather()
```

---

## 🗄️ Database Schema (v2 Additions)

### New Columns on `portfolios`

| Column | Type | Purpose |
|--------|------|---------|
| `model_version` | VARCHAR(20) | LLM model used (e.g., "v2") |
| `prompt_version` | VARCHAR(20) | Prompt template version |
| `allocation_version` | VARCHAR(20) | Allocation rule-engine version |
| `portfolio_score` | FLOAT | Composite score (0–100) from ValidatorAgent |
| `diversification_score` | FLOAT | HHI-based diversification score |
| `volatility_score` | FLOAT | Stability score (penalises high-vol sleeves) |
| `validation_errors` | JSONB | Array of error messages |
| `validation_warnings` | JSONB | Array of warning messages |

### New Table: `rate_limit_logs`

| Column | Type | Purpose |
|--------|------|---------|
| `id` | INTEGER (PK) | Auto-increment |
| `user_id` | VARCHAR(255) | Firebase uid |
| `endpoint` | VARCHAR(120) | API path |
| `hit_at` | TIMESTAMP | Request timestamp |

---

## 📦 Deployment

### Docker Compose (Production-Ready)

```yaml
services:
  postgres:
    image: postgres:15
    volumes:
      - postgres_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U flowvest -d flowvest"]
      interval: 10s
      timeout: 5s
      retries: 5

  redis:
    image: redis:7-alpine
    command: redis-server --appendonly yes
    volumes:
      - redis_data:/data
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 5s
      retries: 5

  backend:
    build:
      context: .
      dockerfile: backend/Dockerfile
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
    env_file:
      - .env
    ports:
      - "8000:8000"
    command: uvicorn backend.main:app --host 0.0.0.0 --port 8000 --workers 4

  celery-worker:
    build:
      context: .
      dockerfile: backend/Dockerfile
    depends_on:
      - redis
      - postgres
    env_file:
      - .env
    command: celery -A backend.tasks.celery_app worker --loglevel=info --concurrency=4

  flower:
    build:
      context: .
      dockerfile: backend/Dockerfile
    depends_on:
      - redis
    env_file:
      - .env
    ports:
      - "5555:5555"
    command: celery -A backend.tasks.celery_app flower --port=5555

volumes:
  postgres_data:
  redis_data:
```

### Environment Variables (.env)

```env
# ── Application ────────────────────────────────────────────────────────────
APP_VERSION=2.0.0
APP_NAME=FlowVest AI
APP_URL=http://localhost:3000
CORS_ORIGINS=http://localhost:3000,http://127.0.0.1:3000
DEBUG=false

# ── Database ───────────────────────────────────────────────────────────────
DATABASE_URL=postgresql://flowvest:flowvest123@postgres:5432/flowvest
DB_POOL_SIZE=5
DB_MAX_OVERFLOW=10

# ── Redis / Celery ─────────────────────────────────────────────────────────
REDIS_URL=redis://redis:6379/0
CELERY_BROKER_URL=redis://redis:6379/0
CELERY_RESULT_BACKEND=redis://redis:6379/1
CELERY_TASK_SOFT_TIME_LIMIT=300
CELERY_TASK_TIME_LIMIT=360

# ── Firebase ───────────────────────────────────────────────────────────────
FIREBASE_PROJECT_ID=your-project-id
GOOGLE_APPLICATION_CREDENTIALS=/app/service-account.json
AUTH_DISABLED=false

# ── OpenRouter / LLM ───────────────────────────────────────────────────────
OPENROUTER_API_KEY=sk-or-v1-xxxxx
OPENROUTER_MODEL=deepseek/deepseek-chat-v3-0324
OPENROUTER_FALLBACK_MODEL=openai/gpt-4o-mini
LLM_MAX_TOKENS_ANALYSIS=220
LLM_MAX_TOKENS_ADVISOR=280
LLM_TEMPERATURE_ANALYSIS=0.4
LLM_TEMPERATURE_ADVISOR=0.45
LLM_CACHE_TTL=600

# ── Market Data Providers ──────────────────────────────────────────────────
ALPHA_VANTAGE_API_KEY=your-av-key
FMP_API_KEY=your-fmp-key
MARKET_CACHE_TTL=300

# ── Rate Limiting ──────────────────────────────────────────────────────────
RATE_LIMIT_PER_MINUTE=10
RATE_LIMIT_GLOBAL_PER_MINUTE=200

# ── Versioning / Audit ─────────────────────────────────────────────────────
MODEL_VERSION=v2
PROMPT_VERSION=v1
ALLOCATION_VERSION=v1
```

---

## 📈 Observability

### Health Endpoint

```bash
curl http://localhost:8000/health
```

Response:
```json
{
  "status": "healthy",
  "database": "online",
  "redis": "online",
  "celery": "online",
  "openrouter": "configured",
  "model": "deepseek/deepseek-chat-v3-0324",
  "timestamp": "2026-05-15T14:30:00Z"
}
```

### Celery Monitoring (Flower)

Access `http://localhost:5555` to view:
- Active tasks
- Task history + retry counts
- Worker pool status
- Task runtime distributions

### Structured Logging

All logs are JSON-formatted via `structlog`:

```json
{
  "event": "Market data SUCCESS",
  "provider": "alpha_vantage",
  "attempt": 1,
  "level": "info",
  "timestamp": "2026-05-15T14:30:00Z"
}
```

### LLM Cost Tracking

```bash
curl http://localhost:8000/llm/cost-summary
```

Response:
```json
{
  "total_tokens_used": 125000,
  "total_cost_usd": 0.0175,
  "cache_entries": 342
}
```

---

## ⚖️ License & Disclaimer

**Educational and Demonstration Purposes Only.**

FlowVest AI is a sample application designed to showcase:
- React 19 + FastAPI architecture
- Celery async task queues
- Multi-agent AI orchestration
- Firebase authentication
- Multi-provider failover patterns

The underlying financial logic, allocation rules, and generated portfolios are **purely illustrative** and **must not be treated as professional investment advice**. Always consult with a qualified financial advisor before conducting real market transactions.

---

**Document Version**: 2.0  
**Last Updated**: May 2026  
**Author**: FlowVest AI Development Team
