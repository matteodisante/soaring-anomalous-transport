FROM python:3.12-slim

# uv handles dependency resolution/install per pyproject.toml + uv.lock
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

ENV UV_PROJECT_ENVIRONMENT=/app/.venv \
    PATH="/app/.venv/bin:$PATH"

# Install deps first so this layer is cached across code-only changes
COPY pyproject.toml uv.lock ./
RUN uv sync --locked --no-install-project

COPY . .
RUN uv sync --locked

CMD ["pytest"]
