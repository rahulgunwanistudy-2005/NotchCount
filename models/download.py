"""Download the worker's ONNX models and verify their SHA-256 (stdlib only).

    python models/download.py models/cache detector.onnx dinov2_vits14_int8.onnx
"""

import hashlib
import json
import sys
import urllib.request
from pathlib import Path

HERE = Path(__file__).parent


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main(target: Path, names: list[str]) -> None:
    spec = json.loads((HERE / "checksums.json").read_text())
    target.mkdir(parents=True, exist_ok=True)
    for name in names or list(spec["files"]):
        want = spec["files"][name]
        dest = target / name
        if dest.exists() and sha256(dest) == want:
            print(f"{name}: present")
            continue
        tmp = dest.with_suffix(".part")
        urllib.request.urlretrieve(f"{spec['release']}/{name}", tmp)  # noqa: S310 (fixed https URL)
        got = sha256(tmp)
        if got != want:
            tmp.unlink()
            raise SystemExit(f"{name}: checksum mismatch ({got} != {want})")
        tmp.rename(dest)
        print(f"{name}: downloaded")


if __name__ == "__main__":
    main(Path(sys.argv[1] if len(sys.argv) > 1 else HERE / "cache"), sys.argv[2:])
