.PHONY: lint fmt type test test-all dev

lint:
	uv run ruff check .
	uv run ruff format --check .

fmt:
	uv run ruff format .
	uv run ruff check --fix .

type:
	uv run mypy

test:
	uv run pytest -m "not integration"

test-all:
	uv run pytest

dev:
	uv run uvicorn tradewinds.api.app:create_app --factory --reload
