.PHONY: help install dev-install test coverage coverage-html lint format clean build publish examples pre-commit setup check

# Default target
help:
	@echo "Available targets:"
	@echo "  install      - Install the package and runtime dependencies (no dev tools)"
	@echo "  dev-install  - Install with all development dependencies"
	@echo "  test         - Run tests"
	@echo "  coverage     - Run tests with coverage report"
	@echo "  coverage-html - Run tests with coverage and open HTML report"
	@echo "  lint         - Run linting (black, isort, mypy, flake8)"
	@echo "  format       - Format code (black, isort)"
	@echo "  clean        - Clean build artifacts"
	@echo "  build        - Build package"
	@echo "  publish      - Publish to PyPI (requires UV_PUBLISH_TOKEN)"
	@echo "  examples     - Run example scripts"
	@echo "  pre-commit   - Install and run pre-commit hooks"
	@echo "  setup        - Complete development environment setup"
	@echo "  check        - Run all checks (lint + test + examples)"

# Install the package and runtime dependencies (no dev tools)
install:
	uv sync --no-dev

# Install with all development dependencies
dev-install:
	uv sync --all-extras

# Run tests (coverage is now automatic via pyproject.toml)
test:
	uv run pytest tests/

# Run tests with detailed coverage report
coverage:
	uv run scripts/coverage_report.sh

# Run tests with coverage and open HTML report
coverage-html:
	uv run scripts/coverage_report.sh --open

# Run linting
lint:
	uv run black --check dataclass_args/ tests/ examples/
	uv run isort --check-only dataclass_args/ tests/ examples/
	uv run mypy dataclass_args/
	uv run flake8 dataclass_args/

# Format code
format:
	uv run black dataclass_args/ tests/ examples/
	uv run isort dataclass_args/ tests/ examples/

# Clean build artifacts
clean:
	rm -rf build/
	rm -rf dist/
	rm -rf *.egg-info/
	rm -rf .pytest_cache/
	rm -rf htmlcov/
	rm -rf .coverage
	rm -rf coverage.xml
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete

# Build package
build: clean
	uv build

# Publish to PyPI
publish: build
	uv run twine check dist/*
	uv publish

# Run examples
examples:
	uv run scripts/run_examples.sh

# Install and run pre-commit hooks
pre-commit:
	uv run pre-commit install
	uv run pre-commit run --all-files

# Development setup
setup: dev-install pre-commit
	@echo "Development environment setup complete!"

# Full check (like CI)
check: lint test examples
	@echo "All checks passed!"
