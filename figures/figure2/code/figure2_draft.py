#!/usr/bin/env python3
"""Render the four-panel Figure 2 draft and its traceable derivatives."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from datetime import datetime, timezone
from pathlib import Path

import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np
from matplotlib import font_manager
from matplotlib.colors import LinearSegmentedColormap, TwoSlopeNorm
from matplotlib.lines import Line2D


SCRIPT_VERSION = "0.8.7"
NEW = "#c97c5d"
EXISTING = "#2f7f6f"
COUNT = "#9b9994"
TEXT = "#222222"
MUTED = "#5f6363"
LIGHT = "#d9dddc"

CITY_NAMES = {
    "atlanta": "Atlanta",
    "boston": "Boston",
    "charlotte": "Charlotte",
    "chicago": "Chicago",
    "dallas": "Dallas",
    "denver": "Denver",
    "detroit": "Detroit",
    "los_angeles": "Los Angeles",
    "miami": "Miami",
    "minneapolis": "Minneapolis",
    "new_york_city": "New York City",
    "philadelphia": "Philadelphia",
    "phoenix": "Phoenix",
    "seattle": "Seattle",
    "washington_dc": "Washington DC",
    "all_cities_pooled": "Pooled",
}

CITY_ABBREVIATIONS = {
    "atlanta": "ATL",
    "boston": "BOS",
    "charlotte": "CLT",
    "chicago": "CHI",
    "dallas": "DAL",
    "denver": "DEN",
    "detroit": "DET",
    "los_angeles": "LA",
    "miami": "MIA",
    "minneapolis": "MSP",
    "new_york_city": "NYC",
    "philadelphia": "PHL",
    "phoenix": "PHX",
    "seattle": "SEA",
    "washington_dc": "DC",
}

PANEL_FIELDS = [
    "panel", "city_id", "display_order", "metric", "route", "value", "unit",
    "denominator", "ratio", "ratio_definition", "share", "log2_contribution",
    "x_value", "y_value", "x_unit", "y_unit", "status", "note",
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
    parser.add_argument("--output-dir", type=Path, default=figure_dir / "draft_v1")
    return parser.parse_args()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as stream:
        return list(csv.DictReader(stream))


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=PANEL_FIELDS)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key, "") for key in PANEL_FIELDS})


def write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def f(row: dict[str, str], field: str) -> float:
    return float(row[field])


def i(row: dict[str, str], field: str) -> int:
    return int(float(row[field]))


def almost_equal(left: float, right: float, tolerance: float = 1e-10) -> bool:
    return math.isclose(left, right, rel_tol=tolerance, abs_tol=tolerance)


def source_record(path: Path, role: str, row_count: int | None = None) -> dict[str, object]:
    record: dict[str, object] = {
        "path": str(path.resolve()), "role": role, "bytes": path.stat().st_size,
        "sha256": sha256_file(path),
    }
    if row_count is not None:
        record["row_count"] = row_count
    return record


def panel_label(ax: plt.Axes, label: str, x: float = -0.12, y: float = 1.08) -> None:
    ax.text(
        x, y, f"{label},", transform=ax.transAxes, ha="left", va="bottom",
        fontsize=9.5, fontweight="normal", color=TEXT, clip_on=False,
    )


def ratio_label(value: float) -> str:
    return f"{value:.1f}×" if value >= 10 else f"{value:.2f}×"


def configure_style(style_path: Path, font_path: Path) -> str:
    if not style_path.exists():
        raise FileNotFoundError(style_path)
    if not font_path.exists():
        raise FileNotFoundError(font_path)
    plt.style.use(style_path)
    font_manager.fontManager.addfont(str(font_path))
    font_name = font_manager.FontProperties(fname=str(font_path)).get_name()
    mpl.rcParams.update({
        "font.family": font_name,
        "font.sans-serif": [font_name],
        "savefig.bbox": None,
        "axes.unicode_minus": False,
    })
    return font_name


def draw_panel_a(
    ax: plt.Axes,
    city_rows: list[dict[str, str]],
    pooled: dict[str, str],
) -> None:
    label_offsets = [(3, 3), (3, -4), (-3, 3), (-3, -4)]
    label_offset_overrides = {
        "new_york_city": (3, -4),
        "atlanta": (3, -4),
        "minneapolis": (3, -4),
    }
    for city_index, row in enumerate(city_rows):
        existing_x_city = f(row, "mean_pv_area_per_retrofit_event_m2")
        existing_y_city = f(row, "pv_area_yield_retrofit_m2_per_stock_exposure")
        new_x_city = f(row, "mean_pv_area_per_new_event_m2")
        new_y_city = f(row, "pv_area_yield_new_m2_per_new_building")
        ax.plot(
            [existing_x_city, new_x_city],
            [existing_y_city, new_y_city],
            color=COUNT,
            lw=0.75,
            alpha=0.42,
            zorder=1,
        )
        ax.scatter(
            existing_x_city,
            existing_y_city,
            s=25,
            marker="o",
            facecolor=EXISTING,
            edgecolor="none",
            alpha=0.30,
            zorder=2,
        )
        ax.scatter(
            new_x_city,
            new_y_city,
            s=25,
            marker="s",
            facecolor=NEW,
            edgecolor="none",
            alpha=0.30,
            zorder=2,
        )
        x_offset, y_offset = label_offset_overrides.get(
            row["city_id"], label_offsets[city_index % len(label_offsets)]
        )
        ax.annotate(
            CITY_ABBREVIATIONS[row["city_id"]],
            (new_x_city, new_y_city),
            xytext=(x_offset, y_offset),
            textcoords="offset points",
            ha="left" if x_offset > 0 else "right",
            va="bottom" if y_offset > 0 else "top",
            fontsize=6.2,
            color=MUTED,
            alpha=0.88,
            zorder=4,
        )

    existing_x = f(pooled, "mean_pv_area_per_retrofit_event_m2")
    existing_y = f(pooled, "pv_area_yield_retrofit_m2_per_stock_exposure")
    new_x = f(pooled, "mean_pv_area_per_new_event_m2")
    new_y = f(pooled, "pv_area_yield_new_m2_per_new_building")
    ax.plot([existing_x, new_x], [existing_y, new_y], color="#000000", lw=1.25, zorder=3)
    ax.scatter(
        existing_x, existing_y, s=86, marker="o", color=EXISTING,
        edgecolor="white", linewidth=0.9, zorder=5,
    )
    ax.scatter(
        new_x, new_y, s=91, marker="s", color=NEW,
        edgecolor="white", linewidth=0.9, zorder=5,
    )
    guide_style = (0, (3.0, 2.2))
    for x_value, y_value, route_color in [
        (existing_x, existing_y, EXISTING),
        (new_x, new_y, NEW),
    ]:
        ax.plot(
            [25, x_value], [y_value, y_value], color=route_color,
            lw=1.0, linestyle=guide_style, alpha=1.0, zorder=3,
        )
        ax.plot(
            [x_value, x_value], [0.025, y_value], color=route_color,
            lw=1.0, linestyle=guide_style, alpha=1.0, zorder=3,
        )
    ax.annotate(
        f"{existing_y:.3f} m²",
        (26.3, existing_y), xytext=(0, -4), textcoords="offset points",
        ha="left", va="top", fontsize=6.6, color=EXISTING,
    )
    ax.annotate(
        f"{new_y:.3f} m²",
        (26.3, new_y), xytext=(0, 4), textcoords="offset points",
        ha="left", va="bottom", fontsize=6.6, color=NEW,
    )
    ax.annotate(
        f"{existing_x:.1f} m²",
        (existing_x, 0.027), xytext=(3, 2), textcoords="offset points",
        ha="left", va="bottom", fontsize=6.6, color=EXISTING,
    )
    ax.annotate(
        f"{new_x:.1f} m²",
        (new_x, 0.027), xytext=(3, 2), textcoords="offset points",
        ha="left", va="bottom", fontsize=6.6, color=NEW,
    )
    ax.annotate(
        "all-city",
        (existing_x, existing_y), xytext=(4, -5), textcoords="offset points",
        ha="left", va="top", fontsize=6.8, color=EXISTING,
    )
    ax.annotate(
        "all-city",
        (new_x, new_y), xytext=(4, 4), textcoords="offset points",
        ha="left", va="bottom", fontsize=6.8, color=NEW,
    )
    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.set_xlim(25, 450)
    ax.set_ylim(0.025, 8)
    ax.set_xticks([30, 50, 100, 200, 400], ["30", "50", "100", "200", "400"])
    ax.set_yticks(
        [0.03, 0.05, 0.1, 0.2, 0.5, 1, 2, 5],
        ["0.03", "0.05", "0.1", "0.2", "0.5", "1", "2", "5"],
    )
    ax.xaxis.set_minor_formatter(mpl.ticker.NullFormatter())
    ax.yaxis.set_minor_formatter(mpl.ticker.NullFormatter())
    ax.tick_params(
        axis="both",
        which="major",
        colors="#000000",
        labelcolor="#000000",
        length=3.5,
        width=0.7,
        direction="out",
    )
    ax.tick_params(
        axis="both",
        which="minor",
        colors="#000000",
        length=2.0,
        width=0.5,
        direction="out",
    )
    for spine_name in ["left", "bottom"]:
        ax.spines[spine_name].set_color("#000000")
        ax.spines[spine_name].set_linewidth(0.7)
        ax.spines[spine_name].set_linestyle("solid")
    ax.set_xlabel("mean PV area among buildings with a first PV appearance (m²; log scale)")
    ax.set_ylabel("mean PV area among all building observations (m²; log scale)")
    legend_handles = [
        Line2D(
            [], [], linestyle="none", marker="o", markersize=7.0,
            markerfacecolor=EXISTING, markeredgecolor="none",
            label="existing building",
        ),
        Line2D(
            [], [], linestyle="none", marker="s", markersize=7.0,
            markerfacecolor=NEW, markeredgecolor="none",
            label="new building",
        ),
    ]
    ax.legend(
        handles=legend_handles,
        loc="upper center",
        bbox_to_anchor=(0.5, 0.995),
        ncol=2,
        frameon=False,
        fontsize=8.8,
        handletextpad=0.35,
        columnspacing=1.1,
        borderaxespad=0.0,
    )
    ax.grid(True, which="major")
    ax.grid(True, which="minor", linewidth=0.35, alpha=0.55)
    panel_label(ax, "a", x=-0.13, y=1.02)


def draw_panel_b(ax: plt.Axes, pooled: dict[str, str]) -> None:
    event_new = i(pooled, "y_new")
    event_existing = i(pooled, "y_retrofit")
    area_new = f(pooled, "pv_area_new_m2")
    area_existing = f(pooled, "pv_area_retrofit_m2")
    rows = [
        (1.0, "Strict-event hosts", event_new, event_existing,
         f"{event_new:,}", f"{event_existing:,}"),
        (0.0, "Anchor PV area", area_new, area_existing,
         f"{area_new / 1e6:.3f} km²", f"{area_existing / 1e6:.3f} km²"),
    ]
    for y, _, new_value, existing_value, new_label, existing_label in rows:
        total = new_value + existing_value
        new_share = new_value / total
        existing_share = existing_value / total
        ax.barh(y, new_share, height=0.29, color=NEW, edgecolor="white", linewidth=0.5)
        ax.barh(
            y, existing_share, left=new_share, height=0.29, color=EXISTING,
            edgecolor="white", linewidth=0.5,
        )
        ax.text(
            new_share + 0.018, y + 0.23,
            f"new {new_label} ({new_share * 100:.1f}%)",
            ha="left", va="bottom", fontsize=6.7, color=NEW,
        )
        ax.plot(
            [new_share / 2, new_share + 0.012], [y + 0.14, y + 0.21],
            color=NEW, lw=0.65, clip_on=False,
        )
        ax.text(
            new_share + existing_share / 2, y,
            f"existing {existing_label}\n{existing_share * 100:.1f}%",
            ha="center", va="center", fontsize=6.7, color="white", linespacing=1.05,
        )
    total_area = f(pooled, "pv_area_total_classified_m2")
    nominal = f(pooled, "nominal_capacity_total_mwdc_equivalent")
    low = f(pooled, "capacity_total_low_mwdc_equivalent")
    high = f(pooled, "capacity_total_high_mwdc_equivalent")
    ax.text(
        0.5, -0.55,
        (f"{total_area / 1e6:.3f} km² = {nominal / 1000:.3f} GWdc-equivalent\n"
         f"scenario range {low / 1000:.3f}–{high / 1000:.3f} GWdc-equivalent"),
        ha="center", va="top", fontsize=6.7, color=MUTED, linespacing=1.25,
    )
    ax.set_xlim(0, 1)
    ax.set_ylim(-0.92, 1.48)
    ax.set_yticks([1, 0], [row[1] for row in rows])
    ax.set_xticks([0, 0.5, 1], ["0", "50", "100"])
    ax.set_xlabel("Route share (%)")
    ax.grid(axis="x")
    ax.grid(axis="y", visible=False)
    ax.tick_params(axis="y", length=0, pad=4)
    ax.spines["left"].set_visible(False)
    panel_label(ax, "b", x=-0.19)


def draw_panel_c(ax: plt.Axes, city_rows: list[dict[str, str]], pooled: dict[str, str]) -> None:
    ordered = sorted(
        city_rows, key=lambda row: f(row, "area_yield_rr_new_to_retrofit"),
        reverse=True,
    )
    display = ordered + [pooled]
    ratios: list[list[float]] = []
    residuals: list[float] = []
    for row in display:
        ratios.append([
            f(row, "stock_multiplier"),
            f(row, "r_retrofit_event_per_building_cohort")
            / f(row, "r_new_event_per_building"),
            f(row, "event_size_ratio_retrofit_to_new"),
            f(row, "area_retrofit_to_new_ratio"),
        ])
        residuals.append(f(row, "three_factor_decomposition_residual"))
    log_values = np.log2(np.asarray(ratios, dtype=float))
    cmap = LinearSegmentedColormap.from_list(
        "new_neutral_existing", [NEW, "#ffffff", EXISTING], N=256
    )
    norm = TwoSlopeNorm(vmin=-3.0, vcenter=0.0, vmax=6.0)
    image = ax.imshow(log_values, cmap=cmap, norm=norm, aspect="auto", interpolation="none")
    for row_index, ratio_row in enumerate(ratios):
        for column_index, ratio in enumerate(ratio_row):
            color = "white" if abs(log_values[row_index, column_index]) > 2.25 else TEXT
            ax.text(
                column_index, row_index, ratio_label(ratio), ha="center", va="center",
                fontsize=6.1, color=color,
            )
    qa_x = 4.18
    ax.scatter([qa_x] * len(display), range(len(display)), s=8, color=COUNT, zorder=4)
    ax.axhline(len(ordered) - 0.5, color=TEXT, lw=0.8)
    ax.axvline(3.5, color=LIGHT, lw=0.7)
    ax.set_xlim(-0.5, 4.45)
    ax.set_yticks(range(len(display)), [CITY_NAMES[row["city_id"]] for row in display])
    ax.set_xticks(
        [0, 1, 2, 3, qa_x],
        ["Stock\nexposure", "Event\nintensity", "Event\nfootprint", "Total\nPV area", "QA"],
    )
    ax.tick_params(axis="both", length=0)
    ax.xaxis.tick_top()
    ax.xaxis.set_label_position("top")
    ax.grid(False)
    for spine in ax.spines.values():
        spine.set_visible(False)
    ax.set_xlabel("Cell labels are existing/new ratios", labelpad=7)
    panel_label(ax, "c", x=-0.25, y=1.04)
    colorbar_axis = ax.inset_axes([0.0, -0.16, 1.0, 0.045])
    colorbar = ax.figure.colorbar(
        image, cax=colorbar_axis, orientation="horizontal", ticks=[-3, 0, 3, 6]
    )
    colorbar.set_label(
        "signed log2 contribution   new route ← 0 → existing route", fontsize=7.0
    )
    colorbar.ax.tick_params(labelsize=6.5, length=2)
    colorbar.outline.set_linewidth(0.5)
    if max(abs(value) for value in residuals) >= 1e-12:
        raise AssertionError("Three-factor residual exceeds the plotting gate")


def draw_panel_d(
    ax: plt.Axes,
    city_rows: list[dict[str, str]],
    pooled: dict[str, str],
    nominal_density: float,
) -> None:
    ordered = sorted(
        city_rows, key=lambda row: f(row, "area_yield_rr_new_to_retrofit"),
        reverse=True,
    )
    display = ordered + [pooled]
    for row_index, row in enumerate(display):
        observed = f(row, "pv_area_yield_new_m2_per_new_building")
        required = f(row, "pv_area_retrofit_m2") / f(row, "n_new")
        ax.plot([observed, required], [row_index, row_index], color=LIGHT, lw=1.25, zorder=1)
        ax.scatter(observed, row_index, s=27, marker="s", color=NEW, zorder=3)
        ax.scatter(required, row_index, s=27, marker="o", color=EXISTING, zorder=3)
    pooled_y = len(display) - 1
    pooled_observed = f(pooled, "pv_area_yield_new_m2_per_new_building")
    pooled_required = f(pooled, "pv_area_retrofit_m2") / f(pooled, "n_new")
    ax.axhline(len(ordered) - 0.5, color=TEXT, lw=0.8)
    ax.annotate(
        f"new {pooled_observed:.2f}", (pooled_observed, pooled_y),
        xytext=(0, -10), textcoords="offset points", ha="center", va="top",
        fontsize=6.6, color=NEW,
    )
    ax.annotate(
        f"parity {pooled_required:.1f}", (pooled_required, pooled_y),
        xytext=(0, -10), textcoords="offset points", ha="center", va="top",
        fontsize=6.6, color=EXISTING,
    )
    ax.set_xscale("log")
    ax.set_xlim(0.08, 160)
    ax.set_ylim(len(display) - 0.5, -0.5)
    ax.set_yticks([])
    ax.set_xlabel("PV area per newly observed Building (m²; log scale)")
    ax.grid(axis="x")
    ax.grid(axis="y", visible=False)
    ax.spines["left"].set_visible(False)
    upper = ax.secondary_xaxis(
        "top",
        functions=(lambda value: value * nominal_density, lambda value: value / nominal_density),
    )
    upper.set_xlabel("Nominal kWdc-equivalent per newly observed Building")
    upper.tick_params(labelsize=6.6)
    panel_label(ax, "d", x=-0.09, y=1.04)


def build_panel_rows(
    pooled: dict[str, str], city_order: list[dict[str, str]],
    display_order: dict[str, int],
) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    footprint_ratio = (
        f(pooled, "mean_pv_area_per_new_event_m2")
        / f(pooled, "mean_pv_area_per_retrofit_event_m2")
    )
    yield_ratio = f(pooled, "area_yield_rr_new_to_retrofit")
    for row in city_order + [pooled]:
        is_pooled = row["city_id"] == "all_cities_pooled"
        for route, x_value, y_value, y_unit, y_denominator in [
            (
                "new_building",
                f(row, "mean_pv_area_per_new_event_m2"),
                f(row, "pv_area_yield_new_m2_per_new_building"),
                "m2_per_newly_observed_building",
                "newly observed Building",
            ),
            (
                "existing_building",
                f(row, "mean_pv_area_per_retrofit_event_m2"),
                f(row, "pv_area_yield_retrofit_m2_per_stock_exposure"),
                "m2_per_existing_building_cohort_observation",
                "eligible existing-Building cohort observation",
            ),
        ]:
            rows.append({
                "panel": "a", "city_id": row["city_id"],
                "display_order": display_order[row["city_id"]],
                "metric": "event_footprint_vs_area_yield", "route": route,
                "x_value": x_value, "y_value": y_value,
                "x_unit": "m2_per_first_event_host", "y_unit": y_unit,
                "denominator": y_denominator,
                "ratio": footprint_ratio if is_pooled else "",
                "ratio_definition": "pooled_new_over_existing_footprint; pooled area-yield ratio stored in note" if is_pooled else "",
                "status": "REPRODUCED",
                "note": f"pooled_new_over_existing_area_yield={yield_ratio}" if is_pooled else "city background point",
            })
    for metric, new_value, existing_value, unit in [
        ("strict_event_host_count", i(pooled, "y_new"), i(pooled, "y_retrofit"), "hosts"),
        ("strict_classified_anchor_pv_area", f(pooled, "pv_area_new_m2"),
         f(pooled, "pv_area_retrofit_m2"), "m2"),
    ]:
        total = new_value + existing_value
        for route, value in [("new_building", new_value), ("existing_building", existing_value)]:
            rows.append({
                "panel": "b", "city_id": "all_cities_pooled",
                "display_order": 1 if metric.startswith("strict_event") else 2,
                "metric": metric, "route": route, "value": value, "unit": unit,
                "denominator": "pooled strict-classified route total",
                "share": value / total, "status": "REPRODUCED",
            })
    for row in city_order + [pooled]:
        factors = [
            ("stock_exposure", f(row, "stock_multiplier")),
            ("event_intensity", f(row, "r_retrofit_event_per_building_cohort")
             / f(row, "r_new_event_per_building")),
            ("event_footprint", f(row, "event_size_ratio_retrofit_to_new")),
            ("total_pv_area", f(row, "area_retrofit_to_new_ratio")),
        ]
        for metric, ratio in factors:
            rows.append({
                "panel": "c", "city_id": row["city_id"],
                "display_order": display_order[row["city_id"]], "metric": metric,
                "route": "existing_building_over_new_building", "ratio": ratio,
                "ratio_definition": "existing_building_over_new_building",
                "log2_contribution": math.log2(ratio), "status": "REPRODUCED",
            })
        rows.append({
            "panel": "c", "city_id": row["city_id"],
            "display_order": display_order[row["city_id"]],
            "metric": "three_factor_residual",
            "value": f(row, "three_factor_decomposition_residual"),
            "unit": "natural_log_residual", "status": "REPRODUCED",
            "note": "QA-only rail; not color-mapped as a result.",
        })
    for row in city_order + [pooled]:
        observed = f(row, "pv_area_yield_new_m2_per_new_building")
        required = f(row, "pv_area_retrofit_m2") / f(row, "n_new")
        for metric, value, note in [
            ("observed_new_route_area_yield", observed, "Observed strict new-route area."),
            ("new_route_area_yield_required_for_total_area_parity", required,
             "Arithmetic only; not roof potential, eligibility, a forecast or a policy effect."),
        ]:
            rows.append({
                "panel": "d", "city_id": row["city_id"],
                "display_order": display_order[row["city_id"]],
                "metric": metric, "route": "new_building", "value": value,
                "unit": "m2_per_newly_observed_building",
                "denominator": "newly observed Buildings in the same city or pooled scope",
                "ratio": required / observed,
                "ratio_definition": "parity_required_over_observed_new_route_yield",
                "status": "REPRODUCED", "note": note,
            })
    return rows


def main() -> None:
    args = parse_args()
    data_dir = args.data_dir.resolve()
    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    area_path = data_dir / "city_area_weighted_stock_flow.csv"
    capacity_path = data_dir / "pv_area_capacity_density_scenarios.csv"
    count_path = data_dir / "city_stock_flow_decomposition.csv"
    manifest_path = data_dir / "area_weighted_results_manifest.json"
    upstream_checks_path = data_dir / "area_weighted_results_checks.json"
    required_paths = [
        area_path, capacity_path, count_path, manifest_path, upstream_checks_path,
        args.style, args.font,
    ]
    for path in required_paths:
        if not path.exists():
            raise FileNotFoundError(path)

    area_rows = read_csv(area_path)
    capacity_rows = read_csv(capacity_path)
    count_rows = read_csv(count_path)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    upstream_checks = json.loads(upstream_checks_path.read_text(encoding="utf-8"))
    if sha256_file(area_path) != manifest["outputs"]["city_area_weighted_stock_flow"]["sha256"]:
        raise AssertionError("Area stock-flow table hash does not match its manifest")
    if sha256_file(capacity_path) != manifest["outputs"]["pv_area_capacity_density_scenarios"]["sha256"]:
        raise AssertionError("Capacity scenario table hash does not match its manifest")

    full_rows = [row for row in area_rows if row["scope"] == "full_aoi"]
    pooled = next(row for row in full_rows if row["city_id"] == "all_cities_pooled")
    city_rows = [row for row in full_rows if row["city_id"] != "all_cities_pooled"]
    if len(city_rows) != 15:
        raise AssertionError(f"Expected 15 cities, found {len(city_rows)}")
    count_lookup = {(row["city_id"], row["scope"]): row for row in count_rows}
    for row in full_rows:
        comparator = count_lookup[(row["city_id"], row["scope"])]
        for field in ["n_new", "y_new", "n_stock", "y_retrofit"]:
            if i(row, field) != i(comparator, field):
                raise AssertionError(f"Count mismatch for {row['city_id']} {field}")
        if not almost_equal(
            f(row, "pv_area_total_classified_m2"),
            f(row, "pv_area_new_m2") + f(row, "pv_area_retrofit_m2"),
        ):
            raise AssertionError(f"Area identity failed for {row['city_id']}")

    nominal_density = next(
        float(row["power_density_kwdc_per_m2"]) for row in capacity_rows
        if row["scenario_id"] == "nominal_display_density"
    )
    low_density = min(float(row["power_density_kwdc_per_m2"]) for row in capacity_rows)
    high_density = max(float(row["power_density_kwdc_per_m2"]) for row in capacity_rows)
    if not almost_equal(
        f(pooled, "pv_area_total_classified_m2") * nominal_density / 1000,
        f(pooled, "nominal_capacity_total_mwdc_equivalent"),
    ):
        raise AssertionError("Nominal capacity translation failed")

    city_order = sorted(
        city_rows, key=lambda row: f(row, "area_yield_rr_new_to_retrofit"),
        reverse=True,
    )
    display_order = {row["city_id"]: index + 1 for index, row in enumerate(city_order)}
    display_order["all_cities_pooled"] = len(city_order) + 1
    panel_rows = build_panel_rows(pooled, city_order, display_order)

    font_name = configure_style(args.style, args.font)
    figure = plt.figure(figsize=(9.1, 7.8), facecolor="white")
    grid = figure.add_gridspec(
        2, 2, width_ratios=[1.43, 1.0], height_ratios=[0.78, 1.72],
        left=0.115, right=0.985, top=0.955, bottom=0.085,
        wspace=0.35, hspace=0.48,
    )
    ax_a = figure.add_subplot(grid[0, 0])
    ax_b = figure.add_subplot(grid[0, 1])
    ax_c = figure.add_subplot(grid[1, 0])
    ax_d = figure.add_subplot(grid[1, 1])
    draw_panel_a(ax_a, city_rows, pooled)
    draw_panel_b(ax_b, pooled)
    draw_panel_c(ax_c, city_rows, pooled)
    draw_panel_d(ax_d, city_rows, pooled, nominal_density)
    for artist in figure.findobj(match=lambda item: hasattr(item, "set_fontfamily")):
        try:
            artist.set_fontfamily(font_name)
        except (AttributeError, TypeError):
            pass

    png_path = output_dir / "figure2_draft_v1.png"
    pdf_path = output_dir / "figure2_draft_v1.pdf"
    data_path = output_dir / "figure2_panel_data.csv"
    checks_path = output_dir / "figure2_checks.json"
    note_path = output_dir / "figure2_note.md"
    caption_path = output_dir / "figure2_caption.md"
    output_manifest_path = output_dir / "figure2_manifest.json"
    figure.savefig(png_path, dpi=300, facecolor="white")
    figure.savefig(pdf_path, facecolor="white")
    plt.close(figure)
    write_csv(data_path, panel_rows)

    max_residual = max(abs(f(row, "three_factor_decomposition_residual")) for row in full_rows)
    footprint_ratio = (
        f(pooled, "mean_pv_area_per_new_event_m2")
        / f(pooled, "mean_pv_area_per_retrofit_event_m2")
    )
    observed = f(pooled, "pv_area_yield_new_m2_per_new_building")
    required = f(pooled, "pv_area_retrofit_m2") / f(pooled, "n_new")
    checks = {
        "schema_version": "figure2-checks-v1",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": "REPRODUCED descriptive",
        "source_hashes_verified": True,
        "source_row_counts": {
            "city_area_weighted_stock_flow": len(area_rows),
            "pv_area_capacity_density_scenarios": len(capacity_rows),
            "city_stock_flow_decomposition": len(count_rows),
        },
        "full_aoi_city_count": len(city_rows),
        "risk_counts_reproduce_count_table": True,
        "area_total_equals_new_plus_existing_all_full_aoi_rows": True,
        "maximum_absolute_three_factor_log_residual": max_residual,
        "three_factor_identity_within_1e_12": max_residual < 1e-12,
        "upstream_source_pv_polygon_ids_unique_within_city": upstream_checks[
            "source_pv_polygon_ids_unique_within_each_city"
        ],
        "upstream_resolved_target_area_reconciles_to_unique_host_area": upstream_checks[
            "resolved_target_area_reconciles_to_unique_host_area"
        ],
        "upstream_host_area_attributed_to_first_strict_event_not_time_resolved_expansion": upstream_checks[
            "host_area_attributed_to_first_strict_event_not_time_resolved_expansion"
        ],
        "upstream_generator_rejects_nonpositive_unique_host_area": True,
        "all_full_aoi_route_event_counts_and_areas_positive": all(
            i(row, "y_new") > 0
            and i(row, "y_retrofit") > 0
            and f(row, "pv_area_new_m2") > 0
            and f(row, "pv_area_retrofit_m2") > 0
            for row in full_rows
        ),
        "capacity_is_scenario_not_measured_nameplate": True,
        "nominal_density_kwdc_per_m2": nominal_density,
        "density_range_kwdc_per_m2": [low_density, high_density],
        "capacity_equivalent_share_equals_area_share": True,
        "city_order_rule": "descending full-AOI PV-area-yield ratio, pooled row last",
        "city_order": [row["city_id"] for row in city_order],
        "pooled_values": {
            "new_to_existing_mean_event_footprint_ratio": footprint_ratio,
            "new_to_existing_area_yield_ratio": f(pooled, "area_yield_rr_new_to_retrofit"),
            "existing_to_new_stock_multiplier": f(pooled, "stock_multiplier"),
            "existing_to_new_total_area_ratio": f(pooled, "area_retrofit_to_new_ratio"),
            "existing_route_area_share": f(pooled, "retrofit_share_of_classified_pv_area"),
            "existing_route_event_share": f(pooled, "retrofit_share_of_classified_event_count"),
            "observed_new_area_yield_m2_per_new_building": observed,
            "parity_required_m2_per_new_building": required,
            "parity_required_over_observed": required / observed,
        },
        "panel_c_and_d_city_order_identical": True,
        "panel_d_is_arithmetic_not_roof_utilization_or_forecast": True,
    }
    write_json(checks_path, checks)

    note = f"""# Figure 2 draft v1 note

