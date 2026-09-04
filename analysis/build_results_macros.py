#!/usr/bin/env python3
"""Build traceable main-text numerical macros for the manuscript.

The script deliberately has no third-party dependencies.  Every macro is read
from a canonical machine-readable result or derived by a declared arithmetic
expression.  It writes the TeX macros, a one-row-per-macro provenance table, a
machine-readable QA report, and a manifest with input/output hashes.
"""

from __future__ import annotations

import csv
import hashlib
import json
import os
import re
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from typing import Any, Callable, Iterable


VERSION = "1.0.4"
SCHEMA = "rpv-manuscript-results-macros/v1"
SCRIPT = Path(__file__).resolve()
MANUSCRIPT_DIR = SCRIPT.parents[1]
ANALYTICS_ROOT = SCRIPT.parents[3]
OUTPUT_DIR = MANUSCRIPT_DIR / "generated"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as handle:
            handle.write(text)
        os.replace(temporary, path)
    except Exception:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass
        raise


def atomic_write_json(path: Path, payload: Any) -> None:
    atomic_write_text(path, json.dumps(payload, indent=2, sort_keys=True) + "\n")


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def D(value: Any) -> Decimal:
    return Decimal(str(value))


def q(value: Decimal, places: int) -> Decimal:
    quantum = Decimal(1).scaleb(-places)
    return value.quantize(quantum, rounding=ROUND_HALF_UP)


def fmt_integer(value: Decimal) -> str:
    return f"{int(q(value, 0)):,}"


def fmt_decimal(places: int) -> Callable[[Decimal], str]:
    return lambda value: f"{q(value, places):,.{places}f}"


def fmt_percent(places: int = 1) -> Callable[[Decimal], str]:
    return lambda value: f"{q(value * 100, places):.{places}f}\\%"


def fmt_percent_already(places: int = 1) -> Callable[[Decimal], str]:
    return lambda value: f"{q(value, places):.{places}f}\\%"


def rel(path: Path) -> str:
    return str(path.resolve().relative_to(ANALYTICS_ROOT))


@dataclass(frozen=True)
class Source:
    key: str
    path: Path
    primary_key: tuple[str, ...]
    rows: tuple[dict[str, str], ...] = ()
    json_data: Any = None

    @property
    def row_count(self) -> int:
        if self.rows:
            return len(self.rows)
        if self.key == "major_results_index":
            return int(self.json_data["city_count"])
        return 1

    def select(self, **selector: str) -> dict[str, str]:
        matches = [
            row for row in self.rows
            if all(row.get(column) == value for column, value in selector.items())
        ]
        if len(matches) != 1:
            raise ValueError(
                f"{self.key}: selector {selector!r} returned {len(matches)} rows"
            )
        return matches[0]


def load_csv(key: str, relative_path: str, primary_key: Iterable[str]) -> Source:
    path = ANALYTICS_ROOT / relative_path
    with path.open(encoding="utf-8", newline="") as handle:
        rows = tuple(csv.DictReader(handle))
    if not rows:
        raise ValueError(f"Empty source table: {path}")
    key_tuple = tuple(primary_key)
    seen: set[tuple[str, ...]] = set()
    for row in rows:
        identity = tuple(row[column] for column in key_tuple)
        if identity in seen:
            raise ValueError(f"Duplicate primary key in {path}: {identity}")
        seen.add(identity)
    return Source(key, path, key_tuple, rows=rows)


def load_json(key: str, relative_path: str, primary_key: Iterable[str] = ()) -> Source:
    path = ANALYTICS_ROOT / relative_path
    return Source(
        key,
        path,
        tuple(primary_key),
        json_data=json.loads(path.read_text(encoding="utf-8")),
    )


SOURCES = {
    source.key: source
    for source in (
        load_json("major_results_index", "results/major_results_index.json", ("city_id",)),
        load_csv("artifact_results_index", "results/artifact_results_index.csv", ("city_id", "name")),
        load_csv("conclusion_summary", "data_high_level/results_conclusion_summary.csv", ("metric_id",)),
        load_csv("area_summary", "data_high_level/area_weighted_results_summary.csv", ("metric_id",)),
        load_csv("inventory_temporal", "data_high_level/city_inventory_temporal_contrast.csv", ("city_id",)),
        load_csv("area_temporal", "data_high_level/city_area_temporal_contrast.csv", ("city_id",)),
        load_csv("pathway_area", "data_high_level/city_pv_area_onset_pathway_composition.csv", ("city_id", "appearance_order")),
        load_csv("stock_flow", "data_high_level/city_area_weighted_stock_flow.csv", ("city_id", "scope")),
        load_csv("roof_flow", "data_high_level/city_roof_area_weighted_stock_flow.csv", ("city_id", "scope")),
        load_csv("event_size", "data_high_level/city_area_weighted_event_size_distribution.csv", ("city_id", "scope", "route")),
        load_csv(
            "capacity_density_scenarios",
            "data_high_level/pv_area_capacity_density_scenarios.csv",
            ("scenario_id",),
        ),
        load_csv(
            "figure1_cd",
            "paper/figures/figure1_city_trajectories/initial_v1/figure1_abcd/panels_c_d_data.csv",
            ("city_id", "lag_bin_start_years"),
        ),
        load_csv(
            "figure4_b",
            "paper/figures/figure4_transition_dynamics/draft_v1/figure4_panel_b_data.csv",
            ("city_id", "transition_index", "metric"),
        ),
        load_csv(
            "figure3_data",
            "paper/figures/figure3_roof_area/initial_v1/figure3_abc/figure3_abc_data.csv",
            ("record_id",),
        ),
        load_csv(
            "figure4_d",
            "paper/figures/figure4_transition_dynamics/draft_v1/figure4_panel_d_data.csv",
            ("city_id",),
        ),
        load_json(
            "figure4_checks",
            "paper/figures/figure4_transition_dynamics/draft_v1/figure4_checks.json",
        ),
    )
}

MANIFEST_SOURCES = {
    source.key: source
    for source in (
        load_json("conclusion_manifest", "data_high_level/results_conclusion_evidence_manifest.json"),
        load_json("area_manifest", "data_high_level/area_weighted_results_manifest.json"),
        load_json("roof_manifest", "data_high_level/roof_area_weighted_results_manifest.json"),
        load_json(
            "figure1_freeze",
            "paper/figures/figure1_city_trajectories/initial_v1/figure1_abcd/freeze_manifest.json",
        ),
        load_json(
            "figure3_freeze",
            "paper/figures/figure3_roof_area/initial_v1/figure3_abc/freeze_manifest.json",
        ),
        load_json(
            "figure4_freeze",
            "paper/figures/figure4_transition_dynamics/draft_v1/freeze_manifest.json",
        ),
    )
}


@dataclass
class Metric:
    macro_name: str
    raw_value: Decimal
    tex_value: str
    unit: str
    format_rule: str
    source_keys: tuple[str, ...]
    source_selector: str
    source_expression: str
    denominator_definition: str
    interpretive_boundary: str
    claim_ids: str
    evidence_status: str


METRICS: list[Metric] = []


