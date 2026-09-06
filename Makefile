.PHONY: lint fmt type test test-all dev migrate up down worker beat frontend backup restore seed demo

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

seed:
	docker compose exec -T api python -m tradewinds.demo_seed

# 一键演示:起全栈(含 Mailpit)→ 迁移 → 演示数据 → 打印入口
demo: up
	docker compose exec -T api alembic upgrade head
	docker compose exec -T api python -m tradewinds.demo_seed
	@echo "演示入口: 前端 http://localhost | Mailpit 收件箱 http://localhost:8025 | 账号 demo@tradewinds.local / demo12345"
