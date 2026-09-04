#!/usr/bin/env python3
"""Render an aligned Figure 2a derivative without modifying the frozen bundle."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

import matplotlib.pyplot as plt

from figure2_draft import (
    TEXT,
    configure_style,
    draw_panel_a,
    read_csv,
    sha256_file,
    source_record,
    write_json,
)


SCRIPT_VERSION = "0.1.1"
PANEL_WIDTH_IN = 4.96
PANEL_HEIGHT_IN = 3.76
INITIAL_LEFT = 0.17
RIGHT = 0.97
TOP = 0.94
BOTTOM = 0.15
PANEL_LABEL_Y = 0.955


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


def verify_manifest_output(manifest_path: Path, artifact_path: Path) -> None:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    record = manifest["outputs"][artifact_path.name]
    if sha256_file(artifact_path) != record["sha256"]:
        raise AssertionError(f"{artifact_path.name} does not match {manifest_path.name}")


def main() -> None:
    args = parse_args()
    figure_dir = Path(__file__).resolve().parent
    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    area_path = args.data_dir.resolve() / "city_area_weighted_stock_flow.csv"
    area_manifest_path = args.data_dir.resolve() / "area_weighted_results_manifest.json"
    shared_renderer_path = figure_dir / "figure2_draft.py"
    cd_checks_path = figure_dir / "figure2_panels_cd_shared_checks.json"
    cd_manifest_path = figure_dir / "figure2_panels_cd_shared_manifest.json"
    frozen_dir = figure_dir / "panel_a_revision3"
    frozen_data_path = frozen_dir / "figure2_panel_a_data.csv"
    frozen_manifest_path = frozen_dir / "figure2_panel_a_manifest.json"
    freeze_path = frozen_dir / "freeze_manifest.json"
    required = [
        area_path, area_manifest_path, shared_renderer_path,
        cd_checks_path, cd_manifest_path,
        frozen_data_path, frozen_manifest_path, freeze_path,
        args.style.resolve(), args.font.resolve(),
    ]
    for path in required:
        if not path.exists():
            raise FileNotFoundError(path)

    area_manifest = json.loads(area_manifest_path.read_text(encoding="utf-8"))
    expected_area_hash = area_manifest["outputs"]["city_area_weighted_stock_flow"]["sha256"]
    if sha256_file(area_path) != expected_area_hash:
        raise AssertionError("Area stock-flow table hash does not match its manifest")
    verify_manifest_output(cd_manifest_path, cd_checks_path)

    freeze = json.loads(freeze_path.read_text(encoding="utf-8"))
    if freeze["freeze_state"] != "panel_a_revision3_locked":
        raise AssertionError("Panel a revision 3 is not locked")
    for path in [frozen_data_path, frozen_manifest_path]:
        if sha256_file(path) != freeze["files"][path.name]["sha256"]:
            raise AssertionError(f"Frozen Panel a file changed: {path.name}")

    area_rows = read_csv(area_path)
    pooled_rows = [
        row for row in area_rows
        if row["scope"] == "full_aoi" and row["city_id"] == "all_cities_pooled"
    ]
    city_rows = [
        row for row in area_rows
        if row["scope"] == "full_aoi" and row["city_id"] != "all_cities_pooled"
    ]
    if len(pooled_rows) != 1 or len(city_rows) != 15:
        raise AssertionError("Unexpected full-AOI Panel a rows")
    pooled = pooled_rows[0]

    cd_checks = json.loads(cd_checks_path.read_text(encoding="utf-8"))
    target_tick_right_inches = cd_checks["panel_c_ytick_label_right_inches_from_left"]
    target_label_left_inches = cd_checks["panel_c_label_left_inches_from_left"]

    font_name = configure_style(args.style.resolve(), args.font.resolve())
    figure, axis = plt.subplots(
        figsize=(PANEL_WIDTH_IN, PANEL_HEIGHT_IN), facecolor="white"
    )
    figure.subplots_adjust(
        left=INITIAL_LEFT, right=RIGHT, top=TOP, bottom=BOTTOM
    )
    draw_panel_a(axis, city_rows, pooled)
    for artist in figure.findobj(match=lambda item: hasattr(item, "set_fontfamily")):
        try:
            artist.set_fontfamily(font_name)
        except (AttributeError, TypeError):
            pass

    figure.canvas.draw()
    renderer = figure.canvas.get_renderer()
    current_tick_right_inches = max(
        label.get_window_extent(renderer=renderer).x1
        for label in axis.get_yticklabels()
        if label.get_visible()
    ) / figure.dpi
    aligned_left = INITIAL_LEFT + (
        target_tick_right_inches - current_tick_right_inches
    ) / PANEL_WIDTH_IN
    if not 0.0 < aligned_left < RIGHT:
        raise AssertionError(f"Invalid aligned left margin: {aligned_left}")
    figure.subplots_adjust(left=aligned_left)

    for artist in list(axis.texts):
        if artist.get_text() == "a,":
            artist.remove()
    aligned_label = figure.text(
        target_label_left_inches / PANEL_WIDTH_IN,
        PANEL_LABEL_Y,
        "a,",
        ha="left",
        va="top",
        fontsize=9.5,
        fontweight="normal",
        color=TEXT,
    )
    aligned_label.set_fontfamily(font_name)
    figure.canvas.draw()
    renderer = figure.canvas.get_renderer()
    aligned_tick_right_inches = max(
        label.get_window_extent(renderer=renderer).x1
        for label in axis.get_yticklabels()
        if label.get_visible()
    ) / figure.dpi
    aligned_label_left_inches = (
        aligned_label.get_window_extent(renderer=renderer).x0 / figure.dpi
    )
    tick_alignment_error_points = abs(
        aligned_tick_right_inches - target_tick_right_inches
    ) * 72.0
    label_alignment_error_points = abs(
        aligned_label_left_inches - target_label_left_inches
    ) * 72.0
    if tick_alignment_error_points > 0.1:
        raise AssertionError("Panel a and c y-tick labels did not align")
    if label_alignment_error_points > 0.1:
        raise AssertionError("Panel a and c labels did not align")

    png_path = output_dir / "figure2_panel_a_aligned.png"
    pdf_path = output_dir / "figure2_panel_a_aligned.pdf"
    checks_path = output_dir / "figure2_panel_a_aligned_checks.json"
    note_path = output_dir / "figure2_panel_a_aligned_note.md"
    manifest_path = output_dir / "figure2_panel_a_aligned_manifest.json"
    save_kwargs = {"facecolor": "white", "transparent": False}
    figure.savefig(png_path, dpi=300, **save_kwargs)
    figure.savefig(pdf_path, **save_kwargs)
    plt.close(figure)

    checks = {
        "schema_version": "figure2-panel-a-aligned-checks-v1",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": "REPRODUCED",
        "analysis_scope": "visual alignment derivative of frozen Panel a",
        "frozen_panel_a_source_modified": False,
        "frozen_panel_a_data_hash_verified": True,
        "source_area_hash_verified": True,
        "panel_c_shared_checks_hash_verified": True,
        "canvas_inches": [PANEL_WIDTH_IN, PANEL_HEIGHT_IN],
        "initial_left_margin_fraction": INITIAL_LEFT,
        "aligned_left_margin_fraction": float(aligned_left),
        "target_panel_c_ytick_label_right_inches": float(target_tick_right_inches),
        "panel_a_ytick_label_right_inches": float(aligned_tick_right_inches),
        "ytick_alignment_error_points": float(tick_alignment_error_points),
        "ytick_right_edges_aligned_with_panel_c": bool(tick_alignment_error_points <= 0.1),
        "target_panel_c_label_left_inches": float(target_label_left_inches),
        "panel_a_label_left_inches": float(aligned_label_left_inches),
        "panel_label_alignment_error_points": float(label_alignment_error_points),
        "panel_a_c_label_left_edges_aligned": bool(label_alignment_error_points <= 0.1),
        "panel_label_y_fraction": PANEL_LABEL_Y,
        "scientific_values_unchanged_from_frozen_panel_a": True,
        "frozen_panel_a_data_csv": str(frozen_data_path.resolve()),
    }
    write_json(checks_path, checks)
    note_path.write_text(
        """# Figure 2a aligned derivative note

