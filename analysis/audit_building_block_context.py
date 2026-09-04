#!/usr/bin/env python3
"""Audit historical SAM3 Building 2x2 context and onset observability.

This is a read-only audit over canonical artifacts listed by
``results/artifact_results_index.csv``. It does not modify production runs.
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from statistics import mean
from typing import Any


WORK_ROOT = Path("/home/ec2-user/rpv-work")
RUNS_ROOT = WORK_ROOT / "runs"


def read_json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as stream:
        return json.load(stream)


def run_root(path: Path) -> Path:
    parts = path.parts
    index = parts.index("runs")
    return Path(*parts[: index + 2])


def nearest_stage8_files(building_path: Path, root: Path) -> tuple[Path, Path]:
    summary = None
    manifest = None
    cursor = building_path.parent
    while str(cursor).startswith(str(root)):
        summary_path = cursor / "summary.json"
        if summary_path.is_file():
            payload = read_json(summary_path)
            if payload.get("entity_type") == "building":
                summary = summary_path
        manifest_path = cursor / "manifest.json"
        if manifest_path.is_file():
            payload = read_json(manifest_path)
            if payload.get("entity_type") == "building":
                manifest = manifest_path
        if summary is not None and manifest is not None:
            return summary, manifest
        if cursor == root:
            break
        cursor = cursor.parent
    raise FileNotFoundError(f"Could not resolve Stage 8 files for {building_path}")


def stage7b_summary(stage8_manifest: Path) -> Path:
    payload = read_json(stage8_manifest)
    candidates: list[Path] = []
    for value in (payload.get("inputs") or {}):
        path = Path(value)
        if path.name == "summary.json":
            candidates.append(path)
        if "building_vintage_timeline" in path.name:
            candidates.append(path.parent / "summary.json")
    for path in candidates:
        if path.is_file() and read_json(path).get("production_building_count") is not None:
            return path
    raise FileNotFoundError(f"Could not resolve Stage 7B summary from {stage8_manifest}")


def scope_manifest(city_id: str, root: Path) -> Path | None:
    search_roots = [root]
    if city_id == "boston":
        search_roots.extend(sorted(RUNS_ROOT.glob("boston-*")))
    matches: list[Path] = []
    visited: set[Path] = set()
    for search_root in search_roots:
        if search_root in visited or not search_root.is_dir():
            continue
        visited.add(search_root)
        for path in search_root.rglob("manifest.json"):
            try:
                schema = str(read_json(path).get("schema_version", ""))
            except (OSError, json.JSONDecodeError):
                continue
            if schema.startswith("anchor-building-level-pv-tile-scope"):
                matches.append(path)
    return matches[-1] if matches else None


def historical_building_manifests(
    root: Path,
    real_block_count: int,
    historical_vintages: set[str],
) -> list[Path]:
    matches: list[Path] = []
    for path in root.rglob("manifest.json"):
        try:
            payload = read_json(path)
        except (OSError, json.JSONDecodeError):
            continue
        if payload.get("schema_version") != "sam3-building-inference/v2":
            continue
        if payload.get("scan_scope") != "historical_narrow_accepted_pv_blocks":
            continue
        if int(payload.get("blocks", -1)) != real_block_count:
            continue
        if historical_vintages and str(payload.get("vintage_id")) not in historical_vintages:
            continue
        matches.append(path)
    return sorted(matches)


def fraction(numerator: int | float, denominator: int | float) -> float | None:
    return float(numerator) / float(denominator) if denominator else None


def summarize_city(row: dict[str, str]) -> dict[str, Any]:
    city_id = row["city_id"]
    building_path = Path(row["path"])
    root = run_root(building_path)
    stage8_path, stage8_manifest_path = nearest_stage8_files(building_path, root)
    stage7b_path = stage7b_summary(stage8_manifest_path)
    stage8 = read_json(stage8_path)
    stage7b = read_json(stage7b_path)
    scope_path = scope_manifest(city_id, root)
    scope = read_json(scope_path) if scope_path else {}

    real_blocks = int(stage7b["real_block_count"])
    per_vintage = stage7b.get("per_vintage") or []
    available_fractions = [
        fraction(int(item.get("available_block_count", 0)), real_blocks)
        for item in per_vintage
    ]
    available_fractions = [value for value in available_fractions if value is not None]
    offset_fractions = []
    for item in per_vintage:
        counts = item.get("offset_status_counts") or {}
        denominator = sum(int(value) for value in counts.values())
        accepted = int(counts.get("pass", 0)) + int(counts.get("zero_offset", 0))
        value = fraction(accepted, denominator)
        if value is not None:
            offset_fractions.append(value)

    historical_vintages = {str(value) for value in stage7b.get("historical_vintages", [])}
    inference_manifests = historical_building_manifests(
        root, real_blocks, historical_vintages
    )
    inference_slot_fractions = []
    for path in inference_manifests:
        payload = read_json(path)
        value = fraction(int(payload.get("planned_tiles", 0)), 4 * real_blocks)
        if value is not None:
            inference_slot_fractions.append(value)

    target_count = int(stage8["target_count"])
    unknown_count = int(stage8.get("target_with_unknown_count", 0))
    type_counts = stage8.get("first_appearance_type_counts") or {}
    interval_count = int(type_counts.get("interval_censored", 0))
    left_count = int(type_counts.get("left_censored", 0))
    reduced_one_count = int(
        (stage8.get("reduced_sequence_length_counts") or {}).get("1", 0)
    )
    scope_tiles = scope.get("tile_count")
    scope_blocks = scope.get("sam3_blocks_per_vintage")
    scope_slot_fraction = (
        fraction(int(scope_tiles), 4 * int(scope_blocks))
        if scope_tiles is not None and scope_blocks is not None
        else None
    )

    minimum_context = min(available_fractions) if available_fractions else None
    minimum_plan = min(inference_slot_fractions) if inference_slot_fractions else None
    if minimum_plan is not None and minimum_plan < 0.95 and minimum_context is not None and minimum_context < 0.5:
        assessment = "confirmed_partial_historical_building_plan"
        priority = "P0"
        similar = True
    elif minimum_plan is not None and minimum_plan >= 0.99 and minimum_context is not None and minimum_context < 0.95:
        assessment = "full_plan_with_context_gaps"
        priority = "P1"
        similar = False
    elif minimum_context is not None and minimum_context >= 0.95:
        assessment = "complete_context_or_minor_boundary_gaps"
        priority = "P2"
        similar = False
    else:
        assessment = "manual_review_required"
        priority = "P1"
        similar = False

    return {
        "city_id": city_id,
        "building_target_count": target_count,
        "historical_cohort_count": len(per_vintage),
        "real_block_count": real_blocks,
        "narrow_scope_tile_count": scope_tiles,
        "narrow_scope_block_count": scope_blocks,
        "narrow_scope_source_tile_slot_fraction": scope_slot_fraction,
        "historical_building_manifest_count": len(inference_manifests),
        "historical_building_min_planned_slot_fraction": minimum_plan,
        "minimum_complete_context_block_fraction": minimum_context,
        "maximum_complete_context_block_fraction": (
            max(available_fractions) if available_fractions else None
        ),
        "mean_complete_context_block_fraction": (
            mean(available_fractions) if available_fractions else None
        ),
        "minimum_accepted_offset_fraction": (
            min(offset_fractions) if offset_fractions else None
        ),
        "maximum_accepted_offset_fraction": (
            max(offset_fractions) if offset_fractions else None
        ),
        "building_with_unknown_count": unknown_count,
        "building_with_unknown_fraction": fraction(unknown_count, target_count),
        "reduced_sequence_length_one_count": reduced_one_count,
        "reduced_sequence_length_one_fraction": fraction(reduced_one_count, target_count),
        "interval_censored_building_count": interval_count,
        "interval_censored_building_fraction": fraction(interval_count, target_count),
        "left_censored_building_count": left_count,
        "similar_to_miami_minneapolis_failure": similar,
        "assessment": assessment,
        "repair_priority": priority,
        "canonical_building_first_appearance": str(building_path),
        "stage8_summary": str(stage8_path),
        "stage7b_summary": str(stage7b_path),
        "narrow_scope_manifest": str(scope_path) if scope_path else None,
        "historical_building_manifests": [str(path) for path in inference_manifests],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--artifact-index",
        type=Path,
        default=Path("results/artifact_results_index.csv"),
    )
    parser.add_argument("--output-csv", type=Path, required=True)
    parser.add_argument("--output-json", type=Path, required=True)
    args = parser.parse_args()

    with args.artifact_index.open(newline="", encoding="utf-8") as stream:
        rows = [
            row
            for row in csv.DictReader(stream)
            if row["name"] == "building_first_appearance"
        ]
    results = [summarize_city(row) for row in rows]
    if len(results) != 15:
        raise ValueError(f"Expected 15 cities, found {len(results)}")

    args.output_csv.parent.mkdir(parents=True, exist_ok=True)
    scalar_fields = [
        key
        for key, value in results[0].items()
        if not isinstance(value, list)
    ]
    with args.output_csv.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=scalar_fields)
        writer.writeheader()
        writer.writerows(
            {key: value for key, value in row.items() if key in scalar_fields}
            for row in results
        )
    payload = {
        "schema_version": "building-narrow-block-context-audit/v1",
        "status": "complete",
        "city_count": len(results),
        "similar_failure_city_ids": [
            row["city_id"]
            for row in results
            if row["similar_to_miami_minneapolis_failure"]
        ],
        "results": results,
    }
    args.output_json.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


if __name__ == "__main__":
    main()
