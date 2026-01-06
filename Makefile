.PHONY: install dev lint format test run docker-up docker-down migrate

# Install production dependencies
install:
	pip install -e .

# Install development dependencies
dev:
	pip install -e ".[dev]"
	pre-commit install

# Run linting
lint:
	ruff check src tests
	mypy src

# Format code
format:
	ruff format src tests
	ruff check --fix src tests

# Run tests
test:
	pytest tests/ -v --cov=src/agent_orchestrator --cov-report=term-missing

# Run tests in parallel
test-parallel:
	pytest tests/ -v -n auto --cov=src/agent_orchestrator

# Run unit tests only
test-unit:
	pytest tests/unit -v

# Run integration tests only
test-integration:
	pytest tests/integration -v

# Run the API server
run:
	uvicorn agent_orchestrator.api.app:create_app --factory --reload --host 0.0.0.0 --port 8000

# Run the agent worker
run-worker:
	python -m agent_orchestrator worker

# Start local infrastructure
docker-up:
	docker compose up -d

# Stop local infrastructure
docker-down:
	docker compose down

# Run database migrations
migrate:
	alembic upgrade head

# Create a new migration
migrate-create:
	@read -p "Migration message: " msg; \
	alembic revision --autogenerate -m "$$msg"

# Generate OpenAPI spec
openapi:
	python scripts/generate-openapi.py

# Build Docker image
docker-build:
	docker build -t agent-orchestrator:latest -f deploy/docker/Dockerfile .

# Clean up
clean:
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".mypy_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".ruff_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
