#!/usr/bin/env python3
"""Build C8 block-bootstrap uncertainty for continuous PV-area contrasts.

The analysis is conditional on the full Anchor AOI, anchor-surviving linked PV,
and the strict raw-known risk panel.  Buildings are assigned once to the source
block containing their largest anchor SAM3 mask (lexicographic tie break).
Spatial blocks are resampled within city; every native transition, route, risk
row, roof-area exposure, event and event-host PV area in a sampled block shares
the same bootstrap weight.  This preserves within-block temporal dependence.

Primary intervals are nonparametric percentile intervals.  Log-/logit-normal
bootstrap intervals, replicate-count checks, an alternate seed, and coarser
2x/4x source-grid clusters are reported as diagnostics.  These are not
binomial Wald intervals and do not remove candidate-domain or anchor-survivor
selection.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import numpy as np


SCRIPT_VERSION = "1.0.1"
FEATURES = (
    "n_new",
    "y_new",
    "n_stock",
    "y_retrofit",
    "pv_area_new_m2",
    "pv_area_retrofit_m2",
    "building_roof_area_new_m2",
    "building_roof_area_stock_exposure_m2",
)
F = {name: index for index, name in enumerate(FEATURES)}
NUMBER = rb"[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?"
BLOCK_PATTERN = re.compile(r"^(.*):(\d+)/(\d+)/(\d+):(\d+)x(\d+)$")
MASK_PATTERN = re.compile(
    rb'"sam3_building_id"\s*:\s*"([^"\\]+)"[^{}]{0,65536}?'
    rb'"source_block_id"\s*:\s*"([^"\\]+)"[^{}]{0,65536}?'
    rb'"area_m2"\s*:\s*(' + NUMBER + rb")",
    re.DOTALL,
)

METRICS: dict[str, dict[str, Any]] = {
    "mean_event_host_pv_area_ratio_new_to_existing": {
        "label": "New/existing mean event-host PV-footprint ratio",
        "unit": "ratio",
        "reference": 1.0,
        "transform": "log",
    },
    "building_count_area_yield_rr_new_to_existing": {
        "label": "New/existing PV-area yield ratio per Building-count risk unit",
        "unit": "ratio",
        "reference": 1.0,
        "transform": "log",
    },
    "roof_area_yield_rr_new_to_existing": {
        "label": "New/existing PV-area yield ratio per plan-view roof-area risk unit",
        "unit": "ratio",
        "reference": 1.0,
        "transform": "log",
    },
    "existing_share_of_strict_classified_pv_area": {
        "label": "Existing-route share of strict-classified anchor PV area",
        "unit": "proportion",
        "reference": 0.5,
        "transform": "logit",
    },
    "log_stock_size_existing_to_new": {
        "label": "Log stock-size component, existing/new",
        "unit": "log ratio",
        "reference": 0.0,
        "transform": "identity",
    },
    "log_event_intensity_existing_to_new": {
        "label": "Log event-intensity component, existing/new",
        "unit": "log ratio",
        "reference": 0.0,
        "transform": "identity",
    },
    "log_event_size_existing_to_new": {
        "label": "Log event-size component, existing/new",
        "unit": "log ratio",
        "reference": 0.0,
        "transform": "identity",
    },
    "count_rr_new_to_existing": {
        "label": "New/existing strict first-event count risk ratio",
        "unit": "ratio",
        "reference": 1.0,
        "transform": "log",
    },
}


def parse_args() -> argparse.Namespace:
    root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--roof-manifest",
        type=Path,
        default=root / "data_high_level" / "roof_area_weighted_results_manifest.json",
    )
    parser.add_argument(
        "--host-manifest",
        type=Path,
        default=root / "data_host_level" / "host_pv_area_distribution_manifest.json",
    )
    parser.add_argument(
        "--host-table",
        type=Path,
        default=root / "data_host_level" / "city_host_pv_area_distribution.csv",
    )
    parser.add_argument(
        "--city-area-table",
        type=Path,
        default=root / "data_high_level" / "city_area_weighted_stock_flow.csv",
    )
    parser.add_argument(
        "--transition-area-table",
        type=Path,
        default=root / "data_high_level" / "city_transition_area_weighted_stock_flow.csv",
    )
    parser.add_argument(
        "--city-roof-table",
        type=Path,
        default=root / "data_high_level" / "city_roof_area_weighted_stock_flow.csv",
    )
    parser.add_argument(
        "--transition-roof-table",
        type=Path,
        default=root / "data_high_level" / "city_transition_roof_area_weighted_stock_flow.csv",
    )
    parser.add_argument(
        "--information-gate",
        type=Path,
        default=root
        / "paper"
        / "figures"
        / "figure4_transition_dynamics"
        / "transition_information_gate_v1.json",
    )
    parser.add_argument(
        "--output-dir", type=Path, default=root / "data_high_level"
    )
    parser.add_argument(
        "--generated-dir", type=Path, default=root / "paper" / "manuscript" / "generated"
    )
    parser.add_argument("--replicates", type=int, default=5000)
    parser.add_argument("--sensitivity-replicates", type=int, default=2500)
    parser.add_argument("--alternate-seed-replicates", type=int, default=2000)
    parser.add_argument("--seed", type=int, default=20260904)
    parser.add_argument("--alternate-seed", type=int, default=20260905)
    parser.add_argument("--chunk-size", type=int, default=50)
    parser.add_argument(
        "--cities", default="", help="Debug subset; full release requires all cities."
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


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        raise ValueError(f"Refusing to write empty CSV: {path}")
    fields = list(rows[0])
    if any(list(row) != fields for row in rows):
        raise ValueError(f"Inconsistent schema: {path}")
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def write_json(path: Path, value: Any) -> None:
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )


def input_record(role: str, path: Path, expected: str | None = None) -> dict[str, Any]:
    path = path.resolve()
    observed = sha256_file(path)
    if expected and observed != expected:
        raise ValueError(f"Input hash mismatch: {path}")
    record: dict[str, Any] = {
        "role": role,
        "path": str(path),
        "sha256_expected": expected or observed,
        "sha256_observed": observed,
        "bytes": path.stat().st_size,
    }
    if path.suffix == ".csv":
        record["row_count_observed"] = csv_row_count(path)
    return record


def output_record(path: Path, primary_key: list[str] | None) -> dict[str, Any]:
    return {
        "path": str(path.resolve()),
        "sha256": sha256_file(path),
        "bytes": path.stat().st_size,
        "row_count": csv_row_count(path) if path.suffix == ".csv" else None,
        "primary_key": primary_key,
    }


def verified_bound_input(meta: dict[str, Any]) -> dict[str, Any]:
    """Record a large manifest-bound input already verified while streaming."""
    record = {
        "role": meta["input_role"],
        "path": str(Path(meta["path"]).resolve()),
        "sha256_expected": meta["sha256_expected"],
        "sha256_observed": meta.get("sha256_observed", meta["sha256_expected"]),
        "bytes": meta["bytes"],
    }
    for key in (
        "city_id",
        "row_count_expected",
        "row_count_observed",
        "primary_key",
        "owner_manifest_path",
        "owner_manifest_sha256",
    ):
        if key in meta:
            record[key] = meta[key]
    return record


def by_city_role(manifest: dict[str, Any], role: str) -> dict[str, dict[str, Any]]:
    result = {
        row["city_id"]: row
        for row in manifest["inputs"]
        if row.get("input_role") == role
    }
    if len(result) != manifest["city_count"]:
        raise ValueError(f"Expected one {role} input for every city")
    return result


def load_host_events(
    path: Path, expected_sha: str, expected_rows: int
) -> dict[str, dict[str, tuple[int, str, float]]]:
    if sha256_file(path) != expected_sha or csv_row_count(path) != expected_rows:
        raise ValueError("Host-level distribution input does not match its manifest")
    result: dict[str, dict[str, tuple[int, str, float]]] = defaultdict(dict)
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        required = {
            "city_id",
            "scope",
            "route",
            "production_building_id",
            "pv_first_appearance_transition_index",
            "host_pv_union_area_m2",
        }
        if reader.fieldnames is None or not required.issubset(reader.fieldnames):
            raise ValueError("Unexpected host-level schema")
        for row in reader:
            if row["scope"] != "full_aoi":
                continue
            city = row["city_id"]
            building = row["production_building_id"]
            if building in result[city]:
                raise ValueError(f"Duplicate strict event host: {city}/{building}")
            area = float(row["host_pv_union_area_m2"])
            if not math.isfinite(area) or area <= 0:
                raise ValueError(f"Invalid strict event-host area: {city}/{building}")
            result[city][building] = (
                int(row["pv_first_appearance_transition_index"]),
                row["route"],
                area,
            )
    return dict(result)


def load_pair_onsets(path: Path, meta: dict[str, Any], city: str) -> dict[str, int | None]:
    if sha256_file(path) != meta["sha256_expected"]:
        raise ValueError(f"{city}: unique-pair hash mismatch")
    result: dict[str, int | None] = {}
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        required = {"production_building_id", "pv_pau_first_credible_present_index"}
        if reader.fieldnames is None or not required.issubset(reader.fieldnames):
            raise ValueError(f"{city}: unique-pair schema mismatch")
        for row in reader:
            building = row["production_building_id"]
            if not building or building in result:
                raise ValueError(f"{city}: blank or duplicate paired Building")
            text = row["pv_pau_first_credible_present_index"].strip()
            result[building] = int(float(text)) if text else None
    if len(result) != meta["row_count_expected"]:
        raise ValueError(f"{city}: unique-pair row-count mismatch")
    return result


def load_membership(path: Path, meta: dict[str, Any], city: str, source: str) -> dict[str, str]:
    if sha256_file(path) != meta["sha256_expected"]:
        raise ValueError(f"{city}/{source}: membership hash mismatch")
    result: dict[str, str] = {}
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        required = {"sam3_building_id", "production_building_id"}
        if reader.fieldnames is None or not required.issubset(reader.fieldnames):
            raise ValueError(f"{city}/{source}: membership schema mismatch")
        for row in reader:
            mask = row["sam3_building_id"]
            building = row["production_building_id"]
            if not mask or not building or mask in result:
                raise ValueError(f"{city}/{source}: blank or duplicate mask identity")
            result[mask] = building
    if len(result) != meta["row_count_expected"]:
        raise ValueError(f"{city}/{source}: membership row-count mismatch")
    return result


def scan_masks(
    path: Path,
    meta: dict[str, Any],
    mask_to_building: dict[str, str],
    city: str,
    source: str,
    roof_area: dict[str, float],
    assigned_block: dict[str, str],
    largest_mask_area: dict[str, float],
    first_block: dict[str, str],
    multi_block_buildings: set[str],
) -> dict[str, Any]:
    """Stream a GeoJSON, validate its hash, and update Building area/block maps."""
    digest = hashlib.sha256()
    seen: set[str] = set()
    feature_count = 0
    matched_area = 0.0
    buffer = b""
    tail = 2 * 1024 * 1024

    def accept(match: re.Match[bytes]) -> None:
        nonlocal feature_count, matched_area
        feature_count += 1
        mask = match.group(1).decode("utf-8")
        building = mask_to_building.get(mask)
        if building is None:
            return
        if mask in seen:
            raise ValueError(f"{city}/{source}: duplicate requested mask")
        block = match.group(2).decode("utf-8")
        if not BLOCK_PATTERN.match(block):
            raise ValueError(f"{city}/{source}: unparseable source block {block}")
        area = float(match.group(3))
        if not math.isfinite(area) or area <= 0:
            raise ValueError(f"{city}/{source}: invalid mask area")
        seen.add(mask)
        matched_area += area
        roof_area[building] = roof_area.get(building, 0.0) + area
        if building not in first_block:
            first_block[building] = block
        elif first_block[building] != block:
            multi_block_buildings.add(building)
        current_area = largest_mask_area.get(building, -1.0)
        current_block = assigned_block.get(building, "")
        if area > current_area or (area == current_area and block < current_block):
            largest_mask_area[building] = area
            assigned_block[building] = block

    with path.open("rb") as handle:
        while True:
            chunk = handle.read(16 * 1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
            buffer += chunk
            cut = max(0, len(buffer) - tail)
            for match in MASK_PATTERN.finditer(buffer):
                if match.start() >= cut:
                    break
                accept(match)
            buffer = buffer[cut:]
        for match in MASK_PATTERN.finditer(buffer):
            accept(match)
    if digest.hexdigest() != meta["sha256_expected"]:
        raise ValueError(f"{city}/{source}: GeoJSON hash mismatch")
    missing = set(mask_to_building).difference(seen)
    if missing:
        raise ValueError(
            f"{city}/{source}: {len(missing)} membership masks missing from GeoJSON"
        )
    return {
        "feature_count": feature_count,
        "membership_mask_count": len(mask_to_building),
        "matched_mask_count": len(seen),
        "matched_area_m2": matched_area,
    }


def coarse_block(block: str, factor: int) -> str:
    match = BLOCK_PATTERN.match(block)
    if not match:
        raise ValueError(block)
    prefix, zoom, x, y, width, height = match.groups()
    return (
        f"{prefix}:z{zoom}:grid{factor}:"
        f"{int(x)//factor}/{int(y)//factor}:source_context_{width}x{height}"
    )


def aggregate_blocks(
    primary: dict[str, np.ndarray], factor: int
) -> tuple[list[str], np.ndarray]:
    if factor == 1:
        names = sorted(primary)
        return names, np.stack([primary[name] for name in names])
    grouped: dict[str, np.ndarray] = {}
    for name, values in primary.items():
        target = coarse_block(name, factor)
        if target not in grouped:
            grouped[target] = values.copy()
        else:
            grouped[target] += values
    names = sorted(grouped)
    return names, np.stack([grouped[name] for name in names])


def build_city_block_statistics(
    city: str,
    cohorts: list[str],
    building_meta: dict[str, Any],
    building_path: Path,
    pair_onsets: dict[str, int | None],
    host_events: dict[str, tuple[int, str, float]],
    roof_area: dict[str, float],
    assigned_block: dict[str, str],
) -> tuple[dict[str, np.ndarray], dict[str, Any]]:
    transition_count = len(cohorts) - 1
    blocks: dict[str, np.ndarray] = {}
    seen_buildings: set[str] = set()
    seen_pairs: set[str] = set()
    seen_strict_hosts: set[str] = set()
    row_count = 0
    with building_path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        required = {
            "production_building_id",
            "pau_first_appearance_type",
            "pau_first_appearance_lower_index",
            "pau_first_appearance_upper_index",
            *cohorts,
        }
        if reader.fieldnames is None or not required.issubset(reader.fieldnames):
            raise ValueError(f"{city}: full-AOI Building schema mismatch")
        for row in reader:
            row_count += 1
            building = row["production_building_id"]
            if not building or building in seen_buildings:
                raise ValueError(f"{city}: blank or duplicate full-AOI Building")
            seen_buildings.add(building)
            if building not in roof_area or building not in assigned_block:
                raise ValueError(f"{city}: Building lacks roof area or block: {building}")
            block = assigned_block[building]
            values = blocks.setdefault(
                block, np.zeros((transition_count, len(FEATURES)), dtype=np.float64)
            )
            onset = pair_onsets.get(building)
            if building in pair_onsets:
                seen_pairs.add(building)
            lower_text = row["pau_first_appearance_lower_index"].strip()
            upper_text = row["pau_first_appearance_upper_index"].strip()
            lower = int(float(lower_text)) if lower_text else None
            upper = int(float(upper_text)) if upper_text else None
            building_strict = (
                row["pau_first_appearance_type"] == "interval_censored"
                and lower is not None
                and upper is not None
                and upper - lower == 1
            )
            strict = host_events.get(building)
            for transition_index, (previous, current) in enumerate(
                zip(cohorts, cohorts[1:]), start=1
            ):
                if onset is not None and onset < transition_index:
                    continue
                position = transition_index - 1
                is_new = building_strict and upper == transition_index
                is_existing = row[previous] == "present" and row[current] == "present"
                event_here = strict is not None and strict[0] == transition_index
                if is_new:
                    values[position, F["n_new"]] += 1
                    values[position, F["building_roof_area_new_m2"]] += roof_area[building]
                    if event_here:
                        if strict[1] != "new":
                            raise ValueError(f"{city}/{building}: strict route disagreement")
                        values[position, F["y_new"]] += 1
                        values[position, F["pv_area_new_m2"]] += strict[2]
                        seen_strict_hosts.add(building)
                if is_existing:
                    values[position, F["n_stock"]] += 1
                    values[position, F["building_roof_area_stock_exposure_m2"]] += roof_area[
                        building
                    ]
                    if event_here:
                        if strict[1] != "existing":
                            raise ValueError(f"{city}/{building}: strict route disagreement")
                        values[position, F["y_retrofit"]] += 1
                        values[position, F["pv_area_retrofit_m2"]] += strict[2]
                        seen_strict_hosts.add(building)
    if sha256_file(building_path) != building_meta["sha256_expected"]:
        raise ValueError(f"{city}: full-AOI Building hash mismatch")
    if row_count != building_meta["row_count_expected"]:
        raise ValueError(f"{city}: full-AOI Building row-count mismatch")
    if seen_buildings != set(roof_area):
        raise ValueError(f"{city}: roof-area/full-AOI Building identity mismatch")
    if seen_pairs != set(pair_onsets):
        raise ValueError(f"{city}: paired-Building coverage mismatch")
    if seen_strict_hosts != set(host_events):
        missing = set(host_events).difference(seen_strict_hosts)
        raise ValueError(f"{city}: {len(missing)} strict hosts not classified")
    risk_blocks = {
        block: values
        for block, values in blocks.items()
        if values[:, [F["n_new"], F["n_stock"]]].sum() > 0
    }
    if not risk_blocks:
        raise ValueError(f"{city}: no risk-bearing blocks")
    return risk_blocks, {
        "building_identity_count": row_count,
        "assigned_source_block_count": len(blocks),
        "risk_bearing_source_block_count": len(risk_blocks),
        "strict_event_host_count": len(seen_strict_hosts),
    }


def primitive_metrics(values: np.ndarray) -> dict[str, np.ndarray]:
    """Calculate metrics on (..., 8) primitive arrays; invalid ratios become NaN."""
    x = np.asarray(values, dtype=np.float64)
    n_new = x[..., F["n_new"]]
    y_new = x[..., F["y_new"]]
    n_stock = x[..., F["n_stock"]]
    y_existing = x[..., F["y_retrofit"]]
    area_new = x[..., F["pv_area_new_m2"]]
    area_existing = x[..., F["pv_area_retrofit_m2"]]
    roof_new = x[..., F["building_roof_area_new_m2"]]
    roof_existing = x[..., F["building_roof_area_stock_exposure_m2"]]
    with np.errstate(divide="ignore", invalid="ignore"):
        footprint = (area_new / y_new) / (area_existing / y_existing)
        area_rr = (area_new / n_new) / (area_existing / n_stock)
        roof_rr = (area_new / roof_new) / (area_existing / roof_existing)
        existing_share = area_existing / (area_new + area_existing)
        log_stock = np.log(n_stock / n_new)
        log_event = np.log((y_existing / n_stock) / (y_new / n_new))
        log_size = np.log((area_existing / y_existing) / (area_new / y_new))
        count_rr = (y_new / n_new) / (y_existing / n_stock)
    return {
        "mean_event_host_pv_area_ratio_new_to_existing": footprint,
        "building_count_area_yield_rr_new_to_existing": area_rr,
        "roof_area_yield_rr_new_to_existing": roof_rr,
        "existing_share_of_strict_classified_pv_area": existing_share,
        "log_stock_size_existing_to_new": log_stock,
        "log_event_intensity_existing_to_new": log_event,
        "log_event_size_existing_to_new": log_size,
        "count_rr_new_to_existing": count_rr,
    }


def bootstrap_primitives(
    blocks: np.ndarray, replicates: int, seed: int, chunk_size: int
) -> np.ndarray:
    """Multinomial nonparametric cluster bootstrap with fixed cluster count."""
    if blocks.ndim not in (2, 3):
        raise ValueError("Blocks must be block×feature or block×transition×feature")
    block_count = blocks.shape[0]
    if block_count < 2:
        raise ValueError("At least two spatial blocks are required")
    flat = blocks.reshape(block_count, -1)
    output = np.empty((replicates, flat.shape[1]), dtype=np.float64)
    rng = np.random.default_rng(seed)
    probabilities = np.full(block_count, 1.0 / block_count, dtype=np.float64)
    for start in range(0, replicates, chunk_size):
        stop = min(start + chunk_size, replicates)
        weights = rng.multinomial(block_count, probabilities, size=stop - start)
        output[start:stop] = weights @ flat
    return output.reshape((replicates,) + blocks.shape[1:])


def stable_seed(base: int, city: str, factor: int) -> int:
    digest = hashlib.sha256(f"{base}|{city}|{factor}".encode()).digest()
    return int.from_bytes(digest[:8], "big")


def transform(values: np.ndarray, kind: str) -> np.ndarray:
    if kind == "log":
        return np.log(values)
    if kind == "logit":
        return np.log(values / (1.0 - values))
    return values


def inverse_transform(values: np.ndarray | float, kind: str) -> np.ndarray | float:
    if kind == "log":
        return np.exp(values)
    if kind == "logit":
        return 1.0 / (1.0 + np.exp(-values))
    return values


def summarize_metric(
    metric_id: str, point: float, samples: np.ndarray, confidence: float = 0.95
) -> dict[str, Any]:
    definition = METRICS[metric_id]
    finite = samples[np.isfinite(samples)]
    if definition["transform"] == "log":
        finite = finite[finite > 0]
        point_in_domain = math.isfinite(float(point)) and point > 0
    elif definition["transform"] == "logit":
        finite = finite[(finite > 0) & (finite < 1)]
        point_in_domain = math.isfinite(float(point)) and 0 < point < 1
    else:
        point_in_domain = math.isfinite(float(point))
    total = len(samples)
    if not point_in_domain or finite.size == 0:
        return {
            "estimate": "",
            "ci_lower": "",
            "ci_upper": "",
            "bootstrap_median": "",
            "bootstrap_se_analysis_scale": "",
            "normal_ci_lower": "",
            "normal_ci_upper": "",
            "estimable_replicates": int(finite.size),
            "nonestimable_replicates": int(total - finite.size),
            "nonestimable_fraction": (total - finite.size) / total,
            "fraction_above_reference": "",
            "percentile_ci_excludes_reference": "",
        }
    alpha = (1.0 - confidence) / 2.0
    lower, median, upper = np.quantile(finite, [alpha, 0.5, 1.0 - alpha])
    analysis = transform(finite, definition["transform"])
    point_analysis = float(transform(np.asarray(point), definition["transform"]))
    se = float(np.std(analysis, ddof=1)) if analysis.size > 1 else float("nan")
    normal = inverse_transform(
        np.asarray([point_analysis - 1.959963984540054 * se, point_analysis + 1.959963984540054 * se]),
        definition["transform"],
    )
    reference = definition["reference"]
    return {
        "estimate": float(point),
        "ci_lower": float(lower),
        "ci_upper": float(upper),
        "bootstrap_median": float(median),
        "bootstrap_se_analysis_scale": se,
        "normal_ci_lower": float(normal[0]),
        "normal_ci_upper": float(normal[1]),
        "estimable_replicates": int(finite.size),
        "nonestimable_replicates": int(total - finite.size),
        "nonestimable_fraction": (total - finite.size) / total,
        "fraction_above_reference": float(np.mean(finite > reference)),
        "percentile_ci_excludes_reference": bool(lower > reference or upper < reference),
    }


def interval_rows(
    level: str,
    city: str,
    point: np.ndarray,
    samples: np.ndarray,
    replicates: int,
    block_definition: str,
    transition_index: int | str = "",
    previous_cohort: str = "",
    current_cohort: str = "",
) -> list[dict[str, Any]]:
    point_metrics = primitive_metrics(point)
    sample_metrics = primitive_metrics(samples)
    rows: list[dict[str, Any]] = []
    for metric_id, definition in METRICS.items():
        summary = summarize_metric(
            metric_id, float(point_metrics[metric_id]), sample_metrics[metric_id]
        )
        rows.append(
            {
                "analysis_level": level,
                "city_id": city,
                "transition_index": transition_index,
                "previous_cohort": previous_cohort,
                "current_cohort": current_cohort,
                "metric_id": metric_id,
                "metric_label": definition["label"],
                "unit": definition["unit"],
                "reference_value": definition["reference"],
                **summary,
                "confidence_level": 0.95,
                "primary_interval": "nonparametric spatial-block bootstrap percentile interval",
                "comparison_interval": f"bootstrap-normal interval on {definition['transform']} scale",
                "bootstrap_replicates": replicates,
                "block_definition": block_definition,
                "scope": "full_aoi",
                "target_population": "full Anchor AOI risk rows and anchor-surviving accepted linked PV",
                "status": "REPRODUCED",
            }
        )
    return rows


def kish_effective_count(weights: np.ndarray) -> float:
    weights = np.asarray(weights, dtype=float)
    denominator = float(np.square(weights).sum())
    return float(weights.sum() ** 2 / denominator) if denominator > 0 else 0.0


def exact_row(table: list[dict[str, str]], city: str, scope: str = "full_aoi") -> dict[str, str]:
    rows = [row for row in table if row["city_id"] == city and row["scope"] == scope]
    if len(rows) != 1:
        raise ValueError(f"Expected one row for {city}/{scope}")
    return rows[0]


def reconcile_city(
    city: str,
    point: np.ndarray,
    city_area: dict[str, str],
    city_roof: dict[str, str],
) -> dict[str, float]:
    tolerances: dict[str, float] = {}
    for name in FEATURES:
        expected_source = city_roof if name.startswith("building_roof") else city_area
        expected = float(expected_source[name])
        observed = float(point[F[name]])
        tolerance = 1e-6 if "area" in name else 0.0
        if not math.isclose(observed, expected, rel_tol=1e-12, abs_tol=tolerance):
            raise ValueError(f"{city}: point estimate does not reproduce {name}: {observed}!={expected}")
        tolerances[name] = abs(observed - expected)
    return tolerances


def fmt(value: Any, digits: int = 2) -> str:
    if value == "" or value is None:
        return "---"
    number = float(value)
    if abs(number) >= 100:
        return f"{number:,.1f}"
    return f"{number:.{digits}f}"


def write_tex_tables(
    generated_dir: Path,
    city_rows: list[dict[str, Any]],
    pooled_rows: list[dict[str, Any]],
    diagnostic_rows: list[dict[str, Any]],
) -> tuple[Path, Path, Path, Path]:
    primary_metrics = {
        "building_count_area_yield_rr_new_to_existing": "Building-normalized area ratio",
        "roof_area_yield_rr_new_to_existing": "Roof-normalized area ratio",
        "mean_event_host_pv_area_ratio_new_to_existing": "Mean footprint ratio",
    }
    table_fields = list(city_rows[0])
    selected = [
        {field: row.get(field, "") for field in table_fields}
        for row in city_rows + pooled_rows
        if row["metric_id"] in primary_metrics
    ]
    csv_path = generated_dir / "table_s5_area_uncertainty_city.csv"
    write_csv(csv_path, selected)
    by_city: dict[str, dict[str, dict[str, Any]]] = defaultdict(dict)
    for row in selected:
        by_city[row["city_id"]][row["metric_id"]] = row
    lines = [
        "% Generated by scripts/build_area_block_bootstrap.py; do not edit.",
        "\\begin{table}",
        "\\centering",
        "\\caption{City-level spatial-block bootstrap intervals for continuous PV-area contrasts.}",
        "\\label{tab:s5-area-uncertainty}",
        "\\begin{tabular}{lccc}",
        "\\toprule",
        "City & Building-normalized area ratio & Roof-normalized area ratio & Mean footprint ratio \\\\",
        "\\midrule",
    ]
    ordered_cities = sorted(city for city in by_city if city != "all_cities_pooled")
    if "all_cities_pooled" in by_city:
        ordered_cities.append("all_cities_pooled")
    for city in ordered_cities:
        cells = []
        for metric in primary_metrics:
            row = by_city[city][metric]
            cells.append(
                f"{fmt(row['estimate'])} [{fmt(row['ci_lower'])}, {fmt(row['ci_upper'])}]"
            )
        label = (
            "All cities (count/area summed)"
            if city == "all_cities_pooled"
            else city.replace("_", " ").title()
        )
        if city == "all_cities_pooled":
            lines.append("\\midrule")
        lines.append(label + " & " + " & ".join(cells) + " \\\\")
    lines.extend(
        [
            "\\bottomrule",
            "\\end{tabular}",
            "\\begin{minipage}{0.98\\linewidth}\\footnotesize",
            "Values are point estimates with 95\\% nonparametric percentile intervals. Buildings are assigned to the source block containing their largest anchor SAM3 mask; blocks are resampled within city with all transitions and routes retained together. Ratios compare newly observed with existing-Building routes. The final row sums resampled primitive numerators and denominators across the 15 observed cities and is not a population-level cross-city synthesis. Intervals are conditional on the full Anchor AOI and anchor-surviving linked PV; they do not address candidate-domain or anchor-survival selection.",
            "\\end{minipage}",
            "\\end{table}",
            "",
        ]
    )
    tex_path = generated_dir / "table_s5_area_uncertainty_city.tex"
    tex_path.write_text("\n".join(lines), encoding="utf-8")

    diag_csv = generated_dir / "table_s6_area_uncertainty_diagnostics.csv"
    write_csv(diag_csv, diagnostic_rows)
    diag_lines = [
        "% Generated by scripts/build_area_block_bootstrap.py; do not edit.",
        "\\begin{table}",
        "\\centering",
        "\\caption{Spatial-block bootstrap diagnostics by city.}",
        "\\label{tab:s6-area-uncertainty-diagnostics}",
        "\\begin{tabular}{lrrrrr}",
        "\\toprule",
        "City & Buildings & Risk blocks & New-event blocks & Existing-event blocks & Cross-block Buildings \\\\",
        "\\midrule",
    ]
    for row in diagnostic_rows:
        diag_lines.append(
            f"{row['city_id'].replace('_', ' ').title()} & {int(row['building_identity_count']):,} & "
            f"{int(row['risk_bearing_source_block_count']):,} & {int(row['new_event_block_count']):,} & "
            f"{int(row['existing_event_block_count']):,} & {int(row['multi_source_block_building_count']):,} \\\\")
    diag_lines.extend(
        [
            "\\bottomrule",
            "\\end{tabular}",
            "\\begin{minipage}{0.98\\linewidth}\\footnotesize",
            "Risk blocks contain at least one strict raw-known new- or existing-Building risk observation. Cross-block Buildings are assigned once by their largest anchor mask. Effective block counts and all interval diagnostics are provided in the adjacent machine-readable CSV and JSON check file.",
            "\\end{minipage}",
            "\\end{table}",
            "",
        ]
    )
    diag_tex = generated_dir / "table_s6_area_uncertainty_diagnostics.tex"
    diag_tex.write_text("\n".join(diag_lines), encoding="utf-8")
    return csv_path, tex_path, diag_csv, diag_tex


def write_uncertainty_macros(
    generated_dir: Path,
    pooled_rows: list[dict[str, Any]],
    checks: dict[str, Any],
) -> tuple[Path, Path]:
    by_metric = {row["metric_id"]: row for row in pooled_rows}
    specifications = [
        ("PooledCountRiskRatio", "count_rr_new_to_existing", "estimate", "number", 3),
        ("PooledCountRiskRatioCILower", "count_rr_new_to_existing", "ci_lower", "number", 3),
        ("PooledCountRiskRatioCIUpper", "count_rr_new_to_existing", "ci_upper", "number", 3),
        ("PooledFootprintRatio", "mean_event_host_pv_area_ratio_new_to_existing", "estimate", "number", 2),
        ("PooledFootprintRatioCILower", "mean_event_host_pv_area_ratio_new_to_existing", "ci_lower", "number", 2),
        ("PooledFootprintRatioCIUpper", "mean_event_host_pv_area_ratio_new_to_existing", "ci_upper", "number", 2),
        ("PooledBuildingAreaRatio", "building_count_area_yield_rr_new_to_existing", "estimate", "number", 2),
        ("PooledBuildingAreaRatioCILower", "building_count_area_yield_rr_new_to_existing", "ci_lower", "number", 2),
        ("PooledBuildingAreaRatioCIUpper", "building_count_area_yield_rr_new_to_existing", "ci_upper", "number", 2),
        ("PooledRoofAreaRatio", "roof_area_yield_rr_new_to_existing", "estimate", "number", 2),
        ("PooledRoofAreaRatioCILower", "roof_area_yield_rr_new_to_existing", "ci_lower", "number", 2),
        ("PooledRoofAreaRatioCIUpper", "roof_area_yield_rr_new_to_existing", "ci_upper", "number", 2),
        ("PooledExistingAreaShare", "existing_share_of_strict_classified_pv_area", "estimate", "percent", 1),
        ("PooledExistingAreaShareCILower", "existing_share_of_strict_classified_pv_area", "ci_lower", "percent", 1),
        ("PooledExistingAreaShareCIUpper", "existing_share_of_strict_classified_pv_area", "ci_upper", "percent", 1),
    ]
    rows: list[dict[str, Any]] = []
    for macro, metric, field, display, digits in specifications:
        raw = float(by_metric[metric][field])
        formatted = f"{raw * 100:.{digits}f}\\%" if display == "percent" else f"{raw:.{digits}f}"
        rows.append(
            {
                "macro": macro,
                "display_value": formatted,
                "raw_value": raw,
                "metric_id": metric,
                "field": field,
                "source_file": "data_high_level/area_uncertainty_pooled.csv",
                "status": "REPRODUCED",
            }
        )
    count_specs = [
        ("AreaBootstrapPrimaryReplicateCount", "primary_replicates"),
        ("BuildingAreaRatioCIAboveOneCityCount", "city_building_area_ratio_ci_above_one_count"),
        ("RoofAreaRatioCIAboveOneCityCount", "city_roof_area_ratio_ci_above_one_count"),
        ("BuildingAreaRatioCIExcludesOneTransitionCount", "transition_building_area_ratio_ci_excludes_one_count"),
        ("RoofAreaRatioCIExcludesOneTransitionCount", "transition_roof_area_ratio_ci_excludes_one_count"),
        ("GateEligibleRoofRatioCIAboveOneTransitionCount", "information_gate_roof_area_ratio_ci_above_one_count"),
        ("GateEligibleRoofRatioCIIncludesOneTransitionCount", "information_gate_roof_area_ratio_ci_includes_one_count"),
        ("GateEligibleRoofRatioCIBelowOneTransitionCount", "information_gate_roof_area_ratio_ci_below_one_count"),
        ("GateEligibleRoofRatioBelowOnePointEstimateCount", "information_gate_roof_area_ratio_point_below_one_count"),
        ("GateEligibleRoofRatioBelowOnePointEstimateCIIncludesOneCount", "information_gate_roof_area_ratio_point_below_one_ci_includes_one_count"),
    ]
    for macro, field in count_specs:
        rows.append(
            {
                "macro": macro,
                "display_value": str(checks[field]),
                "raw_value": checks[field],
                "metric_id": "qa_count",
                "field": field,
                "source_file": "data_high_level/area_uncertainty_checks.json",
                "status": "REPRODUCED",
            }
        )
    csv_path = generated_dir / "area_uncertainty_macros_source.csv"
    write_csv(csv_path, rows)
    tex_path = generated_dir / "area_uncertainty_macros.tex"
    lines = [
        "% AUTO-GENERATED by scripts/build_area_block_bootstrap.py; DO NOT EDIT.",
        "% Raw values and provenance are in area_uncertainty_macros_source.csv.",
    ]
    lines.extend(
        f"\\providecommand{{\\{row['macro']}}}{{{row['display_value']}}}" for row in rows
    )
    lines.append("")
    tex_path.write_text("\n".join(lines), encoding="utf-8")
    return csv_path, tex_path


def main() -> int:
    args = parse_args()
    if args.replicates < 1000 or args.sensitivity_replicates < 1000:
        raise ValueError("Release run requires at least 1,000 bootstrap replicates")
    args.output_dir.mkdir(parents=True, exist_ok=True)
    args.generated_dir.mkdir(parents=True, exist_ok=True)

    roof_manifest = json.loads(args.roof_manifest.read_text(encoding="utf-8"))
    host_manifest = json.loads(args.host_manifest.read_text(encoding="utf-8"))
    information_gate = json.loads(args.information_gate.read_text(encoding="utf-8"))
    if roof_manifest.get("status") != "REPRODUCED" or host_manifest.get("status") != "REPRODUCED":
        raise ValueError("Required upstream paper-analysis bundles are not REPRODUCED")
    if information_gate.get("gate_status") != "FROZEN_BEFORE_FIRST_RENDER":
        raise ValueError("Figure 4 information gate is not frozen")
    if information_gate.get("scope") != "full_aoi":
        raise ValueError("Figure 4 information gate must use the full_aoi scope")
    minimum_events_per_route = int(
        information_gate["eligibility_rule"]["minimum_strict_first_event_hosts_per_route"]
    )
    cities = sorted(roof_manifest["cohort_order_by_city"])
    selected = [value.strip() for value in args.cities.split(",") if value.strip()]
    if selected:
        if not set(selected).issubset(cities):
            raise ValueError("Unknown --cities selection")
        cities = sorted(selected)
    release = len(cities) == roof_manifest["city_count"]
    status = "REPRODUCED" if release else "PRELIMINARY"

    building_inputs = by_city_role(roof_manifest, "full_aoi_building_strict_risk_source")
    pair_inputs = by_city_role(roof_manifest, "canonical_unique_pv_building_pairs")
    membership_inputs = {
        "narrow": by_city_role(roof_manifest, "canonical_narrow_building_anchor_mask_membership"),
        "outside": by_city_role(roof_manifest, "outside_building_anchor_mask_membership"),
    }
    geojson_inputs = {
        "narrow": by_city_role(roof_manifest, "canonical_narrow_anchor_sam3_roof_masks"),
        "outside": by_city_role(roof_manifest, "outside_anchor_sam3_roof_masks"),
    }
    host_output = host_manifest["outputs"]["city_host_pv_area_distribution"]
    host_events_all = load_host_events(
        args.host_table, host_output["sha256"], host_output["row_count"]
    )
    city_area_table = read_csv(args.city_area_table)
    transition_area_table = read_csv(args.transition_area_table)
    city_roof_table = read_csv(args.city_roof_table)
    transition_roof_table = read_csv(args.transition_roof_table)

    city_interval_rows: list[dict[str, Any]] = []
    transition_interval_rows: list[dict[str, Any]] = []
    sensitivity_rows: list[dict[str, Any]] = []
    block_rows: list[dict[str, Any]] = []
    diagnostics: list[dict[str, Any]] = []
    transition_diagnostics: list[dict[str, Any]] = []
    city_checks: dict[str, Any] = {}
    primary_city_boot: list[np.ndarray] = []
    primary_city_point: list[np.ndarray] = []
    alternate_city_boot: list[np.ndarray] = []
    scale_boot: dict[int, list[np.ndarray]] = {2: [], 4: []}
    scale_points: dict[int, list[np.ndarray]] = {2: [], 4: []}

    for city in cities:
        print(f"[{utc_now()}] {city}: loading anchor mask membership", flush=True)
        roof_area: dict[str, float] = {}
        assigned_block: dict[str, str] = {}
        largest_mask_area: dict[str, float] = {}
        first_block: dict[str, str] = {}
        multi_block_buildings: set[str] = set()
        scan_checks: dict[str, Any] = {}
        for source in ("narrow", "outside"):
            membership_meta = membership_inputs[source][city]
            membership = load_membership(
                Path(membership_meta["path"]), membership_meta, city, source
            )
            geojson_meta = geojson_inputs[source][city]
            print(
                f"[{utc_now()}] {city}: scanning {source} anchor masks "
                f"({geojson_meta['bytes']/1e9:.2f} GB)",
                flush=True,
            )
            scan_checks[source] = scan_masks(
                Path(geojson_meta["path"]),
                geojson_meta,
                membership,
                city,
                source,
                roof_area,
                assigned_block,
                largest_mask_area,
                first_block,
                multi_block_buildings,
            )
            del membership
        del largest_mask_area, first_block

        pair_meta = pair_inputs[city]
        pair_onsets = load_pair_onsets(Path(pair_meta["path"]), pair_meta, city)
        cohorts = roof_manifest["cohort_order_by_city"][city]
        print(f"[{utc_now()}] {city}: constructing block sufficient statistics", flush=True)
        primary, risk_checks = build_city_block_statistics(
            city,
            cohorts,
            building_inputs[city],
            Path(building_inputs[city]["path"]),
            pair_onsets,
            host_events_all.get(city, {}),
            roof_area,
            assigned_block,
        )
        del pair_onsets, roof_area, assigned_block
        names, block_array = aggregate_blocks(primary, 1)
        point_transitions = block_array.sum(axis=0)
        point_city = point_transitions.sum(axis=0)
        reconciliation = reconcile_city(
            city,
            point_city,
            exact_row(city_area_table, city),
            exact_row(city_roof_table, city),
        )
        transition_expected_area = {
            int(row["transition_index"]): row
            for row in transition_area_table
            if row["city_id"] == city and row["scope"] == "full_aoi"
        }
        transition_expected_roof = {
            int(row["transition_index"]): row
            for row in transition_roof_table
            if row["city_id"] == city and row["scope"] == "full_aoi"
        }
        for index in range(1, len(cohorts)):
            reconcile_city(
                f"{city}/transition_{index}",
                point_transitions[index - 1],
                transition_expected_area[index],
                transition_expected_roof[index],
            )
            transition_values = block_array[:, index - 1, :]
            n_new_by_block = transition_values[:, F["n_new"]]
            n_stock_by_block = transition_values[:, F["n_stock"]]
            y_new_by_block = transition_values[:, F["y_new"]]
            y_existing_by_block = transition_values[:, F["y_retrofit"]]
            area_new_by_block = transition_values[:, F["pv_area_new_m2"]]
            area_existing_by_block = transition_values[:, F["pv_area_retrofit_m2"]]
            roof_new_by_block = transition_values[:, F["building_roof_area_new_m2"]]
            roof_existing_by_block = transition_values[:, F["building_roof_area_stock_exposure_m2"]]
            transition_diagnostics.append(
                {
                    "city_id": city,
                    "transition_index": index,
                    "previous_cohort": cohorts[index - 1],
                    "current_cohort": cohorts[index],
                    "risk_block_count": int(np.sum((n_new_by_block + n_stock_by_block) > 0)),
                    "new_risk_block_count": int(np.sum(n_new_by_block > 0)),
                    "existing_risk_block_count": int(np.sum(n_stock_by_block > 0)),
                    "new_event_block_count": int(np.sum(y_new_by_block > 0)),
                    "existing_event_block_count": int(np.sum(y_existing_by_block > 0)),
                    "effective_block_count_n_new": kish_effective_count(n_new_by_block),
                    "effective_block_count_n_stock": kish_effective_count(n_stock_by_block),
                    "effective_block_count_pv_area_new": kish_effective_count(area_new_by_block),
                    "effective_block_count_pv_area_existing": kish_effective_count(area_existing_by_block),
                    "effective_block_count_roof_area_new": kish_effective_count(roof_new_by_block),
                    "effective_block_count_roof_area_existing": kish_effective_count(roof_existing_by_block),
                    "n_new": point_transitions[index - 1, F["n_new"]],
                    "y_new": point_transitions[index - 1, F["y_new"]],
                    "n_stock": point_transitions[index - 1, F["n_stock"]],
                    "y_retrofit": point_transitions[index - 1, F["y_retrofit"]],
                    "information_gate_eligible": bool(
                        point_transitions[index - 1, F["y_new"]] >= minimum_events_per_route
                        and point_transitions[index - 1, F["y_retrofit"]] >= minimum_events_per_route
                        and point_transitions[index - 1, F["pv_area_new_m2"]] > 0
                        and point_transitions[index - 1, F["pv_area_retrofit_m2"]] > 0
                        and point_transitions[index - 1, F["building_roof_area_new_m2"]] > 0
                        and point_transitions[index - 1, F["building_roof_area_stock_exposure_m2"]] > 0
                    ),
                    "maximum_metric_nonestimable_fraction": "",
                    "status": status,
                }
            )
        for block_name, values in zip(names, block_array):
            for index, (previous, current) in enumerate(zip(cohorts, cohorts[1:]), start=1):
                row_values = values[index - 1]
                if row_values.sum() == 0:
                    continue
                block_rows.append(
                    {
                        "city_id": city,
                        "source_block_id": block_name,
                        "transition_index": index,
                        "previous_cohort": previous,
                        "current_cohort": current,
                        **{name: row_values[F[name]] for name in FEATURES},
                        "block_assignment_rule": "source block of largest anchor SAM3 mask; lexicographic tie break",
                        "scope": "full_aoi",
                        "status": status,
                    }
                )

        event_new_by_block = block_array[:, :, F["y_new"]].sum(axis=1)
        event_existing_by_block = block_array[:, :, F["y_retrofit"]].sum(axis=1)
        risk_weight = block_array[:, :, [F["n_new"], F["n_stock"]]].sum(axis=(1, 2))
        area_weight = block_array[:, :, [F["pv_area_new_m2"], F["pv_area_retrofit_m2"]]].sum(axis=(1, 2))
        diagnostic = {
            "city_id": city,
            **risk_checks,
            "multi_source_block_building_count": len(multi_block_buildings),
            "multi_source_block_building_share": len(multi_block_buildings)
            / risk_checks["building_identity_count"],
            "new_event_block_count": int(np.sum(event_new_by_block > 0)),
            "existing_event_block_count": int(np.sum(event_existing_by_block > 0)),
            "effective_block_count_by_risk_observations": kish_effective_count(risk_weight),
            "effective_block_count_by_strict_pv_area": kish_effective_count(area_weight),
            "source_grid_2_cluster_count": aggregate_blocks(primary, 2)[1].shape[0],
            "source_grid_4_cluster_count": aggregate_blocks(primary, 4)[1].shape[0],
            "primary_replicates": args.replicates,
            "sensitivity_replicates": args.sensitivity_replicates,
            "seed": args.seed,
            "alternate_seed": args.alternate_seed,
            "status": status,
        }
        diagnostics.append(diagnostic)

        print(
            f"[{utc_now()}] {city}: primary bootstrap, {len(names)} risk blocks × {args.replicates}",
            flush=True,
        )
        boot = bootstrap_primitives(
            block_array,
            args.replicates,
            stable_seed(args.seed, city, 1),
            args.chunk_size,
        )
        city_interval_rows.extend(
            interval_rows(
                "city",
                city,
                point_city,
                boot.sum(axis=1),
                args.replicates,
                "source_block_id of largest anchor SAM3 mask",
            )
        )
        for index, (previous, current) in enumerate(zip(cohorts, cohorts[1:]), start=1):
            transition_interval_rows.extend(
                interval_rows(
                    "city_transition",
                    city,
                    point_transitions[index - 1],
                    boot[:, index - 1, :],
                    args.replicates,
                    "source_block_id of largest anchor SAM3 mask; city-level block draw shared across transitions",
                    index,
                    previous,
                    current,
                )
            )
        primary_city_boot.append(boot.sum(axis=1))
        primary_city_point.append(point_city)

        alternate = bootstrap_primitives(
            block_array.sum(axis=1),
            args.alternate_seed_replicates,
            stable_seed(args.alternate_seed, city, 1),
            args.chunk_size,
        )
        alternate_city_boot.append(alternate)

        for factor in (2, 4):
            _, coarse = aggregate_blocks(primary, factor)
            coarse_boot = bootstrap_primitives(
                coarse.sum(axis=1),
                args.sensitivity_replicates,
                stable_seed(args.seed, city, factor),
                args.chunk_size,
            )
            scale_boot[factor].append(coarse_boot)
            scale_points[factor].append(coarse.sum(axis=(0, 1)))
            factor_rows = interval_rows(
                "city_cluster_sensitivity",
                city,
                point_city,
                coarse_boot,
                args.sensitivity_replicates,
                f"source-grid coordinates aggregated {factor}x{factor}",
            )
            for row in factor_rows:
                row["cluster_scale_factor"] = factor
            sensitivity_rows.extend(factor_rows)

        city_checks[city] = {
            "mask_scans": scan_checks,
            "risk_panel": risk_checks,
            "point_reconciliation_max_absolute_difference": max(reconciliation.values()),
            "source_block_count": len(names),
            "multi_source_block_building_count": len(multi_block_buildings),
        }
        del primary, block_array, boot, multi_block_buildings

    pooled_point = np.stack(primary_city_point).sum(axis=0)
    pooled_boot = np.stack(primary_city_boot).sum(axis=0)
    pooled_rows = interval_rows(
        "all_cities_count_area_summed",
        "all_cities_pooled",
        pooled_point,
        pooled_boot,
        args.replicates,
        "source blocks resampled independently within each city; city totals then summed",
    )
    for row in pooled_rows:
        row["pooling_warning"] = "conditional arithmetic aggregate over the 15 observed cities; not an unweighted city mean or population-level cross-city synthesis"

    for factor in (2, 4):
        coarse_point = np.stack(scale_points[factor]).sum(axis=0)
        coarse_boot = np.stack(scale_boot[factor]).sum(axis=0)
        rows = interval_rows(
            "all_cities_cluster_sensitivity",
            "all_cities_pooled",
            coarse_point,
            coarse_boot,
            args.sensitivity_replicates,
            f"source-grid coordinates aggregated {factor}x{factor}; independently resampled within city",
        )
        for row in rows:
            row["cluster_scale_factor"] = factor
        sensitivity_rows.extend(rows)

    stability_rows: list[dict[str, Any]] = []
    entities = [(row[0]["city_id"], point, boot, alt) for row, point, boot, alt in zip(
        [[r for r in city_interval_rows if r["city_id"] == city] for city in cities],
        primary_city_point,
        primary_city_boot,
        alternate_city_boot,
    )]
    entities.append(
        (
            "all_cities_pooled",
            pooled_point,
            pooled_boot,
            np.stack(alternate_city_boot).sum(axis=0),
        )
    )
    for entity, point, samples, alternate in entities:
        primary_metrics = primitive_metrics(samples)
        alt_metrics = primitive_metrics(alternate)
        for metric_id in METRICS:
            point_value = float(primitive_metrics(point)[metric_id])
            for count in (1000, 2500, args.replicates):
                if count > args.replicates:
                    continue
                summary = summarize_metric(metric_id, point_value, primary_metrics[metric_id][:count])
                stability_rows.append(
                    {
                        "city_id": entity,
                        "metric_id": metric_id,
                        "diagnostic": "replicate_count",
                        "replicates": count,
                        "seed": args.seed,
                        "ci_lower": summary["ci_lower"],
                        "ci_upper": summary["ci_upper"],
                        "nonestimable_fraction": summary["nonestimable_fraction"],
                        "status": status,
                    }
                )
            alt_summary = summarize_metric(metric_id, point_value, alt_metrics[metric_id])
            stability_rows.append(
                {
                    "city_id": entity,
                    "metric_id": metric_id,
                    "diagnostic": "alternate_seed",
                    "replicates": args.alternate_seed_replicates,
                    "seed": args.alternate_seed,
                    "ci_lower": alt_summary["ci_lower"],
                    "ci_upper": alt_summary["ci_upper"],
                    "nonestimable_fraction": alt_summary["nonestimable_fraction"],
                    "status": status,
                }
            )

    transition_nonestimable: dict[tuple[str, str], float] = defaultdict(float)
    for row in transition_interval_rows:
        key = (row["city_id"], str(row["transition_index"]))
        if row["nonestimable_fraction"] != "":
            transition_nonestimable[key] = max(
                transition_nonestimable[key], float(row["nonestimable_fraction"])
            )
    for row in transition_diagnostics:
        row["maximum_metric_nonestimable_fraction"] = transition_nonestimable[
            (row["city_id"], str(row["transition_index"]))
        ]

    paths = {
        "city": args.output_dir / "area_uncertainty_city.csv",
        "pooled": args.output_dir / "area_uncertainty_pooled.csv",
        "transition": args.output_dir / "area_uncertainty_transition.csv",
        "sensitivity": args.output_dir / "area_uncertainty_cluster_sensitivity.csv",
        "stability": args.output_dir / "area_uncertainty_bootstrap_stability.csv",
        "blocks": args.output_dir / "area_uncertainty_block_sufficient_statistics.csv",
        "diagnostics": args.output_dir / "area_uncertainty_block_diagnostics.csv",
        "transition_diagnostics": args.output_dir / "area_uncertainty_transition_diagnostics.csv",
        "checks": args.output_dir / "area_uncertainty_checks.json",
        "manifest": args.output_dir / "area_uncertainty_manifest.json",
    }
    write_csv(paths["city"], city_interval_rows)
    write_csv(paths["pooled"], pooled_rows)
    write_csv(paths["transition"], transition_interval_rows)
    write_csv(paths["sensitivity"], sensitivity_rows)
    write_csv(paths["stability"], stability_rows)
    write_csv(paths["blocks"], block_rows)
    write_csv(paths["diagnostics"], diagnostics)
    write_csv(paths["transition_diagnostics"], transition_diagnostics)

    primary_area_rows = [
        row
        for row in city_interval_rows
        if row["metric_id"] == "building_count_area_yield_rr_new_to_existing"
    ]
    primary_roof_rows = [
        row
        for row in city_interval_rows
        if row["metric_id"] == "roof_area_yield_rr_new_to_existing"
    ]
    transition_area_rows = [
        row
        for row in transition_interval_rows
        if row["metric_id"] == "building_count_area_yield_rr_new_to_existing"
    ]
    transition_roof_rows = [
        row
        for row in transition_interval_rows
        if row["metric_id"] == "roof_area_yield_rr_new_to_existing"
    ]
    max_nonestimable = max(
        float(row["nonestimable_fraction"])
        for row in city_interval_rows + pooled_rows
        if row["nonestimable_fraction"] != ""
    )
    checks = {
        "status": status,
        "city_count": len(cities),
        "transition_count": len({(row["city_id"], row["transition_index"]) for row in transition_interval_rows}),
        "metric_count": len(METRICS),
        "primary_replicates": args.replicates,
        "primary_seed": args.seed,
        "alternate_seed": args.alternate_seed,
        "all_input_hashes_match": True,
        "all_city_point_estimates_reproduce_released_area_and_roof_tables": True,
        "all_buildings_assigned_exactly_one_primary_block": True,
        "all_strict_event_hosts_classified_once": True,
        "all_city_primary_metrics_have_at_least_99_percent_estimable_replicates": max_nonestimable <= 0.01,
        "maximum_city_or_pooled_nonestimable_fraction": max_nonestimable,
        "city_building_area_ratio_ci_excludes_one_count": sum(row["percentile_ci_excludes_reference"] is True for row in primary_area_rows),
        "city_building_area_ratio_ci_above_one_count": sum(row["ci_lower"] != "" and float(row["ci_lower"]) > 1 for row in primary_area_rows),
        "city_roof_area_ratio_ci_excludes_one_count": sum(row["percentile_ci_excludes_reference"] is True for row in primary_roof_rows),
        "city_roof_area_ratio_ci_above_one_count": sum(row["ci_lower"] != "" and float(row["ci_lower"]) > 1 for row in primary_roof_rows),
        "transition_building_area_ratio_estimable_count": sum(row["estimate"] != "" for row in transition_area_rows),
        "transition_building_area_ratio_ci_excludes_one_count": sum(row["percentile_ci_excludes_reference"] is True for row in transition_area_rows),
        "transition_roof_area_ratio_estimable_count": sum(row["estimate"] != "" for row in transition_roof_rows),
        "transition_roof_area_ratio_ci_excludes_one_count": sum(row["percentile_ci_excludes_reference"] is True for row in transition_roof_rows),
        "information_gate_eligible_transition_count": sum(row["information_gate_eligible"] is True for row in transition_diagnostics),
        "transition_cells_over_one_percent_nonestimable_replicates": sum(float(row["maximum_metric_nonestimable_fraction"]) > 0.01 for row in transition_diagnostics),
        "transition_cells_over_five_percent_nonestimable_replicates": sum(float(row["maximum_metric_nonestimable_fraction"]) > 0.05 for row in transition_diagnostics),
        "city_checks": city_checks,
        "interpretation_boundary": "intervals quantify spatial-block resampling variability within the observed full Anchor AOI risk panels; they do not address candidate-domain selection, anchor survival, city sampling, causal identification, or measured nameplate capacity",
    }
    if release and not checks["all_city_primary_metrics_have_at_least_99_percent_estimable_replicates"]:
        raise ValueError("Release gate failed: excessive non-estimable city bootstrap replicates")

    def interval_class(row: dict[str, Any]) -> str:
        if row["ci_lower"] == "":
            return "nonestimable"
        reference = float(row["reference_value"])
        if float(row["ci_lower"]) > reference:
            return "above"
        if float(row["ci_upper"]) < reference:
            return "below"
        return "crosses"

    gate_eligible_pairs = {
        (row["city_id"], str(row["transition_index"]))
        for row in transition_diagnostics
        if row["information_gate_eligible"] is True
    }
    gate_eligible_roof_rows = [
        row
        for row in transition_roof_rows
        if (row["city_id"], str(row["transition_index"])) in gate_eligible_pairs
    ]
    gate_roof_ci_above = sum(interval_class(row) == "above" for row in gate_eligible_roof_rows)
    gate_roof_ci_includes = sum(interval_class(row) == "crosses" for row in gate_eligible_roof_rows)
    gate_roof_ci_below = sum(interval_class(row) == "below" for row in gate_eligible_roof_rows)
    gate_roof_point_below_rows = [
        row for row in gate_eligible_roof_rows if float(row["estimate"]) < 1.0
    ]
    gate_roof_point_below_ci_includes = sum(
        interval_class(row) == "crosses" for row in gate_roof_point_below_rows
    )
    checks.update(
        {
            "information_gate_minimum_strict_first_event_hosts_per_route": minimum_events_per_route,
            "information_gate_roof_area_ratio_ci_above_one_count": gate_roof_ci_above,
            "information_gate_roof_area_ratio_ci_includes_one_count": gate_roof_ci_includes,
            "information_gate_roof_area_ratio_ci_below_one_count": gate_roof_ci_below,
            "information_gate_roof_area_ratio_point_below_one_count": len(gate_roof_point_below_rows),
            "information_gate_roof_area_ratio_point_below_one_ci_includes_one_count": gate_roof_point_below_ci_includes,
            "information_gate_roof_area_ratio_interval_accounting_reconciles": (
                gate_roof_ci_above + gate_roof_ci_includes + gate_roof_ci_below
                == len(gate_eligible_roof_rows)
                == checks["information_gate_eligible_transition_count"]
            ),
            "all_information_gate_roof_area_ratio_points_below_one_have_ci_including_one": (
                gate_roof_point_below_ci_includes == len(gate_roof_point_below_rows)
            ),
        }
    )
    if release and not checks["information_gate_roof_area_ratio_interval_accounting_reconciles"]:
        raise ValueError("Release gate failed: gate-eligible roof interval accounting")
    if release and not checks[
        "all_information_gate_roof_area_ratio_points_below_one_have_ci_including_one"
    ]:
        raise ValueError("Release gate failed: a below-one roof point has a fully below-one interval")

    percentile_normal_disagreements = 0
    for row in city_interval_rows + pooled_rows:
        reference = float(row["reference_value"])
        percentile = interval_class(row)
        if row["normal_ci_lower"] == "":
            normal = "nonestimable"
        elif float(row["normal_ci_lower"]) > reference:
            normal = "above"
        elif float(row["normal_ci_upper"]) < reference:
            normal = "below"
        else:
            normal = "crosses"
        percentile_normal_disagreements += percentile != normal
    checks["percentile_vs_bootstrap_normal_interval_classification_disagreement_count_city_and_pooled"] = percentile_normal_disagreements

    def stability_max_difference(compare: str) -> float:
        groups: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
        for row in stability_rows:
            if compare == "replicate_count":
                use = (
                    row["diagnostic"] == "replicate_count"
                    and row["replicates"] in (2500, args.replicates)
                )
            else:
                use = (
                    row["diagnostic"] == "alternate_seed"
                    or (
                        row["diagnostic"] == "replicate_count"
                        and row["replicates"] == args.replicates
                    )
                )
            if use:
                groups[(row["city_id"], row["metric_id"])].append(row)
        maximum = 0.0
        for (_, metric_id), group in groups.items():
            if len(group) != 2:
                continue
            definition = METRICS[metric_id]
            for field in ("ci_lower", "ci_upper"):
                values = np.asarray([float(row[field]) for row in group])
                transformed = transform(values, definition["transform"])
                maximum = max(maximum, abs(float(transformed[0] - transformed[1])))
        return maximum

    checks["maximum_interval_endpoint_change_analysis_scale_2500_vs_5000_replicates"] = stability_max_difference("replicate_count")
    checks["maximum_interval_endpoint_change_analysis_scale_alternate_seed_vs_primary"] = stability_max_difference("alternate_seed")

    base_class = {
        (row["city_id"], row["metric_id"]): interval_class(row)
        for row in city_interval_rows
    }
    cluster_class_changes: set[tuple[str, str]] = set()
    for row in sensitivity_rows:
        if row["analysis_level"] != "city_cluster_sensitivity":
            continue
        key = (row["city_id"], row["metric_id"])
        if interval_class(row) != base_class[key]:
            cluster_class_changes.add(key)
    checks["city_metric_interval_classifications_changed_by_2x_or_4x_cluster_sensitivity"] = [
        {"city_id": city, "metric_id": metric}
        for city, metric in sorted(cluster_class_changes)
    ]
    checks["city_metric_interval_classification_change_count_under_coarse_clusters"] = len(cluster_class_changes)

    write_json(paths["checks"], checks)
    table_paths = write_tex_tables(
        args.generated_dir, city_interval_rows, pooled_rows, diagnostics
    )
    macro_paths = write_uncertainty_macros(args.generated_dir, pooled_rows, checks)

    upstream_files = [
        ("roof_area_weighted_results_manifest", args.roof_manifest, None),
        ("host_pv_area_distribution_manifest", args.host_manifest, None),
        ("strict_event_host_area_table", args.host_table, host_output["sha256"]),
        ("city_area_weighted_stock_flow", args.city_area_table, None),
        ("city_transition_area_weighted_stock_flow", args.transition_area_table, None),
        ("city_roof_area_weighted_stock_flow", args.city_roof_table, None),
        ("city_transition_roof_area_weighted_stock_flow", args.transition_roof_table, None),
        ("figure4_frozen_transition_information_gate", args.information_gate, None),
    ]
    direct_inputs = [input_record(role, path, expected) for role, path, expected in upstream_files]
    for city in cities:
        for role_map in (building_inputs, pair_inputs, membership_inputs["narrow"], membership_inputs["outside"], geojson_inputs["narrow"], geojson_inputs["outside"]):
            meta = role_map[city]
            direct_inputs.append(verified_bound_input(meta))
    output_specs = {
        "area_uncertainty_city": (paths["city"], ["city_id", "metric_id"]),
        "area_uncertainty_pooled": (paths["pooled"], ["city_id", "metric_id"]),
        "area_uncertainty_transition": (paths["transition"], ["city_id", "transition_index", "metric_id"]),
        "area_uncertainty_cluster_sensitivity": (paths["sensitivity"], ["analysis_level", "city_id", "cluster_scale_factor", "metric_id"]),
        "area_uncertainty_bootstrap_stability": (paths["stability"], ["city_id", "metric_id", "diagnostic", "replicates", "seed"]),
        "area_uncertainty_block_sufficient_statistics": (paths["blocks"], ["city_id", "source_block_id", "transition_index"]),
        "area_uncertainty_block_diagnostics": (paths["diagnostics"], ["city_id"]),
        "area_uncertainty_transition_diagnostics": (paths["transition_diagnostics"], ["city_id", "transition_index"]),
        "area_uncertainty_checks": (paths["checks"], None),
        "table_s5_source": (table_paths[0], ["city_id", "metric_id"]),
        "table_s5_tex": (table_paths[1], None),
        "table_s6_source": (table_paths[2], ["city_id"]),
        "table_s6_tex": (table_paths[3], None),
        "uncertainty_macros_source": (macro_paths[0], ["macro"]),
        "uncertainty_macros_tex": (macro_paths[1], None),
    }
    manifest = {
        "schema_version": "1.0",
        "status": status,
        "generated_at_utc": utc_now(),
        "generator": {
            "path": str(Path(__file__).resolve()),
            "sha256": sha256_file(Path(__file__)),
            "version": SCRIPT_VERSION,
        },
        "command": "python3 scripts/build_area_block_bootstrap.py",
        "scope": "full Anchor AOI; strict raw-known adjacent risk panel; anchor-surviving accepted linked PV",
        "estimands": {metric: value["label"] for metric, value in METRICS.items()},
        "block_assignment": "Each Building is assigned once to the source_block_id containing its largest-area anchor SAM3 mask; exact-area ties use lexicographic block ID.",
        "resampling": {
            "primary": "Nonparametric multinomial cluster bootstrap within city using risk-bearing source blocks. A block draw supplies one shared weight to all native transitions, routes, risk rows, roof-area exposures, events and host PV areas in that block.",
            "primary_replicates": args.replicates,
            "primary_seed": args.seed,
            "primary_interval": "two-sided 95% percentile interval",
            "comparison_interval": "normal interval on log scale for positive ratios, logit scale for shares and identity scale for log components",
            "alternate_seed_replicates": args.alternate_seed_replicates,
            "alternate_seed": args.alternate_seed,
            "cluster_sensitivity": "source-grid coordinates grouped at 2x2 and 4x4 scales",
            "cluster_sensitivity_replicates": args.sensitivity_replicates,
            "pooled_definition": "source blocks independently resampled within each observed city, then primitive numerators and denominators summed before metric calculation",
        },
        "filters_and_exclusions": [
            "Original native adjacent cohort grid retained; no bridging across unknown or missing observations.",
            "New risk group requires strict raw-known Building interval-censored onset on the current transition.",
            "Existing risk group requires raw-known present-to-present Building states.",
            "Buildings exit after their linked PV first-present index; only strict adjacent accepted PV first events enter event and area numerators.",
            "All resolved source-target anchor PV union area on a unique host is attributed once to its first strict event.",
            "Only risk-bearing source blocks are resampled; blocks without an eligible strict risk observation contribute no sufficient statistic.",
            "Gate-specific transition summaries use the immutable Figure 4 information gate loaded from its frozen JSON contract; interval results do not determine eligibility.",
        ],
        "interpretation_boundary": checks["interpretation_boundary"],
        "cohort_order_by_city": {city: roof_manifest["cohort_order_by_city"][city] for city in cities},
        "inputs": direct_inputs,
        "outputs": {name: output_record(path, key) for name, (path, key) in output_specs.items()},
        "qa": {
            "path": str(paths["checks"].resolve()),
            "sha256": sha256_file(paths["checks"]),
            "all_required_checks_pass": True,
        },
    }
    write_json(paths["manifest"], manifest)
    print(json.dumps({"status": status, "outputs": {key: str(value) for key, value in paths.items()}, "checks": checks}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
