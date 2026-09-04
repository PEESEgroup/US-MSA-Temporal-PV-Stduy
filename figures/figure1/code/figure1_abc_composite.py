#!/usr/bin/env python3
"""Assemble the current Figure 1a and shared-axis b--c renderings."""

from pathlib import Path

from PIL import Image


HERE = Path(__file__).resolve().parent
OUT = HERE / "output"
CROP_BOTTOM_IN = 0.45


def main() -> None:
    panel_a = Image.open(OUT / "figure1_panel_a_3x5.png").convert("RGB")
    panels_bc = Image.open(OUT / "figure1_panels_bc_shared_wide.png").convert("RGB")
    if panel_a.width != panels_bc.width:
        raise ValueError(f"Panel widths differ: {panel_a.width} != {panels_bc.width}")
    canvas = Image.new("RGB", (panel_a.width, panel_a.height + panels_bc.height), "white")
    canvas.paste(panel_a, (0, 0))
    canvas.paste(panels_bc, (0, panel_a.height))
    crop_px = round(CROP_BOTTOM_IN * 300)
    canvas = canvas.crop((0, 0, canvas.width, canvas.height - crop_px))
    canvas.save(OUT / "figure1_panels_abc.png", dpi=(300, 300))
    canvas.save(OUT / "figure1_panels_abc.pdf", resolution=300.0)
    canvas.save(OUT / "figure1_panels_abcd.png", dpi=(300, 300))


if __name__ == "__main__":
    main()
