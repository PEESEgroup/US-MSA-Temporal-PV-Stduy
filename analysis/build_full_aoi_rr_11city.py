#!/usr/bin/env python3
"""Merge narrow/outside Building states and estimate strict full-AOI crude RRs."""

from __future__ import annotations

import argparse
import csv
import gc
import hashlib
import json
import math
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from rpv_agent.inventory.temporal_sequence_drop_unknown import resolve_pau_sequence


CITY_IDS = (
    "atlanta",
    "boston",
    "charlotte",
    "dallas",
    "denver",
    "miami",
    "minneapolis",
    "new_york_city",
    "philadelphia",
    "phoenix",
    "washington_dc",
)

# Exact narrow-scope reproduction gate for the preliminary strict-adjacent
# estimator documented in PAPER_ANALYSIS_AGENDA.md on 2026-09-01.
EXPECTED_NARROW = {
    "atlanta": (6224, 78, 82307, 1029),
    "boston": (26815, 116, 1301782, 17774),
    "charlotte": (5547, 50, 56283, 646),
    "dallas": (37588, 371, 1355234, 9901),
    "denver": (32123, 986, 1677826, 24130),
    "miami": (61738, 954, 3490828, 47406),
    "minneapolis": (13499, 185, 479278, 3757),
    "new_york_city": (38497, 258, 2347446, 32025),
    "philadelphia": (14515, 75, 728319, 3530),
    "phoenix": (158027, 2833, 2711273, 77992),
    "washington_dc": (7116, 117, 332943, 8237),
}

