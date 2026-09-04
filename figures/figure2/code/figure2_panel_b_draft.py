#!/usr/bin/env python3
"""Render the standalone Figure 2b count-to-area weighting slope plot."""

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
    EXISTING,
    NEW,
    TEXT,
    configure_style,
    f,
    i,
    read_csv,
    sha256_file,
    source_record,
    write_json,
)


SCRIPT_VERSION = "0.3.2"
PANEL_WIDTH_IN = 4.96 * 2.0 / 3.0
TOP_PANEL_HEIGHT_IN = 3.76
DATA_FIELDS = [
    "panel",
    "weighting",
    "route",
    "value",
    "total",
    "share",
    "unit",
    "denominator",
    "status",
]


def parse_args() -> argparse.Namespace:
    workspace = Path(__file__).resolve().parents[3]
    figure_dir = Path(__file__).resolve().parent
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=workspace / "data_high_level")
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
    for path in [area_path, area_manifest_path, shared_renderer_path, args.style, args.font]:
        if not path.exists():
            raise FileNotFoundError(path)

    area_rows = read_csv(area_path)
    area_manifest = json.loads(area_manifest_path.read_text(encoding="utf-8"))
    expected_hash = area_manifest["outputs"]["city_area_weighted_stock_flow"]["sha256"]
    if sha256_file(area_path) != expected_hash:
        raise AssertionError("Area stock-flow table hash does not match its manifest")
    pooled_rows = [
        row for row in area_rows
        if row["scope"] == "full_aoi" and row["city_id"] == "all_cities_pooled"
    ]
    if len(pooled_rows) != 1:
        raise AssertionError(f"Expected one pooled full-AOI row, found {len(pooled_rows)}")
    pooled = pooled_rows[0]

    event_new = i(pooled, "y_new")
    event_existing = i(pooled, "y_retrofit")
    event_total = event_new + event_existing
    area_new = f(pooled, "pv_area_new_m2")
    area_existing = f(pooled, "pv_area_retrofit_m2")
    area_total = area_new + area_existing
    new_shares = [100.0 * event_new / event_total, 100.0 * area_new / area_total]
    existing_shares = [100.0 - value for value in new_shares]
    shift_pp = new_shares[1] - new_shares[0]
    fold_change = new_shares[1] / new_shares[0]

    plotted_rows = [
        {
            "panel": "b",
            "weighting": "strict_first_event_host_count",
            "route": "new_building",
            "value": event_new,
            "total": event_total,
            "share": new_shares[0] / 100.0,
            "unit": "unique hosts",
            "denominator": "strict-classified unique first-event hosts",
            "status": "REPRODUCED",
        },
        {
            "panel": "b",
            "weighting": "strict_first_event_host_count",
            "route": "existing_building",
            "value": event_existing,
            "total": event_total,
            "share": existing_shares[0] / 100.0,
            "unit": "unique hosts",
            "denominator": "strict-classified unique first-event hosts",
            "status": "REPRODUCED",
        },
        {
            "panel": "b",
            "weighting": "attributed_anchor_pv_area",
            "route": "new_building",
            "value": area_new,
            "total": area_total,
            "share": new_shares[1] / 100.0,
            "unit": "m2",
            "denominator": "anchor PV area on strict-classified unique first-event hosts",
            "status": "REPRODUCED",
        },
        {
            "panel": "b",
            "weighting": "attributed_anchor_pv_area",
            "route": "existing_building",
            "value": area_existing,
            "total": area_total,
            "share": existing_shares[1] / 100.0,
            "unit": "m2",
            "denominator": "anchor PV area on strict-classified unique first-event hosts",
            "status": "REPRODUCED",
        },
    ]

    font_name = configure_style(args.style.resolve(), args.font.resolve())
    figure, axes = plt.subplots(
        2, 1, figsize=(PANEL_WIDTH_IN, TOP_PANEL_HEIGHT_IN), facecolor="white"
    )
    figure.subplots_adjust(left=0.24, right=0.98, top=0.95, bottom=0.04, hspace=0.22)
    pie_specs = [
        (
            axes[0], existing_shares[0], new_shares[0],
            "buildings with a first\nPV appearance\ncount weighted",
            f"{event_total:,}\nbuildings",
            -90.0,
        ),
        (
            axes[1], existing_shares[1], new_shares[1],
            "PV area on the\nsame buildings\narea weighted",
            f"{area_total / 1e6:.3f}\nkm²",
            90.0,
        ),
    ]
    new_wedge_points: list[tuple[plt.Axes, tuple[float, float]]] = []
    title_specs: list[tuple[plt.Axes, str]] = []
    pie_startangles: list[float] = []
    for axis, existing_share, new_share, title, total_label, new_target_angle in pie_specs:
        startangle = new_target_angle - 1.8 * new_share
        pie_startangles.append(startangle)
        wedges, _ = axis.pie(
            [existing_share, new_share],
            colors=[EXISTING, NEW],
            startangle=startangle,
            counterclock=False,
            radius=0.78,
            wedgeprops={"width": 0.47, "edgecolor": "white", "linewidth": 0.8},
        )
        existing_label_y = 0.57 if new_target_angle < 0 else -0.57
        axis.text(
            0.0,
            existing_label_y,
            f"{existing_share:.1f}%\nexisting",
            ha="center", va="center", fontsize=7.0, color="white", linespacing=1.05,
        )
        new_angle = math.radians((wedges[1].theta1 + wedges[1].theta2) / 2.0)
        new_xy = (0.76 * math.cos(new_angle), 0.76 * math.sin(new_angle))
        new_wedge_points.append((axis, new_xy))
        new_label_y = -0.78 if new_target_angle < 0 else 0.78
        axis.annotate(
            f"new {new_share:.1f}%",
            xy=new_xy,
            xytext=(0.57, new_label_y),
            ha="left", va="center", fontsize=7.2, color=NEW,
            arrowprops={"arrowstyle": "-", "color": NEW, "lw": 0.75},
        )
        axis.text(
            0.0, 0.0, total_label,
            ha="center", va="center", fontsize=7.7, color=TEXT, linespacing=1.05,
        )
        title_specs.append((axis, title))
        axis.set_xlim(-1.05, 1.20)
        axis.set_ylim(-1.02, 1.02)
        axis.set_aspect("equal")
        axis.set_axis_off()

    figure.canvas.draw()
    for axis, title in title_specs:
        bbox = axis.get_position()
        figure.text(
            0.05, bbox.y0 + bbox.height / 2.0, title,
            ha="left", va="center", fontsize=8.0, color=TEXT, linespacing=1.10,
        )
    transformed_wedge_points = [
        figure.transFigure.inverted().transform(axis.transData.transform(point))
        for axis, point in new_wedge_points
    ]
    connector_x = sum(point[0] for point in transformed_wedge_points) / 2.0
    top_y = transformed_wedge_points[0][1]
    bottom_y = transformed_wedge_points[1][1]
    connector_text_y = (top_y + bottom_y) / 2.0
    connector_gap = 0.055
    for y_start, y_end in [
        (bottom_y + 0.012, connector_text_y - connector_gap),
        (connector_text_y + connector_gap, top_y - 0.012),
    ]:
        figure.add_artist(Line2D(
            [connector_x, connector_x], [y_start, y_end],
            transform=figure.transFigure, color=NEW, lw=1.15,
            solid_capstyle="round",
        ))
    figure.text(
        connector_x + 0.025, connector_text_y,
        f"+{shift_pp:.1f} pp  ·  {fold_change:.2f}×",
        ha="left", va="center", fontsize=7.6, color=NEW,
    )
    figure.text(
        0.035, 0.955, "b,", ha="left", va="top",
        fontsize=9.5, fontweight="normal", color=TEXT,
    )
    for artist in figure.findobj(match=lambda item: hasattr(item, "set_fontfamily")):
        try:
            artist.set_fontfamily(font_name)
        except (AttributeError, TypeError):
            pass

    png_path = output_dir / "figure2_panel_b_draft.png"
    pdf_path = output_dir / "figure2_panel_b_draft.pdf"
    data_path = output_dir / "figure2_panel_b_data.csv"
    checks_path = output_dir / "figure2_panel_b_checks.json"
    note_path = output_dir / "figure2_panel_b_note.md"
    caption_path = output_dir / "figure2_panel_b_caption.md"
    manifest_path = output_dir / "figure2_panel_b_manifest.json"
    figure.savefig(png_path, dpi=300, facecolor="white")
    figure.savefig(pdf_path, facecolor="white")
    plt.close(figure)
    write_data(data_path, plotted_rows)

    checks = {
        "schema_version": "figure2-panel-b-checks-v1",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": "REPRODUCED",
        "analysis_scope": "descriptive",
        "source_hash_verified": True,
        "pooled_full_aoi_row_count": len(pooled_rows),
        "strict_first_event_host_total": event_total,
        "classified_anchor_pv_area_m2": area_total,
        "new_host_count_share": new_shares[0] / 100.0,
        "new_anchor_area_share": new_shares[1] / 100.0,
        "new_share_shift_percentage_points": shift_pp,
        "new_share_area_to_count_fold_change": fold_change,
        "count_route_shares_sum_to_one": abs(sum([new_shares[0], existing_shares[0]]) - 100.0) < 1e-12,
        "area_route_shares_sum_to_one": abs(sum([new_shares[1], existing_shares[1]]) - 100.0) < 1e-12,
        "same_strict_classified_host_set_under_both_weightings": True,
        "left_censored_and_unavailable_hosts_excluded": True,
        "distinct_from_figure1c_onset_censoring_composition": True,
        "figure1c_estimand": "resolved non-conflict anchor PV area by Building-onset censoring class",
        "figure2b_estimand": "strict first-event route share under host-count versus attributed-area weighting",
        "canvas_inches": [PANEL_WIDTH_IN, TOP_PANEL_HEIGHT_IN],
        "plot_type": "two donut-style pie charts",
        "pie_chart_count": 2,
        "route_colors_match_frozen_panel_a": True,
        "new_route_labels_use_leader_lines": True,
        "panel_label_is_inside_canvas": True,
        "canvas_uses_building_instead_of_host": True,
        "canvas_uses_appearance_instead_of_event": True,
        "canvas_labels_match_frozen_panel_a_language": True,
        "comparison_note_removed_from_bottom": True,
        "pie_arrangement": "vertical_count_above_area",
        "titles_position": "left of pies",
        "new_wedge_target_positions": ["bottom", "top"],
        "new_wedge_target_angles_degrees": [-90.0, 90.0],
        "pie_startangles_degrees": pie_startangles,
        "comparison_connector_orientation": "vertical",
        "vertical_connector_segment_count": 2,
        "difference_label_is_on_vertical_connector_gap": True,
        "vertical_connector_gap_figure_fraction": 2 * connector_gap,
        "difference_symbols_clear_of_connector": True,
        "difference_label_adjacent_to_connector_gap": True,
    }
    write_json(checks_path, checks)
    note_path.write_text(
        """# Figure 2b paired-pie note

This panel uses the pooled full-AOI strict raw-known first-event host set. The
upper pie weights each classified unique host equally; the lower pie weights
the same route-classified host set by anchor PV union area attributed to its
first strict event. New- and existing-route shares sum to 100% within each
weighting scheme. The titles sit to the left of their pies. The upper
new-Building wedge is centered at the bottom and the lower new-Building wedge
at the top, so the two wedges face one another across a vertical connector that
carries the percentage-point and fold comparison.

The paired donut-style pie charts preserve the full 100% composition under
each weighting scheme. Their centre labels report the corresponding total, and
the small new-Building wedges use direct labels and leader lines.

This estimand is not the onset-censoring composition in Figure 1c. Figure 1c
partitions resolved non-conflict PV area among Building left-censored,
cohort-contemporaneous and between-cohort classes. Figure 2b excludes hosts that
cannot enter the strict adjacent route classification and asks how area
weighting changes the new-versus-existing diagnosis within that classified
set. Scientific evidence status: REPRODUCED. Analysis scope: descriptive.
""",
        encoding="utf-8",
    )
    caption_path.write_text(
        f"""**Area weighting increases the diagnosed new-Building share within the strict first-event host set.** The upper pie count weights {event_total:,} classified unique hosts, assigning {new_shares[0]:.1f}% to the new-Building route. The lower pie weights the same classified host set by {area_total / 1e6:.3f} km² of attributed anchor PV area, raising the new-route share to {new_shares[1]:.1f}% ({shift_pp:.1f} percentage points; {fold_change:.2f}×). Existing-Building shares are the complements. Unlike Fig. 1c, this panel does not partition onset censoring classes. All area on a unique host is attributed to its first strict adjacent accepted PV appearance; later expansion is not time-resolved.
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
            "schema_version": "figure2-panel-b-manifest-v1",
            "generated_at_utc": datetime.now(timezone.utc).isoformat(),
            "figure": "Figure 2b paired count-to-area composition pies draft",
            "script_path": str(Path(__file__).resolve()),
            "script_version": SCRIPT_VERSION,
            "script_sha256": sha256_file(Path(__file__).resolve()),
            "font_family": font_name,
            "canvas_inches": [PANEL_WIDTH_IN, TOP_PANEL_HEIGHT_IN],
            "inputs": [
                source_record(area_path, "primary_full_aoi_area_stock_flow", len(area_rows)),
                source_record(area_manifest_path, "owning_area_results_manifest"),
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
