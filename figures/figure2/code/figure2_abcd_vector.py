#!/usr/bin/env python3
"""Assemble native-vector Figure 2 from a--b and shared-axis c--d panels."""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from PIL import Image, ImageChops
import pypdf
from pypdf import PdfReader, PdfWriter, Transformation
from pypdf._page import PageObject


HERE = Path(__file__).resolve().parent
SCRIPT_VERSION = "0.3.0"
DPI = 300
VSPACE_REDUCTION_IN = 0.02
LEFT_CONTENT_MARGIN_IN = 0.10


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=HERE)
    parser.add_argument("--basename", default="figure2_abcd_vector")
    return parser.parse_args()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def source_record(path: Path, role: str) -> dict[str, object]:
    return {
        "path": str(path.resolve()),
        "role": role,
        "bytes": path.stat().st_size,
        "sha256": sha256_file(path),
    }


def verify_output(manifest_path: Path, artifact_path: Path) -> None:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    record = manifest["outputs"][artifact_path.name]
    if sha256_file(artifact_path) != record["sha256"]:
        raise AssertionError(f"{artifact_path.name} does not match {manifest_path.name}")


def main() -> None:
    args = parse_args()
    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    frozen_a_dir = HERE / "panel_a_revision3"
    a_pdf = HERE / "figure2_panel_a_aligned.pdf"
    a_png = HERE / "figure2_panel_a_aligned.png"
    a_checks = HERE / "figure2_panel_a_aligned_checks.json"
    a_manifest = HERE / "figure2_panel_a_aligned_manifest.json"
    a_data = frozen_a_dir / "figure2_panel_a_data.csv"
    frozen_a_pdf = frozen_a_dir / "figure2_panel_a_revision3.pdf"
    frozen_a_png = frozen_a_dir / "figure2_panel_a_revision3.png"
    frozen_a_checks = frozen_a_dir / "figure2_panel_a_checks.json"
    frozen_a_manifest = frozen_a_dir / "figure2_panel_a_manifest.json"
    a_freeze = frozen_a_dir / "freeze_manifest.json"
    b_pdf = HERE / "figure2_panel_b_draft.pdf"
    b_png = HERE / "figure2_panel_b_draft.png"
    b_data = HERE / "figure2_panel_b_data.csv"
    b_checks = HERE / "figure2_panel_b_checks.json"
    b_manifest = HERE / "figure2_panel_b_manifest.json"
    cd_pdf = HERE / "figure2_panels_cd_shared.pdf"
    cd_png = HERE / "figure2_panels_cd_shared.png"
    cd_checks = HERE / "figure2_panels_cd_shared_checks.json"
    cd_manifest = HERE / "figure2_panels_cd_shared_manifest.json"
    c_data = HERE / "figure2_panel_c_data.csv"
    d_data = HERE / "figure2_panel_d_data.csv"
    required = [
        a_pdf, a_png, a_checks, a_manifest,
        a_data, frozen_a_pdf, frozen_a_png, frozen_a_checks,
        frozen_a_manifest, a_freeze,
        b_pdf, b_png, b_data, b_checks, b_manifest,
        cd_pdf, cd_png, cd_checks, cd_manifest, c_data, d_data,
    ]
    for path in required:
        if not path.exists():
            raise FileNotFoundError(path)

    for path in [a_pdf, a_png, a_checks]:
        verify_output(a_manifest, path)
    for path in [b_pdf, b_png, b_data, b_checks]:
        verify_output(b_manifest, path)
    for path in [cd_pdf, cd_png, cd_checks]:
        verify_output(cd_manifest, path)

    freeze = json.loads(a_freeze.read_text(encoding="utf-8"))
    if freeze["freeze_state"] != "panel_a_revision3_locked":
        raise AssertionError("Panel a is not locked")
    for path in [
        frozen_a_pdf, frozen_a_png, a_data, frozen_a_checks, frozen_a_manifest
    ]:
        if sha256_file(path) != freeze["files"][path.name]["sha256"]:
            raise AssertionError(f"Frozen Panel a file changed: {path.name}")

    a_alignment_checks = json.loads(a_checks.read_text(encoding="utf-8"))
    if not a_alignment_checks["ytick_right_edges_aligned_with_panel_c"]:
        raise AssertionError("Panels a and c y-tick labels are not aligned")
    if not a_alignment_checks["panel_a_c_label_left_edges_aligned"]:
        raise AssertionError("Panels a and c labels are not aligned")

    cd_check_values = json.loads(cd_checks.read_text(encoding="utf-8"))
    if not cd_check_values["shared_yaxis"] or not cd_check_values["city_order_matches"]:
        raise AssertionError("Panels c and d do not share a verified city axis")
    if not cd_check_values["city_order_sorted_by_panel_d_observed_new_building_pv_area"]:
        raise AssertionError("Panels c and d are not sorted by observed new-building PV area")

    a_page = PdfReader(str(a_pdf)).pages[0]
    b_page = PdfReader(str(b_pdf)).pages[0]
    cd_page = PdfReader(str(cd_pdf)).pages[0]
    a_width, a_height = float(a_page.mediabox.width), float(a_page.mediabox.height)
    b_width, b_height = float(b_page.mediabox.width), float(b_page.mediabox.height)
    cd_width, cd_height = float(cd_page.mediabox.width), float(cd_page.mediabox.height)
    tolerance = 0.01
    if abs(a_height - b_height) > tolerance:
        raise AssertionError("Panels a and b have different page heights")
    if not abs(b_width / a_width - 2.0 / 3.0) < 1e-8:
        raise AssertionError("Panel b width is not two-thirds of Panel a")
    if abs(a_width + b_width - cd_width) > tolerance:
        raise AssertionError("Top-row and bottom-row vector widths differ")
    panel_b_label_left_inches = a_width / 72.0 + 0.035 * b_width / 72.0
    panel_d_label_left_inches = cd_check_values["panel_d_label_left_inches_from_left"]
    panel_b_d_label_error_points = abs(
        panel_b_label_left_inches - panel_d_label_left_inches
    ) * 72.0
    if panel_b_d_label_error_points > 0.1:
        raise AssertionError("Panels b and d labels are not aligned")

    with Image.open(a_png) as a_source, Image.open(cd_png) as cd_source:
        a_rgb = a_source.convert("RGB")
        cd_rgb = cd_source.convert("RGB")
        a_bbox = ImageChops.difference(
            a_rgb, Image.new("RGB", a_rgb.size, "white")
        ).getbbox()
        cd_bbox = ImageChops.difference(
            cd_rgb, Image.new("RGB", cd_rgb.size, "white")
        ).getbbox()
    if a_bbox is None or cd_bbox is None:
        raise AssertionError("Cannot determine the left content boundary")
    source_leftmost_content_pixel = min(a_bbox[0], cd_bbox[0])
    requested_left_margin_pixels = round(LEFT_CONTENT_MARGIN_IN * DPI)
    left_crop_pixels = max(
        0, source_leftmost_content_pixel - requested_left_margin_pixels
    )
    left_crop_points = left_crop_pixels / DPI * 72.0

    source_combined_width = cd_width
    combined_width = source_combined_width - left_crop_points
    vspace_reduction_points = VSPACE_REDUCTION_IN * 72.0
    combined_height = a_height + cd_height - vspace_reduction_points
    combined_page = PageObject.create_blank_page(width=combined_width, height=combined_height)
    combined_page.merge_transformed_page(
        cd_page, Transformation().translate(-left_crop_points, 0)
    )
    top_row_y = cd_height - vspace_reduction_points
    combined_page.merge_transformed_page(
        a_page, Transformation().translate(-left_crop_points, top_row_y)
    )
    combined_page.merge_transformed_page(
        b_page, Transformation().translate(a_width - left_crop_points, top_row_y)
    )

    pdf_path = output_dir / f"{args.basename}.pdf"
    png_path = output_dir / f"{args.basename}.png"
    checks_path = output_dir / f"{args.basename}_checks.json"
    note_path = output_dir / f"{args.basename}_note.md"
    caption_path = output_dir / f"{args.basename}_caption.md"
    manifest_path = output_dir / f"{args.basename}_manifest.json"
    writer = PdfWriter()
    writer.add_page(combined_page)
    writer.add_metadata({
        "/Title": "Figure 2 — New-route area advantages meet inherited stock scale",
        "/Subject": "Native-vector 2x2 composite; panels c and d share the city y-axis",
        "/Creator": f"figure2_abcd_vector.py {SCRIPT_VERSION}",
    })
    with pdf_path.open("wb") as stream:
        writer.write(stream)

    with Image.open(a_png) as a_source, Image.open(b_png) as b_source, Image.open(cd_png) as cd_source:
        a_image = a_source.convert("RGB")
        b_image = b_source.convert("RGB")
        cd_image = cd_source.convert("RGB")
        if a_image.height != b_image.height:
            raise AssertionError("Panel a and b PNG heights differ")
        top_png_width = a_image.width + b_image.width
        if abs(top_png_width - cd_image.width) > 1:
            raise AssertionError("Top-row and bottom-row PNG widths differ by more than rounding")
        vspace_reduction_pixels = round(VSPACE_REDUCTION_IN * DPI)
        top_overlap = Image.new("RGB", (top_png_width, vspace_reduction_pixels), "white")
        top_overlap.paste(
            a_image.crop((0, a_image.height - vspace_reduction_pixels,
                          a_image.width, a_image.height)),
            (0, 0),
        )
        top_overlap.paste(
            b_image.crop((0, b_image.height - vspace_reduction_pixels,
                          b_image.width, b_image.height)),
            (a_image.width, 0),
        )
        white_overlap = Image.new("RGB", top_overlap.size, "white")
        top_overlap_has_content = ImageChops.difference(
            top_overlap, white_overlap
        ).getbbox() is not None
        cd_top_strip = cd_image.crop((0, 0, cd_image.width, vspace_reduction_pixels))
        cd_top_has_content = ImageChops.difference(
            cd_top_strip, Image.new("RGB", cd_top_strip.size, "white")
        ).getbbox() is not None
        if top_overlap_has_content or cd_top_has_content:
            raise AssertionError("Requested row overlap would cover rendered content")
        combined_image = Image.new(
            "RGB",
            (top_png_width, a_image.height + cd_image.height - vspace_reduction_pixels),
            "white",
        )
        combined_image.paste(cd_image, (0, a_image.height - vspace_reduction_pixels))
        combined_image.paste(a_image, (0, 0))
        combined_image.paste(b_image, (a_image.width, 0))
        combined_image = combined_image.crop(
            (left_crop_pixels, 0, combined_image.width, combined_image.height)
        )
        combined_image.save(png_path, dpi=(DPI, DPI), optimize=True)
        png_dimensions = combined_image.size

    rendered = PdfReader(str(pdf_path))
    if len(rendered.pages) != 1:
        raise AssertionError("Combined vector PDF must have one page")
    rendered_page = rendered.pages[0]
    resources = rendered_page.get("/Resources") or {}
    if "/Font" not in resources:
        raise AssertionError("Combined PDF lost vector font resources")
    extracted_text = rendered_page.extract_text()
    if not all(f"{label}," in extracted_text for label in "abcd"):
        raise AssertionError("Combined PDF is missing one or more panel labels")

    checks = {
        "schema_version": "figure2-abcd-vector-checks-v1",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": "REPRODUCED",
        "analysis_scope": "native-vector composition of reproduced panel derivatives",
        "layout": "a-b above shared-axis c-d",
        "native_vector_pdf": True,
        "panel_pages_embedded_without_scaling": True,
        "panel_a_frozen_hashes_verified": True,
        "panel_a_source_modified": False,
        "panel_a_uses_aligned_visual_derivative": True,
        "panel_a_c_ytick_right_edges_aligned": True,
        "panel_a_c_label_left_edges_aligned": True,
        "panel_b_d_label_left_edges_aligned": True,
        "panel_a_c_ytick_alignment_error_points": a_alignment_checks[
            "ytick_alignment_error_points"
        ],
        "panel_a_c_label_alignment_error_points": a_alignment_checks[
            "panel_label_alignment_error_points"
        ],
        "panel_b_d_label_alignment_error_points": panel_b_d_label_error_points,
        "panel_a_and_b_page_heights_equal": True,
        "panel_b_to_a_width_ratio": b_width / a_width,
        "panel_b_is_two_thirds_panel_a": True,
        "top_and_bottom_page_widths_equal": True,
        "panels_c_d_generated_together": True,
        "panels_c_d_share_yaxis": True,
        "panel_d_repeated_city_labels_removed": True,
        "panel_c_d_city_order_matches": True,
        "city_order_sort_key": cd_check_values["city_order_sort_key"],
        "city_order_sort_description": cd_check_values["city_order_sort_description"],
        "city_order_sort_direction": "descending",
        "city_order_sorted_by_panel_d_observed_new_building_pv_area": True,
        "panel_a_dimensions_inches": [a_width / 72.0, a_height / 72.0],
        "panel_b_dimensions_inches": [b_width / 72.0, b_height / 72.0],
        "bottom_shared_dimensions_inches": [cd_width / 72.0, cd_height / 72.0],
        "source_combined_width_inches_before_left_crop": source_combined_width / 72.0,
        "combined_dimensions_inches": [combined_width / 72.0, combined_height / 72.0],
        "left_whitespace_crop_inches": left_crop_points / 72.0,
        "left_whitespace_crop_pixels_at_300_dpi": left_crop_pixels,
        "left_content_margin_inches": LEFT_CONTENT_MARGIN_IN,
        "left_content_margin_pixels_at_300_dpi": (
            source_leftmost_content_pixel - left_crop_pixels
        ),
        "left_crop_preserves_all_rendered_content": bool(
            left_crop_pixels <= source_leftmost_content_pixel
        ),
        "row_vspace_reduction_inches": VSPACE_REDUCTION_IN,
        "row_vspace_reduction_pixels_at_300_dpi": vspace_reduction_pixels,
        "row_overlap_strips_are_content_free": True,
        "combined_png_dimensions_pixels": list(png_dimensions),
        "png_uses_source_300_dpi_without_resampling": True,
        "pdf_page_count": 1,
        "pdf_font_resources_present": True,
        "pdf_extractable_text_character_count": len(extracted_text),
        "panel_labels_a_to_d_present": True,
        "per_panel_data_tables": {
            "a": str(a_data.resolve()),
            "b": str(b_data.resolve()),
            "c": str(c_data.resolve()),
            "d": str(d_data.resolve()),
        },
    }
    write_json(checks_path, checks)
    note_path.write_text(
        """# Figure 2a--d native-vector note

This is the native-vector Figure 2 release candidate. It follows the Figure 1
assembly pattern: equal-height standalone a and b PDF pages form the upper row,
with b two-thirds as wide as a. Panels c and d are first rendered together in
3:2 GridSpec columns and share a single city y-axis. Panel a uses a new visual
derivative whose y-tick-label right edge and panel-label left edge are aligned
to Panel c; its data remain the frozen revision-3 derivative. Panels c and d
are sorted in descending order by Panel d's observed new-building PV area per
newly observed building, with the pooled row retained last. The c--d canvas is
4.35 inches high (three-quarters of the previous 5.80-inch height). The upper
and lower pages overlap only 0.02 inch of verified content-free whitespace.
Excess whitespace to the left of the earliest rendered label is cropped while
retaining a 0.10-inch content margin; panel pages are translated without
scaling.

The companion PNG uses the corresponding 300-dpi sources without resampling.
Panel c intentionally uses a raster heatmap artist; all text, points, lines,
axes and pie wedges remain vector in the PDF. The four panel CSVs remain the
machine-readable numerical sources. Scientific evidence status: REPRODUCED.
""",
        encoding="utf-8",
    )
    caption_path.write_text(
        """**Newly observed buildings yield larger PV footprints and more PV area per risk unit, but inherited building-stock scale keeps most classified PV area on existing buildings.** (a) City-level and all-city comparisons of mean PV area among buildings with a first PV appearance and PV area averaged across all eligible observations; routes use their corresponding building and building–cohort denominators. (b) Vertically stacked pies show the same strict-classified first-appearance buildings weighted first by host count and then by attributed anchor PV area. (c) Existing/new ratios decompose total PV area into stock exposure, first-appearance intensity and event-footprint contributions. (d) Observed new-building PV area per newly observed building and the arithmetic level required to equal the existing-building route's total attributed PV area. Panels c and d are sorted by descending observed new-building PV area per newly observed building and end with a separately pooled `All cities` row. The upper Panel-d scale uses a nominal 0.20 kWdc m^-2 conversion and is not measured nameplate capacity. Results use full-AOI strict adjacent raw-known transitions and unique-building first-appearance attribution.
""",
        encoding="utf-8",
    )

    outputs = {}
    for path in [pdf_path, png_path, checks_path, note_path, caption_path]:
        outputs[path.name] = {
            "path": str(path.resolve()),
            "bytes": path.stat().st_size,
            "sha256": sha256_file(path),
        }
    inputs = [
        source_record(a_pdf, "aligned_panel_a_vector_pdf"),
        source_record(a_png, "aligned_panel_a_300dpi_png"),
        source_record(a_checks, "aligned_panel_a_checks"),
        source_record(a_manifest, "aligned_panel_a_manifest"),
        source_record(a_data, "frozen_panel_a_data"),
        source_record(frozen_a_pdf, "frozen_panel_a_vector_pdf"),
        source_record(frozen_a_png, "frozen_panel_a_300dpi_png"),
        source_record(frozen_a_checks, "frozen_panel_a_checks"),
        source_record(frozen_a_manifest, "frozen_panel_a_manifest"),
        source_record(a_freeze, "panel_a_freeze_manifest"),
        source_record(b_pdf, "panel_b_vector_pdf"),
        source_record(b_png, "panel_b_300dpi_png"),
        source_record(b_data, "panel_b_data"),
        source_record(b_checks, "panel_b_checks"),
        source_record(b_manifest, "panel_b_manifest"),
        source_record(cd_pdf, "panels_cd_shared_vector_pdf"),
        source_record(cd_png, "panels_cd_shared_300dpi_png"),
        source_record(cd_checks, "panels_cd_shared_checks"),
        source_record(cd_manifest, "panels_cd_shared_manifest"),
        source_record(c_data, "panel_c_data"),
        source_record(d_data, "panel_d_data"),
    ]
    write_json(
        manifest_path,
        {
            "schema_version": "figure2-abcd-vector-manifest-v1",
            "generated_at_utc": datetime.now(timezone.utc).isoformat(),
            "figure": "Figure 2 native-vector a--d composition",
            "script_path": str(Path(__file__).resolve()),
            "script_version": SCRIPT_VERSION,
            "script_sha256": sha256_file(Path(__file__).resolve()),
            "pypdf_version": pypdf.__version__,
            "inputs": inputs,
            "outputs": outputs,
            "status": "REPRODUCED",
            "analysis_scope": "native-vector composition of reproduced panel derivatives",
        },
    )


if __name__ == "__main__":
    main()
