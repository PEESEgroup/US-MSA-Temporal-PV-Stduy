#!/usr/bin/env python3
"""Render Figure 3 panels a--c in one vector figure with shared city rows."""

from __future__ import annotations

import argparse
import ast
import json
from datetime import datetime, timezone
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.collections import PathCollection
from matplotlib.lines import Line2D
from matplotlib.patches import Patch
from PIL import Image

from figure3_draft import (
    AREA,
    CITY_NAMES,
    COUNT,
    EXISTING,
    MUTED,
    NEW,
    TEXT,
    configure_style,
    read_csv,
    sha256_file,
    source_record,
    write_csv,
    write_json,
)


SCRIPT_VERSION = "1.0.0"
CANVAS_SCALE = 0.75
CANVAS_SCALE_RELATIVE_TO_V7 = 0.80
CANVAS_SCALE_RELATIVE_TO_V10 = 0.80
FIGURE_HEIGHT_IN = (
    5.75
    * CANVAS_SCALE
    * CANVAS_SCALE_RELATIVE_TO_V7
    * CANVAS_SCALE_RELATIVE_TO_V10
)
TIGHT_PAD_IN = 0.0
AUXILIARY = "#b8bdbc"
PANEL_LABEL_FONTSIZE = 9.5
PANEL_B_C_LABEL_X_OFFSET_FIGURE = 0.010
LEGEND_VERTICAL_ANCHOR = (
    -0.155 / CANVAS_SCALE_RELATIVE_TO_V7 / CANVAS_SCALE_RELATIVE_TO_V10
)
LEGEND_FONTSIZE = 6.1
LEGEND_MARKERSIZE = 5.8
LEGEND_COLUMN_SPACING = 0.70
LEGEND_HANDLETEXTPAD = 0.30
ROUTES = ("new", "existing")
LOW_INFORMATION_TOP_COUNT = 2


def parse_args() -> argparse.Namespace:
    workspace = Path(__file__).resolve().parents[3]
    figure_dir = Path(__file__).resolve().parent
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--panel-a-dir",
        type=Path,
        default=figure_dir / "panel_a_appearance_sorted_v2",
    )
    parser.add_argument(
        "--panel-b-dir",
        type=Path,
        default=figure_dir / "panel_b_boxen_v3",
    )
    parser.add_argument(
        "--panel-c-dir",
        type=Path,
        default=figure_dir / "panel_c_paired_columns_v2",
    )
    parser.add_argument(
        "--style",
        type=Path,
        default=workspace / "paper" / "style" / "temporal_pv.mplstyle",
    )
    parser.add_argument(
        "--figure-plan",
        type=Path,
        default=workspace / "paper" / "FIGURE_PLAN.md",
    )
    parser.add_argument(
        "--figure4-script",
        type=Path,
        default=(
            workspace
            / "paper"
            / "figures"
            / "figure4_transition_dynamics"
            / "figure4_transition_dynamics.py"
        ),
    )
    parser.add_argument(
        "--font",
        type=Path,
        default=(
            workspace
            / "paper"
            / "figures"
            / "figure1_city_trajectories"
            / "initial_v1"
            / "figure1_abcd"
            / "code"
            / "arial.ttf"
        ),
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=figure_dir / "initial_v1" / "figure3_abc",
    )
    return parser.parse_args()


def read_numeric_constant(path: Path, constant_name: str) -> float:
    """Read a top-level numeric constant without executing the reference script."""
    module = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for node in module.body:
        if not isinstance(node, (ast.Assign, ast.AnnAssign)):
            continue
        targets = node.targets if isinstance(node, ast.Assign) else [node.target]
        if not any(isinstance(target, ast.Name) and target.id == constant_name for target in targets):
            continue
        value_node = node.value
        value = ast.literal_eval(value_node)
        if not isinstance(value, (int, float)):
            break
        return float(value)
    raise ValueError(f"Could not read numeric constant {constant_name} from {path}")


def load_panel_bundle(
    directory: Path,
    panel: str,
) -> tuple[list[dict[str, str]], dict, dict, Path, Path, Path]:
    data_path = directory / f"figure3_panel_{panel}_data.csv"
    checks_path = directory / f"figure3_panel_{panel}_checks.json"
    manifest_path = directory / f"figure3_panel_{panel}_manifest.json"
    for path in (data_path, checks_path, manifest_path):
        if not path.resolve().is_file():
            raise FileNotFoundError(path)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    checks = json.loads(checks_path.read_text(encoding="utf-8"))
    if manifest["status"] != "REPRODUCED" or checks["status"] != "REPRODUCED":
        raise AssertionError(f"Panel {panel} source bundle is not REPRODUCED")
    for path in (data_path, checks_path):
        if sha256_file(path) != manifest["outputs"][path.name]["sha256"]:
            raise AssertionError(f"Panel {panel} {path.name} does not match its manifest")
    return (
        read_csv(data_path),
        checks,
        manifest,
        data_path.resolve(),
        checks_path.resolve(),
        manifest_path.resolve(),
    )


