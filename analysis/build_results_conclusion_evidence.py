#!/usr/bin/env python3
"""Build conclusion-oriented high-level evidence for the paper Results plan.

This script does not rebuild upstream inventories. It combines three completed,
hash-bound full-AOI raw-known risk-panel releases, re-reads canonical unique
building--PV pairs through the frozen results index, summarizes the already
REPRODUCED city trajectories, and audits readiness of the external context
tables. Outputs are aggregate reusable tables under data_high_level/.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


SCRIPT_VERSION = "1.0.0"
Z_95 = 1.959963984540054
EXPECTED_CITY_COUNT = 15
ALLOWED_APPEARANCE_ORDERS = {
    "building_before_pv",
    "same_first_present_cohort",
    "pv_before_building_conflict",
}


def parse_args() -> argparse.Namespace:
    workspace = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--index",
        type=Path,
        default=workspace / "results" / "major_results_index.json",
    )
    parser.add_argument(
        "--trajectory-table",
        type=Path,
        default=workspace / "data_high_level" / "city_pv_building_trajectories.csv",
    )
    parser.add_argument(
        "--trajectory-manifest",
        type=Path,
        default=workspace
        / "data_high_level"
        / "city_pv_building_trajectories_manifest.json",
    )
    parser.add_argument(
        "--external-coverage",
        type=Path,
        default=workspace
        / "data_external"
        / "integrated"
        / "external_attributes_v1"
        / "integration_coverage_by_city.csv",
    )
    parser.add_argument(
        "--external-manifest",
        type=Path,
        default=workspace
        / "data_external"
        / "integrated"
        / "external_attributes_v1"
        / "manifest.json",
    )
    parser.add_argument(
        "--policy-table",
        type=Path,
        default=workspace / "data_external" / "policy" / "complete" / "policies.csv",
    )
    parser.add_argument(
        "--policy-manifest",
        type=Path,
        default=workspace
        / "data_external"
        / "policy"
        / "complete"
        / "merge_manifest.json",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=workspace / "data_high_level",
    )
    parser.add_argument(
        "--risk-root",
        action="append",
        type=Path,
        default=None,
        help="Completed raw-known run root containing manifest.json and risk_panel/.",
    )
    return parser.parse_args()


def default_risk_roots() -> list[Path]:
    return [
        Path(
            "/home/ec2-user/rpv-work/runs/"
            "11-city-full-aoi-risk-panel-raw-known-v1-20260901/artifacts"
        ),
        Path(
            "/home/ec2-user/rpv-work/runs/"
            "los-angeles-full-aoi-extension-v1-20260901/artifacts/raw_known"
        ),
        Path(
            "/home/ec2-user/rpv-work/runs/"
            "chicago-seattle-detroit-full-aoi-extension-v1-20260902/"
            "artifacts/raw_known"
        ),
    ]


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def count_csv_rows(path: Path) -> int:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return max(sum(1 for _ in handle) - 1, 0)


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str] | None = None) -> None:
    if not rows:
        raise ValueError(f"Refusing to write empty table: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = fields or list(rows[0].keys())
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, sort_keys=True)
        handle.write("\n")


def as_int(value: str | int | float) -> int:
    return int(float(value))


def as_float(value: str | int | float) -> float:
    return float(value)


def parse_optional_float(value: str) -> float | None:
    value = value.strip()
    if not value:
        return None
    parsed = float(value)
    return parsed if math.isfinite(parsed) else None


def ratio_metrics(n_new: int, y_new: int, n_stock: int, y_retrofit: int) -> dict[str, Any]:
    r_new = y_new / n_new if n_new else None
    r_retrofit = y_retrofit / n_stock if n_stock else None
    rr = (
        r_new / r_retrofit
        if r_new is not None and r_retrofit not in (None, 0)
        else None
    )
    rd = (
        r_new - r_retrofit
        if r_new is not None and r_retrofit is not None
        else None
    )
    se = (
        math.sqrt((1 / y_new) - (1 / n_new) + (1 / y_retrofit) - (1 / n_stock))
        if y_new > 0 and y_retrofit > 0 and n_new > y_new and n_stock > y_retrofit
        else None
    )
    stock_multiplier = n_stock / n_new if n_new else None
    retrofit_share = (
        y_retrofit / (y_new + y_retrofit) if y_new + y_retrofit else None
    )
    contribution_ratio = y_retrofit / y_new if y_new else None
    log_stock = math.log(stock_multiplier) if stock_multiplier and stock_multiplier > 0 else None
    log_intensity = math.log(r_retrofit / r_new) if r_new and r_retrofit else None
    log_observed = math.log(contribution_ratio) if contribution_ratio and contribution_ratio > 0 else None
    decomposition_residual = (
        log_observed - log_stock - log_intensity
        if None not in (log_observed, log_stock, log_intensity)
        else None
    )
    required_new_rate = y_retrofit / n_new if n_new else None
    universal_new_share = n_new / (n_new + y_retrofit) if n_new + y_retrofit else None
    return {
        "n_new": n_new,
        "y_new": y_new,
        "n_stock": n_stock,
        "y_retrofit": y_retrofit,
        "r_new": r_new,
        "r_retrofit": r_retrofit,
        "rr": rr,
        "rd": rd,
        "log_rr_wald_se": se,
        "rr_wald_95_lower": math.exp(math.log(rr) - Z_95 * se) if rr and se else None,
        "rr_wald_95_upper": math.exp(math.log(rr) + Z_95 * se) if rr and se else None,
        "stock_multiplier": stock_multiplier,
        "retrofit_composition_share": retrofit_share,
        "retrofit_to_new_contribution_ratio": contribution_ratio,
        "log_stock_size_contribution": log_stock,
        "log_intensity_contribution": log_intensity,
        "log_observed_contribution_ratio": log_observed,
        "decomposition_residual": decomposition_residual,
        "new_event_proportion_required_for_route_parity": required_new_rate,
        "route_parity_feasible_at_100pct_new": (
            required_new_rate <= 1 if required_new_rate is not None else None
        ),
        "new_route_share_if_all_new_buildings_had_observed_pv": universal_new_share,
    }


def validate_and_read_risk_runs(
    roots: list[Path],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    city_rows: list[dict[str, Any]] = []
    transition_rows: list[dict[str, Any]] = []
    input_records: list[dict[str, Any]] = []
    seen_cities: set[tuple[str, str]] = set()
    for root in roots:
        manifest_path = root / "manifest.json"
        qa_path = root / "qa" / "final_qa.json"
        city_path = root / "risk_panel" / "city_estimates.csv"
        transition_path = root / "risk_panel" / "city_transition_estimates.csv"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        qa = json.loads(qa_path.read_text(encoding="utf-8"))
        if manifest.get("status") != "complete" or qa.get("status") != "pass":
            raise ValueError(f"Risk release is not complete/pass: {root}")
        declared_outputs = manifest.get("outputs", {})
        for relative, path in (
            ("risk_panel/city_estimates.csv", city_path),
            ("risk_panel/city_transition_estimates.csv", transition_path),
            ("qa/final_qa.json", qa_path),
        ):
            observed = sha256_file(path)
            expected = declared_outputs.get(relative, {}).get("sha256")
            if expected and observed != expected:
                raise ValueError(f"Risk release hash mismatch: {path}")
        for row in read_csv(city_path):
            key = (row["city_id"], row["scope"])
            if key in seen_cities:
                raise ValueError(f"Duplicate city/scope across risk releases: {key}")
            seen_cities.add(key)
            parsed: dict[str, Any] = {
                "city_id": row["city_id"],
                "scope": row["scope"],
                "cohort_count": as_int(row["cohort_count"]),
                "transition_count": as_int(row["transition_count"]),
                "building_identity_count": as_int(row["building_identity_count"]),
                "pv_paired_building_count": as_int(row["pv_paired_building_count"]),
            }
            for field in (
                "n_new",
                "y_new",
                "n_stock",
                "y_retrofit",
            ):
                parsed[field] = as_int(row[field])
            parsed.update(ratio_metrics(
                parsed["n_new"], parsed["y_new"], parsed["n_stock"], parsed["y_retrofit"]
            ))
            parsed.update(
                {
                    "estimand": (
                        "strict adjacent raw-known Building A-to-P new risk versus "
                        "raw-known Building P-to-P stock risk, with strict adjacent "
                        "linked PV A-to-P events"
                    ),
                    "target_population": (
                        "full Anchor AOI Buildings or narrow candidate-scope Buildings, "
                        "with anchor-surviving accepted linked PV"
                    ),
                    "status": "REPRODUCED",
                }
            )
            city_rows.append(parsed)
        for row in read_csv(transition_path):
            parsed = {
                "city_id": row["city_id"],
                "scope": row["scope"],
                "transition_index": as_int(row["transition_index"]),
                "previous_cohort": row["previous_cohort"],
                "current_cohort": row["current_cohort"],
            }
            for field in ("n_new", "y_new", "n_stock", "y_retrofit"):
                parsed[field] = as_int(row[field])
            parsed.update(ratio_metrics(
                parsed["n_new"], parsed["y_new"], parsed["n_stock"], parsed["y_retrofit"]
            ))
            rr = parsed["rr"]
            parsed.update(
                {
                    "intensity_direction": (
                        "new_higher"
                        if rr is not None and rr > 1
                        else "existing_higher"
                        if rr is not None and rr < 1
                        else "equal_or_inestimable"
                    ),
                    "both_routes_have_events": parsed["y_new"] > 0 and parsed["y_retrofit"] > 0,
                    "total_strict_events": parsed["y_new"] + parsed["y_retrofit"],
                    "time_unit_warning": "ordered cohort transition; not an annual hazard",
                    "status": "REPRODUCED",
                }
            )
            transition_rows.append(parsed)
        input_records.append(
            {
                "input_role": "completed_full_aoi_raw_known_risk_release",
                "path": str(manifest_path.resolve()),
                "sha256": sha256_file(manifest_path),
                "status": manifest["status"],
                "qa_path": str(qa_path.resolve()),
                "qa_sha256": sha256_file(qa_path),
                "city_estimates_path": str(city_path.resolve()),
                "city_estimates_sha256": sha256_file(city_path),
                "city_estimates_row_count": count_csv_rows(city_path),
                "transition_estimates_path": str(transition_path.resolve()),
                "transition_estimates_sha256": sha256_file(transition_path),
                "transition_estimates_row_count": count_csv_rows(transition_path),
            }
        )
    if len({row["city_id"] for row in city_rows}) != EXPECTED_CITY_COUNT:
        raise ValueError("Risk releases do not cover exactly 15 unique cities")
    for city_id in {row["city_id"] for row in city_rows}:
        scopes = {row["scope"] for row in city_rows if row["city_id"] == city_id}
        if scopes != {"narrow", "full_aoi"}:
            raise ValueError(f"Incomplete scopes for {city_id}: {scopes}")
    return city_rows, transition_rows, input_records


def add_pooled_rows(city_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    output = list(city_rows)
    for scope in ("narrow", "full_aoi"):
        selected = [row for row in city_rows if row["scope"] == scope]
        pooled = {
            "city_id": "all_cities_pooled",
            "scope": scope,
            "cohort_count": sum(row["cohort_count"] for row in selected),
            "transition_count": sum(row["transition_count"] for row in selected),
            "building_identity_count": sum(row["building_identity_count"] for row in selected),
            "pv_paired_building_count": sum(row["pv_paired_building_count"] for row in selected),
        }
        counts = [
            sum(row[field] for row in selected)
            for field in ("n_new", "y_new", "n_stock", "y_retrofit")
        ]
        pooled.update(ratio_metrics(*counts))
        pooled.update(
            {
                "estimand": (
                    "descriptive count-pooled strict adjacent raw-known contrast; "
                    "not the cross-city primary synthesis"
                ),
                "target_population": (
                    "pooled city-specific full Anchor AOI or narrow candidate scopes, "
                    "with anchor-surviving accepted linked PV"
                ),
                "status": "REPRODUCED",
            }
        )
        output.append(pooled)
    return output


def summarize_route_stability(
    transition_rows: list[dict[str, Any]], city_rows: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    city_lookup = {
        (row["city_id"], row["scope"]): row
        for row in city_rows
        if row["city_id"] != "all_cities_pooled"
    }
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in transition_rows:
        grouped[(row["city_id"], row["scope"])].append(row)
    output: list[dict[str, Any]] = []
    for (city_id, scope), rows in sorted(grouped.items()):
        rows.sort(key=lambda item: item["transition_index"])
        new_higher = sum(row["intensity_direction"] == "new_higher" for row in rows)
        existing_higher = sum(row["intensity_direction"] == "existing_higher" for row in rows)
        city = city_lookup[(city_id, scope)]
        aggregate_direction = (
            "new_higher" if city["rr"] > 1 else "existing_higher" if city["rr"] < 1 else "equal"
        )
        majority_direction = (
            "new_higher"
            if new_higher > existing_higher
            else "existing_higher"
            if existing_higher > new_higher
            else "tied"
        )
        total_events = sum(row["total_strict_events"] for row in rows)
        largest = max(rows, key=lambda row: row["total_strict_events"])
        output.append(
            {
                "city_id": city_id,
                "scope": scope,
                "transition_count": len(rows),
                "new_higher_transition_count": new_higher,
                "existing_higher_transition_count": existing_higher,
                "direction_switch_observed": new_higher > 0 and existing_higher > 0,
                "first_transition_direction": rows[0]["intensity_direction"],
                "last_transition_direction": rows[-1]["intensity_direction"],
                "transition_majority_direction": majority_direction,
                "city_aggregate_direction": aggregate_direction,
                "aggregate_differs_from_transition_majority": (
                    majority_direction != "tied" and majority_direction != aggregate_direction
                ),
                "total_strict_events": total_events,
                "largest_event_transition_index": largest["transition_index"],
                "largest_event_transition_label": (
                    f"{largest['previous_cohort']}->{largest['current_cohort']}"
                ),
                "largest_transition_share_of_strict_events": (
                    largest["total_strict_events"] / total_events if total_events else None
                ),
                "scope_warning": (
                    "descriptive transition direction; cohort intervals differ in duration "
                    "and sparse cells are retained"
                ),
                "status": "REPRODUCED",
            }
        )
    return output


def random_effects_dl(city_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    selected = [
        row for row in city_rows
        if row["scope"] == "full_aoi" and row["city_id"] != "all_cities_pooled"
    ]
    effects = [math.log(row["rr"]) for row in selected]
    variances = [row["log_rr_wald_se"] ** 2 for row in selected]
    weights = [1 / variance for variance in variances]
    fixed_mean = sum(w * y for w, y in zip(weights, effects)) / sum(weights)
    fixed_se = math.sqrt(1 / sum(weights))
    q = sum(w * (y - fixed_mean) ** 2 for w, y in zip(weights, effects))
    df = len(effects) - 1
    c_value = sum(weights) - sum(w * w for w in weights) / sum(weights)
    tau2 = max(0.0, (q - df) / c_value)
    random_weights = [1 / (variance + tau2) for variance in variances]
    random_mean = (
        sum(w * y for w, y in zip(random_weights, effects)) / sum(random_weights)
    )
    random_se = math.sqrt(1 / sum(random_weights))
    prediction_se = math.sqrt(tau2 + random_se**2)
    i2 = max(0.0, (q - df) / q) if q else 0.0
    common = {
        "scope": "full_aoi",
        "city_count": len(selected),
        "variance_source": "descriptive unclustered city Wald log-RR variance",
        "time_unit_warning": "per observed cohort transition; intervals differ in duration",
        "status": "REPRODUCED",
    }
    return [
        {
            "model": "fixed_effect_inverse_variance",
            **common,
            "mean_log_rr": fixed_mean,
            "mean_rr": math.exp(fixed_mean),
            "mean_rr_95_lower": math.exp(fixed_mean - Z_95 * fixed_se),
            "mean_rr_95_upper": math.exp(fixed_mean + Z_95 * fixed_se),
            "prediction_95_lower": "",
            "prediction_95_upper": "",
            "tau_squared": 0.0,
            "q": q,
            "degrees_of_freedom": df,
            "i_squared": i2,
        },
        {
            "model": "random_effects_der_simonian_laird",
            **common,
            "mean_log_rr": random_mean,
            "mean_rr": math.exp(random_mean),
            "mean_rr_95_lower": math.exp(random_mean - Z_95 * random_se),
            "mean_rr_95_upper": math.exp(random_mean + Z_95 * random_se),
            "prediction_95_lower": math.exp(random_mean - Z_95 * prediction_se),
            "prediction_95_upper": math.exp(random_mean + Z_95 * prediction_se),
            "tau_squared": tau2,
            "q": q,
            "degrees_of_freedom": df,
            "i_squared": i2,
        },
    ]


def leave_one_city_out_meta(city_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    selected = [
        row for row in city_rows
        if row["scope"] == "full_aoi" and row["city_id"] != "all_cities_pooled"
    ]
    output: list[dict[str, Any]] = []
    for omitted in sorted(row["city_id"] for row in selected):
        retained = [row for row in selected if row["city_id"] != omitted]
        random_row = next(
            row
            for row in random_effects_dl(retained)
            if row["model"] == "random_effects_der_simonian_laird"
        )
        output.append(
            {
                "omitted_city_id": omitted,
                "retained_city_count": random_row["city_count"],
                "mean_rr": random_row["mean_rr"],
                "mean_rr_95_lower": random_row["mean_rr_95_lower"],
                "mean_rr_95_upper": random_row["mean_rr_95_upper"],
                "prediction_95_lower": random_row["prediction_95_lower"],
                "prediction_95_upper": random_row["prediction_95_upper"],
                "tau_squared": random_row["tau_squared"],
                "i_squared": random_row["i_squared"],
                "variance_source": random_row["variance_source"],
                "status": "REPRODUCED",
            }
        )
    return output


def weighted_quantile(counter: Counter[int], quantile: float) -> int:
    total = sum(counter.values())
    if total <= 0:
        raise ValueError("Cannot compute weighted quantile of empty distribution")
    threshold = quantile * total
    cumulative = 0
    for value in sorted(counter):
        cumulative += counter[value]
        if cumulative >= threshold:
            return value
    return max(counter)


def canonical_pair_summaries(
    index: dict[str, Any]
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    pathway_rows: list[dict[str, Any]] = []
    lag_rows: list[dict[str, Any]] = []
    separation_rows: list[dict[str, Any]] = []
    input_records: list[dict[str, Any]] = []
    all_orders: Counter[str] = Counter()
    all_lags: Counter[int] = Counter()
    all_unique = 0
    all_unavailable = 0
    for city in index["cities"]:
        city_id = city["city_id"]
        city_name = city["city_name"]
        artifact = city["artifacts"]["unique_pv_building_pairs"]
        path = Path(artifact["path"])
        observed_hash = sha256_file(path)
        if observed_hash != artifact["sha256"]:
            raise ValueError(f"Canonical pair hash mismatch: {city_id}")
        order_counts: Counter[str] = Counter()
        lag_counts: Counter[int] = Counter()
        seen: set[str] = set()
        with path.open("r", encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle)
            required = {
                "production_building_id",
                "pv_minus_building_onset_cohort_steps",
                "appearance_order",
            }
            if not required.issubset(set(reader.fieldnames or [])):
                raise ValueError(f"Canonical pair schema mismatch: {city_id}")
            for row in reader:
                identity = row["production_building_id"]
                if identity in seen:
                    raise ValueError(f"Duplicate canonical paired building: {city_id}/{identity}")
                seen.add(identity)
                appearance = row["appearance_order"]
                if appearance not in ALLOWED_APPEARANCE_ORDERS:
                    raise ValueError(f"Unexpected appearance order: {city_id}/{appearance}")
                lag = int(row["pv_minus_building_onset_cohort_steps"])
                expected = (
                    "building_before_pv" if lag > 0 else "same_first_present_cohort" if lag == 0 else "pv_before_building_conflict"
                )
                if appearance != expected:
                    raise ValueError(f"Lag/order mismatch: {city_id}/{identity}")
                order_counts[appearance] += 1
                lag_counts[lag] += 1
        if len(seen) != artifact["row_count"]:
            raise ValueError(f"Canonical pair row-count mismatch: {city_id}")
        total = len(seen)
        unavailable = city["counts"]["unavailable_relationship_count"]
        for appearance in sorted(ALLOWED_APPEARANCE_ORDERS):
            count = order_counts[appearance]
            pathway_rows.append(
                {
                    "city_id": city_id,
                    "city_name": city_name,
                    "unit": "unique_paired_building",
                    "appearance_order": appearance,
                    "count": count,
                    "share_of_unique_paired_buildings": count / total if total else None,
                    "unique_paired_building_denominator": total,
                    "unavailable_relationship_count_separate_unit": unavailable,
                    "status": "REPRODUCED",
                }
            )
        for lag, count in sorted(lag_counts.items()):
            lag_rows.append(
                {
                    "city_id": city_id,
                    "city_name": city_name,
                    "pv_minus_building_onset_cohort_steps": lag,
                    "appearance_order": (
                        "building_before_pv" if lag > 0 else "same_first_present_cohort" if lag == 0 else "pv_before_building_conflict"
                    ),
                    "unique_paired_building_count": count,
                    "share_of_unique_paired_buildings": count / total if total else None,
                    "time_unit_warning": "cohort steps, not years",
                    "status": "REPRODUCED",
                }
            )
        positive = Counter({lag: count for lag, count in lag_counts.items() if lag > 0})
        separation_rows.append(
            {
                "city_id": city_id,
                "city_name": city_name,
                "unique_paired_building_count": total,
                "building_before_pv_count": order_counts["building_before_pv"],
                "cohort_contemporaneous_count": order_counts["same_first_present_cohort"],
                "temporal_conflict_count": order_counts["pv_before_building_conflict"],
                "median_positive_onset_step_separation": weighted_quantile(positive, 0.5) if positive else "",
                "share_positive_separation_at_least_two_steps": (
                    sum(count for lag, count in positive.items() if lag >= 2) / sum(positive.values())
                    if positive else ""
                ),
                "time_unit_warning": "cohort steps, not years",
                "status": "REPRODUCED",
            }
        )
        all_orders.update(order_counts)
        all_lags.update(lag_counts)
        all_unique += total
        all_unavailable += unavailable
        input_records.append(
            {
                "input_role": "canonical_unique_pv_building_pairs",
                "city_id": city_id,
                "path": str(path.resolve()),
                "sha256": observed_hash,
                "row_count": total,
                "primary_key": "production_building_id",
                "release_manifest_path": city["release_manifest"]["path"],
                "release_manifest_sha256": city["release_manifest"]["sha256"],
            }
        )
    for appearance in sorted(ALLOWED_APPEARANCE_ORDERS):
        count = all_orders[appearance]
        pathway_rows.append(
            {
                "city_id": "all_cities",
                "city_name": "All cities",
                "unit": "unique_paired_building",
                "appearance_order": appearance,
                "count": count,
                "share_of_unique_paired_buildings": count / all_unique,
                "unique_paired_building_denominator": all_unique,
                "unavailable_relationship_count_separate_unit": all_unavailable,
                "status": "REPRODUCED",
            }
        )
    for lag, count in sorted(all_lags.items()):
        lag_rows.append(
            {
                "city_id": "all_cities",
                "city_name": "All cities",
                "pv_minus_building_onset_cohort_steps": lag,
                "appearance_order": (
                    "building_before_pv" if lag > 0 else "same_first_present_cohort" if lag == 0 else "pv_before_building_conflict"
                ),
                "unique_paired_building_count": count,
                "share_of_unique_paired_buildings": count / all_unique,
                "time_unit_warning": "cohort steps, not years",
                "status": "REPRODUCED",
            }
        )
    positive = Counter({lag: count for lag, count in all_lags.items() if lag > 0})
    separation_rows.append(
        {
            "city_id": "all_cities",
            "city_name": "All cities",
            "unique_paired_building_count": all_unique,
            "building_before_pv_count": all_orders["building_before_pv"],
            "cohort_contemporaneous_count": all_orders["same_first_present_cohort"],
            "temporal_conflict_count": all_orders["pv_before_building_conflict"],
            "median_positive_onset_step_separation": weighted_quantile(positive, 0.5),
            "share_positive_separation_at_least_two_steps": sum(
                count for lag, count in positive.items() if lag >= 2
            )
            / sum(positive.values()),
            "time_unit_warning": "cohort steps, not years",
            "status": "REPRODUCED",
        }
    )
    if all_unique != index["totals"]["unique_paired_building_count"]:
        raise ValueError("All-city canonical unique-pair count does not reconcile")
    return pathway_rows, lag_rows, separation_rows, input_records


def trajectory_contrasts(path: Path) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in read_csv(path):
        grouped[row["city_id"]].append(row)
    output: list[dict[str, Any]] = []
    pooled = {
        "anchor_pv": 0,
        "baseline_pv": 0,
        "anchor_buildings": 0,
        "baseline_buildings": 0,
    }
    for city_id, rows in sorted(grouped.items()):
        rows.sort(key=lambda row: int(row["calendar_year"]))
        first = rows[0]
        last = rows[-1]
        if last["is_anchor_year"].lower() != "true":
            raise ValueError(f"Trajectory missing anchor row: {city_id}")
        anchor_pv = as_int(first["anchor_pv_targets"])
        baseline_pv = as_int(first["left_censored_baseline_pv_targets"])
        anchor_buildings = as_int(first["anchor_buildings"])
        baseline_buildings = as_int(first["left_censored_baseline_buildings"])
        pv_post = 1 - baseline_pv / anchor_pv
        building_post = 1 - baseline_buildings / anchor_buildings
        output.append(
            {
                "city_id": city_id,
                "city_name": first["city_name"],
                "baseline_calendar_year": first["calendar_year"],
                "anchor_calendar_year": last["calendar_year"],
                "anchor_pv_target_count": anchor_pv,
                "left_censored_baseline_pv_target_count": baseline_pv,
                "postbaseline_pv_target_share": pv_post,
                "anchor_building_target_count": anchor_buildings,
                "left_censored_baseline_building_target_count": baseline_buildings,
                "postbaseline_building_target_share": building_post,
                "postbaseline_share_gap_pv_minus_building": pv_post - building_post,
                "interpretation": (
                    "relative temporal composition of separate anchor inventories; "
                    "not PV prevalence and not an annual event rate"
                ),
                "status": "REPRODUCED",
            }
        )
        pooled["anchor_pv"] += anchor_pv
        pooled["baseline_pv"] += baseline_pv
        pooled["anchor_buildings"] += anchor_buildings
        pooled["baseline_buildings"] += baseline_buildings
    pv_post = 1 - pooled["baseline_pv"] / pooled["anchor_pv"]
    building_post = 1 - pooled["baseline_buildings"] / pooled["anchor_buildings"]
    output.append(
        {
            "city_id": "all_cities_pooled",
            "city_name": "All cities (target-count pooled)",
            "baseline_calendar_year": "city-specific",
            "anchor_calendar_year": "city-specific",
            "anchor_pv_target_count": pooled["anchor_pv"],
            "left_censored_baseline_pv_target_count": pooled["baseline_pv"],
            "postbaseline_pv_target_share": pv_post,
            "anchor_building_target_count": pooled["anchor_buildings"],
            "left_censored_baseline_building_target_count": pooled["baseline_buildings"],
            "postbaseline_building_target_share": building_post,
            "postbaseline_share_gap_pv_minus_building": pv_post - building_post,
            "interpretation": (
                "target-count pooled relative temporal composition of separate anchor "
                "inventories; not PV prevalence and not an annual event rate"
            ),
            "status": "REPRODUCED",
        }
    )
    return output


def audit_external_readiness(
    coverage_path: Path, policy_path: Path
) -> list[dict[str, Any]]:
    coverage = {row["city_id"]: row for row in read_csv(coverage_path)}
    policies: dict[str, Counter[str]] = defaultdict(Counter)
    date_pattern = re.compile(r"^\d{4}(?:-\d{2})?(?:-\d{2})?$")
    for row in read_csv(policy_path):
        city_id = row["study_city_id"]
        policies[city_id]["policy_record_count"] += 1
        if row["effective_date"].strip():
            policies[city_id]["effective_date_nonblank_count"] += 1
            if date_pattern.match(row["effective_date"].strip()):
                policies[city_id]["effective_date_machine_parseable_count"] += 1
        if row["review_required"].strip().lower() == "true":
            policies[city_id]["review_required_count"] += 1
    output: list[dict[str, Any]] = []
    for city_id, row in sorted(coverage.items()):
        building_count = as_int(row["building_count"])
        exact_linked = as_int(row["exact_linked_building_count"])
        output.append(
            {
                "city_id": city_id,
                "building_context_row_count": building_count,
                "specific_building_category_share": as_int(row["specific_building_category_count"]) / building_count,
                "official_match_share": as_int(row["official_match_count"]) / building_count,
                "zoning_match_share": as_int(row["zoning_match_count"]) / building_count,
                "exact_external_attribute_link_share": exact_linked / building_count,
                "linkage_status": row["linkage_status"],
                "external_year_built_record_count": as_int(row["external_year_built_count"]),
                "external_building_type_record_count": as_int(row["external_building_type_count"]),
                "policy_record_count": policies[city_id]["policy_record_count"],
                "policy_effective_date_nonblank_count": policies[city_id]["effective_date_nonblank_count"],
                "policy_effective_date_machine_parseable_count": policies[city_id]["effective_date_machine_parseable_count"],
                "policy_review_required_count": policies[city_id]["review_required_count"],
                "main_text_context_result_gate": "NOT_PASSED",
                "gate_reason": (
                    "No released cross-city context-to-strict-risk-panel join and model; "
                    "exact external linkage is available for only a subset of cities"
                ),
                "status": "REPRODUCED",
            }
        )
    return output


def conclusion_summary(
    stock_rows: list[dict[str, Any]],
    pathway_rows: list[dict[str, Any]],
    separation_rows: list[dict[str, Any]],
    stability_rows: list[dict[str, Any]],
    meta_rows: list[dict[str, Any]],
    trajectory_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    full_city = [
        row for row in stock_rows
        if row["scope"] == "full_aoi" and row["city_id"] != "all_cities_pooled"
    ]
    full_pooled = next(
        row for row in stock_rows
        if row["scope"] == "full_aoi" and row["city_id"] == "all_cities_pooled"
    )
    all_paths = {
        row["appearance_order"]: row
        for row in pathway_rows
        if row["city_id"] == "all_cities"
    }
    all_separation = next(row for row in separation_rows if row["city_id"] == "all_cities")
    random_meta = next(
        row for row in meta_rows if row["model"] == "random_effects_der_simonian_laird"
    )
    full_stability = [row for row in stability_rows if row["scope"] == "full_aoi"]
    pooled_trajectory = next(
        row for row in trajectory_rows if row["city_id"] == "all_cities_pooled"
    )
    metrics: list[tuple[str, Any, str, str, str]] = [
        (
            "unique_paired_building_before_pv_share",
            all_paths["building_before_pv"]["share_of_unique_paired_buildings"],
            "proportion",
            "city_onset_pathway_composition.csv",
            "Unique paired buildings; composition, not propensity.",
        ),
        (
            "median_positive_onset_separation_steps",
            all_separation["median_positive_onset_step_separation"],
            "cohort_steps",
            "city_temporal_separation_summary.csv",
            "Ordered observation steps, not years.",
        ),
        (
            "pooled_full_aoi_retrofit_event_share",
            full_pooled["retrofit_composition_share"],
            "proportion",
            "city_stock_flow_decomposition.csv",
            "Strict adjacent events in full Anchor AOI risk panels.",
        ),
        (
            "pooled_full_aoi_stock_multiplier",
            full_pooled["stock_multiplier"],
            "ratio",
            "city_stock_flow_decomposition.csv",
            "Building-cohort stock exposures divided by newly observed buildings.",
        ),
        (
            "pooled_full_aoi_crude_rr",
            full_pooled["rr"],
            "risk_ratio",
            "city_stock_flow_decomposition.csv",
            "Count-pooled descriptive RR; not the cross-city primary synthesis.",
        ),
        (
            "city_rr_below_one_count",
            sum(row["rr"] < 1 for row in full_city),
            "cities",
            "city_stock_flow_decomposition.csv",
            "Full-AOI descriptive raw-known RR.",
        ),
        (
            "city_rr_above_one_count",
            sum(row["rr"] > 1 for row in full_city),
            "cities",
            "city_stock_flow_decomposition.csv",
            "Full-AOI descriptive raw-known RR.",
        ),
        (
            "random_effects_prediction_lower",
            random_meta["prediction_95_lower"],
            "risk_ratio",
            "cross_city_descriptive_meta_analysis.csv",
            "DL synthesis using unclustered descriptive city Wald variances.",
        ),
        (
            "random_effects_prediction_upper",
            random_meta["prediction_95_upper"],
            "risk_ratio",
            "cross_city_descriptive_meta_analysis.csv",
            "DL synthesis using unclustered descriptive city Wald variances.",
        ),
        (
            "cities_with_transition_direction_switch",
            sum(row["direction_switch_observed"] for row in full_stability),
            "cities",
            "city_route_stability.csv",
            "Across all finite ordered transition estimates; sparse cells retained.",
        ),
        (
            "cities_where_100pct_new_route_cannot_match_observed_retrofit_events",
            sum(not row["route_parity_feasible_at_100pct_new"] for row in full_city),
            "cities",
            "city_stock_flow_decomposition.csv",
            "Transparent arithmetic frontier, not a policy effect.",
        ),
        (
            "pooled_postbaseline_pv_share",
            pooled_trajectory["postbaseline_pv_target_share"],
            "proportion",
            "city_inventory_temporal_contrast.csv",
            "Temporal composition of anchor-surviving PV targets.",
        ),
        (
            "pooled_postbaseline_building_share",
            pooled_trajectory["postbaseline_building_target_share"],
            "proportion",
            "city_inventory_temporal_contrast.csv",
            "Temporal composition of in-scope building targets.",
        ),
    ]
    return [
        {
            "metric_id": metric,
            "value": value,
            "unit": unit,
            "source_table": source,
            "interpretive_boundary": boundary,
            "status": "REPRODUCED",
        }
        for metric, value, unit, source, boundary in metrics
    ]


def output_record(path: Path, primary_key: list[str]) -> dict[str, Any]:
    record = {
        "path": str(path.resolve()),
        "sha256": sha256_file(path),
        "bytes": path.stat().st_size,
        "primary_key": primary_key,
    }
    if path.suffix.lower() == ".csv":
        record["row_count"] = count_csv_rows(path)
    else:
        record["record_count"] = 1
    return record


def assert_unique(rows: Iterable[dict[str, Any]], fields: tuple[str, ...], label: str) -> None:
    seen: set[tuple[Any, ...]] = set()
    for row in rows:
        key = tuple(row[field] for field in fields)
        if key in seen:
            raise ValueError(f"Duplicate primary key in {label}: {key}")
        seen.add(key)


def main() -> None:
    args = parse_args()
    risk_roots = args.risk_root or default_risk_roots()
    index_path = args.index.resolve()
    index = json.loads(index_path.read_text(encoding="utf-8"))
    if index.get("status") != "complete" or index.get("city_count") != EXPECTED_CITY_COUNT:
        raise ValueError("Frozen major-results index is not complete for 15 cities")
    if not index.get("all_release_evidence_complete"):
        raise ValueError("Frozen index reports incomplete release evidence")
    trajectory_manifest = json.loads(args.trajectory_manifest.read_text(encoding="utf-8"))
    if trajectory_manifest.get("status") != "REPRODUCED":
        raise ValueError("Trajectory source table is not REPRODUCED")
    external_manifest = json.loads(args.external_manifest.read_text(encoding="utf-8"))
    if external_manifest.get("status") != "pass":
        raise ValueError("External attribute integration manifest is not pass")
    policy_manifest = json.loads(args.policy_manifest.read_text(encoding="utf-8"))
    if policy_manifest.get("status") not in {"complete", "pass"}:
        raise ValueError("Policy merge manifest is not complete/pass")

    city_rows, transition_rows, risk_inputs = validate_and_read_risk_runs(risk_roots)
    stock_rows = add_pooled_rows(city_rows)
    stability_rows = summarize_route_stability(transition_rows, stock_rows)
    meta_rows = random_effects_dl(stock_rows)
    meta_loo_rows = leave_one_city_out_meta(stock_rows)
    pathway_rows, lag_rows, separation_rows, pair_inputs = canonical_pair_summaries(index)
    trajectory_rows = trajectory_contrasts(args.trajectory_table)
    external_rows = audit_external_readiness(args.external_coverage, args.policy_table)
    summary_rows = conclusion_summary(
        stock_rows,
        pathway_rows,
        separation_rows,
        stability_rows,
        meta_rows,
        trajectory_rows,
    )

    assert_unique(stock_rows, ("city_id", "scope"), "stock flow")
    assert_unique(transition_rows, ("city_id", "scope", "transition_index"), "transitions")
    assert_unique(stability_rows, ("city_id", "scope"), "route stability")
    assert_unique(pathway_rows, ("city_id", "appearance_order"), "pathways")
    assert_unique(lag_rows, ("city_id", "pv_minus_building_onset_cohort_steps"), "lag distribution")
    assert_unique(separation_rows, ("city_id",), "separation summary")
    assert_unique(trajectory_rows, ("city_id",), "trajectory contrast")
    assert_unique(external_rows, ("city_id",), "external readiness")
    assert_unique(summary_rows, ("metric_id",), "conclusion summary")
    assert_unique(meta_loo_rows, ("omitted_city_id",), "leave-one-city-out meta-analysis")

    full_cities = [
        row for row in stock_rows
        if row["scope"] == "full_aoi" and row["city_id"] != "all_cities_pooled"
    ]
    decomposition_max = max(abs(row["decomposition_residual"]) for row in stock_rows)
    trajectory_ids = {row["city_id"] for row in trajectory_rows if row["city_id"] != "all_cities_pooled"}
    index_ids = {city["city_id"] for city in index["cities"]}
    risk_ids = {row["city_id"] for row in full_cities}
    if trajectory_ids != index_ids or risk_ids != index_ids:
        raise ValueError("City identity sets disagree among index/risk/trajectory inputs")

    paths = {
        "stock": args.output_dir / "city_stock_flow_decomposition.csv",
        "transition": args.output_dir / "city_transition_route_dynamics.csv",
        "stability": args.output_dir / "city_route_stability.csv",
        "meta": args.output_dir / "cross_city_descriptive_meta_analysis.csv",
        "meta_loo": args.output_dir / "cross_city_descriptive_meta_leave_one_out.csv",
        "pathway": args.output_dir / "city_onset_pathway_composition.csv",
        "lag": args.output_dir / "city_onset_step_distribution.csv",
        "separation": args.output_dir / "city_temporal_separation_summary.csv",
        "trajectory": args.output_dir / "city_inventory_temporal_contrast.csv",
        "external": args.output_dir / "context_evidence_readiness.csv",
        "summary": args.output_dir / "results_conclusion_summary.csv",
        "checks": args.output_dir / "results_conclusion_evidence_checks.json",
        "manifest": args.output_dir / "results_conclusion_evidence_manifest.json",
    }
    write_csv(paths["stock"], stock_rows)
    write_csv(paths["transition"], transition_rows)
    write_csv(paths["stability"], stability_rows)
    write_csv(paths["meta"], meta_rows)
    write_csv(paths["meta_loo"], meta_loo_rows)
    write_csv(paths["pathway"], pathway_rows)
    write_csv(paths["lag"], lag_rows)
    write_csv(paths["separation"], separation_rows)
    write_csv(paths["trajectory"], trajectory_rows)
    write_csv(paths["external"], external_rows)
    write_csv(paths["summary"], summary_rows)

    pooled_full = next(
        row for row in stock_rows
        if row["city_id"] == "all_cities_pooled" and row["scope"] == "full_aoi"
    )
    checks = {
        "schema_version": "results-conclusion-evidence-checks/v1",
        "status": "pass",
        "generated_at_utc": utc_now(),
        "checks": {
            "frozen_index_complete": True,
            "all_15_cities_present_in_every_primary_input": True,
            "all_risk_release_manifests_complete_and_qa_pass": True,
            "all_risk_release_output_hashes_match": True,
            "canonical_unique_pair_hashes_match_frozen_index": True,
            "canonical_unique_pair_primary_keys_unique": True,
            "canonical_unique_pairs_reconcile_to_frozen_total": True,
            "city_counts_reconcile_to_transition_counts": all(
                row["n_new"]
                == sum(
                    t["n_new"]
                    for t in transition_rows
                    if t["city_id"] == row["city_id"] and t["scope"] == row["scope"]
                )
                and row["y_new"]
                == sum(
                    t["y_new"]
                    for t in transition_rows
                    if t["city_id"] == row["city_id"] and t["scope"] == row["scope"]
                )
                and row["n_stock"]
                == sum(
                    t["n_stock"]
                    for t in transition_rows
                    if t["city_id"] == row["city_id"] and t["scope"] == row["scope"]
                )
                and row["y_retrofit"]
                == sum(
                    t["y_retrofit"]
                    for t in transition_rows
                    if t["city_id"] == row["city_id"] and t["scope"] == row["scope"]
                )
                for row in city_rows
            ),
            "pooled_full_aoi_counts_reconcile": (
                pooled_full["n_new"] == sum(row["n_new"] for row in full_cities)
                and pooled_full["y_new"] == sum(row["y_new"] for row in full_cities)
                and pooled_full["n_stock"] == sum(row["n_stock"] for row in full_cities)
                and pooled_full["y_retrofit"] == sum(row["y_retrofit"] for row in full_cities)
            ),
            "stock_flow_identity_max_abs_residual_below_1e_12": decomposition_max < 1e-12,
            "trajectory_source_manifest_reproduced": True,
            "external_attribute_manifest_pass": True,
            "external_context_main_text_gate_intentionally_not_passed": all(
                row["main_text_context_result_gate"] == "NOT_PASSED" for row in external_rows
            ),
        },
        "diagnostics": {
            "max_abs_stock_flow_decomposition_residual": decomposition_max,
            "full_aoi_city_count": len(full_cities),
            "full_aoi_transition_count": sum(
                row["transition_count"] for row in full_cities
            ),
            "canonical_unique_paired_building_count": index["totals"]["unique_paired_building_count"],
        },
    }
    failed = [key for key, passed in checks["checks"].items() if not passed]
    if failed:
        checks["status"] = "fail"
        checks["failed_checks"] = failed
    else:
        checks["failed_checks"] = []
    write_json(paths["checks"], checks)
    if failed:
        raise ValueError(f"Conclusion-evidence QA failed: {failed}")

    output_specs = {
        "city_stock_flow_decomposition": (paths["stock"], ["city_id", "scope"]),
        "city_transition_route_dynamics": (
            paths["transition"], ["city_id", "scope", "transition_index"]
        ),
        "city_route_stability": (paths["stability"], ["city_id", "scope"]),
        "cross_city_descriptive_meta_analysis": (paths["meta"], ["model", "scope"]),
        "cross_city_descriptive_meta_leave_one_out": (
            paths["meta_loo"], ["omitted_city_id"]
        ),
        "city_onset_pathway_composition": (
            paths["pathway"], ["city_id", "appearance_order"]
        ),
        "city_onset_step_distribution": (
            paths["lag"], ["city_id", "pv_minus_building_onset_cohort_steps"]
        ),
        "city_temporal_separation_summary": (paths["separation"], ["city_id"]),
        "city_inventory_temporal_contrast": (paths["trajectory"], ["city_id"]),
        "context_evidence_readiness": (paths["external"], ["city_id"]),
        "results_conclusion_summary": (paths["summary"], ["metric_id"]),
        "results_conclusion_evidence_checks": (paths["checks"], []),
    }
    manifest = {
        "schema_version": "results-conclusion-evidence-manifest/v1",
        "status": "REPRODUCED",
        "generated_at_utc": utc_now(),
        "command": "python3 scripts/build_results_conclusion_evidence.py",
        "generator_script": {
            "path": str(Path(__file__).resolve()),
            "sha256": sha256_file(Path(__file__).resolve()),
            "version": SCRIPT_VERSION,
        },
        "input_resolution": (
            "Canonical paired-building artifacts are resolved only through the frozen "
            "major-results index. Risk-panel inputs are completed hash-bound paper-analysis "
            "runs named explicitly in this manifest."
        ),
        "inputs": [
            {
                "input_role": "frozen_major_results_index",
                "path": str(index_path),
                "sha256": sha256_file(index_path),
                "row_count": index["city_count"],
                "primary_key": "city_id",
            },
            *risk_inputs,
            *pair_inputs,
            {
                "input_role": "reproduced_city_trajectory_table",
                "path": str(args.trajectory_table.resolve()),
                "sha256": sha256_file(args.trajectory_table),
                "row_count": count_csv_rows(args.trajectory_table),
                "primary_key": ["city_id", "calendar_year"],
                "manifest_path": str(args.trajectory_manifest.resolve()),
                "manifest_sha256": sha256_file(args.trajectory_manifest),
            },
            {
                "input_role": "external_attribute_coverage_audit",
                "path": str(args.external_coverage.resolve()),
                "sha256": sha256_file(args.external_coverage),
                "row_count": count_csv_rows(args.external_coverage),
                "primary_key": "city_id",
                "manifest_path": str(args.external_manifest.resolve()),
                "manifest_sha256": sha256_file(args.external_manifest),
            },
            {
                "input_role": "primary_source_policy_catalog",
                "path": str(args.policy_table.resolve()),
                "sha256": sha256_file(args.policy_table),
                "row_count": count_csv_rows(args.policy_table),
                "primary_key": "catalog rows; policy identity is not used as a paper estimand here",
                "manifest_path": str(args.policy_manifest.resolve()),
                "manifest_sha256": sha256_file(args.policy_manifest),
            },
        ],
        "filters_and_exclusions": {
            "risk_panel": (
                "Inherited from completed raw-known runs: adjacent original cohort grid only; "
                "new risk requires Building A-to-P; stock risk requires P-to-P; prior linked PV "
                "events exit; events require strict adjacent accepted PV A-to-P."
            ),
            "onset_pathways": (
                "All canonical unique paired buildings; unavailable relationship rows are "
                "reported separately and are not folded into the unique-building denominator."
            ),
            "trajectories": (
                "No target exclusions; left-censored onsets enter baseline and interval-censored "
                "mass follows the existing trajectory manifest."
            ),
            "external_context": (
                "Coverage audit only. No context association is estimated because a released "
                "cross-city context-to-risk-panel join does not yet exist."
            ),
        },
        "denominator_definitions": {
            "pathway_composition": "unique canonical paired buildings",
            "stock_flow": "new buildings and building-cohort stock exposures by strict adjacent transition",
            "trajectory": "separate city anchor inventories for PV targets and building targets",
            "meta_analysis": "15 city-specific full-AOI descriptive log risk ratios",
        },
        "uncertainty": (
            "City and transition Wald intervals are descriptive and unclustered. The DL "
            "random-effects synthesis inherits those variances and is not a substitute for "
            "the planned block-clustered adjusted model."
        ),
        "outputs": {
            name: output_record(path, key)
            for name, (path, key) in output_specs.items()
        },
    }
    write_json(paths["manifest"], manifest)
    print(json.dumps({
        "status": "REPRODUCED",
        "outputs": len(output_specs),
        "full_aoi_city_count": len(full_cities),
        "full_aoi_transition_count": checks["diagnostics"]["full_aoi_transition_count"],
        "max_abs_decomposition_residual": decomposition_max,
    }, sort_keys=True))


if __name__ == "__main__":
    main()
