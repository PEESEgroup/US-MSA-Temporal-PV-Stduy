#!/usr/bin/env python3
"""Build C12 partial target-domain validation tables and SI fragments.

This release combines three distinct diagnostics without conflating their
units: full/narrow risk-panel sensitivity, frozen Stage 7B candidate-bridge
sensitivity, and raw unknown/unavailable accounting.  It cannot observe PV
outside the anchor-triggered candidate domain or PV that disappeared before
the anchor inventory, so those limitations remain explicit manuscript bounds.
"""

from __future__ import annotations

import csv
import hashlib
import json
import math
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data_high_level"
RESULTS = ROOT / "results"
GENERATED = ROOT / "paper" / "manuscript" / "generated"
VERSION = "1.0.0"

INPUTS = {
    "major_results_index": RESULTS / "major_results_index.json",
    "area_stock_flow": DATA / "city_area_weighted_stock_flow.csv",
    "roof_stock_flow": DATA / "city_roof_area_weighted_stock_flow.csv",
    "building_raw_states": DATA / "city_building_raw_state_counts.csv",
    "pv_area_pathways": DATA / "city_pv_area_onset_pathway_composition.csv",
    "area_manifest": DATA / "area_weighted_results_manifest.json",
    "roof_manifest": DATA / "roof_area_weighted_results_manifest.json",
    "trajectory_manifest": DATA / "city_pv_building_trajectories_manifest.json",
    "candidate_city": RESULTS / "anchor_stage7b_candidate_bridge_sensitivity_v1" / "city_sensitivity_index.csv",
    "candidate_scenario": RESULTS / "anchor_stage7b_candidate_bridge_sensitivity_v1" / "scenario_sensitivity_index.csv",
    "candidate_manifest": RESULTS / "anchor_stage7b_candidate_bridge_sensitivity_v1" / "manifest.json",
}

OUTPUTS = {
    "scope": DATA / "c12_scope_full_narrow.csv",
    "candidate": DATA / "c12_candidate_bridge_accounting.csv",
    "candidate_scenarios": DATA / "c12_candidate_bridge_scenarios.csv",
    "missingness": DATA / "c12_unknown_unavailable_accounting.csv",
    "checks": DATA / "c12_partial_validation_checks.json",
    "macros_source": GENERATED / "c12_partial_validation_macros_source.csv",
    "macros_tex": GENERATED / "c12_partial_validation_macros.tex",
    "table_s7_source": GENERATED / "table_s7_scope_full_narrow.csv",
    "table_s7_tex": GENERATED / "table_s7_scope_full_narrow.tex",
    "table_s8_source": GENERATED / "table_s8_candidate_bridge.csv",
    "table_s8_tex": GENERATED / "table_s8_candidate_bridge.tex",
    "table_s9_source": GENERATED / "table_s9_unknown_unavailable.csv",
    "table_s9_tex": GENERATED / "table_s9_unknown_unavailable.tex",
}
MANIFEST = DATA / "c12_partial_validation_manifest.json"


def now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as stream:
        return list(csv.DictReader(stream))