def add_metric(
    name: str,
    value: Any,
    formatter: Callable[[Decimal], str],
    format_rule: str,
    unit: str,
    source_keys: Iterable[str],
    selector: str,
    expression: str,
    denominator: str,
    boundary: str,
    claims: str,
    status: str = "REPRODUCED",
) -> None:
    if not re.fullmatch(r"[A-Za-z]+", name):
        raise ValueError(f"TeX macro names must contain letters only: {name}")
    if any(metric.macro_name == name for metric in METRICS):
        raise ValueError(f"Duplicate macro name: {name}")
    decimal_value = D(value)
    METRICS.append(
        Metric(
            name,
            decimal_value,
            formatter(decimal_value),
            unit,
            format_rule,
            tuple(source_keys),
            selector,
            expression,
            denominator,
            boundary,
            claims,
            status,
        )
    )


def add_row_metric(
    name: str,
    source_key: str,
    selector: dict[str, str],
    column: str,
    formatter: Callable[[Decimal], str],
    format_rule: str,
    unit: str,
    denominator: str,
    boundary: str,
    claims: str,
) -> None:
    row = SOURCES[source_key].select(**selector)
    if row.get("status", "REPRODUCED").split()[0] != "REPRODUCED":
        raise ValueError(f"Non-reproduced source row for {name}: {row.get('status')}")
    selector_text = "; ".join(f"{key}={value}" for key, value in selector.items())
    add_metric(
        name, row[column], formatter, format_rule, unit, (source_key,),
        selector_text, column, denominator, boundary, claims,
    )


