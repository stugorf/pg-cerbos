#!/usr/bin/env just

# Load .env automatically (Compose also auto-loads .env in the cwd)
set dotenv-load

# Default: show available recipes
default:
    @just --list

# =============================================================================
# DOCKER INFRASTRUCTURE
# =============================================================================

# Bring the stack up (build images if needed)
up:
    docker compose up -d
    @echo "⏳ Waiting for services to be ready..."
    @sleep 10
    @echo "✅ Infrastructure is ready!"
    @echo "💡 Run 'just init' to complete system initialization"

# Bring the stack up and force rebuild all images
up-build:
    docker compose up -d --build
    @echo "⏳ Waiting for services to be ready..."
    @sleep 10
    @echo "✅ Infrastructure is ready!"
    @echo "💡 Run 'just init' to complete system initialization"

# Tear everything down and remove volumes
down:
    docker compose down -v

# Tail service logs
logs:
    docker compose logs -f --tail=200

# Show container status
ps:
    docker compose ps

# Initialize Iceberg objects via Envoy → Trino (DEPRECATED - now handled by 'just init')
# init-iceberg:
#     bash scripts/init_iceberg.sh

# Robust Iceberg initialization with catalog persistence
init-iceberg-robust:
    @echo "🚀 Robust Iceberg Initialization with Catalog Persistence"
    @echo "========================================================"
    @echo "This will initialize Iceberg with persistent catalog state"
    @echo "and create the missing schemas and tables."
    @echo ""
    bash scripts/init-iceberg-robust.sh

# Complete system initialization for new developers
init:
    chmod +x scripts/init.sh
    bash scripts/init.sh

# Complete setup: up + init (for new developers)
setup-mvp:
    @echo "🚀 Complete pg-cerbos Setup for New Developers"
    @echo "============================================="
    @echo "1️⃣  Starting infrastructure..."
    @just up
    @echo ""
    @echo "2️⃣  Initializing system..."
    @just init
    @echo ""
    @echo "🎉 Setup complete! Your system is ready to use."
    @echo "🌐 Access the UI at: http://localhost:8083/auth.html"


# =============================================================================
# Cerbos Management Commands
# =============================================================================

# Check Cerbos service health
check-cerbos:
    @echo "🔍 Checking Cerbos service health..."
    @curl -s http://localhost:3593/_cerbos/health | jq || echo "❌ Cerbos not responding"

# Check Cerbos configuration
check-cerbos-config:
    bash scripts/check-cerbos-config.sh

# Validate Cerbos policies
validate-cerbos-policies:
    @echo "🔍 Validating Cerbos policies..."
    @if command -v cerbos >/dev/null 2>&1; then \
        cerbos compile cerbos/policies || echo "❌ Policy validation failed"; \
    else \
        echo "⚠️  Cerbos CLI not installed. Install with: brew install cerbos"; \
        echo "   Or validate via Docker: docker run --rm -v $(pwd)/cerbos/policies:/policies ghcr.io/cerbos/cerbos:latest compile /policies"; \
    fi

# Test Cerbos policies
test-cerbos-policies:
    @echo "🧪 Running Cerbos policy tests..."
    @if command -v cerbos >/dev/null 2>&1; then \
        cerbos test cerbos/policies/tests/test_suite.yaml || echo "❌ Policy tests failed"; \
    else \
        echo "⚠️  Cerbos CLI not installed. Install with: brew install cerbos"; \
        echo "   Or test via Docker: docker run --rm -v $(pwd)/cerbos/policies:/policies ghcr.io/cerbos/cerbos:latest test /policies/tests/test_suite.yaml"; \
    fi

# Validate AML Cerbos policies
validate-aml-policies:
    @echo "🔍 Validating AML Cerbos policies..."
    @if command -v cerbos >/dev/null 2>&1; then \
        cerbos compile cerbos/policies || echo "❌ AML policy validation failed"; \
    else \
        echo "⚠️  Cerbos CLI not installed. Install with: brew install cerbos"; \
        echo "   Or validate via Docker: docker run --rm -v $(pwd)/cerbos/policies:/policies ghcr.io/cerbos/cerbos:latest compile /policies"; \
    fi