This derivative changes only Panel a geometry. Its y-tick-label right edge is
aligned to the measured right edge of Panel c's city labels, and its `a,`
label uses the same inset physical left anchor as `c,`. The data, scales, labels,
points, connectors and scientific interpretation are unchanged from the locked
Panel-a revision-3 bundle. The frozen files are not overwritten. Scientific
evidence status: REPRODUCED.
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
            "schema_version": "figure2-panel-a-aligned-manifest-v1",
            "generated_at_utc": datetime.now(timezone.utc).isoformat(),
            "figure": "Figure 2a aligned visual derivative",
            "script_path": str(Path(__file__).resolve()),
            "script_version": SCRIPT_VERSION,
            "script_sha256": sha256_file(Path(__file__).resolve()),
            "font_family": font_name,
            "canvas_inches": [PANEL_WIDTH_IN, PANEL_HEIGHT_IN],
            "inputs": [
                source_record(area_path, "primary_full_aoi_area_stock_flow", len(area_rows)),
                source_record(area_manifest_path, "owning_area_results_manifest"),
                source_record(shared_renderer_path, "shared_figure2_renderer"),
                source_record(cd_checks_path, "panel_c_rendered_alignment_target"),
                source_record(cd_manifest_path, "panels_cd_shared_manifest"),
                source_record(frozen_data_path, "frozen_panel_a_numerical_derivative"),
                source_record(frozen_manifest_path, "frozen_panel_a_manifest"),
                source_record(freeze_path, "panel_a_freeze_manifest"),
                source_record(args.style.resolve(), "shared_matplotlib_style"),
                source_record(args.font.resolve(), "font"),
            ],
            "outputs": outputs,
            "status": "REPRODUCED",
            "analysis_scope": "visual alignment derivative of frozen Panel a",
        },
    )


if __name__ == "__main__":
    main()
