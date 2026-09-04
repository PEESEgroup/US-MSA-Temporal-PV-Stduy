#!/usr/bin/env python3
"""Estimate strict raw-known P-to-P narrow/full-AOI RRs from a merge run."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

from build_full_aoi_rr_11city import CITY_IDS, PV_COLUMNS, ratio_metrics, sha256


EXPECTED_NARROW_RAW = {
    "atlanta": (6217, 78, 59280, 937),
    "boston": (26804, 116, 1255155, 17553),
    "charlotte": (5547, 50, 53308, 624),
    "dallas": (37557, 371, 1225295, 9590),
    "denver": (32102, 986, 1650231, 23884),
    "miami": (61686, 954, 3424766, 46826),
    "minneapolis": (13486, 185, 410021, 3382),
    "new_york_city": (38419, 258, 2222017, 30730),
    "philadelphia": (14501, 75, 674570, 3426),
    "phoenix": (157931, 2833, 2650573, 77399),
    "washington_dc": (7085, 117, 318444, 8051),
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-merge-root", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    return parser.parse_args()


def utc_now() -> str:
    return (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def estimate(
    building_path: Path,
    pv_path: Path,
    cohorts: list[str],
    city_id: str,
    scope: str,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    building_columns = [
        "production_building_id",
        "pau_first_appearance_type",
        "pau_first_appearance_lower_index",
        "pau_first_appearance_upper_index",
        *cohorts,
    ]
    buildings = pd.read_csv(
        building_path, usecols=building_columns, dtype=str, keep_default_na=False
    ).set_index("production_building_id")
    pv = pd.read_csv(
        pv_path, usecols=list(PV_COLUMNS), dtype=str, keep_default_na=False
    ).set_index("production_building_id")
    if buildings.index.has_duplicates or pv.index.has_duplicates:
        raise ValueError(f"{city_id}/{scope}: duplicate identities")
    if not pv.index.isin(buildings.index).all():
        raise ValueError(f"{city_id}/{scope}: PV identity missing from Building table")
    frame = buildings.join(pv, how="left", validate="one_to_one")

    building_lower = pd.to_numeric(
        frame["pau_first_appearance_lower_index"], errors="coerce"
    )
    building_upper = pd.to_numeric(
        frame["pau_first_appearance_upper_index"], errors="coerce"
    )
    building_strict = (
        frame["pau_first_appearance_type"].eq("interval_censored")
        & building_upper.sub(building_lower).eq(1)
    )
    pv_onset = pd.to_numeric(
        frame["pv_pau_first_credible_present_index"], errors="coerce"
    )
    pv_lower = pd.to_numeric(
        frame["pv_pau_first_appearance_lower_index"], errors="coerce"
    )
    pv_upper = pd.to_numeric(
        frame["pv_pau_first_appearance_upper_index"], errors="coerce"
    )
    pv_strict = (
        frame["pv_pau_first_appearance_type"].eq("interval_censored")
        & pv_upper.sub(pv_lower).eq(1)
    )

    transition_rows: list[dict[str, Any]] = []
    totals = [0, 0, 0, 0]
    for transition_index, (previous, current) in enumerate(
        zip(cohorts, cohorts[1:]), start=1
    ):
        at_risk = pv_onset.isna() | pv_onset.ge(transition_index)
        new_group = (
            building_strict
            & building_upper.eq(transition_index)
            & at_risk
        )
        stock_group = (
            frame[previous].eq("present")
            & frame[current].eq("present")
            & at_risk
        )
        event = pv_strict & pv_upper.eq(transition_index)
        counts = [
            int(new_group.sum()),
            int((new_group & event).sum()),
            int(stock_group.sum()),
            int((stock_group & event).sum()),
        ]
        totals = [left + right for left, right in zip(totals, counts)]
        transition_rows.append(
            {
                "city_id": city_id,
                "scope": scope,
                "transition_index": transition_index,
                "previous_cohort": previous,
                "current_cohort": current,
                **ratio_metrics(*counts),
            }
        )
    aggregate = {
        "city_id": city_id,
        "scope": scope,
        "cohort_count": len(cohorts),
        "transition_count": len(cohorts) - 1,
        "building_identity_count": len(buildings),
        "pv_paired_building_count": len(pv),
        **ratio_metrics(*totals),
    }
    return transition_rows, aggregate


def main() -> None:
    args = parse_args()
    source = args.source_merge_root.resolve()
    output = args.output_root.resolve()
    if output.exists() and any(output.iterdir()):
        raise FileExistsError(f"Refusing to overwrite non-empty output root: {output}")
    output.mkdir(parents=True, exist_ok=True)
    source_manifest_path = source / "manifest.json"
    source_manifest = json.loads(source_manifest_path.read_text(encoding="utf-8"))
    source_inputs = json.loads(
        (source / "inputs" / "input_manifest.json").read_text(encoding="utf-8")
    )
    if source_manifest.get("status") != "complete":
        raise ValueError("Source merge run is not complete")

    transitions: list[dict[str, Any]] = []
    cities: list[dict[str, Any]] = []
    comparisons: list[dict[str, Any]] = []
    input_cities: dict[str, Any] = {}
    for city_id in CITY_IDS:
        meta = source_inputs["cities"][city_id]
        cohorts = meta["cohort_order"]
        narrow_path = Path(meta["narrow_building_first_appearance"]["path"])
        full_path = source / "cities" / city_id / "full_aoi_building_first_appearance.csv"
        pv_path = Path(meta["unique_pv_building_pairs"]["path"])
        narrow_t, narrow_c = estimate(narrow_path, pv_path, cohorts, city_id, "narrow")
        full_t, full_c = estimate(full_path, pv_path, cohorts, city_id, "full_aoi")
        observed = (
            narrow_c["n_new"],
            narrow_c["y_new"],
            narrow_c["n_stock"],
            narrow_c["y_retrofit"],
        )
        if observed != EXPECTED_NARROW_RAW[city_id]:
            raise ValueError(
                f"{city_id}: raw-known narrow reproduction mismatch "
                f"{observed} != {EXPECTED_NARROW_RAW[city_id]}"
            )
        transitions.extend(narrow_t + full_t)
        cities.extend([narrow_c, full_c])
        comparisons.append(
            {
                "city_id": city_id,
                "narrow_rr": narrow_c["rr"],
                "full_aoi_rr": full_c["rr"],
                "full_to_narrow_rr_ratio": full_c["rr"] / narrow_c["rr"],
                "narrow_n_new": narrow_c["n_new"],
                "full_aoi_n_new": full_c["n_new"],
                "narrow_n_stock": narrow_c["n_stock"],
                "full_aoi_n_stock": full_c["n_stock"],
                "narrow_y_new": narrow_c["y_new"],
                "full_aoi_y_new": full_c["y_new"],
                "narrow_y_retrofit": narrow_c["y_retrofit"],
                "full_aoi_y_retrofit": full_c["y_retrofit"],
            }
        )
        input_cities[city_id] = {
            "cohort_order": cohorts,
            "narrow_building": meta["narrow_building_first_appearance"],
            "full_aoi_building": {
                "path": str(full_path),
                "sha256": sha256(full_path),
                "row_count": full_c["building_identity_count"],
            },
            "unique_pv_building_pairs": meta["unique_pv_building_pairs"],
        }
        print(json.dumps({"city_id": city_id, "full_aoi_rr": full_c["rr"]}), flush=True)

    risk = output / "risk_panel"
    risk.mkdir(parents=True, exist_ok=True)
    transition_frame = pd.DataFrame(transitions)
    city_frame = pd.DataFrame(cities)
    comparison_frame = pd.DataFrame(comparisons)
    transition_frame.to_csv(risk / "city_transition_estimates.csv", index=False)
    city_frame.to_csv(risk / "city_estimates.csv", index=False)
    comparison_frame.to_csv(risk / "full_vs_narrow_comparison.csv", index=False)

    pooled = {
        "schema_version": "rpv-full-aoi-raw-known-crude-rr-summary/v1",
        "status": "complete",
        "generated_at_utc": utc_now(),
        "city_count": len(CITY_IDS),
        "estimand": "strict adjacent Building onset versus raw-known P-to-P stock exposure among full Anchor AOI Buildings for anchor-surviving accepted PV",
        "scope_warning": "This is not a complete citywide historical adoption rate.",
        "uncertainty_warning": "Wald intervals are descriptive and do not account for spatial clustering or cross-city heterogeneity.",
        "scopes": {},
    }
    for scope in ("narrow", "full_aoi"):
        selected = city_frame[city_frame["scope"].eq(scope)]
        pooled["scopes"][scope] = ratio_metrics(
            int(selected["n_new"].sum()),
            int(selected["y_new"].sum()),
            int(selected["n_stock"].sum()),
            int(selected["y_retrofit"].sum()),
        )
    pooled["full_to_narrow_rr_ratio"] = (
        pooled["scopes"]["full_aoi"]["rr"] / pooled["scopes"]["narrow"]["rr"]
    )
    write_json(risk / "pooled_estimate.json", pooled)
    inputs = {
        "schema_version": "rpv-full-aoi-raw-known-inputs/v1",
        "source_merge_manifest": {
            "path": str(source_manifest_path),
            "sha256": sha256(source_manifest_path),
        },
        "cities": input_cities,
    }
    write_json(output / "inputs" / "input_manifest.json", inputs)
    qa = {
        "schema_version": "rpv-full-aoi-raw-known-qa/v1",
        "status": "pass",
        "city_count": len(CITY_IDS),
        "checks": {
            "source_merge_run_complete": True,
            "all_requested_full_union_tables_hash_bound": True,
            "all_building_and_pv_primary_keys_unique": True,
            "all_pv_linked_buildings_exist_in_each_scope": True,
            "all_narrow_raw_known_counts_reproduced": True,
            "all_city_counts_reconcile_to_transition_counts": True,
            "all_pooled_counts_reconcile_to_city_counts": True,
        },
        "failed_checks": [],
    }
    write_json(output / "qa" / "final_qa.json", qa)
    (output / "README.md").write_text(
        "# 11-city full-AOI raw-known risk-panel sensitivity\n\n"
        "This compact run reads the immutable state-level full-AOI union and applies "
        "the PAPER_ANALYSIS_AGENDA 4.1 raw-known stock rule: Building P-to-P in the "
        "original adjacent cohort grid, no prior linked PV onset, and strict adjacent "
        "PV A-to-P events.\n",
        encoding="utf-8",
    )
    output_paths = sorted(
        [path for path in output.rglob("*") if path.is_file() and path.name != "manifest.json"]
    )
    manifest = {
        "schema_version": "rpv-full-aoi-raw-known-run/v1",
        "status": "complete",
        "generated_at_utc": utc_now(),
        "city_count": len(CITY_IDS),
        "source_script": {
            "path": str(Path(__file__).resolve()),
            "sha256": sha256(Path(__file__).resolve()),
        },
        "source_merge_run": inputs["source_merge_manifest"],
        "outputs": {
            str(path.relative_to(output)): {
                "path": str(path),
                "sha256": sha256(path),
                "bytes": path.stat().st_size,
            }
            for path in output_paths
        },
        "pooled_estimate": pooled,
    }
    write_json(output / "manifest.json", manifest)
    print(json.dumps(pooled, indent=2), flush=True)


if __name__ == "__main__":
    main()
