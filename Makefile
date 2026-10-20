.PHONY: check check-py check-web test-db dev-api dev-web worker migrate build-web sim

PY_TYPED = packages/notchcount_stats/src packages/pipeline/src services/api/src services/worker/src

check: check-py check-web

check-py:
	uv run ruff check .
	uv run ruff format --check .
	uv run mypy $(PY_TYPED)
	uv run pytest -q -m "not db and not models"

test-db:
	uv run pytest -q -m "db"

check-web:
	cd apps/web && pnpm run lint && pnpm run check && pnpm run test:unit -- --run && pnpm run build && pnpm run test:e2e

migrate:
	cd services/api && uv run alembic upgrade head

dev-api:
	uv run uvicorn notchcount_api.main:app --reload --port 8000

dev-web:
	cd apps/web && pnpm run dev

worker:
	uv run nc-worker

build-web:
	cd apps/web && pnpm install --frozen-lockfile && pnpm run build

sim:
	uv run python -m sim.run --replicates 1000 --out docs/ESTIMATOR_VALIDATION.md
