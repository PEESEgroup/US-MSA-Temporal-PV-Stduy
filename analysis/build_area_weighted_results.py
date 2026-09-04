#!/usr/bin/env python3
"""Build area-weighted PV--Building results from frozen paper inputs.

The primary physical outcome is anchor-year PV polygon-union area.  For the
strict risk panel, all resolved source-PV areas on a unique host are summed and
attributed to that host's first strict adjacent PV event.  This supports the
exact decomposition

    A_retrofit / A_new
      = (N_stock / N_new)
        * (r_retrofit / r_new)
        * (mean_area_retrofit / mean_area_new).

Capacity fields are explicitly labelled DC-capacity-equivalent scenarios; the
frozen inventory contains no measured system nameplate capacity.
"""

from __future__ import annotations

import argparse
import ast
import csv
import hashlib
import json
import math
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import numpy as np


SCRIPT_VERSION = "1.0.0"
CAPACITY_SCENARIOS = (
    {
        "scenario_id": "legacy_module_density_low",
        "power_density_kwdc_per_m2": 0.160,
        "role": "lower_bound",
        "source_title": "Rooftop Solar Photovoltaic Technical Potential in the United States",
        "source_url": "https://www.nrel.gov/docs/fy16osti/65298.pdf",
        "source_fact": "NREL rooftop-potential analysis used 160 Wdc per square metre of module area, representing approximately 16% efficiency and the 2014 installed mixture.",
        "applicability": "Illustrative legacy-module-density scenario; the detected PV union is plan-view footprint, not measured module surface area.",
        "status": "REPRODUCED",
    },
    {
        "scenario_id": "nominal_display_density",
        "power_density_kwdc_per_m2": 0.200,
        "role": "nominal",
        "source_title": "Analytical display conversion bracketed by the two NREL/DOE scenarios",
        "source_url": "",
        "source_fact": "Rounded conversion used only to provide a readable MWdc-equivalent secondary scale.",
        "applicability": "Not a calibrated or measured nameplate estimate; route shares and area ratios do not depend on this constant.",
        "status": "REPRODUCED",
    },
    {
        "scenario_id": "contemporary_module_density_high",
        "power_density_kwdc_per_m2": 400.0 / 1.9 / 1000.0,
        "role": "upper_bound",
        "source_title": "Solar Photovoltaic System Cost Benchmarks",
        "source_url": "https://www.energy.gov/cmei/systems/solar-photovoltaic-system-cost-benchmarks",
        "source_fact": "The 2024 representative residential rooftop module is 400 Wdc over 1.9 square metres (about 210.5 Wdc per square metre).",
        "applicability": "Illustrative contemporary-module-density scenario; not a city- or vintage-specific calibration.",
        "status": "REPRODUCED",
    },
)