def style_shared_city_axis(
    axis: plt.Axes,
    city_order: list[str],
    show_labels: bool,
    internal_left_spine: bool = False,
) -> None:
    display_cities = city_order + ["all_cities_pooled"]
    y = np.arange(len(display_cities))
    axis.set_yticks(y)
    if show_labels:
        axis.set_yticklabels([CITY_NAMES[city_id] for city_id in display_cities])
        for tick_label in axis.get_yticklabels():
            tick_label.set_color("#000000")
    else:
        axis.tick_params(axis="y", labelleft=False)
    axis.tick_params(
        axis="y",
        left=True,
        length=2.6,
        width=0.65,
        direction="out",
        color=TEXT,
    )
    axis.set_ylim(len(display_cities) - 0.35, -0.65)
    axis.axhline(len(city_order) - 0.5, color=AUXILIARY, lw=0.65, zorder=6)
    axis.grid(axis="y", visible=False)
    axis.spines["left"].set_visible(True)
    axis.spines["left"].set_color(AUXILIARY if internal_left_spine else TEXT)
    axis.spines["left"].set_linewidth(0.65 if internal_left_spine else 0.75)
    axis.spines["left"].set_linestyle("-")
    axis.spines["bottom"].set_visible(True)
    axis.spines["bottom"].set_color(TEXT)
    axis.spines["bottom"].set_linewidth(0.75)
    axis.spines["bottom"].set_linestyle("-")
    axis.spines["top"].set_visible(False)
    axis.spines["right"].set_visible(False)
    axis.tick_params(axis="x", width=0.65, color=TEXT)


def style_internal_grid(axis: plt.Axes) -> None:
    axis.grid(False, which="both", axis="both")


def scale_figure_artists(figure: plt.Figure, scale: float) -> None:
    """Scale typography and vector marks with the reduced physical canvas."""
    for artist in figure.findobj(match=lambda item: hasattr(item, "get_fontsize")):
        try:
            artist.set_fontsize(artist.get_fontsize() * scale)
        except (AttributeError, TypeError, ValueError):
            pass
    for line in figure.findobj(match=Line2D):
        line.set_linewidth(line.get_linewidth() * scale)
        line.set_markersize(line.get_markersize() * scale)
        line.set_markeredgewidth(line.get_markeredgewidth() * scale)
    for collection in figure.findobj(match=PathCollection):
        collection.set_sizes(collection.get_sizes() * scale * scale)
        collection.set_linewidths(collection.get_linewidths() * scale)
    for patch in figure.findobj(match=Patch):
        patch.set_linewidth(patch.get_linewidth() * scale)


def draw_panel_a(
    axis: plt.Axes,
    rows: list[dict[str, str]],
    city_order: list[str],
) -> None:
    lookup = {(row["city_id"], row["metric"]): row for row in rows}
    display_cities = city_order + ["all_cities_pooled"]
    metric_specs = [
        (
            "pv_first_appearance_frequency_per_building",
            "PV first appearances / building",
            COUNT,
            "o",
            "white",
        ),
        ("pv_area_per_building", "PV area / building", "#89a7b0", "D", "#89a7b0"),
        ("pv_area_per_roof_m2", "PV area / m² roof", AREA, "s", AREA),
    ]
    axis.axvline(1.0, color=AUXILIARY, lw=0.75, zorder=1)
    for y, city_id in enumerate(display_cities):
        values = [
            float(lookup[(city_id, metric)]["newly_observed_to_existing_ratio"])
            for metric, *_ in metric_specs
        ]
        axis.plot(values[:2], [y, y], color=AUXILIARY, lw=0.75, ls="-", zorder=1)
        axis.plot(values[1:], [y, y], color="#89a7b0", lw=1.0, zorder=2)
        for value, (metric, _, edge, marker, face) in zip(values, metric_specs):
            pooled = city_id == "all_cities_pooled"
            axis.scatter(
                value,
                y,
                s=25 if not pooled else 58,
                marker=marker,
                facecolor=face,
                edgecolor=edge,
                lw=0.9,
                zorder=4 if metric == "pv_first_appearance_frequency_per_building" else 3,
            )
        roof_value = values[-1]
        axis.annotate(
            f"{roof_value:.2f}×",
            (roof_value, y),
            xytext=(6, 0),
            textcoords="offset points",
            ha="left",
            va="center",
            fontsize=5.1,
            color=AREA,
            clip_on=False,
        )

    style_shared_city_axis(axis, city_order, show_labels=True)
    axis.set_xscale("log")
    axis.set_xlim(0.22, 12.0)
    axis.set_xticks([0.25, 0.5, 1, 2, 4, 8], ["0.25", "0.5", "1", "2", "4", "8"])
    axis.set_xlabel("Ratio: newly observed / existing")
    style_internal_grid(axis)
    axis.text(
        0.0,
        1.02,
        "← existing higher",
        transform=axis.transAxes,
        ha="left",
        va="bottom",
        fontsize=5.5,
        color=MUTED,
    )
    axis.text(
        1.0,
        1.02,
        "newly observed higher →",
        transform=axis.transAxes,
        ha="right",
        va="bottom",
        fontsize=5.5,
        color=MUTED,
    )
    handles = [
        Line2D(
            [0], [0], marker="o", markersize=LEGEND_MARKERSIZE,
            markerfacecolor="white",
            markeredgecolor=COUNT, lw=0, label="PV appearances",
        ),
        Line2D(
            [0], [0], marker="D", markersize=LEGEND_MARKERSIZE,
            markerfacecolor="#89a7b0",
            markeredgecolor="#89a7b0", lw=0, label="PV area/building",
        ),
        Line2D(
            [0], [0], marker="s", markersize=LEGEND_MARKERSIZE,
            markerfacecolor=AREA,
            markeredgecolor=AREA, lw=0, label="PV/roof m²",
        ),
    ]
    axis.legend(
        handles=handles,
        loc="upper center",
        bbox_to_anchor=(0.5, LEGEND_VERTICAL_ANCHOR),
        ncol=3,
        columnspacing=LEGEND_COLUMN_SPACING,
        handletextpad=LEGEND_HANDLETEXTPAD,
        borderaxespad=0,
        fontsize=LEGEND_FONTSIZE,
    )
