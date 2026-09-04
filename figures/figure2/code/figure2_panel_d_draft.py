#!/usr/bin/env python3
"""Render the standalone Figure 2d capacity-parity frontier."""

from __future__ import annotations

import argparse
import csv
import json
import math
from datetime import datetime, timezone
from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.lines import Line2D

from figure2_draft import (
    CITY_NAMES,
    EXISTING,
    LIGHT,
    NEW,
    TEXT,
    configure_style,
    f,
    read_csv,
    sha256_file,
    source_record,
    write_json,
)


SCRIPT_VERSION = "0.2.0"
PANEL_WIDTH_IN = 4.96 * 2.0 / 3.0
BOTTOM_PANEL_HEIGHT_IN = 5.80 * 3.0 / 4.0
SORT_FIELD = "pv_area_yield_new_m2_per_new_building"
SORT_DESCRIPTION = (
    "Panel d observed new building PV area per newly observed building"
)
DATA_FIELDS = [
    "panel",
    "city_id",
    "city_name",
    "display_order",
    "metric",
    "value",
    "unit",
    "numerator",
    "denominator",
    "status",
]
OBSERVED_LABEL = "observed new building"
PARITY_LABEL = "parity to existing"


def parse_args() -> argparse.Namespace:
    workspace = Path(__file__).resolve().parents[3]
    figure_dir = Path(__file__).resolve().parent
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=workspace / "data_high_level")
    parser.add_argument("--output-dir", type=Path, default=figure_dir)
    parser.add_argument(
        "--panel-c-checks", type=Path,
        default=figure_dir / "figure2_panel_c_checks.json",
    )
    parser.add_argument(
        "--panel-c-manifest", type=Path,
        default=figure_dir / "figure2_panel_c_manifest.json",
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
    capacity_path = args.data_dir.resolve() / "pv_area_capacity_density_scenarios.csv"
    panel_c_checks_path = args.panel_c_checks.resolve()
    panel_c_manifest_path = args.panel_c_manifest.resolve()
    shared_renderer_path = Path(__file__).resolve().parent / "figure2_draft.py"
    required = [
        area_path,
        area_manifest_path,
        capacity_path,
        panel_c_checks_path,
        panel_c_manifest_path,
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

    panel_c_checks = json.loads(panel_c_checks_path.read_text(encoding="utf-8"))
    panel_c_manifest = json.loads(panel_c_manifest_path.read_text(encoding="utf-8"))
    panel_c_checks_record = panel_c_manifest["outputs"][panel_c_checks_path.name]
    if sha256_file(panel_c_checks_path) != panel_c_checks_record["sha256"]:
        raise AssertionError("Panel c checks do not match the Panel c manifest")
    panel_c_city_order = panel_c_checks["panel_c_city_order"]

    capacity_rows = read_csv(capacity_path)
    nominal_rows = [row for row in capacity_rows if row["role"] == "nominal"]
    if len(nominal_rows) != 1:
        raise AssertionError(f"Expected one nominal capacity-density row, found {len(nominal_rows)}")
    nominal_density = float(nominal_rows[0]["power_density_kwdc_per_m2"])

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
    if set(city_rows) != set(panel_c_city_order):
        raise AssertionError("Full-AOI cities do not match Panel c")
    ordered_rows = [city_rows[city_id] for city_id in panel_c_city_order]
    display_rows = ordered_rows + [pooled_rows[0]]
    observed_city_values = [f(row, SORT_FIELD) for row in ordered_rows]
    if any(
        left < right
        for left, right in zip(observed_city_values, observed_city_values[1:])
    ):
        raise AssertionError("Panel d city order is not descending by observed PV area")

    observed_values: list[float] = []
    parity_values: list[float] = []
    plotted_rows: list[dict[str, object]] = []
    identity_errors: list[float] = []
    for display_order, row in enumerate(display_rows, start=1):
        observed = f(row, "pv_area_yield_new_m2_per_new_building")
        parity = f(row, "pv_area_retrofit_m2") / f(row, "n_new")
        observed_values.append(observed)
        parity_values.append(parity)
        identity_errors.append(
            abs((parity / observed) - f(row, "area_retrofit_to_new_ratio"))
        )
        city_name = "All cities" if row["city_id"] == "all_cities_pooled" else CITY_NAMES[row["city_id"]]
        plotted_rows.extend([
            {
                "panel": "d",
                "city_id": row["city_id"],
                "city_name": city_name,
                "display_order": display_order,
                "metric": "observed_new_building",
                "value": observed,
                "unit": "m2 per newly observed building",
                "numerator": "PV area attributed to the new-building first-appearance route",
                "denominator": "newly observed buildings",
                "status": "REPRODUCED",
            },
            {
                "panel": "d",
                "city_id": row["city_id"],
                "city_name": city_name,
                "display_order": display_order,
                "metric": "parity_to_existing",
                "value": parity,
                "unit": "m2 per newly observed building",
                "numerator": "PV area attributed to the existing-building first-appearance route",
                "denominator": "newly observed buildings",
                "status": "REPRODUCED",
            },
        ])

    font_name = configure_style(args.style.resolve(), args.font.resolve())
    figure, axis = plt.subplots(
        figsize=(PANEL_WIDTH_IN, BOTTOM_PANEL_HEIGHT_IN), facecolor="white"
    )
    figure.patch.set_facecolor("white")
    axis.set_facecolor("white")
    figure.subplots_adjust(left=0.25, right=0.97, top=0.86, bottom=0.24)

    row_indices = list(range(len(display_rows)))
    for row_index, (observed, parity) in enumerate(zip(observed_values, parity_values)):
        axis.plot([observed, parity], [row_index, row_index], color=LIGHT, lw=1.25, zorder=1)
    axis.scatter(
        observed_values, row_indices, s=31, marker="s", color=NEW,
        edgecolors="none", zorder=3,
    )
    axis.scatter(
        parity_values, row_indices, s=31, marker="o", color=EXISTING,
        edgecolors="none", zorder=3,
    )
    axis.axhline(len(ordered_rows) - 0.5, color=TEXT, lw=0.8)
    axis.set_xscale("log")
    axis.set_xlim(0.08, 160)
    axis.set_ylim(len(display_rows) - 0.5, -0.5)
    axis.set_yticks(
        row_indices,
        ["All cities" if row["city_id"] == "all_cities_pooled" else CITY_NAMES[row["city_id"]]
         for row in display_rows],
    )
    axis.set_xlabel(
        "PV area per newly observed building\n(m²; log scale)", labelpad=7
    )
    axis.tick_params(axis="both", colors="#000000", labelcolor="#000000")
    axis.tick_params(axis="y", length=0)
    axis.grid(axis="x")
    axis.grid(axis="y", visible=False)
    axis.spines["left"].set_visible(False)

    upper = axis.secondary_xaxis(
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
    axis.legend(
        handles=legend_handles,
        loc="upper center",
        bbox_to_anchor=(0.5, -0.14),
        ncol=2,
        frameon=False,
        fontsize=8.0,
        handletextpad=0.45,
        columnspacing=1.8,
        borderaxespad=0.0,
    )
    figure.text(
        0.035, 0.97, "d,", ha="left", va="top",
        fontsize=9.5, fontweight="normal", color=TEXT,
    )
    for artist in figure.findobj(match=lambda item: hasattr(item, "set_fontfamily")):
        try:
            artist.set_fontfamily(font_name)
        except (AttributeError, TypeError):
            pass

    maximum_identity_error = max(identity_errors)
    if not all(math.isclose(error, 0.0, rel_tol=1e-10, abs_tol=1e-10)
               for error in identity_errors):
        raise AssertionError("Parity/observed ratio does not reproduce total PV-area ratio")

    png_path = output_dir / "figure2_panel_d_draft.png"
    pdf_path = output_dir / "figure2_panel_d_draft.pdf"
    data_path = output_dir / "figure2_panel_d_data.csv"
    checks_path = output_dir / "figure2_panel_d_checks.json"
    note_path = output_dir / "figure2_panel_d_note.md"
    caption_path = output_dir / "figure2_panel_d_caption.md"
    manifest_path = output_dir / "figure2_panel_d_manifest.json"
    save_kwargs = {"facecolor": "white", "transparent": False}
    figure.savefig(png_path, dpi=300, **save_kwargs)
    figure.savefig(pdf_path, **save_kwargs)
    plt.close(figure)
    write_data(data_path, plotted_rows)

    checks = {
        "schema_version": "figure2-panel-d-checks-v1",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": "REPRODUCED",
        "analysis_scope": "descriptive arithmetic",
        "source_hash_verified": True,
        "full_aoi_city_count": len(ordered_rows),
        "display_row_count": len(display_rows),
        "panel_c_city_order": panel_c_city_order,
        "panel_d_city_order": [row["city_id"] for row in ordered_rows],
        "city_order_matches_panel_c": [row["city_id"] for row in ordered_rows] == panel_c_city_order,
        "city_order_sort_key": SORT_FIELD,
        "city_order_sort_description": SORT_DESCRIPTION,
        "city_order_sort_direction": "descending",
        "city_order_sorted_by_panel_d_observed_new_building_pv_area": True,
        "panel_d_observed_new_building_values_in_display_order": observed_city_values,
        "all_cities_row_is_last": display_rows[-1]["city_id"] == "all_cities_pooled",
        "pooled_canvas_label": "All cities",
        "pooled_direct_annotations_removed": True,
        "legend_position": "below x-axis label",
        "legend_anchor_axes_fraction": [0.5, -0.14],
        "legend_xlabel_vertical_gap_scale_from_previous": 0.5,
        "legend_labels": [OBSERVED_LABEL, PARITY_LABEL],
        "parity_to_existing_definition": "existing-route PV area divided by newly observed building count",
        "parity_is_not_observed_existing_building_yield": True,
        "maximum_absolute_parity_identity_error": maximum_identity_error,
        "parity_divided_by_observed_reproduces_total_pv_area_ratio": maximum_identity_error < 1e-10,
        "nominal_capacity_density_kwdc_per_m2": nominal_density,
        "nominal_capacity_axis_is_scenario_not_measured_nameplate": True,
        "png_background": "opaque white",
        "pdf_background": "opaque white",
        "x_tick_labels_are_black": True,
        "y_tick_labels_are_black": True,
        "axis_labels_wrapped_for_two_thirds_width": True,
        "canvas_inches": [PANEL_WIDTH_IN, BOTTOM_PANEL_HEIGHT_IN],
    }
    write_json(checks_path, checks)
    note_path.write_text(
        """# Figure 2d capacity-parity note

Rows exactly follow Panel c's descending observed new-building PV-area order,
followed by a separately count/area-summed `All cities` row. Orange squares show observed new-building-route PV area divided by
the number of newly observed buildings. Green circles show the PV area per
newly observed building that would be required for the new-building route to
equal the observed total PV area attributed to the existing-building route.
Thus `parity to existing` is a counterfactual arithmetic benchmark, not an
observed existing-building yield, forecast, roof-potential estimate or policy
effect.

The upper scale applies the nominal 0.20 kWdc m^-2 display conversion and is
not measured nameplate capacity. Results use full-AOI strict adjacent raw-known
transitions and unique-building first-appearance area attribution. Scientific
evidence status: REPRODUCED. Analysis scope: descriptive arithmetic.
""",
        encoding="utf-8",
    )
    caption_path.write_text(
        """**Observed new-building PV-area yield remains below the arithmetic level required to match the existing-building route's total attributed PV area.** Rows follow Panel c's descending observed new-building PV-area order, followed by a separately pooled `All cities` row. Orange squares show observed new-building-route PV area per newly observed building; green circles show the corresponding level required for that route to equal the observed existing-building-route total. Horizontal connectors show the within-city gap on a logarithmic scale. The upper axis is a nominal 0.20 kWdc m^-2 capacity-equivalent conversion, not measured nameplate capacity. Results use full-AOI strict adjacent raw-known transitions and unique-building first-appearance attribution.
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
            "schema_version": "figure2-panel-d-manifest-v1",
            "generated_at_utc": datetime.now(timezone.utc).isoformat(),
            "figure": "Figure 2d capacity-parity frontier draft",
            "script_path": str(Path(__file__).resolve()),
            "script_version": SCRIPT_VERSION,
            "script_sha256": sha256_file(Path(__file__).resolve()),
            "font_family": font_name,
            "canvas_inches": [PANEL_WIDTH_IN, BOTTOM_PANEL_HEIGHT_IN],
            "inputs": [
                source_record(area_path, "primary_full_aoi_area_stock_flow", len(area_rows)),
                source_record(area_manifest_path, "owning_area_results_manifest"),
                source_record(capacity_path, "capacity_density_scenarios", len(capacity_rows)),
                source_record(panel_c_checks_path, "panel_c_city_order_checks"),
                source_record(panel_c_manifest_path, "panel_c_manifest"),
                source_record(shared_renderer_path, "shared_style_and_helpers"),
                source_record(args.style.resolve(), "shared_matplotlib_style"),
                source_record(args.font.resolve(), "font"),
            ],
            "outputs": outputs,
            "status": "REPRODUCED",
            "analysis_scope": "descriptive arithmetic",
        },
    )


if __name__ == "__main__":
    main()
