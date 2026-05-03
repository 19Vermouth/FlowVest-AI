# Getting Started with FlowVest AI

A production-grade multi-agent portfolio generator for Indian retail investors.

---

## Prerequisites

### Required Software
| Software | Version | Download |
|----------|---------|---------|
| Docker Desktop | Latest | [docker.com](https://www.docker.com/products/docker-desktop) |
| Git | Latest | [git-scm.com](https://git-scm.com) |

### Optional (Local Development)
| Software | Version | Purpose |
|----------|---------|---------|
| Node.js | 18+ | Frontend development |
| Python | 3.11 | Backend development |

### Required API Keys
Get free API keys from these services:

| Service | Purpose | Free Tier | URL |
|---------|---------|----------|-----|
| **OpenRouter** | LLM (DeepSeek) | Yes (limited) | [openrouter.ai](https://openrouter.ai) |
| **Alpha Vantage** | Market Data | 25 req/day | [alphavantage.co](https://www.alphavantage.co) |
| **Financial Modeling Prep** | Market Data | 250 req/day | [financialmodelingprep.com](https://site.financialmodelingprep.com) |
| **Firebase** | Auth (optional) | 10k/month | [console.firebase.google.com](https://console.firebase.google.com) |

---

## Quick Start (Docker Compose)

### 1. Clone and Setup
```bash
git clone https://github.com/19Vermouth/FlowVest-AI.git
cd FlowVest-AI
```

### 2. Configure Environment
```bash
# Copy environment template
copy .env.example .env

# Edit .env with your API keys
# Minimum required:
#   - OPENROUTER_API_KEY
# Optional (will use fallback if missing):
#   - ALPHA_VANTAGE_API_KEY
#   - FMP_API_KEY
```

### 3. Start Services
```bash
docker-compose up --build
```

### 4. Access the Application
| Service | URL | Credentials |
|---------|-----|------------|
| **Frontend** | http://localhost:5173 | - |
| **Backend API** | http://localhost:8000 | - |
| **Swagger UI** | http://localhost:8000/docs | - |
| **Flower (Celery)** | http://localhost:5555 | admin/flower123 |
| **PostgreSQL** | localhost:5432 | flowvest/flowvest123 |
| **Redis** | localhost:6379 | - |

### 5. Stop Services
```bash
docker-compose down
# To remove data volumes:
docker-compose down -v
```

---

## Local Development

### Backend Only

#### 1. Create Virtual Environment
```bash
cd backend
python -m venv venv
# Windows:
venv\Scripts\activate
# Mac/Linux:
source venv/bin/activate
```

#### 2. Install Dependencies
```bash
pip install -r requirements.txt
```

#### 3. Start Redis (Required)
```bash
# Mac (Homebrew):
brew install redis
redis-server

# Or Docker:
docker run -d -p 6379:6379 redis:7
```

#### 4. Start PostgreSQL (Required)
```bash
docker run -d -p 5432:5432 -e POSTGRES_DB=flowvest ^
  -e POSTGRES_USER=flowvest -e POSTGRES_PASSWORD=flowvest123 postgres:15
```

#### 5. Start Celery Worker
```bash
cd backend
set AUTH_DISABLED=true  # Dev only - skips JWT verification
celery -A backend.tasks.celery_app worker --loglevel=info --pool=solo
```

#### 6. Start FastAPI
```bash
uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
```

---

### Frontend Only

#### 1. Install Dependencies
```bash
npm install
```

#### 2. Start Development Server
```bash
npm run dev
# Access: http://localhost:5173
```

#### 3. Build for Production
```bash
npm run build
# Output: dist/index.html (~290KB, self-contained)
```

---

## Testing the API

### Health Check
```bash
curl http://localhost:8000/health
```

Response:
```json
{
  "status": "healthy",
  "database": "online",
  "redis": "online",
  "openrouter": "configured"
}
```

### Create Portfolio
```bash
curl -X POST http://localhost:8000/portfolio/create ^
  -H "Content-Type: application/json" ^
  -H "x-demo-user: test-user" ^
  -d "{\"budget\": 250000, \"risk\": \"Medium\", \"horizon\": \"Long\"}"
```

Response:
```json
{
  "execution_id": "exec_...",
  "status": "pending"
}
```

### Check Status
```bash
curl http://localhost:8000/portfolio/execution/exec_... ^
  -H "x-demo-user: test-user"
```

### List Portfolios
```bash
curl http://localhost:8000/portfolio/list ^
  -H "x-demo-user: test-user"
```

---

## Environment Variables

### Required
| Variable | Description |
|----------|-------------|
| `OPENROUTER_API_KEY` | Your OpenRouter API key for LLM |

### Optional (Market Data)
| Variable | Default | Description |
|----------|---------|-------------|
| `ALPHA_VANTAGE_API_KEY` | - | Alpha Vantage API key |
| `FMP_API_KEY` | - | Financial Modeling Prep API key |

### Optional (Authentication)
| Variable | Default | Description |
|----------|---------|-------------|
| `AUTH_DISABLED` | `false` | Set to `true` for local dev (skips JWT) |
| `FIREBASE_PROJECT_ID` | - | Firebase project ID |
| `GOOGLE_APPLICATION_CREDENTIALS` | - | Path to service account JSON |

### Optional (Configuration)
| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_URL` | `postgresql://flowvest:flowvest123@postgres:5432/flowvest` | PostgreSQL connection |
| `REDIS_URL` | `redis://redis:6379/0` | Redis connection |
| `CORS_ORIGINS` | `http://localhost:3000,http://localhost:5173` | Allowed CORS origins |

---

## Troubleshooting

### Common Issues

#### "Connection refused" to backend
- Make sure Docker containers are running: `docker-compose ps`
- Check logs: `docker-compose logs backend`

#### Market data failures
- Expected if API keys are missing/limited
- System automatically falls back to deterministic data generator
- Check logs for provider error details

#### Celery worker not processing tasks
- Check worker logs: `docker-compose logs celery-worker`
- Verify Redis is running: `docker-compose ps redis`

#### Frontend not connecting to backend
- Backend must be running on localhost:8000
- Check browser console for CORS errors

---

## Project Structure

```
FlowVest-AI/
├── backend/                 # FastAPI + Celery backend
│   ├── agents/            # AI agents (Market, Analysis, Allocation, etc.)
│   ├── providers/        # Market data providers
│   ├── routers/        # API endpoints
│   ├── tasks/          # Celery tasks
│   └── services/       # Business logic
├── src/                  # React frontend
├── frontend/              # Alternative frontend (mirror)
├── docker-compose.yml       # Docker orchestration
├── package.json          # Frontend dependencies
└── .env.example         # Environment template
```

---

## Next Steps

- Read the full [README.md](./README.md) for architecture details
- Check [PRD.md](./PRD.md) for feature specifications
- See [DEPLOYMENT.md](./DEPLOYMENT.md) for production deployment

---

**Note**: This is for educational and demonstration purposes. The portfolios generated are illustrative and should not be treated as professional investment advice.