def draw_panel_b(
    axis: plt.Axes,
    rows: list[dict[str, str]],
    city_order: list[str],
    nominal_density: float,
) -> plt.Axes:
    displayed_rows = [row for row in rows if row["track"] == "paired_boxen_distribution"]
    lookup = {(row["city_id"], row["route"]): row for row in displayed_rows}
    display_cities = city_order + ["all_cities_pooled"]
    route_specs = [("new", NEW, -0.15), ("existing", EXISTING, 0.15)]
    band_specs = [
        ("q01_host_pv_area_m2", "q99_host_pv_area_m2", 0.07, 0.20),
        ("q10_host_pv_area_m2", "q90_host_pv_area_m2", 0.14, 0.38),
        ("q25_host_pv_area_m2", "q75_host_pv_area_m2", 0.22, 0.72),
    ]
    for y, city_id in enumerate(display_cities):
        for route, color, offset in route_specs:
            row = lookup[(city_id, route)]
            yy = y + offset
            for lower, upper, height, alpha in band_specs:
                axis.fill_betweenx(
                    [yy - height / 2, yy + height / 2],
                    float(row[lower]),
                    float(row[upper]),
                    facecolor=color,
                    edgecolor="none",
                    alpha=alpha,
                    zorder=1,
                )
            axis.plot(
                [float(row["q25_host_pv_area_m2"]), float(row["q75_host_pv_area_m2"])],
                [yy, yy],
                color=color,
                lw=0.45,
                zorder=2,
            )
            axis.plot(
                [float(row["median_host_pv_area_m2"])] * 2,
                [yy - 0.13, yy + 0.13],
                color=TEXT,
                lw=0.72,
                zorder=3,
            )
            axis.scatter(
                float(row["mean_host_pv_area_m2"]),
                yy,
                marker="D",
                s=10,
                facecolor="white",
                edgecolor=color,
                lw=0.65,
                zorder=4,
            )

    style_shared_city_axis(axis, city_order, show_labels=False)
    axis.set_xscale("log")
    axis.set_xlim(2.2, 8000)
    axis.set_xticks(
        [3, 10, 30, 100, 300, 1000, 3000],
        ["3", "10", "30", "100", "300", "1k", "3k"],
    )
    axis.set_xlabel("PV area per host building (m², log scale)")
    style_internal_grid(axis)
    secondary = axis.secondary_xaxis(
        "top",
        functions=(
            lambda area: area * nominal_density,
            lambda power: power / nominal_density,
        ),
    )
    secondary.set_xscale("log")
    secondary.set_xticks(
        [0.6, 2, 6, 20, 60, 200, 600],
        ["0.6", "2", "6", "20", "60", "200", "600"],
    )
    secondary.set_xlabel("Capacity-equivalent (kWdc / building)", labelpad=1.5)
    secondary.tick_params(labelsize=5.5, pad=1.0)
    secondary.spines["top"].set_visible(True)
    secondary.spines["top"].set_color(TEXT)
    secondary.spines["top"].set_linewidth(0.75)
    secondary.spines["top"].set_linestyle("-")
    handles = [
        Patch(facecolor=NEW, edgecolor=NEW, alpha=0.72, label="newly observed"),
        Patch(facecolor=EXISTING, edgecolor=EXISTING, alpha=0.72, label="existing"),
        Patch(facecolor=TEXT, edgecolor="none", alpha=0.20, label="1–99 / 10–90 / 25–75%"),
        Line2D([0], [0], color=TEXT, lw=0.8, label="median"),
        Line2D(
            [0], [0], marker="D", markersize=LEGEND_MARKERSIZE,
            markerfacecolor="white",
            markeredgecolor=TEXT, lw=0, label="mean",
        ),
    ]
    axis.legend(
        handles=handles,
        loc="upper center",
        bbox_to_anchor=(0.5, LEGEND_VERTICAL_ANCHOR),
        ncol=3,
        columnspacing=LEGEND_COLUMN_SPACING,
        handletextpad=LEGEND_HANDLETEXTPAD,
        borderaxespad=0,
        fontsize=LEGEND_FONTSIZE,
    )
    return secondary


def draw_c_pair(
    axis: plt.Axes,
    y: float,
    new_value: float,
    existing_value: float,
    pooled: bool,
) -> None:
    offset = 0.10
    new_y = y - offset
    existing_y = y + offset
    axis.plot(
        [new_value, existing_value],
        [new_y, existing_y],
        color=AUXILIARY,
        lw=0.70 if not pooled else 0.95,
        zorder=1,
    )
    axis.scatter(
        new_value,
        new_y,
        s=22 if not pooled else 52,
        marker="s",
        facecolor=NEW,
        edgecolor="white",
        lw=0.45 if not pooled else 0.70,
        zorder=3,
    )
    axis.scatter(
        existing_value,
        existing_y,
        s=22 if not pooled else 52,
        marker="o",
        facecolor=EXISTING,
        edgecolor="white",
        lw=0.45 if not pooled else 0.70,
        zorder=2,
    )


