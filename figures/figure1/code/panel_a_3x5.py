#!/usr/bin/env python3
"""Render the Atlanta Figure 1a design for 15 cities in a 3-row by 5-column grid."""

from __future__ import annotations

import argparse
import json
import math
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from matplotlib import font_manager
from matplotlib.lines import Line2D
from matplotlib.patches import Patch
from matplotlib.ticker import FuncFormatter, MaxNLocator

from figure1 import read_csv, sha256_file, verified_table, write_csv, write_json


SCRIPT_VERSION = "0.11.0"
FONT_PATH = Path(__file__).resolve().parents[3] / "arial.ttf"
if not FONT_PATH.is_file():
    raise FileNotFoundError(f"Required Arial font is missing: {FONT_PATH}")
font_manager.fontManager.addfont(str(FONT_PATH))
FONT = font_manager.FontProperties(fname=str(FONT_PATH)).get_name()
BLACK = "#000000"
GRID = "#d8dddc"
PV_BASELINE = "#356f83"
PV_POSTBASELINE = "#c97c5d"
BUILDING_BASELINE = "#d9dddc"
BUILDING_POSTBASELINE = "#aeb7b4"
BAR_WIDTH = 0.78


def parse_args() -> argparse.Namespace:
    workspace = Path(__file__).resolve().parents[3]
    figure_dir = Path(__file__).resolve().parent
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--data-dir", type=Path, default=workspace / "data_high_level"
    )
    parser.add_argument(
        "--index",
        type=Path,
        default=workspace / "results" / "major_results_index.json",
    )
    parser.add_argument(
        "--cohort-ranges",
        type=Path,
        default=workspace / "config" / "city_cohort_ranges.csv",
    )
    parser.add_argument("--output-dir", type=Path, default=figure_dir / "output")
    return parser.parse_args()


def pv_tick(value: float, _: int) -> str:
    if math.isclose(value, 0.0, abs_tol=1e-12):
        return "0"
    magnitude = abs(value)
    if magnitude >= 10:
        return f"{magnitude:.0f}"
    if magnitude >= 1:
        return f"{magnitude:.1f}"
    return f"{magnitude:.2f}"