# Initialize PuppyGraph (wait for service and provide upload instructions)
init-puppygraph:
    bash scripts/init-puppygraph.sh

# Load PuppyGraph AML schema
load-puppygraph-schema:
    bash scripts/load-puppygraph-schema.sh

# Check PuppyGraph health
check-puppygraph:
    @echo "🔍 Checking PuppyGraph service health..."
    @curl -s http://localhost:8081/api/health | jq || echo "❌ PuppyGraph not responding"

# Activate PuppyGraph schema for query execution (uploads via API)
activate-puppygraph-schema:
    bash scripts/activate-puppygraph-schema.sh

# Test PuppyGraph schema loading
test-puppygraph-schema:
    bash tests/test-schema-loading.sh

# Test PuppyGraph schema API
test-puppygraph-api:
    bash tests/test-schema-api.sh

# Test PuppyGraph schema validation
test-puppygraph-validation:
    bash tests/test-schema-validation.sh

# Test PuppyGraph vertex queries
test-puppygraph-vertices:
    bash tests/test-vertex-queries.sh

# Test PuppyGraph edge queries
test-puppygraph-edges:
    bash tests/test-edge-queries.sh

# Test PuppyGraph complex queries
test-puppygraph-complex:
    bash tests/test-complex-queries.sh

# Test PuppyGraph schema format
test-puppygraph-format:
    bash tests/test-schema-format.sh

# Test PuppyGraph version compatibility
test-puppygraph-version:
    bash tests/test-version-compatibility.sh

# Test PuppyGraph configuration persistence
test-puppygraph-persistence:
    bash tests/test-configuration-persistence.sh

# Run all PuppyGraph tests
test-puppygraph-all:
    @echo "🧪 Running all PuppyGraph tests..."
    just test-puppygraph-format
    just test-puppygraph-version
    just test-puppygraph-schema
    just test-puppygraph-api
    just test-puppygraph-validation
    just test-puppygraph-vertices
    just test-puppygraph-edges
    just test-puppygraph-complex
    just test-puppygraph-persistence
    @echo "✅ All PuppyGraph tests passed!"

# List Cerbos policies
list-cerbos-policies:
    @echo "📋 Listing Cerbos policies..."
    @find cerbos/policies -name "*.yaml" -o -name "*.yml" | sort

# Show Cerbos service logs
cerbos-logs:
    docker compose logs -f cerbos


# Test authorization flow
test-auth:
    bash scripts/test-authorization.sh

# Verify system setup and test authentication
verify:
    bash scripts/verify_setup.sh

# Run the demo queries against Postgres (via backend API with Cerbos auth)
demo-postgres:
    @echo "🔐 Getting auth token..."
    @TOKEN=$$(curl -s -X POST http://localhost:8082/auth/login \
        -H "Content-Type: application/json" \
        -d '{"email": "fullaccess@pg-cerbos.com", "password": "user123"}' \
        | jq -r '.access_token'); \
    echo "📊 Querying Postgres..."; \
    curl -sS -X POST \
        -H "Authorization: Bearer $$TOKEN" \
        -H "Content-Type: application/json" \
        -d '{"query": "SELECT COUNT(*) as total_records FROM postgres.public.person"}' \
        http://localhost:8082/query | jq

# Run the demo queries against Iceberg (via backend API with Cerbos auth)
demo-iceberg:
    @echo "🔐 Getting auth token..."
    @TOKEN=$$(curl -s -X POST http://localhost:8082/auth/login \
        -H "Content-Type: application/json" \
        -d '{"email": "fullaccess@pg-cerbos.com", "password": "user123"}' \
        | jq -r '.access_token'); \
    echo "📊 Querying Iceberg..."; \
    curl -sS -X POST \
        -H "Authorization: Bearer $$TOKEN" \
        -H "Content-Type: application/json" \
        -d '{"query": "SELECT COUNT(*) as total_records FROM iceberg.demo.employee_performance"}' \
        http://localhost:8082/query | jq