def draw_panel_c(
    top_axis: plt.Axes,
    gini_axis: plt.Axes,
    rows: list[dict[str, str]],
    city_order: list[str],
) -> None:
    lookup = {(row["city_id"], row["route"]): row for row in rows}
    display_cities = city_order + ["all_cities_pooled"]
    for y, city_id in enumerate(display_cities):
        new_row = lookup[(city_id, "new")]
        existing_row = lookup[(city_id, "existing")]
        pooled = city_id == "all_cities_pooled"
        draw_c_pair(
            top_axis,
            y,
            float(new_row["pv_area_share_largest_1pct_percent"]),
            float(existing_row["pv_area_share_largest_1pct_percent"]),
            pooled,
        )
        draw_c_pair(
            gini_axis,
            y,
            float(new_row["gini_coefficient"]),
            float(existing_row["gini_coefficient"]),
            pooled,
        )
        top_count = int(float(new_row["top_1pct_host_count"]))
        if city_id != "all_cities_pooled" and top_count <= LOW_INFORMATION_TOP_COUNT:
            top_axis.annotate(
                f"n={top_count}",
                (float(new_row["pv_area_share_largest_1pct_percent"]), y - 0.10),
                xytext=(0, -4),
                textcoords="offset points",
                ha="center",
                va="top",
                fontsize=4.3,
                color=MUTED,
                zorder=5,
            )

    for axis in (top_axis, gini_axis):
        style_shared_city_axis(
            axis,
            city_order,
            show_labels=False,
            internal_left_spine=(axis is gini_axis),
        )
        style_internal_grid(axis)
    gini_axis.tick_params(axis="y", left=False)
    top_axis.set_xlim(5, 45)
    top_axis.set_xticks([10, 20, 30, 40])
    top_axis.set_xlabel("PV area in largest 1%\nof buildings (%)")
    gini_axis.set_xlim(0.35, 0.87)
    gini_axis.set_xticks([0.4, 0.6, 0.8])
    gini_axis.set_xlabel("Gini coefficient")

    pooled_y = len(city_order)
    pooled_new = lookup[("all_cities_pooled", "new")]
    pooled_existing = lookup[("all_cities_pooled", "existing")]
    labels = [
        (
            top_axis,
            float(pooled_new["pv_area_share_largest_1pct_percent"]),
            pooled_y - 0.10,
            f"{float(pooled_new['pv_area_share_largest_1pct_percent']):.1f}%",
            NEW,
            "right",
            (-3, 0),
        ),
        (
            top_axis,
            float(pooled_existing["pv_area_share_largest_1pct_percent"]),
            pooled_y + 0.10,
            f"{float(pooled_existing['pv_area_share_largest_1pct_percent']):.1f}%",
            EXISTING,
            "left",
            (3, 0),
        ),
        (
            gini_axis,
            float(pooled_new["gini_coefficient"]),
            pooled_y - 0.10,
            f"{float(pooled_new['gini_coefficient']):.2f}",
            NEW,
            "left",
            (3, 0),
        ),
        (
            gini_axis,
            float(pooled_existing["gini_coefficient"]),
            pooled_y + 0.10,
            f"{float(pooled_existing['gini_coefficient']):.2f}",
            EXISTING,
            "right",
            (-3, 0),
        ),
    ]
    for axis, xx, yy, label, color, horizontal, offset in labels:
        axis.annotate(
            label,
            (xx, yy),
            xytext=offset,
            textcoords="offset points",
            ha=horizontal,
            va="center",
            fontsize=4.9,
            color=color,
            zorder=6,
        )

    handles = [
        Line2D(
            [0], [0], marker="s", markersize=LEGEND_MARKERSIZE,
            markerfacecolor=NEW,
            markeredgecolor="white", lw=0, label="newly observed",
        ),
        Line2D(
            [0], [0], marker="o", markersize=LEGEND_MARKERSIZE,
            markerfacecolor=EXISTING,
            markeredgecolor="white", lw=0, label="existing",
        ),
        Line2D([0], [0], color=AUXILIARY, lw=0.8, label="same city"),
    ]
    top_axis.legend(
        handles=handles,
        loc="upper center",
        bbox_to_anchor=(1.08, LEGEND_VERTICAL_ANCHOR),
        ncol=3,
        columnspacing=LEGEND_COLUMN_SPACING,
        handletextpad=LEGEND_HANDLETEXTPAD,
        borderaxespad=0,
        fontsize=LEGEND_FONTSIZE,
    )


