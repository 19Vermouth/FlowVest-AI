# ═══════════════════════════════════════════════════════════════════════════════
# FlowVest AI — Makefile (Developer Convenience Commands)
# ═══════════════════════════════════════════════════════════════════════════════
# Usage:
#   make help              # Show all commands
#   make install           # Install all dependencies
#   make dev               # Start local development environment
#   make test              # Run all tests
#   make lint              # Run linters
#   make build             # Build for production
#   make docker-up         # Start Docker Compose stack
#   make docker-down       # Stop Docker Compose stack
# ═══════════════════════════════════════════════════════════════════════════════

.PHONY: help install dev test lint format build docker-up docker-down clean

# ── Default Target ─────────────────────────────────────────────────────────────
help:
	@echo "FlowVest AI — Development Commands"
	@echo "===================================="
	@echo ""
	@echo "Setup:"
	@echo "  make install           Install all dependencies (backend + frontend)"
	@echo "  make install-backend   Install Python dependencies only"
	@echo "  make install-frontend  Install Node dependencies only"
	@echo "  make env               Copy .env.example to .env"
	@echo ""
	@echo "Development:"
	@echo "  make dev               Start local dev environment (Redis + Postgres)"
	@echo "  make dev-backend       Start backend with auto-reload"
	@echo "  make dev-frontend      Start frontend dev server"
	@echo "  make celery            Start Celery worker"
	@echo "  make flower            Start Flower monitoring UI"
	@echo ""
	@echo "Testing:"
	@echo "  make test              Run all tests (backend + frontend)"
	@echo "  make test-backend      Run backend tests only"
	@echo "  make test-frontend     Run frontend tests only"
	@echo "  make coverage          Run tests with coverage report"
	@echo ""
	@echo "Code Quality:"
	@echo "  make lint              Run all linters"
	@echo "  make lint-backend      Lint Python code (ruff + mypy)"
	@echo "  make lint-frontend     Lint TypeScript code (eslint)"
	@echo "  make format            Format all code"
	@echo "  make typecheck         Run type checker (mypy + tsc)"
	@echo ""
	@echo "Build:"
	@echo "  make build             Build frontend for production"
	@echo "  make build-docker      Build Docker images"
	@echo ""
	@echo "Docker:"
	@echo "  make docker-up         Start full Docker Compose stack"
	@echo "  make docker-down       Stop Docker Compose stack"
	@echo "  make docker-logs       Follow all container logs"
	@echo "  make docker-clean      Remove all containers and volumes (CAUTION)"
	@echo ""
	@echo "Database:"
	@echo "  make db-migrate        Run Alembic migrations"
	@echo "  make db-migration NAME=xyz  Create new migration"
	@echo "  make db-shell          Open PostgreSQL shell"
	@echo ""
	@echo "Utilities:"
	@echo "  make clean             Remove build artifacts and caches"
	@echo "  make security          Run security audits (pip-audit + npm audit)"
	@echo ""

# ── Setup ──────────────────────────────────────────────────────────────────────
install: install-backend install-frontend
	@echo "✓ All dependencies installed"

install-backend:
	@echo "Installing backend dependencies..."
	cd backend && pip install -r requirements.txt
	@echo "✓ Backend dependencies installed"

install-frontend:
	@echo "Installing frontend dependencies..."
	npm install
	@echo "✓ Frontend dependencies installed"

install-dev:
	@echo "Installing development dependencies..."
	cd backend && pip install -r requirements-dev.txt
	npm install
	@echo "✓ Development dependencies installed"

env:
	@echo "Creating .env from .env.example..."
	cp .env.example .env
	@echo "✓ .env created — Please edit with your API keys!"

# ── Development ────────────────────────────────────────────────────────────────
dev:
	@echo "Starting local development environment..."
	@echo "  - Redis:    localhost:6379"
	@echo "  - Postgres: localhost:5432"
	docker-compose up -d redis postgres
	@echo "✓ Redis and PostgreSQL started"
	@echo ""
	@echo "Next steps:"
	@echo "  1. Edit .env with your API keys"
	@echo "  2. Terminal 1: make dev-backend"
	@echo "  3. Terminal 2: make dev-frontend"
	@echo "  4. Terminal 3: make celery"

dev-backend:
	cd backend && uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload

dev-frontend:
	npm run dev

celery:
	cd backend && celery -A backend.tasks.celery_app worker --loglevel=info --pool=solo

flower:
	cd backend && celery -A backend.tasks.celery_app flower --port=5555

# ── Testing ────────────────────────────────────────────────────────────────────
test: test-backend test-frontend
	@echo "✓ All tests passed"

test-backend:
	cd backend && pytest backend/tests/ -v

test-frontend:
	npm run test

coverage:
	cd backend && pytest backend/tests/ -v --cov=backend --cov-report=html
	@echo "Coverage report: backend/htmlcov/index.html"

# ── Code Quality ───────────────────────────────────────────────────────────────
lint: lint-backend lint-frontend
	@echo "✓ All linters passed"

lint-backend:
	cd backend && ruff check .
	cd backend && mypy backend/

lint-frontend:
	npm run lint

format:
	cd backend && ruff check . --fix
	npm run format

typecheck:
	cd backend && mypy backend/ --no-error-summary
	npm run typecheck

# ── Build ──────────────────────────────────────────────────────────────────────
build:
	@echo "Building frontend for production..."
	npm run build
	@echo "✓ Production build: dist/index.html"

build-docker:
	docker-compose build

# ── Docker ─────────────────────────────────────────────────────────────────────
docker-up:
	docker-compose up --build -d
	@echo "✓ All services started"
	@echo "  - Backend:   http://localhost:8000"
	@echo "  - Flower:    http://localhost:5555 (admin:flower123)"
	@echo "  - Postgres:  localhost:5432"
	@echo "  - Redis:     localhost:6379"

docker-down:
	docker-compose down
	@echo "✓ All services stopped"

docker-logs:
	docker-compose logs -f

docker-clean:
	@echo "WARNING: This will remove all containers and volumes!"
	@echo "Press Ctrl+C to cancel..."
	sleep 3
	docker-compose down -v
	docker system prune -f
	@echo "✓ Docker cleaned"

# ── Database ───────────────────────────────────────────────────────────────────
db-migrate:
	cd backend && alembic upgrade head

db-migration:
ifndef NAME
	$(error NAME is required. Usage: make db-migration NAME=add_user_table)
endif
	cd backend && alembic revision --autogenerate -m "$(NAME)"

db-shell:
	docker-compose exec postgres psql -U flowvest -d flowvest

# ── Utilities ──────────────────────────────────────────────────────────────────
clean:
	@echo "Cleaning build artifacts..."
	rm -rf dist/
	rm -rf backend/__pycache__/
	rm -rf backend/**/__pycache__/
	rm -rf .pytest_cache/
	rm -rf .mypy_cache/
	rm -rf backend/htmlcov/
	rm -rf node_modules/
	@echo "✓ Cleaned"

security:
	@echo "Running security audits..."
	cd backend && pip-audit || true
	npm audit || true
	@echo "✓ Security audit complete"

# ── Shortcuts ──────────────────────────────────────────────────────────────────
up: docker-up
down: docker-down
logs: docker-logs
shell: db-shell
