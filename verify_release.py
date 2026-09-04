#!/usr/bin/env python3
"""Write or verify the curated GitHub release file manifest."""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parent
MANIFEST = ROOT / "release_manifest.json"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def release_files() -> list[Path]:
    return sorted(
        path
        for path in ROOT.rglob("*")
        if path.is_file()
        and path != MANIFEST
        and ".git" not in path.relative_to(ROOT).parts
        and "__pycache__" not in path.relative_to(ROOT).parts
    )


def records() -> dict[str, dict[str, object]]:
    return {
        path.relative_to(ROOT).as_posix(): {
            "bytes": path.stat().st_size,
            "sha256": sha256(path),
        }
        for path in release_files()
    }


def write_manifest() -> None:
    files = records()
    payload = {
        "schema_version": "temporal-pv-github-release/v1",
        "generated_utc": datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z"),
        "scope": "main figures, plotted data, checks, manifests, plotting code, paper-analysis code and agent workflow records",
        "explicit_exclusions": [
            "source imagery and third-party Building footprints",
            "upstream city-run directories",
            "complete high-level analytical table collection",
            "Arial font file pending redistribution permission",
            "credentials and chat transcripts",
        ],
        "file_count": len(files),
        "files": files,
    }
    MANIFEST.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(f"WROTE {MANIFEST} ({len(files)} files)")


def verify_manifest() -> int:
    if not MANIFEST.is_file():
        print("FAIL: release_manifest.json is missing; run with --write")
        return 1
    expected = json.loads(MANIFEST.read_text(encoding="utf-8"))["files"]
    observed = records()
    missing = sorted(set(expected) - set(observed))
    unexpected = sorted(set(observed) - set(expected))
    mismatched = sorted(
        name
        for name in set(expected) & set(observed)
        if expected[name] != observed[name]
    )
    result = {
        "status": "PASS" if not (missing or unexpected or mismatched) else "FAIL",
        "file_count": len(observed),
        "missing": missing,
        "unexpected": unexpected,
        "mismatched": mismatched,
    }
    print(json.dumps(result, indent=2))
    return 0 if result["status"] == "PASS" else 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--write", action="store_true", help="replace the manifest from current files"
    )
    args = parser.parse_args()
    if args.write:
        write_manifest()
        return 0
    return verify_manifest()


if __name__ == "__main__":
    raise SystemExit(main())