def build_metrics() -> None:
    index = SOURCES["major_results_index"].json_data
    totals = index["totals"]
    inventory_selector = {"city_id": "all_cities_pooled"}
    full_selector = {"city_id": "all_cities_pooled", "scope": "full_aoi"}
    denominator_inventory = (
        "Separate target-count pooled anchor inventories; the PV and Building "
        "shares do not share a denominator."
    )
    boundary_inventory = (
        "Temporal composition of anchor-surviving targets; not prevalence, an "
        "annual event rate, or a citywide historical adoption rate."
    )

    # Frozen study inventory totals.
    for name, key, unit in (
        ("StudyCityCount", "city_count", "cities"),
        ("BuildingTargetCount", "building_target_count", "Building targets"),
        ("PVTargetCount", "pv_target_count", "PV targets"),
        ("ResolvedRelationshipCount", "resolved_relationship_count", "relationship rows"),
        ("UnavailableRelationshipCount", "unavailable_relationship_count", "relationship rows"),
        ("UniquePairedBuildingCount", "unique_paired_building_count", "unique paired Buildings"),
    ):
        value = index[key] if key == "city_count" else totals[key]
        add_metric(
            name, value, fmt_integer, "integer_with_grouping", unit,
            ("major_results_index",),
            f"JSON pointer /{'city_count' if key == 'city_count' else 'totals/' + key}",
            key, "Frozen 15-city canonical inventory.",
            "Counts are distinct entity types and must not be interchanged.",
            "C0", "FROZEN",
        )
    add_metric(
        "UnavailableRelationshipShare", D(totals["unavailable_relationship_count"]) / D(totals["relationship_count"]),
        fmt_percent(1), "100*x; 1 decimal; percent sign included", "percent of relationship rows",
        ("major_results_index",), "JSON pointer /totals",
        "unavailable_relationship_count / relationship_count",
        "All PV--Building relationship rows in the frozen index.",
        "Unavailable is retained explicitly and never recoded as resolved.", "C0", "FROZEN",
    )

    # Figure 1: separate temporal composition and linked onset order.
    for args in (
        ("PostBaselinePVTargetShare", "postbaseline_pv_target_share", "PV targets"),
        ("PostBaselineBuildingTargetShare", "postbaseline_building_target_share", "Building targets"),
    ):
        add_row_metric(
            args[0], "inventory_temporal", inventory_selector, args[1], fmt_percent(1),
            "100*x; 1 decimal; percent sign included", f"percent of anchor {args[2]}",
            denominator_inventory, boundary_inventory, "C1",
        )
    for name, column, format_fn, rule, unit in (
        ("AnchorPVAreaSqKm", "anchor_pv_area_m2", lambda x: fmt_decimal(2)(x / D(1_000_000)), "m2/1e6; 2 decimals", "km2 PV union area"),
        ("PostBaselinePVAreaSqKm", "postbaseline_pv_area_m2", lambda x: fmt_decimal(2)(x / D(1_000_000)), "m2/1e6; 2 decimals", "km2 PV union area"),
        ("PostBaselinePVAreaShare", "postbaseline_pv_area_share", fmt_percent(1), "100*x; 1 decimal; percent sign included", "percent of anchor PV union area"),
        ("AnchorBuildingRoofAreaSqKm", "anchor_building_roof_mask_area_m2", lambda x: fmt_decimal(1)(x / D(1_000_000)), "m2/1e6; 1 decimal", "km2 plan-view roof-mask area"),
        ("PostBaselineBuildingRoofAreaSqKm", "postbaseline_building_roof_mask_area_m2", lambda x: fmt_decimal(1)(x / D(1_000_000)), "m2/1e6; 1 decimal", "km2 plan-view roof-mask area"),
        ("PostBaselineBuildingRoofAreaShare", "postbaseline_building_roof_mask_area_share", fmt_percent(1), "100*x; 1 decimal; percent sign included", "percent of anchor Building roof-mask area"),
    ):
        add_row_metric(
            name, "area_temporal", inventory_selector, column, format_fn, rule, unit,
            "Separate pooled anchor-area denominators for PV union area and Building plan-view roof-mask area.",
            "Cohort entry is left- or interval-censored and is not an exact installation or construction date.",
            "C1",
        )
    city_area_rows = [
        row for row in SOURCES["area_temporal"].rows
        if row["city_id"] != "all_cities_pooled"
    ]
    if len(city_area_rows) != int(index["city_count"]):
        raise ValueError("Expected one non-pooled temporal-area row per city")
    temporal_area_gap_positive_city_count = sum(
        D(row["postbaseline_pv_area_share"])
        > D(row["postbaseline_building_roof_mask_area_share"])
        for row in city_area_rows
    )
    add_metric(
        "TemporalAreaGapPositiveCityCount", temporal_area_gap_positive_city_count,
        fmt_integer, "integer", "cities", ("area_temporal",),
        "exclude city_id=all_cities_pooled",
        "count(postbaseline_pv_area_share > postbaseline_building_roof_mask_area_share)",
        "All 15 city-specific anchor inventories, with separate PV-area and Building roof-mask-area denominators.",
        "Descriptive cross-city direction count; not an inferential generalization or city ranking.", "C1",
    )

    pathway_rows = {
        key: SOURCES["pathway_area"].select(city_id="all_cities_pooled", appearance_order=key)
        for key in ("building_before_pv", "same_first_present_cohort", "pv_before_building_conflict", "unavailable_relationship")
    }
    for name, route in (
        ("ResolvedPVTargetBuildingBeforeShare", "building_before_pv"),
        ("ResolvedPVTargetContemporaneousShare", "same_first_present_cohort"),
        ("ResolvedPVTargetConflictShare", "pv_before_building_conflict"),
    ):
        add_row_metric(
            name, "pathway_area", {"city_id": "all_cities_pooled", "appearance_order": route},
            "share_of_resolved_pv_target_count", fmt_percent(1),
            "100*x; 1 decimal; percent sign included", "percent of resolved PV targets",
            "Resolved canonical PV targets; unavailable relationships are reported separately.",
            "Composition, not propensity; conflict is a temporal-consistency diagnostic.", "C2",
        )
    for name, route in (
        ("ResolvedPVAreaBuildingBeforeShare", "building_before_pv"),
        ("ResolvedPVAreaContemporaneousShare", "same_first_present_cohort"),
        ("ResolvedPVAreaConflictShare", "pv_before_building_conflict"),
    ):
        add_row_metric(
            name, "pathway_area", {"city_id": "all_cities_pooled", "appearance_order": route},
            "share_of_resolved_pv_union_area", fmt_percent(1),
            "100*x; 1 decimal; percent sign included", "percent of resolved PV union area",
            "Resolved canonical PV-target union area; unavailable relationships are separate.",
            "Cohort-contemporaneous is not construction-time installation; conflict is QA.", "C2",
        )
    add_metric(
        "UnavailablePVAreaSqKm", D(pathway_rows["unavailable_relationship"]["pv_union_area_m2"]) / D(1_000_000),
        fmt_decimal(2), "m2/1e6; 2 decimals", "km2 PV union area",
        ("pathway_area",), "city_id=all_cities_pooled; appearance_order=unavailable_relationship",
        "pv_union_area_m2 / 1e6", "PV targets with unavailable Building relationships.",
        "Unavailable area is not folded into the resolved pathway denominator.", "C2",
    )
    conclusion = {row["metric_id"]: row for row in SOURCES["conclusion_summary"].rows}
    add_metric(
        "MedianPositiveOnsetSeparationSteps", conclusion["median_positive_onset_separation_steps"]["value"],
        fmt_integer, "integer", "cohort steps", ("conclusion_summary",),
        "metric_id=median_positive_onset_separation_steps", "value",
        "Positive resolved Building-before-PV onset separations.",
        "Ordered cohort steps, not years or exact elapsed time.", "C2",
    )

    figure1_rows = [row for row in SOURCES["figure1_cd"].rows if row["city_id"] == "all_cities_pooled"]
    if len(figure1_rows) != 15:
        raise ValueError("Expected 15 pooled Figure 1 lag-bin rows")
    first_fig1 = figure1_rows[0]
    for name, column in (
        ("LinkedAreaBuildingLeftCensoredShare", "composition_left_censored_percent"),
        ("LinkedAreaContemporaneousShare", "composition_cohort_contemporaneous_percent"),
        ("LinkedAreaBetweenCohortShare", "composition_between_cohort_percent"),
    ):
        add_metric(
            name, first_fig1[column], fmt_percent_already(1),
            "already percent; 1 decimal; percent sign included", "percent of resolved non-conflict PV area",
            ("figure1_cd",), "city_id=all_cities_pooled; all lag bins agree", column,
            "Resolved non-conflict PV area with linked Building onset classification.",
            "Observed cohort relationship; not exact construction-to-installation lag.", "C2",
        )
    figure1_city_rows: dict[str, dict[str, str]] = {}
    for row in SOURCES["figure1_cd"].rows:
        if row["city_id"] == "all_cities_pooled":
            continue
        prior = figure1_city_rows.setdefault(row["city_id"], row)
        for column in (
            "composition_left_censored_percent",
            "composition_cohort_contemporaneous_percent",
            "composition_between_cohort_percent",
        ):
            if row[column] != prior[column]:
                raise ValueError(f"Figure 1 composition varies across lag bins for {row['city_id']}")
    if len(figure1_city_rows) != int(index["city_count"]):
        raise ValueError("Expected one repeated Figure 1 composition per city")
    left_censored_largest_city_count = sum(
        D(row["composition_left_censored_percent"])
        > max(
            D(row["composition_cohort_contemporaneous_percent"]),
            D(row["composition_between_cohort_percent"]),
        )
        for row in figure1_city_rows.values()
    )
    add_metric(
        "LinkedAreaLeftCensoredLargestCityCount", left_censored_largest_city_count,
        fmt_integer, "integer", "cities", ("figure1_cd",),
        "exclude city_id=all_cities_pooled; deduplicate repeated composition by city_id",
        "count(left-censored share > both cohort-contemporaneous and between-cohort shares)",
        "Resolved non-conflict PV area within each of the 15 city inventories.",
        "Descriptive dominance of an onset-censoring class; it does not estimate an exact PV delay.", "C2",
    )
    visible_lag_share = sum(D(row["pv_area_share_of_all_resolved_percent"]) for row in figure1_rows)
    maximum_lag_bin_share = max(D(row["pv_area_share_of_all_resolved_percent"]) for row in figure1_rows)
    add_metric(
        "IntervalResolvedLagVisibleAreaShare", visible_lag_share, fmt_percent_already(1),
        "sum already-percent lag bins; 1 decimal; percent sign included", "percent of all resolved PV area",
        ("figure1_cd",), "city_id=all_cities_pooled; lag bins 0--14", "sum(pv_area_share_of_all_resolved_percent)",
        "All resolved PV area is the denominator; only interval-resolved lag mass is visible.",
        "Non-cumulative interval-imputed observed lag; not exact elapsed time.", "C2",
    )
    add_metric(
        "LargestObservedLagBinAreaShare", maximum_lag_bin_share, fmt_percent_already(1),
        "maximum already-percent lag bin; 1 decimal; percent sign included", "percent of all resolved PV area",
        ("figure1_cd",), "city_id=all_cities_pooled; lag bins 0--14", "max(pv_area_share_of_all_resolved_percent)",
        "All resolved PV area is the denominator.",
        "Maximum one-year interval-imputed bin; not an uncertainty interval.", "C2",
    )

    # Figure 2: full-AOI strict stock--flow accounting.
    stock = SOURCES["stock_flow"].select(**full_selector)
    stock_denominator = (
        "New route: newly observed Buildings. Existing route: eligible "
        "existing-Building cohort exposures on the native adjacent grid."
    )
    stock_boundary = (
        "Strict raw-known adjacent first events among anchor-surviving linked PV; "
        "host anchor area is attributed to its first event and is not cohort addition."
    )
    for name, column, unit in (
        ("StrictNewBuildingRiskCount", "n_new", "newly observed Buildings"),
        ("StrictExistingBuildingExposureCount", "n_stock", "Building--cohort exposures"),
        ("StrictNewPVEventCount", "y_new", "unique first-event hosts"),
        ("StrictExistingPVEventCount", "y_retrofit", "unique first-event hosts"),
    ):
        add_row_metric(name, "stock_flow", full_selector, column, fmt_integer, "integer_with_grouping", unit, stock_denominator, stock_boundary, "C3;C4")
    strict_event_total = D(stock["y_new"]) + D(stock["y_retrofit"])
    add_metric(
        "StrictPVEventCount", strict_event_total, fmt_integer, "integer_with_grouping", "unique first-event hosts",
        ("stock_flow",), "city_id=all_cities_pooled; scope=full_aoi", "y_new + y_retrofit",
        "All strictly classified new- and existing-route first-event hosts.", stock_boundary, "C3;C4",
    )
    for name, column in (
        ("StrictNewPVAreaSqKm", "pv_area_new_m2"),
        ("StrictExistingPVAreaSqKm", "pv_area_retrofit_m2"),
        ("StrictClassifiedPVAreaSqKm", "pv_area_total_classified_m2"),
    ):
        add_metric(
            name, D(stock[column]) / D(1_000_000), fmt_decimal(2), "m2/1e6; 2 decimals", "km2 anchor PV union area",
            ("stock_flow",), "city_id=all_cities_pooled; scope=full_aoi", f"{column} / 1e6",
            "Strictly classified unique first-event hosts.", stock_boundary, "C3;C4",
        )
    for name, column in (
        ("StrictExistingPVEventShare", "retrofit_share_of_classified_event_count"),
        ("StrictExistingPVAreaShare", "retrofit_share_of_classified_pv_area"),
        ("StrictClassifiedShareOfResolvedHostArea", "strict_classified_share_of_resolved_linked_host_pv_area"),
    ):
        add_row_metric(
            name, "stock_flow", full_selector, column, fmt_percent(1),
            "100*x; 1 decimal; percent sign included", "percent", stock_denominator, stock_boundary, "C3;C4",
        )
    for name, column, places, unit in (
        ("StockExposureMultiplier", "stock_multiplier", 2, "existing/new risk-unit ratio"),
        ("NewToExistingEventRiskRatio", "count_rr_new_to_retrofit", 2, "risk ratio"),
        ("ExistingToNewPVAreaRatio", "area_retrofit_to_new_ratio", 2, "PV-area ratio"),
        ("NewMeanEventPVAreaSqM", "mean_pv_area_per_new_event_m2", 2, "m2 per new-route host"),
        ("ExistingMeanEventPVAreaSqM", "mean_pv_area_per_retrofit_event_m2", 2, "m2 per existing-route host"),
        ("ExistingToNewEventSizeRatio", "event_size_ratio_retrofit_to_new", 2, "mean-area ratio"),
        ("NewPVAreaYieldPerBuilding", "pv_area_yield_new_m2_per_new_building", 3, "m2 per newly observed Building"),
        ("ExistingPVAreaYieldPerExposure", "pv_area_yield_retrofit_m2_per_stock_exposure", 3, "m2 per Building--cohort exposure"),
        ("NewToExistingPVAreaYieldRatio", "area_yield_rr_new_to_retrofit", 2, "area-yield ratio"),
    ):
        add_row_metric(name, "stock_flow", full_selector, column, fmt_decimal(places), f"{places} decimals", unit, stock_denominator, stock_boundary, "C3;C4;C5")
    add_metric(
        "ExistingToNewEventIntensityRatio",
        (D(stock["y_retrofit"]) / D(stock["n_stock"]))
        / (D(stock["y_new"]) / D(stock["n_new"])),
        fmt_decimal(2), "existing/new first-event intensity; 2 decimals",
        "event-intensity ratio", ("stock_flow",),
        "city_id=all_cities_pooled; scope=full_aoi",
        "(y_retrofit / n_stock) / (y_new / n_new)", stock_denominator,
        "Descriptive raw-known strict-adjacent intensity ratio; no spatial clustering or causal interpretation.",
        "C4",
    )
    add_metric(
        "NewToExistingMeanEventSizeRatio", D(1) / D(stock["event_size_ratio_retrofit_to_new"]),
        fmt_decimal(2), "1/event_size_ratio_retrofit_to_new; 2 decimals", "mean-area ratio",
        ("stock_flow",), "city_id=all_cities_pooled; scope=full_aoi", "1 / event_size_ratio_retrofit_to_new",
        "Mean anchor PV union area per strict first-event host.", stock_boundary, "C4",
    )
    add_metric(
        "ParityNewRouteAreaYield", D(stock["pv_area_retrofit_m2"]) / D(stock["n_new"]),
        fmt_decimal(2), "pv_area_retrofit_m2/n_new; 2 decimals", "m2 per newly observed Building",
        ("stock_flow",), "city_id=all_cities_pooled; scope=full_aoi", "pv_area_retrofit_m2 / n_new",
        "Observed existing-route PV area divided by observed new-Building risk count.",
        "Arithmetic parity frontier, not a forecast, policy effect, or roof potential.", "C5",
    )
    for name, column in (
        ("NominalCapacityEquivalentGWdc", "nominal_capacity_total_mwdc_equivalent"),
        ("LowCapacityEquivalentGWdc", "capacity_total_low_mwdc_equivalent"),
        ("HighCapacityEquivalentGWdc", "capacity_total_high_mwdc_equivalent"),
    ):
        add_metric(
            name, D(stock[column]) / D(1000), fmt_decimal(2), "MWdc/1000; 2 decimals", "GWdc-equivalent",
            ("stock_flow",), "city_id=all_cities_pooled; scope=full_aoi", f"{column} / 1000",
            "Strict-classified host PV union area under declared constant-density scenarios.",
            "Illustrative DC-capacity-equivalent, not measured nameplate capacity.", "C9",
        )
    for name, scenario_id, places in (
        ("LowCapacityDensityKWdcPerSqM", "legacy_module_density_low", 2),
        ("NominalCapacityDensityKWdcPerSqM", "nominal_display_density", 2),
        ("HighCapacityDensityKWdcPerSqM", "contemporary_module_density_high", 3),
    ):
        add_row_metric(
            name,
            "capacity_density_scenarios",
            {"scenario_id": scenario_id},
            "power_density_kwdc_per_m2",
            fmt_decimal(places),
            f"{places} decimals",
            "kWdc per m2",
            "Declared constant-density scenario applied to strict-classified anchor PV union area.",
            "Illustrative DC-capacity-equivalent scenario, not measured module surface or nameplate capacity.",
            "C9",
        )

    # Figure 3: roof denominator sensitivity and event-size concentration.
    roof = SOURCES["roof_flow"].select(**full_selector)
    roof_denominator = (
        "New route uses plan-view roof-mask area of newly observed Buildings; "
        "existing route uses roof-area--cohort exposure."
    )
    roof_boundary = (
        "Plan-view SAM3 mask area is neither usable roof surface nor a realized "
        "coverage or citywide historical uptake measure."
    )
    for name, column, places, unit in (
        ("NewPVAreaYieldPerRoofArea", "pv_area_yield_new_m2_per_building_roof_m2", 4, "m2 PV per m2 roof-mask area"),
        ("ExistingPVAreaYieldPerRoofExposure", "pv_area_yield_retrofit_m2_per_building_roof_m2_exposure", 4, "m2 PV per m2 roof-area--cohort exposure"),
        ("NewToExistingRoofAreaYieldRatio", "roof_area_yield_rr_new_to_retrofit", 2, "roof-area-yield ratio"),
    ):
        add_row_metric(name, "roof_flow", full_selector, column, fmt_decimal(places), f"{places} decimals", unit, roof_denominator, roof_boundary, "C5;C14")

    city_roof_rows = [row for row in SOURCES["roof_flow"].rows if row["scope"] == "full_aoi" and row["city_id"] != "all_cities_pooled"]
    contrasts = (
        ("CountRatioAboveParityCityCount", "count_rr_new_to_retrofit", True, "C6"),
        ("CountRatioBelowParityCityCount", "count_rr_new_to_retrofit", False, "C6"),
        ("BuildingAreaRatioAboveParityCityCount", "building_count_area_yield_rr_new_to_retrofit", True, "C5;C6"),
        ("BuildingAreaRatioBelowParityCityCount", "building_count_area_yield_rr_new_to_retrofit", False, "C5;C6"),
        ("RoofAreaRatioAboveParityCityCount", "roof_area_yield_rr_new_to_retrofit", True, "C6;C14"),
        ("RoofAreaRatioBelowParityCityCount", "roof_area_yield_rr_new_to_retrofit", False, "C6;C14"),
    )
    for name, column, above, claims in contrasts:
        count = sum((D(row[column]) > 1) if above else (D(row[column]) < 1) for row in city_roof_rows)
        add_metric(
            name, count, fmt_integer, "integer", "cities", ("roof_flow",),
            "scope=full_aoi; exclude city_id=all_cities_pooled", f"count({column} {'>' if above else '<'} 1)",
            "Fifteen city-specific descriptive full-AOI estimates.",
            "Direction counts are descriptive and do not constitute rankings or inferential multiplicity control.", claims,
        )
    for name, left, right in (
        ("CountToBuildingAreaDirectionChangeCityCount", "count_rr_new_to_retrofit", "building_count_area_yield_rr_new_to_retrofit"),
        ("CountToRoofAreaDirectionChangeCityCount", "count_rr_new_to_retrofit", "roof_area_yield_rr_new_to_retrofit"),
        ("BuildingAreaToRoofAreaDirectionChangeCityCount", "building_count_area_yield_rr_new_to_retrofit", "roof_area_yield_rr_new_to_retrofit"),
    ):
        count = sum((D(row[left]) > 1) != (D(row[right]) > 1) for row in city_roof_rows)
        add_metric(
            name, count, fmt_integer, "integer", "cities", ("roof_flow",),
            "scope=full_aoi; exclude city_id=all_cities_pooled", f"count(direction({left}) != direction({right}))",
            "Fifteen paired city-specific denominator contrasts.",
            "Descriptive sign changes across estimands, not uncertainty-tested reversals.", "C5;C6;C14",
        )

    for route, prefix in (("new", "NewRoute"), ("existing", "ExistingRoute")):
        event_selector = {"city_id": "all_cities_pooled", "scope": "full_aoi", "route": route}
        for suffix, column, formatter, rule, unit in (
            ("MedianEventPVAreaSqM", "median_host_pv_area_m2", fmt_decimal(1), "1 decimal", "m2 per host"),
            ("NinetiethPercentileEventPVAreaSqM", "p90_host_pv_area_m2", fmt_decimal(1), "1 decimal", "m2 per host"),
            ("NinetyNinthPercentileEventPVAreaSqM", "p99_host_pv_area_m2", fmt_decimal(1), "1 decimal", "m2 per host"),
            ("TopOnePercentPVAreaShare", "top_1pct_share_of_route_pv_area", fmt_percent(1), "100*x; 1 decimal; percent sign included", "percent of route PV area"),
            ("PVAreaGini", "gini_host_pv_area", fmt_decimal(2), "2 decimals", "Gini coefficient"),
        ):
            add_row_metric(
                prefix + suffix, "event_size", event_selector, column, formatter, rule, unit,
                "Unique strict first-event hosts within the stated route.",
                "Host anchor PV union area is a distribution, not uncertainty or cohort-added area.", "C4;C10",
            )

    # Figure 4: prespecified information gate and transition direction switching.
    fig4d = SOURCES["figure4_d"].rows
    native = sum(int(row["native_transition_count"]) for row in fig4d)
    eligible = sum(int(row["eligible_transition_count"]) for row in fig4d)
    masked = sum(int(row["masked_transition_count"]) for row in fig4d)
    roof_above = sum(int(row["roof_ratio_above_one_count"]) for row in fig4d)
    roof_below = sum(int(row["roof_ratio_below_one_count"]) for row in fig4d)
    building_above = sum(int(row["building_area_ratio_above_one_count"]) for row in fig4d)
    building_below = sum(int(row["building_area_ratio_below_one_count"]) for row in fig4d)
    roof_switch = sum(row["roof_ratio_direction_switch_observed"] == "True" for row in fig4d)
    building_switch = sum(row["building_area_ratio_direction_switch_observed"] == "True" for row in fig4d)
    transition_values = (
        ("NativeTransitionCount", native, "sum(native_transition_count)"),
        ("EligibleTransitionCount", eligible, "sum(eligible_transition_count)"),
        ("MaskedTransitionCount", masked, "sum(masked_transition_count)"),
        ("EligibleRoofRatioAboveParityCount", roof_above, "sum(roof_ratio_above_one_count)"),
        ("EligibleRoofRatioBelowParityCount", roof_below, "sum(roof_ratio_below_one_count)"),
        ("RoofRatioSwitchCityCount", roof_switch, "count(roof_ratio_direction_switch_observed=True)"),
        ("EligibleBuildingAreaRatioAboveParityCount", building_above, "sum(building_area_ratio_above_one_count)"),
        ("EligibleBuildingAreaRatioBelowParityCount", building_below, "sum(building_area_ratio_below_one_count)"),
        ("BuildingAreaRatioSwitchCityCount", building_switch, "count(building_area_ratio_direction_switch_observed=True)"),
    )
    for name, value, expression in transition_values:
        add_metric(
            name, value, fmt_integer, "integer", "transitions" if "City" not in name else "cities",
            ("figure4_d",), "all 15 city rows", expression,
            "Native full-AOI adjacent transitions; eligible summaries apply the prespecified information gate.",
            "Masked cells are low-information observations, not zeros; results are descriptive.", "C6;C7;C14",
        )
    check_data = SOURCES["figure4_checks"].json_data
    for name, key, unit in (
        ("TransitionMinimumEventsPerRoute", "minimum_strict_first_event_hosts_per_route", "events per route"),
        ("EligibleAnyMetricDirectionDisagreementCount", "any_three_metric_direction_disagreement_count_eligible", "transitions"),
        ("EligibleCountBuildingAreaDirectionDisagreementCount", "count_vs_building_area_direction_disagreement_count_eligible", "transitions"),
        ("EligibleCountRoofAreaDirectionDisagreementCount", "count_vs_roof_area_direction_disagreement_count_eligible", "transitions"),
        ("EligibleBuildingRoofAreaDirectionDisagreementCount", "building_area_vs_roof_area_direction_disagreement_count_eligible", "transitions"),
    ):
        add_metric(
            name, check_data[key], fmt_integer, "integer", unit, ("figure4_checks",),
            f"JSON pointer /{key}", key,
            "Eligible full-AOI transitions under the frozen information gate.",
            "Point-estimate direction comparisons are descriptive; interval support is supplied separately by the reproduced C8 spatial-block bootstrap.", "C6;C7;C14",
        )


