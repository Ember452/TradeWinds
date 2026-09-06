.PHONY: lint fmt type test test-all dev migrate up down worker beat frontend backup restore

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

migrate:
	uv run alembic upgrade head

up:
	docker compose up -d --build

down:
	docker compose down

worker:
	uv run python -m tradewinds.tasks.worker

beat:
	uv run python -m tradewinds.tasks.beat

frontend:
	cd frontend && npm run dev

backup:
	./deploy/backup.sh

restore:
	./deploy/restore.sh $(file)
