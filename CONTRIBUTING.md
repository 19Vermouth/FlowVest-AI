# Contributing to FlowVest AI

Thank you for your interest in contributing to FlowVest AI! This document provides guidelines and instructions for developers.

---

## 🚀 Quick Start for Developers

### 1. Clone and Setup

```bash
# Clone the repository
git clone https://github.com/your-org/flowvest-ai.git
cd flowvest-ai

# Copy environment template
cp .env.example .env

# Edit .env with your API keys (at minimum: OPENROUTER_API_KEY)
# For local dev, set AUTH_DISABLED=true

# Install dependencies
make install-dev

# Start infrastructure (Redis + PostgreSQL)
make dev
```

### 2. Start Development Servers

Open **three terminals**:

```bash
# Terminal 1: Backend API
make dev-backend

# Terminal 2: Frontend
make dev-frontend

# Terminal 3: Celery Worker
make celery
```

### 3. Verify Setup

- Frontend: http://localhost:5173
- Backend API: http://localhost:8000
- Swagger UI: http://localhost:8000/docs
- Flower (Celery monitoring): http://localhost:5555 (admin:flower123)

---

## 📋 Development Workflow

### 1. Create a Feature Branch

```bash
git checkout -b feature/your-feature-name
```

### 2. Make Changes

- Follow existing code style
- Add tests for new functionality
- Update documentation if needed

### 3. Run Pre-Commit Checks

```bash
# Install pre-commit hooks (first time only)
pre-commit install

# Or run manually
make lint
make typecheck
make test
```

### 4. Commit Changes

```bash
git add .
git commit -m "feat: add your feature description"
```

**Commit Message Convention** (based on [Conventional Commits](https://www.conventionalcommits.org/)):

- `feat:` New feature
- `fix:` Bug fix
- `docs:` Documentation changes
- `style:` Code style changes (formatting, etc.)
- `refactor:` Code refactoring (no functional changes)
- `test:` Adding or updating tests
- `chore:` Maintenance tasks (dependencies, config, etc.)

### 5. Push and Create Pull Request

```bash
git push origin feature/your-feature-name
```

Then create a PR on GitHub with:
- Clear description of changes
- Screenshots (if UI changes)
- Test results
- Any breaking changes noted

---

## 🧪 Testing

### Backend Tests

```bash
# Run all tests
make test-backend

# Run with coverage
make coverage

# Run specific test file
pytest backend/tests/test_portfolio.py -v

# Run with live output
pytest backend/tests/ -v -s
```

### Frontend Tests

```bash
# Run all tests
npm run test

# Run in watch mode
npm run test:watch

# Run with coverage
npm run test:coverage
```

### Writing Tests

**Backend Example** (`backend/tests/test_market_agent.py`):

```python
import pytest
from backend.agents.market_agent import MarketAgent
from backend.providers.manager import market_manager

@pytest.mark.asyncio
async def test_market_agent_fetches_data():
    agent = MarketAgent()
    result = await agent.run({}, {})

    assert "market_data" in result
    assert result["market_data"]["source"] in [
        "alpha_vantage", "fmp", "yfinance", "fallback"
    ]
    assert "nifty" in result["market_data"]
    assert "sensex" in result["market_data"]
    assert "gold" in result["market_data"]
```

**Frontend Example** (`src/__tests__/App.test.tsx`):

```tsx
import { render, screen } from '@testing-library/react'
import App from '../App'

test('renders landing page heading', () => {
  render(<App />)
  const heading = screen.getByText(/FlowVest AI/i)
  expect(heading).toBeInTheDocument()
})
```

---

## 🔧 Code Style

### Backend (Python)

- **Formatter**: ruff (auto-fixes on save)
- **Type Checker**: mypy (strict mode)
- **Line Length**: 100 characters
- **Imports**: Sorted automatically by ruff

```bash
# Format code
ruff check . --fix

# Type check
mypy backend/
```

### Frontend (TypeScript/React)

- **Formatter**: Prettier
- **Linter**: ESLint
- **Line Length**: 100 characters

```bash
# Format code
npm run format

# Lint
npm run lint
```

---

## 📁 Project Structure

```
flowvest-ai/
├── backend/                    # Python FastAPI backend
│   ├── agents/                # Multi-agent implementations
│   ├── orchestrator/          # DAG-aware orchestrator
│   ├── providers/             # Market data providers
│   ├── llm/                   # LLM abstraction layer
│   ├── middleware/            # Auth, rate limiting
│   ├── tasks/                 # Celery tasks
│   ├── services/              # Business logic
│   ├── models/                # SQLAlchemy ORM models
│   ├── routers/               # FastAPI route handlers
│   ├── db/                    # Database configuration
│   ├── tests/                 # Backend tests
│   └── requirements*.txt      # Python dependencies
├── src/                       # React frontend source
│   ├── App.tsx               # Main application component
│   ├── main.tsx              # Entry point
│   └── index.css             # Global styles
├── frontend/                  # Frontend mirror structure
├── dist/                      # Production build output
├── docker-compose.yml         # Docker services
├── Makefile                   # Development commands
├── package.json               # Node dependencies
└── .env.example              # Environment variables template
```

---

## 🐛 Debugging

### Backend

```bash
# Start with debug logging
export LOG_LEVEL=DEBUG
make dev-backend

# Use ipdb debugger
import ipdb; ipdb.set_trace()

# Inspect Celery tasks
celery -A backend.tasks.celery_app inspect active
celery -A backend.tasks.celery_app inspect registered
```

### Frontend

```bash
# Start with verbose logging
npm run dev

# React DevTools: Install browser extension
# Redux DevTools: Not needed (using Context API)
```

### Database

```bash
# Open PostgreSQL shell
make db-shell

# Common queries:
SELECT COUNT(*) FROM portfolios;
SELECT status, COUNT(*) FROM executions GROUP BY status;
SELECT * FROM agent_runs WHERE execution_id = '...';
```

---

## 🔐 Security

### Before Committing

- [ ] No secrets in code (API keys, passwords, etc.)
- [ ] `.env` file is gitignored
- [ ] Dependencies are up to date (`pip-audit`, `npm audit`)
- [ ] SQL queries use parameterised statements (ORM handles this)
- [ ] User input is validated (Pydantic schemas)

### Running Security Audits

```bash
make security
```

---

## 📦 Deployment

### Local Docker Deployment

```bash
make docker-up
```

### Production Deployment

See `DEPLOYMENT.md` for production deployment guide.

---

## 🆘 Getting Help

- **Documentation**: `README.md`, `PRD.md`, `ScratchPad.md`
- **Issues**: GitHub Issues tab
- **Discussions**: GitHub Discussions tab
- **Code of Conduct**: Please be respectful and inclusive

---

## 🎯 Areas Needing Contributions

- [ ] PDF export functionality
- [ ] Portfolio performance tracking
- [ ] Email notifications
- [ ] Admin dashboard
- [ ] Multi-language support (i18n)
- [ ] Mobile app (React Native)
- [ ] More unit tests (target: 80% coverage)
- [ ] Documentation improvements

---

Thank you for contributing to FlowVest AI! 🚀
