#!/usr/bin/env python3
"""Compare upper-cohort and interval-stacked PAU building-stock estimates."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SCRIPT_VERSION = "1.0.1"


def parse_args() -> argparse.Namespace:
    workspace = Path(__file__).resolve().parents[1]
    data_dir = workspace / "data_high_level"
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--data-manifest",
        type=Path,
        default=data_dir / "city_pv_building_trajectories_manifest.json",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=data_dir / "city_building_stock_upper_vs_interval.csv",
    )
    return parser.parse_args()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        raise ValueError("Refusing to write an empty comparison table")
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def write_json(path: Path, payload: dict[str, Any]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, sort_keys=True)
        handle.write("\n")


def verified_table_path(
    manifest: dict[str, Any], table_name: str
) -> tuple[Path, dict[str, Any]]:
    record = manifest["tables"][table_name]
    path = Path(record["path"])
    if not path.is_file():
        raise FileNotFoundError(path)
    observed_hash = sha256_file(path)
    if observed_hash != record["sha256"]:
        raise ValueError(
            f"High-level input hash mismatch for {table_name}: "
            f"{observed_hash}!={record['sha256']}"
        )
    return path, record


def main() -> int:
    args = parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.data_manifest.open("r", encoding="utf-8") as handle:
        source_manifest = json.load(handle)
    if source_manifest.get("status") != "REPRODUCED":
        raise ValueError("Source high-level dataset is not REPRODUCED")

    stock_path, stock_record = verified_table_path(
        source_manifest, "city_building_stock_interval_stacked"
    )
    raw_path, raw_record = verified_table_path(
        source_manifest, "city_building_raw_state_counts"
    )
    interval_path, interval_record = verified_table_path(
        source_manifest, "city_building_pau_interval_counts"
    )

    stock_rows = read_csv(stock_path)
    raw_rows = read_csv(raw_path)
    interval_rows = read_csv(interval_path)
    if len(stock_rows) != stock_record["row_count"]:
        raise ValueError("Interval-stacked stock row count does not match manifest")
    if len(raw_rows) != raw_record["row_count"]:
        raise ValueError("Raw-state row count does not match manifest")
    if len(interval_rows) != interval_record["row_count"]:
        raise ValueError("PAU interval row count does not match manifest")

    upper_counts: dict[str, dict[int, int]] = defaultdict(dict)
    boundary_labels: dict[str, dict[int, str]] = defaultdict(dict)
    for row in raw_rows:
        city_id = row["city_id"]
        year = int(row["cohort_end_year"])
        if year in upper_counts[city_id]:
            raise ValueError(f"Duplicate cohort boundary for {city_id}/{year}")
        upper_counts[city_id][year] = int(row["accepted_onset_upper_count"])
        boundary_labels[city_id][year] = row["canonical_range_id"]

    interval_totals: dict[str, int] = defaultdict(int)
    for row in interval_rows:
        interval_totals[row["city_id"]] += int(row["building_count"])

    output_rows: list[dict[str, Any]] = []
    for source in sorted(
        stock_rows,
        key=lambda row: (int(row["city_order"]), int(row["calendar_year"])),
    ):
        city_id = source["city_id"]
        year = int(source["calendar_year"])
        city_boundaries = upper_counts[city_id]
        first_boundary = min(city_boundaries)
        is_boundary = year in city_boundaries
        interval_stock = float(source["interval_stacked_present_buildings"])
        anchor_stock = float(source["anchor_interval_stacked_buildings"])
        if year < first_boundary:
            upper_stock: int | str = ""
            difference: float | str = ""
            difference_anchor_share: float | str = ""
            difference_upper_share: float | str = ""
            upper_status = "unavailable_before_first_cohort_boundary"
        else:
            upper_stock = sum(
                count
                for boundary_year, count in city_boundaries.items()
                if boundary_year <= year
            )
            difference = interval_stock - upper_stock
            difference_anchor_share = difference / anchor_stock
            difference_upper_share = difference / upper_stock if upper_stock else math.nan
            upper_status = (
                "direct_cohort_boundary"
                if is_boundary
                else "step_held_between_cohort_boundaries"
            )
        output_rows.append(
            {
                "city_id": city_id,
                "city_name": source["city_name"],
                "city_order": source["city_order"],
                "calendar_year": year,
                "is_cohort_boundary": is_boundary,
                "canonical_range_at_boundary": boundary_labels[city_id].get(
                    year, ""
                ),
                "upper_value_status": upper_status,
                "upper_cohort_cumulative_buildings": upper_stock,
                "interval_stacked_present_buildings": interval_stock,
                "interval_minus_upper_buildings": difference,
                "difference_share_of_anchor": difference_anchor_share,
                "difference_share_of_upper": difference_upper_share,
                "anchor_buildings": anchor_stock,
                "upper_definition": (
                    "all accepted PAU onset mass assigned to its upper cohort boundary"
                ),
                "interval_definition": (
                    "left-censored baseline plus uniform mass over each PAU interval"
                ),
                "status": "REPRODUCED",
            }
        )

    write_csv(args.output, output_rows)
    comparable = [
        row
        for row in output_rows
        if row["upper_value_status"]
        != "unavailable_before_first_cohort_boundary"
    ]
    boundary_rows = [row for row in comparable if row["is_cohort_boundary"]]
    city_ids = sorted({row["city_id"] for row in output_rows})
    anchor_rows = [
        max(
            (row for row in output_rows if row["city_id"] == city_id),
            key=lambda row: row["calendar_year"],
        )
        for city_id in city_ids
    ]
    checks = {
        "dataset": "city_building_stock_upper_vs_interval",
        "status": "REPRODUCED",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "city_count": len(city_ids),
        "row_count": len(output_rows),
        "cohort_boundary_row_count": len(boundary_rows),
        "source_stock_rows_reconciled": len(output_rows) == len(stock_rows),
        "upper_counts_reconcile_to_interval_table": all(
            sum(upper_counts[city_id].values()) == interval_totals[city_id]
            for city_id in city_ids
        ),
        "interval_not_below_upper_after_first_boundary": all(
            float(row["interval_minus_upper_buildings"]) >= -1e-8
            for row in comparable
        ),
        "anchor_estimators_reconcile": all(
            math.isclose(
                float(row["upper_cohort_cumulative_buildings"]),
                float(row["interval_stacked_present_buildings"]),
                rel_tol=0,
                abs_tol=1e-8,
            )
            for row in anchor_rows
        ),
        "maximum_boundary_gap": max(
            boundary_rows,
            key=lambda row: float(row["interval_minus_upper_buildings"]),
        ),
        "maximum_post_baseline_annual_gap": max(
            comparable,
            key=lambda row: float(row["interval_minus_upper_buildings"]),
        ),
    }
    if not all(
        [
            checks["city_count"] == 15,
            checks["source_stock_rows_reconciled"],
            checks["upper_counts_reconcile_to_interval_table"],
            checks["interval_not_below_upper_after_first_boundary"],
            checks["anchor_estimators_reconcile"],
        ]
    ):
        raise ValueError("One or more upper-versus-interval checks failed")

    checks_path = args.output.with_name(
        "city_building_stock_upper_vs_interval_checks.json"
    )
    manifest_path = args.output.with_name(
        "city_building_stock_upper_vs_interval_manifest.json"
    )
    write_json(checks_path, checks)
    write_json(
        manifest_path,
        {
            "schema_version": "high-level-analysis-data-manifest-v1",
            "dataset": "city_building_stock_upper_vs_interval",
            "status": "REPRODUCED",
            "generated_at_utc": datetime.now(timezone.utc).isoformat(),
            "script_path": str(Path(__file__).resolve()),
            "script_version": SCRIPT_VERSION,
            "script_sha256": sha256_file(Path(__file__).resolve()),
            "command": "python3 scripts/compare_city_building_stock_estimators.py",
            "source_manifest_path": str(args.data_manifest.resolve()),
            "source_manifest_sha256": sha256_file(args.data_manifest),
            "filters": (
                "upper comparison unavailable before each city's first cohort "
                "end year; no other rows excluded"
            ),
            "primary_key": ["city_id", "calendar_year"],
            "upper_definition": (
                "cumulative accepted PAU onset count assigned entirely at each "
                "upper cohort boundary; step-held only for between-boundary comparison"
            ),
            "interval_definition": (
                "left-censored targets enter baseline; interval-censored mass "
                "is uniform over integer years in (lower end year, upper end year]"
            ),
            "output": {
                "path": str(args.output.resolve()),
                "sha256": sha256_file(args.output),
                "bytes": args.output.stat().st_size,
                "row_count": len(output_rows),
            },
            "checks": {
                "path": str(checks_path.resolve()),
                "sha256": sha256_file(checks_path),
                "bytes": checks_path.stat().st_size,
            },
        },
    )
    print(f"Wrote {args.output}")
    print(f"Wrote {checks_path}")
    print(f"Wrote {manifest_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