## Estimand

Full-AOI strict raw-known adjacent risk rows compare newly observed Buildings
with eligible existing-Building cohort exposures. A PV event is the first
accepted adjacent A-to-P transition on a unique linked host. All resolved source
PV target union areas on that host are summed once and the anchor-year area is
attributed to the host's first strict event; later within-host expansion is not
time-resolved.

Panel a reports two distinct pooled contrasts: mean anchor PV area per strict
event host and PV-area yield per route-specific risk unit. Their denominators
must not be interchanged. Panel b partitions strict-event hosts and their
classified anchor PV area. Panel c uses existing/new ratios; the three signed
log components sum to the observed total-area ratio, and the pooled row is
count/area-summed descriptive arithmetic. Panel d uses the same city order and
divides each city's observed existing-route area by its observed number of
newly observed Buildings, followed by the separately pooled row. It is an
arithmetic parity frontier, not roof utilization, a capacity-potential estimate,
eligibility assumption, forecast or policy effect.

## Capacity-equivalent translation

The primary observable is PV polygon-union area. The nominal secondary scale is
{nominal_density:.2f} kWdc m^-2, bracketed by {low_density:.3f}-{high_density:.3f}
kWdc m^-2. These are transparent DC-capacity-equivalent scenarios; the inventory
contains no measured nameplate field.

