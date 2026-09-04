#!/usr/bin/env python3
"""Render the standalone Figure 2c three-factor contribution heatmap."""

from __future__ import annotations

import argparse
import csv
import json
from datetime import datetime, timezone
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.colors import LinearSegmentedColormap, TwoSlopeNorm

from figure2_draft import (
    CITY_NAMES,
    EXISTING,
    NEW,
    TEXT,
    configure_style,
    f,
    ratio_label,
    read_csv,
    sha256_file,
    source_record,
    write_json,
)


SCRIPT_VERSION = "0.2.0"
PANEL_WIDTH_IN = 4.96
BOTTOM_PANEL_HEIGHT_IN = 5.80 * 3.0 / 4.0
SORT_FIELD = "pv_area_yield_new_m2_per_new_building"
SORT_DESCRIPTION = (
    "Panel d observed new building PV area per newly observed building"
)
COMPONENTS = [
    ("stock_exposure", "Stock\nexposure"),
    ("event_intensity", "Event\nintensity"),
    ("event_footprint", "Event\nfootprint"),
    ("total_pv_area", "Total\nPV area"),
]
DATA_FIELDS = [
    "panel",
    "city_id",
    "city_name",
    "display_order",
    "component",
    "existing_to_new_ratio",
    "log2_contribution",
    "status",
]


def parse_args() -> argparse.Namespace:
    workspace = Path(__file__).resolve().parents[3]
    figure_dir = Path(__file__).resolve().parent
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=workspace / "data_high_level")
    parser.add_argument("--output-dir", type=Path, default=figure_dir)
    parser.add_argument(
        "--figure1-checks", type=Path,
        default=(workspace / "paper" / "figures" / "figure1_city_trajectories"
                 / "initial_v1" / "figure1_abcd" / "panel_a_checks.json"),
    )
    parser.add_argument(
        "--figure1-freeze-manifest", type=Path,
        default=(workspace / "paper" / "figures" / "figure1_city_trajectories"
                 / "initial_v1" / "figure1_abcd" / "freeze_manifest.json"),
    )
    parser.add_argument(
        "--style", type=Path,
        default=workspace / "paper" / "style" / "temporal_pv.mplstyle",
    )
    parser.add_argument(
        "--font", type=Path,
        default=(workspace / "paper" / "figures" / "figure1_city_trajectories"
                 / "initial_v1" / "figure1_abcd" / "code" / "arial.ttf"),
    )
    return parser.parse_args()


