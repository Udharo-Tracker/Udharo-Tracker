FROM python:3.13-slim

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

# pyproject.toml and uv.lock live at the repo root (build context is ..)
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

COPY backend/ ./backend/

WORKDIR /app/backend

ENV PATH="/app/.venv/bin:$PATH"
