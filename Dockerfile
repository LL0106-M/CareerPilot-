# syntax=docker/dockerfile:1.7

FROM node:22-alpine AS frontend-build
WORKDIR /build/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM ghcr.io/astral-sh/uv:0.12.21 AS uv

FROM python:3.12-slim AS runtime
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/app/.venv/bin:$PATH" \
    CAREERPILOT_ENVIRONMENT=production \
    CAREERPILOT_FRONTEND_DIST_PATH=/app/frontend/dist \
    CAREERPILOT_RAG_DB_PATH=/app/data/rag/careerpilot.db \
    CAREERPILOT_MEMORY_DB_PATH=/app/data/memory/careerpilot.db \
    CAREERPILOT_SESSION_DB_PATH=/app/data/sessions/careerpilot.db \
    CAREERPILOT_PRODUCT_DB_PATH=/app/data/product/careerpilot.db \
    CAREERPILOT_ACTION_DB_PATH=/app/data/actions/careerpilot.db

WORKDIR /app
COPY --from=uv /uv /uvx /bin/
COPY pyproject.toml uv.lock README.md ./
COPY src/ ./src/
RUN uv sync --frozen --no-dev --no-cache

COPY --from=frontend-build /build/frontend/dist ./frontend/dist
COPY data/rag/sources ./data/rag/sources

RUN useradd --create-home --uid 10001 careerpilot \
    && mkdir -p /app/data \
    && chown -R careerpilot:careerpilot /app/data

USER careerpilot
EXPOSE 8080
VOLUME ["/app/data"]

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8080/ready', timeout=3)"

CMD ["uvicorn", "careerpilot.api.app:app", "--host", "0.0.0.0", "--port", "8080", "--workers", "1", "--proxy-headers", "--forwarded-allow-ips=*"]
