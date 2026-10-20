"""FastAPI app: JSON API under /api/v1 and, in production, the built web app at /."""

from __future__ import annotations

import asyncio
import logging
import time
import uuid
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import APIRouter, Depends, FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from sqlalchemy import text

from notchcount_api import logs as nc_logging
from notchcount_api.config import Settings, get_settings
from notchcount_api.db.session import get_sessionmaker
from notchcount_api.deps import csrf_guard
from notchcount_api.routers import auth, ops, passes, setup

log = logging.getLogger("notchcount.api")

SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "same-origin",
    "X-Frame-Options": "DENY",
    "Permissions-Policy": "camera=(self), geolocation=(self), microphone=()",
}


def _static_routes(app: FastAPI, build: Path) -> None:
    """Serve the SvelteKit static build; unknown paths fall back to the SPA shell."""
    shell = build / "200.html"
    root = build.resolve()

    @app.get("/{path:path}", include_in_schema=False)
    async def spa(path: str) -> Response:
        if path.startswith("api/"):
            return JSONResponse({"detail": "Not found."}, status_code=404)
        candidate = (build / path).resolve()
        if path and candidate.is_file() and candidate.is_relative_to(root):
            headers = {}
            if path.startswith("_app/immutable/"):
                headers["Cache-Control"] = "public, max-age=31536000, immutable"
            elif path in ("service-worker.js", "manifest.webmanifest"):
                headers["Cache-Control"] = "no-cache"
            return FileResponse(candidate, headers=headers)
        return FileResponse(shell, headers={"Cache-Control": "no-cache"})


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    nc_logging.configure()

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        task: asyncio.Task[None] | None = None
        if settings.run_worker_inprocess:
            from notchcount_worker.runner import run_forever

            task = asyncio.create_task(run_forever(stop=None))
            log.info("worker started in-process")
        yield
        if task is not None:
            task.cancel()

    app = FastAPI(
        title="NotchCount API",
        version="0.1.0",
        lifespan=lifespan,
        docs_url="/api/docs",
        openapi_url="/api/openapi.json",
    )
    if settings.cors_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.cors_origins,
            allow_credentials=True,
            allow_methods=["GET", "POST"],
            allow_headers=["content-type", "x-notchcount"],
        )

    @app.middleware("http")
    async def request_context(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        request_id = request.headers.get("x-request-id") or uuid.uuid4().hex[:16]
        start = time.perf_counter()
        response = await call_next(request)
        for k, v in SECURITY_HEADERS.items():
            response.headers.setdefault(k, v)
        response.headers["x-request-id"] = request_id
        if request.url.path.startswith("/api/"):
            log.info(
                "request",
                extra={
                    "request_id": request_id,
                    "method": request.method,
                    "path": request.url.path,
                    "status": response.status_code,
                    "ms": round((time.perf_counter() - start) * 1000, 1),
                },
            )
        return response

    api = APIRouter(prefix="/api/v1", dependencies=[Depends(csrf_guard)])
    for r in (auth.router, setup.router, passes.router, ops.router):
        api.include_router(r)
    app.include_router(api)

    @app.get("/healthz", include_in_schema=False)
    async def healthz() -> dict[str, str]:
        async with get_sessionmaker()() as db:
            await db.execute(text("select 1"))
        return {"status": "ok"}

    if settings.static_dir is not None and (settings.static_dir / "200.html").is_file():
        _static_routes(app, settings.static_dir)
    return app


app = create_app()
