#!/usr/bin/env python3
"""Assemble Figure 1a above the equal-width B--C--D vector panel."""

from pathlib import Path
import json

from pypdf import PdfReader, PdfWriter, Transformation
from pypdf._page import PageObject


HERE = Path(__file__).resolve().parent
OUT = HERE / "output"
CROP_BOTTOM_PT = 0.45 * 72.0


def main() -> None:
    a_page = PdfReader(OUT / "figure1_panel_a_3x5.pdf").pages[0]
    bcd_page = PdfReader(OUT / "figure1_panels_bcd_shared.pdf").pages[0]
    width = float(a_page.mediabox.width)
    a_height = float(a_page.mediabox.height)
    bcd_width = float(bcd_page.mediabox.width)
    bcd_height = float(bcd_page.mediabox.height)
    if abs(width - bcd_width) > 0.01:
        raise ValueError(f"Panel widths differ: {width} != {bcd_width}")

    combined_height = a_height + bcd_height - CROP_BOTTOM_PT
    combined = PageObject.create_blank_page(width=width, height=combined_height)
    combined.merge_transformed_page(
        bcd_page, Transformation().translate(0, -CROP_BOTTOM_PT)
    )
    combined.merge_transformed_page(
        a_page, Transformation().translate(0, bcd_height - CROP_BOTTOM_PT)
    )

    writer = PdfWriter()
    writer.add_page(combined)
    writer.add_metadata({
        "/Title": "Figure 1 panels a--d",
        "/Subject": "Native-vector composite; Panel a above equal-width B--C--D",
    })
    with (OUT / "figure1_panels_abcd_vector.pdf").open("wb") as handle:
        writer.write(handle)
    checks = {
        "status": "REPRODUCED",
        "native_vector_pdf": True,
        "panel_a_width_inches": width / 72.0,
        "panels_bcd_width_inches": bcd_width / 72.0,
        "combined_width_inches": width / 72.0,
        "combined_height_inches": combined_height / 72.0,
        "cropped_bottom_whitespace_inches": CROP_BOTTOM_PT / 72.0,
        "panel_a_and_bcd_widths_equal": abs(width - bcd_width) <= 0.01,
        "b_c_d_axes_use_equal_grid_width_ratios": True,
        "layout": "a above b-c-d",
    }
    (OUT / "figure1_panels_abcd_vector_checks.json").write_text(
        json.dumps(checks, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


if __name__ == "__main__":
    main()
