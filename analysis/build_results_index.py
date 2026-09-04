#!/usr/bin/env python3
"""Build a compact, verified index of city-level final RPV results."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml


WORK_ROOT = Path("/home/ec2-user/rpv-work")
CORE_ARTIFACTS = (
    "building_first_appearance",
    "pv_first_appearance",
    "pv_building_relationship",
    "unique_pv_building_pairs",
    "unavailable_pv_targets",
)
PRIMARY_KEYS = {
    "building_first_appearance": "production_building_id",
    "pv_first_appearance": "temporal_pv_target_id",
    "pv_building_relationship": "temporal_pv_target_id",
    "unique_pv_building_pairs": "production_building_id",
    "unavailable_pv_targets": "temporal_pv_target_id",
}
DISPLAY_NAMES = {
    "atlanta": "Atlanta",
    "boston": "Boston",
    "charlotte": "Charlotte",
    "chicago": "Chicago",
    "dallas": "Dallas",
    "denver": "Denver",
    "detroit": "Detroit",
    "los_angeles": "Los Angeles",
    "miami": "Miami",
    "minneapolis": "Minneapolis",
    "new_york_city": "New York City",
    "philadelphia": "Philadelphia",
    "phoenix": "Phoenix",
    "seattle": "Seattle",
    "washington_dc": "Washington DC",
}
ACCEPTED_COMPLETE = {"pass", "complete", "completed", "production_complete"}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(16 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def csv_rows(path: Path) -> int:
    csv.field_size_limit(sys.maxsize)
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.reader(handle)
        next(reader, None)
        return sum(1 for _ in reader)


def resolve(run_root: Path, value: str | Path) -> Path:
    path = Path(value)
    if path.is_absolute():
        return path
    if str(path).startswith("runs/"):
        return WORK_ROOT / path
    return run_root / path


def path_value(value: Any) -> str | None:
    if isinstance(value, dict):
        value = value.get("path")
    return str(value) if value else None


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def find_qa_path(profile: dict[str, Any], run_root: Path, manifest: dict[str, Any]) -> Path | None:
    candidates: list[str] = []
    release = profile.get("release_evidence") or {}
    if path_value(release.get("final_qa")):
        candidates.append(path_value(release["final_qa"]))
    for section_name in ("canonical_outputs", "canonical_artifacts", "artifacts"):
        section = profile.get(section_name) or {}
        if path_value(section.get("final_qa")):
            candidates.append(path_value(section["final_qa"]))
        if path_value(section.get("final_pairing_qa")):
            candidates.append(path_value(section["final_pairing_qa"]))
    if path_value(manifest.get("final_qa")):
        candidates.append(path_value(manifest["final_qa"]))
    if path_value(manifest.get("stage9_gate")):
        candidates.append(path_value(manifest["stage9_gate"]))
    gates = profile.get("gates") or {}
    for key in ("stage9_qa", "stage9"):
        if path_value(gates.get(key)):
            candidates.append(path_value(gates[key]))
    candidates.extend(
        [
            "final_qa.json",
            "final_qa_retry1.json",
            "final/stage9_qa.json",
            "qa/stage9_gate.json",
            "qa/stage9_gate_retry1.json",
        ]
    )
    for candidate in candidates:
        path = resolve(run_root, candidate)
        if path.is_file():
            return path
    return None


def find_summary_path(profile: dict[str, Any], run_root: Path, relationship: Path) -> Path | None:
    release = profile.get("release_evidence") or {}
    candidate = path_value(release.get("summary"))
    if candidate:
        path = resolve(run_root, candidate)
        if path.is_file():
            return path
    path = relationship.parent / "summary.json"
    return path if path.is_file() else None


def expected_from_final_qa(final_qa: dict[str, Any], name: str) -> dict[str, Any]:
    for key in ("artifacts", "canonical_artifacts"):
        value = (final_qa.get(key) or {}).get(name)
        if isinstance(value, dict):
            return value
    return {}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--profile", type=Path, action="append", required=True)
    args = parser.parse_args()

    output_root = args.output_root.resolve()
    if output_root.exists() and any(output_root.iterdir()):
        raise FileExistsError(f"Refusing to overwrite non-empty output root: {output_root}")
    output_root.mkdir(parents=True, exist_ok=True)

    generated_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    cities: list[dict[str, Any]] = []
    artifact_rows: list[dict[str, Any]] = []

    for profile_path in sorted(path.resolve() for path in args.profile):
        profile = yaml.safe_load(profile_path.read_text(encoding="utf-8"))
        run_root = profile_path.parent
        manifest_path = run_root / "manifest.json"
        if not manifest_path.is_file():
            raise FileNotFoundError(manifest_path)
        manifest = read_json(manifest_path)
        city_id = str(profile["city_id"])
        section = (
            profile.get("canonical_outputs")
            or profile.get("canonical_artifacts")
            or profile.get("artifacts")
            or {}
        )
        qa_path = find_qa_path(profile, run_root, manifest)
        final_qa = read_json(qa_path) if qa_path else {}
        qa_status = final_qa.get("status") if final_qa else None
        top_hashes = profile.get("hashes") or {}
        artifacts: dict[str, dict[str, Any]] = {}

        for name in CORE_ARTIFACTS:
            raw = section.get(name)
            if raw is None:
                raise KeyError(f"{profile_path}: missing canonical artifact {name}")
            meta = raw if isinstance(raw, dict) else {}
            raw_path = path_value(raw)
            if not raw_path:
                raise ValueError(f"{profile_path}: empty path for {name}")
            path = resolve(run_root, raw_path)
            if not path.is_file() or path.stat().st_size == 0:
                raise FileNotFoundError(f"Missing or empty canonical artifact: {path}")

            qa_meta = expected_from_final_qa(final_qa, name)
            expected_hash = meta.get("sha256") or top_hashes.get(name) or qa_meta.get("sha256")
            expected_rows = meta.get("row_count")
            if expected_rows is None:
                expected_rows = qa_meta.get("rows", qa_meta.get("row_count"))
            actual_hash = sha256(path)
            actual_rows = csv_rows(path)
            hash_match = expected_hash is None or actual_hash == expected_hash
            row_count_match = expected_rows is None or actual_rows == int(expected_rows)
            if not hash_match:
                raise ValueError(f"Hash mismatch for {path}")
            if not row_count_match:
                raise ValueError(f"Row-count mismatch for {path}")
            record = {
                "name": name,
                "path": str(path),
                "sha256": actual_hash,
                "bytes": path.stat().st_size,
                "row_count": actual_rows,
                "primary_key": meta.get("primary_key") or qa_meta.get("primary_key") or PRIMARY_KEYS[name],
                "exists_nonempty": True,
                "declared_hash_present": expected_hash is not None,
                "hash_match": hash_match,
                "declared_row_count_present": expected_rows is not None,
                "row_count_match": row_count_match,
            }
            artifacts[name] = record
            artifact_rows.append({"city_id": city_id, **record})

        relationship_path = Path(artifacts["pv_building_relationship"]["path"])
        summary_path = find_summary_path(profile, run_root, relationship_path)
        advisories = []
        for key in ("advisories", "provenance_advisories"):
            advisories.extend(profile.get(key) or [])
            advisories.extend(manifest.get(key) or [])
        advisories = list(dict.fromkeys(str(item) for item in advisories))
        profile_status = profile.get("status")
        manifest_status = manifest.get("status")
        release_status = "complete" if (
            profile_status in ACCEPTED_COMPLETE
            and manifest_status in ACCEPTED_COMPLETE
            and qa_status == "pass"
            and all(item["hash_match"] and item["row_count_match"] for item in artifacts.values())
        ) else "incomplete"
        if release_status != "complete":
            raise ValueError(
                f"Release evidence incomplete for {city_id}: "
                f"profile={profile_status} manifest={manifest_status} qa={qa_status}"
            )

        relationship_count = artifacts["pv_building_relationship"]["row_count"]
        unavailable_count = artifacts["unavailable_pv_targets"]["row_count"]
        city = {
            "city_id": city_id,
            "city_name": DISPLAY_NAMES.get(city_id, city_id),
            "release_status": release_status,
            "profile_status": profile_status,
            "manifest_status": manifest_status,
            "qa_status": qa_status,
            "advisory_count": len(advisories),
            "advisories": advisories,
            "counts": {
                "building_target_count": artifacts["building_first_appearance"]["row_count"],
                "pv_target_count": artifacts["pv_first_appearance"]["row_count"],
                "relationship_count": relationship_count,
                "resolved_relationship_count": relationship_count - unavailable_count,
                "unavailable_relationship_count": unavailable_count,
                "unique_paired_building_count": artifacts["unique_pv_building_pairs"]["row_count"],
            },
            "release_profile": {"path": str(profile_path), "sha256": sha256(profile_path)},
            "release_manifest": {"path": str(manifest_path), "sha256": sha256(manifest_path)},
            "release_qa": {"path": str(qa_path), "sha256": sha256(qa_path)},
            "summary": (
                {"path": str(summary_path), "sha256": sha256(summary_path)} if summary_path else None
            ),
            "artifacts": artifacts,
        }
        cities.append(city)

    if set(city["city_id"] for city in cities) != set(DISPLAY_NAMES):
        missing = sorted(set(DISPLAY_NAMES) - set(city["city_id"] for city in cities))
        extra = sorted(set(city["city_id"] for city in cities) - set(DISPLAY_NAMES))
        raise ValueError(f"Expected exactly 15 cities; missing={missing}, extra={extra}")

    totals = {
        key: sum(city["counts"][key] for city in cities)
        for key in next(iter(cities))["counts"]
    }
    index = {
        "schema_version": "rpv-major-results-index/v1",
        "status": "complete",
        "generated_at_utc": generated_at,
        "work_root": str(WORK_ROOT),
        "city_count": len(cities),
        "artifact_count": len(artifact_rows),
        "all_release_evidence_complete": True,
        "totals": totals,
        "cities": cities,
    }
    json_path = output_root / "major_results_index.json"
    json_path.write_text(json.dumps(index, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")

    city_columns = [
        "city_id", "city_name", "release_status", "profile_status", "manifest_status", "qa_status",
        "advisory_count", "building_target_count", "pv_target_count", "relationship_count",
        "resolved_relationship_count", "unavailable_relationship_count", "unique_paired_building_count",
        "release_profile_path", "release_manifest_path", "release_qa_path", "summary_path",
    ]
    city_csv = output_root / "city_results_index.csv"
    with city_csv.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=city_columns)
        writer.writeheader()
        for city in cities:
            writer.writerow({
                "city_id": city["city_id"],
                "city_name": city["city_name"],
                "release_status": city["release_status"],
                "profile_status": city["profile_status"],
                "manifest_status": city["manifest_status"],
                "qa_status": city["qa_status"],
                "advisory_count": city["advisory_count"],
                **city["counts"],
                "release_profile_path": city["release_profile"]["path"],
                "release_manifest_path": city["release_manifest"]["path"],
                "release_qa_path": city["release_qa"]["path"],
                "summary_path": city["summary"]["path"] if city["summary"] else "",
            })

    artifact_columns = [
        "city_id", "name", "path", "sha256", "bytes", "row_count", "primary_key",
        "exists_nonempty", "declared_hash_present", "hash_match", "declared_row_count_present",
        "row_count_match",
    ]
    artifact_csv = output_root / "artifact_results_index.csv"
    with artifact_csv.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=artifact_columns)
        writer.writeheader()
        writer.writerows(sorted(artifact_rows, key=lambda item: (item["city_id"], item["name"])))

    readme = output_root / "README.md"
    readme.write_text(
        "# Major results index\n\n"
        f"Generated: `{generated_at}`\n\n"
        "This directory is a compact index of the 15 city final releases. It contains no copied "
        "scientific CSVs and no symlinks; every artifact entry points to its immutable owning run.\n\n"
        "- `city_results_index.csv`: one row per city with release entrypoints, QA status, and counts.\n"
        "- `artifact_results_index.csv`: one row per canonical artifact with path, SHA-256, rows, and primary key.\n"
        "- `major_results_index.json`: complete machine-readable city and artifact index.\n"
        "- `manifest.json`: hashes for this index bundle and all release profile/manifest inputs.\n\n"
        f"Totals: {totals['building_target_count']:,} Building targets; "
        f"{totals['pv_target_count']:,} PV targets; "
        f"{totals['unique_paired_building_count']:,} unique PV-Building pairs.\n",
        encoding="utf-8",
    )

    outputs = {
        path.name: {"sha256": sha256(path), "bytes": path.stat().st_size}
        for path in (json_path, city_csv, artifact_csv, readme)
    }
    manifest_inputs = {
        city["city_id"]: {
            "release_profile": city["release_profile"],
            "release_manifest": city["release_manifest"],
            "release_qa": city["release_qa"],
        }
        for city in cities
    }
    manifest_out = {
        "schema_version": "rpv-major-results-index-manifest/v1",
        "status": "complete",
        "generated_at_utc": generated_at,
        "city_count": len(cities),
        "artifact_count": len(artifact_rows),
        "all_release_evidence_complete": True,
        "inputs": manifest_inputs,
        "outputs": outputs,
        "totals": totals,
    }
    (output_root / "manifest.json").write_text(
        json.dumps(manifest_out, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({
        "status": "complete",
        "output_root": str(output_root),
        "city_count": len(cities),
        "artifact_count": len(artifact_rows),
        "totals": totals,
    }, indent=2))


if __name__ == "__main__":
    main()