# Rebuild and bounce a single service (usage: just rebuild trino)
rebuild SERVICE:
    docker compose build {{SERVICE}} && docker compose up -d {{SERVICE}}

# =============================================================================
# PYTHON DEVELOPMENT
# =============================================================================

# Install development dependencies
install-dev:
    pip install -e ".[dev]"

# Install the package in development mode
install:
    pip install -e .

# Run tests
test:
    python -m pytest tests/ -v

# Run tests with coverage
test-cov:
    python -m pytest tests/ --cov=pg_cerbos --cov-report=html --cov-report=term

# Test Cypher parser specifically
test-cypher-parser:
    @echo "🧪 Running Cypher parser tests..."
    @if docker compose ps policy-registry-backend 2>/dev/null | grep -q "Up"; then \
        echo "Running tests in Docker container..."; \
        docker compose exec policy-registry-backend pip install pytest >/dev/null 2>&1 || true; \
        docker compose exec policy-registry-backend python -m pytest test_cypher_parser.py -v; \
    elif command -v uv >/dev/null 2>&1; then \
        echo "Using uv to run tests..."; \
        cd policy-registry/backend && \
        uv venv .venv 2>/dev/null || true && \
        uv pip install -r requirements.txt && \
        uv run pytest test_cypher_parser.py -v; \
    elif command -v python3 >/dev/null 2>&1; then \
        cd policy-registry/backend && python3 -m pytest test_cypher_parser.py -v; \
    elif command -v python >/dev/null 2>&1; then \
        cd policy-registry/backend && python -m pytest test_cypher_parser.py -v; \
    else \
        echo "❌ uv or Python not found. Please install uv, Python 3, or start Docker containers with 'just up'"; \
        exit 1; \
    fi

# Run linting
lint:
    python -m ruff check src/ tests/
    python -m ruff format src/ tests/

# Run type checking
type-check:
    python -m mypy src/ tests/

# Build the package
build:
    python -m build

# Clean build artifacts
clean:
    rm -rf build/
    rm -rf dist/
    rm -rf *.egg-info/
    find . -type d -name __pycache__ -delete
    find . -type f -name "*.pyc" -delete

# Run the application
run:
    python -m pg_cerbos

# Start development server (if you add one)
dev:
    python -m pg_cerbos --dev

# Format code
format:
    python -m ruff format src/ tests/

# Check code quality
check:
    @echo "Running code quality checks..."
    just lint
    just type-check
    @echo "Code quality checks complete!"

# Install all development tools
install-tools:
    pip install ruff mypy pytest pytest-cov build pre-commit

# Install pre-commit hooks
install-hooks:
    pre-commit install

# Run pre-commit on all files
pre-commit:
    pre-commit run --all-files

# Create virtual environment
venv:
    python3 -m venv .venv
    @echo "Virtual environment created. Activate with: source .venv/bin/activate"

# =============================================================================
# UTILITIES & INFO
# =============================================================================

# Quick dependency check (enhanced for both Docker and Python)
deps:
    @echo "Checking Docker dependencies..."
    which docker >/dev/null && (echo "✓ docker found: $(docker --version)" || echo "✗ docker not found")
    which jq >/dev/null && (echo "✓ jq found: $(jq --version)" || echo "✗ jq not found")
    which curl >/dev/null && (echo "✓ curl found: $(curl --version | head -1)" || echo "✗ curl not found")
    @echo ""
    @echo "Checking Python dependencies..."
    which python3 >/dev/null && (echo "✓ python3 found: $(python3 --version)" || echo "✗ python3 not found")
    which python >/dev/null && (echo "✓ python found: $(python --version)" || echo "✗ python not found")
    which pip3 >/dev/null && (echo "✓ pip3 found: $(pip3 --version)" || echo "✗ pip3 not found")
    which pip >/dev/null && (echo "✓ pip found: $(pip --version)" || echo "✗ pip not found")
    @echo ""
    @echo "Dependency check complete!"

