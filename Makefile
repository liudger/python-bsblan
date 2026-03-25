.PHONY: setup lint test coverage

setup: ## Install dev dependencies and git hooks
	uv sync --dev
	uv run prek install

lint: ## Run all pre-commit hooks
	uv run prek run --all-files

test: ## Run tests
	uv run pytest

coverage: ## Run tests with coverage report
	uv run pytest --cov=src/bsblan --cov-report=term-missing
