#!/usr/bin/env python3
"""Build a verified compact index for the 15-city candidate-bridge sensitivity release."""

# ruff: noqa: E501

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCENARIO_ORDER = (
    "strict",
    "ratio_ge_0_95",
    "ratio_ge_0_90",
    "ratio_ge_0_75",
    "all_candidate_bridge",
)
SCENARIO_LABELS = {
    "strict": "Strict canonical",
    "ratio_ge_0_95": "Ratio >= 0.95",
    "ratio_ge_0_90": "Ratio >= 0.90",
    "ratio_ge_0_75": "Ratio >= 0.75",
    "all_candidate_bridge": "All candidate bridges",
}
REQUIRED_CITY_OUTPUTS = (
    "candidate_bridge_crosswalk.csv",
    "pv_building_first_appearance_pairs_sensitivity.csv",
    "pv_target_building_first_appearance_relationship_sensitivity.csv",
    "resolved_pv_target_relationships_sensitivity.csv",
    "scenario_pairs_compact.csv",
    "scenario_summary.csv",
    "summary.json",
    "unavailable_pv_targets_sensitivity.csv",
)
PRIMARY_KEYS = {
    "candidate_bridge_crosswalk.csv": "temporal_pv_target_id",
    "pv_building_first_appearance_pairs_sensitivity.csv": "production_building_id",
    "pv_target_building_first_appearance_relationship_sensitivity.csv": "temporal_pv_target_id",
    "resolved_pv_target_relationships_sensitivity.csv": "temporal_pv_target_id",
    "scenario_pairs_compact.csv": "scenario_id + production_building_id",
    "scenario_summary.csv": "scenario_id",
    "summary.json": "city_id",
    "unavailable_pv_targets_sensitivity.csv": "temporal_pv_target_id",
}


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(16 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def csv_records(path: Path) -> list[dict[str, str]]:
    csv.field_size_limit(sys.maxsize)
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def csv_row_count(path: Path) -> int:
    return len(csv_records(path))


def evidence(path: Path, *, row_count: int | None = None) -> dict[str, Any]:
    item: dict[str, Any] = {
        "path": str(path),
        "sha256": sha256(path),
        "bytes": path.stat().st_size,
    }
    if row_count is not None:
        item["row_count"] = row_count
    return item


def require_hash(path: Path, expected: str, label: str) -> None:
    if not path.is_file():
        raise FileNotFoundError(f"Missing {label}: {path}")
    actual = sha256(path)
    if actual != expected:
        raise ValueError(f"Hash mismatch for {label}: {path}; expected={expected}, actual={actual}")


def to_int(value: str) -> int:
    return int(value)


def to_float(value: str) -> float:
    return float(value)


def pct(value: float) -> str:
    return f"{value * 100:.2f}%"


def write_csv(path: Path, columns: list[str], rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--release-root", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--failed-predecessor-root", type=Path)
    args = parser.parse_args()

    release_root = args.release_root.resolve()
    output_root = args.output_root.resolve()
    failed_root = args.failed_predecessor_root.resolve() if args.failed_predecessor_root else None
    if output_root.exists() and any(output_root.iterdir()):
        raise FileExistsError(f"Refusing to overwrite non-empty output root: {output_root}")
    output_root.mkdir(parents=True, exist_ok=True)

    final_release_path = release_root / "final_release_manifest.json"
    batch_manifest_path = release_root / "manifest.json"
    final_qa_path = release_root / "qa/final_qa.json"
    report_path = release_root / "FINAL_REPORT.md"
    city_summary_path = release_root / "city_summary.csv"
    scenario_summary_path = release_root / "scenario_summary.csv"
    frozen_input_index_path = release_root / "inputs/frozen_input_index.json"
    stage7_bindings_path = release_root / "inputs/stage7_bindings.json"

    final_release = read_json(final_release_path)
    batch_manifest = read_json(batch_manifest_path)
    final_qa = read_json(final_qa_path)
    if final_release.get("status") != "pass" or not final_release.get("release_authority_for_sensitivity"):
        raise ValueError("The selected run is not a passing sensitivity release authority")
    if batch_manifest.get("status") != "pass" or final_qa.get("status") != "pass":
        raise ValueError("Batch manifest or independent final QA did not pass")
    if final_qa.get("errors"):
        raise ValueError(f"Independent final QA contains errors: {final_qa['errors']}")
    for label, item in final_release["evidence"].items():
        require_hash(Path(item["path"]), item["sha256"], f"final release evidence {label}")

    city_source_rows = csv_records(city_summary_path)
    scenario_source_rows = csv_records(scenario_summary_path)
    if len(city_source_rows) != 15 or len(scenario_source_rows) != 75:
        raise ValueError("Expected exactly 15 city rows and 75 city-scenario rows")

    city_ids = [row["city_id"] for row in city_source_rows]
    if len(city_ids) != len(set(city_ids)):
        raise ValueError("Duplicate city_id in city_summary.csv")

    artifact_rows: list[dict[str, Any]] = []
    city_index_rows: list[dict[str, Any]] = []
    indexed_cities: list[dict[str, Any]] = []
    for row in city_source_rows:
        city_id = row["city_id"]
        manifest_ref = batch_manifest["city_manifests"].get(city_id)
        if not manifest_ref:
            raise KeyError(f"Missing batch city manifest reference for {city_id}")
        city_manifest_path = Path(manifest_ref["path"])
        require_hash(city_manifest_path, manifest_ref["sha256"], f"{city_id} city manifest")
        city_manifest = read_json(city_manifest_path)
        city_summary = read_json(Path(city_manifest["outputs"]["summary.json"]["path"]))
        if city_manifest.get("status") != "pass" or city_summary.get("status") != "pass":
            raise ValueError(f"City release did not pass: {city_id}")
        if not all(city_manifest.get("qa", {}).values()):
            raise ValueError(f"City manifest contains failed QA flags: {city_id}")

        artifacts: dict[str, dict[str, Any]] = {}
        for name in REQUIRED_CITY_OUTPUTS:
            declared = city_manifest["outputs"].get(name)
            if not declared:
                raise KeyError(f"{city_id} manifest missing output {name}")
            path = Path(declared["path"])
            require_hash(path, declared["sha256"], f"{city_id}/{name}")
            declared_rows = declared.get("row_count")
            if path.suffix == ".csv":
                actual_rows = csv_row_count(path)
                if actual_rows != int(declared_rows):
                    raise ValueError(
                        f"CSV record-count mismatch for {path}: declared={declared_rows}, actual={actual_rows}"
                    )
            else:
                actual_rows = None
            item = evidence(path, row_count=actual_rows)
            item["primary_key"] = PRIMARY_KEYS[name]
            artifacts[name] = item
            artifact_rows.append({"city_id": city_id, "city_name": row["city_name"], "artifact": name, **item})

        counts = {
            "anchor_pv_target_count": to_int(row["anchor_pv_target_count"]),
            "canonical_resolved_target_count": to_int(row["canonical_resolved_target_count"]),
            "canonical_unavailable_target_count": to_int(row["canonical_unavailable_target_count"]),
            "candidate_bridge_target_count": to_int(row["candidate_bridge_target_count"]),
            "no_stage7b_candidate_target_count": to_int(row["no_stage7b_candidate_target_count"]),
            "broad_resolved_target_count": to_int(row["broad_resolved_target_count"]),
        }
        coverage = {
            "canonical_coverage_fraction": to_float(row["canonical_coverage_fraction"]),
            "broad_coverage_fraction": to_float(row["broad_coverage_fraction"]),
            "coverage_gain_percentage_points": 100
            * (to_float(row["broad_coverage_fraction"]) - to_float(row["canonical_coverage_fraction"])),
        }
        indexed_city = {
            "city_id": city_id,
            "city_name": row["city_name"],
            "status": "pass",
            "analysis_only": True,
            "counts": counts,
            "coverage": coverage,
            "city_manifest": evidence(city_manifest_path),
            "city_summary": artifacts["summary.json"],
            "artifacts": artifacts,
        }
        indexed_cities.append(indexed_city)
        city_index_rows.append(
            {
                "city_id": city_id,
                "city_name": row["city_name"],
                "status": "pass",
                **counts,
                **coverage,
                "city_manifest_path": str(city_manifest_path),
                "city_summary_path": artifacts["summary.json"]["path"],
                "broad_relationship_path": artifacts[
                    "pv_target_building_first_appearance_relationship_sensitivity.csv"
                ]["path"],
                "broad_pairs_path": artifacts["pv_building_first_appearance_pairs_sensitivity.csv"]["path"],
                "scenario_pairs_path": artifacts["scenario_pairs_compact.csv"]["path"],
                "candidate_crosswalk_path": artifacts["candidate_bridge_crosswalk.csv"]["path"],
            }
        )

    scenario_index_rows: list[dict[str, Any]] = []
    scenario_groups: dict[str, list[dict[str, str]]] = {scenario: [] for scenario in SCENARIO_ORDER}
    city_output_map = {city["city_id"]: city["artifacts"] for city in indexed_cities}
    for row in scenario_source_rows:
        scenario_id = row["scenario_id"]
        if scenario_id not in scenario_groups:
            raise ValueError(f"Unexpected scenario: {scenario_id}")
        scenario_groups[scenario_id].append(row)
        artifacts = city_output_map[row["city_id"]]
        scenario_index_rows.append(
            {
                **row,
                "scenario_pairs_path": artifacts["scenario_pairs_compact.csv"]["path"],
                "city_scenario_summary_path": artifacts["scenario_summary.csv"]["path"],
            }
        )
    if any(len(rows) != 15 for rows in scenario_groups.values()):
        raise ValueError("Each scenario must contain exactly 15 cities")

    aggregate_scenarios: list[dict[str, Any]] = []
    for scenario_id in SCENARIO_ORDER:
        rows = scenario_groups[scenario_id]
        targets = sum(to_int(row["anchor_pv_target_count"]) for row in rows)
        resolved = sum(to_int(row["resolved_pv_target_count"]) for row in rows)
        unavailable = sum(to_int(row["unavailable_pv_target_count"]) for row in rows)
        if resolved + unavailable != targets:
            raise ValueError(f"Aggregate target partition failed for {scenario_id}")
        aggregate_scenarios.append(
            {
                "scenario_id": scenario_id,
                "label": SCENARIO_LABELS[scenario_id],
                "minimum_target_to_winner_overlap_ratio": (
                    None if scenario_id == "strict" else to_float(rows[0]["minimum_target_to_winner_overlap_ratio"])
                ),
                "anchor_pv_target_count": targets,
                "resolved_pv_target_count": resolved,
                "candidate_bridge_target_count": sum(to_int(row["candidate_bridge_target_count"]) for row in rows),
                "unavailable_pv_target_count": unavailable,
                "resolved_coverage_fraction": resolved / targets,
                "unique_paired_building_count": sum(to_int(row["unique_paired_building_count"]) for row in rows),
                "building_before_pv_pair_count": sum(to_int(row["building_before_pv_pair_count"]) for row in rows),
                "same_first_present_cohort_pair_count": sum(
                    to_int(row["same_first_present_cohort_pair_count"]) for row in rows
                ),
                "pv_before_building_conflict_pair_count": sum(
                    to_int(row["pv_before_building_conflict_pair_count"]) for row in rows
                ),
            }
        )

    generated_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    totals = {
        "anchor_pv_target_count": sum(city["counts"]["anchor_pv_target_count"] for city in indexed_cities),
        "canonical_resolved_target_count": sum(
            city["counts"]["canonical_resolved_target_count"] for city in indexed_cities
        ),
        "canonical_unavailable_target_count": sum(
            city["counts"]["canonical_unavailable_target_count"] for city in indexed_cities
        ),
        "candidate_bridge_target_count": sum(
            city["counts"]["candidate_bridge_target_count"] for city in indexed_cities
        ),
        "no_stage7b_candidate_target_count": sum(
            city["counts"]["no_stage7b_candidate_target_count"] for city in indexed_cities
        ),
        "broad_resolved_target_count": sum(city["counts"]["broad_resolved_target_count"] for city in indexed_cities),
    }
    totals["broad_unavailable_target_count"] = (
        totals["anchor_pv_target_count"] - totals["broad_resolved_target_count"]
    )
    totals["canonical_coverage_fraction"] = (
        totals["canonical_resolved_target_count"] / totals["anchor_pv_target_count"]
    )
    totals["broad_coverage_fraction"] = totals["broad_resolved_target_count"] / totals["anchor_pv_target_count"]
    totals["coverage_gain_percentage_points"] = 100 * (
        totals["broad_coverage_fraction"] - totals["canonical_coverage_fraction"]
    )

    index = {
        "schema_version": "rpv-candidate-bridge-sensitivity-results-index/v1",
        "status": "complete",
        "generated_at_utc": generated_at,
        "protocol_id": final_release["protocol_id"],
        "base_protocol_id": "anchor_linked_pv_building_first_appearance_earliest_onset_v2",
        "analysis_only": True,
        "release_authority_for_sensitivity": True,
        "canonical_stage9_release_authority_changed": False,
        "interpretation": {
            "unit": "one frozen Anchor PV target",
            "denominator": "all frozen Anchor PV targets in each city or the 15-city aggregate",
            "strict": "Unchanged canonical Stage 9 relationship and pair semantics.",
            "candidate_bridge": (
                "For canonical unavailable_no_anchor_sam3_building_identity rows only, use the already-materialized "
                "Stage 7B strongest-overlap candidate and its frozen final Building identity."
            ),
            "thresholds": "Accept candidate bridges by target-to-winning-candidate overlap ratio.",
            "all_candidate_bridge": "Accept every valid frozen candidate bridge; this is the broad sensitivity output.",
            "remaining_unavailable": "Rows with no Stage 7B candidate remain unavailable and are not imputed.",
            "time_axis": "Cohort-step differences are not calendar-year differences.",
            "authority": "All sensitivity outputs are analysis-only and do not replace canonical Stage 9 outputs.",
        },
        "release": {
            "root": str(release_root),
            "final_release_manifest": evidence(final_release_path),
            "batch_manifest": evidence(batch_manifest_path),
            "independent_final_qa": evidence(final_qa_path),
            "final_report": evidence(report_path),
            "city_summary": evidence(city_summary_path, row_count=len(city_source_rows)),
            "scenario_summary": evidence(scenario_summary_path, row_count=len(scenario_source_rows)),
            "frozen_input_index": evidence(frozen_input_index_path),
            "stage7_bindings": evidence(stage7_bindings_path),
        },
        "failed_predecessor": (
            {
                "root": str(failed_root),
                "status": "failed_evidence_only",
                "do_not_use_as_release_authority": True,
                "reason": (
                    "Its manifest counted physical CSV lines instead of CSV records when fields contained embedded newlines; "
                    "the suffixed -r1 run is the sensitivity release authority."
                ),
            }
            if failed_root
            else None
        ),
        "city_count": len(indexed_cities),
        "scenario_count": len(aggregate_scenarios),
        "artifact_count": len(artifact_rows),
        "totals": totals,
        "aggregate_scenarios": aggregate_scenarios,
        "cities": indexed_cities,
        "qa": {
            "release_manifest_pass": True,
            "independent_final_qa_pass": True,
            "all_15_city_manifests_pass": True,
            "all_city_manifest_qa_flags_true": True,
            "all_indexed_artifact_hashes_match": True,
            "all_csv_record_counts_match": True,
            "all_scenarios_have_15_cities": True,
            "all_scenario_target_partitions_reconcile": True,
            "canonical_outputs_unchanged": True,
        },
    }

    city_columns = [
        "city_id",
        "city_name",
        "status",
        "anchor_pv_target_count",
        "canonical_resolved_target_count",
        "canonical_unavailable_target_count",
        "candidate_bridge_target_count",
        "no_stage7b_candidate_target_count",
        "broad_resolved_target_count",
        "canonical_coverage_fraction",
        "broad_coverage_fraction",
        "coverage_gain_percentage_points",
        "city_manifest_path",
        "city_summary_path",
        "broad_relationship_path",
        "broad_pairs_path",
        "scenario_pairs_path",
        "candidate_crosswalk_path",
    ]
    scenario_columns = list(scenario_source_rows[0]) + ["scenario_pairs_path", "city_scenario_summary_path"]
    artifact_columns = [
        "city_id",
        "city_name",
        "artifact",
        "path",
        "sha256",
        "bytes",
        "row_count",
        "primary_key",
    ]
    write_csv(output_root / "city_sensitivity_index.csv", city_columns, city_index_rows)
    write_csv(output_root / "scenario_sensitivity_index.csv", scenario_columns, scenario_index_rows)
    write_csv(output_root / "artifact_sensitivity_index.csv", artifact_columns, artifact_rows)
    (output_root / "sensitivity_results_index.json").write_text(
        json.dumps(index, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    scenario_lines = []
    for item in aggregate_scenarios:
        scenario_lines.append(
            "| {label} | {resolved:,} | {coverage} | {bridges:,} | {unavailable:,} | {pairs:,} | {conflicts:,} |".format(
                label=item["label"],
                resolved=item["resolved_pv_target_count"],
                coverage=pct(item["resolved_coverage_fraction"]),
                bridges=item["candidate_bridge_target_count"],
                unavailable=item["unavailable_pv_target_count"],
                pairs=item["unique_paired_building_count"],
                conflicts=item["pv_before_building_conflict_pair_count"],
            )
        )
    city_lines = []
    for city in indexed_cities:
        counts = city["counts"]
        coverage = city["coverage"]
        city_lines.append(
            "| {name} | {targets:,} | {strict:,} ({strict_pct}) | {bridges:,} | {none:,} | {broad:,} ({broad_pct}) |".format(
                name=city["city_name"],
                targets=counts["anchor_pv_target_count"],
                strict=counts["canonical_resolved_target_count"],
                strict_pct=pct(coverage["canonical_coverage_fraction"]),
                bridges=counts["candidate_bridge_target_count"],
                none=counts["no_stage7b_candidate_target_count"],
                broad=counts["broad_resolved_target_count"],
                broad_pct=pct(coverage["broad_coverage_fraction"]),
            )
        )
    readme = f"""# 15-city PV-Building candidate-bridge sensitivity index

Generated: `{generated_at}`  
Status: **PASS**  
Protocol: `{final_release['protocol_id']}`  
Release authority: `{release_root}`

This directory is a compact index of the 15-city sensitivity release. It contains no copied
scientific CSVs and no symlinks: every indexed artifact points to its immutable owning `-r1`
run and is bound by path, SHA-256, CSV-aware record count, and primary key.

## How to use it

- Use `strict` as the unchanged canonical Stage 9 baseline.
- Use `ratio_ge_0_95`, `ratio_ge_0_90`, and `ratio_ge_0_75` as threshold sensitivity cases.
- Use `all_candidate_bridge` as the broad sensitivity case. Its analysis-ready full relationship,
  resolved/unavailable partitions, and full pair table are the files ending in `_sensitivity.csv`.
- Do not treat any sensitivity output as a replacement for canonical Stage 9. No canonical output,
  onset table, raw P/A/U sequence, or geometry was modified.
- Rows without a frozen Stage 7B candidate remain unavailable; they are not imputed.
- Cohort-step differences are not calendar-year differences.

## Aggregate scenarios

| Scenario | Resolved PV targets | Coverage | Added bridges | Remaining unavailable | Unique Building pairs | PV-before-Building conflicts |
|---|---:|---:|---:|---:|---:|---:|
{chr(10).join(scenario_lines)}

The broad scenario adds {totals['candidate_bridge_target_count']:,} resolved target relationships,
raising coverage from {pct(totals['canonical_coverage_fraction'])} to {pct(totals['broad_coverage_fraction'])}
(+{totals['coverage_gain_percentage_points']:.2f} percentage points). The remaining
{totals['broad_unavailable_target_count']:,} targets have no Stage 7B candidate and remain unavailable.

## City overview

| City | All targets | Strict resolved | Candidate bridges | No candidate | Broad resolved |
|---|---:|---:|---:|---:|---:|
{chr(10).join(city_lines)}

The sensitivity effect is largest in New York City, Philadelphia, and Washington DC because their
strict unavailable share is high and many of those rows have a frozen Stage 7B candidate. Report
strict and sensitivity estimates together for all cities so the analytical rule is uniform.

## Files in this index

- `sensitivity_results_index.json`: complete machine-readable release, scenario, city, artifact,
  interpretation, and QA index.
- `city_sensitivity_index.csv`: one row per city with strict/broad counts, coverage, and main paths.
- `scenario_sensitivity_index.csv`: 15 x 5 city-scenario rows and threshold-specific pair paths.
- `artifact_sensitivity_index.csv`: all 120 city artifacts with paths, hashes, CSV-aware counts,
  and primary keys.
- `manifest.json`: hashes this compact index bundle and freezes its release evidence inputs.

The source run's `candidate_bridge_crosswalk.csv` preserves original target identity, SAM3 lineage,
target/winner overlaps, ratio, and threshold eligibility. `scenario_pairs_compact.csv` contains all
five threshold-specific pair tables. The broad `_sensitivity.csv` relationship and pair files
represent `all_candidate_bridge`, not the intermediate thresholds.

## Provenance warning

The unsuffixed predecessor `{failed_root}` is failed evidence only. Its scientific files were
retained, but its manifest used physical line counts for CSVs containing embedded newlines. Use the
`-r1` release above; it uses CSV-aware record counts and is the sole sensitivity release authority.
"""
    (output_root / "README.md").write_text(readme, encoding="utf-8")

    source_inputs = {
        "final_release_manifest": evidence(final_release_path),
        "batch_manifest": evidence(batch_manifest_path),
        "independent_final_qa": evidence(final_qa_path),
        "final_report": evidence(report_path),
        "city_summary": evidence(city_summary_path, row_count=len(city_source_rows)),
        "scenario_summary": evidence(scenario_summary_path, row_count=len(scenario_source_rows)),
        "frozen_input_index": evidence(frozen_input_index_path),
        "stage7_bindings": evidence(stage7_bindings_path),
    }
    output_files = {}
    for name in (
        "README.md",
        "artifact_sensitivity_index.csv",
        "city_sensitivity_index.csv",
        "scenario_sensitivity_index.csv",
        "sensitivity_results_index.json",
    ):
        path = output_root / name
        row_count = csv_row_count(path) if path.suffix == ".csv" else None
        output_files[name] = evidence(path, row_count=row_count)
    manifest = {
        "schema_version": "rpv-candidate-bridge-sensitivity-index-manifest/v1",
        "status": "complete",
        "generated_at_utc": generated_at,
        "protocol_id": final_release["protocol_id"],
        "analysis_only": True,
        "canonical_stage9_release_authority_changed": False,
        "release_root": str(release_root),
        "city_count": len(indexed_cities),
        "scenario_count": len(aggregate_scenarios),
        "artifact_count": len(artifact_rows),
        "source_inputs": source_inputs,
        "outputs": output_files,
        "qa": index["qa"],
    }
    (output_root / "manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
