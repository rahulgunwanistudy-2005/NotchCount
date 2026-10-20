"""Handlers by job kind. Model-backed handlers register only when their model files exist, so a
worker without models leaves those jobs queued for one that has them."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from notchcount_worker.runner import Handler


def available_handlers() -> dict[str, Handler]:
    handlers: dict[str, Handler] = {}
    try:
        from notchcount_worker.ingest import ingest_photo, models_ready
    except ImportError:
        return handlers
    if models_ready():
        handlers["ingest_photo"] = ingest_photo
    return handlers
