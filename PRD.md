# FlowVest AI - Product Requirements Document (PRD)

## Version 2.0 | Production-Grade Multi-Agent System

---

## 1. Executive Summary

| Item | Description |
|------|-------------|
| **Product Name** | FlowVest AI |
| **Type** | AI-Powered Portfolio Generator (B2C SaaS) |
| **Core Value** | DAG-orchestrated multi-agent pipeline that generates personalized, compliance-validated investment portfolios with crash-resilient async execution |
| **Current State** | Production-ready v2.0 with Celery job queue, Firebase JWT auth, multi-provider market data, risk-engine validator, and LLM cost tracking |
| **Target Market** | Individual retail investors in India |

---

## 2. Technology Stack

### 2.1 Backend (v2 Production)

| Layer | Technology | Version | Purpose |
|-------|-----------|---------|---------|
| **Web Framework** | FastAPI | 0.109.0 | Async REST API |
| **Task Queue** | Celery | 5.3.6 | Crash-resilient background jobs |
| **Message Broker** | Redis | 7.x | Celery broker + rate-limit store + prompt cache |
| **ORM** | SQLAlchemy | 2.0.25 | Database abstraction |
| **Migrations** | Alembic | 1.13.1 | Schema versioning (future-proofing) |
| **Validation** | Pydantic + pydantic-settings | 2.5.3 | Request validation + centralised config |
| **Auth** | Firebase Admin SDK | 6.4.0 | JWT verification (production) |
| **Rate Limiting** | slowapi + limits | 0.1.9 + 3.8.0 | Per-user + global limits (Redis-backed) |
| **HTTP Client** | httpx | 0.26.0 | Async calls to OpenRouter + market APIs |
| **Market Data** | Alpha Vantage, FMP, yfinance | - | Multi-provider failover chain |
| **Logging** | structlog | 24.1.0 | Structured JSON logging |
| **Database** | PostgreSQL | 15.x | Persistent storage (portfolios, executions, agent_runs, rate_limit_logs) |
| **Container** | Docker + Compose | - | Multi-service orchestration |

### 2.2 Frontend

| Layer | Technology | Version |
|-------|-----------|---------|
| **UI Framework** | React | 19.x |
| **Build Tool** | Vite | 7.x |
| **Styling** | TailwindCSS | 4.1.x |
| **Auth** | Firebase Web SDK | 10.x |
| **State** | React Context + localStorage | - |
| **Output** | vite-plugin-singlefile | Single ~290KB `dist/index.html` |

### 2.3 Project Structure