## Scope and status

The target population is anchor-surviving PV and Buildings observed in the
full Anchor AOI candidate scope. The results are not a citywide historical
adoption rate. Cohorts are opaque ordered observations, not years. Unknown
states are not converted to absence and are not bridged. Status: REPRODUCED
descriptive.
"""
    note_path.write_text(note, encoding="utf-8")
    caption = """**Newly observed Buildings yield larger PV footprints and more PV area per risk unit, but the inherited Building stock still carries most PV area.** **a,** Pooled full-AOI comparisons show mean anchor PV area per strict event host and PV-area yield per route-specific risk unit; newly observed Buildings and existing-Building cohort exposures are distinct denominators. **b,** Strict-event hosts and classified anchor PV area are partitioned between new- and existing-Building routes. The displayed capacity translation is DC-capacity-equivalent under declared constant-density scenarios, not measured nameplate capacity. **c,** Existing/new ratios decompose each city's observed PV-area ratio exactly into stock exposure, event intensity and mean event-host footprint; the pooled row is separately count/area-summed. Color represents signed log2 contribution, and the neutral QA rail records decomposition residuals. **d,** In the same city order and a separately pooled row, observed new-route PV-area yield is compared with the arithmetic yield required for each new-Building denominator to equal observed existing-route area. This is not roof utilization, a forecast, a policy effect or a capacity-potential estimate. All panels use strict adjacent raw-known transitions, unique-host first-event attribution and anchor-surviving full-AOI inventories; cohort steps are ordered observations rather than years.