def add_aligned_panel_labels(
    figure: plt.Figure,
    panel_axes: list[plt.Axes],
    reference_axis: plt.Axes,
    font_name: str,
) -> tuple[list[float], list[float]]:
    """Align identifiers to the top-axis title without changing horizontal anchors."""
    figure.canvas.draw()
    renderer = figure.canvas.get_renderer()
    washington_label = next(
        label
        for label in panel_axes[0].get_yticklabels()
        if label.get_text() == "Washington DC"
    )
    washington_bbox = washington_label.get_window_extent(renderer=renderer)
    washington_bbox_figure = washington_bbox.transformed(figure.transFigure.inverted())
    reference_bbox = reference_axis.xaxis.label.get_window_extent(renderer=renderer)
    reference_bbox_figure = reference_bbox.transformed(figure.transFigure.inverted())
    label_y = (reference_bbox_figure.y0 + reference_bbox_figure.y1) / 2
    label_xs = [
        washington_bbox_figure.x0,
        panel_axes[1].get_position().x0 - PANEL_B_C_LABEL_X_OFFSET_FIGURE,
        panel_axes[2].get_position().x0 - PANEL_B_C_LABEL_X_OFFSET_FIGURE,
    ]
    label_ys = [label_y] * 3
    horizontal_alignments = ["left", "left", "left"]
    for label, label_x, label_y, horizontal_alignment in zip(
        ("a", "b", "c"),
        label_xs,
        label_ys,
        horizontal_alignments,
    ):
        figure.text(
            label_x,
            label_y,
            f"{label},",
            ha=horizontal_alignment,
            va="center",
            fontsize=PANEL_LABEL_FONTSIZE * CANVAS_SCALE,
            color=TEXT,
            fontfamily=font_name,
        )
    return label_ys, label_xs


def combined_rows(
    a_rows: list[dict[str, str]],
    b_rows: list[dict[str, str]],
    c_rows: list[dict[str, str]],
) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for row in a_rows:
        rows.append(
            {
                "record_id": f"a:{row['city_id']}:{row['metric']}",
                "panel": "a",
                "city_id": row["city_id"],
                "city_name": row["city_name"],
                "display_order": row["display_order"],
                "metric": row["metric"],
                "metric_label": row["metric_label"],
                "value": row["newly_observed_to_existing_ratio"],
                "value_unit": "ratio_newly_observed_to_existing",
                "status": row["status"],
            }
        )
    for row in b_rows:
        if row["track"] != "paired_boxen_distribution":
            continue
        rows.append(
            {
                "record_id": f"b:{row['city_id']}:{row['route']}",
                "panel": "b",
                "city_id": row["city_id"],
                "city_name": row["city_name"],
                "display_order": row["display_order"],
                "route": row["route"],
                "host_count": row["host_count"],
                "q01_host_pv_area_m2": row["q01_host_pv_area_m2"],
                "q10_host_pv_area_m2": row["q10_host_pv_area_m2"],
                "q25_host_pv_area_m2": row["q25_host_pv_area_m2"],
                "median_host_pv_area_m2": row["median_host_pv_area_m2"],
                "q75_host_pv_area_m2": row["q75_host_pv_area_m2"],
                "q90_host_pv_area_m2": row["q90_host_pv_area_m2"],
                "q99_host_pv_area_m2": row["q99_host_pv_area_m2"],
                "mean_host_pv_area_m2": row["mean_host_pv_area_m2"],
                "value_unit": "m2_anchor_pv_union_area_per_unique_strict_event_host",
                "status": row["status"],
            }
        )
    for row in c_rows:
        rows.append(
            {
                "record_id": f"c:{row['city_id']}:{row['route']}",
                "panel": "c",
                "city_id": row["city_id"],
                "city_name": row["city_name"],
                "display_order": row["display_order"],
                "route": row["route"],
                "host_count": row["host_building_count"],
                "top_1pct_host_count": row["top_1pct_host_count"],
                "low_information_top_1pct": row["low_information_top_1pct"],
                "pv_area_share_largest_1pct": row["pv_area_share_largest_1pct"],
                "gini_coefficient": row["gini_coefficient"],
                "value_unit": "route_level_distribution_summary",
                "status": row["status"],
            }
        )
    if len({row["record_id"] for row in rows}) != len(rows):
        raise AssertionError("Combined panel record_id is not unique")
    return rows


