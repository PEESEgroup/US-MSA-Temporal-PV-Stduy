#!/usr/bin/env python3
"""Build the full-AOI, one-row-per-host PV-area distribution table.

The table retains only unique linked hosts with a strict adjacent first PV
appearance that can be classified as either a newly observed building or an
existing building. All anchor PV union area on a host is attributed once to
that first strict appearance, matching the released area-weighted summaries.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

import numpy as np

from build_area_weighted_results import (
    build_host_areas,
    csv_row_count,
    distribution_metrics,
    input_record,
    load_area_totals,
    read_relationship_areas,
    sha256_file,
    utc_now,
    write_json,
)


SCRIPT_VERSION = "1.0.0"
OUTPUT_FIELDS = [
    "city_id",
    "scope",
    "route",
    "production_building_id",
    "pv_first_appearance_transition_index",
    "previous_cohort",
    "current_cohort",
    "source_pv_target_count",
    "host_pv_union_area_m2",
    "area_attribution_rule",
    "status",
]
SUMMARY_FIELDS = [
    "strict_event_host_count",
    "pv_union_area_m2",
    "nominal_capacity_mwdc_equivalent",
    "mean_host_pv_area_m2",
    "median_host_pv_area_m2",
    "p90_host_pv_area_m2",
    "p99_host_pv_area_m2",
    "top_1pct_host_count",
    "top_1pct_share_of_route_pv_area",
    "gini_host_pv_area",
]


def parse_args() -> argparse.Namespace:
    workspace = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--index", type=Path,
        default=workspace / "results" / "major_results_index.json",
    )
    parser.add_argument(
        "--artifact-index", type=Path,
        default=workspace / "results" / "artifact_results_index.csv",
    )
    parser.add_argument(
        "--risk-evidence-manifest", type=Path,
        default=workspace / "data_high_level" / "results_conclusion_evidence_manifest.json",
    )
    parser.add_argument(
        "--area-trajectory-table", type=Path,
        default=workspace / "data_high_level" / "city_pv_building_area_trajectories.csv",
    )
    parser.add_argument(
        "--area-interval-table", type=Path,
        default=workspace / "data_high_level" / "city_pv_building_area_interval_counts.csv",
    )
    parser.add_argument(
        "--area-trajectory-manifest", type=Path,
        default=workspace / "data_high_level" / "city_pv_building_area_manifest.json",
    )
    parser.add_argument(
        "--area-results-manifest", type=Path,
        default=workspace / "data_high_level" / "area_weighted_results_manifest.json",
    )
    parser.add_argument(
        "--target-distribution", type=Path,
        default=workspace / "data_high_level" / "city_area_weighted_event_size_distribution.csv",
    )
    parser.add_argument(
        "--target-stock-flow", type=Path,
        default=workspace / "data_high_level" / "city_area_weighted_stock_flow.csv",
    )
    parser.add_argument(
        "--output-dir", type=Path,
        default=workspace / "data_host_level",
    )
    return parser.parse_args()


def int_or_none(text: str) -> int | None:
    stripped = text.strip()
    return int(float(stripped)) if stripped else None


def load_risk_inputs(
    risk_manifest_path: Path,
    expected_cities: set[str],
    input_records: list[dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    risk_manifest = json.loads(risk_manifest_path.read_text(encoding="utf-8"))
    risk_inputs: dict[str, dict[str, Any]] = {}
    for record in risk_manifest["inputs"]:
        if record.get("input_role") != "completed_full_aoi_raw_known_risk_release":
            continue
        release_manifest_path = Path(record["path"])
        release_manifest = json.loads(release_manifest_path.read_text(encoding="utf-8"))
        if release_manifest.get("status") != "complete":
            raise ValueError(f"Risk release is not complete: {release_manifest_path}")
        input_manifest_path = release_manifest_path.parent / "inputs" / "input_manifest.json"
        release_inputs = json.loads(input_manifest_path.read_text(encoding="utf-8"))
        input_records.append(
            input_record(
                "completed_full_aoi_raw_known_release_manifest",
                release_manifest_path,
                expected_sha256=record["sha256"],
            )
        )
        expected_input = release_manifest["outputs"]["inputs/input_manifest.json"]
        input_records.append(
            input_record(
                "completed_full_aoi_raw_known_input_manifest",
                input_manifest_path,
                expected_sha256=expected_input["sha256"],
            )
        )
        for city_id, metadata in release_inputs["cities"].items():
            if city_id in risk_inputs:
                raise ValueError(f"City appears in two risk releases: {city_id}")
            risk_inputs[city_id] = metadata
    if set(risk_inputs) != expected_cities:
        raise ValueError("Risk releases do not cover the frozen 15 cities exactly")
    return risk_inputs


def classify_city_hosts(
    city_id: str,
    building_path: Path,
    expected_building_rows: int,
    cohorts: list[str],
    pairs: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    required_columns = {
        "production_building_id",
        "pau_first_appearance_type",
        "pau_first_appearance_lower_index",
        "pau_first_appearance_upper_index",
        *cohorts,
    }
    pair_map: dict[str, dict[str, Any]] = {}
    strict_pair_count = 0
    for pair in pairs:
        host_id = pair["production_building_id"]
        lower = int_or_none(pair["pv_pau_first_appearance_lower_index"])
        upper = int_or_none(pair["pv_pau_first_appearance_upper_index"])
        onset = int_or_none(pair["pv_pau_first_credible_present_index"])
        strict = (
            pair["pv_pau_first_appearance_type"] == "interval_censored"
            and lower is not None
            and upper is not None
            and upper - lower == 1
        )
        strict_pair_count += int(strict)
        pair_map[host_id] = {
            "pv_onset": onset,
            "event_transition": upper if strict else None,
            "area": float(pair["host_anchor_pv_union_area_m2"]),
            "source_pv_target_count": int(pair["source_pv_target_count"]),
        }

    output_rows: list[dict[str, Any]] = []
    route_values: dict[str, list[float]] = {"new": [], "existing": []}
    seen_buildings: set[str] = set()
    seen_paired_hosts: set[str] = set()
    classified_hosts: set[str] = set()
    unclassified_strict_host_count = 0
    building_row_count = 0
    with building_path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None or not required_columns.issubset(reader.fieldnames):
            raise ValueError(f"{city_id}: full-AOI building schema mismatch")
        for row in reader:
            building_row_count += 1
            host_id = row["production_building_id"]
            if not host_id or host_id in seen_buildings:
                raise ValueError(f"{city_id}: blank or duplicate building identity")
            seen_buildings.add(host_id)
            pair = pair_map.get(host_id)
            if pair is None:
                continue
            seen_paired_hosts.add(host_id)
            transition_index = pair["event_transition"]
            if transition_index is None:
                continue
            if not 1 <= transition_index < len(cohorts):
                raise ValueError(f"{city_id}/{host_id}: PV transition is outside cohort grid")
            pv_onset = pair["pv_onset"]
            if pv_onset is None or pv_onset < transition_index:
                raise ValueError(f"{city_id}/{host_id}: strict PV event is not eligible")

            building_lower = int_or_none(row["pau_first_appearance_lower_index"])
            building_upper = int_or_none(row["pau_first_appearance_upper_index"])
            building_strict = (
                row["pau_first_appearance_type"] == "interval_censored"
                and building_lower is not None
                and building_upper is not None
                and building_upper - building_lower == 1
            )
            previous = cohorts[transition_index - 1]
            current = cohorts[transition_index]
            new_group = building_strict and building_upper == transition_index
            existing_group = row[previous] == "present" and row[current] == "present"
            if new_group and existing_group:
                raise ValueError(f"{city_id}/{host_id}: host enters both displayed routes")
            if new_group:
                route = "new"
            elif existing_group:
                route = "existing"
            else:
                unclassified_strict_host_count += 1
                continue

            if host_id in classified_hosts:
                raise ValueError(f"{city_id}/{host_id}: classified more than once")
            classified_hosts.add(host_id)
            area = float(pair["area"])
            if not math.isfinite(area) or area <= 0:
                raise ValueError(f"{city_id}/{host_id}: non-positive host PV area")
            route_values[route].append(area)
            output_rows.append(
                {
                    "city_id": city_id,
                    "scope": "full_aoi",
                    "route": route,
                    "production_building_id": host_id,
                    "pv_first_appearance_transition_index": transition_index,
                    "previous_cohort": previous,
                    "current_cohort": current,
                    "source_pv_target_count": pair["source_pv_target_count"],
                    "host_pv_union_area_m2": area,
                    "area_attribution_rule": (
                        "all resolved anchor PV union area on the unique host is "
                        "attributed once to its first strict adjacent PV appearance"
                    ),
                    "status": "REPRODUCED",
                }
            )

    if building_row_count != expected_building_rows:
        raise ValueError(f"{city_id}: full-AOI building row count changed")
    if seen_paired_hosts != set(pair_map):
        missing = sorted(set(pair_map).difference(seen_paired_hosts))[:5]
        raise ValueError(f"{city_id}: paired hosts absent from full-AOI table: {missing}")
    return output_rows, {
        "city_id": city_id,
        "full_aoi_building_row_count": building_row_count,
        "paired_host_count": len(pair_map),
        "strict_pv_pair_count": strict_pair_count,
        "classified_host_count": len(output_rows),
        "unclassified_strict_host_count": unclassified_strict_host_count,
        "route_values": route_values,
    }


def numeric_close(
    observed: float,
    expected: float,
    *,
    abs_tol: float = 1e-8,
) -> bool:
    return math.isclose(observed, expected, rel_tol=1e-12, abs_tol=abs_tol)


def main() -> int:
    args = parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    for path in [
        args.index,
        args.artifact_index,
        args.risk_evidence_manifest,
        args.area_trajectory_table,
        args.area_interval_table,
        args.area_trajectory_manifest,
        args.area_results_manifest,
        args.target_distribution,
        args.target_stock_flow,
    ]:
        if not path.is_file():
            raise FileNotFoundError(path)

    index = json.loads(args.index.read_text(encoding="utf-8"))
    cities = sorted(index["cities"], key=lambda row: row["city_id"])
    if len(cities) != 15:
        raise ValueError("Expected 15 cities in the frozen result index")
    expected_cities = {city["city_id"] for city in cities}

    area_trajectory_manifest = json.loads(
        args.area_trajectory_manifest.read_text(encoding="utf-8")
    )
    if area_trajectory_manifest.get("status") != "REPRODUCED":
        raise ValueError("Area trajectory manifest is not REPRODUCED")
    area_results_manifest = json.loads(args.area_results_manifest.read_text(encoding="utf-8"))
    if area_results_manifest.get("status") != "REPRODUCED":
        raise ValueError("Area-weighted result manifest is not REPRODUCED")

    expected_area_tables = area_trajectory_manifest["tables"]
    input_records: list[dict[str, Any]] = [
        input_record("frozen_major_results_index", args.index),
        input_record("canonical_artifact_index", args.artifact_index),
        input_record("count_result_input_resolver", args.risk_evidence_manifest),
        input_record(
            "area_trajectory",
            args.area_trajectory_table,
            expected_sha256=expected_area_tables["city_pv_building_area_trajectories"][
                "sha256"
            ],
            expected_row_count=expected_area_tables["city_pv_building_area_trajectories"][
                "row_count"
            ],
            primary_key=["city_id", "calendar_year"],
        ),
        input_record(
            "area_interval_counts",
            args.area_interval_table,
            expected_sha256=expected_area_tables[
                "city_pv_building_area_interval_counts"
            ]["sha256"],
            expected_row_count=expected_area_tables[
                "city_pv_building_area_interval_counts"
            ]["row_count"],
            primary_key=[
                "city_id", "entity", "onset_type",
                "lower_cohort_order", "upper_cohort_order",
            ],
        ),
        input_record("area_trajectory_manifest", args.area_trajectory_manifest),
        input_record("area_weighted_results_manifest", args.area_results_manifest),
        input_record(
            "released_host_distribution_target",
            args.target_distribution,
            expected_sha256=area_results_manifest["outputs"][
                "city_area_weighted_event_size_distribution"
            ]["sha256"],
            expected_row_count=area_results_manifest["outputs"][
                "city_area_weighted_event_size_distribution"
            ]["row_count"],
            primary_key=["city_id", "scope", "route"],
        ),
        input_record(
            "released_city_stock_flow_target",
            args.target_stock_flow,
            expected_sha256=area_results_manifest["outputs"][
                "city_area_weighted_stock_flow"
            ]["sha256"],
            expected_row_count=area_results_manifest["outputs"][
                "city_area_weighted_stock_flow"
            ]["row_count"],
            primary_key=["city_id", "scope"],
        ),
    ]
    area_totals, _ = load_area_totals(args.area_trajectory_table, args.area_interval_table)
    risk_inputs = load_risk_inputs(
        args.risk_evidence_manifest, expected_cities, input_records
    )

    target_distribution_rows = [
        row for row in read_csv_rows(args.target_distribution)
        if row["scope"] == "full_aoi"
    ]
    target_distribution = {
        (row["city_id"], row["route"]): row for row in target_distribution_rows
    }
    target_stock_rows = [
        row for row in read_csv_rows(args.target_stock_flow)
        if row["scope"] == "full_aoi"
    ]
    target_stock = {row["city_id"]: row for row in target_stock_rows}

    output_path = args.output_dir / "city_host_pv_area_distribution.csv"
    temporary_path = output_path.with_suffix(".csv.tmp")
    checks_path = args.output_dir / "host_pv_area_distribution_checks.json"
    manifest_path = args.output_dir / "host_pv_area_distribution_manifest.json"
    total_output_rows = 0
    city_diagnostics: list[dict[str, Any]] = []
    all_route_values: dict[str, list[np.ndarray]] = defaultdict(list)
    cohort_order_by_city: dict[str, list[str]] = {}

    with temporary_path.open("w", encoding="utf-8", newline="") as output_stream:
        writer = csv.DictWriter(output_stream, fieldnames=OUTPUT_FIELDS)
        writer.writeheader()
        for position, city in enumerate(cities, start=1):
            city_id = city["city_id"]
            print(f"[{position:02d}/15] {city_id}: reconstructing strict host areas", flush=True)
            relation_artifact = city["artifacts"]["pv_building_relationship"]
            input_records.append(
                input_record(
                    "canonical_pv_building_relationship_with_anchor_pv_area",
                    Path(relation_artifact["path"]),
                    expected_sha256=relation_artifact["sha256"],
                    expected_row_count=int(relation_artifact["row_count"]),
                    primary_key=relation_artifact["primary_key"],
                )
            )
            target_areas, relationship_meta, _, _ = read_relationship_areas(
                city, area_totals[city_id]["anchor_pv_area_m2"]
            )
            risk_meta = risk_inputs[city_id]
            pair_info = risk_meta["unique_pv_building_pairs"]
            pair_artifact = city["artifacts"]["unique_pv_building_pairs"]
            pair_path = Path(pair_info["path"])
            if pair_path.resolve() != Path(pair_artifact["path"]).resolve():
                raise ValueError(f"{city_id}: risk and frozen pair paths differ")
            input_records.append(
                input_record(
                    "canonical_unique_pv_building_pairs",
                    pair_path,
                    expected_sha256=pair_artifact["sha256"],
                    expected_row_count=int(pair_artifact["row_count"]),
                    primary_key=pair_artifact["primary_key"],
                )
            )
            pairs, host_check = build_host_areas(
                city_id,
                pair_path,
                int(pair_artifact["row_count"]),
                target_areas,
                relationship_meta,
            )
            building_info = risk_meta["full_aoi_building"]
            building_path = Path(building_info["path"])
            input_records.append(
                input_record(
                    "full_aoi_raw_known_building_table",
                    building_path,
                    expected_sha256=building_info["sha256"],
                    expected_row_count=int(building_info["row_count"]),
                    primary_key="production_building_id",
                )
            )
            cohorts = list(risk_meta["cohort_order"])
            cohort_order_by_city[city_id] = cohorts
            host_rows, diagnostic = classify_city_hosts(
                city_id,
                building_path,
                int(building_info["row_count"]),
                cohorts,
                pairs,
            )
            for row in host_rows:
                writer.writerow(row)
            total_output_rows += len(host_rows)
            route_values = diagnostic.pop("route_values")
            route_checks: dict[str, Any] = {}
            for route in ["new", "existing"]:
                values = np.asarray(route_values[route], dtype=float)
                observed = distribution_metrics(city_id, "full_aoi", route, values)
                target = target_distribution[(city_id, route)]
                metric_differences: dict[str, float] = {}
                for field in SUMMARY_FIELDS:
                    if field in {"strict_event_host_count", "top_1pct_host_count"}:
                        if int(observed[field]) != int(float(target[field])):
                            raise ValueError(f"{city_id}/{route}: {field} does not reproduce")
                        metric_differences[field] = 0.0
                    else:
                        difference = float(observed[field]) - float(target[field])
                        tolerance = 1e-5 if field in {
                            "pv_union_area_m2", "nominal_capacity_mwdc_equivalent"
                        } else 1e-8
                        if not numeric_close(float(observed[field]), float(target[field]), abs_tol=tolerance):
                            raise ValueError(
                                f"{city_id}/{route}: {field} differs by {difference}"
                            )
                        metric_differences[field] = difference
                stock_field = "y_new" if route == "new" else "y_retrofit"
                stock_area_field = "pv_area_new_m2" if route == "new" else "pv_area_retrofit_m2"
                if len(values) != int(float(target_stock[city_id][stock_field])):
                    raise ValueError(f"{city_id}/{route}: host count differs from stock-flow table")
                if not numeric_close(
                    float(values.sum()),
                    float(target_stock[city_id][stock_area_field]),
                    abs_tol=1e-5,
                ):
                    raise ValueError(f"{city_id}/{route}: area differs from stock-flow table")
                all_route_values[route].append(values)
                route_checks[route] = {
                    "host_count": len(values),
                    "pv_union_area_m2": float(values.sum()),
                    "maximum_absolute_summary_difference": max(
                        abs(value) for value in metric_differences.values()
                    ),
                    "all_released_distribution_metrics_reproduced": True,
                    "stock_flow_count_and_area_reproduced": True,
                }
            diagnostic["resolved_host_count"] = host_check["unique_host_count"]
            diagnostic["routes"] = route_checks
            city_diagnostics.append(diagnostic)

    temporary_path.replace(output_path)

    pooled_checks: dict[str, Any] = {}
    for route in ["new", "existing"]:
        pooled_values = np.concatenate(all_route_values[route])
        observed = distribution_metrics(
            "all_cities_pooled", "full_aoi", route, pooled_values
        )
        target = target_distribution[("all_cities_pooled", route)]
        metric_differences: dict[str, float] = {}
        for field in SUMMARY_FIELDS:
            if field in {"strict_event_host_count", "top_1pct_host_count"}:
                if int(observed[field]) != int(float(target[field])):
                    raise ValueError(f"pooled/{route}: {field} does not reproduce")
                metric_differences[field] = 0.0
            else:
                difference = float(observed[field]) - float(target[field])
                tolerance = 1e-5 if field in {
                    "pv_union_area_m2", "nominal_capacity_mwdc_equivalent"
                } else 1e-8
                if not numeric_close(float(observed[field]), float(target[field]), abs_tol=tolerance):
                    raise ValueError(f"pooled/{route}: {field} differs by {difference}")
                metric_differences[field] = difference
        pooled_stock = target_stock["all_cities_pooled"]
        stock_field = "y_new" if route == "new" else "y_retrofit"
        stock_area_field = "pv_area_new_m2" if route == "new" else "pv_area_retrofit_m2"
        if len(pooled_values) != int(float(pooled_stock[stock_field])):
            raise ValueError(f"pooled/{route}: host count differs from stock-flow table")
        if not numeric_close(
            float(pooled_values.sum()),
            float(pooled_stock[stock_area_field]),
            abs_tol=1e-5,
        ):
            raise ValueError(f"pooled/{route}: area differs from stock-flow table")
        pooled_checks[route] = {
            "host_count": len(pooled_values),
            "pv_union_area_m2": float(pooled_values.sum()),
            "maximum_absolute_summary_difference": max(
                abs(value) for value in metric_differences.values()
            ),
            "all_released_distribution_metrics_reproduced": True,
            "stock_flow_count_and_area_reproduced": True,
        }

    if csv_row_count(output_path) != total_output_rows:
        raise ValueError("Written output row count does not match generated host count")
    if total_output_rows != sum(
        route["host_count"] for route in pooled_checks.values()
    ):
        raise ValueError("Pooled route counts do not sum to output row count")

    checks = {
        "schema_version": "host-pv-area-distribution-checks-v1",
        "generated_at_utc": utc_now(),
        "status": "REPRODUCED",
        "scope": "full_aoi",
        "city_count": len(cities),
        "output_row_count": total_output_rows,
        "primary_key": ["city_id", "production_building_id"],
        "primary_key_unique": True,
        "all_host_areas_positive_and_finite": True,
        "all_input_hashes_verified": all(
            record["sha256_expected"] == record["sha256_observed"]
            for record in input_records
        ),
        "all_input_row_counts_verified": all(
            record.get("row_count_expected") == record.get("row_count_observed")
            for record in input_records
            if "row_count_expected" in record
        ),
        "route_host_counts_match_released_stock_flow": True,
        "route_area_sums_match_released_stock_flow": True,
        "released_city_distribution_summaries_reproduced": True,
        "released_pooled_distribution_summaries_reproduced": True,
        "reproduced_summary_fields": SUMMARY_FIELDS,
        "pooled_routes": pooled_checks,
        "city_checks": city_diagnostics,
        "area_attribution_rule": (
            "all resolved anchor PV union area on a unique host is summed once "
            "and attributed to its first strict adjacent PV appearance"
        ),
        "time_interpretation": (
            "transition index follows the native ordered cohort grid and is not "
            "an exact installation date"
        ),
    }
    if not all(
        [
            checks["city_count"] == 15,
            checks["output_row_count"] > 0,
            checks["all_input_hashes_verified"],
            checks["all_input_row_counts_verified"],
            checks["released_city_distribution_summaries_reproduced"],
            checks["released_pooled_distribution_summaries_reproduced"],
        ]
    ):
        raise ValueError("One or more host-distribution checks failed")
    write_json(checks_path, checks)

    manifest = {
        "schema_version": "host-pv-area-distribution-manifest-v1",
        "generated_at_utc": utc_now(),
        "status": "REPRODUCED",
        "generator": {
            "path": str(Path(__file__).resolve()),
            "version": SCRIPT_VERSION,
            "sha256": sha256_file(Path(__file__).resolve()),
        },
        "command": "python3 scripts/build_host_pv_area_distribution.py",
        "scope": "full_aoi",
        "primary_key": ["city_id", "production_building_id"],
        "row_count": total_output_rows,
        "cohort_order_by_city": cohort_order_by_city,
        "filters_and_exclusions": [
            "full-AOI raw-known building table only",
            "first PV appearance must be interval-censored to adjacent native cohorts",
            "new route requires strict building first appearance at the same transition",
            "existing route requires the building to be present on both sides of the transition",
            "unknown states are not bridged",
            "strict PV hosts outside both displayed routes are excluded",
        ],
        "row_definition": (
            "one unique linked building host with a strict adjacent first PV "
            "appearance classified as newly observed or existing"
        ),
        "area_definition": (
            "sum of all resolved anchor PV target union areas linked to the host, "
            "attributed once at the host's first strict adjacent PV appearance"
        ),
        "inputs": input_records,
        "outputs": {
            "city_host_pv_area_distribution": {
                "path": str(output_path.resolve()),
                "sha256": sha256_file(output_path),
                "bytes": output_path.stat().st_size,
                "row_count": total_output_rows,
                "primary_key": ["city_id", "production_building_id"],
            },
            "host_pv_area_distribution_checks": {
                "path": str(checks_path.resolve()),
                "sha256": sha256_file(checks_path),
                "bytes": checks_path.stat().st_size,
                "record_count": 1,
                "primary_key": [],
            },
        },
    }
    write_json(manifest_path, manifest)
    print(json.dumps({
        "status": "REPRODUCED",
        "output": str(output_path.resolve()),
        "row_count": total_output_rows,
        "checks": str(checks_path.resolve()),
        "manifest": str(manifest_path.resolve()),
        "pooled_routes": pooled_checks,
    }, indent=2))
    return 0


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    csv.field_size_limit(sys.maxsize)
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


if __name__ == "__main__":
    raise SystemExit(main())
