# 多阶段构建:builder 用 uv 装依赖,运行时只带虚拟环境,非 root 运行
FROM python:3.13-slim AS builder

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv
WORKDIR /app

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

COPY . .
RUN uv sync --frozen --no-dev

FROM python:3.13-slim

RUN useradd --create-home --uid 1000 tradewinds
WORKDIR /app

COPY --from=builder /app/.venv /app/.venv
COPY --from=builder /app/src /app/src
COPY --from=builder /app/alembic /app/alembic
COPY --from=builder /app/alembic.ini /app/alembic.ini

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1

USER tradewinds

# --proxy-headers:信任 Caddy 传入的 X-Forwarded-For,IP 限流按真实客户端 IP 计数
CMD ["uvicorn", "tradewinds.api.app:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers"]
