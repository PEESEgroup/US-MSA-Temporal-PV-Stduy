#!/usr/bin/env python3
"""Build the four-panel transition-dynamics Figure 4 evidence bundle."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np
from matplotlib import font_manager
from matplotlib.colors import LinearSegmentedColormap, TwoSlopeNorm
from matplotlib.lines import Line2D
from matplotlib.patches import Patch, Rectangle


SCRIPT_VERSION = "0.2.3"
FIGURE_WIDTH_IN = 8.85
FIGURE_HEIGHT_IN = 6.30
COLORBAR_WIDTH_FRACTION_OF_PANEL_A = 2.0 / 3.0
PREVIOUS_COLORBAR_HEIGHT_IN = 0.11562834746568683
COLORBAR_HEIGHT_IN = PREVIOUS_COLORBAR_HEIGHT_IN / 2.0
COLORBAR_GAP_ABOVE_PANEL_A = 0.018
LEGEND_DOWN_SHIFT = 0.006

NEW = "#c97c5d"
EXISTING = "#2f7f6f"
AREA = "#245f73"
COUNT = "#9b9994"
TEXT = "#222222"
MUTED = "#5f6363"
LIGHT = "#d8dddc"
PALE = "#eceeed"
UNAVAILABLE = "#d7d7d7"

CITY_NAMES = {
    "atlanta": "Atlanta",
    "boston": "Boston",
    "charlotte": "Charlotte",
    "chicago": "Chicago",
    "dallas": "Dallas",
    "denver": "Denver",
    "detroit": "Detroit",
    "los_angeles": "Los Angeles",
    "miami": "Miami",
    "minneapolis": "Minneapolis",
    "new_york_city": "New York City",
    "philadelphia": "Philadelphia",
    "phoenix": "Phoenix",
    "seattle": "Seattle",
    "washington_dc": "Washington DC",
}


def parse_args() -> argparse.Namespace:
    workspace = Path(__file__).resolve().parents[3]
    figure_dir = Path(__file__).resolve().parent
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--area-transition",
        type=Path,
        default=workspace / "data_high_level" / "city_transition_area_weighted_stock_flow.csv",
    )
    parser.add_argument(
        "--roof-transition",
        type=Path,
        default=workspace / "data_high_level" / "city_transition_roof_area_weighted_stock_flow.csv",
    )
    parser.add_argument(
        "--city-area",
        type=Path,
        default=workspace / "data_high_level" / "city_area_weighted_stock_flow.csv",
    )
    parser.add_argument(
        "--area-manifest",
        type=Path,
        default=workspace / "data_high_level" / "area_weighted_results_manifest.json",
    )
    parser.add_argument(
        "--roof-manifest",
        type=Path,
        default=workspace / "data_high_level" / "roof_area_weighted_results_manifest.json",
    )
    parser.add_argument(
        "--area-checks",
        type=Path,
        default=workspace / "data_high_level" / "area_weighted_results_checks.json",
    )
    parser.add_argument(
        "--roof-checks",
        type=Path,
        default=workspace / "data_high_level" / "roof_area_weighted_results_checks.json",
    )
    parser.add_argument(
        "--city-order-checks",
        type=Path,
        default=(workspace / "paper" / "figures" / "figure3_roof_area" / "initial_v1" / "figure3_abc"
                 / "figure3_abc_checks.json"),
    )
    parser.add_argument(
        "--city-order-manifest",
        type=Path,
        default=(workspace / "paper" / "figures" / "figure3_roof_area" / "initial_v1" / "figure3_abc"
                 / "figure3_abc_manifest.json"),
    )
    parser.add_argument(
        "--gate",
        type=Path,
        default=figure_dir / "transition_information_gate_v1.json",
    )
    parser.add_argument(
        "--style",
        type=Path,
        default=workspace / "paper" / "style" / "temporal_pv.mplstyle",
    )
    parser.add_argument(
        "--font",
        type=Path,
        default=(workspace / "paper" / "figures" / "figure1_city_trajectories"
                 / "initial_v1" / "figure1_abcd" / "code" / "arial.ttf"),
    )
    parser.add_argument(
        "--figure-plan",
        type=Path,
        default=workspace / "paper" / "FIGURE_PLAN.md",
    )
    parser.add_argument(
        "--claims-matrix",
        type=Path,
        default=workspace / "paper" / "CLAIMS_EVIDENCE_MATRIX.md",
    )
    parser.add_argument(
        "--analysis-agenda",
        type=Path,
        default=workspace / "PAPER_ANALYSIS_AGENDA.md",
    )
    parser.add_argument(
        "--paper-readme",
        type=Path,
        default=workspace / "paper" / "README.md",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=figure_dir / "draft_v1",
    )
    return parser.parse_args()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as stream:
        return list(csv.DictReader(stream))


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    fields: list[str] = []
    for row in rows:
        for field in row:
            if field not in fields:
                fields.append(field)
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def source_record(path: Path, role: str, row_count: int | None = None) -> dict[str, object]:
    record: dict[str, object] = {
        "path": str(path.resolve()),
        "role": role,
        "bytes": path.stat().st_size,
        "sha256": sha256_file(path),
    }
    if row_count is not None:
        record["row_count"] = row_count
    return record


def output_record(path: Path, row_count: int | None = None) -> dict[str, object]:
    record: dict[str, object] = {
        "path": str(path.resolve()),
        "bytes": path.stat().st_size,
        "sha256": sha256_file(path),
    }
    if row_count is not None:
        record["row_count"] = row_count
    return record


def finite(value: float) -> bool:
    return math.isfinite(value)


def log2(value: float) -> float:
    return math.log(value, 2)


def close(left: float, right: float, tolerance: float = 1e-9) -> bool:
    return math.isclose(left, right, rel_tol=tolerance, abs_tol=tolerance)


def configure_style(style: Path, font: Path) -> str:
    plt.style.use(style)
    font_name = "Arial"
    if font.is_file():
        font_manager.fontManager.addfont(str(font))
        font_name = font_manager.FontProperties(fname=str(font)).get_name()
    mpl.rcParams["font.family"] = font_name
    mpl.rcParams["font.sans-serif"] = [font_name]
    mpl.rcParams["pdf.fonttype"] = 42
    return font_name


def panel_label(axis: plt.Axes, label: str, x: float = -0.11, y: float = 1.075) -> None:
    axis.text(
        x, y, f"{label},", transform=axis.transAxes, ha="left", va="bottom",
        fontsize=9.5, color=TEXT, clip_on=False,
    )


def verify_reproduced_input(
    table_path: Path,
    manifest: dict,
    output_key: str,
) -> None:
    if manifest.get("status") != "REPRODUCED":
        raise AssertionError(f"Owning manifest is not REPRODUCED: {output_key}")
    record = manifest["outputs"][output_key]
    if sha256_file(table_path) != record["sha256"]:
        raise AssertionError(f"Input hash does not match owning manifest: {table_path}")


def transition_key(row: dict[str, str]) -> tuple[str, str, int]:
    return row["city_id"], row["scope"], int(row["transition_index"])


def gate_row(
    area_row: dict[str, str],
    roof_row: dict[str, str],
    gate: dict,
) -> tuple[bool, list[str]]:
    rule = gate["eligibility_rule"]
    reasons: list[str] = []
    minimum_events = int(rule["minimum_strict_first_event_hosts_per_route"])
    if int(area_row["y_new"]) < minimum_events:
        reasons.append("y_new_below_minimum")
    if int(area_row["y_retrofit"]) < minimum_events:
        reasons.append("y_retrofit_below_minimum")
    positive_fields = [
        ("building_roof_area_new_m2", roof_row, "new_roof_area_not_positive"),
        ("building_roof_area_stock_exposure_m2", roof_row, "existing_roof_area_not_positive"),
        ("pv_area_new_m2", area_row, "new_pv_area_not_positive"),
        ("pv_area_retrofit_m2", area_row, "existing_pv_area_not_positive"),
    ]
    for field, row, reason in positive_fields:
        if float(row[field]) <= 0:
            reasons.append(reason)
    ratio_fields = [
        ("count_rr_new_to_retrofit", area_row, "count_rr_not_finite"),
        ("area_yield_rr_new_to_retrofit", area_row, "building_area_yield_rr_not_finite"),
        ("roof_area_yield_rr_new_to_retrofit", roof_row, "roof_area_yield_rr_not_finite"),
    ]
    for field, row, reason in ratio_fields:
        value = float(row[field])
        if not finite(value) or value <= 0:
            reasons.append(reason)
    return len(reasons) == 0, reasons


def validate_native_order(rows: list[dict[str, str]], cohort_order: dict[str, list[str]]) -> bool:
    by_city: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        by_city[row["city_id"]].append(row)
    for city_id, city_rows in by_city.items():
        ordered = sorted(city_rows, key=lambda row: int(row["transition_index"]))
        expected = cohort_order[city_id]
        if len(ordered) != len(expected) - 1:
            return False
        for index, row in enumerate(ordered):
            if int(row["transition_index"]) != index + 1:
                return False
            if row["previous_cohort"] != expected[index]:
                return False
            if row["current_cohort"] != expected[index + 1]:
                return False
    return True


def range_of(values: list[float]) -> float:
    return max(values) - min(values)


def select_panel_c_cities(
    joined: list[dict[str, object]],
    selection_rule: dict,
) -> list[tuple[str, str]]:
    by_city: dict[str, list[dict[str, object]]] = defaultdict(list)
    for row in joined:
        if row["eligible"]:
            by_city[str(row["city_id"])].append(row)
    candidates = [
        city_id for city_id, rows in by_city.items()
        if any(float(row["roof_rr"]) > 1 for row in rows)
        and any(float(row["roof_rr"]) < 1 for row in rows)
    ]
    if len(candidates) < int(selection_rule["selection_count"]):
        raise AssertionError("Fewer gate-eligible switching cities than required exemplars")

    frequency_city = sorted(
        candidates,
        key=lambda city_id: (
            -range_of([log2(float(row["count_rr"])) for row in by_city[city_id]]),
            city_id,
        ),
    )[0]
    remaining = [city_id for city_id in candidates if city_id != frequency_city]
    size_city = sorted(
        remaining,
        key=lambda city_id: (
            -range_of([
                log2(float(row["mean_area_new"]) / float(row["mean_area_existing"]))
                for row in by_city[city_id]
            ]),
            city_id,
        ),
    )[0]
    remaining = [city_id for city_id in remaining if city_id != size_city]

    def denominator_key(city_id: str) -> tuple[float, float, str]:
        rows = by_city[city_id]
        disagreement_count = sum(
            (float(row["building_area_rr"]) > 1) != (float(row["roof_rr"]) > 1)
            for row in rows
        )
        difference_range = range_of([
            log2(float(row["roof_rr"])) - log2(float(row["building_area_rr"]))
            for row in rows
        ])
        return -disagreement_count, -difference_range, city_id

    denominator_city = sorted(remaining, key=denominator_key)[0]
    selected = [
        (frequency_city, "frequency-variation exemplar"),
        (size_city, "system-size-variation exemplar"),
        (denominator_city, "denominator-sensitivity exemplar"),
    ]
    if len({city_id for city_id, _ in selected}) != len(selected):
        raise AssertionError("Panel c selection did not produce unique cities")
    return selected


def derive_panel_rows(
    joined: list[dict[str, object]],
    city_order: list[str],
    selected_cities: list[tuple[str, str]],
) -> tuple[list[dict[str, object]], list[dict[str, object]], list[dict[str, object]], list[dict[str, object]]]:
    order_lookup = {city_id: index + 1 for index, city_id in enumerate(city_order)}
    panel_a: list[dict[str, object]] = []
    panel_b: list[dict[str, object]] = []
    selected_lookup = dict(selected_cities)
    panel_c: list[dict[str, object]] = []
    by_city: dict[str, list[dict[str, object]]] = defaultdict(list)

    for row in joined:
        city_id = str(row["city_id"])
        by_city[city_id].append(row)
        common = {
            "panel": "a",
            "city_id": city_id,
            "city_display": CITY_NAMES[city_id],
            "city_order": order_lookup[city_id],
            "transition_index": row["transition_index"],
            "previous_cohort": row["previous_cohort"],
            "current_cohort": row["current_cohort"],
            "transition_label": f"{row['previous_cohort']} to {row['current_cohort']}",
            "n_new": row["n_new"],
            "y_new": row["y_new"],
            "n_stock": row["n_stock"],
            "y_retrofit": row["y_retrofit"],
            "building_roof_area_new_m2": row["roof_area_new"],
            "building_roof_area_stock_exposure_m2": row["roof_area_existing"],
            "pv_area_new_m2": row["pv_area_new"],
            "pv_area_retrofit_m2": row["pv_area_existing"],
            "roof_area_yield_rr_new_to_retrofit": row["roof_rr"],
            "log2_roof_area_yield_rr": log2(float(row["roof_rr"])),
            "information_gate_eligible": row["eligible"],
            "information_gate_failure_reasons": ";".join(row["gate_failure_reasons"]),
            "status": "REPRODUCED descriptive",
        }
        panel_a.append(common)

        directions = {
            "count_rr": float(row["count_rr"]),
            "pv_area_per_building": float(row["building_area_rr"]),
            "pv_area_per_roof_m2": float(row["roof_rr"]),
        }
        any_disagreement = len({value > 1 for value in directions.values()}) > 1
        for metric_order, (metric, value) in enumerate(directions.items(), start=1):
            panel_b.append({
                "panel": "b",
                "city_id": city_id,
                "city_display": CITY_NAMES[city_id],
                "city_order": order_lookup[city_id],
                "transition_index": row["transition_index"],
                "previous_cohort": row["previous_cohort"],
                "current_cohort": row["current_cohort"],
                "metric": metric,
                "metric_order": metric_order,
                "ratio_new_to_existing": value,
                "direction": "newly_observed_higher" if value > 1 else "existing_higher",
                "any_three_metric_direction_disagreement": any_disagreement,
                "information_gate_eligible": row["eligible"],
                "information_gate_failure_reasons": ";".join(row["gate_failure_reasons"]),
                "status": "REPRODUCED descriptive",
            })

        if city_id in selected_lookup:
            for route in ("newly_observed", "existing"):
                if route == "newly_observed":
                    event_proportion = float(row["event_rate_new"])
                    mean_area = float(row["mean_area_new"])
                    eligible_observation = "Building first observed in this transition"
                else:
                    event_proportion = float(row["event_rate_existing"])
                    mean_area = float(row["mean_area_existing"])
                    eligible_observation = "existing Building carried into this transition"
                panel_c.append({
                    "panel": "c",
                    "city_id": city_id,
                    "city_display": CITY_NAMES[city_id],
                    "selection_role": selected_lookup[city_id],
                    "transition_index": row["transition_index"],
                    "previous_cohort": row["previous_cohort"],
                    "current_cohort": row["current_cohort"],
                    "route": route,
                    "event_proportion_per_risk_unit": event_proportion,
                    "event_proportion_per_1000_risk_units": 1000.0 * event_proportion,
                    "mean_pv_area_per_event_m2": mean_area,
                    "eligible_observation_definition": eligible_observation,
                    "roof_area_yield_rr_new_to_retrofit": row["roof_rr"],
                    "building_count_area_yield_rr_new_to_retrofit": row["building_area_rr"],
                    "information_gate_eligible": row["eligible"],
                    "status": "REPRODUCED descriptive",
                })

    panel_d: list[dict[str, object]] = []
    for city_id in city_order:
        rows = sorted(by_city[city_id], key=lambda row: int(row["transition_index"]))
        eligible = [row for row in rows if row["eligible"]]
        roof_above = sum(float(row["roof_rr"]) > 1 for row in eligible)
        roof_below = sum(float(row["roof_rr"]) < 1 for row in eligible)
        building_above = sum(float(row["building_area_rr"]) > 1 for row in eligible)
        building_below = sum(float(row["building_area_rr"]) < 1 for row in eligible)
        total_area = sum(float(row["pv_area_new"]) + float(row["pv_area_existing"]) for row in eligible)
        largest_area = max(
            float(row["pv_area_new"]) + float(row["pv_area_existing"])
            for row in eligible
        )
        panel_d.append({
            "panel": "d",
            "city_id": city_id,
            "city_display": CITY_NAMES[city_id],
            "city_order": order_lookup[city_id],
            "native_transition_count": len(rows),
            "eligible_transition_count": len(eligible),
            "masked_transition_count": len(rows) - len(eligible),
            "roof_ratio_above_one_count": roof_above,
            "roof_ratio_below_one_count": roof_below,
            "roof_ratio_direction_switch_observed": roof_above > 0 and roof_below > 0,
            "building_area_ratio_above_one_count": building_above,
            "building_area_ratio_below_one_count": building_below,
            "building_area_ratio_direction_switch_observed": building_above > 0 and building_below > 0,
            "largest_eligible_transition_share_of_strict_pv_area": largest_area / total_area,
            "eligible_strict_pv_area_m2": total_area,
            "summary_estimand": "roof-area-normalized ratio primary; Building-count-normalized area-yield switch comparator",
            "status": "REPRODUCED descriptive",
        })

    return panel_a, panel_b, panel_c, panel_d


def draw_panel_a(
    axis: plt.Axes,
    color_axis: plt.Axes,
    rows: list[dict[str, object]],
    city_order: list[str],
    display_limit: float,
) -> None:
    max_transition = max(int(row["transition_index"]) for row in rows)
    lookup = {(str(row["city_id"]), int(row["transition_index"])): row for row in rows}
    cmap = LinearSegmentedColormap.from_list("existing_neutral_new", [EXISTING, "#f7f7f5", NEW])
    norm = TwoSlopeNorm(vmin=-display_limit, vcenter=0.0, vmax=display_limit)
    for y, city_id in enumerate(city_order):
        city_rows = [row for row in rows if row["city_id"] == city_id]
        native_count = max(int(row["transition_index"]) for row in city_rows)
        for transition_index in range(1, max_transition + 1):
            x = transition_index - 1
            if transition_index > native_count:
                continue
            row = lookup[(city_id, transition_index)]
            if row["information_gate_eligible"]:
                color = cmap(norm(float(row["log2_roof_area_yield_rr"])))
                patch = Rectangle((x - 0.46, y - 0.40), 0.92, 0.80,
                                  facecolor=color, edgecolor="white", lw=0.55)
            else:
                patch = Rectangle((x - 0.46, y - 0.40), 0.92, 0.80,
                                  facecolor=UNAVAILABLE, edgecolor=MUTED, lw=0.45,
                                  hatch="////")
            axis.add_patch(patch)
    axis.set_xlim(-0.55, max_transition - 0.45)
    axis.set_ylim(len(city_order) - 0.45, -0.55)
    axis.set_xticks(np.arange(max_transition), [str(i) for i in range(1, max_transition + 1)])
    axis.set_xlabel("")
    axis.set_yticks(np.arange(len(city_order)), [CITY_NAMES[city_id] for city_id in city_order])
    axis.tick_params(axis="both", length=0)
    axis.tick_params(axis="y", labelcolor=TEXT)
    axis.grid(False)
    for spine in axis.spines.values():
        spine.set_visible(False)
    scalar = mpl.cm.ScalarMappable(norm=norm, cmap=cmap)
    cbar = plt.colorbar(scalar, cax=color_axis, orientation="horizontal")
    cbar.set_ticks([-3, -2, -1, 0, 1, 2, 3])
    cbar.set_ticklabels(["1/8", "1/4", "1/2", "1", "2", "4", "8"])
    cbar.set_label(r"PV area per roof area ratio, new / existing", fontsize=6.2, labelpad=1.5)
    color_axis.xaxis.set_ticks_position("bottom")
    color_axis.xaxis.set_label_position("top")
    color_axis.tick_params(
        axis="x", top=False, bottom=True, labeltop=False, labelbottom=True,
        labelsize=5.4, length=2.0, width=0.5, pad=1.0,
    )
    cbar.outline.set_linewidth(0.5)


def draw_panel_b(
    axis: plt.Axes,
    rows: list[dict[str, object]],
    city_order: list[str],
) -> None:
    offsets = {"count_rr": -0.20, "pv_area_per_building": 0.0, "pv_area_per_roof_m2": 0.20}
    markers = {"count_rr": "o", "pv_area_per_building": "D", "pv_area_per_roof_m2": "s"}
    max_transition = max(int(row["transition_index"]) for row in rows)
    grouped: dict[tuple[str, int], list[dict[str, object]]] = defaultdict(list)
    for row in rows:
        grouped[(str(row["city_id"]), int(row["transition_index"]))].append(row)
    for y, city_id in enumerate(city_order):
        native_indices = sorted(index for (city, index) in grouped if city == city_id)
        for transition_index in native_indices:
            cell = grouped[(city_id, transition_index)]
            eligible = bool(cell[0]["information_gate_eligible"])
            if not eligible:
                axis.add_patch(Rectangle(
                    (transition_index - 1 - 0.46, y - 0.40), 0.92, 0.80,
                    facecolor=UNAVAILABLE, edgecolor=MUTED, lw=0.45, hatch="////",
                ))
                continue
            if bool(cell[0]["any_three_metric_direction_disagreement"]):
                axis.add_patch(Rectangle(
                    (transition_index - 1 - 0.43, y - 0.36), 0.86, 0.72,
                    facecolor="none", edgecolor=AREA, lw=0.65,
                ))
            for row in cell:
                metric = str(row["metric"])
                direction_color = NEW if row["direction"] == "newly_observed_higher" else EXISTING
                axis.scatter(
                    transition_index - 1 + offsets[metric], y,
                    marker=markers[metric], s=15 if metric != "pv_area_per_roof_m2" else 18,
                    facecolor=direction_color if metric == "pv_area_per_roof_m2" else "white",
                    edgecolor=direction_color, lw=0.8, zorder=3,
                )
    axis.set_xlim(-0.55, max_transition - 0.45)
    axis.set_ylim(len(city_order) - 0.45, -0.55)
    axis.set_xticks(np.arange(max_transition), [str(i) for i in range(1, max_transition + 1)])
    axis.set_xlabel("Observed transition order")
    axis.set_yticks(np.arange(len(city_order)))
    axis.tick_params(axis="y", labelleft=False, length=0)
    axis.tick_params(axis="x", length=0)
    axis.grid(False)
    for spine in axis.spines.values():
        spine.set_visible(False)


def draw_panel_c(
    figure: plt.Figure,
    subgrid: mpl.gridspec.SubplotSpec,
    rows: list[dict[str, object]],
    selected_cities: list[tuple[str, str]],
) -> list[plt.Axes]:
    inner = subgrid.subgridspec(3, 2, hspace=0.26, wspace=0.24)
    axes: list[plt.Axes] = []
    route_specs = {
        "newly_observed": (NEW, "s"),
        "existing": (EXISTING, "o"),
    }
    for row_index, (city_id, selection_role) in enumerate(selected_cities):
        city_rows = [row for row in rows if row["city_id"] == city_id]
        axis_rate = figure.add_subplot(inner[row_index, 0])
        axis_size = figure.add_subplot(inner[row_index, 1], sharex=axis_rate)
        axes.extend([axis_rate, axis_size])
        for route, (color, marker) in route_specs.items():
            route_rows = sorted(
                [row for row in city_rows if row["route"] == route],
                key=lambda row: int(row["transition_index"]),
            )
            x = [int(row["transition_index"]) for row in route_rows]
            rates = [
                float(row["event_proportion_per_1000_risk_units"])
                if row["information_gate_eligible"] else np.nan
                for row in route_rows
            ]
            sizes = [
                float(row["mean_pv_area_per_event_m2"])
                if row["information_gate_eligible"] else np.nan
                for row in route_rows
            ]
            axis_rate.plot(x, rates, color=color, marker=marker, ms=3.7, lw=1.0, zorder=3)
            axis_size.plot(x, sizes, color=color, marker=marker, ms=3.7, lw=1.0, zorder=3)
        native_count = max(int(row["transition_index"]) for row in city_rows)
        masked_x = sorted({
            int(row["transition_index"]) for row in city_rows
            if not row["information_gate_eligible"]
        })
        for axis in (axis_rate, axis_size):
            axis.set_yscale("log")
            axis.set_xlim(0.7, native_count + 0.3)
            axis.set_xticks(range(1, native_count + 1))
            axis.grid(axis="y", which="major")
            axis.grid(axis="x", visible=False)
            for spine_name in ("left", "bottom"):
                axis.spines[spine_name].set_visible(True)
                axis.spines[spine_name].set_color(TEXT)
                axis.spines[spine_name].set_linewidth(0.65)
                axis.spines[spine_name].set_linestyle("-")
            axis.tick_params(axis="both", color=TEXT)
            for masked_transition in masked_x:
                axis.axvspan(
                    masked_transition - 0.16, masked_transition + 0.16,
                    facecolor=UNAVAILABLE, edgecolor=MUTED, lw=0.35,
                    hatch="////", alpha=0.45, zorder=0,
                )
        if row_index < len(selected_cities) - 1:
            axis_rate.tick_params(axis="x", labelbottom=False)
            axis_size.tick_params(axis="x", labelbottom=False)
        else:
            axis_rate.set_xlabel("Observed transition order")
            axis_size.set_xlabel("Observed transition order")
        axis_rate.set_ylabel(CITY_NAMES[city_id])
        axis_rate.yaxis.label.set_color(TEXT)
        readable_role = {
            "frequency-variation exemplar": "frequency contrast",
            "system-size-variation exemplar": "PV-size contrast",
            "denominator-sensitivity exemplar": "denominator contrast",
        }[selection_role]
        axis_rate.text(
            0.01, 0.93, readable_role,
            transform=axis_rate.transAxes, ha="left", va="top", fontsize=5.2, color=MUTED,
        )
        if row_index == 0:
            axis_rate.set_title("PV additions / 1,000 observations", loc="left", pad=2, fontsize=7.5)
            axis_size.set_title("Average PV area / addition (m²)", loc="left", pad=2, fontsize=7.5)
    return axes


def draw_panel_d(
    figure: plt.Figure,
    subgrid: mpl.gridspec.SubplotSpec,
    rows: list[dict[str, object]],
    city_order: list[str],
) -> list[plt.Axes]:
    inner = subgrid.subgridspec(1, 3, width_ratios=[1.35, 1.0, 0.72], wspace=0.18)
    axis_counts = figure.add_subplot(inner[0, 0])
    axis_share = figure.add_subplot(inner[0, 1], sharey=axis_counts)
    axis_switch = figure.add_subplot(inner[0, 2], sharey=axis_counts)
    lookup = {str(row["city_id"]): row for row in rows}
    y = np.arange(len(city_order))
    below = np.array([int(lookup[city]["roof_ratio_below_one_count"]) for city in city_order])
    above = np.array([int(lookup[city]["roof_ratio_above_one_count"]) for city in city_order])
    shares = np.array([
        100.0 * float(lookup[city]["largest_eligible_transition_share_of_strict_pv_area"])
        for city in city_order
    ])
    axis_counts.barh(y, -below, color=EXISTING, height=0.56)
    axis_counts.barh(y, above, color=NEW, height=0.56)
    axis_counts.axvline(0, color=TEXT, lw=0.65)
    axis_counts.set_xlim(-6.4, 6.4)
    axis_counts.set_xticks([-6, -3, 0, 3, 6], ["6", "3", "0", "3", "6"])
    axis_counts.set_xlabel("Eligible transitions\nbelow / above 1")
    axis_counts.set_yticks(y, [CITY_NAMES[city_id] for city_id in city_order])
    axis_counts.tick_params(axis="y", labelsize=6.1, pad=2.0, labelcolor=TEXT)
    axis_counts.tick_params(axis="y", length=2.5, width=0.65, direction="out", color=TEXT)
    axis_counts.tick_params(axis="x", length=3.0, width=0.65, direction="out", color=TEXT)
    axis_counts.grid(axis="x")
    axis_counts.grid(axis="y", visible=False)

    axis_share.scatter(shares, y, color=AREA, s=18, zorder=3)
    for value, yy in zip(shares, y):
        axis_share.plot([0, value], [yy, yy], color=LIGHT, lw=0.7, zorder=1)
    share_upper = max(105.0, math.ceil(max(shares) / 10) * 10 + 5.0)
    axis_share.set_xlim(0, share_upper)
    axis_share.set_xticks([0, 50, 100])
    axis_share.set_xlabel("PV area in largest\neligible transition (%)")
    axis_share.tick_params(axis="y", labelleft=False, length=0)
    axis_share.grid(axis="x")
    axis_share.grid(axis="y", visible=False)

    for yy, city_id in zip(y, city_order):
        roof_switch = bool(lookup[city_id]["roof_ratio_direction_switch_observed"])
        area_switch = bool(lookup[city_id]["building_area_ratio_direction_switch_observed"])
        axis_switch.scatter(
            0, yy, marker="s", s=22, facecolor=AREA if roof_switch else "white",
            edgecolor=AREA if roof_switch else COUNT, lw=0.85,
        )
        axis_switch.scatter(
            1, yy, marker="D", s=16, facecolor="white",
            edgecolor="#89a7b0" if area_switch else COUNT,
            lw=1.1 if area_switch else 0.75,
        )
        if area_switch:
            axis_switch.scatter(1, yy, marker=".", s=7, color="#89a7b0", zorder=4)
    axis_switch.set_xlim(-0.55, 1.55)
    axis_switch.set_xticks([0, 1], ["per roof\narea", "per\nbuilding"])
    axis_switch.set_xlabel("Direction switch")
    axis_switch.tick_params(axis="x", labelrotation=0, labelsize=5.8)
    axis_switch.tick_params(axis="y", labelleft=False, length=0)
    axis_switch.grid(False)
    for axis in (axis_counts, axis_share, axis_switch):
        axis.set_ylim(len(city_order) - 0.45, -0.55)
        for spine_name in ("left", "bottom"):
            axis.spines[spine_name].set_visible(True)
            axis.spines[spine_name].set_color(TEXT)
            axis.spines[spine_name].set_linewidth(0.65)
            axis.spines[spine_name].set_linestyle("-")
        axis.tick_params(axis="both", color=TEXT)
    return [axis_counts, axis_share, axis_switch]


def main() -> None:
    args = parse_args()
    output_dir = args.output_dir.resolve()
    if (output_dir / "LOCKED").exists():
        raise FileExistsError(
            f"Refusing to overwrite immutable Figure 4 bundle: {output_dir}. "
            "Use a new sibling version directory."
        )
    paths = [
        args.area_transition, args.roof_transition, args.city_area,
        args.area_manifest, args.roof_manifest, args.area_checks, args.roof_checks,
        args.city_order_checks, args.city_order_manifest, args.gate, args.style,
        args.font, args.figure_plan, args.claims_matrix, args.analysis_agenda,
        args.paper_readme,
    ]
    for path in paths:
        if not path.resolve().is_file():
            raise FileNotFoundError(path)

    area_manifest = json.loads(args.area_manifest.read_text(encoding="utf-8"))
    roof_manifest = json.loads(args.roof_manifest.read_text(encoding="utf-8"))
    area_checks = json.loads(args.area_checks.read_text(encoding="utf-8"))
    roof_checks = json.loads(args.roof_checks.read_text(encoding="utf-8"))
    city_order_checks = json.loads(args.city_order_checks.read_text(encoding="utf-8"))
    city_order_manifest = json.loads(args.city_order_manifest.read_text(encoding="utf-8"))
    gate = json.loads(args.gate.read_text(encoding="utf-8"))
    if gate.get("gate_status") != "FROZEN_BEFORE_FIRST_RENDER":
        raise AssertionError("Transition information gate is not frozen")
    if gate.get("scope") != "full_aoi":
        raise AssertionError("Figure 4 primary gate must use full_aoi")

    verify_reproduced_input(
        args.area_transition, area_manifest, "city_transition_area_weighted_stock_flow"
    )
    verify_reproduced_input(args.city_area, area_manifest, "city_area_weighted_stock_flow")
    verify_reproduced_input(
        args.roof_transition, roof_manifest, "city_transition_roof_area_weighted_stock_flow"
    )
    if sha256_file(args.area_checks) != area_manifest["outputs"]["area_weighted_results_checks"]["sha256"]:
        raise AssertionError("Area QA file does not match owning manifest")
    if sha256_file(args.roof_checks) != roof_manifest["qa"]["sha256"]:
        raise AssertionError("Roof-area QA file does not match owning manifest")
    if city_order_manifest.get("status") != "REPRODUCED" or city_order_checks.get("status") != "REPRODUCED":
        raise AssertionError("Figure 3 city-order bundle is not REPRODUCED")
    city_checks_record = city_order_manifest["outputs"][args.city_order_checks.name]
    if sha256_file(args.city_order_checks) != city_checks_record["sha256"]:
        raise AssertionError("Figure 3 city order checks do not match their manifest")

    area_rows_all = read_csv(args.area_transition)
    roof_rows_all = read_csv(args.roof_transition)
    city_area_rows = read_csv(args.city_area)
    area_rows = [row for row in area_rows_all if row["scope"] == "full_aoi"]
    roof_rows = [row for row in roof_rows_all if row["scope"] == "full_aoi"]
    if len(area_rows) != 67 or len(roof_rows) != 67:
        raise AssertionError("Expected exactly 67 full-AOI transitions")
    area_lookup = {transition_key(row): row for row in area_rows}
    roof_lookup = {transition_key(row): row for row in roof_rows}
    if len(area_lookup) != len(area_rows) or len(roof_lookup) != len(roof_rows):
        raise AssertionError("Transition primary keys are not unique")
    if set(area_lookup) != set(roof_lookup):
        raise AssertionError("Area and roof transition keys differ")
    if not validate_native_order(area_rows, roof_manifest["cohort_order_by_city"]):
        raise AssertionError("Native cohort order does not match the owning manifest")

    city_order = list(city_order_checks["city_order"])
    if len(city_order) != 15 or len(set(city_order)) != 15:
        raise AssertionError("Expected 15 unique cities in the shared Figure 3 order")
    if set(city_order) != {row["city_id"] for row in area_rows}:
        raise AssertionError("City order does not cover the transition tables")

    joined: list[dict[str, object]] = []
    for key in sorted(area_lookup, key=lambda item: (city_order.index(item[0]), item[2])):
        area_row = area_lookup[key]
        roof_row = roof_lookup[key]
        identity_fields = ["city_id", "scope", "transition_index", "previous_cohort", "current_cohort",
                           "n_new", "y_new", "n_stock", "y_retrofit", "pv_area_new_m2",
                           "pv_area_retrofit_m2"]
        for field in identity_fields:
            if area_row[field] != roof_row[field]:
                raise AssertionError(f"Area/roof transition mismatch for {key}: {field}")
        eligible, reasons = gate_row(area_row, roof_row, gate)
        joined.append({
            "city_id": area_row["city_id"],
            "transition_index": int(area_row["transition_index"]),
            "previous_cohort": area_row["previous_cohort"],
            "current_cohort": area_row["current_cohort"],
            "n_new": int(area_row["n_new"]),
            "y_new": int(area_row["y_new"]),
            "n_stock": int(area_row["n_stock"]),
            "y_retrofit": int(area_row["y_retrofit"]),
            "roof_area_new": float(roof_row["building_roof_area_new_m2"]),
            "roof_area_existing": float(roof_row["building_roof_area_stock_exposure_m2"]),
            "pv_area_new": float(area_row["pv_area_new_m2"]),
            "pv_area_existing": float(area_row["pv_area_retrofit_m2"]),
            "count_rr": float(area_row["count_rr_new_to_retrofit"]),
            "building_area_rr": float(area_row["area_yield_rr_new_to_retrofit"]),
            "roof_rr": float(roof_row["roof_area_yield_rr_new_to_retrofit"]),
            "event_rate_new": float(area_row["r_new_event_per_building"]),
            "event_rate_existing": float(area_row["r_retrofit_event_per_building_cohort"]),
            "mean_area_new": float(area_row["mean_pv_area_per_new_event_m2"]),
            "mean_area_existing": float(area_row["mean_pv_area_per_retrofit_event_m2"]),
            "eligible": eligible,
            "gate_failure_reasons": reasons,
        })

    selected_cities = select_panel_c_cities(joined, gate["panel_c_selection_rule"])
    panel_a, panel_b, panel_c, panel_d = derive_panel_rows(joined, city_order, selected_cities)

    city_area_lookup = {
        row["city_id"]: row for row in city_area_rows
        if row["scope"] == "full_aoi" and row["city_id"] != "all_cities_pooled"
    }
    transition_area_reconciliation: dict[str, dict[str, float]] = {}
    max_relative_residual = 0.0
    for city_id in city_order:
        city_transitions = [row for row in joined if row["city_id"] == city_id]
        transition_new = sum(float(row["pv_area_new"]) for row in city_transitions)
        transition_existing = sum(float(row["pv_area_existing"]) for row in city_transitions)
        city_new = float(city_area_lookup[city_id]["pv_area_new_m2"])
        city_existing = float(city_area_lookup[city_id]["pv_area_retrofit_m2"])
        residual = max(abs(transition_new - city_new), abs(transition_existing - city_existing))
        scale = max(city_new, city_existing, 1.0)
        max_relative_residual = max(max_relative_residual, residual / scale)
        if not close(transition_new, city_new) or not close(transition_existing, city_existing):
            raise AssertionError(f"Transition areas do not reconcile to city total: {city_id}")
        transition_area_reconciliation[city_id] = {
            "transition_new_m2": transition_new,
            "city_new_m2": city_new,
            "transition_existing_m2": transition_existing,
            "city_existing_m2": city_existing,
        }

    output_dir.mkdir(parents=True, exist_ok=True)
    panel_a_path = output_dir / "figure4_panel_a_data.csv"
    panel_b_path = output_dir / "figure4_panel_b_data.csv"
    panel_c_path = output_dir / "figure4_panel_c_data.csv"
    panel_d_path = output_dir / "figure4_panel_d_data.csv"
    write_csv(panel_a_path, panel_a)
    write_csv(panel_b_path, panel_b)
    write_csv(panel_c_path, panel_c)
    write_csv(panel_d_path, panel_d)

    font_name = configure_style(args.style.resolve(), args.font.resolve())
    figure = plt.figure(figsize=(FIGURE_WIDTH_IN, FIGURE_HEIGHT_IN), facecolor="white")
    outer = figure.add_gridspec(
        2, 2, width_ratios=[1.12, 1.0], height_ratios=[1.0, 1.0],
        left=0.105, right=0.985, top=0.90, bottom=0.075, wspace=0.08, hspace=0.28,
    )
    axis_a = figure.add_subplot(outer[0, 0])
    axis_b = figure.add_subplot(outer[0, 1], sharey=axis_a)
    panel_a_bbox = axis_a.get_position()
    colorbar_width = panel_a_bbox.width * COLORBAR_WIDTH_FRACTION_OF_PANEL_A
    colorbar_height = COLORBAR_HEIGHT_IN / FIGURE_HEIGHT_IN
    colorbar_left = panel_a_bbox.x0 + (panel_a_bbox.width - colorbar_width) / 2.0
    colorbar_bottom = panel_a_bbox.y1 + COLORBAR_GAP_ABOVE_PANEL_A
    axis_a_color = figure.add_axes(
        [colorbar_left, colorbar_bottom, colorbar_width, colorbar_height]
    )
    draw_panel_a(
        axis_a, axis_a_color, panel_a, city_order,
        float(gate["display_rule"]["heatmap_symmetric_display_limit_log2"]),
    )
    draw_panel_b(axis_b, panel_b, city_order)
    c_axes = draw_panel_c(figure, outer[1, 0], panel_c, selected_cities)
    d_axes = draw_panel_d(figure, outer[1, 1], panel_d, city_order)

    figure.canvas.draw()
    renderer = figure.canvas.get_renderer()
    inverse_figure = figure.transFigure.inverted()
    panel_a_visible_bbox = axis_a.get_tightbbox(renderer).transformed(inverse_figure)
    panel_c_visible_bboxes = [
        axis.get_tightbbox(renderer).transformed(inverse_figure) for axis in c_axes
    ]
    panel_c_visible_left_before = min(bbox.x0 for bbox in panel_c_visible_bboxes)
    panel_c_left_shift = panel_a_visible_bbox.x0 - panel_c_visible_left_before
    for axis in c_axes:
        position = axis.get_position()
        axis.set_position([
            position.x0 + panel_c_left_shift,
            position.y0,
            position.width,
            position.height,
        ])
    figure.canvas.draw()
    renderer = figure.canvas.get_renderer()
    panel_c_visible_bboxes = [
        axis.get_tightbbox(renderer).transformed(inverse_figure) for axis in c_axes
    ]
    panel_c_visible_left_after = min(bbox.x0 for bbox in panel_c_visible_bboxes)
    panel_c_visible_left_aligned = bool(np.isclose(
        panel_a_visible_bbox.x0, panel_c_visible_left_after, atol=0.001
    ))
    if not panel_c_visible_left_aligned:
        raise AssertionError("Panel c visible left edge is not aligned with panel a")

    top_left_bbox = outer[0, 0].get_position(figure)
    top_right_bbox = outer[0, 1].get_position(figure)
    bottom_left_bbox = outer[1, 0].get_position(figure)
    bottom_right_bbox = outer[1, 1].get_position(figure)
    panel_label_x_left = max(0.008, top_left_bbox.x0 - 0.095)
    panel_label_x_right = top_right_bbox.x0 - 0.045
    panel_label_y_top = 0.957
    panel_label_y_bottom = bottom_left_bbox.y1 + 0.030
    panel_label_positions = {
        "a": [panel_label_x_left, panel_label_y_top],
        "b": [panel_label_x_right, panel_label_y_top],
        "c": [panel_label_x_left, panel_label_y_bottom],
        "d": [panel_label_x_right, panel_label_y_bottom],
    }
    for label, (x_position, y_position) in panel_label_positions.items():
        figure.text(
            x_position, y_position, f"{label},", ha="left", va="top",
            fontsize=9.5, color=TEXT,
        )

    panel_ab_share_y_joined = bool(axis_a.get_shared_y_axes().joined(axis_a, axis_b))
    panel_ab_y_limits_equal = bool(np.allclose(axis_a.get_ylim(), axis_b.get_ylim()))
    panel_ab_axes_bbox_aligned = bool(np.allclose(
        [axis_a.get_position().y0, axis_a.get_position().y1],
        [axis_b.get_position().y0, axis_b.get_position().y1],
    ))
    panel_a_colorbar_above = bool(
        axis_a_color.get_position().y0 > axis_a.get_position().y1
    )
    panel_a_colorbar_width_fraction = (
        axis_a_color.get_position().width / axis_a.get_position().width
    )
    panel_a_colorbar_height_inches = axis_a_color.get_position().height * FIGURE_HEIGHT_IN
    panel_a_colorbar_height_fraction_of_previous = (
        panel_a_colorbar_height_inches / PREVIOUS_COLORBAR_HEIGHT_IN
    )
    panel_rows_equal_overall_height = bool(np.isclose(
        top_left_bbox.height, bottom_left_bbox.height
    ))
    panel_label_four_corner_alignment = bool(
        panel_label_positions["a"][0] == panel_label_positions["c"][0]
        and panel_label_positions["b"][0] == panel_label_positions["d"][0]
        and panel_label_positions["a"][1] == panel_label_positions["b"][1]
        and panel_label_positions["c"][1] == panel_label_positions["d"][1]
    )
    if not (
        panel_ab_share_y_joined
        and panel_ab_y_limits_equal
        and panel_ab_axes_bbox_aligned
        and panel_a_colorbar_above
        and panel_rows_equal_overall_height
        and panel_label_four_corner_alignment
    ):
        raise AssertionError("Panel row heights, shared y axis, or four-corner labels are misaligned")

    black_rgba = mpl.colors.to_rgba(TEXT)
    city_label_artists = (
        list(axis_a.get_yticklabels())
        + list(d_axes[0].get_yticklabels())
        + [c_axes[index].yaxis.label for index in (0, 2, 4)]
    )
    all_city_y_labels_black = bool(all(
        np.allclose(mpl.colors.to_rgba(artist.get_color()), black_rgba)
        for artist in city_label_artists
    ))
    if not all_city_y_labels_black:
        raise AssertionError("A city y-axis label is not black")
    panel_cd_axes_black_solid = bool(all(
        axis.spines[spine].get_visible()
        and np.allclose(axis.spines[spine].get_edgecolor(), black_rgba)
        and axis.spines[spine].get_linestyle() in ("-", "solid")
        for axis in c_axes + d_axes
        for spine in ("left", "bottom")
    ))
    if not panel_cd_axes_black_solid:
        raise AssertionError("A panel c or d visible axis is not a solid black line")

    panel_d_left_ticks_visible = bool(
        d_axes[0].xaxis.majorTicks[0].tick1line.get_markersize() > 0
        and d_axes[0].yaxis.majorTicks[0].tick1line.get_markersize() > 0
    )
    atlanta_share = next(
        100.0 * float(row["largest_eligible_transition_share_of_strict_pv_area"])
        for row in panel_d if row["city_id"] == "atlanta"
    )
    panel_d_atlanta_marker_inside_xlim = bool(
        d_axes[1].get_xlim()[0] < atlanta_share < d_axes[1].get_xlim()[1]
    )
    if not panel_d_left_ticks_visible or not panel_d_atlanta_marker_inside_xlim:
        raise AssertionError("Panel d ticks or Atlanta marker margin check failed")

    legend_handles = [
        Patch(facecolor=NEW, edgecolor=NEW, label="new higher"),
        Patch(facecolor=EXISTING, edgecolor=EXISTING, label="existing higher"),
        Line2D([0], [0], marker="o", markerfacecolor="white", markeredgecolor=COUNT,
               lw=0, label="PV addition rate"),
        Line2D([0], [0], marker="D", markerfacecolor="white", markeredgecolor=COUNT,
               lw=0, label="PV area / building"),
        Line2D([0], [0], marker="s", markerfacecolor="white", markeredgecolor=COUNT,
               lw=0, label="PV area / roof"),
        Patch(facecolor=UNAVAILABLE, edgecolor=MUTED, hatch="////", label="insufficient evidence"),
    ]
    legend_y = (top_left_bbox.y0 + bottom_left_bbox.y1) / 2.0 - LEGEND_DOWN_SHIFT
    figure.legend(
        handles=legend_handles, loc="center", bbox_to_anchor=(0.545, legend_y),
        ncol=6, columnspacing=0.72, handletextpad=0.30, frameon=False,
        fontsize=5.4,
    )
    for artist in figure.findobj(match=lambda item: hasattr(item, "set_fontfamily")):
        try:
            artist.set_fontfamily(font_name)
        except (AttributeError, TypeError):
            pass

    png_path = output_dir / "figure4_transition_dynamics_v1.png"
    pdf_path = output_dir / "figure4_transition_dynamics_v1.pdf"
    figure.savefig(png_path, dpi=300, facecolor="white")
    figure.savefig(pdf_path, facecolor="white")
    plt.close(figure)

    eligible_rows = [row for row in joined if row["eligible"]]
    masked_rows = [row for row in joined if not row["eligible"]]
    roof_switch_cities = [
        row["city_id"] for row in panel_d if row["roof_ratio_direction_switch_observed"]
    ]
    building_switch_cities = [
        row["city_id"] for row in panel_d if row["building_area_ratio_direction_switch_observed"]
    ]
    count_area_disagreements = sum(
        (float(row["count_rr"]) > 1) != (float(row["building_area_rr"]) > 1)
        for row in eligible_rows
    )
    count_roof_disagreements = sum(
        (float(row["count_rr"]) > 1) != (float(row["roof_rr"]) > 1)
        for row in eligible_rows
    )
    area_roof_disagreements = sum(
        (float(row["building_area_rr"]) > 1) != (float(row["roof_rr"]) > 1)
        for row in eligible_rows
    )
    any_three_disagreements = sum(
        len({float(row[metric]) > 1 for metric in ("count_rr", "building_area_rr", "roof_rr")}) > 1
        for row in eligible_rows
    )
    checks_path = output_dir / "figure4_checks.json"
    checks = {
        "schema_version": "figure4-transition-dynamics-checks-v1",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": "REPRODUCED",
        "scope": "full_aoi",
        "canvas_dimensions_inches": [FIGURE_WIDTH_IN, FIGURE_HEIGHT_IN],
        "canvas_scaled_to_three_quarters_of_previous_dimensions": True,
        "outer_grid_width_space": 0.08,
        "outer_grid_height_space": 0.28,
        "outer_grid_width_space_reduced_from": 0.22,
        "outer_grid_height_space_reduced_from": 0.70,
        "panel_rows_equal_overall_height": panel_rows_equal_overall_height,
        "panel_c_visible_left_aligned_with_panel_a": panel_c_visible_left_aligned,
        "panel_c_left_shift_figure_fraction": panel_c_left_shift,
        "panel_a_visible_left_figure_fraction": panel_a_visible_bbox.x0,
        "panel_c_visible_left_figure_fraction": panel_c_visible_left_after,
        "panel_label_positions_figure_fraction": panel_label_positions,
        "panel_labels_aligned_to_four_grid_corners": panel_label_four_corner_alignment,
        "source_manifests_reproduced": True,
        "source_table_hashes_match_manifests": True,
        "source_qa_hashes_match_manifests": True,
        "transition_information_gate_frozen_before_render": True,
        "transition_information_gate_sha256": sha256_file(args.gate),
        "minimum_strict_first_event_hosts_per_route": gate["eligibility_rule"]["minimum_strict_first_event_hosts_per_route"],
        "full_aoi_transition_count": len(joined),
        "eligible_transition_count": len(eligible_rows),
        "masked_transition_count": len(masked_rows),
        "masked_transition_keys": [
            f"{row['city_id']}:{row['transition_index']}" for row in masked_rows
        ],
        "city_count": len(city_order),
        "city_order": city_order,
        "city_order_matches_figure3": True,
        "native_cohort_order_matches_roof_manifest": True,
        "all_three_ratios_finite_and_positive_in_eligible_cells": all(
            finite(float(row[metric])) and float(row[metric]) > 0
            for row in eligible_rows for metric in ("count_rr", "building_area_rr", "roof_rr")
        ),
        "directions_computed_from_unrounded_values": True,
        "count_vs_building_area_direction_disagreement_count_eligible": count_area_disagreements,
        "count_vs_roof_area_direction_disagreement_count_eligible": count_roof_disagreements,
        "building_area_vs_roof_area_direction_disagreement_count_eligible": area_roof_disagreements,
        "any_three_metric_direction_disagreement_count_eligible": any_three_disagreements,
        "roof_area_ratio_switch_city_count_eligible": len(roof_switch_cities),
        "roof_area_ratio_switch_cities_eligible": roof_switch_cities,
        "building_area_ratio_switch_city_count_eligible": len(building_switch_cities),
        "building_area_ratio_switch_cities_eligible": building_switch_cities,
        "panel_c_selection_rule_frozen_before_render": True,
        "panel_c_selected_cities": [
            {"city_id": city_id, "role": role} for city_id, role in selected_cities
        ],
        "panel_row_counts": {
            "a": len(panel_a), "b": len(panel_b), "c": len(panel_c), "d": len(panel_d),
        },
        "panel_primary_keys": {
            "a": ["city_id", "transition_index"],
            "b": ["city_id", "transition_index", "metric"],
            "c": ["city_id", "transition_index", "route"],
            "d": ["city_id"],
        },
        "panel_primary_keys_unique": {
            "a": len({(row["city_id"], row["transition_index"]) for row in panel_a}) == len(panel_a),
            "b": len({(row["city_id"], row["transition_index"], row["metric"]) for row in panel_b}) == len(panel_b),
            "c": len({(row["city_id"], row["transition_index"], row["route"]) for row in panel_c}) == len(panel_c),
            "d": len({row["city_id"] for row in panel_d}) == len(panel_d),
        },
        "transition_area_sums_reconcile_to_city_totals": True,
        "transition_area_reconciliation_max_relative_residual": max_relative_residual,
        "transition_area_reconciliation": transition_area_reconciliation,
        "heatmap_display_limit_log2": gate["display_rule"]["heatmap_symmetric_display_limit_log2"],
        "masked_cells_hatched_not_zero": True,
        "structurally_absent_cells_blank": True,
        "single_shared_legend": True,
        "shared_legend_location": "single row shifted downward within the narrowed inter-row whitespace",
        "shared_legend_down_shift_figure_fraction": LEGEND_DOWN_SHIFT,
        "legend_to_panel_cd_vertical_space_increased_from_previous": True,
        "panel_a_b_share_y_axis": panel_ab_share_y_joined,
        "panel_a_b_y_limits_equal": panel_ab_y_limits_equal,
        "panel_a_b_axes_bbox_aligned": panel_ab_axes_bbox_aligned,
        "panel_a_horizontal_colorbar_above": panel_a_colorbar_above,
        "panel_a_colorbar_gap_above_axis_figure_fraction": COLORBAR_GAP_ABOVE_PANEL_A,
        "panel_a_colorbar_width_fraction_of_panel_a": panel_a_colorbar_width_fraction,
        "panel_a_colorbar_height_inches": panel_a_colorbar_height_inches,
        "panel_a_colorbar_height_fraction_of_previous": panel_a_colorbar_height_fraction_of_previous,
        "panel_a_colorbar_font_sizes_points": {"label": 6.2, "ticks": 5.4},
        "panel_c_d_visible_axes_black_solid": panel_cd_axes_black_solid,
        "all_city_y_axis_labels_black": all_city_y_labels_black,
        "panel_d_left_subplot_ticks_visible": panel_d_left_ticks_visible,
        "panel_d_city_labels_inside_left_axis": False,
        "panel_d_city_labels_restored_outside_axis": True,
        "panel_d_atlanta_marker_inside_xlim": panel_d_atlanta_marker_inside_xlim,
        "panel_c_uses_aligned_tracks_not_dual_axis": True,
        "panel_d_roof_switch_is_primary": True,
        "panel_d_building_area_switch_is_comparator": True,
        "no_inferential_intervals_displayed": True,
        "status_is_descriptive_not_inferential": True,
    }
    if not all(checks["panel_primary_keys_unique"].values()):
        raise AssertionError("A panel output primary key is not unique")
    write_json(checks_path, checks)

    note_path = output_dir / "figure4_note.md"
    note_path.write_text(
        f"""# Figure 4 transition-dynamics note

