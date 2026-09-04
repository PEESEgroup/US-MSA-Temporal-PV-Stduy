#!/usr/bin/env python3
"""Render Figure 1 panels b and c with one shared city axis."""

from __future__ import annotations

import argparse
import csv
from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib import font_manager
from matplotlib.lines import Line2D
from matplotlib.patches import Rectangle


ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
OUT = HERE / "output"
FONT = ROOT / "arial.ttf"
WIDTH = 9.1
HEIGHT = 4.0
BLUE = "#245f73"
GRAY = "#777772"
GRID = "#d8dddc"


def rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--width", type=float, default=WIDTH)
    parser.add_argument("--stem", default="figure1_panels_bc_shared")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    font_manager.fontManager.addfont(str(FONT))
    family = font_manager.FontProperties(fname=str(FONT)).get_name()
    plt.rcParams.update({
        "font.family": family, "text.color": "black", "axes.labelcolor": "black",
        "xtick.color": "black", "ytick.color": "black", "pdf.fonttype": 42,
        "ps.fonttype": 42, "savefig.bbox": None,
    })

    order_rows = rows(HERE / "output/figure1_panel_a_3x5_data.csv")
    position = {}
    names = {}
    for row in order_rows:
        position[row["city_id"]] = (int(row["grid_row"]), int(row["grid_column"]))
        names[row["city_id"]] = row["city_name"]
    cities = sorted(position, key=position.get)
    display = cities + ["all_cities_pooled"]
    ypos = {city: len(display) - 1 - i for i, city in enumerate(display)}

    b = {row["city_id"]: row for row in rows(OUT / "figure1_panel_b_initial_data.csv")}
    c_rows = rows(OUT / "figure1_panel_c_lag_data.csv")
    c_by_city = {city: [] for city in display}
    for row in c_rows:
        c_by_city[row["city_id"]].append(row)
    for city in display:
        c_by_city[city].sort(key=lambda row: float(row["lag_bin_start_years"]))
    global_peak = max(
        float(row["pv_area_share_of_all_resolved_percent"]) for row in c_rows
    )
    city_peaks = {
        city: max(
            float(row["pv_area_share_of_all_resolved_percent"])
            for row in c_by_city[city]
        )
        for city in display
    }

    fig = plt.figure(figsize=(args.width, HEIGHT))
    gs = fig.add_gridspec(1, 3, left=0.095, right=0.952, bottom=0.26, top=0.98,
                          width_ratios=[1, 1, 1], wspace=0.30)
    ax_b = fig.add_subplot(gs[0, 0])
    ax_comp = fig.add_subplot(gs[0, 1], sharey=ax_b)
    ax_lag = fig.add_subplot(gs[0, 2], sharey=ax_b)
    city_label_artists = {}

    def pair(ax, start, end, y, color, lw):
        ax.plot([start, end], [y, y], color=color, lw=lw, zorder=2)
        ax.scatter(start, y, s=8, facecolor="white", edgecolor=color, lw=0.6, zorder=3)
        ax.scatter(end, y, s=9, facecolor=color, edgecolor=color, lw=0.4, zorder=3)

    for city in display:
        y = ypos[city]
        r = b[city]
        area_values = (
            100 * float(r["building_area_postbaseline_share"]),
            100 * float(r["pv_area_postbaseline_share"]),
        )
        count_values = (
            100 * float(r["building_target_count_postbaseline_share"]),
            100 * float(r["pv_target_count_postbaseline_share"]),
        )
        pair(ax_b, *area_values, y + 0.15, BLUE, 0.9)
        pair(ax_b, *count_values, y - 0.15, GRAY, 0.55)
        if city == "all_cities_pooled":
            ax_b.text(area_values[0] - 1.8, y + 0.15, f"{area_values[0]:.1f}%",
                      ha="right", va="center", fontsize=5.2, color=BLUE)
            ax_b.text(area_values[1] + 1.8, y + 0.15, f"{area_values[1]:.1f}%",
                      ha="left", va="center", fontsize=5.2, color=BLUE)
            ax_b.text(count_values[0] - 1.8, y - 0.15, f"{count_values[0]:.1f}%",
                      ha="right", va="center", fontsize=5.2, color=GRAY)
            ax_b.text(count_values[1] + 1.8, y - 0.15, f"{count_values[1]:.1f}%",
                      ha="left", va="center", fontsize=5.2, color=GRAY)
        label = "All cities" if city == "all_cities_pooled" else names[city]
        city_label_artists[city] = ax_b.text(
            -4, y, label, ha="right", va="center", fontsize=7.0, clip_on=False
        )

        cr = c_by_city[city][0]
        components = [
            (float(cr["composition_left_censored_percent"]), "#d7d7d7", "#b9b9b9", "////"),
            (float(cr["composition_cohort_contemporaneous_percent"]), "#d47c60", "#d47c60", None),
            (float(cr["composition_between_cohort_percent"]), "#338579", "#338579", None),
        ]
        left = 0.0
        for value, face, edge, hatch in components:
            ax_comp.barh(y, value, left=left, height=0.34, color=face,
                         edgecolor=edge, hatch=hatch, linewidth=0.4)
            left += value
        left_censored = components[0][0]
        ax_comp.text(
            left_censored / 2, y, f"{left_censored:.1f}%",
            ha="center", va="center", fontsize=5.2, color="#555959",
        )

        xs = [float(row["lag_bin_start_years"]) for row in c_by_city[city]]
        shares = [float(row["pv_area_share_of_all_resolved_percent"]) for row in c_by_city[city]]
        ys = [y + 0.72 * value / global_peak for value in shares]
        ax_lag.fill_between(xs, y, ys, color=BLUE, alpha=0.12, linewidth=0)
        ax_lag.plot(xs, ys, color=BLUE, lw=0.85, marker="o", markersize=1.4,
                    markeredgewidth=0)

    for ax in (ax_b, ax_comp, ax_lag):
        ax.set_ylim(-0.55, len(display) + 0.05)
        ax.set_yticks([])
        ax.spines[["top", "right"]].set_visible(False)
        ax.spines["bottom"].set_color("black")
        ax.spines["bottom"].set_linewidth(0.55)
        ax.tick_params(axis="x", labelsize=6.5, length=2, width=0.5, pad=1.5)
    ax_b.spines["left"].set_visible(False)
    ax_b.set_xlim(-2, 102)
    ax_b.set_xticks([0, 25, 50, 75, 100], ["0", "25", "50", "75", "100%"])
    ax_b.set_xlabel("Share entering after baseline", fontsize=7.0, labelpad=3)
    ax_b.axvline(50, color="#eceeed", lw=0.6, zorder=0)

    ax_comp.spines["left"].set_visible(False)
    ax_comp.tick_params(axis="y", left=False)
    ax_comp.set_xlim(0, 100)
    ax_comp.set_xticks([0, 50, 100], ["0", "50", "100%"])
    ax_comp.set_xlabel("Composition", fontsize=7.0, labelpad=3)

    xmax = max(float(row["lag_bin_start_years"]) for row in c_rows)
    ax_lag.spines["left"].set_color("black")
    ax_lag.spines["left"].set_linewidth(0.55)
    # Every ridge uses the same vertical scale. For each city show only the
    # nonzero upper reference at that city's observed peak; omit zero baselines.
    ax_lag.set_yticks(
        [ypos[city] + 0.72 * city_peaks[city] / global_peak for city in display],
        labels=[f"{city_peaks[city]:.1f}%" for city in display],
    )
    ax_lag.tick_params(axis="y", left=True, right=False, length=2.2,
                       width=0.50, direction="out", colors="black",
                       labelsize=5.2, pad=1.8, labelleft=True)
    ax_b.tick_params(axis="y", left=False, right=False, labelleft=False)
    ax_comp.tick_params(axis="y", left=False, right=False, labelleft=False)
    ax_lag.set_xlim(0, xmax)
    ax_lag.set_xticks([0, 4, 8, 12])
    ax_lag.set_xlabel("Observed lag (years)", fontsize=7.0, labelpad=3)
    ax_lag.grid(axis="x", color=GRID, lw=0.45, linestyle=":")

    for ax in (ax_b, ax_comp, ax_lag):
        ax.axhline(0.50, color="black", lw=0.50, linestyle=(0, (2.2, 1.8)))
    fig.text(0.012, 0.98, "b,", ha="left", va="top", fontsize=9.5)
    ax_comp.text(-0.09, 1.0, "c,", transform=ax_comp.transAxes, ha="left", va="top",
                 fontsize=9.5, clip_on=False)
    ax_lag.text(-0.16, 1.0, "d,", transform=ax_lag.transAxes, ha="left", va="top",
                fontsize=9.5, clip_on=False)

    ax_b.legend(handles=[
        Line2D([0], [0], color=BLUE, lw=0.9, label="Area"),
        Line2D([0], [0], color=GRAY, lw=0.6, label="Count"),
        Line2D([0], [0], marker="o", ls="none", ms=3, mfc="black", mec="black", label="PV"),
        Line2D([0], [0], marker="o", ls="none", ms=3, mfc="white", mec="black", mew=0.6, label="Building"),
    ], loc="upper center", bbox_to_anchor=(0.5, -0.095), ncol=4, frameon=False,
       fontsize=5.5, handlelength=0.8, handletextpad=0.28, columnspacing=0.60,
       borderaxespad=0, labelspacing=0.15)

    ax_comp.legend(handles=[
        Rectangle((0, 0), 1, 1, fc="#d7d7d7", ec="#b9b9b9", hatch="////", label="Left-censored"),
        Rectangle((0, 0), 1, 1, fc="#d47c60", ec="#d47c60", label="Cohort-contemporaneous"),
        Rectangle((0, 0), 1, 1, fc="#338579", ec="#338579", label="Between-cohort"),
    ], loc="upper center", bbox_to_anchor=(0.5, -0.095), ncol=2, frameon=False,
       fontsize=5.2, handlelength=0.9, handleheight=0.55, handletextpad=0.30,
       columnspacing=0.85, borderaxespad=0, labelspacing=0.14)

    ax_lag.legend(handles=[
        Line2D([0], [0], color=BLUE, marker="o", ms=2.2, lw=0.8, label="Annual lag share"),
    ], loc="upper center", bbox_to_anchor=(0.5, -0.095), ncol=1, frameon=False,
       fontsize=5.5, handlelength=1.0, handletextpad=0.32, borderaxespad=0)

    # Align the true rendered left edge of the longest city label with Panel a's
    # figure-left anchor. Move labels only; preserve all three equal-width axes.
    fig.canvas.draw()
    renderer = fig.canvas.get_renderer()
    washington = city_label_artists["washington_dc"]
    washington_left = washington.get_window_extent(renderer=renderer).x0
    target_left = 0.012 * fig.bbox.width
    anchor_x_px = ax_b.transData.transform((-4.0, 0.0))[0]
    aligned_anchor_x = ax_b.transData.inverted().transform(
        (anchor_x_px + target_left - washington_left, 0.0)
    )[0]
    for artist in city_label_artists.values():
        artist.set_x(aligned_anchor_x)
    fig.canvas.draw()
    aligned_left = washington.get_window_extent(renderer=fig.canvas.get_renderer()).x0
    if abs(aligned_left - target_left) > 0.5:
        raise RuntimeError(
            f"Washington DC left edge did not align: {aligned_left} vs {target_left} px"
        )

    OUT.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT / f"{args.stem}.png", dpi=300, facecolor="white")
    fig.savefig(OUT / f"{args.stem}.pdf", facecolor="white")
    plt.close(fig)


if __name__ == "__main__":
    main()
