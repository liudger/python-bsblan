.PHONY: setup lint test coverage docs docs-serve help

.DEFAULT_GOAL := help

help: ## Show this help message
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-15s\033[0m %s\n", $$1, $$2}'

setup: ## Install dev dependencies and git hooks
	uv sync --dev
	uv run prek install

lint: ## Run all pre-commit hooks
	uv run prek run --all-files

test: ## Run tests
	uv run pytest

coverage: ## Run tests with coverage report
	uv run pytest --cov=src/bsblan --cov-report=term-missing

docs: ## Build documentation
	uv run mkdocs build --strict

docs-serve: ## Serve documentation locally
	uv run mkdocs serve