def main() -> None:
    args = parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    plt.rcParams.update(
        {
            "font.family": FONT,
            "font.weight": "normal",
            "text.color": BLACK,
            "axes.labelcolor": BLACK,
            "xtick.color": BLACK,
            "ytick.color": BLACK,
            "pdf.fonttype": 42,
            "ps.fonttype": 42,
            "savefig.bbox": None,
        }
    )

    input_manifest = args.data_dir / "city_pv_building_area_manifest.json"
    table_path, input_record = verified_table(
        input_manifest, "tables", "city_pv_building_area_trajectories"
    )
    area_manifest = args.data_dir / "area_weighted_results_manifest.json"
    area_path, area_input = verified_table(
        area_manifest, "outputs", "city_area_temporal_contrast"
    )
    all_rows = read_csv(table_path)
    area_rows = {row["city_id"]: row for row in read_csv(area_path)}
    panel_c_path = args.output_dir / "figure1_panel_c_lag_data.csv"
    if not panel_c_path.is_file():
        raise FileNotFoundError(
            "Panel c plotted data is required to define the requested city order: "
            f"{panel_c_path}"
        )
    panel_c_rows = read_csv(panel_c_path)
    left_censored_share: dict[str, float] = {}
    for row in panel_c_rows:
        city_id = row["city_id"]
        if city_id == "all_cities_pooled":
            continue
        value = float(row["composition_left_censored_percent"])
        if city_id in left_censored_share and not math.isclose(
            left_censored_share[city_id], value, abs_tol=1e-12
        ):
            raise ValueError(f"Panel c left-censored share varies within city: {city_id}")
        left_censored_share[city_id] = value
    by_city: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in all_rows:
        by_city[row["city_id"]].append(row)
    for rows in by_city.values():
        rows.sort(key=lambda row: int(row["calendar_year"]))
    cities = [
        city_id
        for city_id, _ in sorted(
            (
                (city_id, int(rows[0]["city_order"]))
                for city_id, rows in by_city.items()
            ),
            key=lambda item: item[1],
        )
    ]
    if len(cities) != 15:
        raise ValueError(f"Expected 15 cities, found {len(cities)}")
    if set(area_rows) != set(cities) | {"all_cities_pooled"}:
        raise ValueError("Panel b area-share city set does not match panel a")
    if set(left_censored_share) != set(cities):
        raise ValueError("Panel c left-censored city set does not match panel a")
    cities.sort(
        key=lambda city_id: (left_censored_share[city_id], city_id),
    )
    display_group_names = ["low", "middle", "high"]

    cohort_by_city: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in read_csv(args.cohort_ranges):
        cohort_by_city[row["city_id"]].append(row)
    for rows in cohort_by_city.values():
        rows.sort(key=lambda row: int(row["cohort_order"]))

    result_index = json.loads(args.index.read_text(encoding="utf-8"))
    indexed_cities = {city["city_id"]: city for city in result_index["cities"]}

    figure, axes = plt.subplots(3, 5, figsize=(9.1, 4.0), squeeze=False)
    figure.patch.set_facecolor("white")
    figure.subplots_adjust(
        left=0.052,
        right=0.952,
        bottom=0.185,
        top=0.905,
        wspace=0.34,
        hspace=0.34,
    )

    panel_data: list[dict[str, object]] = []
    city_checks: dict[str, dict[str, object]] = {}
    relationship_inputs: dict[str, dict[str, object]] = {}

    for index, city_id in enumerate(cities):
        grid_row, grid_column = divmod(index, 5)
        ax = axes[grid_row, grid_column]
        pv_ax = ax.twinx()
        rows = by_city[city_id]
        cohort_rows = cohort_by_city[city_id]
        if not cohort_rows or int(cohort_rows[0]["cohort_order"]) != 0:
            raise ValueError(f"Missing first cohort for {city_id}")

        years = np.array([int(row["calendar_year"]) for row in rows])
        pv_share = np.array(
            [float(row["cumulative_share_of_anchor_pv_area_percent"]) for row in rows]
        )
        building_share = np.array(
            [
                float(row["cumulative_share_of_anchor_building_area_percent"])
                for row in rows
            ]
        )
        building_area = np.array(
            [float(row["interval_stacked_building_area_m2"]) for row in rows]
        )
        if np.any(np.diff(pv_share) < -1e-9) or np.any(
            np.diff(building_share) < -1e-9
        ):
            raise ValueError(f"Non-monotonic trajectory: {city_id}")
        if not math.isclose(float(pv_share[-1]), 100.0, abs_tol=1e-8) or not math.isclose(
            float(building_share[-1]), 100.0, abs_tol=1e-8
        ):
            raise ValueError(f"Trajectory does not end at 100%: {city_id}")

        curve_start_year = int(cohort_rows[0]["range_end_year"])
        start_positions = np.flatnonzero(years == curve_start_year)
        if len(start_positions) != 1:
            raise ValueError(f"Missing curve-start row for {city_id}")
        start_position = int(start_positions[0])
        curve_mask = years >= curve_start_year
        plot_years = years[curve_mask]
        building_baseline_m2 = float(building_area[start_position])
        plot_building_baseline = np.full(
            plot_years.shape, building_baseline_m2 / 1_000_000.0
        )
        plot_building_postbaseline = (
            building_area[curve_mask] - building_baseline_m2
        ) / 1_000_000.0

        relationship_record = indexed_cities[city_id]["artifacts"][
            "pv_building_relationship"
        ]
        relationship_path = Path(relationship_record["path"])
        if sha256_file(relationship_path) != relationship_record["sha256"]:
            raise ValueError(f"Relationship hash mismatch: {city_id}")
        relationships = read_csv(relationship_path)
        if len(relationships) != int(relationship_record["row_count"]):
            raise ValueError(f"Relationship row-count mismatch: {city_id}")
        relationship_inputs[city_id] = {
            "path": str(relationship_path),
            "sha256": relationship_record["sha256"],
            "row_count": int(relationship_record["row_count"]),
            "primary_key": relationship_record["primary_key"],
        }

        cohort_end_years = [int(row["range_end_year"]) for row in cohort_rows]
        pv_by_host = {
            "baseline": np.zeros(plot_years.shape, dtype=float),
            "later": np.zeros(plot_years.shape, dtype=float),
        }
        unavailable_area = 0.0
        resolved_area = 0.0
        conflict_area = 0.0
        conflict_count = 0
        substantive_area = 0.0

        for relationship in relationships:
            area_m2 = float(relationship["anchor_pv_union_area_m2"])
            if relationship["building_first_appearance_available"].lower() != "true":
                unavailable_area += area_m2
                continue
            building_type = relationship["building_pau_first_appearance_type"]
            if building_type == "left_censored":
                host_class = "baseline"
            elif building_type == "interval_censored":
                host_class = "later"
            else:
                raise ValueError(f"Unsupported Building onset for {city_id}")
            resolved_area += area_m2
            pv_credible = int(
                float(relationship["pv_pau_first_credible_present_index"])
            )
            building_credible = int(
                float(relationship["building_pau_first_credible_present_index"])
            )
            if host_class == "later" and pv_credible < building_credible:
                conflict_area += area_m2
                conflict_count += 1
                continue
            substantive_area += area_m2

            pv_type = relationship["pv_pau_first_appearance_type"]
            if pv_type == "left_censored":
                if host_class == "baseline":
                    pv_by_host[host_class] += area_m2
                else:
                    pv_upper = int(
                        float(relationship["pv_pau_first_appearance_upper_index"])
                    )
                    building_upper = int(
                        float(relationship["building_pau_first_appearance_upper_index"])
                    )
                    first_joint_year = max(
                        cohort_end_years[pv_upper], cohort_end_years[building_upper]
                    )
                    pv_by_host[host_class][plot_years >= first_joint_year] += area_m2
                continue
            if pv_type != "interval_censored":
                raise ValueError(f"Unsupported PV onset for {city_id}")
            lower_index = int(
                float(relationship["pv_pau_first_appearance_lower_index"])
            )
            upper_index = int(
                float(relationship["pv_pau_first_appearance_upper_index"])
            )
            lower_year = cohort_end_years[lower_index]
            upper_year = cohort_end_years[upper_index]
            building_entry_year = None
            if host_class == "later":
                building_upper = int(
                    float(relationship["building_pau_first_appearance_upper_index"])
                )
                building_entry_year = cohort_end_years[building_upper]
            for position, year in enumerate(plot_years):
                if building_entry_year is not None and year < building_entry_year:
                    contribution = 0.0
                elif year <= lower_year:
                    contribution = 0.0
                elif year >= upper_year:
                    contribution = area_m2
                else:
                    contribution = area_m2 * (year - lower_year) / (
                        upper_year - lower_year
                    )
                pv_by_host[host_class][position] += contribution

        if not math.isclose(
            float(pv_by_host["baseline"][-1] + pv_by_host["later"][-1]),
            substantive_area,
            abs_tol=1e-5,
        ):
            raise ValueError(f"PV component reconciliation failed: {city_id}")
        if not math.isclose(resolved_area, substantive_area + conflict_area, abs_tol=1e-5):
            raise ValueError(f"Conflict reconciliation failed: {city_id}")
        if not math.isclose(float(pv_by_host["later"][0]), 0.0, abs_tol=1e-12):
            raise ValueError(f"Later-host PV is nonzero at baseline: {city_id}")

        ax.bar(
            plot_years,
            plot_building_baseline,
            width=BAR_WIDTH,
            color=BUILDING_BASELINE,
            edgecolor="none",
            zorder=1,
        )
        ax.bar(
            plot_years,
            plot_building_postbaseline,
            bottom=plot_building_baseline,
            width=BAR_WIDTH,
            color=BUILDING_POSTBASELINE,
            edgecolor="none",
            zorder=1,
        )
        baseline_pv_million = pv_by_host["baseline"] / 1_000_000.0
        later_pv_million = pv_by_host["later"] / 1_000_000.0
        pv_ax.fill_between(
            plot_years, 0, -baseline_pv_million,
            color=PV_BASELINE, alpha=0.22, zorder=4
        )
        pv_ax.plot(
            plot_years, -baseline_pv_million,
            color=PV_BASELINE, linewidth=1.05, solid_capstyle="round", zorder=5
        )
        pv_ax.fill_between(
            plot_years, 0, later_pv_million,
            color=PV_POSTBASELINE, alpha=0.22, zorder=4
        )
        pv_ax.plot(
            plot_years, later_pv_million,
            color=PV_POSTBASELINE, linewidth=1.05, solid_capstyle="round", zorder=5
        )

        building_ymax = float(building_area[-1] / 1_000_000.0) * 1.03
        ax.set_ylim(0, building_ymax)
        baseline_fraction = (building_baseline_m2 / 1_000_000.0) / building_ymax
        baseline_max = float(baseline_pv_million.max())
        later_max = float(later_pv_million.max())
        positive_ymax = max(
            later_max * 1.18,
            baseline_max * (1.0 - baseline_fraction) / baseline_fraction * 1.08,
            1e-6,
        )
        negative_ymin = -baseline_fraction / (1.0 - baseline_fraction) * positive_ymax
        pv_ax.set_ylim(negative_ymin, positive_ymax)

        x_min = int(years[0])
        x_max_tick = int(years[-1])
        ax.set_xlim(x_min, x_max_tick + BAR_WIDTH / 2.0)
        x_ticks = list(range(x_min, x_max_tick + 1, 4))
        if x_max_tick not in x_ticks:
            x_ticks.append(x_max_tick)
        ax.set_xticks(x_ticks)
        ax.yaxis.set_major_locator(MaxNLocator(nbins=4, min_n_ticks=3))
        pv_ax.set_yticks([-baseline_max, 0, later_max] if later_max > 0 else [-baseline_max, 0])
        pv_ax.yaxis.set_major_formatter(FuncFormatter(pv_tick))
        ax.grid(axis="y", color=GRID, linewidth=0.45, linestyle=":", zorder=0)
        ax.tick_params(
            axis="both", labelsize=7.0, colors=BLACK,
            length=2.1, width=0.55, pad=1.5, direction="out"
        )
        pv_ax.tick_params(
            axis="y", labelsize=5.7, colors=BLACK,
            length=2.1, width=0.55, pad=1.5, direction="out"
        )
        for label in [
            *ax.get_xticklabels(), *ax.get_yticklabels(), *pv_ax.get_yticklabels()
        ]:
            label.set_fontfamily(FONT)
            label.set_fontweight("normal")
        if grid_row < 2:
            ax.tick_params(axis="x", labelbottom=False)
        else:
            plt.setp(ax.get_xticklabels(), rotation=45, ha="right", rotation_mode="anchor")
        for spine in ("top", "right"):
            ax.spines[spine].set_visible(False)
        ax.spines["left"].set_color(BLACK)
        ax.spines["left"].set_linewidth(0.55)
        ax.spines["bottom"].set_color(BLACK)
        ax.spines["bottom"].set_linewidth(0.55)
        for spine in ("top", "bottom", "left"):
            pv_ax.spines[spine].set_visible(False)
        pv_ax.spines["right"].set_color(BLACK)
        pv_ax.spines["right"].set_linewidth(0.55)
        pv_ax.spines["right"].set_bounds(
            -baseline_max, later_max if later_max > 0 else 0
        )

        city_name = rows[0]["city_name"]
        ax.text(
            0.0, 1.035, city_name, transform=ax.transAxes,
            ha="left", va="bottom", fontsize=7.2, fontfamily=FONT,
            fontweight="normal", color=BLACK,
            clip_on=False,
            zorder=7,
        )
        total_utilization = (
            100.0 * (pv_by_host["baseline"] + pv_by_host["later"])
            / building_area[curve_mask]
        )
        label_y = -float(pv_by_host["baseline"][0]) / 1_000_000.0 / 2.0
        label_style = {
            "fontsize": 5.4, "fontfamily": FONT, "fontweight": "normal",
            "color": BLACK, "va": "center",
            "bbox": {"facecolor": "white", "edgecolor": "none", "alpha": 0.82, "pad": 0.3},
            "zorder": 8,
        }
        pv_ax.text(
            plot_years[0], label_y, f"{total_utilization[0]:.2f}%",
            ha="left", **label_style
        )
        pv_ax.text(
            plot_years[-1], label_y, f"{total_utilization[-1]:.2f}%",
            ha="right", **label_style
        )

        for position, year in enumerate(plot_years):
            panel_data.append(
                {
                    "panel": "a",
                    "layout": "3_rows_x_5_columns",
                    "city_id": city_id,
                    "city_name": city_name,
                    "display_order": index + 1,
                    "grid_row": grid_row + 1,
                    "grid_column": grid_column + 1,
                    "area_group": display_group_names[grid_row],
                    "calendar_year": int(year),
                    "building_baseline_area_m2": building_baseline_m2,
                    "building_postbaseline_area_m2": float(
                        building_area[curve_mask][position] - building_baseline_m2
                    ),
                    "pv_area_on_baseline_buildings_m2": float(
                        pv_by_host["baseline"][position]
                    ),
                    "pv_area_on_later_buildings_m2": float(
                        pv_by_host["later"][position]
                    ),
                    "total_substantive_pv_utilization_percent": float(
                        total_utilization[position]
                    ),
                    "status": "REPRODUCED",
                }
            )

        city_checks[city_id] = {
            "curve_start_year": curve_start_year,
            "curve_end_year": int(plot_years[-1]),
            "later_host_pv_zero_at_curve_start": True,
            "resolved_linked_pv_area_m2": resolved_area,
            "substantive_nonconflict_pv_area_m2": substantive_area,
            "pv_before_building_conflict_excluded_count": conflict_count,
            "pv_before_building_conflict_excluded_area_m2": conflict_area,
            "unavailable_building_onset_pv_area_m2": unavailable_area,
            "left_endpoint_utilization_percent": float(total_utilization[0]),
            "right_endpoint_utilization_percent": float(total_utilization[-1]),
        }

    figure.text(
        0.012, 0.965, "a,", ha="left", va="top",
        fontsize=9.5, fontfamily=FONT, fontweight="normal", color=BLACK
    )
    handles = [
        Patch(facecolor=BUILDING_BASELINE, edgecolor="none", label="Building: baseline"),
        Patch(facecolor=BUILDING_POSTBASELINE, edgecolor="none", label="Building: post-baseline"),
        Line2D([0], [0], color=PV_BASELINE, linewidth=1.1, label="PV: baseline host"),
        Line2D([0], [0], color=PV_POSTBASELINE, linewidth=1.1, label="PV: later host"),
    ]
    legend = figure.legend(
        handles=handles, loc="lower center", bbox_to_anchor=(0.50, 0.006),
        ncol=4, frameon=False, fontsize=7.0, labelcolor=BLACK,
        handlelength=1.6, handletextpad=0.35, columnspacing=0.85, borderaxespad=0
    )
    for label in legend.get_texts():
        label.set_fontfamily(FONT)
        label.set_fontweight("normal")
    figure.supxlabel(
        "Cohort-label-implied calendar bound", x=0.50, y=0.070,
        fontsize=8.2, fontfamily=FONT, color=BLACK
    )
    figure.supylabel(
        "Cumulative building roof area (million m²)", x=0.012, y=0.50,
        fontsize=8.2, fontfamily=FONT, color=BLACK
    )
    figure.text(
        0.997, 0.50, "PV area (million m²)",
        ha="right", va="center", rotation=90,
        fontsize=8.2, fontfamily=FONT, color=BLACK
    )

    png_path = args.output_dir / "figure1_panel_a_3x5.png"
    pdf_path = args.output_dir / "figure1_panel_a_3x5.pdf"
    figure.savefig(png_path, dpi=300, facecolor="white")
    figure.savefig(pdf_path, facecolor="white")
    plt.close(figure)

    data_path = args.output_dir / "figure1_panel_a_3x5_data.csv"
    write_csv(data_path, panel_data)
    checks_path = args.output_dir / "figure1_panel_a_3x5_checks.json"
    checks = {
        "schema_version": "figure-panel-checks-v1",
        "status": "REPRODUCED",
        "city_count": len(cities),
        "grid_rows": 3,
        "grid_columns": 5,
        "city_order": cities,
        "all_later_host_pv_zero_at_curve_start": all(
            value["later_host_pv_zero_at_curve_start"] for value in city_checks.values()
        ),
        "all_conflicts_excluded_from_substantive_pv_lines": True,
        "all_pv_component_reconciliations_pass": True,
        "building_and_pv_axis_unit": "million square metres",
        "area_group_definition": "tertiles of panel-c left-censored area share; ascending display order only",
        "area_groups": {
            display_group_names[row]: {
                "cities": cities[row * 5:(row + 1) * 5],
            }
            for row in range(3)
        },
        "city_order_metric": "composition_left_censored_percent",
        "city_order_source": "figure1_panel_c_lag_data.csv",
        "city_order_direction": "ascending",
        "city_specific_left_y_limits": True,
        "city_specific_right_y_limits": True,
        "right_axis_zero_aligned_to_each_city_building_baseline": True,
        "x_grid_visible": False,
        "y_grid_visible": True,
        "figure_contains_title": False,
        "figure_contains_subtitle": False,
        "figure_contains_footnote": False,
        "city_checks": city_checks,
    }
    write_json(checks_path, checks)

    note_path = args.output_dir / "figure1_panel_a_3x5_note.md"
    note_path.write_text(
        "# Figure 1a 3×5 city iteration\n\n"
        "Fifteen cities are shown in ascending panel-c left-censored area share in a "
        "three-row by five-column layout, split into low-, middle-, and high-share "
        "rows of five for display order. Each "
        "city uses tight city-specific y-axis limits and follows the approved Atlanta "
        "prototype. Building bars "
        "partition absolute roof-mask area at the first-cohort upper bound. PV lines "
        "partition cumulative resolved PV area by whether the linked Building was "
        "left-censored or first observed later. Later-host PV begins only after its "
        "Building enters the record; PV-before-Building conflicts and unavailable "
        "Building onset are excluded. Both axes use million square metres. Each "
        "city's PV-axis zero remains aligned to its Building baseline. Endpoint "
        "labels give substantive PV area divided by cumulative Building roof-mask "
        "area. Cohort bounds are not exact event dates. Status: `REPRODUCED`.\n",
        encoding="utf-8",
    )

    manifest_path = args.output_dir / "figure1_panel_a_3x5_manifest.json"
    outputs = {}
    for path in [png_path, pdf_path, data_path, checks_path, note_path]:
        outputs[path.name] = {
            "path": str(path), "bytes": path.stat().st_size, "sha256": sha256_file(path)
        }
    write_json(
        manifest_path,
        {
            "schema_version": "figure-panel-manifest-v1",
            "generated_at_utc": datetime.now(timezone.utc).isoformat(),
            "panel": "Figure 1a 3-row by 5-column city iteration",
            "script_path": str(Path(__file__).resolve()),
            "script_version": SCRIPT_VERSION,
            "script_sha256": sha256_file(Path(__file__).resolve()),
            "font": {"family": FONT, "path": str(FONT_PATH), "sha256": sha256_file(FONT_PATH)},
            "inputs": {
                "trajectory_table": input_record,
                "area_temporal_contrast": area_input,
                "panel_c_lag_data": {
                    "path": str(panel_c_path.resolve()),
                    "sha256": sha256_file(panel_c_path),
                    "row_count": len(panel_c_rows),
                    "primary_key": ["city_id", "lag_bin_start_years"],
                    "status": "REPRODUCED",
                },
                "major_results_index": {"path": str(args.index.resolve()), "sha256": sha256_file(args.index)},
                "cohort_ranges": {"path": str(args.cohort_ranges.resolve()), "sha256": sha256_file(args.cohort_ranges)},
                "pv_building_relationships": relationship_inputs,
            },
            "outputs": outputs,
            "status": "REPRODUCED",
        },
    )


if __name__ == "__main__":
    main()