# Show project info
info:
    @echo "Project: pg-cerbos"
    @echo "Current directory: $(pwd)"
    @echo ""
    @echo "Docker status:"
    @which docker >/dev/null && (docker compose ps 2>/dev/null | head -5 || echo "  No containers running") || echo "  Docker not available"
    @echo ""
    @echo "Python versions available:"
    @which python3 >/dev/null && echo "  python3: $(python3 --version)" || echo "  python3: not found"
    @which python >/dev/null && echo "  python: $(python --version)" || echo "  python: not found"
    @echo ""
    @echo "Package status:"
    @pip3 show pg-cerbos 2>/dev/null | grep Location || echo "  Not installed via pip3"
    @pip show pg-cerbos 2>/dev/null | grep Location || echo "  Not installed via pip"

# Check Python version compatibility
check-python:
    @echo "Checking Python version compatibility..."
    @echo "Project requires: Python >=3.12"
    @which python3 >/dev/null && (python3 -c "import sys; ver=sys.version_info; exit(0 if ver.major==3 and ver.minor>=12 else 1)" && echo "✓ python3 version compatible" || echo "✗ python3 version incompatible")
    @which python >/dev/null && (python -c "import sys; ver=sys.version_info; exit(0 if ver.major==3 and ver.minor>=12 else 1)" && echo "✓ python version incompatible")

# Setup development environment
setup:
    @echo "Setting up development environment..."
    just check-python
    just venv
    @echo "Now activate the virtual environment: source .venv/bin/activate"
    @echo "Then install dependencies: just install"

# Show help
help:
    @echo "pg-cerbos Development Commands"
    @echo ""
    @echo "Docker Infrastructure:"
    @echo "  up            - Bring the stack up (no rebuild)"
    @echo "  up-build      - Bring the stack up and force rebuild"
    @echo "  down          - Tear everything down"
    @echo "  logs          - Tail service logs"
    @echo "  ps            - Show container status"
    @echo "  init          - Complete system initialization for new developers"
    @echo "  setup-mvp     - Complete setup: up + init (for new developers)"
    @echo "  verify        - Verify system setup and test authentication"
    @echo "  init-iceberg  - Initialize Iceberg objects (DEPRECATED - use 'just init')"
    @echo "  demo-postgres - Run demo queries against Postgres"
    @echo "  demo-iceberg  - Run demo queries against Iceberg"
    @echo "  rebuild       - Rebuild and restart a service"
    @echo ""
    @echo "Setup:"
    @echo "  setup         - Set up development environment"
    @echo "  install-tools - Install development tools"
    @echo "  venv          - Create virtual environment"
    @echo ""
    @echo "Development:"
    @echo "  install       - Install package in development mode"
    @echo "  install-dev   - Install with development dependencies"
    @echo "  run           - Run the application"
    @echo "  dev           - Run in development mode"
    @echo ""
    @echo "Quality:"
    @echo "  check         - Run all quality checks"
    @echo "  lint          - Run linting"
    @echo "  format        - Format code"
    @echo "  type-check    - Run type checking"
    @echo "  test          - Run tests"
    @echo "  test-cov      - Run tests with coverage"
    @echo ""
    @echo "Build:"
    @echo "  build         - Build the package"
    @echo "  clean         - Clean build artifacts"
    @echo ""
    @echo "Info:"
    @echo "  info          - Show project information"
    @echo "  deps          - Check dependencies"
    @echo "  check-python  - Check Python version compatibility" 

# =============================================================================
# MONITORING & STATUS
# =============================================================================

# Show Trino logs
trino-logs:
    docker compose logs -f trino-coordinator trino-worker

# Show all service logs
all-logs:
    docker compose logs -f

# Check Trino cluster status
trino-status:
    curl -s http://localhost:8080/v1/info | jq

# Check running queries
running-queries:
    curl -s http://localhost:8080/v1/query | jq '.[] | select(.state == "RUNNING") | {queryId, state, elapsedTime, progress}' 