def recursive_declared_hashes(node: Any, parent_key: str = "") -> list[tuple[str, str]]:
    found: list[tuple[str, str]] = []
    if isinstance(node, dict):
        path_value = node.get("path")
        hash_value = node.get("sha256") or node.get("sha256_observed")
        if isinstance(path_value, str) and isinstance(hash_value, str):
            found.append((path_value, hash_value))
        for key, value in node.items():
            if isinstance(value, dict) and "sha256" in value and isinstance(value["sha256"], str):
                found.append((key, value["sha256"]))
            found.extend(recursive_declared_hashes(value, key))
    elif isinstance(node, list):
        for value in node:
            found.extend(recursive_declared_hashes(value, parent_key))
    return found


def source_is_bound(source: Source) -> bool:
    observed = sha256(source.path)
    candidates: list[tuple[str, str]] = []
    for manifest in MANIFEST_SOURCES.values():
        candidates.extend(recursive_declared_hashes(manifest.json_data))
    path_strings = {str(source.path.resolve()), rel(source.path), source.path.name}
    for declared_path, declared_hash in candidates:
        declared_variants = {declared_path, Path(declared_path).name}
        if path_strings.intersection(declared_variants) and declared_hash == observed:
            return True
    return source.key in {"major_results_index", "artifact_results_index"}


