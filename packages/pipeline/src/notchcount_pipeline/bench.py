"""Measure ingest latency and memory on a folder of JPEGs (P0 spike, P2 gate numbers).

uv run python -m notchcount_pipeline.bench models/cache data/samples
"""

from __future__ import annotations

import json
import resource
import statistics
import sys
import time
from pathlib import Path

from notchcount_pipeline.ingest import Models, process


def rss_mb() -> float:
    peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return peak / (1024 * 1024) if sys.platform == "darwin" else peak / 1024


def main(
    model_dir: Path, photos: Path, threads: int = 2, embedder: str = "dinov2_vits14_int8"
) -> dict[str, object]:
    t0 = time.perf_counter()
    models = Models.load(model_dir, embedder, threads=threads)
    load_ms = (time.perf_counter() - t0) * 1000
    rows: list[dict[str, object]] = []
    times: list[int] = []
    for path in sorted(photos.glob("*.jpg")):
        res = process(path.read_bytes(), models)
        times.append(round(res.timings_ms["total"]))
        rows.append(
            {
                "file": path.name,
                "ms": round(res.timings_ms["total"]),
                "dogs": len(res.dogs),
                "usable": sum(d.usable for d in res.dogs),
                "persons_blurred": res.persons_blurred,
                "vehicles_blurred": res.vehicles_blurred,
                "quality": [round(d.quality, 2) for d in res.dogs],
            }
        )
    times.sort()
    summary = {
        "models": models.version,
        "threads": threads,
        "load_ms": round(load_ms),
        "photos": len(rows),
        "p50_ms": statistics.median(times),
        "p95_ms": times[min(len(times) - 1, round(0.95 * (len(times) - 1)))],
        "peak_rss_mb": round(rss_mb()),
        "rows": rows,
    }
    return summary


if __name__ == "__main__":
    out = main(Path(sys.argv[1]), Path(sys.argv[2]), int(sys.argv[3]) if len(sys.argv) > 3 else 2)
    print(json.dumps(out, indent=1))
