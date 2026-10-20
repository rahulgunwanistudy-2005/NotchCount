"""Public report (no sign-in): route-level numbers only, never where any single dog was seen."""

from __future__ import annotations

import json
import random
from datetime import datetime
from typing import Any

from fastapi import APIRouter, HTTPException, Response, status
from geoalchemy2.functions import ST_AsGeoJSON, ST_Simplify
from pydantic import BaseModel
from sqlalchemy import select

from notchcount_api.db.models import Estimate, RouteRow, Survey, Team
from notchcount_api.deps import DbDep, SettingsDep
from notchcount_api.reporting import ASSUMPTIONS, headline, method_lines, render_pdf

router = APIRouter(tags=["reports"])


class ReportOut(BaseModel):
    slug: str
    title: str
    team: str
    city: str
    route_name: str
    route: dict[str, Any]
    headline: dict[str, str | None]
    method: str
    method_lines: list[str]
    assumptions: list[str]
    results: dict[str, Any]
    code_version: str
    data_hash: str | None
    seed: int
    computed_at: datetime
    strip: list[dict[str, Any]]


def public_strip(individuals: list[dict[str, Any]], seed: int) -> list[dict[str, Any]]:
    """Dots for the public route strip with no position: shuffled order, evenly spaced. Shows who
    was seen in which walk and their ear status, never where an individual dog was."""
    rows = [{"passes": i["passes"], "status": i["status"]} for i in individuals]
    random.Random(seed).shuffle(rows)  # noqa: S311 (display order, not security)
    return rows


PUBLIC_RESULT_KEYS = (
    "counts",
    "population",
    "share",
    "deficit",
    "point_share",
    "chapman",
    "replicates",
    "single_pass",
    "comparability_problems",
    "passes",
    "target_share",
    "no_recapture_fraction",
    "decided_pairs",
    "pairs",
    "sightings",
)


async def _load(db: DbDep, slug: str) -> tuple[Survey, RouteRow, Team, Estimate, dict[str, Any]]:
    row = (
        await db.execute(
            select(Survey, RouteRow, Team, ST_AsGeoJSON(ST_Simplify(RouteRow.geom, 0.00005)))
            .join(RouteRow, RouteRow.id == Survey.route_id)
            .join(Team, Team.id == RouteRow.team_id)
            .where(Survey.public_slug == slug)
        )
    ).one_or_none()
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No report at this address.")
    survey, route, team, geo = row
    est = (
        await db.execute(
            select(Estimate)
            .where(Estimate.survey_id == survey.id, Estimate.status == "done")
            .order_by(Estimate.created_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    if est is None or est.results is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "This report has no estimate yet.")
    return survey, route, team, est, json.loads(geo)


@router.get("/reports/{slug}.pdf")
async def public_report_pdf(slug: str, db: DbDep, settings: SettingsDep) -> Response:
    _, route, team, est, _ = await _load(db, slug)
    assert est.results is not None
    pdf = render_pdf(
        title=f"Street dogs on {route.name}",
        route_name=route.name,
        city=team.city,
        results=est.results,
        method=est.method,
        code_version=est.code_version,
        data_hash=est.data_hash,
        created_at=est.created_at,
        report_url=f"{settings.public_base_url}/r/{slug}",
    )
    return Response(
        pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="notchcount-{slug}.pdf"'},
    )


# Registered after the .pdf route so "x.pdf" is not read as a slug.
@router.get("/reports/{slug}", response_model=ReportOut)
async def public_report(slug: str, db: DbDep) -> ReportOut:
    _, route, team, est, geo = await _load(db, slug)
    assert est.results is not None
    hl = headline(est.results)
    return ReportOut(
        slug=slug,
        title=f"Street dogs on {route.name}",
        team=team.name,
        city=team.city,
        route_name=route.name,
        route=geo,
        headline={"population": hl.population, "share": hl.share, "deficit": hl.deficit, "note": hl.note},
        method=est.method,
        method_lines=method_lines(est.results, est.method),
        assumptions=list(ASSUMPTIONS),
        results={k: est.results[k] for k in PUBLIC_RESULT_KEYS if k in est.results},
        strip=public_strip(est.results.get("individuals", []), est.seed),
        code_version=est.code_version,
        data_hash=est.data_hash,
        seed=est.seed,
        computed_at=est.created_at,
    )