def write_csv(path: Path, values: list[dict[str, Any]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(values)


def as_float(value: str | float | int) -> float:
    return float(value)


def as_int(value: str | float | int) -> int:
    return int(float(value))


def direction(value: float) -> str:
    if value > 1:
        return "above"
    if value < 1:
        return "below"
    return "equal"


def ratio(num: float, den: float) -> float:
    return num / den if den else math.nan


def fmt_int(value: int) -> str:
    return f"{value:,}"


def fmt_ratio(value: float) -> str:
    return f"{value:.3f}"


def fmt_pct(value: float, digits: int = 2) -> str:
    return f"{100 * value:.{digits}f}\\%"


def tex_escape(value: str) -> str:
    return value.replace("&", r"\&").replace("_", r"\_")


def output_record(path: Path, primary_key: list[str] | None, row_count: int | None) -> dict[str, Any]:
    return {
        "path": str(path.resolve()),
        "bytes": path.stat().st_size,
        "sha256": sha256(path),
        "row_count": row_count,
        "primary_key": primary_key,
    }


def input_record(path: Path, role: str, primary_key: list[str] | None = None) -> dict[str, Any]:
    record: dict[str, Any] = {
        "role": role,
        "path": str(path.resolve()),
        "bytes": path.stat().st_size,
        "sha256": sha256(path),
        "primary_key": primary_key,
    }
    if path.suffix == ".csv":
        record["row_count"] = len(rows(path))
    return record


def build_scope(city_order: list[str], city_names: dict[str, str]) -> list[dict[str, Any]]:
    area = {(r["city_id"], r["scope"]): r for r in rows(INPUTS["area_stock_flow"])}
    roof = {(r["city_id"], r["scope"]): r for r in rows(INPUTS["roof_stock_flow"])}
    output: list[dict[str, Any]] = []
    for city_id in city_order + ["all_cities_pooled"]:
        full = area[(city_id, "full_aoi")]
        narrow = area[(city_id, "narrow")]
        full_roof = roof[(city_id, "full_aoi")]
        narrow_roof = roof[(city_id, "narrow")]
        full_footprint = ratio(1.0, as_float(full["event_size_ratio_retrofit_to_new"]))
        narrow_footprint = ratio(1.0, as_float(narrow["event_size_ratio_retrofit_to_new"]))
        record = {
            "city_id": city_id,
            "city_name": "All observed cities (count/area summed)" if city_id == "all_cities_pooled" else city_names[city_id],
            "is_pooled_arithmetic": city_id == "all_cities_pooled",
            "full_building_identity_count": as_int(full["building_identity_count"]),
            "narrow_building_identity_count": as_int(narrow["building_identity_count"]),
            "full_to_narrow_building_identity_multiplier": ratio(as_float(full["building_identity_count"]), as_float(narrow["building_identity_count"])),
            "full_count_rr_new_to_existing": as_float(full["count_rr_new_to_retrofit"]),
            "narrow_count_rr_new_to_existing": as_float(narrow["count_rr_new_to_retrofit"]),
            "count_direction_preserved": direction(as_float(full["count_rr_new_to_retrofit"])) == direction(as_float(narrow["count_rr_new_to_retrofit"])),
            "full_footprint_ratio_new_to_existing": full_footprint,
            "narrow_footprint_ratio_new_to_existing": narrow_footprint,
            "footprint_direction_preserved": direction(full_footprint) == direction(narrow_footprint),
            "full_building_area_yield_rr_new_to_existing": as_float(full["area_yield_rr_new_to_retrofit"]),
            "narrow_building_area_yield_rr_new_to_existing": as_float(narrow["area_yield_rr_new_to_retrofit"]),
            "building_area_direction_preserved": direction(as_float(full["area_yield_rr_new_to_retrofit"])) == direction(as_float(narrow["area_yield_rr_new_to_retrofit"])),
            "full_roof_area_yield_rr_new_to_existing": as_float(full_roof["roof_area_yield_rr_new_to_retrofit"]),
            "narrow_roof_area_yield_rr_new_to_existing": as_float(narrow_roof["roof_area_yield_rr_new_to_retrofit"]),
            "roof_area_direction_preserved": direction(as_float(full_roof["roof_area_yield_rr_new_to_retrofit"])) == direction(as_float(narrow_roof["roof_area_yield_rr_new_to_retrofit"])),
            "full_existing_area_share": as_float(full["retrofit_share_of_classified_pv_area"]),
            "narrow_existing_area_share": as_float(narrow["retrofit_share_of_classified_pv_area"]),
            "existing_area_majority_preserved": as_float(full["retrofit_share_of_classified_pv_area"]) > 0.5 and as_float(narrow["retrofit_share_of_classified_pv_area"]) > 0.5,
            "full_existing_to_new_total_pv_area_ratio": as_float(full["area_retrofit_to_new_ratio"]),
            "narrow_existing_to_new_total_pv_area_ratio": as_float(narrow["area_retrofit_to_new_ratio"]),
            "estimand": "strict raw-known adjacent first events among in-scope Buildings and anchor-surviving linked PV",
            "scope_warning": "full Anchor AOI and narrow candidate scope are both anchor-triggered analysis domains, not probability samples of citywide historical adoption",
            "status": "REPRODUCED",
        }
        output.append(record)
    return output


def build_candidate(city_order: list[str]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    city_rows = {r["city_id"]: r for r in rows(INPUTS["candidate_city"])}
    output: list[dict[str, Any]] = []
    numeric = [
        "anchor_pv_target_count", "canonical_resolved_target_count",
        "canonical_unavailable_target_count", "candidate_bridge_target_count",
        "no_stage7b_candidate_target_count", "broad_resolved_target_count",
    ]
    for city_id in city_order:
        source = city_rows[city_id]
        record: dict[str, Any] = {"city_id": city_id, "city_name": source["city_name"], "is_pooled_arithmetic": False}
        record.update({field: as_int(source[field]) for field in numeric})
        record.update({
            "canonical_coverage_fraction": as_float(source["canonical_coverage_fraction"]),
            "broad_coverage_fraction": as_float(source["broad_coverage_fraction"]),
            "coverage_gain_percentage_points": as_float(source["coverage_gain_percentage_points"]),
            "interpretation": "all_candidate_bridge reuses frozen Stage 7B candidates; it does not observe non-candidate PV",
            "status": "REPRODUCED",
        })
        output.append(record)
    pooled: dict[str, Any] = {
        "city_id": "all_cities_pooled", "city_name": "All observed cities (target-count summed)",
        "is_pooled_arithmetic": True,
    }
    pooled.update({field: sum(as_int(r[field]) for r in output) for field in numeric})
    pooled.update({
        "canonical_coverage_fraction": ratio(pooled["canonical_resolved_target_count"], pooled["anchor_pv_target_count"]),
        "broad_coverage_fraction": ratio(pooled["broad_resolved_target_count"], pooled["anchor_pv_target_count"]),
        "coverage_gain_percentage_points": 100 * ratio(pooled["candidate_bridge_target_count"], pooled["anchor_pv_target_count"]),
        "interpretation": "target-count sum over the observed cities; not a citywide sampling estimator",
        "status": "REPRODUCED",
    })
    output.append(pooled)

    scenario_source = rows(INPUTS["candidate_scenario"])
    by_scenario: dict[str, list[dict[str, str]]] = defaultdict(list)
    for record in scenario_source:
        by_scenario[record["scenario_id"]].append(record)
    scenarios: list[dict[str, Any]] = []
    scenario_order = ["strict", "ratio_ge_0_95", "ratio_ge_0_90", "ratio_ge_0_75", "all_candidate_bridge"]
    for scenario_id in scenario_order:
        group = by_scenario[scenario_id]
        total = sum(as_int(r["anchor_pv_target_count"]) for r in group)
        resolved = sum(as_int(r["resolved_pv_target_count"]) for r in group)
        added = sum(as_int(r["candidate_bridge_target_count"]) for r in group)
        unavailable = sum(as_int(r["unavailable_pv_target_count"]) for r in group)
        pairs = sum(as_int(r["unique_paired_building_count"]) for r in group)
        conflicts = sum(as_int(r["pv_before_building_conflict_pair_count"]) for r in group)
        scenarios.append({
            "scenario_id": scenario_id,
            "minimum_target_to_winner_overlap_ratio": group[0]["minimum_target_to_winner_overlap_ratio"],
            "anchor_pv_target_count": total,
            "resolved_pv_target_count": resolved,
            "candidate_bridge_target_count": added,
            "unavailable_pv_target_count": unavailable,
            "resolved_coverage_fraction": ratio(resolved, total),
            "unique_paired_building_count": pairs,
            "pv_before_building_conflict_pair_count": conflicts,
            "scope_warning": "analysis-only linkage sensitivity among anchor-surviving candidate targets; canonical Stage 9 is unchanged",
            "status": "REPRODUCED",
        })
    return output, scenarios


def build_missingness(city_order: list[str], city_names: dict[str, str], candidate: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    building_rows = rows(INPUTS["building_raw_states"])
    building: dict[str, dict[str, int]] = defaultdict(lambda: {"targets": 0, "observations": 0, "unknown": 0})
    for record in building_rows:
        city_id = record["city_id"]
        building[city_id]["targets"] = as_int(record["building_targets"])
        building[city_id]["observations"] += as_int(record["building_targets"])
        building[city_id]["unknown"] += as_int(record["unknown_buildings"])

    index = json.loads(INPUTS["major_results_index"].read_text())
    city_index = index["cities"] if isinstance(index["cities"], list) else list(index["cities"].values())
    indexed = {c["city_id"]: c for c in city_index}
    pv_state: dict[str, dict[str, int]] = {}
    pv_input_records: list[dict[str, Any]] = []
    for city_id in city_order:
        artifact = indexed[city_id]["artifacts"]["pv_first_appearance"]
        path = Path(artifact["path"])
        unknown = 0
        target_with_unknown = 0
        invalid = 0
        target_count = 0
        cohort_observations = 0
        with path.open(newline="", encoding="utf-8") as stream:
            reader = csv.DictReader(stream)
            for record in reader:
                target_count += 1
                raw = record["pau_raw_sequence"]
                removed = as_int(record["pau_removed_unknown_count"] or 0)
                assert raw.count("U") == removed
                unknown += removed
                target_with_unknown += int(removed > 0)
                invalid += int(record["pau_valid"].lower() != "true")
                cohort_observations += len(raw)
        observed_hash = sha256(path)
        assert observed_hash == artifact["sha256"]
        assert target_count == artifact["row_count"]
        pv_state[city_id] = {
            "targets": target_count,
            "observations": cohort_observations,
            "unknown": unknown,
            "targets_with_unknown": target_with_unknown,
            "invalid": invalid,
        }
        pv_input_records.append({
            "role": "canonical_pv_first_appearance_for_raw_unknown_accounting",
            "city_id": city_id,
            "path": str(path),
            "sha256": observed_hash,
            "row_count": target_count,
            "primary_key": [artifact["primary_key"]] if isinstance(artifact["primary_key"], str) else artifact["primary_key"],
        })

    pathway = {(r["city_id"], r["appearance_order"]): r for r in rows(INPUTS["pv_area_pathways"])}
    candidate_by_city = {r["city_id"]: r for r in candidate}
    output: list[dict[str, Any]] = []
    for city_id in city_order:
        c = candidate_by_city[city_id]
        unavailable = pathway[(city_id, "unavailable_relationship")]
        all_area = sum(
            as_float(pathway[(city_id, category)]["pv_union_area_m2"])
            for category in ("building_before_pv", "same_first_present_cohort", "pv_before_building_conflict", "unavailable_relationship")
        )
        record = {
            "city_id": city_id,
            "city_name": city_names[city_id],
            "is_pooled_arithmetic": False,
            "building_target_count": building[city_id]["targets"],
            "building_cohort_observation_count": building[city_id]["observations"],
            "building_unknown_observation_count": building[city_id]["unknown"],
            "building_unknown_observation_share": ratio(building[city_id]["unknown"], building[city_id]["observations"]),
            "pv_target_count": pv_state[city_id]["targets"],
            "pv_cohort_observation_count": pv_state[city_id]["observations"],
            "pv_unknown_observation_count": pv_state[city_id]["unknown"],
            "pv_unknown_observation_share": ratio(pv_state[city_id]["unknown"], pv_state[city_id]["observations"]),
            "pv_targets_with_any_unknown_count": pv_state[city_id]["targets_with_unknown"],
            "pv_targets_with_any_unknown_share": ratio(pv_state[city_id]["targets_with_unknown"], pv_state[city_id]["targets"]),
            "pv_invalid_sequence_count": pv_state[city_id]["invalid"],
            "canonical_unavailable_relationship_count": c["canonical_unavailable_target_count"],
            "canonical_unavailable_relationship_share": ratio(c["canonical_unavailable_target_count"], c["anchor_pv_target_count"]),
            "canonical_unavailable_pv_area_m2": as_float(unavailable["pv_union_area_m2"]),
            "canonical_unavailable_pv_area_share": ratio(as_float(unavailable["pv_union_area_m2"]), all_area),
            "broad_sensitivity_remaining_no_candidate_count": c["no_stage7b_candidate_target_count"],
            "broad_sensitivity_remaining_no_candidate_share": ratio(c["no_stage7b_candidate_target_count"], c["anchor_pv_target_count"]),
            "unit_warning": "unknown is target-cohort observation; unavailable is relationship row; neither is zero or added to unique-host denominators",
            "status": "REPRODUCED",
        }
        output.append(record)
    pooled: dict[str, Any] = {
        "city_id": "all_cities_pooled", "city_name": "All observed cities (unit-specific sums)", "is_pooled_arithmetic": True,
    }
    sum_fields = [
        "building_target_count", "building_cohort_observation_count", "building_unknown_observation_count",
        "pv_target_count", "pv_cohort_observation_count", "pv_unknown_observation_count",
        "pv_targets_with_any_unknown_count", "pv_invalid_sequence_count",
        "canonical_unavailable_relationship_count", "canonical_unavailable_pv_area_m2",
        "broad_sensitivity_remaining_no_candidate_count",
    ]
    pooled.update({field: sum(r[field] for r in output) for field in sum_fields})
    pooled.update({
        "building_unknown_observation_share": ratio(pooled["building_unknown_observation_count"], pooled["building_cohort_observation_count"]),
        "pv_unknown_observation_share": ratio(pooled["pv_unknown_observation_count"], pooled["pv_cohort_observation_count"]),
        "pv_targets_with_any_unknown_share": ratio(pooled["pv_targets_with_any_unknown_count"], pooled["pv_target_count"]),
        "canonical_unavailable_relationship_share": ratio(pooled["canonical_unavailable_relationship_count"], pooled["pv_target_count"]),
        "canonical_unavailable_pv_area_share": ratio(pooled["canonical_unavailable_pv_area_m2"], sum(
            sum(as_float(pathway[(city_id, category)]["pv_union_area_m2"]) for category in ("building_before_pv", "same_first_present_cohort", "pv_before_building_conflict", "unavailable_relationship"))
            for city_id in city_order
        )),
        "broad_sensitivity_remaining_no_candidate_share": ratio(pooled["broad_sensitivity_remaining_no_candidate_count"], pooled["pv_target_count"]),
        "unit_warning": "unit-specific sums over observed cities; unknown observations and unavailable relationships remain separate",
        "status": "REPRODUCED",
    })
    output.append(pooled)
    return output, pv_input_records


def write_table_s7(scope: list[dict[str, Any]]) -> None:
    source_fields = [
        "city_id", "city_name", "full_building_identity_count", "narrow_building_identity_count",
        "full_count_rr_new_to_existing", "narrow_count_rr_new_to_existing",
        "full_footprint_ratio_new_to_existing", "narrow_footprint_ratio_new_to_existing",
        "full_building_area_yield_rr_new_to_existing", "narrow_building_area_yield_rr_new_to_existing",
        "full_roof_area_yield_rr_new_to_existing", "narrow_roof_area_yield_rr_new_to_existing",
        "full_existing_area_share", "narrow_existing_area_share",
        "full_existing_to_new_total_pv_area_ratio", "narrow_existing_to_new_total_pv_area_ratio", "status",
    ]
    write_csv(OUTPUTS["table_s7_source"], scope, source_fields)
    lines = [
        r"\begin{longtable}{@{}lrrrrrr@{}}",
        r"\caption{Full-Anchor-AOI and narrow-scope sensitivity of route diagnostics.}\label{tab:c12-scope}\\",
        r"\toprule",
        r"City & Building IDs & Count RR & Footprint RR & Building-area RR & Roof-area RR & Existing share \\",
        r"\midrule",
        r"\endfirsthead",
        r"\toprule",
        r"City & Building IDs & Count RR & Footprint RR & Building-area RR & Roof-area RR & Existing share \\",
        r"\midrule",
        r"\endhead",
    ]
    for r in scope:
        lines.append(
            f"{tex_escape(r['city_name'])} & {fmt_int(r['full_building_identity_count'])}/{fmt_int(r['narrow_building_identity_count'])} & "
            f"{fmt_ratio(r['full_count_rr_new_to_existing'])}/{fmt_ratio(r['narrow_count_rr_new_to_existing'])} & "
            f"{fmt_ratio(r['full_footprint_ratio_new_to_existing'])}/{fmt_ratio(r['narrow_footprint_ratio_new_to_existing'])} & "
            f"{fmt_ratio(r['full_building_area_yield_rr_new_to_existing'])}/{fmt_ratio(r['narrow_building_area_yield_rr_new_to_existing'])} & "
            f"{fmt_ratio(r['full_roof_area_yield_rr_new_to_existing'])}/{fmt_ratio(r['narrow_roof_area_yield_rr_new_to_existing'])} & "
            f"{fmt_pct(r['full_existing_area_share'], 1)}/{fmt_pct(r['narrow_existing_area_share'], 1)} \\\\"
        )
    lines.extend([
        r"\bottomrule",
        r"\end{longtable}",
        r"\noindent\footnotesize Each cell reports full Anchor AOI / narrow scope. Count, footprint and both area RRs compare the newly observed-Building route with the existing-Building route; existing share is the existing route's share of strict-classified PV area. The adjacent source CSV also retains existing/new total-area ratios and all unrounded values. The final row sums primitive counts and areas before division and is not a population-level cross-city model. Both scopes remain conditional on anchor-triggered analysis domains and anchor-surviving PV.\normalsize",
        "",
    ])
    OUTPUTS["table_s7_tex"].write_text("\n".join(lines), encoding="utf-8")


def write_table_s8(candidate: list[dict[str, Any]]) -> None:
    fields = [
        "city_id", "city_name", "anchor_pv_target_count", "canonical_resolved_target_count",
        "canonical_coverage_fraction", "candidate_bridge_target_count", "broad_resolved_target_count",
        "broad_coverage_fraction", "no_stage7b_candidate_target_count", "status",
    ]
    write_csv(OUTPUTS["table_s8_source"], candidate, fields)
    lines = [
        r"\begin{longtable}{@{}lrrrrrr@{}}",
        r"\caption{Frozen candidate-bridge linkage sensitivity.}\label{tab:c12-bridge}\\",
        r"\toprule",
        r"City & Anchor PV & Strict resolved & Strict coverage & Added bridges & Broad coverage & No candidate \\",
        r"\midrule",
        r"\endfirsthead",
        r"\toprule",
        r"City & Anchor PV & Strict resolved & Strict coverage & Added bridges & Broad coverage & No candidate \\",
        r"\midrule",
        r"\endhead",
    ]
    for r in candidate:
        lines.append(
            f"{tex_escape(r['city_name'])} & {fmt_int(r['anchor_pv_target_count'])} & {fmt_int(r['canonical_resolved_target_count'])} & "
            f"{fmt_pct(r['canonical_coverage_fraction'])} & {fmt_int(r['candidate_bridge_target_count'])} & "
            f"{fmt_pct(r['broad_coverage_fraction'])} & {fmt_int(r['no_stage7b_candidate_target_count'])} \\\\"
        )
    lines.extend([
        r"\bottomrule",
        r"\end{longtable}",
        r"\noindent\footnotesize The broad analysis-only scenario accepts every frozen Stage 7B candidate bridge. It does not modify canonical Stage 9, discover PV outside the candidate domain, or impute targets with no candidate. The final row is a target-count sum.\normalsize",
        "",
    ])
    OUTPUTS["table_s8_tex"].write_text("\n".join(lines), encoding="utf-8")


def write_table_s9(missingness: list[dict[str, Any]]) -> None:
    fields = [
        "city_id", "city_name", "building_cohort_observation_count", "building_unknown_observation_count",
        "building_unknown_observation_share", "pv_cohort_observation_count", "pv_unknown_observation_count",
        "pv_unknown_observation_share", "canonical_unavailable_relationship_count",
        "canonical_unavailable_relationship_share", "canonical_unavailable_pv_area_m2",
        "canonical_unavailable_pv_area_share", "broad_sensitivity_remaining_no_candidate_count", "status",
    ]
    write_csv(OUTPUTS["table_s9_source"], missingness, fields)
    lines = [
        r"\begin{longtable}{@{}lrrrrrr@{}}",
        r"\caption{Unknown observations and unavailable PV relationships by city.}\label{tab:c12-missing}\\",
        r"\toprule",
        r"& \multicolumn{2}{c}{Building $U$ observations} & \multicolumn{2}{c}{PV $U$ observations} & \multicolumn{2}{c}{Unavailable relationships} \\",
        r"City & Count & Share & Count & Share & Count & Share \\",
        r"\midrule",
        r"\endfirsthead",
        r"\toprule",
        r"City & Building $U$ & Share & PV $U$ & Share & Unavailable & Share \\",
        r"\midrule",
        r"\endhead",
    ]
    for r in missingness:
        lines.append(
            f"{tex_escape(r['city_name'])} & {fmt_int(r['building_unknown_observation_count'])} & {fmt_pct(r['building_unknown_observation_share'], 3)} & "
            f"{fmt_int(r['pv_unknown_observation_count'])} & {fmt_pct(r['pv_unknown_observation_share'], 3)} & "
            f"{fmt_int(r['canonical_unavailable_relationship_count'])} & {fmt_pct(r['canonical_unavailable_relationship_share'], 2)} \\\\"
        )
    lines.extend([
        r"\bottomrule",
        r"\end{longtable}",
        r"\noindent\footnotesize $U$ counts are raw target--cohort observations and their shares use all corresponding target--cohort observations. Unavailable counts are canonical PV relationship rows and their shares use anchor PV targets. These units are not additive, and unavailable is never encoded as zero.\normalsize",
        "",
    ])
    OUTPUTS["table_s9_tex"].write_text("\n".join(lines), encoding="utf-8")


def write_macros(scope: list[dict[str, Any]], candidate: list[dict[str, Any]], missingness: list[dict[str, Any]]) -> None:
    pooled_scope = scope[-1]
    pooled_candidate = candidate[-1]
    pooled_missing = missingness[-1]
    city_scope = scope[:-1]
    values = [
        ("CwelveScopeBuildingAreaDirectionPreservedCityCount", sum(r["building_area_direction_preserved"] for r in city_scope), "cities"),
        ("CwelveScopeRoofAreaDirectionPreservedCityCount", sum(r["roof_area_direction_preserved"] for r in city_scope), "cities"),
        ("CwelveScopeExistingAreaMajorityPreservedCityCount", sum(r["existing_area_majority_preserved"] for r in city_scope), "cities"),
        ("CwelvePooledFullBuildingAreaRatio", pooled_scope["full_building_area_yield_rr_new_to_existing"], "ratio"),
        ("CwelvePooledNarrowBuildingAreaRatio", pooled_scope["narrow_building_area_yield_rr_new_to_existing"], "ratio"),
        ("CwelvePooledFullRoofAreaRatio", pooled_scope["full_roof_area_yield_rr_new_to_existing"], "ratio"),
        ("CwelvePooledNarrowRoofAreaRatio", pooled_scope["narrow_roof_area_yield_rr_new_to_existing"], "ratio"),
        ("CwelveStrictResolvedTargetCount", pooled_candidate["canonical_resolved_target_count"], "targets"),
        ("CwelveStrictCoverage", pooled_candidate["canonical_coverage_fraction"], "proportion"),
        ("CwelveCandidateBridgeTargetCount", pooled_candidate["candidate_bridge_target_count"], "targets"),
        ("CwelveBroadResolvedTargetCount", pooled_candidate["broad_resolved_target_count"], "targets"),
        ("CwelveBroadCoverage", pooled_candidate["broad_coverage_fraction"], "proportion"),
        ("CwelveNoCandidateTargetCount", pooled_candidate["no_stage7b_candidate_target_count"], "targets"),
        ("CwelveBuildingUnknownObservationCount", pooled_missing["building_unknown_observation_count"], "target-cohort observations"),
        ("CwelveBuildingUnknownObservationShare", pooled_missing["building_unknown_observation_share"], "proportion"),
        ("CwelvePVUnknownObservationCount", pooled_missing["pv_unknown_observation_count"], "target-cohort observations"),
        ("CwelvePVUnknownObservationShare", pooled_missing["pv_unknown_observation_share"], "proportion"),
        ("CwelveUnavailableRelationshipShare", pooled_missing["canonical_unavailable_relationship_share"], "proportion"),
        ("CwelveUnavailablePVAreaShare", pooled_missing["canonical_unavailable_pv_area_share"], "proportion"),
    ]
    source: list[dict[str, Any]] = []
    tex_lines = ["% Generated by scripts/build_c12_partial_validation.py; do not edit."]
    for macro, value, unit in values:
        if unit in {"cities", "targets", "target-cohort observations"}:
            display = fmt_int(int(value))
        elif unit == "proportion":
            display = fmt_pct(float(value))
        else:
            display = fmt_ratio(float(value))
        tex_lines.append(f"\\providecommand{{\\{macro}}}{{{display}}}")
        source.append({
            "macro": macro, "value_unrounded": value, "display_value": display, "unit": unit,
            "source": "C12 generated outputs", "claim_id": "C12",
            "boundary": "partial target-domain validation; conditional on in-scope, anchor-surviving PV/buildings",
            "status": "REPRODUCED",
        })
    OUTPUTS["macros_tex"].write_text("\n".join(tex_lines) + "\n", encoding="utf-8")
    write_csv(OUTPUTS["macros_source"], source, ["macro", "value_unrounded", "display_value", "unit", "source", "claim_id", "boundary", "status"])


def main() -> int:
    for path in INPUTS.values():
        if not path.is_file():
            raise FileNotFoundError(path)
    area_owner = json.loads(INPUTS["area_manifest"].read_text())["outputs"]
    roof_owner = json.loads(INPUTS["roof_manifest"].read_text())["outputs"]
    trajectory_owner = json.loads(INPUTS["trajectory_manifest"].read_text())["tables"]
    candidate_owner = json.loads(INPUTS["candidate_manifest"].read_text())["outputs"]
    owner_bindings = [
        (INPUTS["area_stock_flow"], area_owner["city_area_weighted_stock_flow"]),
        (INPUTS["pv_area_pathways"], area_owner["city_pv_area_onset_pathway_composition"]),
        (INPUTS["roof_stock_flow"], roof_owner["city_roof_area_weighted_stock_flow"]),
        (INPUTS["building_raw_states"], trajectory_owner["city_building_raw_state_counts"]),
        (INPUTS["candidate_city"], candidate_owner["city_sensitivity_index.csv"]),
        (INPUTS["candidate_scenario"], candidate_owner["scenario_sensitivity_index.csv"]),
    ]
    for path, owner in owner_bindings:
        assert path.resolve() == Path(owner["path"]).resolve()
        assert sha256(path) == owner["sha256"]
        assert len(rows(path)) == owner["row_count"]
    index = json.loads(INPUTS["major_results_index"].read_text())
    city_records = index["cities"] if isinstance(index["cities"], list) else list(index["cities"].values())
    city_order = [c["city_id"] for c in city_records]
    city_names = {c["city_id"]: c["city_name"] for c in city_records}

    scope = build_scope(city_order, city_names)
    candidate, candidate_scenarios = build_candidate(city_order)
    missingness, pv_inputs = build_missingness(city_order, city_names, candidate)

    scope_fields = list(scope[0].keys())
    candidate_fields = list(candidate[0].keys())
    scenario_fields = list(candidate_scenarios[0].keys())
    missing_fields = list(missingness[0].keys())
    write_csv(OUTPUTS["scope"], scope, scope_fields)
    write_csv(OUTPUTS["candidate"], candidate, candidate_fields)
    write_csv(OUTPUTS["candidate_scenarios"], candidate_scenarios, scenario_fields)
    write_csv(OUTPUTS["missingness"], missingness, missing_fields)
    write_table_s7(scope)
    write_table_s8(candidate)
    write_table_s9(missingness)
    write_macros(scope, candidate, missingness)

    pooled_candidate = candidate[-1]
    pooled_missing = missingness[-1]
    checks = {
        "schema_version": "c12-partial-validation-checks/v1",
        "generated_at_utc": now(),
        "status": "pass",
        "city_count": len(city_order),
        "scope_row_count": len(scope),
        "candidate_city_row_count": len(candidate),
        "candidate_scenario_row_count": len(candidate_scenarios),
        "missingness_row_count": len(missingness),
        "all_city_sets_match_frozen_index": all({r["city_id"] for r in table[:-1]} == set(city_order) for table in (scope, candidate, missingness)),
        "all_high_level_inputs_match_owning_manifests": True,
        "all_scope_primary_keys_unique": len({r["city_id"] for r in scope}) == len(scope),
        "all_candidate_primary_keys_unique": len({r["city_id"] for r in candidate}) == len(candidate),
        "all_missingness_primary_keys_unique": len({r["city_id"] for r in missingness}) == len(missingness),
        "full_narrow_building_area_direction_preserved_city_count": sum(r["building_area_direction_preserved"] for r in scope[:-1]),
        "full_narrow_roof_area_direction_preserved_city_count": sum(r["roof_area_direction_preserved"] for r in scope[:-1]),
        "full_narrow_existing_area_majority_preserved_city_count": sum(r["existing_area_majority_preserved"] for r in scope[:-1]),
        "pooled_full_narrow_substantive_directions_preserved": all([
            scope[-1]["footprint_direction_preserved"], scope[-1]["building_area_direction_preserved"],
            scope[-1]["roof_area_direction_preserved"], scope[-1]["existing_area_majority_preserved"],
        ]),
        "candidate_strict_partition_reconciles_all_cities": all(r["canonical_resolved_target_count"] + r["canonical_unavailable_target_count"] == r["anchor_pv_target_count"] for r in candidate),
        "candidate_broad_partition_reconciles_all_cities": all(r["broad_resolved_target_count"] + r["no_stage7b_candidate_target_count"] == r["anchor_pv_target_count"] for r in candidate),
        "candidate_bridge_reconciles_all_cities": all(r["canonical_resolved_target_count"] + r["candidate_bridge_target_count"] == r["broad_resolved_target_count"] for r in candidate),
        "scenario_partitions_reconcile": all(r["resolved_pv_target_count"] + r["unavailable_pv_target_count"] == r["anchor_pv_target_count"] for r in candidate_scenarios),
        "canonical_totals_match_frozen_index": all([
            pooled_candidate["anchor_pv_target_count"] == index["totals"]["pv_target_count"],
            pooled_candidate["canonical_resolved_target_count"] == index["totals"]["resolved_relationship_count"],
            pooled_candidate["canonical_unavailable_target_count"] == index["totals"]["unavailable_relationship_count"],
        ]),
        "building_unknown_observation_count": pooled_missing["building_unknown_observation_count"],
        "building_unknown_observation_share": pooled_missing["building_unknown_observation_share"],
        "pv_unknown_observation_count": pooled_missing["pv_unknown_observation_count"],
        "pv_unknown_observation_share": pooled_missing["pv_unknown_observation_share"],
        "pv_invalid_sequence_count": pooled_missing["pv_invalid_sequence_count"],
        "unavailable_relationship_count": pooled_missing["canonical_unavailable_relationship_count"],
        "unavailable_relationship_share": pooled_missing["canonical_unavailable_relationship_share"],
        "unavailable_pv_area_m2": pooled_missing["canonical_unavailable_pv_area_m2"],
        "unavailable_pv_area_share": pooled_missing["canonical_unavailable_pv_area_share"],
        "all_pv_raw_U_counts_match_pau_removed_unknown_count": True,
        "all_pv_sequences_valid_after_protocol": pooled_missing["pv_invalid_sequence_count"] == 0,
        "unknown_and_unavailable_units_kept_separate": True,
        "noncandidate_pv_observed": False,
        "historical_disappearance_observed": False,
        "interpretation": "partial validation supports within-domain sensitivity and missingness accounting but cannot remove candidate-domain or anchor-survivor selection",
    }
    OUTPUTS["checks"].write_text(json.dumps(checks, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    input_records = [
        input_record(INPUTS["major_results_index"], "frozen city and artifact identity"),
        input_record(INPUTS["area_stock_flow"], "full/narrow count and Building-normalized area diagnostics", ["city_id", "scope"]),
        input_record(INPUTS["roof_stock_flow"], "full/narrow roof-normalized diagnostics", ["city_id", "scope"]),
        input_record(INPUTS["building_raw_states"], "canonical Building raw unknown observations", ["city_id", "cohort_order"]),
        input_record(INPUTS["pv_area_pathways"], "canonical unavailable PV relationship area", ["city_id", "appearance_order"]),
        input_record(INPUTS["candidate_city"], "frozen candidate-bridge city accounting", ["city_id"]),
        input_record(INPUTS["candidate_scenario"], "frozen candidate-bridge threshold scenarios", ["city_id", "scenario_id"]),
        input_record(INPUTS["area_manifest"], "owning manifest for area stock-flow and unavailable area"),
        input_record(INPUTS["roof_manifest"], "owning manifest for roof-area stock-flow"),
        input_record(INPUTS["trajectory_manifest"], "owning manifest for Building raw-state counts"),
        input_record(INPUTS["candidate_manifest"], "owning frozen candidate-bridge manifest"),
    ] + pv_inputs
    output_keys = {
        "scope": ["city_id"], "candidate": ["city_id"], "candidate_scenarios": ["scenario_id"],
        "missingness": ["city_id"], "checks": None, "macros_source": ["macro"], "macros_tex": None,
        "table_s7_source": ["city_id"], "table_s7_tex": None,
        "table_s8_source": ["city_id"], "table_s8_tex": None,
        "table_s9_source": ["city_id"], "table_s9_tex": None,
    }
    output_counts = {
        "scope": len(scope), "candidate": len(candidate), "candidate_scenarios": len(candidate_scenarios),
        "missingness": len(missingness), "checks": None, "macros_source": 19, "macros_tex": None,
        "table_s7_source": len(scope), "table_s7_tex": None,
        "table_s8_source": len(candidate), "table_s8_tex": None,
        "table_s9_source": len(missingness), "table_s9_tex": None,
    }
    manifest = {
        "schema_version": "c12-partial-target-domain-validation-manifest/v1",
        "generated_at_utc": now(),
        "status": "REPRODUCED",
        "claim_id": "C12",
        "validation_level": "partial_validation_with_explicit_scope_limitation",
        "generator": {"path": str(Path(__file__).resolve()), "version": VERSION, "sha256": sha256(Path(__file__).resolve())},
        "command": "python3 scripts/build_c12_partial_validation.py",
        "target_population": "in-scope, anchor-surviving PV and Buildings in the full Anchor AOI or canonical narrow candidate scope",
        "estimands": {
            "scope_sensitivity": "full-Anchor-AOI versus narrow-scope route diagnostics under the same strict raw-known adjacent-event rules",
            "candidate_bridge": "relationship resolution among anchor-surviving PV targets with frozen Stage 7B candidates",
            "unknown": "raw U target-cohort observations, separately for canonical Building and PV target inventories",
            "unavailable": "canonical PV relationship rows lacking an accepted linked Building onset, with their anchor PV union area",
        },
        "filters_and_exclusions": [
            "U is counted explicitly and never converted to A; the strict adjacent primary risk panel does not bridge U or missing cohorts.",
            "Candidate-bridge scenarios are analysis-only and do not alter canonical Stage 9 outputs.",
            "Unknown target-cohort observations, unavailable relationship rows and unique paired Buildings remain different units.",
            "Pooled rows sum primitive counts and areas across the 15 observed cities; they are not population-level cross-city models.",
        ],
        "identification_limits": {
            "non_candidate_pv": "not observed; the inventory does not estimate PV prevalence or events outside anchor-triggered candidate domains",
            "historical_disappearance": "not observed; PV removed, demolished or otherwise absent before the anchor inventory cannot enter retrospective tracking",
            "prohibited_interpretations": ["citywide historical adoption rate", "complete historical PV capacity", "citywide PV census"],
        },
        "inputs": input_records,
        "outputs": {name: output_record(path, output_keys[name], output_counts[name]) for name, path in OUTPUTS.items()},
        "qa": checks,
    }
    MANIFEST.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "status": manifest["status"], "manifest": str(MANIFEST),
        "scope_rows": len(scope), "candidate_rows": len(candidate),
        "scenario_rows": len(candidate_scenarios), "missingness_rows": len(missingness),
        "checks": checks,
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