Figure 4 compares new- and existing-Building rooftop-PV pathways within each city's original adjacent cohort grid. Panel a's primary estimand is the ratio `(A_new / B_roof_new) / (A_retrofit / B_roof_stock)`, where the existing denominator is plan-view roof area summed over eligible existing-Building observations at the start of each transition. Panel b shows whether the PV-addition rate ratio, PV area per Building ratio, and PV area per roof area ratio lie on the same side of one. Panel c separates PV-addition frequency from average PV area per classified addition for three cities selected by the deterministic rule frozen in `transition_information_gate_v1.json`. Panel d summarizes switching in the roof-area ratio as the primary result and switching in PV area per Building as a lighter comparator.

The information gate was frozen before the first rendering. A transition is displayed only when both pathways contain at least {gate['eligibility_rule']['minimum_strict_first_event_hosts_per_route']} classified PV additions, both plan-view roof-area denominators and both attributed anchor PV-area totals are positive, and all three ratios are finite and positive. Ineligible observed cells are hatched; structurally absent cells are blank. The main gate retains {len(eligible_rows)} of 67 full-AOI transitions and masks {len(masked_rows)}. Thresholds of 5 and 20 additions per pathway are reserved for sensitivity analysis and were not used to tune the main figure.

PV union area is the anchor-year area on each unique host attributed to its first strict adjacent PV event; later within-host expansion is not time-resolved. Cohort labels are opaque ordered observations, transition durations may differ, and the figure does not show annual volatility, exact cohort capacity additions, usable-roof utilization, measured nameplate capacity, policy response, or causal effects. No continuous-outcome inferential intervals are available or displayed.