def run_checks() -> dict[str, Any]:
    checks: list[dict[str, Any]] = []

    def check(name: str, observed: Any, expected: Any, tolerance: Decimal | None = None) -> None:
        if tolerance is None:
            passed = observed == expected
        else:
            passed = abs(D(observed) - D(expected)) <= tolerance
        checks.append({
            "check": name,
            "observed": str(observed) if isinstance(observed, Decimal) else observed,
            "expected": str(expected) if isinstance(expected, Decimal) else expected,
            "tolerance": str(tolerance) if tolerance is not None else None,
            "pass": passed,
        })

    index = SOURCES["major_results_index"].json_data
    totals = index["totals"]
    check("major index status", index["status"], "complete")
    check("major index release evidence", index["all_release_evidence_complete"], True)
    check("city count", index["city_count"], 15)
    check("artifact index row count", SOURCES["artifact_results_index"].row_count, index["artifact_count"])
    check(
        "relationship accounting",
        totals["resolved_relationship_count"] + totals["unavailable_relationship_count"],
        totals["relationship_count"],
    )
    check("relationship and PV target identity", totals["relationship_count"], totals["pv_target_count"])
    inventory = SOURCES["inventory_temporal"].select(city_id="all_cities_pooled")
    check("inventory PV target reconciliation", int(inventory["anchor_pv_target_count"]), totals["pv_target_count"])
    check("inventory Building target reconciliation", int(inventory["anchor_building_target_count"]), totals["building_target_count"])

    area = SOURCES["area_temporal"].select(city_id="all_cities_pooled")
    check("PV area temporal identity", D(area["left_censored_pv_area_m2"]) + D(area["postbaseline_pv_area_m2"]), D(area["anchor_pv_area_m2"]), D("1e-6"))
    check("Building area temporal identity", D(area["left_censored_building_roof_mask_area_m2"]) + D(area["postbaseline_building_roof_mask_area_m2"]), D(area["anchor_building_roof_mask_area_m2"]), D("1e-5"))
    city_area_rows = [row for row in SOURCES["area_temporal"].rows if row["city_id"] != "all_cities_pooled"]
    check("Figure 1 city temporal-area row count", len(city_area_rows), index["city_count"])
    check(
        "Figure 1 PV post-baseline area share exceeds Building share in every city",
        sum(
            D(row["postbaseline_pv_area_share"])
            > D(row["postbaseline_building_roof_mask_area_share"])
            for row in city_area_rows
        ),
        index["city_count"],
    )

    pathway = [row for row in SOURCES["pathway_area"].rows if row["city_id"] == "all_cities_pooled" and row["appearance_order"] != "unavailable_relationship"]
    check("resolved pathway target shares sum to one", sum(D(row["share_of_resolved_pv_target_count"]) for row in pathway), D(1), D("1e-12"))
    check("resolved pathway area shares sum to one", sum(D(row["share_of_resolved_pv_union_area"]) for row in pathway), D(1), D("1e-12"))
    check("resolved pathway target count", sum(int(row["pv_target_count"]) for row in pathway), totals["resolved_relationship_count"])

    stock = SOURCES["stock_flow"].select(city_id="all_cities_pooled", scope="full_aoi")
    check("strict event share identity", D(stock["y_retrofit"]) / (D(stock["y_new"]) + D(stock["y_retrofit"])), D(stock["retrofit_share_of_classified_event_count"]), D("1e-12"))
    check("strict area identity", D(stock["pv_area_new_m2"]) + D(stock["pv_area_retrofit_m2"]), D(stock["pv_area_total_classified_m2"]), D("1e-6"))
    check("strict area share identity", D(stock["pv_area_retrofit_m2"]) / D(stock["pv_area_total_classified_m2"]), D(stock["retrofit_share_of_classified_pv_area"]), D("1e-12"))
    check("stock multiplier identity", D(stock["n_stock"]) / D(stock["n_new"]), D(stock["stock_multiplier"]), D("1e-12"))
    check("count RR identity", (D(stock["y_new"]) / D(stock["n_new"])) / (D(stock["y_retrofit"]) / D(stock["n_stock"])), D(stock["count_rr_new_to_retrofit"]), D("1e-12"))
    check(
        "existing/new event-intensity reciprocal identity",
        ((D(stock["y_retrofit"]) / D(stock["n_stock"])) / (D(stock["y_new"]) / D(stock["n_new"])))
        * D(stock["count_rr_new_to_retrofit"]),
        D(1), D("1e-12"),
    )
    check("three-factor residual", D(stock["three_factor_decomposition_residual"]), D(0), D("1e-12"))

    roof = SOURCES["roof_flow"].select(city_id="all_cities_pooled", scope="full_aoi")
    for column in ("n_new", "y_new", "n_stock", "y_retrofit", "pv_area_new_m2", "pv_area_retrofit_m2"):
        check(f"roof table reconciles {column}", D(roof[column]), D(stock[column]), D("1e-6"))
    calculated_roof_rr = (D(roof["pv_area_new_m2"]) / D(roof["building_roof_area_new_m2"])) / (D(roof["pv_area_retrofit_m2"]) / D(roof["building_roof_area_stock_exposure_m2"]))
    check("roof-area yield ratio identity", calculated_roof_rr, D(roof["roof_area_yield_rr_new_to_retrofit"]), D("1e-12"))

    city_roof_rows = [
        row for row in SOURCES["roof_flow"].rows
        if row["scope"] == "full_aoi" and row["city_id"] != "all_cities_pooled"
    ]
    check("Figure 3 full-AOI city count", len(city_roof_rows), index["city_count"])
    figure3_metrics = {
        "pv_first_appearance_frequency_per_building": "count_rr_new_to_retrofit",
        "pv_area_per_building": "building_count_area_yield_rr_new_to_retrofit",
        "pv_area_per_roof_m2": "roof_area_yield_rr_new_to_retrofit",
    }
    for metric_name, roof_column in figure3_metrics.items():
        pooled_figure3 = SOURCES["figure3_data"].select(
            record_id=f"a:all_cities_pooled:{metric_name}"
        )
        check(
            f"Figure 3 pooled panel-a reconciliation: {metric_name}",
            D(pooled_figure3["value"]),
            D(roof[roof_column]),
            D("1e-12"),
        )
        for city_row in city_roof_rows:
            plotted = SOURCES["figure3_data"].select(
                record_id=f"a:{city_row['city_id']}:{metric_name}"
            )
            check(
                f"Figure 3 city panel-a reconciliation: {city_row['city_id']} {metric_name}",
                D(plotted["value"]),
                D(city_row[roof_column]),
                D("1e-12"),
            )
    for column, expected_above, expected_below in (
        ("count_rr_new_to_retrofit", 6, 9),
        ("building_count_area_yield_rr_new_to_retrofit", 13, 2),
        ("roof_area_yield_rr_new_to_retrofit", 15, 0),
    ):
        check(
            f"Figure 3 city directions above parity: {column}",
            sum(D(row[column]) > 1 for row in city_roof_rows),
            expected_above,
        )
        check(
            f"Figure 3 city directions below parity: {column}",
            sum(D(row[column]) < 1 for row in city_roof_rows),
            expected_below,
        )

    for route in ("new", "existing"):
        event = SOURCES["event_size"].select(city_id="all_cities_pooled", scope="full_aoi", route=route)
        stock_prefix = "new" if route == "new" else "retrofit"
        check(f"{route} event host count reconciliation", int(event["strict_event_host_count"]), int(stock[f"y_{stock_prefix}"]))
        check(f"{route} event area reconciliation", D(event["pv_union_area_m2"]), D(stock[f"pv_area_{stock_prefix}_m2"]), D("1e-6"))
        check(f"{route} top-one-percent share range", D(0) <= D(event["top_1pct_share_of_route_pv_area"]) <= D(1), True)
        figure3_b = SOURCES["figure3_data"].select(record_id=f"b:all_cities_pooled:{route}")
        for event_column, plotted_column in (
            ("median_host_pv_area_m2", "median_host_pv_area_m2"),
            ("p90_host_pv_area_m2", "q90_host_pv_area_m2"),
            ("p99_host_pv_area_m2", "q99_host_pv_area_m2"),
            ("mean_host_pv_area_m2", "mean_host_pv_area_m2"),
        ):
            check(
                f"Figure 3 pooled panel-b reconciliation: {route} {event_column}",
                D(figure3_b[plotted_column]),
                D(event[event_column]),
                D("1e-9"),
            )
        figure3_c = SOURCES["figure3_data"].select(record_id=f"c:all_cities_pooled:{route}")
        check(
            f"Figure 3 pooled panel-c top-one-percent reconciliation: {route}",
            D(figure3_c["pv_area_share_largest_1pct"]),
            D(event["top_1pct_share_of_route_pv_area"]),
            D("1e-12"),
        )
        check(
            f"Figure 3 pooled panel-c Gini reconciliation: {route}",
            D(figure3_c["gini_coefficient"]),
            D(event["gini_host_pv_area"]),
            D("1e-12"),
        )

    check(
        "event-size pooled and city quantiles ordered",
        all(
            D(row["median_host_pv_area_m2"])
            <= D(row["p90_host_pv_area_m2"])
            <= D(row["p99_host_pv_area_m2"])
            for row in SOURCES["event_size"].rows
        ),
        True,
    )
    check(
        "event-size Gini coefficients in unit interval",
        all(D(0) <= D(row["gini_host_pv_area"]) <= D(1) for row in SOURCES["event_size"].rows),
        True,
    )

    figure1_rows = [row for row in SOURCES["figure1_cd"].rows if row["city_id"] == "all_cities_pooled"]
    composition = sum(D(figure1_rows[0][column]) for column in ("composition_left_censored_percent", "composition_cohort_contemporaneous_percent", "composition_between_cohort_percent"))
    check("Figure 1 linked-area composition sums to 100 percent", composition, D(100), D("1e-9"))
    figure1_city_rows: dict[str, dict[str, str]] = {}
    composition_repeats_agree = True
    for row in SOURCES["figure1_cd"].rows:
        if row["city_id"] == "all_cities_pooled":
            continue
        prior = figure1_city_rows.setdefault(row["city_id"], row)
        composition_repeats_agree = composition_repeats_agree and all(
            row[column] == prior[column]
            for column in (
                "composition_left_censored_percent",
                "composition_cohort_contemporaneous_percent",
                "composition_between_cohort_percent",
            )
        )
    check("Figure 1 city composition repeats agree across lag bins", composition_repeats_agree, True)
    check("Figure 1 city composition count", len(figure1_city_rows), index["city_count"])
    check(
        "Figure 1 left-censored linked-area class is largest in every city",
        sum(
            D(row["composition_left_censored_percent"])
            > max(
                D(row["composition_cohort_contemporaneous_percent"]),
                D(row["composition_between_cohort_percent"]),
            )
            for row in figure1_city_rows.values()
        ),
        index["city_count"],
    )

    fig4d = SOURCES["figure4_d"].rows
    native = sum(int(row["native_transition_count"]) for row in fig4d)
    eligible = sum(int(row["eligible_transition_count"]) for row in fig4d)
    masked = sum(int(row["masked_transition_count"]) for row in fig4d)
    check("Figure 4 native transition accounting", eligible + masked, native)
    check("Figure 4 native transition count", native, 67)
    check("Figure 4 eligible transition count", eligible, 55)
    check("Figure 4 masked transition count", masked, 12)
    check(
        "Figure 4 eligible roof-direction accounting",
        sum(int(row["roof_ratio_above_one_count"]) + int(row["roof_ratio_below_one_count"]) for row in fig4d),
        eligible,
    )
    check(
        "Figure 4 eligible Building-area-direction accounting",
        sum(int(row["building_area_ratio_above_one_count"]) + int(row["building_area_ratio_below_one_count"]) for row in fig4d),
        eligible,
    )
    figure4_check_data = SOURCES["figure4_checks"].json_data
    observed_roof_switches = sorted(
        row["city_id"] for row in fig4d if row["roof_ratio_direction_switch_observed"] == "True"
    )
    observed_building_switches = sorted(
        row["city_id"] for row in fig4d if row["building_area_ratio_direction_switch_observed"] == "True"
    )
    check(
        "Figure 4 roof-switch city identities",
        observed_roof_switches,
        sorted(figure4_check_data["roof_area_ratio_switch_cities_eligible"]),
    )
    check(
        "Figure 4 Building-area-switch city identities",
        observed_building_switches,
        sorted(figure4_check_data["building_area_ratio_switch_cities_eligible"]),
    )
    check(
        "Figure 4 disagreement count does not exceed eligible transitions",
        figure4_check_data["any_three_metric_direction_disagreement_count_eligible"] <= eligible,
        True,
    )
    check("Figure 4 panel rows reproduced", all(row["status"].startswith("REPRODUCED") for row in fig4d), True)

    for key, source in SOURCES.items():
        if key != "figure4_checks":
            check(f"source bound to selected manifest: {key}", source_is_bound(source), True)
    for key, manifest in MANIFEST_SOURCES.items():
        check(f"manifest scientific status: {key}", manifest.json_data.get("status", manifest.json_data.get("evidence_status")), "REPRODUCED" if "freeze" not in key else "REPRODUCED")

    check("macro names unique", len({metric.macro_name for metric in METRICS}), len(METRICS))
    check("macro evidence statuses allowed", all(metric.evidence_status in {"FROZEN", "REPRODUCED"} for metric in METRICS), True)
    failures = [item for item in checks if not item["pass"]]
    return {
        "schema_version": f"{SCHEMA}-checks",
        "generated_at_utc": utc_now(),
        "status": "pass" if not failures else "fail",
        "check_count": len(checks),
        "failure_count": len(failures),
        "checks": checks,
    }


