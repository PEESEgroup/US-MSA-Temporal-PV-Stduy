#!/usr/bin/env python3
"""Render Figure 2 panels c and d natively with one shared city y-axis."""

from __future__ import annotations

import argparse
import json
import math
from datetime import datetime, timezone
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.colors import LinearSegmentedColormap, TwoSlopeNorm
from matplotlib.lines import Line2D

from figure2_draft import (
    EXISTING,
    LIGHT,
    NEW,
    TEXT,
    configure_style,
    ratio_label,
    read_csv,
    sha256_file,
    source_record,
    write_json,
)
from figure2_panel_c_draft import (
    BOTTOM_PANEL_HEIGHT_IN as C_PANEL_HEIGHT_IN,
    COMPONENTS,
    PANEL_WIDTH_IN as C_PANEL_WIDTH_IN,
)
from figure2_panel_d_draft import (
    BOTTOM_PANEL_HEIGHT_IN as D_PANEL_HEIGHT_IN,
    OBSERVED_LABEL,
    PANEL_WIDTH_IN as D_PANEL_WIDTH_IN,
    PARITY_LABEL,
)


SCRIPT_VERSION = "0.2.0"
LEFT_MARGIN = 0.145
RIGHT_MARGIN = 0.985
BOTTOM_MARGIN = 0.165
TOP_MARGIN = 0.875
PANEL_WSPACE = 0.14
LEFT_PANEL_LABEL_X_IN = 0.65


def parse_args() -> argparse.Namespace:
    workspace = Path(__file__).resolve().parents[3]
    figure_dir = Path(__file__).resolve().parent
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=figure_dir)
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


def verify_output(manifest_path: Path, artifact_path: Path) -> None:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    record = manifest["outputs"][artifact_path.name]
    if sha256_file(artifact_path) != record["sha256"]:
        raise AssertionError(f"{artifact_path.name} does not match {manifest_path.name}")