Status: `REPRODUCED` (descriptive candidate rendering).
""",
        encoding="utf-8",
    )
    caption_path = output_dir / "figure4_caption.md"
    caption_path.write_text(
        f"""**The new-Building PV-area advantage changes direction across observed cohort transitions.** (a) The heatmap shows the base-2 logarithm of the ratio of anchor PV area per plan-view roof area for new versus existing Buildings within each city's original adjacent cohort grid. Terracotta cells indicate higher new-Building values, green cells indicate higher existing-Building values, and hatched cells lack sufficient transition evidence; blank cells are structurally absent because cities contain different numbers of transitions. For existing Buildings, roof area is summed over eligible Building observations at the start of each transition. (b) Aligned symbols show the direction of the PV-addition rate ratio (circles), PV area per Building ratio (diamonds), and PV area per roof area ratio (squares); blue outlines identify transitions in which the three diagnostics do not lie on the same side of one. (c) For three deterministically selected switching cities, aligned tracks separate classified PV additions per 1,000 eligible observations from average anchor PV area per addition. The new-Building denominator counts Buildings first observed in the transition, whereas the existing-Building denominator counts eligible Building observations carried into the transition. These tracks diagnose frequency and PV-size contributions; panel b separately shows changes introduced by roof-area normalization. (d) Diverging bars count eligible roof-area ratios below and above one, blue dots give the percentage of eligible classified PV area in the largest transition, and the final columns mark observed direction switching for the primary roof-area ratio and the lighter per-Building comparator. The gate requires at least {gate['eligibility_rule']['minimum_strict_first_event_hosts_per_route']} classified PV additions in each pathway together with positive PV-area totals, positive roof-area denominators, and finite ratios. Cohort intervals may have unequal durations; switching is descriptive and does not identify annual volatility, exact capacity additions, policy response, or a causal mechanism. Anchor PV union area on a Building is assigned to its first classified adjacent PV addition, plan-view roof-mask area is not usable roof surface, and no inferential intervals are shown.