def write_data(path: Path, rows: list[dict[str, object]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=DATA_FIELDS)
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    args = parse_args()
    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    area_path = args.data_dir.resolve() / "city_area_weighted_stock_flow.csv"
    area_manifest_path = args.data_dir.resolve() / "area_weighted_results_manifest.json"
    shared_renderer_path = Path(__file__).resolve().parent / "figure2_draft.py"
    required = [
        area_path,
        area_manifest_path,
        args.figure1_checks.resolve(),
        args.figure1_freeze_manifest.resolve(),
        shared_renderer_path,
        args.style.resolve(),
        args.font.resolve(),
    ]
    for path in required:
        if not path.exists():
            raise FileNotFoundError(path)

    area_rows = read_csv(area_path)
    area_manifest = json.loads(area_manifest_path.read_text(encoding="utf-8"))
    expected_area_hash = area_manifest["outputs"]["city_area_weighted_stock_flow"]["sha256"]
    if sha256_file(area_path) != expected_area_hash:
        raise AssertionError("Area stock-flow table hash does not match its manifest")

    figure1_checks_path = args.figure1_checks.resolve()
    figure1_freeze_path = args.figure1_freeze_manifest.resolve()
    figure1_checks = json.loads(figure1_checks_path.read_text(encoding="utf-8"))
    figure1_freeze = json.loads(figure1_freeze_path.read_text(encoding="utf-8"))
    frozen_checks_record = figure1_freeze["files"]["panel_a_checks.json"]
    if sha256_file(figure1_checks_path) != frozen_checks_record["sha256"]:
        raise AssertionError("Figure 1 city-order checks do not match the frozen manifest")
    frozen_city_order = figure1_checks["city_order"]

    pooled_rows = [
        row for row in area_rows
        if row["scope"] == "full_aoi" and row["city_id"] == "all_cities_pooled"
    ]
    city_rows = {
        row["city_id"]: row for row in area_rows
        if row["scope"] == "full_aoi" and row["city_id"] != "all_cities_pooled"
    }
    if len(pooled_rows) != 1:
        raise AssertionError(f"Expected one pooled full-AOI row, found {len(pooled_rows)}")
    if set(city_rows) != set(frozen_city_order):
        raise AssertionError("Full-AOI cities do not match the frozen Figure 1 order")
    pooled = pooled_rows[0]
    ordered_rows = sorted(
        city_rows.values(),
        key=lambda row: (-f(row, SORT_FIELD), row["city_id"]),
    )
    ordered_observed_values = [f(row, SORT_FIELD) for row in ordered_rows]
    if any(
        left < right
        for left, right in zip(ordered_observed_values, ordered_observed_values[1:])
    ):
        raise AssertionError("Panel c city order is not descending by Panel d observed PV area")
    display_rows = ordered_rows + [pooled]

    ratios: list[list[float]] = []
    residuals: list[float] = []
    plotted_rows: list[dict[str, object]] = []
    for display_order, row in enumerate(display_rows, start=1):
        ratio_values = [
            f(row, "stock_multiplier"),
            f(row, "r_retrofit_event_per_building_cohort")
            / f(row, "r_new_event_per_building"),
            f(row, "event_size_ratio_retrofit_to_new"),
            f(row, "area_retrofit_to_new_ratio"),
        ]
        ratios.append(ratio_values)
        residuals.append(f(row, "three_factor_decomposition_residual"))
        city_name = "All cities" if row["city_id"] == "all_cities_pooled" else CITY_NAMES[row["city_id"]]
        for (component, _), ratio in zip(COMPONENTS, ratio_values):
            plotted_rows.append({
                "panel": "c",
                "city_id": row["city_id"],
                "city_name": city_name,
                "display_order": display_order,
                "component": component,
                "existing_to_new_ratio": ratio,
                "log2_contribution": np.log2(ratio),
                "status": "REPRODUCED",
            })

    log_values = np.log2(np.asarray(ratios, dtype=float))
    cmap = LinearSegmentedColormap.from_list(
        "new_neutral_existing", [NEW, "#ffffff", EXISTING], N=256
    )
    norm = TwoSlopeNorm(vmin=-3.0, vcenter=0.0, vmax=6.0)
    font_name = configure_style(args.style.resolve(), args.font.resolve())
    figure, axis = plt.subplots(
        figsize=(PANEL_WIDTH_IN, BOTTOM_PANEL_HEIGHT_IN), facecolor="white"
    )
    figure.patch.set_facecolor("white")
    axis.set_facecolor("white")
    figure.subplots_adjust(left=0.25, right=0.97, top=0.88, bottom=0.16)
    image = axis.imshow(
        log_values, cmap=cmap, norm=norm, aspect="auto", interpolation="none", alpha=1.0
    )
    for row_index, ratio_row in enumerate(ratios):
        for column_index, ratio in enumerate(ratio_row):
            label_color = "white" if abs(log_values[row_index, column_index]) > 2.25 else TEXT
            axis.text(
                column_index, row_index, ratio_label(ratio),
                ha="center", va="center", fontsize=6.5, color=label_color,
            )
    axis.axhline(len(ordered_rows) - 0.5, color=TEXT, lw=0.8)
    axis.set_xlim(-0.5, 3.5)
    axis.set_yticks(
        range(len(display_rows)),
        ["All cities" if row["city_id"] == "all_cities_pooled" else CITY_NAMES[row["city_id"]]
         for row in display_rows],
    )
    axis.set_xticks(range(len(COMPONENTS)), [label for _, label in COMPONENTS])
    axis.tick_params(
        axis="both", length=0, colors="#000000", labelcolor="#000000"
    )
    axis.xaxis.tick_top()
    axis.grid(False)
    for spine in axis.spines.values():
        spine.set_visible(False)
    axis.set_xlabel("existing building/new building ratios", labelpad=7)
    axis.xaxis.set_label_position("top")
    colorbar_bbox = [0.0, -0.055, 1.0, 0.035]
    colorbar_axis = axis.inset_axes(colorbar_bbox)
    colorbar = figure.colorbar(
        image, cax=colorbar_axis, orientation="horizontal", ticks=[-3, 0, 3, 6]
    )
    colorbar.set_label(
        r"$\log_{2}(\mathrm{contribution})$"
        "\nnew building ← 0 → existing building",
        fontsize=7.0,
        labelpad=4.0,
    )
    colorbar.ax.tick_params(labelsize=6.5, length=2, colors="#000000")
    colorbar.outline.set_linewidth(0.5)
    figure.text(
        0.035, 0.97, "c,", ha="left", va="top",
        fontsize=9.5, fontweight="normal", color=TEXT,
    )
    for artist in figure.findobj(match=lambda item: hasattr(item, "set_fontfamily")):
        try:
            artist.set_fontfamily(font_name)
        except (AttributeError, TypeError):
            pass

    maximum_residual = max(abs(value) for value in residuals)
    if maximum_residual >= 1e-12:
        raise AssertionError("Three-factor residual exceeds the plotting gate")

    png_path = output_dir / "figure2_panel_c_draft.png"
    pdf_path = output_dir / "figure2_panel_c_draft.pdf"
    data_path = output_dir / "figure2_panel_c_data.csv"
    checks_path = output_dir / "figure2_panel_c_checks.json"
    note_path = output_dir / "figure2_panel_c_note.md"
    caption_path = output_dir / "figure2_panel_c_caption.md"
    manifest_path = output_dir / "figure2_panel_c_manifest.json"
    save_kwargs = {"facecolor": "white", "transparent": False}
    figure.savefig(png_path, dpi=300, **save_kwargs)
    figure.savefig(pdf_path, **save_kwargs)
    plt.close(figure)
    write_data(data_path, plotted_rows)

    checks = {
        "schema_version": "figure2-panel-c-checks-v1",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": "REPRODUCED",
        "analysis_scope": "descriptive",
        "source_hash_verified": True,
        "full_aoi_city_count": len(ordered_rows),
        "display_row_count": len(display_rows),
        "component_column_count": len(COMPONENTS),
        "figure1_reference_city_order": frozen_city_order,
        "panel_c_city_order": [row["city_id"] for row in ordered_rows],
        "city_order_matches_frozen_figure1": [row["city_id"] for row in ordered_rows] == frozen_city_order,
        "city_order_sort_key": SORT_FIELD,
        "city_order_sort_description": SORT_DESCRIPTION,
        "city_order_sort_direction": "descending",
        "city_order_sorted_by_panel_d_observed_new_building_pv_area": True,
        "panel_d_observed_new_building_values_in_display_order": ordered_observed_values,
        "all_cities_row_is_last": display_rows[-1]["city_id"] == "all_cities_pooled",
        "pooled_canvas_label": "All cities",
        "qa_column_removed": True,
        "residual_retained_as_machine_check_only": True,
        "maximum_absolute_three_factor_log_residual": maximum_residual,
        "three_factor_identity_within_1e_12": maximum_residual < 1e-12,
        "colorbar_inset_bbox_axes_fraction": colorbar_bbox,
        "colorbar_vertical_gap_axes_fraction": 0.02,
        "colorbar_vertical_gap_scale_from_previous": 1.0 / 3.0,
        "colorbar_vspace_tighter_than_previous": True,
        "png_background": "opaque white",
        "pdf_background": "opaque white",
        "pdf_png_share_identical_colormap_and_norm": True,
        "colormap_vmin_vcenter_vmax_log2": [-3.0, 0.0, 6.0],
        "canvas_inches": [PANEL_WIDTH_IN, BOTTOM_PANEL_HEIGHT_IN],
        "top_title": "existing building/new building ratios",
        "colorbar_label_uses_math_log2_contribution": True,
        "colorbar_direction_explanation_is_second_line": True,
        "x_tick_labels_are_black": True,
        "y_tick_labels_are_black": True,
    }
    write_json(checks_path, checks)
    note_path.write_text(
        """# Figure 2c heatmap note

Rows are sorted in descending order by Panel d's observed new-building PV area
per newly observed building, followed by a separately count/area-summed `All
cities` row. Cell labels are existing-Building/new-Building ratios. The
four signed log2 components are stock exposure, event intensity, event-host PV
footprint and total attributed PV area. Positive values support the existing
route; negative values support the new route.

The decomposition residual is checked against a 1e-12 tolerance but is not
shown as a QA column. PNG and PDF use the same opaque white background, route
colormap and normalization. All values use the full-AOI strict raw-known
definition and unique-host first-appearance area attribution. Scientific
evidence status: REPRODUCED. Analysis scope: descriptive.
""",
        encoding="utf-8",
    )
    caption_path.write_text(
        """**Inherited stock exposure outweighs the new-Building event-footprint advantage, with heterogeneous event-intensity contributions across cities.** Rows are sorted in descending order by Panel d's observed new-building PV area per newly observed building, followed by a separately pooled `All cities` row. Cells report existing-Building/new-Building ratios for stock exposure, first-appearance intensity, mean PV area per first-appearance Building and total attributed anchor PV area; fill encodes the signed log2 contribution. The four components satisfy the exact multiplicative identity. The residual is machine checked and is not displayed. Results use full-AOI strict adjacent raw-known transitions and unique-Building first-appearance attribution.
""",
        encoding="utf-8",
    )

    outputs = {}
    for path in [png_path, pdf_path, data_path, checks_path, note_path, caption_path]:
        outputs[path.name] = {
            "path": str(path.resolve()),
            "bytes": path.stat().st_size,
            "sha256": sha256_file(path),
        }
    write_json(
        manifest_path,
        {
            "schema_version": "figure2-panel-c-manifest-v1",
            "generated_at_utc": datetime.now(timezone.utc).isoformat(),
            "figure": "Figure 2c three-factor contribution heatmap draft",
            "script_path": str(Path(__file__).resolve()),
            "script_version": SCRIPT_VERSION,
            "script_sha256": sha256_file(Path(__file__).resolve()),
            "font_family": font_name,
            "canvas_inches": [PANEL_WIDTH_IN, BOTTOM_PANEL_HEIGHT_IN],
            "inputs": [
                source_record(area_path, "primary_full_aoi_area_stock_flow", len(area_rows)),
                source_record(area_manifest_path, "owning_area_results_manifest"),
                source_record(figure1_checks_path, "frozen_figure1_city_order_checks"),
                source_record(figure1_freeze_path, "figure1_freeze_manifest"),
                source_record(shared_renderer_path, "shared_style_and_helpers"),
                source_record(args.style.resolve(), "shared_matplotlib_style"),
                source_record(args.font.resolve(), "font"),
            ],
            "outputs": outputs,
            "status": "REPRODUCED",
            "analysis_scope": "descriptive",
        },
    )


if __name__ == "__main__":
    main()