def main() -> None:
    args = parse_args()
    output_dir = args.output_dir.resolve()
    if (output_dir / "LOCKED").exists():
        raise FileExistsError(
            f"Refusing to overwrite locked Figure 3 bundle: {output_dir}. "
            "Pass --output-dir with a new sibling version directory."
        )
    output_dir.mkdir(parents=True, exist_ok=True)
    script_path = Path(__file__).resolve()
    shared_code_path = script_path.parent / "figure3_draft.py"
    for path in (
        args.figure_plan,
        args.figure4_script,
        args.style,
        args.font,
        shared_code_path,
    ):
        if not path.resolve().is_file():
            raise FileNotFoundError(path)
    figure4_reference_width_in = read_numeric_constant(
        args.figure4_script.resolve(),
        "FIGURE_WIDTH_IN",
    )
    figure_width_in = figure4_reference_width_in * CANVAS_SCALE_RELATIVE_TO_V10

    a_rows, a_checks, a_manifest, a_data_path, a_checks_path, a_manifest_path = (
        load_panel_bundle(args.panel_a_dir.resolve(), "a")
    )
    b_rows, b_checks, b_manifest, b_data_path, b_checks_path, b_manifest_path = (
        load_panel_bundle(args.panel_b_dir.resolve(), "b")
    )
    c_rows, c_checks, c_manifest, c_data_path, c_checks_path, c_manifest_path = (
        load_panel_bundle(args.panel_c_dir.resolve(), "c")
    )

    city_order = list(a_checks["city_order"])
    if city_order != list(b_checks["city_order"]) or city_order != list(c_checks["city_order"]):
        raise AssertionError("Panel city orders differ")
    if len(city_order) != 15 or len(set(city_order)) != 15:
        raise AssertionError("Shared city order must contain 15 unique cities")
    display_cities = city_order + ["all_cities_pooled"]
    expected_a_keys = {
        (city_id, metric)
        for city_id in display_cities
        for metric in (
            "pv_first_appearance_frequency_per_building",
            "pv_area_per_building",
            "pv_area_per_roof_m2",
        )
    }
    if {(row["city_id"], row["metric"]) for row in a_rows} != expected_a_keys:
        raise AssertionError("Panel a data do not contain three metrics per shared city row")
    displayed_b_rows = [row for row in b_rows if row["track"] == "paired_boxen_distribution"]
    expected_route_keys = {
        (city_id, route) for city_id in display_cities for route in ROUTES
    }
    if {(row["city_id"], row["route"]) for row in displayed_b_rows} != expected_route_keys:
        raise AssertionError("Panel b data do not contain two routes per shared city row")
    if {(row["city_id"], row["route"]) for row in c_rows} != expected_route_keys:
        raise AssertionError("Panel c data do not contain two routes per shared city row")

    nominal_density = float(b_checks["nominal_density_kwdc_per_m2"])
    if nominal_density != 0.20:
        raise AssertionError("Unexpected nominal capacity-equivalent density")
    combined = combined_rows(a_rows, b_rows, c_rows)

    font_name = configure_style(args.style.resolve(), args.font.resolve())
    figure = plt.figure(
        figsize=(figure_width_in, FIGURE_HEIGHT_IN),
        facecolor="white",
    )
    outer = figure.add_gridspec(
        1,
        3,
        width_ratios=[1.12, 1.52, 1.56],
        left=0.125,
        right=0.987,
        top=0.84,
        bottom=0.22,
        wspace=0.14,
    )
    axis_a = figure.add_subplot(outer[0, 0])
    axis_b = figure.add_subplot(outer[0, 1], sharey=axis_a)
    c_grid = outer[0, 2].subgridspec(1, 2, width_ratios=[1.05, 1.0], wspace=0.10)
    axis_c_top = figure.add_subplot(c_grid[0, 0], sharey=axis_a)
    axis_c_gini = figure.add_subplot(c_grid[0, 1], sharey=axis_a)

    draw_panel_a(axis_a, a_rows, city_order)
    secondary_b = draw_panel_b(axis_b, b_rows, city_order, nominal_density)
    draw_panel_c(axis_c_top, axis_c_gini, c_rows, city_order)
    analytical_axes = [axis_a, axis_b, axis_c_top, axis_c_gini]
    shared_y_joined = all(
        axis_a.get_shared_y_axes().joined(axis_a, axis)
        for axis in analytical_axes[1:]
    )
    shared_y_limits_equal = all(
        np.allclose(axis_a.get_ylim(), axis.get_ylim())
        for axis in analytical_axes[1:]
    )
    if not shared_y_joined or not shared_y_limits_equal:
        raise AssertionError("Analytical axes do not share an identical city y axis")
    for artist in figure.findobj(match=lambda item: hasattr(item, "set_fontfamily")):
        try:
            artist.set_fontfamily(font_name)
        except (AttributeError, TypeError):
            pass
    scale_figure_artists(figure, CANVAS_SCALE)
    panel_label_ys, panel_label_xs = add_aligned_panel_labels(
        figure,
        [axis_a, axis_b, axis_c_top],
        secondary_b,
        font_name,
    )

    stem = "figure3_initial_v1"
    png_path = output_dir / f"{stem}.png"
    pdf_path = output_dir / f"{stem}.pdf"
    data_path = output_dir / "figure3_abc_data.csv"
    checks_path = output_dir / "figure3_abc_checks.json"
    note_path = output_dir / "figure3_abc_note.md"
    caption_path = output_dir / "figure3_abc_caption.md"
    manifest_path = output_dir / "figure3_abc_manifest.json"
    figure.savefig(
        png_path,
        dpi=300,
        facecolor="white",
        bbox_inches="tight",
        pad_inches=TIGHT_PAD_IN,
    )
    figure.savefig(
        pdf_path,
        facecolor="white",
        bbox_inches="tight",
        pad_inches=TIGHT_PAD_IN,
    )
    plt.close(figure)
    with Image.open(png_path) as rendered_png:
        png_dimensions_pixels = [rendered_png.width, rendered_png.height]
    cropped_canvas_inches = [value / 300 for value in png_dimensions_pixels]
    write_csv(data_path, combined)

    checks = {
        "schema_version": "figure3-initial-v1-checks-v1",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": "REPRODUCED",
        "source_panel_manifests_verified": True,
        "source_panel_checks_verified": True,
        "source_panel_data_hashes_verified": True,
        "canvas_dimensions_inches": [figure_width_in, FIGURE_HEIGHT_IN],
        "tight_crop_applied": True,
        "tight_crop_pad_inches": TIGHT_PAD_IN,
        "outer_canvas_padding_removed": True,
        "output_png_dimensions_pixels": png_dimensions_pixels,
        "cropped_canvas_dimensions_inches_approx": cropped_canvas_inches,
        "canvas_scale_relative_to_v10": CANVAS_SCALE_RELATIVE_TO_V10,
        "canvas_width_and_height_are_80pct_of_v10": True,
        "figure4_reference_width_inches": figure4_reference_width_in,
        "canvas_width_scale_relative_to_figure4": CANVAS_SCALE_RELATIVE_TO_V10,
        "figure4_reference_script": str(args.figure4_script.resolve()),
        "font_and_mark_sizes_unchanged_from_v10": True,
        "panel_labels": ["a", "b", "c"],
        "panel_labels_are_figure_level": True,
        "panel_label_figure_x": panel_label_xs,
        "panel_label_figure_y": panel_label_ys,
        "panel_labels_share_one_horizontal_figure_y": len(set(panel_label_ys)) == 1,
        "panel_labels_aligned_to_panel_b_top_axis_label": True,
        "panel_label_vertical_alignment": "center",
        "panel_a_label_left_aligned_to_washington_dc": True,
        "panel_b_c_labels_offset_left_of_panel_boundaries": True,
        "panel_c_top1_xlabel": "PV area in largest 1% of buildings (%)",
        "panel_c_gini_xlabel": "Gini coefficient",
        "panel_c_gini_parenthetical_removed": True,
        "panel_c_top1_host_word_replaced_with_buildings": True,
        "shared_city_y_axis": shared_y_joined,
        "shared_city_y_limits_equal": shared_y_limits_equal,
        "shared_city_y_limits": [len(display_cities) - 0.35, -0.65],
        "city_labels_appear_once_on_panel_a": True,
        "all_cities_separator_drawn_across_all_axes": True,
        "panel_legends_centered_below_xlabels": True,
        "panel_a_legend_is_single_row": True,
        "all_panel_legends_same_fontsize": True,
        "all_panel_legends_same_marker_scale": True,
        "all_panel_legends_same_column_and_handle_spacing": True,
        "all_panel_legends_vertically_aligned": True,
        "shared_legend_fontsize_before_canvas_scaling": LEGEND_FONTSIZE,
        "shared_legend_markersize_before_canvas_scaling": LEGEND_MARKERSIZE,
        "legend_fontsize_increase_from_v11_points": 1.0,
        "legend_markersize_increase_from_v11_points": 1.0,
        "shared_legend_vertical_anchor_axes": LEGEND_VERTICAL_ANCHOR,
        "panel_a_ratio_label_x_offset_points": 6,
        "panel_b_capacity_axis_label": "Capacity-equivalent (kWdc / building)",
        "panel_b_top_tick_label_pad_points": 1.0,
        "panel_b_top_axis_label_pad_points": 1.5,
        "panel_b_top_axis_label_moved_up_relative_to_v12": True,
        "panel_a_b_xlabel_to_legend_spacing_reduced": True,
        "external_axis_spines_black_solid": True,
        "internal_reference_and_separator_lines_light_gray_solid": True,
        "major_tick_grids_removed": True,
        "only_solid_auxiliary_lines_retained": True,
        "auxiliary_line_color": AUXILIARY,
        "auxiliary_lines_darkened_relative_to_v4": True,
        "panel_spacing_reduced_relative_to_v3": True,
        "artist_scale_relative_to_v3": CANVAS_SCALE,
        "y_ticks_visible_on_panels_a_b_c": True,
        "city_y_tick_labels_black": True,
        "panel_c_internal_gini_axis_y_ticks_hidden": True,
        "city_order": city_order,
        "city_order_identical_across_panels": True,
        "displayed_city_count": len(city_order),
        "pooled_row_last": True,
        "panel_a_metric_row_count": len(a_rows),
        "panel_b_route_row_count": len(displayed_b_rows),
        "panel_c_route_row_count": len(c_rows),
        "combined_data_row_count": len(combined),
        "combined_data_primary_key": ["record_id"],
        "combined_data_primary_key_unique": True,
        "panel_b_pathway_track_displayed": False,
        "panel_b_pathway_track_omission_reason": (
            "Composite requested to share city y rows across panels; the standalone "
            "three-row pooled pathway mean track remains in panel_b_boxen_v3"
        ),
        "panel_b_capacity_axis_is_nominal_not_measured": True,
        "panel_b_nominal_density_kwdc_per_m2": nominal_density,
        "panel_c_small_top_1pct_host_counts_labelled": True,
        "status_is_descriptive_not_inferential": True,
    }
    write_json(checks_path, checks)

    note_path.write_text(
        """# Figure 3 `initial_v1` note

Panels a–c are redrawn in one Matplotlib figure and use one common ordered city coordinate. City labels appear only on panel a in pure black, while visible y-axis tick marks identify the aligned rows on the left edge of each conceptual panel. All analytical axes share the same y limits, tick positions, city order, and separated pooled row. The three legends use the same font size, marker scale, column spacing, handle-to-text spacing, and vertical anchor; panel a's three entries remain on one line. Panel a ratio annotations are shifted six points to the right of their square markers. The panel b secondary axis is labelled `Capacity-equivalent (kWdc / building)` and remains a nominal 0.20 kWdc m⁻² translation; its tick-label pad is 1.0 point and title pad is 1.5 points. External axis spines are black solid lines. Major-tick grids are not drawn; only solid analytical guides, route/metric connectors, pooled-row separators, and the divider inside panel c remain. Neutral auxiliary lines use `#b8bdbc`. The 7.08-by-2.76-inch design canvas is exported with a tight bounding box and zero added padding. The three panel identifiers share the exact vertical center of the panel b title; `a,` aligns to the left edge of the `Washington DC` city label. Panel c's first x-axis label uses “buildings”, and the explanatory parenthetical below the Gini label is omitted. The lines in panels a and c connect estimands or routes within a city and are neither time trends nor uncertainty intervals.

Panel a compares newly observed-to-existing ratios for PV first appearances per Building, PV area per Building risk unit, and PV area per plan-view roof-mask area at risk. Panel b shows route-specific host-level anchor PV-area distributions with nested percentile bands, medians, and means; the top axis is a nominal 0.20 kWdc m⁻² capacity-equivalent translation. To preserve the requested common city y axis, the standalone panel b pooled pathway-mean track is not displayed in this composite and remains available in `panel_b_boxen_v3`. Panel c separates the largest-1%-host area share from the Gini coefficient; small `n=` labels identify newly observed-Building routes whose top-1% group contains only one or two hosts.

All host-area quantities attribute the anchor PV union area on a unique strict-event host to its first strict adjacent PV appearance. The figure is descriptive full-AOI evidence, not an uncertainty display, city ranking, citywide adoption estimate, measured nameplate capacity, or causal effect.

Status: `REPRODUCED` (descriptive). This `initial_v1` rendering is the user-approved visual lock; that lock does not promote the scientific evidence status to `FROZEN`.
""",
        encoding="utf-8",
    )
    caption_path.write_text(
        """**Roof-area normalization and host-size concentration change how newly observed and existing-Building PV pathways compare across cities.** (a) Connected marks give the ratio of newly observed to existing routes for PV first appearances per Building, anchor PV area per Building risk unit, and anchor PV area per corresponding plan-view roof-mask area at risk; the vertical reference at one indicates parity, and connections are not time trends or uncertainty intervals. (b) Paired nested bands summarize the 1st–99th, 10th–90th, and 25th–75th percentiles of anchor PV union area per unique strict-event host, with vertical median lines and open mean diamonds; band height does not encode host count, and the upper axis is a nominal 0.20 kWdc m⁻² translation rather than measured capacity. (c) Paired marks separately show the share of route-level PV area carried by the largest 1% of hosts and the Gini coefficient; small `n=` labels identify newly observed-Building routes whose top-1% set contains only one or two hosts. All panels use the same descriptive city order and separated pooled row. Existing-route roof area in panel a is roof-area–cohort exposure; all host-area quantities in panels b–c attribute anchor PV area to each host's first strict adjacent PV appearance. Results are descriptive full-AOI summaries rather than city rankings, uncertainty intervals, citywide adoption estimates, or causal effects.
""",
        encoding="utf-8",
    )

    output_paths = [png_path, pdf_path, data_path, checks_path, note_path, caption_path]
    manifest = {
        "schema_version": "figure3-initial-v1-source-manifest-v1",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": "REPRODUCED",
        "command": "python3 paper/figures/figure3_roof_area/figure3_abc_shared_y.py",
        "generator": {
            "path": str(script_path),
            "version": SCRIPT_VERSION,
            "sha256": sha256_file(script_path),
        },
        "scope": "full_aoi",
        "primary_key": ["record_id"],
        "city_order": city_order,
        "city_order_rule": (
            "Panel a descending full-AOI PV first-appearance ratio; pooled row last"
        ),
        "display_filters": [
            "Panel a: all three released city-level ratio metrics",
            "Panel b: paired_boxen_distribution rows only; pooled pathway mean track "
            "omitted from shared-y composite",
            "Panel c: both released concentration metrics and both routes",
        ],
        "inputs": [
            source_record(a_data_path, "Panel a displayed data", len(a_rows)),
            source_record(a_checks_path, "Panel a QA"),
            source_record(a_manifest_path, "Panel a owning manifest"),
            source_record(b_data_path, "Panel b source data", len(b_rows)),
            source_record(b_checks_path, "Panel b QA"),
            source_record(b_manifest_path, "Panel b owning manifest"),
            source_record(c_data_path, "Panel c displayed data", len(c_rows)),
            source_record(c_checks_path, "Panel c QA"),
            source_record(c_manifest_path, "Panel c owning manifest"),
            source_record(
                args.figure4_script.resolve(),
                "Figure 4 canvas-width reference script",
            ),
            source_record(args.figure_plan.resolve(), "Figure 3 design contract"),
            source_record(shared_code_path, "shared Figure 3 helpers"),
            source_record(args.style.resolve(), "shared plotting style"),
            source_record(args.font.resolve(), "embedded plotting font"),
        ],
        "outputs": {
            path.name: {
                "path": str(path),
                "bytes": path.stat().st_size,
                "sha256": sha256_file(path),
            }
            for path in output_paths
        },
    }
    manifest["outputs"][data_path.name]["row_count"] = len(combined)
    write_json(manifest_path, manifest)
    print(
        json.dumps(
            {
                "status": "REPRODUCED",
                "pdf": str(pdf_path),
                "png": str(png_path),
                "canvas_inches": [figure_width_in, FIGURE_HEIGHT_IN],
                "cropped_canvas_inches_approx": cropped_canvas_inches,
                "shared_city_rows": len(display_cities),
                "combined_data_rows": len(combined),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
