# justfile for python-package-copier-template

# List available commands
default:
    @just --list

# Install dependencies
install:
    uv sync --group test --group docs

# Run tests
test:
    uv run pytest -v

# Run tests with coverage
test-cov:
    uv run pytest --cov --cov-report=html --cov-report=term

# Lint code
lint:
    uvx nox -s lint

# Format and fix code
fix:
    uvx nox -s fix

# Check code (lint + format check)
check: lint
    uv run ruff format --check

# Build documentation
docs:
    uvx nox -s build_docs

# Serve documentation locally
serve:
    uvx nox -s serve_docs

# Clean build artifacts
clean:
    rm -rf .nox
    rm -rf .pytest_cache
    rm -rf .ruff_cache
    rm -rf site
    rm -rf htmlcov
    rm -rf .coverage
    find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
    find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true

# Run all checks
all: check test

# Run pre-commit hooks on all files
pre-commit:
    uv run pre-commit run --all-files
