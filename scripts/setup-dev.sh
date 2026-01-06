#!/bin/bash
# Development environment setup script

set -e

echo "🚀 Setting up Agent Orchestrator development environment..."

# Check Python version
PYTHON_VERSION=$(python3 --version 2>&1 | cut -d' ' -f2 | cut -d'.' -f1,2)
REQUIRED_VERSION="3.12"

if [ "$(printf '%s\n' "$REQUIRED_VERSION" "$PYTHON_VERSION" | sort -V | head -n1)" != "$REQUIRED_VERSION" ]; then
    echo "❌ Python $REQUIRED_VERSION or higher is required. Found: $PYTHON_VERSION"
    exit 1
fi

echo "✅ Python $PYTHON_VERSION found"

# Create virtual environment if it doesn't exist
if [ ! -d ".venv" ]; then
    echo "📦 Creating virtual environment..."
    python3 -m venv .venv
fi

# Activate virtual environment
source .venv/bin/activate

# Upgrade pip
echo "⬆️  Upgrading pip..."
pip install --upgrade pip

# Install dependencies
echo "📚 Installing dependencies..."
pip install -e ".[dev]"

# Install pre-commit hooks
echo "🪝 Installing pre-commit hooks..."
pre-commit install

# Copy environment template if .env doesn't exist
if [ ! -f ".env" ]; then
    echo "📝 Creating .env from template..."
    cp .env.example .env
    echo "⚠️  Please update .env with your API keys"
fi

# Check if Docker is running
if command -v docker &> /dev/null; then
    if docker info &> /dev/null; then
        echo "🐳 Docker is running"

        # Start infrastructure
        read -p "Start local infrastructure (NATS, PostgreSQL, Redis)? [y/N] " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            echo "🏗️  Starting infrastructure..."
            docker compose up -d

            # Wait for services
            echo "⏳ Waiting for services to be ready..."
            sleep 5

            # Run migrations
            echo "🗃️  Running database migrations..."
            alembic upgrade head || echo "⚠️  Migrations skipped (may need to create initial migration)"
        fi
    else
        echo "⚠️  Docker is installed but not running"
    fi
else
    echo "⚠️  Docker is not installed. Install Docker to run local infrastructure."
fi

echo ""
echo "✨ Development environment setup complete!"
echo ""
echo "Next steps:"
echo "  1. Update .env with your API keys"
echo "  2. Start the API server: make run"
echo "  3. Start a worker: agent-orchestrator worker"
echo "  4. Visit http://localhost:8000/docs for API documentation"
echo ""
