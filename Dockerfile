# One image for the web app (static build) and the API; the worker reuses it with a different command.
FROM node:24-slim AS web
WORKDIR /app/apps/web
RUN corepack enable
COPY apps/web/package.json apps/web/pnpm-lock.yaml apps/web/pnpm-workspace.yaml ./
RUN pnpm install --frozen-lockfile
COPY apps/web/ ./
RUN pnpm run build

FROM python:3.12-slim AS app
COPY --from=ghcr.io/astral-sh/uv:0.8.23 /uv /usr/local/bin/uv
RUN apt-get update && apt-get install -y --no-install-recommends libglib2.0-0 && rm -rf /var/lib/apt/lists/*
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=never PYTHONUNBUFFERED=1
WORKDIR /app
COPY pyproject.toml uv.lock ./
COPY packages/notchcount_stats/pyproject.toml packages/notchcount_stats/
COPY packages/pipeline/pyproject.toml packages/pipeline/
COPY services/api/pyproject.toml services/api/
COPY services/worker/pyproject.toml services/worker/
RUN uv sync --frozen --no-dev --no-install-workspace --package notchcount-worker
COPY packages packages
COPY services services
COPY config config
COPY models models
RUN python models/download.py models/cache detector.onnx dinov2_vits14_int8.onnx
RUN uv sync --frozen --no-dev --package notchcount-worker
COPY --from=web /app/apps/web/build apps/web/build
RUN useradd --create-home --uid 10001 app && chown -R app /app
USER app
ENV PATH="/app/.venv/bin:$PATH" NC_ENV=prod PORT=8080
EXPOSE 8080
CMD ["sh", "-c", "uvicorn notchcount_api.main:app --host 0.0.0.0 --port ${PORT} --proxy-headers --forwarded-allow-ips='*'"]