""",
        encoding="utf-8",
    )

    manifest_path = output_dir / "figure4_manifest.json"
    script_path = Path(__file__).resolve()
    input_records = [
        source_record(args.area_transition, "REPRODUCED transition-level area stock-flow table", len(area_rows_all)),
        source_record(args.roof_transition, "REPRODUCED transition-level roof-area stock-flow table", len(roof_rows_all)),
        source_record(args.city_area, "REPRODUCED city area stock-flow reconciliation table", len(city_area_rows)),
        source_record(args.area_manifest, "owning area-weighted results manifest"),
        source_record(args.roof_manifest, "owning roof-area-weighted results manifest"),
        source_record(args.area_checks, "area-weighted results QA"),
        source_record(args.roof_checks, "roof-area-weighted results QA"),
        source_record(args.city_order_checks, "Figure 3 stable city order checks"),
        source_record(args.city_order_manifest, "Figure 3 city-order owning manifest"),
        source_record(args.gate, "prespecified frozen transition information gate"),
        source_record(args.style, "shared plotting style"),
        source_record(args.font, "embedded plotting font"),
        source_record(args.figure_plan, "Figure 4 design contract"),
        source_record(args.claims_matrix, "claims and evidence ledger"),
        source_record(args.analysis_agenda, "scientific interpretation agenda"),
        source_record(args.paper_readme, "paper architecture and status vocabulary"),
    ]
    outputs = {
        path.name: output_record(path, row_count)
        for path, row_count in [
            (png_path, None), (pdf_path, None),
            (panel_a_path, len(panel_a)), (panel_b_path, len(panel_b)),
            (panel_c_path, len(panel_c)), (panel_d_path, len(panel_d)),
            (checks_path, None), (note_path, None), (caption_path, None),
        ]
    }
    manifest = {
        "schema_version": "figure4-transition-dynamics-manifest-v1",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": "REPRODUCED",
        "evidence_scope": "descriptive full_aoi",
        "command": "python3 paper/figures/figure4_transition_dynamics/figure4_transition_dynamics.py",
        "generator": {
            "path": str(script_path),
            "version": SCRIPT_VERSION,
            "sha256": sha256_file(script_path),
        },
        "input_primary_keys": {
            "area_transition": ["city_id", "scope", "transition_index"],
            "roof_transition": ["city_id", "scope", "transition_index"],
            "city_area": ["city_id", "scope"],
        },
        "output_primary_keys": checks["panel_primary_keys"],
        "filters": [
            "scope == full_aoi",
            "retain native adjacent transitions without bridging unknown or missing observations",
            "apply transition_information_gate_v1.json identically to panels a--d",
        ],
        "exclusions": [
            "cells with fewer than 10 strict first-event hosts in either route are hatched",
            "cells without positive PV-area numerators or positive roof-area risk denominators are hatched",
            "cells without finite positive count, Building-area, and roof-area ratios are hatched",
            "no continuity corrections and no conversion of unavailable cells to zero",
        ],
        "denominator_definitions": roof_manifest["denominator_definitions"],
        "cohort_order_by_city": roof_manifest["cohort_order_by_city"],
        "city_order": city_order,
        "city_order_source": str(args.city_order_checks.resolve()),
        "panel_c_selection": [
            {"city_id": city_id, "role": role} for city_id, role in selected_cities
        ],
        "inputs": input_records,
        "outputs": outputs,
    }
    write_json(manifest_path, manifest)

    print(f"Wrote {png_path}")
    print(f"Wrote {pdf_path}")
    print(f"Eligible transitions: {len(eligible_rows)}/67")
    print("Panel c: " + ", ".join(f"{city_id} ({role})" for city_id, role in selected_cities))


if __name__ == "__main__":
    main()