```
FlowVest-AI/
├── backend/
│   ├── main.py                    # FastAPI entry + middleware wiring
│   ├── config.py                  # Centralised env-var settings
│   ├── requirements.txt           # All Python deps
│   ├── Dockerfile                 # Production container
│   ├── db/
│   │   └── database.py           # SQLAlchemy engine + session factory
│   ├── models/
│   │   └── schemas.py            # ORM tables + Pydantic models (v2: versioning, audit)
│   ├── routers/
│   │   └── portfolio.py          # API endpoints (JWT-protected, rate-limited)
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

## 3. Feature Specification

### 3.1 Core Features

#### 3.1.1 Portfolio Creation (Async, Resumable)
- **Inputs**: Budget (₹), Risk Level (Low/Medium/High), Horizon (Short/Medium/Long)
- **Process**: Celery task executes DAG-aware multi-agent pipeline
- **Output**: Asset allocation + AI reasoning + risk-engine scores + audit trail
- **Resumability**: If worker crashes, task resumes from last completed agent (state persisted in `Execution.partial_state`)

#### 3.1.2 Multi-Agent Pipeline (v2)

| Agent | Function | Input | Output | Timeout | Retries | v2 Upgrade |
|-------|----------|-------|--------|---------|---------|------------|
| **Market Agent** | Fetch real-time market data via failover chain | - | Nifty, Sensex, Gold prices + trends | 20s | 1 | Multi-provider (Alpha Vantage → FMP → yfinance → fallback) + 300s TTL cache |
| **Analysis Agent** | AI-powered market analysis | Market data + user risk profile | Insights + risk notes | 45s | 2 | Central LLM client (prompt cache, cost tracking, fallback model) |
| **Allocation Agent** | Rule-based asset allocation | Risk + horizon + budget | Asset percentages | 10s | 2 | Unchanged (deterministic) |
| **Advisor Agent** | Generate human-readable explanation | Allocation + analysis | Markdown reasoning | 45s | 2 | Central LLM client |
| **Validator Agent** | Risk-engine compliance check | Full pipeline state | Pass/fail + scores + errors/warnings | 10s | 0 | **NEW**: HHI diversification, concentration caps, volatility scoring, equity floor checks |
| **Planner Agent** | DAG decision engine | Input constraints + state | Ordered stages (parallel-capable) | 5s | 0 | **NEW**: Returns `plan_dag` for parallel execution, budget-tier hints |

#### 3.1.3 Authentication (Firebase JWT)
- **Production**: Firebase Admin SDK verifies ID tokens on every request
- **Development**: `AUTH_DISABLED=true` trusts `x-demo-user` header (NEVER use in production)
- **User Scoping**: All queries filtered by `user_id` extracted from verified JWT
- **Token Revocation**: `check_revoked=True` in Firebase Admin SDK

#### 3.1.4 Rate Limiting
- **Per-User**: 10 requests/minute on protected POST endpoints
- **Global**: 200 requests/minute across entire API
- **Backend**: Redis-backed sliding window via `slowapi` + `limits`
- **Headers**: Returns `Retry-After` on 429 responses

#### 3.1.5 Dashboard (Frontend)
- List all user portfolios (filtered by Firebase uid)
- Status indicators (pending/running/completed/failed/completed_with_errors)
- Quick navigation to execution status or result
- Delete portfolio action

#### 3.1.6 Execution Status Polling
- `GET /portfolio/execution/{execution_id}` returns:
  - Celery task state (PENDING → STARTED → SUCCESS/FAILURE)
  - Partial state (if resuming after crash)
  - Completed agents list (for resume skipping)
  - Final state + metadata on completion

#### 3.1.7 Result Page
- Donut chart visualization (Custom SVG)
- Asset allocation breakdown
- Investment strategy reasoning
- **NEW**: Portfolio score (0–100), diversification score, volatility score
- **NEW**: Validation errors/warnings array
- **NEW**: Audit fields (model_version, prompt_version, allocation_version)
- Copy to clipboard
- Disclaimer notice

### 3.2 User Flows

```
User Journey (v2):
1. Landing Page → Click "Get Started" or "Sign In"
2. Auth Page → Firebase Sign up or Sign in (JWT issued)
3. Dashboard → View portfolios or click "Create Portfolio"
4. New Portfolio → Enter budget, risk, horizon → Submit
5. Backend: Celery task enqueued → returns execution_id immediately (HTTP 202)
6. Frontend polls /portfolio/execution/{id} every 2-3s
7. Backend: Orchestrator runs DAG (crash-resumable, agents skipped if already done)
8. Result → View allocation chart + reasoning + risk scores
9. Dashboard → See completed portfolio in list (with scores visible)
```

### 3.3 API Endpoints

| Method | Endpoint | Auth | Rate Limit | Description |
|--------|----------|------|------------|-------------|
| GET | `/` | ❌ | Global | Root health check |
| GET | `/health` | ❌ | Global | API health status (DB, Redis, Celery, OpenRouter) |
| POST | `/portfolio/create` | ✅ | 10/min/user | Create new portfolio (async, returns execution_id) |
| GET | `/portfolio/execution/{id}` | ✅ | 30/min/user | Poll execution status (Celery task state) |
| GET | `/portfolio/{id}` | ✅ | 30/min/user | Get portfolio details |
| GET | `/portfolio/list` | ✅ | 30/min/user | List all portfolios |
| DELETE | `/portfolio/{id}` | ✅ | 10/min/user | Delete a portfolio |
| GET | `/llm/cost-summary` | ✅ | 5/min/user | LLM token usage + cost tracking |

---

## 4. Database Schema (v2)

### 4.1 portfolios (Enhanced)

```sql
CREATE TABLE portfolios (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id             VARCHAR(255) NOT NULL,
    budget              NUMERIC NOT NULL,
    risk                VARCHAR(20) NOT NULL,
    horizon             VARCHAR(20) NOT NULL,
    status              VARCHAR(30) NOT NULL DEFAULT 'completed',
    allocation          JSONB,
    reasoning           TEXT,
    analysis_summary    TEXT,
    market_data         JSONB,
    steps_data          JSONB DEFAULT '[]',
    cadence             VARCHAR(100),
    -- Audit / versioning
    model_version       VARCHAR(20),
    prompt_version      VARCHAR(20),
    allocation_version  VARCHAR(20),
    -- Risk-engine scores
    portfolio_score       FLOAT,
    diversification_score FLOAT,
    volatility_score      FLOAT,
    validation_errors     JSONB,
    validation_warnings   JSONB,
    created_at          TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_portfolios_user_created ON portfolios (user_id, created_at DESC);
```

### 4.2 executions (Crash-Resumable State)

```sql
CREATE TABLE executions (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    portfolio_id    UUID REFERENCES portfolios(id),
    user_id         VARCHAR(255) NOT NULL,
    celery_task_id  VARCHAR(255),  -- Links to Celery task
    status          VARCHAR(30) DEFAULT 'pending',  -- pending/running/completed/failed/completed_with_errors
    input_data      JSONB,
    partial_state   JSONB,  -- For crash recovery
    final_state     JSONB,
    metadata        JSONB,
    error           TEXT,
    retry_count     INTEGER DEFAULT 0,
    -- Audit
    model_version       VARCHAR(20),
    prompt_version      VARCHAR(20),
    allocation_version  VARCHAR(20),
    created_at      TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at      TIMESTAMP WITH TIME ZONE
);

CREATE INDEX idx_executions_user_status ON executions (user_id, status);
CREATE INDEX idx_executions_celery_task ON executions (celery_task_id);
```

### 4.3 agent_runs (Per-Agent Audit Trail)

```sql
CREATE TABLE agent_runs (
    id              SERIAL PRIMARY KEY,
    execution_id    UUID NOT NULL,
    agent_name      VARCHAR(60) NOT NULL,
    status          VARCHAR(20) NOT NULL,  -- success/failed
    input_state     JSONB,
    output_state    JSONB,
    error           TEXT,
    attempt         INTEGER DEFAULT 1,
    start_time      TIMESTAMP WITH TIME ZONE,
    end_time        TIMESTAMP WITH TIME ZONE,
    elapsed_seconds FLOAT
);

CREATE INDEX idx_agent_runs_exec_agent ON agent_runs (execution_id, agent_name);
```

### 4.4 rate_limit_logs (Sliding Window Counter)

```sql
CREATE TABLE rate_limit_logs (
    id        SERIAL PRIMARY KEY,
    user_id   VARCHAR(255) NOT NULL,
    endpoint  VARCHAR(120) NOT NULL,
    hit_at    TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_rate_limit_user_endpoint ON rate_limit_logs (user_id, endpoint, hit_at);
```

### 4.5 Notes
- No authentication table (handled by Firebase)
- All queries filtered by `user_id` from verified JWT
- `partial_state` enables crash recovery without re-running completed agents

---

## 5. UI/UX Specification

### 5.1 Design System

| Element | Value |
|---------|-------|
| **Theme** | Dark mode fintech aesthetic |
| **Primary Color** | #0ea5e9 (Sky Blue) |
| **Secondary Color** | #8b5cf6 (Purple) |
| **Background** | #020617 (Dark Navy) |
| **Surface** | #1e293b (Dark Slate) |
| **Text Primary** | #f8fafc (White) |
| **Text Secondary** | #94a3b8 (Gray) |
| **Success** | #10b981 (Green) |
| **Error** | #ef4444 (Red) |
| **Warning** | #f59e0b (Amber) |

### 5.2 Pages

| Page | Route | Features |
|------|-------|----------|
| Landing | `/` | Hero, features, CTA, how-it-works, live market ticker |
| Auth | `/` (modal) | Firebase sign-in/sign-up |
| Dashboard | `/` (view state) | Portfolio list, create button, stats grid |
| New Portfolio | `/` (view state) | Form with budget, risk, horizon |
| Execution | `/` (view state) | Step-by-step progress (polls backend) |
| Result | `/` (view state) | Donut chart + reasoning + risk scores |
| API Studio | `/` (view state) | Interactive API tester + PostgreSQL explorer |

### 5.3 Components

- **Navbar**: Logo, navigation, user menu, sign out
- **StepCard**: Pipeline step with status indicator
- **DonutChart**: SVG donut chart with tooltips
- **StatusBadge**: Portfolio status indicator
- **SectionHeader**: Page section header component
- **AuthProvider**: Firebase JWT context provider
- **RateLimitBanner**: Shows remaining requests (optional)

---

## 6. Environment Variables

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
AUTH_DISABLED=false  # NEVER use true in production

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

## 7. Docker Configuration

### 7.1 Services

| Service | Port | Health Check | Purpose |
|---------|------|--------------|---------|
| postgres | 5432 | `pg_isready` | Persistent storage |
| redis | 6379 | `redis-cli ping` | Celery broker + rate limits + prompt cache |
| backend | 8000 | `/health` | FastAPI REST API |
| celery-worker | - | Celery inspect ping | Background task execution |
| flower | 5555 | HTTP 200 | Celery monitoring UI |

### 7.2 Volumes
- `postgres_data`: PostgreSQL persistent storage
- `redis_data`: Redis AOF persistence (optional)

### 7.3 Dependencies
- Backend waits for PostgreSQL + Redis health checks
- Celery worker depends on Redis + PostgreSQL
- Flower depends on Redis

---

## 8. Known Issues & Limitations

| Issue | Status | Mitigation |
|-------|--------|------------|
| Alpha Vantage free tier (25 req/day) | Known | Cache TTL=300s reduces calls; failover to FMP/yfinance |
| yfinance rate limiting | Known | Tertiary provider only; fallback to deterministic generator |
| Firebase Admin SDK requires service account JSON | To Document | Use Application Default Credentials on GCP/Cloud Run |
| Celery task retries not yet implemented | To Do | Add `@task(autoretry_for=(Exception,), retry_backoff=True)` |
| No WebSocket for real-time updates | To Do | Frontend polls every 2-3s; WebSocket future enhancement |
| No PDF export | To Do | Implement with jsPDF or Puppeteer |
| No billing/subscription | To Do | Stripe integration future feature |

---

## 9. Future Roadmap

### Phase 1: Stability (Immediate)
- [x] Celery job queue (crash-resilient execution)
- [x] Firebase JWT authentication
- [x] Multi-provider market data failover
- [x] DAG-aware orchestrator
- [x] Risk-engine validator
- [ ] Celery task auto-retry on transient failures
- [ ] WebSocket real-time execution updates

### Phase 2: Features (Short-term)
- [ ] Portfolio comparison (side-by-side)
- [ ] Historical backtesting (5Y)
- [ ] Multiple portfolio scenarios (what-if analysis)
- [ ] Email notifications (portfolio review due)
- [ ] Mobile responsive design improvements
- [ ] PDF export (investor memo + allocation chart)

### Phase 3: Monetization (Mid-term)
- [ ] Stripe integration for payments
- [ ] Subscription tiers (Free/Pro/Institutional)
- [ ] Usage limits per tier
- [ ] API access for developers (API keys)
- [ ] White-label options

### Phase 4: Scale (Long-term)
- [ ] Admin dashboard (user management, usage analytics)
- [ ] Advanced analytics (portfolio performance tracking)
- [ ] Multi-language support (Hindi, Tamil, etc.)
- [ ] Additional asset classes (International equities, REITs, Bonds)
- [ ] Custom fine-tuned LLM models
- [ ] Direct broker integrations (Zerodha, Groww API)

---

## 10. Success Criteria

| Metric | Target | Measurement |
|--------|--------|-------------|
| User Registration | 100+ users | Firebase Auth dashboard |
| Portfolio Generation | 500+ portfolios | `SELECT COUNT(*) FROM portfolios` |
| Pipeline Success Rate | >95% | `executions.status = 'completed' / total` |
| Crash Recovery Success | 100% | Resumed executions complete without data loss |
| Market Data Availability | >99% | Provider failover logs |
| UI/UX Score | 4+ / 5 | User surveys |
| Page Load Time | < 3 seconds | Lighthouse audits |
| API Latency (p95) | < 500ms | Prometheus histograms |
| Celery Task Success Rate | >98% | Flower monitoring |

---

## 11. Appendix

### A. Dependencies List

**Backend (Python)**
```
fastapi==0.109.0
uvicorn[standard]==0.27.0
sqlalchemy==2.0.25
psycopg2-binary==2.9.9
pydantic==2.5.3
pydantic-settings==2.1.0
alembic==1.13.1
celery==5.3.6
redis==5.0.1
kombu==5.3.4
flower==2.0.1
firebase-admin==6.4.0
slowapi==0.1.9
limits==3.8.0
yfinance==0.2.36
httpx==0.26.0
structlog==24.1.0
```

**Frontend (Node)**
```
react@19.x
react-dom@19.x
firebase@10.x
tailwindcss@4.x
vite@7.x
```

### B. External Services

| Service | Purpose | Free Tier | Rate Limits |
|---------|---------|-----------|-------------|
| Firebase Auth | Authentication | Yes (10k/month) | - |
| OpenRouter | AI LLM | Yes (limited credits) | Model-dependent |
| Alpha Vantage | Market Data | Yes (25 req/day) | 5 req/min |
| FMP | Market Data | Yes (250 req/day) | - |
| Yahoo Finance | Market Data (fallback) | Yes | Rate-limited |

---

## 12. How to Run

### Prerequisites
- Docker Desktop installed and running
- OpenRouter API key (free at openrouter.ai)
- Alpha Vantage API key (free at alphavantage.co)
- FMP API key (free at financialmodelingprep.com)
- Firebase project (free at console.firebase.google.com)

### Quick Start (Docker Compose)
```bash
# 1. Clone the project
cd FlowVest-AI

# 2. Create .env file with your keys
cp .env.example .env
# Edit .env with all required API keys

# 3. Start all services
docker-compose up --build

# 4. Access points:
#    Frontend:    http://localhost:3000
#    Backend API: http://localhost:8000
#    Swagger UI:  http://localhost:8000/docs
#    Flower UI:   http://localhost:5555
```

### Local Development (No Docker)
```bash
# Terminal 1: Redis
redis-server

# Terminal 2: PostgreSQL
docker run -d -p 5432:5432 -e POSTGRES_DB=flowvest \
  -e POSTGRES_USER=flowvest -e POSTGRES_PASSWORD=flowvest123 postgres:15

# Terminal 3: Celery Worker
cd backend
export DATABASE_URL="postgresql://flowvest:flowvest123@localhost:5432/flowvest"
export REDIS_URL="redis://localhost:6379/0"
export AUTH_DISABLED=true  # Dev only
celery -A backend.tasks.celery_app worker --loglevel=info --pool=solo

# Terminal 4: FastAPI Backend
uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload

# Terminal 5: Frontend
npm install
npm run dev
```

---

**Document Version**: 2.0  
**Last Updated**: May 2026  
**Author**: FlowVest AI Development Team
