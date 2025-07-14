.PHONY: help install dev test format lint type-check clean run-example

# Default target
help: ## Show this help message
	@echo "HR智能体简历筛选系统 - 开发命令"
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

install: ## Install dependencies
	uv sync

dev: ## Install development dependencies
	uv sync --group dev

test: ## Run tests
	uv run pytest -v

test-cov: ## Run tests with coverage
	uv run pytest --cov=src --cov-report=html --cov-report=term

format: ## Format code
	uv run black src/ tests/ main.py
	uv run isort src/ tests/ main.py

lint: ## Run linting
	uv run flake8 src/ tests/ main.py
	uv run black --check src/ tests/ main.py
	uv run isort --check-only src/ tests/ main.py

type-check: ## Run type checking
	uv run mypy src/

clean: ## Clean up generated files
	rm -rf build/
	rm -rf dist/
	rm -rf *.egg-info/
	rm -rf .pytest_cache/
	rm -rf .coverage
	rm -rf htmlcov/
	rm -rf .mypy_cache/
	find . -type d -name __pycache__ -delete
	find . -type f -name "*.pyc" -delete

run-example: ## Run example workflow
	./examples/test_run.sh

run-interactive: ## Run in interactive mode
	uv run python main.py --interactive

build: ## Build the package
	uv build

check: format lint type-check test ## Run all checks

pre-commit: ## Install pre-commit hooks
	uv run pre-commit install

# Development shortcuts
setup: install dev pre-commit ## Set up development environment

all: clean format lint type-check test ## Run all quality checks