"""
    caption_path.write_text(caption, encoding="utf-8")

    inputs = [
        source_record(area_path, "primary_full_aoi_area_stock_flow", len(area_rows)),
        source_record(capacity_path, "capacity_equivalent_scenarios", len(capacity_rows)),
        source_record(count_path, "risk_count_reconciliation", len(count_rows)),
        source_record(manifest_path, "owning_area_results_manifest"),
        source_record(upstream_checks_path, "owning_area_results_checks"),
        source_record(args.style.resolve(), "shared_matplotlib_style"),
        source_record(args.font.resolve(), "font"),
    ]
    outputs = {}
    for path in [png_path, pdf_path, data_path, checks_path, note_path, caption_path]:
        outputs[path.name] = {
            "path": str(path.resolve()), "bytes": path.stat().st_size,
            "sha256": sha256_file(path),
        }
    output_manifest = {
        "schema_version": "figure2-manifest-v1",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "figure": "Figure 2 draft v1",
        "script_path": str(Path(__file__).resolve()),
        "script_version": SCRIPT_VERSION,
        "script_sha256": sha256_file(Path(__file__).resolve()),
        "canvas_inches": [9.1, 7.8],
        "font_family": font_name,
        "inputs": inputs,
        "outputs": outputs,
        "status": "REPRODUCED descriptive",
    }
    write_json(output_manifest_path, output_manifest)


if __name__ == "__main__":
    main()