def main() -> None:
    args = parse_args()
    figure_dir = Path(__file__).resolve().parent
    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    c_data_path = figure_dir / "figure2_panel_c_data.csv"
    c_checks_path = figure_dir / "figure2_panel_c_checks.json"
    c_manifest_path = figure_dir / "figure2_panel_c_manifest.json"
    d_data_path = figure_dir / "figure2_panel_d_data.csv"
    d_checks_path = figure_dir / "figure2_panel_d_checks.json"
    d_manifest_path = figure_dir / "figure2_panel_d_manifest.json"
    required = [
        c_data_path, c_checks_path, c_manifest_path,
        d_data_path, d_checks_path, d_manifest_path,
        args.style.resolve(), args.font.resolve(),
    ]
    for path in required:
        if not path.exists():
            raise FileNotFoundError(path)
    for manifest_path, paths in [
        (c_manifest_path, [c_data_path, c_checks_path]),
        (d_manifest_path, [d_data_path, d_checks_path]),
    ]:
        for path in paths:
            verify_output(manifest_path, path)

    if not math.isclose(D_PANEL_WIDTH_IN / C_PANEL_WIDTH_IN, 2.0 / 3.0):
        raise AssertionError("Panel d width is not two-thirds of Panel c")
    if not math.isclose(C_PANEL_HEIGHT_IN, D_PANEL_HEIGHT_IN):
        raise AssertionError("Panel c and d height constants differ")
    combined_width = C_PANEL_WIDTH_IN + D_PANEL_WIDTH_IN
    combined_height = C_PANEL_HEIGHT_IN

    c_checks = json.loads(c_checks_path.read_text(encoding="utf-8"))
    d_checks = json.loads(d_checks_path.read_text(encoding="utf-8"))
    city_order = c_checks["panel_c_city_order"]
    if city_order != d_checks["panel_d_city_order"]:
        raise AssertionError("Panel c and d city orders differ")
    if not c_checks["city_order_sorted_by_panel_d_observed_new_building_pv_area"]:
        raise AssertionError("Panel c is not sorted by Panel d observed PV area")
    if not d_checks["city_order_sorted_by_panel_d_observed_new_building_pv_area"]:
        raise AssertionError("Panel d is not sorted by observed PV area")
    if c_checks["city_order_sort_direction"] != "descending":
        raise AssertionError("Panel c sort direction is not descending")
    if d_checks["city_order_sort_direction"] != "descending":
        raise AssertionError("Panel d sort direction is not descending")
    display_city_ids = city_order + ["all_cities_pooled"]

    c_rows = read_csv(c_data_path)
    d_rows = read_csv(d_data_path)
    c_lookup = {(row["city_id"], row["component"]): row for row in c_rows}
    d_lookup = {(row["city_id"], row["metric"]): row for row in d_rows}
    expected_c_keys = {
        (city_id, component) for city_id in display_city_ids for component, _ in COMPONENTS
    }
    expected_d_keys = {
        (city_id, metric)
        for city_id in display_city_ids
        for metric in ["observed_new_building", "parity_to_existing"]
    }
    if set(c_lookup) != expected_c_keys:
        raise AssertionError("Panel c data keys are incomplete")
    if set(d_lookup) != expected_d_keys:
        raise AssertionError("Panel d data keys are incomplete")

    city_names = {
        city_id: c_lookup[(city_id, COMPONENTS[0][0])]["city_name"]
        for city_id in display_city_ids
    }
    ratios = np.asarray([
        [float(c_lookup[(city_id, component)]["existing_to_new_ratio"])
         for component, _ in COMPONENTS]
        for city_id in display_city_ids
    ])
    log_values = np.log2(ratios)
    observed_values = [
        float(d_lookup[(city_id, "observed_new_building")]["value"])
        for city_id in display_city_ids
    ]
    parity_values = [
        float(d_lookup[(city_id, "parity_to_existing")]["value"])
        for city_id in display_city_ids
    ]
    identity_errors = [
        abs(parity / observed - ratios[row_index, -1])
        for row_index, (observed, parity) in enumerate(zip(observed_values, parity_values))
    ]
    if max(identity_errors) >= 1e-10:
        raise AssertionError("Panel c total-area ratios and Panel d parity gaps disagree")

    font_name = configure_style(args.style.resolve(), args.font.resolve())
    figure = plt.figure(figsize=(combined_width, combined_height), facecolor="white")
    grid = figure.add_gridspec(
        1, 2,
        left=LEFT_MARGIN,
        right=RIGHT_MARGIN,
        bottom=BOTTOM_MARGIN,
        top=TOP_MARGIN,
        wspace=PANEL_WSPACE,
        width_ratios=[C_PANEL_WIDTH_IN, D_PANEL_WIDTH_IN],
    )
    axis_c = figure.add_subplot(grid[0, 0])
    axis_d = figure.add_subplot(grid[0, 1], sharey=axis_c)
    for axis in [axis_c, axis_d]:
        axis.set_facecolor("white")

    cmap = LinearSegmentedColormap.from_list(
        "new_neutral_existing", [NEW, "#ffffff", EXISTING], N=256
    )
    norm = TwoSlopeNorm(vmin=-3.0, vcenter=0.0, vmax=6.0)
    image = axis_c.imshow(
        log_values, cmap=cmap, norm=norm, aspect="auto",
        interpolation="none", alpha=1.0,
    )
    for row_index, ratio_row in enumerate(ratios):
        for column_index, ratio in enumerate(ratio_row):
            label_color = "white" if abs(log_values[row_index, column_index]) > 2.25 else TEXT
            axis_c.text(
                column_index, row_index, ratio_label(ratio),
                ha="center", va="center", fontsize=6.5, color=label_color,
            )
    pooled_separator = len(city_order) - 0.5
    axis_c.axhline(pooled_separator, color=TEXT, lw=0.8)
    axis_c.set_xlim(-0.5, 3.5)
    axis_c.set_ylim(len(display_city_ids) - 0.5, -0.5)
    axis_c.set_yticks(
        range(len(display_city_ids)),
        [city_names[city_id] for city_id in display_city_ids],
    )
    axis_c.set_xticks(range(len(COMPONENTS)), [label for _, label in COMPONENTS])
    axis_c.tick_params(axis="both", length=0, colors="#000000", labelcolor="#000000")
    axis_c.xaxis.tick_top()
    axis_c.grid(False)
    for spine in axis_c.spines.values():
        spine.set_visible(False)
    axis_c.set_xlabel("existing building/new building ratios", labelpad=7)
    axis_c.xaxis.set_label_position("top")
    colorbar_bbox = [0.0, -0.055, 1.0, 0.035]
    colorbar_axis = axis_c.inset_axes(colorbar_bbox)
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

    row_indices = list(range(len(display_city_ids)))
    for row_index, (observed, parity) in enumerate(zip(observed_values, parity_values)):
        axis_d.plot(
            [observed, parity], [row_index, row_index],
            color=LIGHT, lw=1.25, zorder=1,
        )
    axis_d.scatter(
        observed_values, row_indices, s=31, marker="s", color=NEW,
        edgecolors="none", zorder=3,
    )
    axis_d.scatter(
        parity_values, row_indices, s=31, marker="o", color=EXISTING,
        edgecolors="none", zorder=3,
    )
    axis_d.axhline(pooled_separator, color=TEXT, lw=0.8)
    axis_d.set_xscale("log")
    axis_d.set_xlim(0.08, 160)
    axis_d.set_ylim(len(display_city_ids) - 0.5, -0.5)
    axis_d.tick_params(
        axis="x", colors="#000000", labelcolor="#000000"
    )
    axis_d.tick_params(axis="y", left=False, labelleft=False)
    axis_d.grid(axis="x")
    axis_d.grid(axis="y", visible=False)
    axis_d.spines["left"].set_visible(False)
    axis_d.set_xlabel(
        "PV area per newly observed building\n(m²; log scale)", labelpad=2
    )
    nominal_density = float(d_checks["nominal_capacity_density_kwdc_per_m2"])
    upper = axis_d.secondary_xaxis(
        "top",
        functions=(lambda area: area * nominal_density, lambda kwdc: kwdc / nominal_density),
    )
    upper.set_xlabel(
        "nominal kWdc-equivalent per\nnewly observed building", labelpad=7
    )
    upper.tick_params(labelsize=6.6, colors="#000000", labelcolor="#000000")
    legend_handles = [
        Line2D([], [], linestyle="none", marker="s", markersize=6.2,
               markerfacecolor=NEW, markeredgecolor="none", label=OBSERVED_LABEL),
        Line2D([], [], linestyle="none", marker="o", markersize=6.2,
               markerfacecolor=EXISTING, markeredgecolor="none", label=PARITY_LABEL),
    ]
    axis_d.legend(
        handles=legend_handles,
        loc="upper center",
        bbox_to_anchor=(0.5, -0.16),
        ncol=2,
        frameon=False,
        fontsize=8.0,
        handletextpad=0.45,
        columnspacing=1.8,
        borderaxespad=0.0,
    )

    c_label_artist = figure.text(
        LEFT_PANEL_LABEL_X_IN / combined_width,
        0.975,
        "c,",
        ha="left",
        va="top",
        fontsize=9.5,
        color=TEXT,
    )
    right_panel_left = C_PANEL_WIDTH_IN / combined_width
    d_label_artist = figure.text(
        right_panel_left + 0.014, 0.975, "d,",
        ha="left", va="top", fontsize=9.5, color=TEXT,
    )
    for artist in figure.findobj(match=lambda item: hasattr(item, "set_fontfamily")):
        try:
            artist.set_fontfamily(font_name)
        except (AttributeError, TypeError):
            pass
    figure.canvas.draw()
    renderer = figure.canvas.get_renderer()
    panel_c_ytick_right_inches = max(
        label.get_window_extent(renderer=renderer).x1
        for label in axis_c.get_yticklabels()
        if label.get_visible()
    ) / figure.dpi
    panel_c_label_left_inches = (
        c_label_artist.get_window_extent(renderer=renderer).x0 / figure.dpi
    )
    panel_d_label_left_inches = (
        d_label_artist.get_window_extent(renderer=renderer).x0 / figure.dpi
    )

    png_path = output_dir / "figure2_panels_cd_shared.png"
    pdf_path = output_dir / "figure2_panels_cd_shared.pdf"
    checks_path = output_dir / "figure2_panels_cd_shared_checks.json"
    note_path = output_dir / "figure2_panels_cd_shared_note.md"
    manifest_path = output_dir / "figure2_panels_cd_shared_manifest.json"
    save_kwargs = {"facecolor": "white", "transparent": False}
    figure.savefig(png_path, dpi=300, **save_kwargs)
    figure.savefig(pdf_path, **save_kwargs)
    plt.close(figure)

    checks = {
        "schema_version": "figure2-panels-cd-shared-checks-v1",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": "REPRODUCED",
        "analysis_scope": "native-vector shared-axis rendering of reproduced derivatives",
        "panel_layout": ["c", "d"],
        "native_matplotlib_render": True,
        "shared_yaxis": True,
        "shared_yaxis_owner": "panel c",
        "panel_d_repeated_city_labels_removed": True,
        "panel_c_city_order": city_order,
        "panel_d_city_order": d_checks["panel_d_city_order"],
        "city_order_matches": city_order == d_checks["panel_d_city_order"],
        "city_order_sort_key": c_checks["city_order_sort_key"],
        "city_order_sort_description": c_checks["city_order_sort_description"],
        "city_order_sort_direction": "descending",
        "city_order_sorted_by_panel_d_observed_new_building_pv_area": True,
        "all_cities_row_is_last": display_city_ids[-1] == "all_cities_pooled",
        "maximum_absolute_parity_identity_error": float(max(identity_errors)),
        "parity_identity_within_1e_10": bool(max(identity_errors) < 1e-10),
        "panel_c_width_inches": C_PANEL_WIDTH_IN,
        "panel_d_width_inches": D_PANEL_WIDTH_IN,
        "panel_d_to_c_width_ratio": D_PANEL_WIDTH_IN / C_PANEL_WIDTH_IN,
        "panel_d_is_two_thirds_panel_c": math.isclose(
            D_PANEL_WIDTH_IN / C_PANEL_WIDTH_IN, 2.0 / 3.0
        ),
        "shared_canvas_inches": [combined_width, combined_height],
        "grid_width_ratios": [3, 2],
        "axes_width_ratio_matches_panel_ratio": True,
        "panel_d_axis_labels_wrapped_for_two_thirds_width": True,
        "panel_d_xlabel_labelpad_points": 2.0,
        "legend_anchor_axes_fraction": [0.5, -0.16],
        "panel_c_ytick_label_right_inches_from_left": panel_c_ytick_right_inches,
        "panel_c_label_left_inches_from_left": panel_c_label_left_inches,
        "panel_c_label_requested_left_inches": LEFT_PANEL_LABEL_X_IN,
        "panel_d_label_left_inches_from_left": panel_d_label_left_inches,
        "subplot_margins": {
            "left": LEFT_MARGIN,
            "right": RIGHT_MARGIN,
            "bottom": BOTTOM_MARGIN,
            "top": TOP_MARGIN,
            "wspace": PANEL_WSPACE,
        },
        "nominal_capacity_density_kwdc_per_m2": nominal_density,
        "pdf_fonttype": 42,
        "png_background": "opaque white",
        "pdf_background": "opaque white",
    }
    write_json(checks_path, checks)
    note_path.write_text(
        """# Figure 2c--d shared-axis note

Panels c and d are rendered natively on one 8.27 × 4.35 inch Matplotlib canvas.
Their GridSpec widths follow a 3:2 ratio, with Panel d two-thirds as wide as
Panel c. They use the same y-axis object, so each Panel-d connector is centered
on the corresponding Panel-c city row. City rows are sorted in descending order
by Panel d's observed new-building PV area per newly observed building; `All
cities` is the final separated row. No standalone panel image or PDF is
rasterized into this shared page. Panel c's heatmap body uses Matplotlib's
intentional image artist while all labels, points, lines and axes remain vector
in the PDF. Scientific evidence status: REPRODUCED.
""",
        encoding="utf-8",
    )

    outputs = {}
    for path in [png_path, pdf_path, checks_path, note_path]:
        outputs[path.name] = {
            "path": str(path.resolve()),
            "bytes": path.stat().st_size,
            "sha256": sha256_file(path),
        }
    write_json(
        manifest_path,
        {
            "schema_version": "figure2-panels-cd-shared-manifest-v1",
            "generated_at_utc": datetime.now(timezone.utc).isoformat(),
            "figure": "Figure 2 panels c--d shared city axis",
            "script_path": str(Path(__file__).resolve()),
            "script_version": SCRIPT_VERSION,
            "script_sha256": sha256_file(Path(__file__).resolve()),
            "font_family": font_name,
            "canvas_inches": [combined_width, combined_height],
            "inputs": [
                source_record(c_data_path, "panel_c_reproduced_data", len(c_rows)),
                source_record(c_checks_path, "panel_c_checks"),
                source_record(c_manifest_path, "panel_c_manifest"),
                source_record(d_data_path, "panel_d_reproduced_data", len(d_rows)),
                source_record(d_checks_path, "panel_d_checks"),
                source_record(d_manifest_path, "panel_d_manifest"),
                source_record(args.style.resolve(), "shared_matplotlib_style"),
                source_record(args.font.resolve(), "font"),
            ],
            "outputs": outputs,
            "status": "REPRODUCED",
            "analysis_scope": "native-vector shared-axis rendering of reproduced derivatives",
        },
    )


if __name__ == "__main__":
    main()
