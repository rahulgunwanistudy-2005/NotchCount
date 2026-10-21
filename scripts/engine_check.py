"""End-to-end engine check on REAL photos with real models, against a known truth.

Pass 1 uses real CC BY-SA street-dog photos (data/samples, from Wikimedia Commons) plus one photo
with people. Pass 2 is SYNTHETIC: the same dogs' photos re-shot by transforms (mirror, crop,
light, slight rotation), so which dogs appear in both passes is known. Everything else is the
production path: HTTP upload to the API, the worker's ingest with ONNX models, candidate pairs,
labels through the API, model training, estimate. Runs in the `notchcount_test` schema only.

    uv run python scripts/engine_check.py --api http://127.0.0.1:8002   # API started with NC_DB_SCHEMA=notchcount_test
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import io
import json
import os
import sys
import time
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path

os.environ["NC_DB_SCHEMA"] = "notchcount_test"

import httpx
import numpy as np
from geoalchemy2.functions import ST_GeomFromText
from PIL import Image, ImageEnhance, ImageOps
from sklearn.metrics import roc_auc_score
from sqlalchemy import func, select, text

from notchcount_api.auth.invites import create_invite
from notchcount_api.config import get_settings
from notchcount_api.db.models import (
    Base,
    Detection,
    Estimate,
    MatchPair,
    ModelVersion,
    PassRow,
    Photo,
    Role,
    RouteRow,
    Survey,
    Team,
    TeamMember,
    User,
)
from notchcount_api.db.session import get_engine, get_sessionmaker
from notchcount_worker.runner import registry, run_once

ROOT = Path(__file__).resolve().parents[1]
SAMPLES = ROOT / "data" / "samples"
IST = timedelta(hours=5, minutes=30)
LON0, LAT0 = 77.2085, 28.6135
STEP_DEG = 0.0006  # about 59 m of longitude at this latitude


def reshoot(data: bytes, seed: int) -> bytes:
    """A different photo of the same dog: mirrored, recropped, relit, slightly rotated."""
    rng = np.random.default_rng(seed)
    im = ImageOps.exif_transpose(Image.open(io.BytesIO(data))).convert("RGB")
    im = ImageOps.mirror(im)
    w, h = im.size
    f = rng.uniform(0.86, 0.95)
    x0, y0 = int(rng.uniform(0, w * (1 - f))), int(rng.uniform(0, h * (1 - f)))
    im = im.crop((x0, y0, x0 + int(w * f), y0 + int(h * f))).rotate(rng.uniform(-4, 4), expand=False)
    im = ImageEnhance.Brightness(im).enhance(rng.uniform(0.8, 1.2))
    im = ImageEnhance.Contrast(im).enhance(rng.uniform(0.85, 1.15))
    buf = io.BytesIO()
    im.save(buf, "JPEG", quality=85)
    return buf.getvalue()


async def reset_and_seed() -> dict[str, object]:
    assert get_settings().db_schema == "notchcount_test"
    tables = ", ".join(t.name for t in reversed(Base.metadata.sorted_tables))
    async with get_engine().begin() as conn:
        await conn.execute(text(f"truncate {tables} restart identity cascade"))
    async with get_sessionmaker()() as db:
        team = Team(name="Engine check (synthetic pass 2)", city="Test city")
        user = User(auth_subject=f"engine:{uuid.uuid4()}", display_name="Engine checker")
        db.add_all([team, user])
        await db.flush()
        db.add(TeamMember(team_id=team.id, user_id=user.id, role=Role.ADMIN))
        route = RouteRow(
            team_id=team.id,
            name="Check lane",
            corridor_m=40,
            geom=ST_GeomFromText(f"LINESTRING({LON0} {LAT0}, {LON0 + STEP_DEG * 17} {LAT0})", 4326),
        )
        db.add(route)
        await db.flush()
        from datetime import time as dtime

        survey = Survey(route_id=route.id, name="Engine check", start_window_local=dtime(6, 30))
        db.add(survey)
        await db.flush()
        today = (datetime.now(UTC) + IST).date()
        starts = [
            datetime.combine(today - timedelta(days=2 - k), dtime(1, 0), tzinfo=UTC) for k in (0, 1)
        ]  # 06:30 IST on two consecutive mornings
        passes = []
        for k, start in enumerate(starts, 1):
            p = PassRow(
                survey_id=survey.id,
                pass_no=k,
                observer_id=user.id,
                started_at=start,
                ended_at=start + timedelta(minutes=45),
                locked=True,
            )
            db.add(p)
            passes.append(p)
        code = await create_invite(db, user.id)
        await db.commit()
        return {
            "code": code,
            "survey_id": str(survey.id),
            "team_id": str(team.id),
            "passes": [(str(p.id), p.started_at) for p in passes],
        }


async def upload_all(
    api: httpx.AsyncClient, seed: dict[str, object], dog_files: list[Path]
) -> dict[str, object]:
    (p1_id, p1_start), (p2_id, p2_start) = seed["passes"]  # type: ignore[misc]
    n = len(dog_files)
    pass1 = list(range(0, n - 3))  # first n-3 dogs seen on walk 1
    pass2 = list(range(3, n))  # last n-3 dogs seen on walk 2
    truth_photo: dict[str, int] = {}
    timings: list[float] = []

    async def send(pass_id: str, data: bytes, taken: datetime, dog: int | None, lon: float) -> str:
        r = await api.post(
            f"/api/v1/passes/{pass_id}/photos",
            data={
                "sha256": hashlib.sha256(data).hexdigest(),
                "taken_at": taken.isoformat(),
                "shot": "side",
                "lat": str(LAT0 + 0.00005),
                "lon": str(lon),
                "accuracy_m": "6",
            },
            files={"file": ("p.jpg", data, "image/jpeg")},
        )
        r.raise_for_status()
        pid = r.json()["id"]
        if dog is not None:
            truth_photo[pid] = dog
        return str(pid)

    for k, d in enumerate(pass1):
        data = dog_files[d].read_bytes()
        t0 = time.perf_counter()
        await send(p1_id, data, p1_start + timedelta(minutes=2 + 2 * k), d, LON0 + STEP_DEG * (d + 0.5))
        timings.append(time.perf_counter() - t0)
    people = (SAMPLES / "people_bus.jpg").read_bytes()
    people_id = await send(p1_id, people, p1_start + timedelta(minutes=40), None, LON0 + STEP_DEG * 8)
    for k, d in enumerate(pass2):
        data = reshoot(dog_files[d].read_bytes(), seed=100 + d)
        await send(
            p2_id, data, p2_start + timedelta(minutes=2 + 2 * k), d, LON0 + STEP_DEG * (d + 0.5) + 0.00008
        )
    return {
        "truth_photo": truth_photo,
        "pass1": pass1,
        "pass2": pass2,
        "people_photo": people_id,
        "upload_ms": [round(t * 1000) for t in timings],
    }


async def drain(handlers: dict[str, object]) -> int:
    n = 0
    while await run_once("engine-check", handlers):  # type: ignore[arg-type]
        n += 1
    return n


async def main(api_url: str) -> None:
    dog_files = sorted(SAMPLES.glob("dog_*.jpg"))
    seed = await reset_and_seed()
    report: dict[str, object] = {"started": datetime.now(UTC).isoformat(), "dog_photos": len(dog_files)}
    async with httpx.AsyncClient(base_url=api_url, headers={"x-notchcount": "1"}, timeout=60) as api:
        (await api.post("/api/v1/auth/invite", json={"code": seed["code"]})).raise_for_status()
        up = await upload_all(api, seed, dog_files)
        truth_photo: dict[str, int] = up["truth_photo"]  # type: ignore[assignment]
        report["upload_p50_ms"] = float(np.median(up["upload_ms"]))  # type: ignore[arg-type]

        handlers = registry()
        assert "ingest_photo" in handlers, "models missing: run models/download.py"
        t0 = time.perf_counter()
        ingested = await drain(handlers)
        report["ingest_jobs"] = ingested
        report["ingest_seconds_total"] = round(time.perf_counter() - t0, 1)

        async with get_sessionmaker()() as db:
            photos = (await db.execute(select(Photo))).scalars().all()
            report["photos"] = {
                s: sum(p.status.value == s for p in photos) for s in ("processed", "failed", "quarantined")
            }
            report["quarantine_left"] = sum(p.quarantine_key is not None for p in photos)
            people = next(p for p in photos if str(p.id) == up["people_photo"])
            report["people_photo"] = {
                "persons_blurred": people.persons_blurred,
                "vehicles_blurred": people.vehicles_blurred,
                "status": people.status.value,
                "error": people.error,
            }
            dets = (
                await db.execute(
                    select(Detection, Photo.id, Photo.pass_id).join(Photo, Photo.id == Detection.photo_id)
                )
            ).all()
        det_truth = {str(d.id): truth_photo.get(str(pid)) for d, pid, _ in dets}
        p1_pass_id = seed["passes"][0][0]  # type: ignore[index]
        det_pass = {str(d.id): (1 if str(pas) == p1_pass_id else 2) for d, _, pas in dets}
        report["dog_detections"] = len(dets)
        report["usable_detections"] = sum(d.usable for d, _, _ in dets)
        report["dogs_photographed"] = {"pass1": len(up["pass1"]), "pass2": len(up["pass2"])}  # type: ignore[arg-type]

        (await api.post(f"/api/v1/surveys/{seed['survey_id']}/match")).raise_for_status()
        await drain(handlers)
        async with get_sessionmaker()() as db:
            pairs = (await db.execute(select(MatchPair))).scalars().all()
        y = np.array([int(det_truth[str(p.a_detection)] == det_truth[str(p.b_detection)]) for p in pairs])
        prior_p = np.array([p.p_same or 0.0 for p in pairs])
        report["candidate_pairs"] = len(pairs)
        report["true_pairs_in_candidates"] = int(y.sum())
        report["cosine_same_mean"] = float(
            np.mean([p.features["cosine"] for p, t in zip(pairs, y, strict=True) if t])
        )
        report["cosine_diff_mean"] = float(
            np.mean([p.features["cosine"] for p, t in zip(pairs, y, strict=True) if not t])
        )
        report["prior_auc"] = float(roc_auc_score(y, prior_p)) if 0 < y.sum() < len(y) else None
        report["cosine_auc"] = (
            float(roc_auc_score(y, [p.features["cosine"] for p in pairs])) if 0 < y.sum() < len(y) else None
        )

        labelled = 0
        while (
            item := (await api.get(f"/api/v1/surveys/{seed['survey_id']}/labeling/pairs")).json()
        ) is not None:
            same = det_truth[item["a"]["detection_id"]] == det_truth[item["b"]["detection_id"]]
            (
                await api.post(
                    "/api/v1/labels/pairs",
                    json={"pair_id": item["pair_id"], "decision": "same" if same else "different"},
                )
            ).raise_for_status()
            labelled += 1
        report["pairs_labelled"] = labelled

        (await api.post(f"/api/v1/surveys/{seed['survey_id']}/train")).raise_for_status()
        est = (await api.post(f"/api/v1/surveys/{seed['survey_id']}/estimates?replicates=2000")).json()
        t0 = time.perf_counter()
        await drain(handlers)
        report["train_and_estimate_seconds"] = round(time.perf_counter() - t0, 1)

        async with get_sessionmaker()() as db:
            mv = (
                (await db.execute(select(ModelVersion).where(ModelVersion.kind == "match"))).scalars().first()
            )
            row = (await db.execute(select(Estimate).where(Estimate.id == uuid.UUID(est["id"])))).scalar_one()
            n_ind = (await db.execute(text("select count(*) from individuals"))).scalar_one()
            report["individuals_rows"] = int(n_ind)
            report["detections_by_pass"] = dict(
                (
                    await db.execute(
                        select(PassRow.pass_no, func.count())
                        .join(Photo, Photo.pass_id == PassRow.id)
                        .join(Detection, Detection.photo_id == Photo.id)
                        .group_by(PassRow.pass_no)
                    )
                ).all()
            )
        report["match_model"] = (
            None
            if mv is None
            else {
                "version": mv.version,
                **{k: mv.metrics[k] for k in ("auc", "brier", "n_train", "n_test", "positives")},
            }
        )
        report["estimate"] = {
            "status": row.status,
            "method": row.method,
            "error": row.error,
            "results": {
                k: row.results.get(k)
                for k in ("counts", "population", "chapman", "share", "comparability_problems")
            }
            if row.results
            else None,
            "data_hash": row.data_hash,
            "seed": row.seed,
        }

        # Truth for the dogs the detector actually found (a dog missed by the detector cannot be counted).
        p1_true = {det_truth[k] for k in det_truth if det_truth[k] is not None and det_pass[k] == 1}
        p2_true = {det_truth[k] for k in det_truth if det_truth[k] is not None and det_pass[k] == 2}
        report["truth_for_detected_dogs"] = {
            "n1": len(p1_true),
            "n2": len(p2_true),
            "m2": len(p1_true & p2_true),
            "distinct": len(p1_true | p2_true),
        }
        report["truth_all_photographed"] = {
            "n1": len(up["pass1"]),
            "n2": len(up["pass2"]),  # type: ignore[arg-type]
            "m2": len(set(up["pass1"]) & set(up["pass2"])),  # type: ignore[arg-type]
            "distinct": len(set(up["pass1"]) | set(up["pass2"])),
        }  # type: ignore[arg-type]
        r = await api.get(f"/api/v1/surveys/{seed['survey_id']}/progress")
        report["progress"] = r.json()
    print(json.dumps(report, indent=1, default=str))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--api", default="http://127.0.0.1:8002")
    asyncio.run(main(ap.parse_args().api))
    sys.exit(0)