def source_record(source: Source) -> dict[str, Any]:
    return {
        "key": source.key,
        "path": str(source.path.resolve()),
        "path_relative_to_analytics": rel(source.path),
        "bytes": source.path.stat().st_size,
        "sha256": sha256(source.path),
        "row_count": source.row_count,
        "primary_key": list(source.primary_key),
    }


def write_source_csv(path: Path) -> None:
    fieldnames = [
        "macro_name", "tex_value", "raw_value", "unit", "format_rule",
        "source_paths", "source_sha256", "source_row_counts", "source_primary_keys",
        "source_selector", "source_expression", "denominator_definition",
        "interpretive_boundary", "claim_ids", "evidence_status",
    ]
    rows: list[dict[str, str]] = []
    for metric in METRICS:
        records = [source_record(SOURCES[key]) for key in metric.source_keys]
        rows.append({
            "macro_name": metric.macro_name,
            "tex_value": metric.tex_value,
            "raw_value": str(metric.raw_value),
            "unit": metric.unit,
            "format_rule": metric.format_rule,
            "source_paths": json.dumps([record["path"] for record in records], separators=(",", ":")),
            "source_sha256": json.dumps([record["sha256"] for record in records], separators=(",", ":")),
            "source_row_counts": json.dumps([record["row_count"] for record in records], separators=(",", ":")),
            "source_primary_keys": json.dumps([record["primary_key"] for record in records], separators=(",", ":")),
            "source_selector": metric.source_selector,
            "source_expression": metric.source_expression,
            "denominator_definition": metric.denominator_definition,
            "interpretive_boundary": metric.interpretive_boundary,
            "claim_ids": metric.claim_ids,
            "evidence_status": metric.evidence_status,
        })
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", newline="", delete=False, dir=path.parent, prefix=f".{path.name}.") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
        temporary = handle.name
    os.replace(temporary, path)


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    build_metrics()
    checks = run_checks()
    if checks["status"] != "pass":
        failures = [item["check"] for item in checks["checks"] if not item["pass"]]
        raise RuntimeError("Macro QA failed: " + "; ".join(failures))

    tex_path = OUTPUT_DIR / "results_macros.tex"
    csv_path = OUTPUT_DIR / "results_macros_source.csv"
    checks_path = OUTPUT_DIR / "results_macros_checks.json"
    manifest_path = OUTPUT_DIR / "results_macros_manifest.json"

    tex_lines = [
        "% AUTO-GENERATED by scripts/build_results_macros.py; DO NOT EDIT.",
        "% Values include display rounding only; raw values and provenance are in results_macros_source.csv.",
    ]
    for metric in METRICS:
        tex_lines.append(f"\\providecommand{{\\{metric.macro_name}}}{{{metric.tex_value}}}")
    atomic_write_text(tex_path, "\n".join(tex_lines) + "\n")
    write_source_csv(csv_path)
    atomic_write_json(checks_path, checks)

    all_inputs = [source_record(source) for source in SOURCES.values()]
    all_inputs.extend(source_record(source) for source in MANIFEST_SOURCES.values())
    all_inputs.sort(key=lambda item: item["path"])
    output_records = []
    for role, path, row_count, primary_key in (
        ("latex_macros", tex_path, len(METRICS), ["macro_name"]),
        ("macro_provenance", csv_path, len(METRICS), ["macro_name"]),
        ("qa_checks", checks_path, checks["check_count"], ["check"]),
    ):
        output_records.append({
            "role": role,
            "path": str(path.resolve()),
            "path_relative_to_manuscript": str(path.relative_to(MANUSCRIPT_DIR)),
            "bytes": path.stat().st_size,
            "sha256": sha256(path),
            "row_count": row_count,
            "primary_key": primary_key,
        })

    area_manifest = MANIFEST_SOURCES["area_manifest"].json_data
    roof_manifest = MANIFEST_SOURCES["roof_manifest"].json_data
    conclusion_manifest = MANIFEST_SOURCES["conclusion_manifest"].json_data
    manifest = {
        "schema_version": SCHEMA,
        "status": "REPRODUCED",
        "generated_at_utc": utc_now(),
        "command": "python3 paper/manuscript/scripts/build_results_macros.py",
        "generator": {
            "path": str(SCRIPT),
            "version": VERSION,
            "sha256": sha256(SCRIPT),
        },
        "purpose": "Traceable display-formatted numerical macros for main-text drafting; the provenance CSV retains unrounded values.",
        "macro_count": len(METRICS),
        "inputs": all_inputs,
        "input_resolution": (
            "Study totals resolve through the frozen major-results index. All analytical values resolve through "
            "hash-bound REPRODUCED paper-analysis tables or frozen plotted-data bundles."
        ),
        "primary_keys": {source.key: list(source.primary_key) for source in SOURCES.values()},
        "filters_and_exclusions": {
            "count_results": conclusion_manifest["filters_and_exclusions"],
            "area_results": area_manifest["filters_and_exclusions"],
            "roof_area_results": roof_manifest["filters_and_exclusions"],
            "macro_scope": "Pooled full-AOI values unless the macro name and provenance selector explicitly state a city-composition or transition-gated summary.",
            "unknown_states": "U is never converted to A and no strict transition bridges unknown or missing observations.",
            "unavailable_relationships": "Unavailable relationships are reported separately and never folded into resolved pathway denominators.",
        },
        "denominator_definitions": {
            "count_results": conclusion_manifest["denominator_definitions"],
            "area_results": area_manifest["denominator_definitions"],
            "roof_area_results": roof_manifest["denominator_definitions"],
            "macro_specific": "Every macro row in results_macros_source.csv carries its exact denominator definition and interpretive boundary.",
        },
        "cohort_order": roof_manifest["cohort_order_by_city"],
        "formatting_policy": {
            "raw_values": "Unrounded Decimal-compatible strings are retained in results_macros_source.csv.",
            "display_values": "TeX macro values are rounded with decimal ROUND_HALF_UP according to each row's format_rule.",
            "percent_macros": "Percent macros include an escaped TeX percent sign and should not be followed by another percent sign.",
            "units": "Most macros contain the number only; add the unit in prose. Percent macros are the exception.",
        },
        "scientific_boundaries": [
            "Cohort steps are opaque ordered observations, not years.",
            "Composition is not propensity.",
            "Host PV area is anchor-year union area attributed to the first strict event, not cohort-added capacity.",
            "Capacity translations are DC-capacity-equivalent scenarios, not measured nameplate capacity.",
            "City and transition point-estimate direction summaries are descriptive; reproduced C8 spatial-block intervals quantify within-domain uncertainty without creating a cross-city population model.",
        ],
        "qa": {
            "path": str(checks_path.resolve()),
            "status": checks["status"],
            "check_count": checks["check_count"],
            "failure_count": checks["failure_count"],
            "sha256": sha256(checks_path),
        },
        "outputs": output_records,
        "manifest_self_hash_note": "The manifest does not contain its own SHA-256 because that would be self-referential.",
    }
    atomic_write_json(manifest_path, manifest)
    print(json.dumps({
        "status": "REPRODUCED",
        "macro_count": len(METRICS),
        "check_count": checks["check_count"],
        "outputs": [str(path) for path in (tex_path, csv_path, checks_path, manifest_path)],
    }, indent=2))


if __name__ == "__main__":
    main()
