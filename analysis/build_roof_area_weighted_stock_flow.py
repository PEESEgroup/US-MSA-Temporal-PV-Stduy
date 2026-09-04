#!/usr/bin/env python3
"""Build roof-area risk denominators for the strict PV stock--flow panel.

The script reproduces the existing raw-known Building-count risk rows, then
replaces each eligible Building contribution with the sum of its plan-view
anchor SAM3 roof-mask areas.  Existing-Building roof area is accumulated over
native adjacent cohort transitions and is therefore a roof-area--cohort
exposure, not an anchor-year stock total or usable-roof estimate.

Full-AOI Building identities and states are read only from the completed risk
releases bound by ``results_conclusion_evidence_manifest.json``.  Roof areas
are assembled from the separately hash-bound narrow and outside-narrow anchor
SAM3 mask inventories; no upstream artifact or frozen index is modified.
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


SCRIPT_VERSION = "1.0.0"
NUMBER_PATTERN = rb"[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?"


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
        "--risk-manifest",
        type=Path,
        default=workspace / "data_high_level" / "results_conclusion_evidence_manifest.json",
    )
    parser.add_argument(
        "--area-manifest",
        type=Path,
        default=workspace / "data_high_level" / "area_weighted_results_manifest.json",
    )
    parser.add_argument(
        "--area-sources",
        type=Path,
        default=workspace / "config" / "city_anchor_area_sources.csv",
    )
    parser.add_argument(
        "--city-area-table",
        type=Path,
        default=workspace / "data_high_level" / "city_area_weighted_stock_flow.csv",
    )
    parser.add_argument(
        "--transition-area-table",
        type=Path,
        default=workspace / "data_high_level" / "city_transition_area_weighted_stock_flow.csv",
    )
    parser.add_argument(
        "--area-trajectory-table",
        type=Path,
        default=workspace / "data_high_level" / "city_pv_building_area_trajectories.csv",
    )
    parser.add_argument(
        "--output-dir", type=Path, default=workspace / "data_high_level"
    )
    parser.add_argument(
        "--cities",
        default="",
        help="Comma-separated debug subset. Omit for the required 15-city release.",
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


def safe_ratio(numerator: float, denominator: float) -> float | None:
    return numerator / denominator if denominator else None


def finite_or_blank(value: Any) -> Any:
    if value is None:
        return ""
    if isinstance(value, float) and not math.isfinite(value):
        return ""
    return value


def input_record(
    role: str,
    path: Path,
    *,
    expected_sha256: str | None = None,
    expected_rows: int | None = None,
    primary_key: Any = None,
    owner_manifest: Path | None = None,
    city_id: str | None = None,
) -> dict[str, Any]:
    path = path.resolve()
    if not path.is_file():
        raise FileNotFoundError(path)
    observed_sha256 = sha256_file(path)
    if expected_sha256 and observed_sha256 != expected_sha256:
        raise ValueError(f"Input hash mismatch: {path}")
    record: dict[str, Any] = {
        "input_role": role,
        "path": str(path),
        "sha256_expected": expected_sha256 or observed_sha256,
        "sha256_observed": observed_sha256,
        "bytes": path.stat().st_size,
    }
    if city_id:
        record["city_id"] = city_id
    if path.suffix.lower() == ".csv":
        observed_rows = csv_row_count(path)
        if expected_rows is not None and observed_rows != expected_rows:
            raise ValueError(
                f"Input row-count mismatch: {path}: {observed_rows}!={expected_rows}"
            )
        record["row_count_expected"] = (
            observed_rows if expected_rows is None else expected_rows
        )
        record["row_count_observed"] = observed_rows
    if primary_key is not None:
        record["primary_key"] = primary_key
    if owner_manifest is not None:
        record["owner_manifest_path"] = str(owner_manifest.resolve())
        record["owner_manifest_sha256"] = sha256_file(owner_manifest)
    return record


def load_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def load_area_sources(path: Path) -> dict[str, dict[str, str]]:
    required = {
        "city_id",
        "pv_geojson_path",
        "pv_geojson_sha256",
        "pv_manifest_path",
        "sam3_geojson_path",
        "sam3_geojson_sha256",
        "sam3_manifest_path",
        "building_membership_path",
        "building_membership_sha256",
        "building_membership_provenance_path",
    }
    rows = load_csv(path)
    if not rows or set(rows[0]) != required:
        raise ValueError(f"Unexpected area-source schema: {path}")
    result: dict[str, dict[str, str]] = {}
    for row in rows:
        city_id = row["city_id"]
        if city_id in result:
            raise ValueError(f"Duplicate area source: {city_id}")
        result[city_id] = row
    return result


def verify_json_reference(reference: dict[str, Any]) -> dict[str, Any]:
    path = Path(reference["path"])
    observed = sha256_file(path)
    if observed != reference["sha256"]:
        raise ValueError(f"Referenced manifest hash mismatch: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def resolve_risk_inputs(
    risk_manifest: dict[str, Any], expected_cities: set[str]
) -> tuple[dict[str, dict[str, Any]], list[dict[str, Any]]]:
    """Follow the completed-risk manifest chain to full/narrow state inputs."""

    city_meta: dict[str, dict[str, Any]] = {}
    records: list[dict[str, Any]] = []
    releases = [
        item
        for item in risk_manifest["inputs"]
        if item.get("input_role") == "completed_full_aoi_raw_known_risk_release"
    ]
    if len(releases) != 3:
        raise ValueError("Expected the three completed full-AOI raw-known releases")
    for release in releases:
        raw_manifest_path = Path(release["path"])
        raw_manifest = verify_json_reference(release)
        if raw_manifest.get("status") != "complete":
            raise ValueError(f"Incomplete risk release: {raw_manifest_path}")
        records.append(
            input_record(
                "completed_full_aoi_raw_known_risk_release_manifest",
                raw_manifest_path,
                expected_sha256=release["sha256"],
            )
        )
        raw_input_ref = raw_manifest["outputs"]["inputs/input_manifest.json"]
        raw_input_path = Path(raw_input_ref["path"])
        raw_inputs = json.loads(raw_input_path.read_text(encoding="utf-8"))
        records.append(
            input_record(
                "completed_full_aoi_raw_known_input_manifest",
                raw_input_path,
                expected_sha256=raw_input_ref["sha256"],
                owner_manifest=raw_manifest_path,
            )
        )
        merge_ref = raw_manifest["source_merge_run"]
        merge_manifest_path = Path(merge_ref["path"])
        merge_manifest = verify_json_reference(merge_ref)
        if merge_manifest.get("status") != "complete":
            raise ValueError(f"Incomplete state-merge release: {merge_manifest_path}")
        records.append(
            input_record(
                "full_aoi_state_merge_manifest",
                merge_manifest_path,
                expected_sha256=merge_ref["sha256"],
            )
        )
        merge_input_ref = merge_manifest["outputs"]["inputs/input_manifest.json"]
        merge_input_path = Path(merge_input_ref["path"])
        merge_inputs = json.loads(merge_input_path.read_text(encoding="utf-8"))
        records.append(
            input_record(
                "full_aoi_state_merge_input_manifest",
                merge_input_path,
                expected_sha256=merge_input_ref["sha256"],
                owner_manifest=merge_manifest_path,
            )
        )
        for city_id, raw_meta in raw_inputs["cities"].items():
            if city_id in city_meta:
                raise ValueError(f"City appears in two risk releases: {city_id}")
            merge_meta = merge_inputs["cities"][city_id]
            if raw_meta["cohort_order"] != merge_meta["cohort_order"]:
                raise ValueError(f"Cohort order disagreement for {city_id}")
            city_meta[city_id] = {
                "cohort_order": raw_meta["cohort_order"],
                "narrow_building": raw_meta["narrow_building"],
                "full_aoi_building": raw_meta["full_aoi_building"],
                "unique_pv_building_pairs": raw_meta["unique_pv_building_pairs"],
                "outside_building_first_appearance": merge_meta[
                    "outside_building_first_appearance"
                ],
                "outside_first_appearance_summary": merge_meta[
                    "outside_first_appearance_summary"
                ],
                "risk_release_manifest": raw_manifest_path,
                "state_merge_manifest": merge_manifest_path,
            }
    if set(city_meta) != expected_cities:
        raise ValueError(
            f"Risk releases do not resolve exactly the indexed cities: "
            f"missing={sorted(expected_cities-set(city_meta))}, "
            f"extra={sorted(set(city_meta)-expected_cities)}"
        )
    return city_meta, records


def city_root_from_outside_path(path: Path, city_id: str) -> Path:
    for candidate in path.resolve().parents:
        if candidate.name == city_id and candidate.parent.name == "artifacts":
            return candidate
    raise ValueError(f"Cannot resolve outside-census city root from {path}")


def yaml_scalar_path(path: Path, key: str) -> Path:
    """Read one top-level ``key: value`` path from a frozen binding YAML."""

    pattern = re.compile(rf"^{re.escape(key)}:\s*(.+?)\s*$")
    for line in path.read_text(encoding="utf-8").splitlines():
        match = pattern.match(line)
        if match:
            return Path(match.group(1).strip().strip("\"'"))
    raise ValueError(f"Missing {key!r} in binding {path}")


def resolve_outside_stage7_summary(
    outside_first_path: Path, city_id: str
) -> tuple[Path, str | None, Path]:
    """Resolve the Stage 7B summary through the owning first-appearance manifest."""

    first_manifest_path = outside_first_path.parent.parent / "manifest.json"
    first_manifest = json.loads(first_manifest_path.read_text(encoding="utf-8"))
    if first_manifest.get("protocol_id") != "pau_sequence_first_appearance_drop_unknown_v3":
        raise ValueError(f"{city_id}: unexpected outside first-appearance manifest")
    candidates: list[tuple[Path, str]] = []
    for raw_path, expected_sha in first_manifest.get("inputs", {}).items():
        candidate = Path(raw_path)
        if candidate.name != "summary.json" or not candidate.is_file():
            continue
        try:
            value = json.loads(candidate.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        if value.get("protocol_id") == "sam3_mask_temporal_then_anchor_osm_link_v1":
            candidates.append((candidate, expected_sha))
    if not candidates:
        # A small number of completed first-appearance manifests bind the
        # Stage 7B timeline but omit its sibling summary.  Resolve the summary
        # from that explicitly bound timeline directory (not by run search).
        timeline_paths = [
            Path(raw_path)
            for raw_path in first_manifest.get("inputs", {})
            if Path(raw_path).name == "building_vintage_timeline.csv"
        ]
        if len(timeline_paths) == 1:
            candidate = timeline_paths[0].parent / "summary.json"
            if candidate.is_file():
                value = json.loads(candidate.read_text(encoding="utf-8"))
                if value.get("protocol_id") == "sam3_mask_temporal_then_anchor_osm_link_v1":
                    candidates.append((candidate, None))
    if len(candidates) != 1:
        raise ValueError(
            f"{city_id}: expected one Stage 7B summary in first-appearance inputs, "
            f"found {len(candidates)}"
        )
    return candidates[0][0], candidates[0][1], first_manifest_path


def load_membership(
    path: Path, expected_sha256: str | None, city_id: str, source: str
) -> tuple[dict[str, str], Counter[str], dict[str, Any]]:
    observed_sha256 = sha256_file(path)
    if expected_sha256 and observed_sha256 != expected_sha256:
        raise ValueError(f"{city_id}/{source}: membership hash mismatch")
    mask_to_building: dict[str, str] = {}
    counts: Counter[str] = Counter()
    row_count = 0
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        required = {"sam3_building_id", "production_building_id"}
        if reader.fieldnames is None or not required.issubset(reader.fieldnames):
            raise ValueError(f"{city_id}/{source}: membership schema mismatch")
        for row in reader:
            row_count += 1
            mask_id = row["sam3_building_id"]
            building_id = row["production_building_id"]
            if not mask_id or not building_id or mask_id in mask_to_building:
                raise ValueError(f"{city_id}/{source}: blank or duplicate mask identity")
            mask_to_building[mask_id] = building_id
            counts[building_id] += 1
    return mask_to_building, counts, {
        "row_count": row_count,
        "unique_mask_count": len(mask_to_building),
        "unique_building_count": len(counts),
    }


def area_pattern() -> re.Pattern[bytes]:
    return re.compile(
        rb'"sam3_building_id"\s*:\s*"([^"\\]+)"[^{}]{0,2097152}?'
        rb'"area_m2"\s*:\s*(' + NUMBER_PATTERN + rb")",
        re.DOTALL,
    )


def scan_mask_areas(
    path: Path,
    expected_sha256: str,
    mask_to_building: dict[str, str],
    city_id: str,
    source: str,
) -> tuple[dict[str, float], dict[str, Any]]:
    """Stream one anchor GeoJSON and sum requested mask areas by Building."""

    pattern = area_pattern()
    building_areas: dict[str, float] = defaultdict(float)
    seen: set[str] = set()
    source_feature_count = 0
    digest = hashlib.sha256()
    buffer = b""
    tail_bytes = 4 * 1024 * 1024

    def accept(match: re.Match[bytes]) -> None:
        nonlocal source_feature_count
        source_feature_count += 1
        mask_id = match.group(1).decode("utf-8")
        building_id = mask_to_building.get(mask_id)
        if building_id is None:
            return
        if mask_id in seen:
            raise ValueError(f"{city_id}/{source}: duplicate requested mask in GeoJSON")
        area = float(match.group(2))
        if not math.isfinite(area) or area <= 0:
            raise ValueError(f"{city_id}/{source}: invalid mask area")
        seen.add(mask_id)
        building_areas[building_id] += area

    with path.open("rb") as handle:
        while True:
            chunk = handle.read(16 * 1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
            buffer += chunk
            cut = max(0, len(buffer) - tail_bytes)
            for match in pattern.finditer(buffer):
                if match.start() >= cut:
                    break
                accept(match)
            buffer = buffer[cut:]
        for match in pattern.finditer(buffer):
            accept(match)
    observed_sha256 = digest.hexdigest()
    if observed_sha256 != expected_sha256:
        raise ValueError(f"{city_id}/{source}: anchor GeoJSON hash mismatch")
    missing = set(mask_to_building).difference(seen)
    if missing:
        raise ValueError(
            f"{city_id}/{source}: {len(missing)} membership masks lack area; "
            f"examples={sorted(missing)[:5]}"
        )
    return dict(building_areas), {
        "source_feature_count": source_feature_count,
        "requested_mask_count": len(mask_to_building),
        "matched_mask_count": len(seen),
        "matched_building_count": len(building_areas),
        "matched_area_m2": math.fsum(building_areas.values()),
    }


def load_pair_events(
    path: Path, expected_sha256: str, expected_rows: int, city_id: str
) -> tuple[dict[str, dict[str, int | None]], dict[str, Any]]:
    observed_sha256 = sha256_file(path)
    if observed_sha256 != expected_sha256:
        raise ValueError(f"{city_id}: pair-table hash mismatch")
    events: dict[str, dict[str, int | None]] = {}
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        required = {
            "production_building_id",
            "pv_pau_first_appearance_type",
            "pv_pau_first_appearance_lower_index",
            "pv_pau_first_appearance_upper_index",
            "pv_pau_first_credible_present_index",
        }
        if reader.fieldnames is None or not required.issubset(reader.fieldnames):
            raise ValueError(f"{city_id}: pair-table schema mismatch")
        for row in reader:
            building_id = row["production_building_id"]
            if not building_id or building_id in events:
                raise ValueError(f"{city_id}: blank or duplicate paired Building")
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
            events[building_id] = {
                "onset": onset,
                "strict_event_transition": upper if strict else None,
            }
    if len(events) != expected_rows:
        raise ValueError(f"{city_id}: pair-table row-count mismatch")
    return events, {
        "unique_paired_building_count": len(events),
        "strict_event_host_count": sum(
            value["strict_event_transition"] is not None for value in events.values()
        ),
    }


def estimate_roof_denominators(
    city_id: str,
    scope: str,
    building_path: Path,
    expected_sha256: str,
    expected_rows: int,
    cohorts: list[str],
    roof_areas: dict[str, float],
    source_mask_counts: dict[str, Counter[str]],
    pair_events: dict[str, dict[str, int | None]],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    observed_sha256 = sha256_file(building_path)
    if observed_sha256 != expected_sha256:
        raise ValueError(f"{city_id}/{scope}: Building-table hash mismatch")
    slots = [
        {
            "n_new": 0,
            "y_new": 0,
            "n_stock": 0,
            "y_retrofit": 0,
            "roof_area_new_m2": [],
            "roof_area_stock_exposure_m2": [],
        }
        for _ in range(len(cohorts) - 1)
    ]
    seen: set[str] = set()
    seen_pairs: set[str] = set()
    row_count = 0
    total_anchor_area_values: list[float] = []
    with building_path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        required = {
            "production_building_id",
            "anchor_mask_count",
            "pau_first_appearance_type",
            "pau_first_appearance_lower_index",
            "pau_first_appearance_upper_index",
            *cohorts,
        }
        if scope == "full_aoi":
            required.update({"narrow_anchor_mask_count", "outside_anchor_mask_count"})
        if reader.fieldnames is None or not required.issubset(reader.fieldnames):
            raise ValueError(f"{city_id}/{scope}: Building-table schema mismatch")
        for row in reader:
            row_count += 1
            building_id = row["production_building_id"]
            if not building_id or building_id in seen:
                raise ValueError(f"{city_id}/{scope}: blank or duplicate Building identity")
            seen.add(building_id)
            area = roof_areas.get(building_id)
            if area is None or not math.isfinite(area) or area <= 0:
                raise ValueError(f"{city_id}/{scope}: Building lacks positive roof area: {building_id}")
            total_anchor_area_values.append(area)
            narrow_count = source_mask_counts["narrow"].get(building_id, 0)
            outside_count = source_mask_counts.get("outside", Counter()).get(building_id, 0)
            if scope == "narrow":
                if int(row["anchor_mask_count"]) != narrow_count or outside_count:
                    raise ValueError(f"{city_id}/{scope}: mask-count reconciliation failure")
            else:
                if (
                    int(row["narrow_anchor_mask_count"]) != narrow_count
                    or int(row["outside_anchor_mask_count"]) != outside_count
                    or int(row["anchor_mask_count"]) != narrow_count + outside_count
                ):
                    raise ValueError(f"{city_id}/{scope}: mask-count reconciliation failure")

            pair = pair_events.get(building_id)
            if pair:
                seen_pairs.add(building_id)
                pv_onset = pair["onset"]
                event_transition = pair["strict_event_transition"]
            else:
                pv_onset = None
                event_transition = None
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
            for transition_index, (previous, current) in enumerate(
                zip(cohorts, cohorts[1:]), start=1
            ):
                at_risk = pv_onset is None or pv_onset >= transition_index
                if not at_risk:
                    continue
                slot = slots[transition_index - 1]
                new_group = building_strict and upper == transition_index
                stock_group = row[previous] == "present" and row[current] == "present"
                is_event = event_transition == transition_index
                if new_group:
                    slot["n_new"] += 1
                    slot["roof_area_new_m2"].append(area)
                    if is_event:
                        slot["y_new"] += 1
                if stock_group:
                    slot["n_stock"] += 1
                    slot["roof_area_stock_exposure_m2"].append(area)
                    if is_event:
                        slot["y_retrofit"] += 1
    if row_count != expected_rows:
        raise ValueError(f"{city_id}/{scope}: Building-table row-count mismatch")
    if seen != set(roof_areas):
        extra = set(roof_areas).difference(seen)
        missing = seen.difference(roof_areas)
        raise ValueError(
            f"{city_id}/{scope}: area identity mismatch; extra={len(extra)}, missing={len(missing)}"
        )
    if seen_pairs != set(pair_events):
        raise ValueError(f"{city_id}/{scope}: paired Building coverage mismatch")

    transition_rows: list[dict[str, Any]] = []
    for index, (previous, current, slot) in enumerate(
        zip(cohorts, cohorts[1:], slots), start=1
    ):
        transition_rows.append(
            {
                "city_id": city_id,
                "scope": scope,
                "transition_index": index,
                "previous_cohort": previous,
                "current_cohort": current,
                "n_new": slot["n_new"],
                "y_new": slot["y_new"],
                "n_stock": slot["n_stock"],
                "y_retrofit": slot["y_retrofit"],
                "building_roof_area_new_m2": math.fsum(slot["roof_area_new_m2"]),
                "building_roof_area_stock_exposure_m2": math.fsum(
                    slot["roof_area_stock_exposure_m2"]
                ),
            }
        )
    return transition_rows, {
        "building_identity_count": row_count,
        "anchor_building_roof_mask_area_m2": math.fsum(total_anchor_area_values),
        "narrow_membership_mask_count": sum(source_mask_counts["narrow"].values()),
        "outside_membership_mask_count": (
            sum(source_mask_counts.get("outside", Counter()).values())
        ),
        "paired_building_count": len(seen_pairs),
        "all_buildings_have_positive_roof_area": True,
        "all_building_mask_counts_reconcile": True,
    }


def index_rows(
    rows: Iterable[dict[str, str]], key_fields: tuple[str, ...]
) -> dict[tuple[str, ...], dict[str, str]]:
    result: dict[tuple[str, ...], dict[str, str]] = {}
    for row in rows:
        key = tuple(row[field] for field in key_fields)
        if key in result:
            raise ValueError(f"Duplicate input-table key: {key}")
        result[key] = row
    return result


def enrich_transition(
    roof: dict[str, Any], area: dict[str, str], status: str
) -> dict[str, Any]:
    for field in ("n_new", "y_new", "n_stock", "y_retrofit"):
        if roof[field] != int(area[field]):
            raise ValueError(
                f"Count mismatch for {roof['city_id']}/{roof['scope']}/"
                f"{roof['transition_index']}/{field}"
            )
    area_new = float(area["pv_area_new_m2"])
    area_existing = float(area["pv_area_retrofit_m2"])
    roof_new = float(roof["building_roof_area_new_m2"])
    roof_existing = float(roof["building_roof_area_stock_exposure_m2"])
    yield_new = safe_ratio(area_new, roof_new)
    yield_existing = safe_ratio(area_existing, roof_existing)
    roof_rr = (
        safe_ratio(yield_new, yield_existing)
        if (
            yield_new is not None
            and yield_existing is not None
            and area_new > 0
            and area_existing > 0
        )
        else None
    )
    return {
        **roof,
        "pv_area_new_m2": area_new,
        "pv_area_retrofit_m2": area_existing,
        "pv_area_yield_new_m2_per_building_roof_m2": finite_or_blank(yield_new),
        "pv_area_yield_retrofit_m2_per_building_roof_m2_exposure": finite_or_blank(
            yield_existing
        ),
        "roof_area_yield_rr_new_to_retrofit": finite_or_blank(roof_rr),
        "count_rr_new_to_retrofit": area["count_rr_new_to_retrofit"],
        "building_count_area_yield_rr_new_to_retrofit": area[
            "area_yield_rr_new_to_retrofit"
        ],
        "new_roof_denominator_definition": "plan-view anchor SAM3 roof-mask area summed over Buildings entering the strict raw-known new-Building risk group",
        "existing_roof_denominator_definition": "plan-view anchor SAM3 roof-mask area summed over eligible existing-Building observations across native adjacent cohort transitions (roof-area--cohort exposure)",
        "estimand_warning": "not usable-roof utilization, realized coverage, annual uptake, or exact cohort capacity addition",
        "status": status,
    }


def aggregate_city_rows(
    transitions: list[dict[str, Any]], city_area: dict[str, str], status: str
) -> dict[str, Any]:
    count_fields = ("n_new", "y_new", "n_stock", "y_retrofit")
    totals = {field: sum(int(row[field]) for row in transitions) for field in count_fields}
    for field in count_fields:
        if totals[field] != int(city_area[field]):
            raise ValueError(
                f"City aggregation mismatch for {city_area['city_id']}/"
                f"{city_area['scope']}/{field}"
            )
    area_new = math.fsum(float(row["pv_area_new_m2"]) for row in transitions)
    area_existing = math.fsum(float(row["pv_area_retrofit_m2"]) for row in transitions)
    roof_new = math.fsum(float(row["building_roof_area_new_m2"]) for row in transitions)
    roof_existing = math.fsum(
        float(row["building_roof_area_stock_exposure_m2"]) for row in transitions
    )
    if not math.isclose(area_new, float(city_area["pv_area_new_m2"]), rel_tol=0, abs_tol=1e-6):
        raise ValueError("City new-PV-area aggregation mismatch")
    if not math.isclose(
        area_existing, float(city_area["pv_area_retrofit_m2"]), rel_tol=0, abs_tol=1e-6
    ):
        raise ValueError("City existing-PV-area aggregation mismatch")
    yield_new = safe_ratio(area_new, roof_new)
    yield_existing = safe_ratio(area_existing, roof_existing)
    roof_rr = (
        safe_ratio(yield_new, yield_existing)
        if (
            yield_new is not None
            and yield_existing is not None
            and area_new > 0
            and area_existing > 0
        )
        else None
    )
    return {
        "city_id": city_area["city_id"],
        "scope": city_area["scope"],
        "cohort_count": int(city_area["cohort_count"]),
        "transition_count": int(city_area["transition_count"]),
        **totals,
        "pv_area_new_m2": area_new,
        "pv_area_retrofit_m2": area_existing,
        "building_roof_area_new_m2": roof_new,
        "building_roof_area_stock_exposure_m2": roof_existing,
        "pv_area_yield_new_m2_per_building_roof_m2": finite_or_blank(yield_new),
        "pv_area_yield_retrofit_m2_per_building_roof_m2_exposure": finite_or_blank(
            yield_existing
        ),
        "roof_area_yield_rr_new_to_retrofit": finite_or_blank(roof_rr),
        "count_rr_new_to_retrofit": city_area["count_rr_new_to_retrofit"],
        "building_count_area_yield_rr_new_to_retrofit": city_area[
            "area_yield_rr_new_to_retrofit"
        ],
        "pooling_definition": "city row sums native transition numerators and route-specific roof-area denominators before division",
        "new_roof_denominator_definition": "plan-view anchor SAM3 roof-mask area summed over Buildings entering the strict raw-known new-Building risk group",
        "existing_roof_denominator_definition": "plan-view anchor SAM3 roof-mask area summed over eligible existing-Building observations across native adjacent cohort transitions (roof-area--cohort exposure)",
        "estimand_warning": "not usable-roof utilization, realized coverage, annual uptake, or exact cohort capacity addition",
        "status": status,
    }


def pooled_row(rows: list[dict[str, Any]], scope: str, status: str) -> dict[str, Any]:
    selected = [row for row in rows if row["scope"] == scope and row["city_id"] != "all_cities_pooled"]
    counts = {
        field: sum(int(row[field]) for row in selected)
        for field in ("n_new", "y_new", "n_stock", "y_retrofit")
    }
    area_new = math.fsum(float(row["pv_area_new_m2"]) for row in selected)
    area_existing = math.fsum(float(row["pv_area_retrofit_m2"]) for row in selected)
    roof_new = math.fsum(float(row["building_roof_area_new_m2"]) for row in selected)
    roof_existing = math.fsum(
        float(row["building_roof_area_stock_exposure_m2"]) for row in selected
    )
    event_new = safe_ratio(counts["y_new"], counts["n_new"])
    event_existing = safe_ratio(counts["y_retrofit"], counts["n_stock"])
    area_count_new = safe_ratio(area_new, counts["n_new"])
    area_count_existing = safe_ratio(area_existing, counts["n_stock"])
    roof_yield_new = safe_ratio(area_new, roof_new)
    roof_yield_existing = safe_ratio(area_existing, roof_existing)
    return {
        "city_id": "all_cities_pooled",
        "scope": scope,
        "cohort_count": sum(int(row["cohort_count"]) for row in selected),
        "transition_count": sum(int(row["transition_count"]) for row in selected),
        **counts,
        "pv_area_new_m2": area_new,
        "pv_area_retrofit_m2": area_existing,
        "building_roof_area_new_m2": roof_new,
        "building_roof_area_stock_exposure_m2": roof_existing,
        "pv_area_yield_new_m2_per_building_roof_m2": finite_or_blank(roof_yield_new),
        "pv_area_yield_retrofit_m2_per_building_roof_m2_exposure": finite_or_blank(
            roof_yield_existing
        ),
        "roof_area_yield_rr_new_to_retrofit": finite_or_blank(
            safe_ratio(roof_yield_new, roof_yield_existing)
            if (
                roof_yield_new is not None
                and roof_yield_existing is not None
                and area_new > 0
                and area_existing > 0
            )
            else None
        ),
        "count_rr_new_to_retrofit": finite_or_blank(
            safe_ratio(event_new, event_existing)
            if event_new is not None and event_existing is not None
            else None
        ),
        "building_count_area_yield_rr_new_to_retrofit": finite_or_blank(
            safe_ratio(area_count_new, area_count_existing)
            if area_count_new is not None and area_count_existing is not None
            else None
        ),
        "pooling_definition": "count/area-summed across cities and native transitions before division; not an unweighted city mean or cross-city model",
        "new_roof_denominator_definition": "plan-view anchor SAM3 roof-mask area summed over Buildings entering the strict raw-known new-Building risk group",
        "existing_roof_denominator_definition": "plan-view anchor SAM3 roof-mask area summed over eligible existing-Building observations across native adjacent cohort transitions (roof-area--cohort exposure)",
        "estimand_warning": "not usable-roof utilization, realized coverage, annual uptake, or exact cohort capacity addition",
        "status": status,
    }


def output_record(path: Path, primary_key: Any) -> dict[str, Any]:
    return {
        "path": str(path.resolve()),
        "sha256": sha256_file(path),
        "bytes": path.stat().st_size,
        "row_count": csv_row_count(path) if path.suffix == ".csv" else None,
        "primary_key": primary_key,
    }


def main() -> int:
    args = parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    major = json.loads(args.index.read_text(encoding="utf-8"))
    if major.get("status") != "complete" or not major.get("all_release_evidence_complete"):
        raise ValueError("Frozen major-results index is not complete")
    city_index = {row["city_id"]: row for row in major["cities"]}
    expected_cities = set(city_index)
    selected_cities = (
        {value.strip() for value in args.cities.split(",") if value.strip()}
        if args.cities
        else expected_cities
    )
    if not selected_cities or not selected_cities.issubset(expected_cities):
        raise ValueError("Invalid --cities selection")
    release_status = "REPRODUCED" if selected_cities == expected_cities else "PRELIMINARY"

    risk_manifest = json.loads(args.risk_manifest.read_text(encoding="utf-8"))
    area_manifest = json.loads(args.area_manifest.read_text(encoding="utf-8"))
    if risk_manifest.get("status") != "REPRODUCED" or area_manifest.get("status") != "REPRODUCED":
        raise ValueError("Required paper-analysis manifests are not REPRODUCED")
    risk_inputs, provenance_inputs = resolve_risk_inputs(risk_manifest, expected_cities)
    area_sources = load_area_sources(args.area_sources)
    if set(area_sources) != expected_cities:
        raise ValueError("Area-source config and frozen city index disagree")

    expected_outputs = area_manifest["outputs"]
    city_expected = expected_outputs["city_area_weighted_stock_flow"]
    transition_expected = expected_outputs["city_transition_area_weighted_stock_flow"]
    trajectory_input = next(
        item
        for item in area_manifest["inputs"]
        if item.get("role") == "area_trajectory"
    )
    base_inputs = [
        input_record("frozen_major_results_index", args.index, primary_key="city_id"),
        input_record(
            "frozen_artifact_results_index",
            args.artifact_index,
            primary_key=["city_id", "name"],
        ),
        input_record("risk_evidence_manifest", args.risk_manifest),
        input_record("area_weighted_results_manifest", args.area_manifest),
        input_record("anchor_area_source_config", args.area_sources, primary_key="city_id"),
        input_record(
            "city_area_weighted_stock_flow",
            args.city_area_table,
            expected_sha256=city_expected["sha256"],
            expected_rows=city_expected["row_count"],
            primary_key=["city_id", "scope"],
            owner_manifest=args.area_manifest,
        ),
        input_record(
            "city_transition_area_weighted_stock_flow",
            args.transition_area_table,
            expected_sha256=transition_expected["sha256"],
            expected_rows=transition_expected["row_count"],
            primary_key=["city_id", "scope", "transition_index"],
            owner_manifest=args.area_manifest,
        ),
        input_record(
            "city_pv_building_area_trajectories",
            args.area_trajectory_table,
            expected_sha256=trajectory_input["sha256_expected"],
            expected_rows=trajectory_input["row_count_expected"],
            primary_key=["city_id", "calendar_year"],
            owner_manifest=args.area_manifest,
        ),
    ]
    input_records = base_inputs + provenance_inputs
    city_area_index = index_rows(load_csv(args.city_area_table), ("city_id", "scope"))
    transition_area_index = index_rows(
        load_csv(args.transition_area_table),
        ("city_id", "scope", "transition_index"),
    )
    trajectory_anchor_area: dict[str, float] = {}
    for row in load_csv(args.area_trajectory_table):
        value = float(row["anchor_building_area_m2"])
        prior = trajectory_anchor_area.setdefault(row["city_id"], value)
        if not math.isclose(prior, value, rel_tol=0, abs_tol=1e-8):
            raise ValueError(f"Nonconstant trajectory anchor area for {row['city_id']}")

    all_transition_rows: list[dict[str, Any]] = []
    city_diagnostics: list[dict[str, Any]] = []
    for ordinal, city_id in enumerate(sorted(selected_cities), start=1):
        print(f"[{ordinal:02d}/{len(selected_cities):02d}] {city_id}: resolving roof areas", flush=True)
        meta = risk_inputs[city_id]
        source = area_sources[city_id]
        cohorts = meta["cohort_order"]

        # Canonical narrow anchor-mask membership and geometry are already used
        # by the reproduced Figure 1 Building-area trajectory.
        narrow_membership_path = Path(source["building_membership_path"])
        narrow_geojson_path = Path(source["sam3_geojson_path"])
        narrow_map, narrow_counts, narrow_membership_diag = load_membership(
            narrow_membership_path,
            source["building_membership_sha256"],
            city_id,
            "narrow",
        )
        narrow_areas, narrow_area_diag = scan_mask_areas(
            narrow_geojson_path,
            source["sam3_geojson_sha256"],
            narrow_map,
            city_id,
            "narrow",
        )
        input_records.extend(
            [
                input_record(
                    "canonical_narrow_building_anchor_mask_membership",
                    narrow_membership_path,
                    expected_sha256=source["building_membership_sha256"],
                    primary_key="sam3_building_id",
                    owner_manifest=Path(source["building_membership_provenance_path"]),
                    city_id=city_id,
                ),
                input_record(
                    "canonical_narrow_anchor_sam3_roof_masks",
                    narrow_geojson_path,
                    expected_sha256=source["sam3_geojson_sha256"],
                    primary_key="sam3_building_id",
                    owner_manifest=Path(source["sam3_manifest_path"]),
                    city_id=city_id,
                ),
            ]
        )

        # The state-merge input binds the outside first-appearance artifact.
        # Its city root contains the hash-gated Stage 7B membership and anchor
        # SAM3 output named by the Stage 7B summary/anchor manifest.
        outside_first = meta["outside_building_first_appearance"]
        outside_summary = meta["outside_first_appearance_summary"]
        outside_first_path = Path(outside_first["path"])
        outside_summary_path = Path(outside_summary["path"])
        city_root = city_root_from_outside_path(outside_first_path, city_id)
        stage7_summary_path, stage7_summary_sha, outside_first_manifest_path = (
            resolve_outside_stage7_summary(outside_first_path, city_id)
        )
        stage7_root = stage7_summary_path.parent
        stage7_gate_path = city_root / "qa" / "stage7b_gate.json"
        stage7_gate: dict[str, Any] | None = None
        stage7_hashes: dict[str, str] = {}
        if stage7_gate_path.is_file():
            stage7_gate = json.loads(stage7_gate_path.read_text(encoding="utf-8"))
            if stage7_gate.get("status") != "pass" or stage7_gate.get("gate_passed") is False:
                raise ValueError(f"{city_id}: outside Stage 7B gate did not pass")
            raw_hashes = stage7_gate.get("hashes", stage7_gate.get("outputs_sha256", {}))
            if isinstance(raw_hashes, dict):
                stage7_hashes = raw_hashes
        outside_membership_path = stage7_root / "building_anchor_mask_membership.csv"
        outside_membership_sha = stage7_hashes.get("building_anchor_mask_membership.csv")
        anchor_candidates = [
            city_root / "sam3" / cohorts[-1] / "sam3_buildings.geojson",
            city_root
            / "sam3_v4_outside_narrow"
            / cohorts[-1]
            / "sam3_buildings.geojson",
        ]
        existing_anchor_candidates = [path for path in anchor_candidates if path.is_file()]
        if len(existing_anchor_candidates) != 1:
            raise ValueError(
                f"{city_id}: expected exactly one known-schema outside anchor SAM3 source, "
                f"found {len(existing_anchor_candidates)}"
            )
        outside_geojson_path = existing_anchor_candidates[0]
        outside_geojson_manifest_path = outside_geojson_path.parent / "manifest.json"
        outside_geojson_manifest = json.loads(
            outside_geojson_manifest_path.read_text(encoding="utf-8")
        )
        if outside_geojson_manifest.get("status") != "complete":
            raise ValueError(f"{city_id}: outside anchor SAM3 manifest incomplete")
        outside_geojson_sha = outside_geojson_manifest["output_sha256"]
        if Path(outside_geojson_manifest["output"]).resolve() != outside_geojson_path.resolve():
            raise ValueError(f"{city_id}: outside anchor SAM3 output path mismatch")
        outside_map, outside_counts, outside_membership_diag = load_membership(
            outside_membership_path,
            outside_membership_sha,
            city_id,
            "outside",
        )
        duplicate_masks = set(narrow_map).intersection(outside_map)
        if duplicate_masks:
            raise ValueError(
                f"{city_id}: {len(duplicate_masks)} anchor mask IDs occur in both scopes"
            )
        outside_areas, outside_area_diag = scan_mask_areas(
            outside_geojson_path,
            outside_geojson_sha,
            outside_map,
            city_id,
            "outside",
        )
        input_records.extend(
            [
                input_record(
                    "outside_building_first_appearance",
                    outside_first_path,
                    expected_sha256=outside_first["sha256"],
                    expected_rows=outside_first["row_count"],
                    primary_key="production_building_id",
                    owner_manifest=meta["state_merge_manifest"],
                    city_id=city_id,
                ),
                input_record(
                    "outside_first_appearance_summary",
                    outside_summary_path,
                    expected_sha256=outside_summary["sha256"],
                    owner_manifest=meta["state_merge_manifest"],
                    city_id=city_id,
                ),
                input_record(
                    "outside_first_appearance_manifest",
                    outside_first_manifest_path,
                    city_id=city_id,
                ),
                input_record(
                    "outside_stage7b_summary",
                    stage7_summary_path,
                    expected_sha256=stage7_summary_sha,
                    owner_manifest=outside_first_manifest_path,
                    city_id=city_id,
                ),
                input_record(
                    "outside_building_anchor_mask_membership",
                    outside_membership_path,
                    expected_sha256=outside_membership_sha,
                    primary_key="sam3_building_id",
                    owner_manifest=(
                        stage7_gate_path if stage7_gate is not None else stage7_summary_path
                    ),
                    city_id=city_id,
                ),
                input_record(
                    "outside_anchor_sam3_manifest",
                    outside_geojson_manifest_path,
                    city_id=city_id,
                ),
                input_record(
                    "outside_anchor_sam3_roof_masks",
                    outside_geojson_path,
                    expected_sha256=outside_geojson_sha,
                    primary_key="sam3_building_id",
                    owner_manifest=outside_geojson_manifest_path,
                    city_id=city_id,
                ),
            ]
        )
        if stage7_gate is not None:
            input_records.append(
                input_record(
                    "outside_stage7b_gate",
                    stage7_gate_path,
                    city_id=city_id,
                )
            )

        combined_areas = dict(narrow_areas)
        for building_id, area in outside_areas.items():
            combined_areas[building_id] = combined_areas.get(building_id, 0.0) + area
        pairs = meta["unique_pv_building_pairs"]
        pair_events, pair_diag = load_pair_events(
            Path(pairs["path"]), pairs["sha256"], pairs["row_count"], city_id
        )
        input_records.append(
            input_record(
                "canonical_unique_pv_building_pairs",
                Path(pairs["path"]),
                expected_sha256=pairs["sha256"],
                expected_rows=pairs["row_count"],
                primary_key="production_building_id",
                owner_manifest=meta["risk_release_manifest"],
                city_id=city_id,
            )
        )

        scope_diags: dict[str, Any] = {}
        for scope, area_map, counts_by_source in (
            ("narrow", narrow_areas, {"narrow": narrow_counts}),
            (
                "full_aoi",
                combined_areas,
                {"narrow": narrow_counts, "outside": outside_counts},
            ),
        ):
            building = meta[f"{scope}_building"]
            building_path = Path(building["path"])
            rows, scope_diag = estimate_roof_denominators(
                city_id,
                scope,
                building_path,
                building["sha256"],
                building["row_count"],
                cohorts,
                area_map,
                counts_by_source,
                pair_events,
            )
            input_records.append(
                input_record(
                    f"{scope}_building_strict_risk_source",
                    building_path,
                    expected_sha256=building["sha256"],
                    expected_rows=building["row_count"],
                    primary_key="production_building_id",
                    owner_manifest=meta["risk_release_manifest"],
                    city_id=city_id,
                )
            )
            for row in rows:
                key = (city_id, scope, str(row["transition_index"]))
                all_transition_rows.append(
                    enrich_transition(row, transition_area_index[key], release_status)
                )
            scope_diags[scope] = scope_diag
        city_diagnostics.append(
            {
                "city_id": city_id,
                "cohort_order": cohorts,
                "narrow_membership": narrow_membership_diag,
                "narrow_anchor_area": narrow_area_diag,
                "outside_membership": outside_membership_diag,
                "outside_anchor_area": outside_area_diag,
                "cross_scope_duplicate_anchor_mask_count": 0,
                "narrow_anchor_area_reproduces_existing_trajectory": math.isclose(
                    scope_diags["narrow"]["anchor_building_roof_mask_area_m2"],
                    trajectory_anchor_area[city_id],
                    rel_tol=0,
                    abs_tol=1e-4,
                ),
                "narrow_anchor_area_minus_existing_trajectory_m2": (
                    scope_diags["narrow"]["anchor_building_roof_mask_area_m2"]
                    - trajectory_anchor_area[city_id]
                ),
                "pair_events": pair_diag,
                "scopes": scope_diags,
            }
        )
        del narrow_map, outside_map, narrow_areas, outside_areas, combined_areas

    all_transition_rows.sort(
        key=lambda row: (row["scope"], row["city_id"], row["transition_index"])
    )
    city_rows: list[dict[str, Any]] = []
    for scope in ("narrow", "full_aoi"):
        for city_id in sorted(selected_cities):
            selected = [
                row
                for row in all_transition_rows
                if row["scope"] == scope and row["city_id"] == city_id
            ]
            city_rows.append(
                aggregate_city_rows(
                    selected, city_area_index[(city_id, scope)], release_status
                )
            )
    if selected_cities == expected_cities:
        city_rows.extend(
            pooled_row(city_rows, scope, release_status)
            for scope in ("narrow", "full_aoi")
        )

    city_path = args.output_dir / "city_roof_area_weighted_stock_flow.csv"
    transition_path = args.output_dir / "city_transition_roof_area_weighted_stock_flow.csv"
    checks_path = args.output_dir / "roof_area_weighted_results_checks.json"
    manifest_path = args.output_dir / "roof_area_weighted_results_manifest.json"
    write_csv(city_path, city_rows)
    write_csv(transition_path, all_transition_rows)

    full_rows = [
        row
        for row in city_rows
        if row["scope"] == "full_aoi" and row["city_id"] != "all_cities_pooled"
    ]
    transition_expected_count = sum(
        len(risk_inputs[city_id]["cohort_order"]) - 1 for city_id in selected_cities
    )
    checks = {
        "schema_version": "rpv-roof-area-weighted-results-checks/v1",
        "status": "pass",
        "evidence_status": release_status,
        "city_count": len(selected_cities),
        "checks": {
            "all_requested_cities_processed": len(city_diagnostics) == len(selected_cities),
            "full_release_has_15_cities": (
                len(full_rows) == 15 if release_status == "REPRODUCED" else None
            ),
            "transition_count_matches_native_grids": len(all_transition_rows)
            == 2 * transition_expected_count,
            "all_buildings_have_positive_roof_area": all(
                scope["all_buildings_have_positive_roof_area"]
                for city in city_diagnostics
                for scope in city["scopes"].values()
            ),
            "all_building_mask_counts_reconcile": all(
                scope["all_building_mask_counts_reconcile"]
                for city in city_diagnostics
                for scope in city["scopes"].values()
            ),
            "narrow_and_outside_anchor_mask_ids_disjoint": all(
                city["cross_scope_duplicate_anchor_mask_count"] == 0
                for city in city_diagnostics
            ),
            "narrow_anchor_area_reproduces_existing_area_trajectory": all(
                city["narrow_anchor_area_reproduces_existing_trajectory"]
                for city in city_diagnostics
            ),
            "strict_risk_counts_reproduce_area_weighted_tables": True,
            "city_sums_reproduce_transition_counts_and_pv_areas": True,
            "zero_denominators_are_blank_not_continuity_corrected": True,
            "existing_denominator_is_roof_area_cohort_exposure": True,
        },
        "failed_checks": [],
        "city_diagnostics": city_diagnostics,
    }
    for name, value in checks["checks"].items():
        if value is False:
            checks["failed_checks"].append(name)
    if checks["failed_checks"]:
        checks["status"] = "fail"
        raise ValueError(f"Final QA failed: {checks['failed_checks']}")
    write_json(checks_path, checks)

    outputs = {
        "city_roof_area_weighted_stock_flow": output_record(
            city_path, ["city_id", "scope"]
        ),
        "city_transition_roof_area_weighted_stock_flow": output_record(
            transition_path, ["city_id", "scope", "transition_index"]
        ),
        "roof_area_weighted_results_checks": output_record(checks_path, None),
    }
    manifest = {
        "schema_version": "rpv-roof-area-weighted-results-manifest/v1",
        "status": release_status,
        "generated_at_utc": utc_now(),
        "generator": {
            "path": str(Path(__file__).resolve()),
            "sha256": sha256_file(Path(__file__).resolve()),
            "version": SCRIPT_VERSION,
        },
        "command": "python3 scripts/build_roof_area_weighted_stock_flow.py",
        "city_count": len(selected_cities),
        "cohort_order_by_city": {
            city_id: risk_inputs[city_id]["cohort_order"]
            for city_id in sorted(selected_cities)
        },
        "primary_estimand": "(strict-event anchor PV union area / plan-view anchor SAM3 roof-mask area entering the new-Building risk group) divided by (strict-event anchor PV union area / eligible existing-Building roof-area--cohort exposure)",
        "filters_and_exclusions": {
            "building_new": "raw-known adjacent A-to-P Building transition; PAU interval spans exactly one native cohort step",
            "building_existing": "raw-known adjacent P-to-P Building transition",
            "pv_event": "first accepted linked PV interval spans exactly one native cohort step",
            "at_risk": "no accepted linked PV onset before the current transition",
            "unknown": "U is never converted to A and transitions do not bridge U or missing cohorts",
            "area": "sum plan-view anchor SAM3 roof-mask area assigned to each canonical production Building",
        },
        "denominator_definitions": {
            "new": "anchor roof-mask m2 summed once when a Building enters the strict new-Building risk group",
            "existing": "anchor roof-mask m2 repeated for each native adjacent transition in which the Building is an eligible P-to-P observation; roof-area--cohort exposure",
            "limitations": "neither denominator is usable roof surface, realized coverage, annual exposure, or a historical citywide roof census",
        },
        "inputs": input_records,
        "outputs": outputs,
        "qa": {
            "path": str(checks_path.resolve()),
            "sha256": outputs["roof_area_weighted_results_checks"]["sha256"],
            "status": checks["status"],
        },
    }
    write_json(manifest_path, manifest)
    print(
        json.dumps(
            {
                "status": release_status,
                "city_count": len(selected_cities),
                "city_rows": len(city_rows),
                "transition_rows": len(all_transition_rows),
                "outputs": {key: value["path"] for key, value in outputs.items()},
            },
            indent=2,
        ),
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