def parse_args() -> argparse.Namespace:
    workspace = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--index", type=Path, default=workspace / "results" / "major_results_index.json"
    )
    parser.add_argument(
        "--artifact-index",
        type=Path,
        default=workspace / "results" / "artifact_results_index.csv",
    )
    parser.add_argument(
        "--risk-evidence-manifest",
        type=Path,
        default=workspace / "data_high_level" / "results_conclusion_evidence_manifest.json",
    )
    parser.add_argument(
        "--count-city-table",
        type=Path,
        default=workspace / "data_high_level" / "city_stock_flow_decomposition.csv",
    )
    parser.add_argument(
        "--count-transition-table",
        type=Path,
        default=workspace / "data_high_level" / "city_transition_route_dynamics.csv",
    )
    parser.add_argument(
        "--area-trajectory-table",
        type=Path,
        default=workspace / "data_high_level" / "city_pv_building_area_trajectories.csv",
    )
    parser.add_argument(
        "--area-interval-table",
        type=Path,
        default=workspace / "data_high_level" / "city_pv_building_area_interval_counts.csv",
    )
    parser.add_argument(
        "--area-manifest",
        type=Path,
        default=workspace / "data_high_level" / "city_pv_building_area_manifest.json",
    )
    parser.add_argument(
        "--output-dir", type=Path, default=workspace / "data_high_level"
    )
    return parser.parse_args()


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace(
        "+00:00", "Z"
    )


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(16 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def csv_row_count(path: Path) -> int:
    csv.field_size_limit(sys.maxsize)
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.reader(handle)
        next(reader, None)
        return sum(1 for _ in reader)


def write_json(path: Path, value: Any) -> None:
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        raise ValueError(f"Refusing to write empty table: {path}")
    fields = list(rows[0])
    if any(list(row) != fields for row in rows):
        raise ValueError(f"Inconsistent row schema for {path}")
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def finite_or_blank(value: Any) -> Any:
    if value is None:
        return ""
    if isinstance(value, (float, np.floating)) and not math.isfinite(float(value)):
        return ""
    return value


def safe_ratio(numerator: float, denominator: float) -> float | None:
    if denominator == 0:
        return None
    return numerator / denominator


def parse_source_polygon_ids(text: str) -> list[str]:
    value = ast.literal_eval(text)
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise ValueError(f"Unexpected anchor_source_pv_ids value: {text[:100]!r}")
    return value


def input_record(
    role: str,
    path: Path,
    expected_sha256: str | None = None,
    expected_row_count: int | None = None,
    primary_key: Any = None,
) -> dict[str, Any]:
    observed_sha256 = sha256_file(path)
    if expected_sha256 and observed_sha256 != expected_sha256:
        raise ValueError(f"Input hash mismatch for {path}")
    record: dict[str, Any] = {
        "role": role,
        "path": str(path.resolve()),
        "sha256_expected": expected_sha256 or observed_sha256,
        "sha256_observed": observed_sha256,
        "bytes": path.stat().st_size,
    }
    if path.suffix.lower() == ".csv":
        observed_rows = csv_row_count(path)
        if expected_row_count is not None and observed_rows != expected_row_count:
            raise ValueError(f"Input row-count mismatch for {path}")
        record["row_count_expected"] = (
            observed_rows if expected_row_count is None else expected_row_count
        )
        record["row_count_observed"] = observed_rows
    if primary_key is not None:
        record["primary_key"] = primary_key
    return record


def load_area_totals(
    trajectory_path: Path, interval_path: Path
) -> tuple[dict[str, dict[str, float]], list[dict[str, Any]]]:
    required = {
        "city_id",
        "calendar_year",
        "anchor_pv_area_m2",
        "left_censored_baseline_pv_area_m2",
        "anchor_building_area_m2",
        "left_censored_baseline_building_area_m2",
        "anchor_pv_target_count",
        "anchor_building_target_count",
    }
    by_city: dict[str, dict[str, float]] = {}
    constant_fields = required - {"city_id", "calendar_year"}
    with trajectory_path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None or not required.issubset(reader.fieldnames):
            raise ValueError("Area trajectory table lacks required columns")
        for row in reader:
            city_id = row["city_id"]
            values = {field: float(row[field]) for field in constant_fields}
            if city_id in by_city:
                for field, value in values.items():
                    if not math.isclose(
                        by_city[city_id][field], value, rel_tol=0, abs_tol=1e-8
                    ):
                        raise ValueError(
                            f"{city_id}: nonconstant trajectory field {field}"
                        )
            else:
                by_city[city_id] = values
    totals: dict[str, dict[str, float]] = {}
    contrast_rows: list[dict[str, Any]] = []
    for city_id, values in sorted(by_city.items()):
        totals[city_id] = values
        pv_post = values["anchor_pv_area_m2"] - values[
            "left_censored_baseline_pv_area_m2"
        ]
        building_post = values["anchor_building_area_m2"] - values[
            "left_censored_baseline_building_area_m2"
        ]
        contrast_rows.append(
            {
                "city_id": city_id,
                "anchor_pv_area_m2": values["anchor_pv_area_m2"],
                "left_censored_pv_area_m2": values[
                    "left_censored_baseline_pv_area_m2"
                ],
                "postbaseline_pv_area_m2": pv_post,
                "postbaseline_pv_area_share": pv_post / values["anchor_pv_area_m2"],
                "anchor_building_roof_mask_area_m2": values[
                    "anchor_building_area_m2"
                ],
                "left_censored_building_roof_mask_area_m2": values[
                    "left_censored_baseline_building_area_m2"
                ],
                "postbaseline_building_roof_mask_area_m2": building_post,
                "postbaseline_building_roof_mask_area_share": building_post
                / values["anchor_building_area_m2"],
                "pv_minus_building_postbaseline_area_share": pv_post
                / values["anchor_pv_area_m2"]
                - building_post / values["anchor_building_area_m2"],
                "denominator_definition": "separate city-specific anchor PV union area and canonical Building SAM3 roof-mask area",
                "time_definition": "PAU interval allocation; left-censored mass is baseline stock; cohort bounds are not exact event dates",
                "status": "REPRODUCED",
            }
        )

    interval_sums: Counter = Counter()
    with interval_path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        required_interval = {"city_id", "entity", "anchor_area_m2"}
        if reader.fieldnames is None or not required_interval.issubset(reader.fieldnames):
            raise ValueError("Area interval table lacks required columns")
        for row in reader:
            interval_sums[(row["city_id"], row["entity"])] += float(
                row["anchor_area_m2"]
            )
    for city_id, values in totals.items():
        for entity, total_field in (
            ("pv", "anchor_pv_area_m2"),
            ("building", "anchor_building_area_m2"),
        ):
            observed = float(interval_sums[(city_id, entity)])
            if not math.isclose(observed, values[total_field], rel_tol=1e-12, abs_tol=1e-5):
                raise ValueError(f"{city_id}/{entity}: interval area does not reconcile")

    sums = {
        field: sum(float(row[field]) for row in contrast_rows)
        for field in (
            "anchor_pv_area_m2",
            "left_censored_pv_area_m2",
            "postbaseline_pv_area_m2",
            "anchor_building_roof_mask_area_m2",
            "left_censored_building_roof_mask_area_m2",
            "postbaseline_building_roof_mask_area_m2",
        )
    }
    pooled_pv_share = sums["postbaseline_pv_area_m2"] / sums["anchor_pv_area_m2"]
    pooled_building_share = (
        sums["postbaseline_building_roof_mask_area_m2"]
        / sums["anchor_building_roof_mask_area_m2"]
    )
    pooled: dict[str, Any] = {
        "city_id": "all_cities_pooled",
        "anchor_pv_area_m2": sums["anchor_pv_area_m2"],
        "left_censored_pv_area_m2": sums["left_censored_pv_area_m2"],
        "postbaseline_pv_area_m2": sums["postbaseline_pv_area_m2"],
        "postbaseline_pv_area_share": pooled_pv_share,
        "anchor_building_roof_mask_area_m2": sums[
            "anchor_building_roof_mask_area_m2"
        ],
        "left_censored_building_roof_mask_area_m2": sums[
            "left_censored_building_roof_mask_area_m2"
        ],
        "postbaseline_building_roof_mask_area_m2": sums[
            "postbaseline_building_roof_mask_area_m2"
        ],
        "postbaseline_building_roof_mask_area_share": pooled_building_share,
        "pv_minus_building_postbaseline_area_share": pooled_pv_share
        - pooled_building_share,
        "denominator_definition": contrast_rows[0]["denominator_definition"],
        "time_definition": contrast_rows[0]["time_definition"],
        "status": "REPRODUCED",
    }
    contrast_rows.append(pooled)
    return totals, contrast_rows


def read_relationship_areas(
    city: dict[str, Any],
    area_total: float,
) -> tuple[
    dict[str, float],
    dict[str, dict[str, Any]],
    list[dict[str, Any]],
    dict[str, Any],
]:
    artifact = city["artifacts"]["pv_building_relationship"]
    path = Path(artifact["path"])
    required = [
        "temporal_pv_target_id",
        "anchor_pv_union_area_m2",
        "anchor_source_pv_ids",
        "building_first_appearance_available",
        "paired_production_building_id",
        "pair_status",
        "pv_pau_first_credible_present_index",
        "building_pau_first_credible_present_index",
    ]
    target_areas: dict[str, float] = {}
    relationship_meta: dict[str, dict[str, Any]] = {}
    seen_polygon_ids: set[str] = set()
    duplicate_polygon_ids = 0
    class_stats: dict[str, dict[str, float]] = defaultdict(
        lambda: {"target_count": 0, "pv_union_area_m2": 0.0}
    )
    observed_total = 0.0
    row_count = 0
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None or not set(required).issubset(reader.fieldnames):
            raise ValueError(f"{city['city_id']}: relationship schema mismatch")
        for row in reader:
            row_count += 1
            target_id = row["temporal_pv_target_id"]
            if not target_id or target_id in target_areas:
                raise ValueError(f"{city['city_id']}: blank or duplicate temporal PV target")
            area = float(row["anchor_pv_union_area_m2"])
            if not math.isfinite(area) or area <= 0:
                raise ValueError(f"{city['city_id']}: non-positive PV area")
            observed_total += area
            polygon_ids = parse_source_polygon_ids(row["anchor_source_pv_ids"])
            for polygon_id in polygon_ids:
                if polygon_id in seen_polygon_ids:
                    duplicate_polygon_ids += 1
                seen_polygon_ids.add(polygon_id)
            available = row["building_first_appearance_available"].lower() == "true"
            if available:
                pv_onset = int(float(row["pv_pau_first_credible_present_index"]))
                building_onset = int(float(row["building_pau_first_credible_present_index"]))
                if pv_onset > building_onset:
                    appearance_order = "building_before_pv"
                elif pv_onset == building_onset:
                    appearance_order = "same_first_present_cohort"
                else:
                    appearance_order = "pv_before_building_conflict"
                if row["pair_status"] != "resolved" or not row["paired_production_building_id"]:
                    raise ValueError(f"{city['city_id']}: available relationship is not resolved")
            else:
                appearance_order = "unavailable_relationship"
            class_stats[appearance_order]["target_count"] += 1
            class_stats[appearance_order]["pv_union_area_m2"] += area
            target_areas[target_id] = area
            relationship_meta[target_id] = {
                "paired_production_building_id": row["paired_production_building_id"],
                "available": available,
            }
    if row_count != int(artifact["row_count"]):
        raise ValueError(f"{city['city_id']}: relationship row count mismatch")
    if not math.isclose(observed_total, area_total, rel_tol=1e-12, abs_tol=1e-5):
        raise ValueError(f"{city['city_id']}: relationship and trajectory PV area disagree")
    if duplicate_polygon_ids:
        raise ValueError(
            f"{city['city_id']}: {duplicate_polygon_ids} source PV polygon identities repeat"
        )
    resolved_area = sum(
        values["pv_union_area_m2"]
        for key, values in class_stats.items()
        if key != "unavailable_relationship"
    )
    resolved_count = sum(
        int(values["target_count"])
        for key, values in class_stats.items()
        if key != "unavailable_relationship"
    )
    pathway_rows: list[dict[str, Any]] = []
    for appearance_order in (
        "building_before_pv",
        "same_first_present_cohort",
        "pv_before_building_conflict",
        "unavailable_relationship",
    ):
        values = class_stats[appearance_order]
        is_resolved = appearance_order != "unavailable_relationship"
        pathway_rows.append(
            {
                "city_id": city["city_id"],
                "appearance_order": appearance_order,
                "pv_target_count": int(values["target_count"]),
                "pv_union_area_m2": values["pv_union_area_m2"],
                "share_of_resolved_pv_target_count": (
                    values["target_count"] / resolved_count if is_resolved else ""
                ),
                "share_of_resolved_pv_union_area": (
                    values["pv_union_area_m2"] / resolved_area if is_resolved else ""
                ),
                "mean_pv_union_area_m2_per_target": safe_ratio(
                    values["pv_union_area_m2"], values["target_count"]
                ),
                "denominator_definition": "resolved canonical PV targets and their additive anchor building-level PV union areas; unavailable relationships shown separately",
                "status": "REPRODUCED",
            }
        )
    diagnostics = {
        "relationship_target_count": row_count,
        "relationship_pv_area_m2": observed_total,
        "resolved_target_count": resolved_count,
        "resolved_pv_area_m2": resolved_area,
        "unavailable_target_count": int(
            class_stats["unavailable_relationship"]["target_count"]
        ),
        "unavailable_pv_area_m2": class_stats["unavailable_relationship"][
            "pv_union_area_m2"
        ],
        "source_pv_polygon_id_count": len(seen_polygon_ids),
        "source_pv_polygon_ids_globally_unique_within_city": True,
    }
    return target_areas, relationship_meta, pathway_rows, diagnostics


def build_host_areas(
    city_id: str,
    pair_path: Path,
    pair_expected_rows: int,
    target_areas: dict[str, float],
    relationship_meta: dict[str, dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    columns = [
        "production_building_id",
        "source_pv_target_count",
        "source_pv_target_ids",
        "pv_pau_first_appearance_type",
        "pv_pau_first_appearance_lower_index",
        "pv_pau_first_appearance_upper_index",
        "pv_pau_first_credible_present_index",
    ]
    pairs: list[dict[str, Any]] = []
    seen_hosts: set[str] = set()
    used_targets: set[str] = set()
    multi_source_hosts = 0
    max_source_count = 0
    with pair_path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None or not set(columns).issubset(reader.fieldnames):
            raise ValueError(f"{city_id}: unique-pair schema mismatch")
        for source_row in reader:
            row = {field: source_row[field] for field in columns}
            host_id = row["production_building_id"]
            if not host_id or host_id in seen_hosts:
                raise ValueError(f"{city_id}: blank or duplicate unique host")
            seen_hosts.add(host_id)
            source_ids = row["source_pv_target_ids"].split("|")
            declared = int(row["source_pv_target_count"])
            if len(source_ids) != declared or len(set(source_ids)) != declared:
                raise ValueError(f"{city_id}/{host_id}: invalid source-target lineage")
            multi_source_hosts += int(declared > 1)
            max_source_count = max(max_source_count, declared)
            area = 0.0
            for target_id in source_ids:
                if target_id in used_targets:
                    raise ValueError(f"{city_id}: source PV target assigned to two hosts")
                meta = relationship_meta.get(target_id)
                if meta is None or not meta["available"]:
                    raise ValueError(f"{city_id}: host uses unavailable PV target {target_id}")
                if meta["paired_production_building_id"] != host_id:
                    raise ValueError(f"{city_id}: target-to-host lineage mismatch")
                used_targets.add(target_id)
                area += target_areas[target_id]
            row["host_anchor_pv_union_area_m2"] = area
            pairs.append(row)
    if len(pairs) != pair_expected_rows:
        raise ValueError(f"{city_id}: unique-pair row-count mismatch")
    resolved_targets = {
        target_id for target_id, meta in relationship_meta.items() if meta["available"]
    }
    if used_targets != resolved_targets:
        raise ValueError(
            f"{city_id}: unique-pair lineage does not cover exactly all resolved PV targets"
        )
    if any(float(row["host_anchor_pv_union_area_m2"]) <= 0 for row in pairs):
        raise ValueError(f"{city_id}: non-positive host PV area")
    resolved_host_area = sum(
        float(row["host_anchor_pv_union_area_m2"]) for row in pairs
    )
    return pairs, {
        "unique_host_count": len(pairs),
        "resolved_source_pv_target_count": len(used_targets),
        "multi_source_host_count": multi_source_hosts,
        "maximum_source_pv_targets_per_host": max_source_count,
        "resolved_host_pv_area_m2": resolved_host_area,
    }


def area_metrics(
    n_new: int,
    y_new: int,
    n_stock: int,
    y_retrofit: int,
    area_new: float,
    area_retrofit: float,
) -> dict[str, Any]:
    total_area = area_new + area_retrofit
    count_total = y_new + y_retrofit
    r_new = safe_ratio(y_new, n_new)
    r_retrofit = safe_ratio(y_retrofit, n_stock)
    mean_new = safe_ratio(area_new, y_new)
    mean_retrofit = safe_ratio(area_retrofit, y_retrofit)
    yield_new = safe_ratio(area_new, n_new)
    yield_retrofit = safe_ratio(area_retrofit, n_stock)
    area_yield_rr = (
        safe_ratio(yield_new, yield_retrofit)
        if yield_new is not None and yield_retrofit is not None
        else None
    )
    count_rr = (
        safe_ratio(r_new, r_retrofit)
        if r_new is not None and r_retrofit is not None
        else None
    )
    stock_multiplier = safe_ratio(n_stock, n_new)
    event_intensity_retrofit_to_new = (
        safe_ratio(r_retrofit, r_new)
        if r_new is not None and r_retrofit is not None
        else None
    )
    event_size_retrofit_to_new = (
        safe_ratio(mean_retrofit, mean_new)
        if mean_new is not None and mean_retrofit is not None
        else None
    )
    area_ratio = safe_ratio(area_retrofit, area_new)
    logs: list[float | None] = []
    for value in (
        stock_multiplier,
        event_intensity_retrofit_to_new,
        event_size_retrofit_to_new,
        area_ratio,
    ):
        logs.append(math.log(value) if value is not None and value > 0 else None)
    residual = (
        logs[0] + logs[1] + logs[2] - logs[3]
        if all(value is not None for value in logs)
        else None
    )
    nominal = next(
        row["power_density_kwdc_per_m2"]
        for row in CAPACITY_SCENARIOS
        if row["role"] == "nominal"
    )
    low = min(row["power_density_kwdc_per_m2"] for row in CAPACITY_SCENARIOS)
    high = max(row["power_density_kwdc_per_m2"] for row in CAPACITY_SCENARIOS)
    return {
        "n_new": n_new,
        "y_new": y_new,
        "n_stock": n_stock,
        "y_retrofit": y_retrofit,
        "pv_area_new_m2": area_new,
        "pv_area_retrofit_m2": area_retrofit,
        "pv_area_total_classified_m2": total_area,
        "nominal_capacity_new_mwdc_equivalent": area_new * nominal / 1000,
        "nominal_capacity_retrofit_mwdc_equivalent": area_retrofit * nominal / 1000,
        "nominal_capacity_total_mwdc_equivalent": total_area * nominal / 1000,
        "capacity_total_low_mwdc_equivalent": total_area * low / 1000,
        "capacity_total_high_mwdc_equivalent": total_area * high / 1000,
        "retrofit_share_of_classified_pv_area": safe_ratio(area_retrofit, total_area),
        "retrofit_share_of_classified_event_count": safe_ratio(y_retrofit, count_total),
        "area_minus_count_retrofit_share": (
            area_retrofit / total_area - y_retrofit / count_total
            if total_area and count_total
            else None
        ),
        "area_retrofit_to_new_ratio": area_ratio,
        "stock_multiplier": stock_multiplier,
        "r_new_event_per_building": r_new,
        "r_retrofit_event_per_building_cohort": r_retrofit,
        "count_rr_new_to_retrofit": count_rr,
        "mean_pv_area_per_new_event_m2": mean_new,
        "mean_pv_area_per_retrofit_event_m2": mean_retrofit,
        "event_size_ratio_retrofit_to_new": event_size_retrofit_to_new,
        "pv_area_yield_new_m2_per_new_building": yield_new,
        "pv_area_yield_retrofit_m2_per_stock_exposure": yield_retrofit,
        "area_yield_rr_new_to_retrofit": area_yield_rr,
        "log_stock_size_contribution": logs[0],
        "log_event_intensity_contribution": logs[1],
        "log_event_size_contribution": logs[2],
        "log_observed_area_contribution_ratio": logs[3],
        "three_factor_decomposition_residual": residual,
    }


def estimate_scope(
    city_id: str,
    scope: str,
    building_path: Path,
    cohorts: list[str],
    pairs: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, Any], dict[str, np.ndarray]]:
    columns = {
        "production_building_id",
        "pau_first_appearance_type",
        "pau_first_appearance_lower_index",
        "pau_first_appearance_upper_index",
        *cohorts,
    }
    pair_map: dict[str, dict[str, Any]] = {}
    for row in pairs:
        host_id = row["production_building_id"]
        lower_text = row["pv_pau_first_appearance_lower_index"].strip()
        upper_text = row["pv_pau_first_appearance_upper_index"].strip()
        onset_text = row["pv_pau_first_credible_present_index"].strip()
        lower = int(float(lower_text)) if lower_text else None
        upper = int(float(upper_text)) if upper_text else None
        onset = int(float(onset_text)) if onset_text else None
        strict = (
            row["pv_pau_first_appearance_type"] == "interval_censored"
            and lower is not None
            and upper is not None
            and upper - lower == 1
        )
        pair_map[host_id] = {
            "onset": onset,
            "strict_event_transition": upper if strict else None,
            "area": float(row["host_anchor_pv_union_area_m2"]),
        }

    per_transition = [
        {
            "n_new": 0,
            "y_new": 0,
            "n_stock": 0,
            "y_retrofit": 0,
            "new_areas": [],
            "retrofit_areas": [],
        }
        for _ in range(len(cohorts) - 1)
    ]
    seen_ids: set[str] = set()
    seen_paired_hosts: set[str] = set()
    row_count = 0
    with building_path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None or not columns.issubset(reader.fieldnames):
            raise ValueError(f"{city_id}/{scope}: Building schema mismatch")
        for row in reader:
            row_count += 1
            building_id = row["production_building_id"]
            if not building_id or building_id in seen_ids:
                raise ValueError(f"{city_id}/{scope}: blank or duplicate Building identity")
            seen_ids.add(building_id)
            pair = pair_map.get(building_id)
            if pair is not None:
                seen_paired_hosts.add(building_id)
                pv_onset = pair["onset"]
                event_transition = pair["strict_event_transition"]
                weight = pair["area"]
            else:
                pv_onset = None
                event_transition = None
                weight = None
            lower_text = row["pau_first_appearance_lower_index"].strip()
            upper_text = row["pau_first_appearance_upper_index"].strip()
            building_lower = int(float(lower_text)) if lower_text else None
            building_upper = int(float(upper_text)) if upper_text else None
            building_strict = (
                row["pau_first_appearance_type"] == "interval_censored"
                and building_lower is not None
                and building_upper is not None
                and building_upper - building_lower == 1
            )
            for transition_index, (previous, current) in enumerate(
                zip(cohorts, cohorts[1:]), start=1
            ):
                at_risk = pv_onset is None or pv_onset >= transition_index
                if not at_risk:
                    continue
                slot = per_transition[transition_index - 1]
                new_group = building_strict and building_upper == transition_index
                stock_group = (
                    row[previous] == "present" and row[current] == "present"
                )
                is_event = event_transition == transition_index
                if new_group:
                    slot["n_new"] += 1
                    if is_event:
                        if weight is None:
                            raise ValueError(f"{city_id}/{scope}: new event lacks PV area")
                        slot["y_new"] += 1
                        slot["new_areas"].append(weight)
                if stock_group:
                    slot["n_stock"] += 1
                    if is_event:
                        if weight is None:
                            raise ValueError(f"{city_id}/{scope}: retrofit event lacks PV area")
                        slot["y_retrofit"] += 1
                        slot["retrofit_areas"].append(weight)
    if seen_paired_hosts != set(pair_map):
        missing = sorted(set(pair_map).difference(seen_paired_hosts))[:5]
        raise ValueError(f"{city_id}/{scope}: paired hosts absent from Building table: {missing}")

    transition_rows: list[dict[str, Any]] = []
    totals = {"n_new": 0, "y_new": 0, "n_stock": 0, "y_retrofit": 0}
    area_new_values: list[np.ndarray] = []
    area_retrofit_values: list[np.ndarray] = []
    for transition_index, (previous, current, slot) in enumerate(
        zip(cohorts, cohorts[1:], per_transition), start=1
    ):
        counts = {key: int(slot[key]) for key in totals}
        new_weights = np.asarray(slot["new_areas"], dtype=float)
        retrofit_weights = np.asarray(slot["retrofit_areas"], dtype=float)
        if len(new_weights) != counts["y_new"] or len(retrofit_weights) != counts["y_retrofit"]:
            raise ValueError(f"{city_id}/{scope}: event/area cardinality mismatch")
        for key in totals:
            totals[key] += counts[key]
        area_new_values.append(new_weights)
        area_retrofit_values.append(retrofit_weights)
        metrics = area_metrics(
            counts["n_new"], counts["y_new"], counts["n_stock"], counts["y_retrofit"],
            float(new_weights.sum()), float(retrofit_weights.sum())
        )
        transition_rows.append(
            {
                "city_id": city_id,
                "scope": scope,
                "transition_index": transition_index,
                "previous_cohort": previous,
                "current_cohort": current,
                **{key: finite_or_blank(value) for key, value in metrics.items()},
                "area_attribution_rule": "sum all resolved source-target anchor PV union areas on a unique host and attribute that anchor area to the host's first strict adjacent PV event",
                "capacity_definition": "illustrative DC-capacity-equivalent; not measured nameplate capacity",
                "time_unit_warning": "ordered cohort transition; not an annual installation or capacity-addition interval",
                "status": "REPRODUCED",
            }
        )
    new_all = np.concatenate(area_new_values) if area_new_values else np.array([])
    retrofit_all = (
        np.concatenate(area_retrofit_values) if area_retrofit_values else np.array([])
    )
    aggregate_metrics = area_metrics(
        totals["n_new"], totals["y_new"], totals["n_stock"], totals["y_retrofit"],
        float(new_all.sum()), float(retrofit_all.sum())
    )
    aggregate = {
        "city_id": city_id,
        "scope": scope,
        "cohort_count": len(cohorts),
        "transition_count": len(cohorts) - 1,
        "building_identity_count": row_count,
        "pv_paired_building_count": len(pairs),
        **{key: finite_or_blank(value) for key, value in aggregate_metrics.items()},
        "resolved_linked_host_pv_area_m2": float(
            sum(float(row["host_anchor_pv_union_area_m2"]) for row in pairs)
        ),
        "strict_classified_share_of_resolved_linked_host_pv_area": safe_ratio(
            float(new_all.sum() + retrofit_all.sum()),
            sum(float(row["host_anchor_pv_union_area_m2"]) for row in pairs),
        ),
        "area_attribution_rule": "sum all resolved source-target anchor PV union areas on a unique host and attribute that anchor area to the host's first strict adjacent PV event",
        "capacity_definition": "illustrative DC-capacity-equivalent; not measured nameplate capacity",
        "estimand": "anchor PV area on unique hosts per strict raw-known new-Building or existing-Building risk unit",
        "target_population": "full Anchor AOI or canonical narrow Building risk set with anchor-surviving accepted linked PV",
        "status": "REPRODUCED",
    }
    return transition_rows, aggregate, {
        "new": new_all,
        "existing": retrofit_all,
    }


def distribution_metrics(
    city_id: str, scope: str, route: str, values: np.ndarray
) -> dict[str, Any]:
    ordered = np.sort(values.astype(float))
    count = len(ordered)
    total = float(ordered.sum())
    if count:
        top_count = max(1, int(math.ceil(count * 0.01)))
        cumulative = np.cumsum(ordered)
        gini = (
            (2 * np.sum((np.arange(1, count + 1)) * ordered) / (count * total))
            - (count + 1) / count
            if total > 0
            else None
        )
    else:
        top_count = 0
        gini = None
    nominal = next(
        row["power_density_kwdc_per_m2"]
        for row in CAPACITY_SCENARIOS
        if row["role"] == "nominal"
    )
    return {
        "city_id": city_id,
        "scope": scope,
        "route": route,
        "strict_event_host_count": count,
        "pv_union_area_m2": total,
        "nominal_capacity_mwdc_equivalent": total * nominal / 1000,
        "mean_host_pv_area_m2": float(ordered.mean()) if count else "",
        "median_host_pv_area_m2": float(np.quantile(ordered, 0.5)) if count else "",
        "p90_host_pv_area_m2": float(np.quantile(ordered, 0.9)) if count else "",
        "p99_host_pv_area_m2": float(np.quantile(ordered, 0.99)) if count else "",
        "top_1pct_host_count": top_count,
        "top_1pct_share_of_route_pv_area": (
            float(ordered[-top_count:].sum() / total) if count and total else ""
        ),
        "gini_host_pv_area": finite_or_blank(gini),
        "unit_definition": "unique host; all anchor PV union area on the host is attributed to its first strict adjacent PV event",
        "status": "REPRODUCED",
    }


def aggregate_pathway_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    pooled_counts: Counter = Counter()
    pooled_areas: Counter = Counter()
    for row in rows:
        pooled_counts[row["appearance_order"]] += int(row["pv_target_count"])
        pooled_areas[row["appearance_order"]] += float(row["pv_union_area_m2"])
    resolved_keys = (
        "building_before_pv",
        "same_first_present_cohort",
        "pv_before_building_conflict",
    )
    resolved_count = sum(pooled_counts[key] for key in resolved_keys)
    resolved_area = sum(pooled_areas[key] for key in resolved_keys)
    pooled_rows: list[dict[str, Any]] = []
    for key in (*resolved_keys, "unavailable_relationship"):
        is_resolved = key != "unavailable_relationship"
        pooled_rows.append(
            {
                "city_id": "all_cities_pooled",
                "appearance_order": key,
                "pv_target_count": pooled_counts[key],
                "pv_union_area_m2": pooled_areas[key],
                "share_of_resolved_pv_target_count": (
                    pooled_counts[key] / resolved_count if is_resolved else ""
                ),
                "share_of_resolved_pv_union_area": (
                    pooled_areas[key] / resolved_area if is_resolved else ""
                ),
                "mean_pv_union_area_m2_per_target": safe_ratio(
                    pooled_areas[key], pooled_counts[key]
                ),
                "denominator_definition": rows[0]["denominator_definition"],
                "status": "REPRODUCED",
            }
        )
    return rows + pooled_rows


def aggregate_stock_rows(
    city_rows: list[dict[str, Any]], scope: str
) -> dict[str, Any]:
    selected = [row for row in city_rows if row["scope"] == scope]
    totals = {
        key: sum(float(row[key]) for row in selected)
        for key in (
            "n_new",
            "y_new",
            "n_stock",
            "y_retrofit",
            "pv_area_new_m2",
            "pv_area_retrofit_m2",
        )
    }
    metrics = area_metrics(
        int(totals["n_new"]), int(totals["y_new"]), int(totals["n_stock"]),
        int(totals["y_retrofit"]), totals["pv_area_new_m2"], totals["pv_area_retrofit_m2"]
    )
    resolved_area = sum(float(row["resolved_linked_host_pv_area_m2"]) for row in selected)
    return {
        "city_id": "all_cities_pooled",
        "scope": scope,
        "cohort_count": "",
        "transition_count": sum(int(row["transition_count"]) for row in selected),
        "building_identity_count": sum(int(row["building_identity_count"]) for row in selected),
        "pv_paired_building_count": sum(int(row["pv_paired_building_count"]) for row in selected),
        **{key: finite_or_blank(value) for key, value in metrics.items()},
        "resolved_linked_host_pv_area_m2": resolved_area,
        "strict_classified_share_of_resolved_linked_host_pv_area": safe_ratio(
            totals["pv_area_new_m2"] + totals["pv_area_retrofit_m2"], resolved_area
        ),
        "area_attribution_rule": selected[0]["area_attribution_rule"],
        "capacity_definition": selected[0]["capacity_definition"],
        "estimand": selected[0]["estimand"],
        "target_population": selected[0]["target_population"],
        "status": "REPRODUCED",
    }


def assert_counts_match(
    observed: Iterable[dict[str, Any]], target_path: Path, transition: bool
) -> None:
    keys = ["city_id", "scope"]
    if transition:
        keys.append("transition_index")
    lookup: dict[tuple[str, ...], tuple[int, ...]] = {}
    with target_path.open("r", encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            if row["city_id"] == "all_cities_pooled":
                continue
            key = tuple(row[field] for field in keys)
            lookup[key] = tuple(
                int(float(row[field]))
                for field in ("n_new", "y_new", "n_stock", "y_retrofit")
            )
    observed_rows = list(observed)
    for row in observed_rows:
        key = tuple(str(row[field]) for field in keys)
        counts = tuple(int(row[field]) for field in ("n_new", "y_new", "n_stock", "y_retrofit"))
        if lookup.get(key) != counts:
            raise ValueError(f"Count reproduction mismatch for {key}: {counts} != {lookup.get(key)}")
    if len(lookup) != len(observed_rows):
        raise ValueError("Count target and area-weighted row cardinalities differ")


def main() -> int:
    args = parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    for path in (
        args.index,
        args.artifact_index,
        args.risk_evidence_manifest,
        args.count_city_table,
        args.count_transition_table,
        args.area_trajectory_table,
        args.area_interval_table,
        args.area_manifest,
    ):
        if not path.is_file():
            raise FileNotFoundError(path)
    index = json.loads(args.index.read_text(encoding="utf-8"))
    cities = sorted(index["cities"], key=lambda row: row["city_id"])
    if len(cities) != 15:
        raise ValueError("Expected the frozen 15-city index")
    area_manifest = json.loads(args.area_manifest.read_text(encoding="utf-8"))
    if area_manifest.get("status") != "REPRODUCED":
        raise ValueError("Area trajectory manifest is not REPRODUCED")
    expected_area_tables = area_manifest["tables"]
    input_records: list[dict[str, Any]] = [
        input_record("frozen_major_results_index", args.index),
        input_record("artifact_results_index", args.artifact_index),
        input_record("count_results_manifest", args.risk_evidence_manifest),
        input_record(
            "count_city_reconciliation",
            args.count_city_table,
            expected_sha256=json.loads(args.risk_evidence_manifest.read_text())["outputs"][
                "city_stock_flow_decomposition"
            ]["sha256"],
        ),
        input_record(
            "count_transition_reconciliation",
            args.count_transition_table,
            expected_sha256=json.loads(args.risk_evidence_manifest.read_text())["outputs"][
                "city_transition_route_dynamics"
            ]["sha256"],
        ),
        input_record(
            "area_trajectory",
            args.area_trajectory_table,
            expected_sha256=expected_area_tables["city_pv_building_area_trajectories"]["sha256"],
            expected_row_count=expected_area_tables["city_pv_building_area_trajectories"]["row_count"],
            primary_key=["city_id", "calendar_year"],
        ),
        input_record(
            "area_interval_counts",
            args.area_interval_table,
            expected_sha256=expected_area_tables["city_pv_building_area_interval_counts"]["sha256"],
            expected_row_count=expected_area_tables["city_pv_building_area_interval_counts"]["row_count"],
            primary_key=["city_id", "entity", "onset_type", "lower_cohort_order", "upper_cohort_order"],
        ),
        input_record("area_trajectory_manifest", args.area_manifest),
    ]
    area_totals, temporal_contrast_rows = load_area_totals(
        args.area_trajectory_table, args.area_interval_table
    )

    risk_manifest = json.loads(args.risk_evidence_manifest.read_text(encoding="utf-8"))
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
                "completed_full_aoi_raw_known_risk_release_manifest",
                release_manifest_path,
                expected_sha256=record["sha256"],
            )
        )
        expected_input = release_manifest["outputs"]["inputs/input_manifest.json"]
        input_records.append(
            input_record(
                "completed_full_aoi_raw_known_risk_input_manifest",
                input_manifest_path,
                expected_sha256=expected_input["sha256"],
            )
        )
        for city_id, metadata in release_inputs["cities"].items():
            if city_id in risk_inputs:
                raise ValueError(f"City appears in two risk releases: {city_id}")
            risk_inputs[city_id] = metadata
    if set(risk_inputs) != {city["city_id"] for city in cities}:
        raise ValueError("Risk releases do not cover the frozen 15 cities exactly")

    pathway_rows: list[dict[str, Any]] = []
    transition_rows: list[dict[str, Any]] = []
    city_rows: list[dict[str, Any]] = []
    distribution_rows: list[dict[str, Any]] = []
    city_checks: list[dict[str, Any]] = []
    pooled_distributions: dict[tuple[str, str], list[np.ndarray]] = defaultdict(list)
    for position, city in enumerate(cities, start=1):
        city_id = city["city_id"]
        print(f"[{position:02d}/15] {city_id}: PV area lineage", flush=True)
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
        target_areas, relationship_meta, city_pathway, relation_check = read_relationship_areas(
            city, area_totals[city_id]["anchor_pv_area_m2"]
        )
        pathway_rows.extend(city_pathway)
        meta = risk_inputs[city_id]
        pair_info = meta["unique_pv_building_pairs"]
        pair_path = Path(pair_info["path"])
        pair_artifact = city["artifacts"]["unique_pv_building_pairs"]
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
        if not math.isclose(
            host_check["resolved_host_pv_area_m2"],
            relation_check["resolved_pv_area_m2"],
            rel_tol=1e-12,
            abs_tol=1e-5,
        ):
            raise ValueError(f"{city_id}: host area does not reconcile to resolved area")
        scope_checks: dict[str, Any] = {}
        for scope in ("narrow", "full_aoi"):
            building_info = meta[f"{scope}_building"]
            building_path = Path(building_info["path"])
            print(f"  {scope}: {int(building_info['row_count']):,} Buildings", flush=True)
            input_records.append(
                input_record(
                    f"{scope}_raw_known_building_risk_table",
                    building_path,
                    expected_sha256=building_info["sha256"],
                    expected_row_count=int(building_info["row_count"]),
                    primary_key="production_building_id",
                )
            )
            scope_transitions, scope_city, distributions = estimate_scope(
                city_id, scope, building_path, meta["cohort_order"], pairs
            )
            transition_rows.extend(scope_transitions)
            city_rows.append(scope_city)
            for route, values in distributions.items():
                distribution_rows.append(
                    distribution_metrics(city_id, scope, route, values)
                )
                pooled_distributions[(scope, route)].append(values)
            scope_checks[scope] = {
                "transition_count": len(scope_transitions),
                "strict_classified_host_count": int(
                    scope_city["y_new"] + scope_city["y_retrofit"]
                ),
                "strict_classified_host_area_m2": float(
                    scope_city["pv_area_total_classified_m2"]
                ),
                "three_factor_decomposition_residual": scope_city[
                    "three_factor_decomposition_residual"
                ],
            }
        city_checks.append(
            {
                "city_id": city_id,
                "relationship_area": relation_check,
                "unique_host_area": host_check,
                "scopes": scope_checks,
            }
        )

    assert_counts_match(city_rows, args.count_city_table, transition=False)
    assert_counts_match(transition_rows, args.count_transition_table, transition=True)
    pathway_rows = aggregate_pathway_rows(pathway_rows)
    city_rows.extend(
        [
            aggregate_stock_rows(city_rows, "narrow"),
            aggregate_stock_rows(city_rows, "full_aoi"),
        ]
    )
    for (scope, route), pieces in sorted(pooled_distributions.items()):
        distribution_rows.append(
            distribution_metrics(
                "all_cities_pooled", scope, route, np.concatenate(pieces)
            )
        )

    capacity_rows = [dict(row) for row in CAPACITY_SCENARIOS]
    output_specs: list[tuple[str, list[dict[str, Any]], list[str]]] = [
        (
            "city_area_temporal_contrast.csv",
            temporal_contrast_rows,
            ["city_id"],
        ),
        (
            "city_pv_area_onset_pathway_composition.csv",
            pathway_rows,
            ["city_id", "appearance_order"],
        ),
        (
            "city_area_weighted_stock_flow.csv",
            city_rows,
            ["city_id", "scope"],
        ),
        (
            "city_transition_area_weighted_stock_flow.csv",
            transition_rows,
            ["city_id", "scope", "transition_index"],
        ),
        (
            "city_area_weighted_event_size_distribution.csv",
            distribution_rows,
            ["city_id", "scope", "route"],
        ),
        (
            "pv_area_capacity_density_scenarios.csv",
            capacity_rows,
            ["scenario_id"],
        ),
    ]
    for name, rows, _ in output_specs:
        write_csv(args.output_dir / name, rows)

    full_pooled = next(
        row
        for row in city_rows
        if row["city_id"] == "all_cities_pooled" and row["scope"] == "full_aoi"
    )
    pathway_pooled = {
        row["appearance_order"]: row
        for row in pathway_rows
        if row["city_id"] == "all_cities_pooled"
    }
    temporal_pooled = next(
        row for row in temporal_contrast_rows if row["city_id"] == "all_cities_pooled"
    )
    full_cities = [
        row for row in city_rows if row["scope"] == "full_aoi" and row["city_id"] != "all_cities_pooled"
    ]
    full_transitions = [
        row for row in transition_rows if row["scope"] == "full_aoi"
    ]
    finite_city_area_rr = [
        float(row["area_yield_rr_new_to_retrofit"])
        for row in full_cities
        if row["area_yield_rr_new_to_retrofit"] != ""
    ]
    count_area_direction_disagreement = sum(
        (float(row["count_rr_new_to_retrofit"]) > 1)
        != (float(row["area_yield_rr_new_to_retrofit"]) > 1)
        for row in full_cities
        if row["count_rr_new_to_retrofit"] != ""
        and row["area_yield_rr_new_to_retrofit"] != ""
    )
    transition_direction_disagreement = sum(
        (float(row["count_rr_new_to_retrofit"]) > 1)
        != (float(row["area_yield_rr_new_to_retrofit"]) > 1)
        for row in full_transitions
        if row["count_rr_new_to_retrofit"] != ""
        and row["area_yield_rr_new_to_retrofit"] != ""
    )
    full_area_switch_cities = 0
    for city in cities:
        finite = [
            float(row["area_yield_rr_new_to_retrofit"])
            for row in full_transitions
            if row["city_id"] == city["city_id"]
            and row["area_yield_rr_new_to_retrofit"] != ""
        ]
        if any(value > 1 for value in finite) and any(value < 1 for value in finite):
            full_area_switch_cities += 1

    summary_rows = [
        {
            "metric_id": "pooled_postbaseline_pv_area_share",
            "value": temporal_pooled["postbaseline_pv_area_share"],
            "unit": "proportion",
            "source_table": "city_area_temporal_contrast.csv",
            "definition": "Anchor PV union area entering after the left-censored baseline, pooled over city-specific area denominators.",
            "status": "REPRODUCED",
        },
        {
            "metric_id": "pooled_postbaseline_building_roof_area_share",
            "value": temporal_pooled["postbaseline_building_roof_mask_area_share"],
            "unit": "proportion",
            "source_table": "city_area_temporal_contrast.csv",
            "definition": "Canonical Building SAM3 roof-mask area entering after baseline, pooled over cities.",
            "status": "REPRODUCED",
        },
        {
            "metric_id": "resolved_pv_area_building_before_pv_share",
            "value": pathway_pooled["building_before_pv"]["share_of_resolved_pv_union_area"],
            "unit": "proportion",
            "source_table": "city_pv_area_onset_pathway_composition.csv",
            "definition": "Share of resolved canonical PV target union area whose linked Building was observed first.",
            "status": "REPRODUCED",
        },
        {
            "metric_id": "full_aoi_strict_retrofit_pv_area_share",
            "value": full_pooled["retrofit_share_of_classified_pv_area"],
            "unit": "proportion",
            "source_table": "city_area_weighted_stock_flow.csv",
            "definition": "Share of strict-classified unique-host anchor PV area attributed to existing-Building first-event routes.",
            "status": "REPRODUCED",
        },
        {
            "metric_id": "full_aoi_strict_classified_pv_area_m2",
            "value": full_pooled["pv_area_total_classified_m2"],
            "unit": "m2",
            "source_table": "city_area_weighted_stock_flow.csv",
            "definition": "Anchor PV union area on unique hosts with a strict adjacent classified first PV event.",
            "status": "REPRODUCED",
        },
        {
            "metric_id": "full_aoi_nominal_capacity_equivalent_mwdc",
            "value": full_pooled["nominal_capacity_total_mwdc_equivalent"],
            "unit": "MWdc-equivalent at 0.20 kWdc/m2",
            "source_table": "city_area_weighted_stock_flow.csv",
            "definition": "Illustrative constant-density translation; not measured nameplate capacity.",
            "status": "REPRODUCED",
        },
        {
            "metric_id": "full_aoi_area_yield_rr_new_to_retrofit",
            "value": full_pooled["area_yield_rr_new_to_retrofit"],
            "unit": "ratio",
            "source_table": "city_area_weighted_stock_flow.csv",
            "definition": "Count-pooled descriptive PV-area yield per new Building divided by yield per stock building-cohort exposure.",
            "status": "REPRODUCED",
        },
        {
            "metric_id": "full_aoi_event_size_ratio_retrofit_to_new",
            "value": full_pooled["event_size_ratio_retrofit_to_new"],
            "unit": "ratio",
            "source_table": "city_area_weighted_stock_flow.csv",
            "definition": "Mean unique-host anchor PV area on existing-route strict events divided by new-route strict events.",
            "status": "REPRODUCED",
        },
        {
            "metric_id": "full_aoi_city_area_yield_rr_below_one_count",
            "value": sum(value < 1 for value in finite_city_area_rr),
            "unit": "cities",
            "source_table": "city_area_weighted_stock_flow.csv",
            "definition": "Cities with lower PV-area yield per new-Building risk unit than per stock exposure.",
            "status": "REPRODUCED",
        },
        {
            "metric_id": "full_aoi_city_count_area_direction_disagreement",
            "value": count_area_direction_disagreement,
            "unit": "cities",
            "source_table": "city_area_weighted_stock_flow.csv",
            "definition": "Cities for which count RR and PV-area-yield RR lie on opposite sides of one.",
            "status": "REPRODUCED",
        },
        {
            "metric_id": "full_aoi_transition_count_area_direction_disagreement",
            "value": transition_direction_disagreement,
            "unit": "transitions",
            "source_table": "city_transition_area_weighted_stock_flow.csv",
            "definition": "Strict transitions for which count RR and PV-area-yield RR lie on opposite sides of one.",
            "status": "REPRODUCED",
        },
        {
            "metric_id": "full_aoi_area_direction_switch_city_count",
            "value": full_area_switch_cities,
            "unit": "cities",
            "source_table": "city_transition_area_weighted_stock_flow.csv",
            "definition": "Cities with finite area-yield ratios both above and below one across observed transitions.",
            "status": "REPRODUCED",
        },
    ]
    summary_path = args.output_dir / "area_weighted_results_summary.csv"
    write_csv(summary_path, summary_rows)
    output_specs.append((summary_path.name, summary_rows, ["metric_id"]))

    max_residual = max(
        abs(float(row["three_factor_decomposition_residual"]))
        for row in [*city_rows, *transition_rows]
        if row["three_factor_decomposition_residual"] != ""
    )
    checks = {
        "schema_version": "area-weighted-paper-results-checks-v1",
        "status": "REPRODUCED",
        "generated_at_utc": utc_now(),
        "city_count": len(cities),
        "full_aoi_transition_count": len(full_transitions),
        "canonical_pv_target_count": sum(
            check["relationship_area"]["relationship_target_count"] for check in city_checks
        ),
        "resolved_pv_target_count": sum(
            check["relationship_area"]["resolved_target_count"] for check in city_checks
        ),
        "unavailable_pv_target_count": sum(
            check["relationship_area"]["unavailable_target_count"] for check in city_checks
        ),
        "unique_paired_host_count": sum(
            check["unique_host_area"]["unique_host_count"] for check in city_checks
        ),
        "all_input_hashes_verified": all(
            row["sha256_expected"] == row["sha256_observed"] for row in input_records
        ),
        "all_input_row_counts_verified": all(
            row.get("row_count_expected") == row.get("row_count_observed")
            for row in input_records
            if "row_count_expected" in row
        ),
        "relationship_area_reconciles_to_area_trajectory": all(
            math.isclose(
                check["relationship_area"]["relationship_pv_area_m2"],
                area_totals[check["city_id"]]["anchor_pv_area_m2"],
                rel_tol=1e-12,
                abs_tol=1e-5,
            )
            for check in city_checks
        ),
        "resolved_target_area_reconciles_to_unique_host_area": all(
            math.isclose(
                check["relationship_area"]["resolved_pv_area_m2"],
                check["unique_host_area"]["resolved_host_pv_area_m2"],
                rel_tol=1e-12,
                abs_tol=1e-5,
            )
            for check in city_checks
        ),
        "source_pv_polygon_ids_unique_within_each_city": all(
            check["relationship_area"]["source_pv_polygon_ids_globally_unique_within_city"]
            for check in city_checks
        ),
        "city_and_transition_counts_reproduce_count_bundle": True,
        "maximum_absolute_three_factor_log_residual": max_residual,
        "three_factor_identity_within_1e_12": max_residual < 1e-12,
        "capacity_is_scenario_not_measured_nameplate": True,
        "host_area_attributed_to_first_strict_event_not_time_resolved_expansion": True,
        "city_checks": city_checks,
    }
    if not all(
        (
            checks["city_count"] == 15,
            checks["full_aoi_transition_count"] == 67,
            checks["canonical_pv_target_count"]
            == sum(int(city["counts"]["pv_target_count"]) for city in cities),
            checks["resolved_pv_target_count"]
            == sum(int(city["counts"]["resolved_relationship_count"]) for city in cities),
            checks["unavailable_pv_target_count"]
            == sum(int(city["counts"]["unavailable_relationship_count"]) for city in cities),
            checks["unique_paired_host_count"]
            == sum(int(city["counts"]["unique_paired_building_count"]) for city in cities),
            checks["all_input_hashes_verified"],
            checks["all_input_row_counts_verified"],
            checks["relationship_area_reconciles_to_area_trajectory"],
            checks["resolved_target_area_reconciles_to_unique_host_area"],
            checks["source_pv_polygon_ids_unique_within_each_city"],
            checks["three_factor_identity_within_1e_12"],
        )
    ):
        raise ValueError("One or more area-weighted result invariants failed")
    checks_path = args.output_dir / "area_weighted_results_checks.json"
    write_json(checks_path, checks)

    outputs: dict[str, Any] = {}
    for name, rows, primary_key in output_specs:
        path = args.output_dir / name
        outputs[path.stem] = {
            "path": str(path.resolve()),
            "sha256": sha256_file(path),
            "bytes": path.stat().st_size,
            "row_count": len(rows),
            "primary_key": primary_key,
        }
    outputs["area_weighted_results_checks"] = {
        "path": str(checks_path.resolve()),
        "sha256": sha256_file(checks_path),
        "bytes": checks_path.stat().st_size,
        "record_count": 1,
        "primary_key": [],
    }
    manifest = {
        "schema_version": "area-weighted-paper-results-manifest-v1",
        "status": "REPRODUCED",
        "generated_at_utc": utc_now(),
        "generator_script": {
            "path": str(Path(__file__).resolve()),
            "version": SCRIPT_VERSION,
            "sha256": sha256_file(Path(__file__).resolve()),
        },
        "estimands": {
            "temporal_area_composition": "PV union area and Building SAM3 roof-mask area use separate city-specific anchor-area denominators",
            "onset_pathway_area_composition": "canonical PV-target union area by its own PV onset relative to linked Building onset",
            "strict_area_stock_flow": "current anchor PV union area on a unique host, attributed to the host's first strict adjacent PV event, per new-Building or stock building-cohort risk unit",
            "three_factor_identity": "stock scale times event intensity times mean PV area per event",
            "capacity": "illustrative DC-capacity-equivalent scenarios; no measured nameplate capacity",
        },
        "filters_and_exclusions": {
            "temporal_composition": "all canonical targets; left-censored area enters baseline",
            "pathway_composition": "resolved PV targets form the denominator; unavailable relationships are separate",
            "strict_risk_panel": "raw known adjacent Building A-to-P or P-to-P; strict adjacent accepted PV A-to-P; unique host exits after first event; no U-to-A conversion or bridging",
        },
        "denominator_definitions": {
            "area_trajectory": "separate anchor PV union area and canonical Building SAM3 roof-mask area",
            "new_area_yield": "PV union square metres on strict new-route event hosts divided by newly observed Buildings",
            "retrofit_area_yield": "PV union square metres on strict existing-route event hosts divided by existing-Building cohort exposures",
            "capacity_equivalent": "area multiplied by a declared constant module power-density scenario",
        },
        "capacity_sources_accessed_utc": "2026-09-02",
        "inputs": input_records,
        "outputs": outputs,
    }
    manifest_path = args.output_dir / "area_weighted_results_manifest.json"
    write_json(manifest_path, manifest)
    print(json.dumps({
        "status": "REPRODUCED",
        "pooled_full_aoi": {
            "strict_area_m2": full_pooled["pv_area_total_classified_m2"],
            "retrofit_area_share": full_pooled["retrofit_share_of_classified_pv_area"],
            "nominal_mwdc_equivalent": full_pooled["nominal_capacity_total_mwdc_equivalent"],
            "area_yield_rr_new_to_retrofit": full_pooled["area_yield_rr_new_to_retrofit"],
            "event_size_ratio_retrofit_to_new": full_pooled["event_size_ratio_retrofit_to_new"],
        },
        "city_count_area_direction_disagreement": count_area_direction_disagreement,
        "transition_count_area_direction_disagreement": transition_direction_disagreement,
        "area_direction_switch_city_count": full_area_switch_cities,
        "manifest": str(manifest_path),
    }, indent=2), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