STATE_TO_CODE = {"present": "P", "absent": "A", "unknown": "U"}
PAU_V3_LOCK = Path(
    "/home/ec2-user/rpv-work/workflows/temporal-inventory-v2/"
    "configs/temporal/pau_sequence_first_appearance_drop_unknown_v3.lock.json"
)
CORE_BUILDING_COLUMNS = (
    "production_building_id",
    "building_source",
    "building_id",
    "anchor_mask_count",
    "state_sequence",
    "pau_first_appearance_type",
    "pau_first_appearance_lower_index",
    "pau_first_appearance_upper_index",
    "pau_first_credible_present_index",
)
PV_COLUMNS = (
    "production_building_id",
    "pv_pau_first_appearance_type",
    "pv_pau_first_appearance_lower_index",
    "pv_pau_first_appearance_upper_index",
    "pv_pau_first_credible_present_index",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results-index", type=Path, required=True)
    parser.add_argument("--outside-root", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    return parser.parse_args()


def sha256(path: Path) -> str:
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


def first_appearance_summary(city_root: Path, city_id: str) -> tuple[Path, dict[str, Any]]:
    candidates: list[tuple[Path, dict[str, Any]]] = []
    # City production layouts differ slightly: most place this artifact under
    # first_appearance/, while Seattle nests it under building_vintage/. Search
    # the city root and retain the existing semantic uniqueness gate.
    for path in city_root.rglob("summary.json"):
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        if (
            value.get("status") == "complete"
            and value.get("city_id") == city_id
            and value.get("entity_type") == "building"
            and value.get("canonical_output")
        ):
            candidates.append((path, value))
    if len(candidates) != 1:
        raise ValueError(
            f"{city_id}: expected exactly one complete outside first-appearance summary, "
            f"found {len(candidates)}"
        )
    return candidates[0]


def cohort_columns(path: Path) -> list[str]:
    columns = pd.read_csv(path, nrows=0).columns.tolist()
    required = set(CORE_BUILDING_COLUMNS)
    missing = required - set(columns)
    if missing:
        raise ValueError(f"{path}: missing Building columns {sorted(missing)}")
    start = columns.index("anchor_mask_count") + 1
    end = columns.index("state_sequence")
    cohorts = columns[start:end]
    if not cohorts or len(cohorts) != len(set(cohorts)):
        raise ValueError(f"{path}: invalid cohort columns")
    return cohorts


def read_buildings(path: Path, cohorts: list[str]) -> pd.DataFrame:
    usecols = [*CORE_BUILDING_COLUMNS, *cohorts]
    frame = pd.read_csv(path, usecols=usecols, dtype=str, keep_default_na=False)
    if frame.empty or frame["production_building_id"].eq("").any():
        raise ValueError(f"{path}: empty data or identity")
    if frame["production_building_id"].duplicated().any():
        raise ValueError(f"{path}: duplicate production_building_id")
    for cohort in cohorts:
        invalid = sorted(set(frame[cohort]) - set(STATE_TO_CODE))
        if invalid:
            raise ValueError(f"{path}: {cohort} has invalid states {invalid}")
    recomputed = frame[cohorts].replace(STATE_TO_CODE).agg("".join, axis=1)
    if not recomputed.eq(frame["state_sequence"]).all():
        raise ValueError(f"{path}: raw cohort columns do not reproduce state_sequence")
    return frame.set_index("production_building_id", drop=True)


def merge_buildings(
    narrow: pd.DataFrame, outside: pd.DataFrame, cohorts: list[str]
) -> tuple[pd.DataFrame, dict[str, Any]]:
    n = narrow.add_prefix("narrow_")
    o = outside.add_prefix("outside_")
    joined = n.join(o, how="outer", validate="one_to_one")
    in_narrow = joined["narrow_building_source"].notna()
    in_outside = joined["outside_building_source"].notna()
    overlap = in_narrow & in_outside
    scope = np.select(
        [overlap, in_narrow, in_outside],
        ["both", "narrow_only", "outside_only"],
        default="invalid",
    )
    if (scope == "invalid").any():
        raise AssertionError("Outer union produced an invalid scope membership")

    for field in ("building_source", "building_id"):
        left = joined[f"narrow_{field}"]
        right = joined[f"outside_{field}"]
        conflict = overlap & left.ne(right)
        if conflict.any():
            examples = joined.index[conflict].tolist()[:5]
            raise ValueError(f"Cross-scope {field} conflict: {examples}")

    full = pd.DataFrame(index=joined.index)
    full.index.name = "production_building_id"
    full["building_source"] = joined["narrow_building_source"].where(
        in_narrow, joined["outside_building_source"]
    )
    full["building_id"] = joined["narrow_building_id"].where(
        in_narrow, joined["outside_building_id"]
    )
    full["scope_membership"] = scope
    n_masks = pd.to_numeric(joined["narrow_anchor_mask_count"], errors="coerce").fillna(0)
    o_masks = pd.to_numeric(joined["outside_anchor_mask_count"], errors="coerce").fillna(0)
    full["narrow_anchor_mask_count"] = n_masks.astype("int64")
    full["outside_anchor_mask_count"] = o_masks.astype("int64")
    full["anchor_mask_count"] = (n_masks + o_masks).astype("int64")
    full["narrow_state_sequence"] = joined["narrow_state_sequence"].fillna("")
    full["outside_state_sequence"] = joined["outside_state_sequence"].fillna("")

    overlap_state_disagreement_count = 0
    overlap_cohort_disagreement_count = 0
    for cohort in cohorts:
        left = joined[f"narrow_{cohort}"].fillna("")
        right = joined[f"outside_{cohort}"].fillna("")
        overlap_cohort_disagreement_count += int((overlap & left.ne(right)).sum())
        present = left.eq("present") | right.eq("present")
        unknown = left.eq("unknown") | right.eq("unknown")
        full[cohort] = np.where(present, "present", np.where(unknown, "unknown", "absent"))
    overlap_state_disagreement_count = int(
        (
            overlap
            & joined["narrow_state_sequence"].ne(joined["outside_state_sequence"])
        ).sum()
    )
    full["state_sequence"] = full[cohorts].replace(STATE_TO_CODE).agg("".join, axis=1)
    if not full["state_sequence"].str.endswith("P").all():
        raise ValueError("Merged full-AOI Building sequences must end in P")
    full["temporal_conflict"] = full["state_sequence"].str.match(r".*P.*A")

    decisions = {
        sequence: resolve_pau_sequence(sequence, "building", cohorts).to_dict()
        for sequence in sorted(full["state_sequence"].unique())
    }
    decision_frame = pd.DataFrame.from_dict(decisions, orient="index")
    decision_frame.columns = [f"pau_{column}" for column in decision_frame.columns]
    full = full.join(decision_frame, on="state_sequence", validate="many_to_one")
    if not full["pau_valid"].eq(True).all():
        raise ValueError("Merged PAU-v3 produced an invalid Building decision")
    if not full["pau_raw_sequence"].eq(full["state_sequence"]).all():
        raise ValueError("Merged PAU-v3 did not preserve the raw sequence")

    def expanded(sequence: str) -> list[str]:
        decision = decisions[sequence]
        retained_text = str(decision["retained_original_indices"])
        retained = [] if not retained_text else [int(value) for value in retained_text.split("|")]
        resolved = str(decision["resolved_sequence"])
        output = [""] * len(cohorts)
        for reduced_index, original_index in enumerate(retained):
            output[original_index] = resolved[reduced_index]
        return output

    expanded_by_sequence = {
        sequence: expanded(sequence) for sequence in decisions
    }
    for index, cohort in enumerate(cohorts):
        full[f"resolved_{cohort}"] = full["state_sequence"].map(
            lambda value, i=index: expanded_by_sequence[value][i]
        )
    full["first_appearance_upper_cohort"] = full[
        "pau_first_appearance_upper_label"
    ]
    full["first_appearance_cohort_interval"] = np.where(
        full["pau_first_appearance_type"].eq("left_censored"),
        "<=" + full["pau_first_appearance_upper_label"].astype(str),
        "("
        + full["pau_first_appearance_lower_label"].astype(str)
        + ","
        + full["pau_first_appearance_upper_label"].astype(str)
        + "]",
    )

    merged_onset = pd.to_numeric(full["pau_first_credible_present_index"])
    narrow_onset = pd.to_numeric(
        joined["narrow_pau_first_credible_present_index"], errors="coerce"
    )
    outside_onset = pd.to_numeric(
        joined["outside_pau_first_credible_present_index"], errors="coerce"
    )
    qa = {
        "narrow_identity_count": int(len(narrow)),
        "outside_identity_count": int(len(outside)),
        "overlap_identity_count": int(overlap.sum()),
        "full_union_identity_count": int(len(full)),
        "outside_net_new_identity_count": int(len(outside) - overlap.sum()),
        "union_identity_reconciliation": bool(
            len(full) == len(narrow) + len(outside) - overlap.sum()
        ),
        "scope_membership_counts": {
            str(key): int(value)
            for key, value in full["scope_membership"].value_counts().items()
        },
        "overlap_state_sequence_disagreement_count": overlap_state_disagreement_count,
        "overlap_cohort_state_disagreement_count": overlap_cohort_disagreement_count,
        "overlap_merged_onset_differs_from_narrow_count": int(
            (overlap & merged_onset.ne(narrow_onset)).sum()
        ),
        "overlap_merged_onset_differs_from_outside_count": int(
            (overlap & merged_onset.ne(outside_onset)).sum()
        ),
        "unique_merged_sequence_count": int(len(decisions)),
        "merged_sequences_terminal_present": True,
        "merged_pau_v3_all_valid": True,
        "merged_raw_sequence_preserved": True,
        "aggregation_precedence": ["present", "unknown", "absent"],
    }
    return full, qa


def read_pv_pairs(path: Path) -> pd.DataFrame:
    columns = pd.read_csv(path, nrows=0).columns.tolist()
    missing = set(PV_COLUMNS) - set(columns)
    if missing:
        raise ValueError(f"{path}: missing PV columns {sorted(missing)}")
    frame = pd.read_csv(path, usecols=list(PV_COLUMNS), dtype=str, keep_default_na=False)
    if frame["production_building_id"].duplicated().any():
        raise ValueError(f"{path}: duplicate PV-paired Building identity")
    return frame.set_index("production_building_id", drop=True)


def ratio_metrics(n_new: int, y_new: int, n_stock: int, y_retrofit: int) -> dict[str, Any]:
    r_new = y_new / n_new if n_new else None
    r_retrofit = y_retrofit / n_stock if n_stock else None
    rr = r_new / r_retrofit if r_new is not None and r_retrofit else None
    rd = r_new - r_retrofit if r_new is not None and r_retrofit is not None else None
    if y_new > 0 and y_retrofit > 0 and n_new > y_new and n_stock > y_retrofit:
        se = math.sqrt(1 / y_new - 1 / n_new + 1 / y_retrofit - 1 / n_stock)
        lower = math.exp(math.log(rr) - 1.96 * se) if rr is not None else None
        upper = math.exp(math.log(rr) + 1.96 * se) if rr is not None else None
    else:
        se = lower = upper = None
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
        "rr_wald_95_lower": lower,
        "rr_wald_95_upper": upper,
        "stock_multiplier": n_stock / n_new if n_new else None,
        "retrofit_composition_share": (
            y_retrofit / (y_new + y_retrofit) if y_new + y_retrofit else None
        ),
        "retrofit_to_new_contribution_ratio": (
            y_retrofit / y_new if y_new else None
        ),
    }


def estimate_risk(
    buildings: pd.DataFrame,
    pv_pairs: pd.DataFrame,
    cohorts: list[str],
    city_id: str,
    scope: str,
) -> tuple[list[dict[str, Any]], dict[str, Any], dict[str, Any]]:
    if not pv_pairs.index.isin(buildings.index).all():
        missing = pv_pairs.index[~pv_pairs.index.isin(buildings.index)].tolist()[:10]
        raise ValueError(f"{city_id}: PV-linked identities missing from {scope}: {missing}")
    frame = buildings.join(pv_pairs, how="left", validate="one_to_one")
    building_onset = pd.to_numeric(
        frame["pau_first_credible_present_index"], errors="coerce"
    )
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
    total_n_new = total_y_new = total_n_stock = total_y_retrofit = 0
    for transition_index in range(1, len(cohorts)):
        previous = cohorts[transition_index - 1]
        current = cohorts[transition_index]
        new_group = building_strict & building_upper.eq(transition_index)
        at_risk = pv_onset.isna() | pv_onset.ge(transition_index)
        stock_group = building_onset.lt(transition_index) & at_risk
        event = pv_strict & pv_upper.eq(transition_index)
        n_new = int(new_group.sum())
        y_new = int((new_group & event).sum())
        n_stock = int(stock_group.sum())
        y_retrofit = int((stock_group & event).sum())
        metrics = ratio_metrics(n_new, y_new, n_stock, y_retrofit)
        transition_rows.append(
            {
                "city_id": city_id,
                "scope": scope,
                "transition_index": transition_index,
                "previous_cohort": previous,
                "current_cohort": current,
                **metrics,
            }
        )
        total_n_new += n_new
        total_y_new += y_new
        total_n_stock += n_stock
        total_y_retrofit += y_retrofit

    aggregate = {
        "city_id": city_id,
        "scope": scope,
        "cohort_count": len(cohorts),
        "transition_count": len(cohorts) - 1,
        **ratio_metrics(total_n_new, total_y_new, total_n_stock, total_y_retrofit),
    }
    diagnostics = {
        "building_identity_count": int(len(buildings)),
        "pv_paired_building_count": int(len(pv_pairs)),
        "strict_pv_event_count": int(pv_strict.sum()),
        "strict_building_onset_count": int(building_strict.sum()),
        "strict_new_denominator_with_prior_pv_onset_count": int(
            (building_strict & pv_onset.lt(building_upper)).sum()
        ),
        "strict_events_classified_new_count": total_y_new,
        "strict_events_classified_retrofit_count": total_y_retrofit,
        "strict_events_unclassified_by_building_timing_count": int(
            pv_strict.sum() - total_y_new - total_y_retrofit
        ),
    }
    return transition_rows, aggregate, diagnostics


def output_metadata(path: Path) -> dict[str, Any]:
    value: dict[str, Any] = {
        "path": str(path),
        "sha256": sha256(path),
        "bytes": path.stat().st_size,
    }
    if path.suffix.lower() == ".csv":
        value["row_count"] = csv_row_count(path)
    return value


def main() -> None:
    args = parse_args()
    output_root = args.output_root.resolve()
    if output_root.exists() and any(output_root.iterdir()):
        raise FileExistsError(f"Refusing to overwrite non-empty output root: {output_root}")
    output_root.mkdir(parents=True, exist_ok=True)

    generated_at = utc_now()
    major = json.loads(args.results_index.read_text(encoding="utf-8"))
    city_index = {city["city_id"]: city for city in major["cities"]}
    if not set(CITY_IDS).issubset(city_index):
        raise ValueError("Results index is missing one or more requested cities")

    input_manifest: dict[str, Any] = {
        "schema_version": "rpv-full-aoi-risk-panel-inputs/v1",
        "generated_at_utc": generated_at,
        "results_index": {
            "path": str(args.results_index.resolve()),
            "sha256": sha256(args.results_index),
        },
        "pau_v3_protocol_lock": {
            "path": str(PAU_V3_LOCK),
            "sha256": sha256(PAU_V3_LOCK),
        },
        "outside_root": str(args.outside_root.resolve()),
        "protocol": {
            "building_state_merge": "P_gt_U_gt_A_across_narrow_and_outside",
            "building_first_appearance": "pau_sequence_first_appearance_drop_unknown_v3",
            "pv_event": "accepted_PV_onset_with_adjacent_original_grid_interval",
            "new_denominator": "accepted_Building_onset_with_adjacent_original_grid_interval",
            "stock_denominator": "accepted_Building_onset_before_transition_and_no_prior_linked_PV_onset",
            "target_population": "full_Anchor_AOI_Buildings_and_anchor_surviving_accepted_PV",
        },
        "cities": {},
    }

    all_transition_rows: list[dict[str, Any]] = []
    all_city_rows: list[dict[str, Any]] = []
    comparison_rows: list[dict[str, Any]] = []
    city_qa: dict[str, Any] = {}
    narrow_reproduction_pass = True

    for city_id in CITY_IDS:
        city = city_index[city_id]
        narrow_path = Path(city["artifacts"]["building_first_appearance"]["path"])
        pv_pairs_path = Path(city["artifacts"]["unique_pv_building_pairs"]["path"])
        summary_path, outside_summary = first_appearance_summary(
            args.outside_root / city_id, city_id
        )
        outside_path = summary_path.parent / outside_summary["canonical_output"]
        if not outside_path.is_file():
            raise FileNotFoundError(outside_path)
        cohorts = cohort_columns(narrow_path)
        if cohorts != outside_summary.get("cohort_order"):
            raise ValueError(f"{city_id}: narrow/outside cohort order mismatch")
        if cohort_columns(outside_path) != cohorts:
            raise ValueError(f"{city_id}: outside raw cohort columns mismatch")

        narrow = read_buildings(narrow_path, cohorts)
        outside = read_buildings(outside_path, cohorts)
        pv_pairs = read_pv_pairs(pv_pairs_path)
        if len(narrow) != city["counts"]["building_target_count"]:
            raise ValueError(f"{city_id}: narrow row count differs from results index")
        if len(outside) != int(outside_summary["target_count"]):
            raise ValueError(f"{city_id}: outside row count differs from its summary")

        full, merge_qa = merge_buildings(narrow, outside, cohorts)
        city_output_root = output_root / "cities" / city_id
        city_output_root.mkdir(parents=True, exist_ok=True)
        full_output = city_output_root / "full_aoi_building_first_appearance.csv"
        full.reset_index().to_csv(full_output, index=False)

        narrow_transitions, narrow_aggregate, narrow_diag = estimate_risk(
            narrow, pv_pairs, cohorts, city_id, "narrow"
        )
        full_transitions, full_aggregate, full_diag = estimate_risk(
            full, pv_pairs, cohorts, city_id, "full_aoi"
        )
        expected = EXPECTED_NARROW[city_id]
        observed = (
            narrow_aggregate["n_new"],
            narrow_aggregate["y_new"],
            narrow_aggregate["n_stock"],
            narrow_aggregate["y_retrofit"],
        )
        reproduction_pass = observed == expected
        narrow_reproduction_pass &= reproduction_pass
        if not reproduction_pass:
            raise ValueError(
                f"{city_id}: narrow reproduction mismatch {observed} != {expected}"
            )

        merge_qa.update(
            {
                "status": "pass",
                "city_id": city_id,
                "cohort_order": cohorts,
                "full_output": output_metadata(full_output),
                "narrow_reproduction_expected": {
                    "n_new": expected[0],
                    "y_new": expected[1],
                    "n_stock": expected[2],
                    "y_retrofit": expected[3],
                },
                "narrow_reproduction_observed": {
                    "n_new": observed[0],
                    "y_new": observed[1],
                    "n_stock": observed[2],
                    "y_retrofit": observed[3],
                },
                "narrow_reproduction_pass": reproduction_pass,
                "narrow_risk_diagnostics": narrow_diag,
                "full_aoi_risk_diagnostics": full_diag,
                "pv_linked_identities_all_in_full_union": True,
            }
        )
        write_json(city_output_root / "merge_qa.json", merge_qa)
        city_qa[city_id] = merge_qa

        all_transition_rows.extend(narrow_transitions)
        all_transition_rows.extend(full_transitions)
        all_city_rows.extend([narrow_aggregate, full_aggregate])
        comparison_rows.append(
            {
                "city_id": city_id,
                "narrow_buildings": len(narrow),
                "outside_buildings": len(outside),
                "overlap_buildings": merge_qa["overlap_identity_count"],
                "full_aoi_buildings": len(full),
                "full_vs_narrow_building_multiplier": len(full) / len(narrow),
                "narrow_n_new": narrow_aggregate["n_new"],
                "full_aoi_n_new": full_aggregate["n_new"],
                "new_denominator_multiplier": (
                    full_aggregate["n_new"] / narrow_aggregate["n_new"]
                    if narrow_aggregate["n_new"]
                    else None
                ),
                "narrow_n_stock": narrow_aggregate["n_stock"],
                "full_aoi_n_stock": full_aggregate["n_stock"],
                "stock_denominator_multiplier": (
                    full_aggregate["n_stock"] / narrow_aggregate["n_stock"]
                    if narrow_aggregate["n_stock"]
                    else None
                ),
                "narrow_y_new": narrow_aggregate["y_new"],
                "full_aoi_y_new": full_aggregate["y_new"],
                "narrow_y_retrofit": narrow_aggregate["y_retrofit"],
                "full_aoi_y_retrofit": full_aggregate["y_retrofit"],
                "narrow_rr": narrow_aggregate["rr"],
                "full_aoi_rr": full_aggregate["rr"],
                "full_to_narrow_rr_ratio": (
                    full_aggregate["rr"] / narrow_aggregate["rr"]
                    if narrow_aggregate["rr"] and full_aggregate["rr"]
                    else None
                ),
            }
        )

        input_manifest["cities"][city_id] = {
            "cohort_order": cohorts,
            "narrow_building_first_appearance": {
                "path": str(narrow_path),
                "sha256": sha256(narrow_path),
                "row_count": len(narrow),
            },
            "outside_building_first_appearance": {
                "path": str(outside_path),
                "sha256": sha256(outside_path),
                "row_count": len(outside),
            },
            "outside_first_appearance_summary": {
                "path": str(summary_path),
                "sha256": sha256(summary_path),
                "status": outside_summary["status"],
            },
            "unique_pv_building_pairs": {
                "path": str(pv_pairs_path),
                "sha256": sha256(pv_pairs_path),
                "row_count": len(pv_pairs),
            },
        }
        print(
            json.dumps(
                {
                    "city_id": city_id,
                    "full_aoi_buildings": len(full),
                    "narrow_rr": narrow_aggregate["rr"],
                    "full_aoi_rr": full_aggregate["rr"],
                }
            ),
            flush=True,
        )
        del narrow, outside, pv_pairs, full
        gc.collect()

    risk_root = output_root / "risk_panel"
    risk_root.mkdir(parents=True, exist_ok=True)
    transition_frame = pd.DataFrame(all_transition_rows)
    city_frame = pd.DataFrame(all_city_rows)
    comparison_frame = pd.DataFrame(comparison_rows)
    transition_path = risk_root / "city_transition_estimates.csv"
    city_path = risk_root / "city_estimates.csv"
    comparison_path = risk_root / "full_vs_narrow_comparison.csv"
    transition_frame.to_csv(transition_path, index=False)
    city_frame.to_csv(city_path, index=False)
    comparison_frame.to_csv(comparison_path, index=False)

    pooled: dict[str, Any] = {
        "schema_version": "rpv-full-aoi-crude-rr-summary/v1",
        "status": "complete",
        "generated_at_utc": generated_at,
        "city_count": len(CITY_IDS),
        "city_ids": list(CITY_IDS),
        "estimand": "per-observed-cohort-transition crude RR among full Anchor AOI Buildings for anchor-surviving accepted PV",
        "scope_warning": "This is not a complete citywide historical adoption rate.",
        "uncertainty_warning": "Wald intervals are descriptive and do not account for spatial clustering or cross-city heterogeneity.",
        "scopes": {},
    }
    for scope in ("narrow", "full_aoi"):
        selected = city_frame[city_frame["scope"].eq(scope)]
        metrics = ratio_metrics(
            int(selected["n_new"].sum()),
            int(selected["y_new"].sum()),
            int(selected["n_stock"].sum()),
            int(selected["y_retrofit"].sum()),
        )
        pooled["scopes"][scope] = metrics
    pooled["full_to_narrow_rr_ratio"] = (
        pooled["scopes"]["full_aoi"]["rr"] / pooled["scopes"]["narrow"]["rr"]
    )
    pooled["identity_counts"] = {
        "narrow_sum": int(sum(value["narrow_identity_count"] for value in city_qa.values())),
        "outside_sum": int(sum(value["outside_identity_count"] for value in city_qa.values())),
        "overlap_sum": int(sum(value["overlap_identity_count"] for value in city_qa.values())),
        "full_union_sum": int(sum(value["full_union_identity_count"] for value in city_qa.values())),
    }
    pooled_path = risk_root / "pooled_estimate.json"
    write_json(pooled_path, pooled)
    write_json(output_root / "inputs" / "input_manifest.json", input_manifest)

    final_qa = {
        "schema_version": "rpv-full-aoi-risk-panel-qa/v1",
        "status": "pass",
        "generated_at_utc": generated_at,
        "city_count": len(CITY_IDS),
        "checks": {
            "all_requested_outside_first_appearance_summaries_complete": True,
            "all_narrow_inputs_match_results_index_counts": True,
            "all_city_cohort_orders_match": True,
            "all_narrow_and_outside_primary_keys_unique": True,
            "all_full_union_primary_keys_unique": True,
            "all_union_cardinalities_reconcile": True,
            "all_cross_scope_identity_components_match": True,
            "all_merged_raw_states_use_p_gt_u_gt_a": True,
            "all_merged_sequences_terminal_present": True,
            "all_merged_pau_v3_decisions_valid": True,
            "all_pv_linked_buildings_exist_in_full_union": True,
            "narrow_preliminary_estimator_reproduced_exactly": narrow_reproduction_pass,
            "pooled_counts_equal_city_sums": True,
        },
        "failed_checks": [],
        "city_qa_paths": {
            city_id: str(output_root / "cities" / city_id / "merge_qa.json")
            for city_id in CITY_IDS
        },
    }
    write_json(output_root / "qa" / "final_qa.json", final_qa)

    readme = f"""# 11-city full-AOI Building-denominator sensitivity\n\nGenerated: `{generated_at}`.\n\nThis run merges canonical narrow and completed outside-narrow Building raw P/A/U\nstates by `production_building_id × cohort`, applies `P > U > A`, reruns frozen\nBuilding PAU-v3, and recomputes the preliminary strict-adjacent stock-flow RR.\nPV events remain the canonical anchor-surviving accepted-PV events.\n\nThe full-AOI result is a spatial-scope sensitivity estimate, not a complete\ncitywide historical adoption rate. See `risk_panel/pooled_estimate.json`,\n`risk_panel/city_estimates.csv`, and `risk_panel/full_vs_narrow_comparison.csv`.\n"""
    (output_root / "README.md").write_text(readme, encoding="utf-8")

    manifest_paths = [
        output_root / "README.md",
        output_root / "inputs" / "input_manifest.json",
        output_root / "qa" / "final_qa.json",
        transition_path,
        city_path,
        comparison_path,
        pooled_path,
        *[output_root / "cities" / city_id / "merge_qa.json" for city_id in CITY_IDS],
        *[
            output_root / "cities" / city_id / "full_aoi_building_first_appearance.csv"
            for city_id in CITY_IDS
        ],
    ]
    manifest = {
        "schema_version": "rpv-full-aoi-risk-panel-run/v1",
        "status": "complete",
        "generated_at_utc": generated_at,
        "city_count": len(CITY_IDS),
        "protocols": input_manifest["protocol"],
        "source_script": {
            "path": str(Path(__file__).resolve()),
            "sha256": sha256(Path(__file__).resolve()),
        },
        "outputs": {
            str(path.relative_to(output_root)): output_metadata(path)
            for path in manifest_paths
        },
        "pooled_estimate": pooled,
    }
    write_json(output_root / "manifest.json", manifest)
    print(json.dumps(pooled, indent=2), flush=True)


if __name__ == "__main__":
    main()
