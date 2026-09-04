#!/usr/bin/env python3
"""Render the visually approved standalone Figure 2a with explicit denominators."""

from __future__ import annotations

import argparse
import csv
import json
from datetime import datetime, timezone
from pathlib import Path

import matplotlib.pyplot as plt

from figure2_draft import (
    CITY_ABBREVIATIONS,
    configure_style,
    draw_panel_a,
    f,
    read_csv,
    sha256_file,
    source_record,
    write_json,
)


SCRIPT_VERSION = "0.4.0"
DATA_FIELDS = [
    "panel",
    "city_id",
    "display_order",
    "city_abbreviation",
    "route",
    "mean_pv_area_per_first_event_host_m2",
    "pv_area_yield_m2_per_eligible_observation",
    "x_denominator",
    "y_denominator",
    "is_pooled",
    "status",
]


def parse_args() -> argparse.Namespace:
    workspace = Path(__file__).resolve().parents[3]
    figure_dir = Path(__file__).resolve().parent
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=workspace / "data_high_level")
    parser.add_argument(
        "--style", type=Path,
        default=workspace / "paper" / "style" / "temporal_pv.mplstyle",
    )
    parser.add_argument(
        "--font", type=Path,
        default=(workspace / "paper" / "figures" / "figure1_city_trajectories"
                 / "initial_v1" / "figure1_abcd" / "code" / "arial.ttf"),
    )
    parser.add_argument(
        "--output-dir", type=Path,
        default=figure_dir / "panel_a_revision3",
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
    if (output_dir / "LOCKED").exists():
        raise RuntimeError(
            f"Refusing to overwrite locked Figure 2a bundle: {output_dir}. "
            "Use a new version directory for any later revision."
        )
    output_dir.mkdir(parents=True, exist_ok=True)
    area_path = args.data_dir.resolve() / "city_area_weighted_stock_flow.csv"
    area_manifest_path = args.data_dir.resolve() / "area_weighted_results_manifest.json"
    shared_renderer_path = Path(__file__).resolve().parent / "figure2_draft.py"
    for path in [area_path, area_manifest_path, shared_renderer_path, args.style, args.font]:
        if not path.exists():
            raise FileNotFoundError(path)

    area_rows = read_csv(area_path)
    area_manifest = json.loads(area_manifest_path.read_text(encoding="utf-8"))
    expected_hash = area_manifest["outputs"]["city_area_weighted_stock_flow"]["sha256"]
    if sha256_file(area_path) != expected_hash:
        raise AssertionError("Area stock-flow table hash does not match its manifest")
    pooled = next(
        row for row in area_rows
        if row["scope"] == "full_aoi" and row["city_id"] == "all_cities_pooled"
    )
    city_rows = [
        row for row in area_rows
        if row["scope"] == "full_aoi" and row["city_id"] != "all_cities_pooled"
    ]
    if len(city_rows) != 15:
        raise AssertionError(f"Expected 15 city rows, found {len(city_rows)}")
    city_order = sorted(
        city_rows,
        key=lambda row: f(row, "area_yield_rr_new_to_retrofit"),
        reverse=True,
    )
    display_order = {row["city_id"]: index + 1 for index, row in enumerate(city_order)}
    display_order["all_cities_pooled"] = 16

    footprint_new = f(pooled, "mean_pv_area_per_new_event_m2")
    footprint_existing = f(pooled, "mean_pv_area_per_retrofit_event_m2")
    yield_new = f(pooled, "pv_area_yield_new_m2_per_new_building")
    yield_existing = f(pooled, "pv_area_yield_retrofit_m2_per_stock_exposure")
    footprint_ratio = footprint_new / footprint_existing
    yield_ratio = yield_new / yield_existing

    plotted_rows: list[dict[str, object]] = []
    for row in city_order + [pooled]:
        is_pooled = row["city_id"] == "all_cities_pooled"
        plotted_rows.extend([
            {
                "panel": "a",
                "city_id": row["city_id"],
                "display_order": display_order[row["city_id"]],
                "city_abbreviation": "POOLED" if is_pooled else CITY_ABBREVIATIONS[row["city_id"]],
                "route": "new_building",
                "mean_pv_area_per_first_event_host_m2": f(
                    row, "mean_pv_area_per_new_event_m2"
                ),
                "pv_area_yield_m2_per_eligible_observation": f(
                    row, "pv_area_yield_new_m2_per_new_building"
                ),
                "x_denominator": "strict unique-host new-route PV event",
                "y_denominator": "newly observed Building",
                "is_pooled": is_pooled,
                "status": "REPRODUCED",
            },
            {
                "panel": "a",
                "city_id": row["city_id"],
                "display_order": display_order[row["city_id"]],
                "city_abbreviation": "POOLED" if is_pooled else CITY_ABBREVIATIONS[row["city_id"]],
                "route": "existing_building",
                "mean_pv_area_per_first_event_host_m2": f(
                    row, "mean_pv_area_per_retrofit_event_m2"
                ),
                "pv_area_yield_m2_per_eligible_observation": f(
                    row, "pv_area_yield_retrofit_m2_per_stock_exposure"
                ),
                "x_denominator": "strict unique-host existing-route PV event",
                "y_denominator": "eligible existing-Building cohort observation",
                "is_pooled": is_pooled,
                "status": "REPRODUCED",
            },
        ])

    font_name = configure_style(args.style.resolve(), args.font.resolve())
    figure, axis = plt.subplots(figsize=(4.96, 3.76), facecolor="white")
    figure.subplots_adjust(left=0.17, right=0.97, top=0.94, bottom=0.15)
    draw_panel_a(axis, city_rows, pooled)
    for artist in figure.findobj(match=lambda item: hasattr(item, "set_fontfamily")):
        try:
            artist.set_fontfamily(font_name)
        except (AttributeError, TypeError):
            pass

    png_path = output_dir / "figure2_panel_a_revision3.png"
    pdf_path = output_dir / "figure2_panel_a_revision3.pdf"
    data_path = output_dir / "figure2_panel_a_data.csv"
    checks_path = output_dir / "figure2_panel_a_checks.json"
    note_path = output_dir / "figure2_panel_a_note.md"
    caption_path = output_dir / "figure2_panel_a_caption.md"
    manifest_path = output_dir / "figure2_panel_a_manifest.json"
    figure.savefig(png_path, dpi=300, facecolor="white")
    figure.savefig(pdf_path, facecolor="white")
    plt.close(figure)
    write_data(data_path, plotted_rows)

    checks = {
        "schema_version": "figure2-panel-a-checks-v3",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": "REPRODUCED",
        "analysis_scope": "descriptive",
        "source_hash_verified": True,
        "source_row_count": len(area_rows),
        "full_aoi_city_count": len(city_rows),
        "background_city_point_count": len(city_rows) * 2,
        "city_connector_count": len(city_rows),
        "city_abbreviation_count": len(CITY_ABBREVIATIONS),
        "city_abbreviations_unique": len(set(CITY_ABBREVIATIONS.values())) == len(city_rows),
        "pooled_point_count": 2,
        "pooled_full_aoi_row_unique": sum(
            row["scope"] == "full_aoi" and row["city_id"] == "all_cities_pooled"
            for row in area_rows
        ) == 1,
        "mean_footprint_new_to_existing_ratio": footprint_ratio,
        "area_yield_new_to_existing_ratio": yield_ratio,
        "x_axis_denominator": "unique PV-host Building with a classified first event",
        "y_axis_new_denominator": "newly observed Building",
        "y_axis_existing_denominator": "eligible existing-Building cohort observation",
        "y_axis_denominators_are_explicitly_distinct": True,
        "pooled_points_are_count_area_summed_not_unweighted_city_means": True,
        "pooled_connector_is_opaque_black": True,
        "pooled_axis_guides_are_route_colored_opaque_dashed": True,
        "pooled_axis_guide_count": 4,
        "pooled_labels_use_consistent_axis_value_format": True,
        "pooled_guide_labels_are_numeric_only": True,
        "pooled_point_labels": [
            "all-city",
            "all-city",
        ],
        "route_legend_labels": ["existing building", "new building"],
        "route_legend_location": "inside upper center",
        "route_legend_fontsize_points": 8.8,
        "route_legend_marker_size_points": 7.0,
        "route_legend_size_increase_points": 2.0,
        "nyc_atl_msp_labels_are_lower_right": True,
        "explicit_x_tick_labels": [30, 50, 100, 200, 400],
        "explicit_y_tick_labels": [0.03, 0.05, 0.1, 0.2, 0.5, 1, 2, 5],
        "axis_labels_use_building_and_observation_language": True,
        "x_axis_label": "mean PV area among buildings with a first PV appearance (m2; log scale)",
        "y_axis_label": "mean PV area among all building observations (m2; log scale)",
        "y_axis_label_is_single_line": True,
        "figure_size_inches": [4.96, 3.76],
        "figure_size_scale_from_previous": 0.8,
        "visual_version": "panel_a_revision3",
        "visual_freeze_ready": True,
        "all_city_point_label_offset_points": 4,
        "major_ticks_and_labels_are_solid_black": True,
        "minor_ticks_are_solid_black": True,
        "left_and_bottom_spines_are_solid_black": True,
        "grid_remains_light_neutral_dotted": True,
        "city_abbreviations_use_three_to_four_point_offsets": True,
        "risk_unit_term_removed_from_canvas": True,
        "strict_event_term_removed_from_canvas": True,
    }
    write_json(checks_path, checks)
    note_path.write_text(
        """# Figure 2a revision 3 note

The x-axis conditions on Buildings with a classified first PV appearance and compares
mean anchor PV area per unique PV-host Building. The y-axis includes all eligible
observations, including those without a PV event: the new route is divided by
newly observed Buildings, whereas the existing route is divided by eligible
existing-Building cohort observations. One existing Building can contribute
multiple cohort observations until its first qualifying PV event or the end of
follow-up.

Each city contributes one semi-transparent point per route. A light connector
joins its existing- and new-route points, and the new-route endpoint carries the
city abbreviation. The two opaque points are count/area-summed 15-city pooled
values, not unweighted arithmetic means of the city points. Both pooled points
are directly labelled `all-city`; the route mapping is defined once by the
circle/square legend inside the upper plot area.

A classified first PV appearance requires an accepted adjacent PV A-to-P transition
with known states and no bridging across unknown observations. New-route events
coincide with a Building A-to-P transition; existing-route events occur while
the Building remains P-to-P. All anchor PV area on a unique host is assigned to
that first classified event, so later expansion is not time-resolved. Scientific
evidence status: REPRODUCED. The analysis scope is descriptive. Visual approval
is recorded separately by the bundle freeze manifest.
""",
        encoding="utf-8",
    )
    caption_path.write_text(
        """**Newly observed Buildings carry larger PV footprints among first-appearance hosts and more PV area when averaged over all eligible observations.** The x-axis reports mean anchor PV area per unique Building with a classified first PV appearance; the y-axis includes observations without an appearance. Each city contributes one semi-transparent point per route; a light connector and city abbreviation identify the pair. Circles denote existing Buildings and squares denote new Buildings. Larger opaque points labelled `all-city` show count/area-summed 15-city pooled values rather than unweighted city means. New-route y-values are divided by newly observed Buildings, whereas existing-route y-values are divided by eligible existing-Building cohort observations. Results use the full-AOI strict raw-known definition; neither axis is roof utilization or measured nameplate capacity.
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
            "schema_version": "figure2-panel-a-manifest-v3",
            "generated_at_utc": datetime.now(timezone.utc).isoformat(),
            "figure": "Figure 2a revision 3 connected scatter",
            "script_path": str(Path(__file__).resolve()),
            "script_version": SCRIPT_VERSION,
            "script_sha256": sha256_file(Path(__file__).resolve()),
            "font_family": font_name,
            "canvas_inches": [4.96, 3.76],
            "inputs": [
                source_record(area_path, "primary_full_aoi_area_stock_flow", len(area_rows)),
                source_record(area_manifest_path, "owning_area_results_manifest"),
                source_record(shared_renderer_path, "shared_figure2_renderer"),
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
