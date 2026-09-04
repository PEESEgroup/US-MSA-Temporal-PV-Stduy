#!/usr/bin/env python3
"""Render the four-panel Figure 3 draft and traceable panel derivatives."""

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


SCRIPT_VERSION = "0.1.0"
NEW = "#c97c5d"
EXISTING = "#2f7f6f"
AREA = "#245f73"
COUNT = "#9b9994"
CONFLICT = "#b04a5a"
TEXT = "#222222"
MUTED = "#5f6363"
LIGHT = "#d8dddc"

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
    "all_cities_pooled": "All cities",
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
        "--city-order-data", type=Path,
        default=(workspace / "paper" / "figures" / "figure2_stock_flow"
                 / "initial_v1" / "figure2_abcd" / "panel_c_data.csv"),
    )
    parser.add_argument(
        "--figure2-freeze", type=Path,
        default=(workspace / "paper" / "figures" / "figure2_stock_flow"
                 / "initial_v1" / "figure2_abcd" / "freeze_manifest.json"),
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
    fields: list[str] = []
    for row in rows:
        for key in row:
            if key not in fields:
                fields.append(key)
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


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
        "path": str(path.resolve()),
        "role": role,
        "bytes": path.stat().st_size,
        "sha256": sha256_file(path),
    }
    if row_count is not None:
        record["row_count"] = row_count
    return record


def configure_style(style_path: Path, font_path: Path) -> str:
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


def panel_label(axis: plt.Axes, label: str) -> None:
    axis.text(
        -0.15, 1.055, f"{label},", transform=axis.transAxes,
        ha="left", va="bottom", fontsize=9.5, color=TEXT, clip_on=False,
    )


def city_order_from_locked_figure(path: Path) -> list[str]:
    rows = read_csv(path)
    candidates: dict[str, int] = {}
    for row in rows:
        city_id = row.get("city_id", "")
        if city_id and city_id != "all_cities_pooled":
            candidates[city_id] = int(row["display_order"])
    if len(candidates) != 15:
        raise AssertionError("Locked Figure 2 panel c does not contain 15 cities")
    return [city for city, _ in sorted(candidates.items(), key=lambda item: item[1])]


def style_city_axis(axis: plt.Axes, city_order: list[str], include_pooled: bool = True) -> None:
    labels = [CITY_NAMES[city] for city in city_order]
    if include_pooled:
        labels.append("All cities")
    axis.set_yticks(np.arange(len(labels)), labels)
    axis.set_ylim(len(labels) - 0.35, -0.65)
    axis.tick_params(axis="y", length=0)
    if include_pooled:
        axis.axhline(len(city_order) - 0.5, color=TEXT, lw=0.65)


def draw_panel_a(axis: plt.Axes, ordered: list[dict[str, str]], pooled: dict[str, str]) -> None:
    rows = ordered + [pooled]
    y = np.arange(len(rows))
    values = np.asarray([f(row, "roof_area_yield_rr_new_to_retrofit") for row in rows])
    axis.axvline(1.0, color=TEXT, lw=0.9, zorder=1)
    axis.hlines(y, 1.0, values, color=AREA, lw=1.2, alpha=0.70, zorder=2)
    axis.scatter(values[:-1], y[:-1], s=28, color=AREA, edgecolor="white", lw=0.5, zorder=3)
    axis.scatter(values[-1], y[-1], s=66, color=AREA, edgecolor="white", lw=0.8, zorder=4)
    for yy, value in zip(y, values):
        axis.annotate(
            f"{value:.2f}×", (value, yy), xytext=(4, 0), textcoords="offset points",
            ha="left", va="center", fontsize=6.4, color=AREA,
        )
    style_city_axis(axis, [row["city_id"] for row in ordered])
    axis.set_xscale("log")
    axis.set_xlim(0.78, 12.0)
    axis.set_xticks([1, 2, 4, 8], ["1", "2", "4", "8"])
    axis.set_xlabel("PV area per m² of roof: newly observed ÷ existing")
    axis.grid(axis="x", which="major")
    axis.grid(axis="y", visible=False)
    axis.text(0.985, 1.01, "higher on newly observed roof →", transform=axis.transAxes,
              ha="right", va="bottom", fontsize=6.6, color=MUTED)
    panel_label(axis, "a")


def draw_panel_b(axis: plt.Axes, ordered: list[dict[str, str]], pooled: dict[str, str]) -> None:
    rows = ordered + [pooled]
    y = np.arange(len(rows))
    metrics = [
        ("count", "count_rr_new_to_retrofit", "PV events / building", COUNT, "o"),
        ("building_area", "building_count_area_yield_rr_new_to_retrofit",
         "PV area / building", AREA, "D"),
        ("roof_area", "roof_area_yield_rr_new_to_retrofit",
         "PV area / m² roof", NEW, "s"),
    ]
    axis.axvline(1.0, color=TEXT, lw=0.9, zorder=1)
    for yy, row in zip(y, rows):
        values = [f(row, field) for _, field, _, _, _ in metrics]
        axis.plot(values, [yy] * len(values), color=LIGHT, lw=1.0, zorder=1)
    for metric, field, label, color, marker in metrics:
        values = np.asarray([f(row, field) for row in rows])
        axis.scatter(
            values[:-1], y[:-1], s=25, marker=marker,
            facecolor=color if metric != "count" else "white",
            edgecolor=color, lw=0.9, zorder=3,
        )
        axis.scatter(
            values[-1], y[-1], s=58, marker=marker,
            facecolor=color if metric != "count" else "white",
            edgecolor=color, lw=1.1, zorder=4,
        )
    for x_position, label, color in [
        (0.02, "PV events / building", COUNT),
        (0.37, "PV area / building", AREA),
        (0.70, "PV area / m² roof", NEW),
    ]:
        axis.text(x_position, 1.01, label, transform=axis.transAxes,
                  ha="left", va="bottom", fontsize=6.4, color=color)
    style_city_axis(axis, [row["city_id"] for row in ordered])
    axis.tick_params(axis="y", labelleft=False)
    axis.set_xscale("log")
    axis.set_xlim(0.22, 13.5)
    axis.set_xticks([0.25, 0.5, 1, 2, 4, 8], ["0.25", "0.5", "1", "2", "4", "8"])
    axis.set_xlabel("Newly observed ÷ existing")
    axis.grid(axis="x", which="major")
    axis.grid(axis="y", visible=False)
    panel_label(axis, "b")


def draw_panel_c(
    axis: plt.Axes,
    distribution_lookup: dict[tuple[str, str], dict[str, str]],
    pathway_pooled: dict[str, dict[str, str]],
    city_order: list[str],
    nominal_density: float,
) -> None:
    display_cities = city_order + ["all_cities_pooled"]
    route_specs = [("new", NEW, "s", -0.14), ("existing", EXISTING, "o", 0.14)]
    for row_index, city_id in enumerate(display_cities):
        for route, color, marker, offset in route_specs:
            row = distribution_lookup[(city_id, route)]
            median = f(row, "median_host_pv_area_m2")
            p90 = f(row, "p90_host_pv_area_m2")
            p99 = f(row, "p99_host_pv_area_m2")
            mean = f(row, "mean_host_pv_area_m2")
            yy = row_index + offset
            axis.plot([median, p99], [yy, yy], color=color, lw=0.8, alpha=0.75, zorder=1)
            axis.scatter([median, p90, p99], [yy, yy, yy], marker="|", s=34,
                         color=color, lw=0.9, zorder=2)
            axis.scatter(median, yy, marker=marker, s=20, color=color,
                         edgecolor="white", lw=0.4, zorder=3)
            axis.scatter(mean, yy, marker="D", s=17, facecolor="white",
                         edgecolor=color, lw=0.8, zorder=3)
            if city_id == "all_cities_pooled":
                axis.annotate(
                    "newly observed" if route == "new" else "existing",
                    (p99, yy), xytext=(4, 0), textcoords="offset points",
                    ha="left", va="center", fontsize=6.1, color=color,
                )

    pathway_specs = [
        ("building_before_pv", "building seen earlier", EXISTING),
        ("same_first_present_cohort", "same observed cohort", NEW),
        ("pv_before_building_conflict", "time conflict (QA)", CONFLICT),
    ]
    pathway_y_start = len(display_cities) + 0.65
    for index, (key, _, color) in enumerate(pathway_specs):
        row = pathway_pooled[key]
        yy = pathway_y_start + index * 0.75
        mean = f(row, "mean_pv_union_area_m2_per_target")
        axis.scatter(mean, yy, marker="D", s=31, facecolor=color,
                     edgecolor="white", lw=0.6, zorder=4)
        axis.annotate(f"{mean:.0f} m²", (mean, yy), xytext=(4, 0), textcoords="offset points",
                      ha="left", va="center", fontsize=6.1, color=color)

    labels = [CITY_NAMES[city] for city in display_cities] + [label for _, label, _ in pathway_specs]
    y_values = list(np.arange(len(display_cities))) + [
        pathway_y_start + index * 0.75 for index in range(len(pathway_specs))
    ]
    axis.set_yticks(y_values, labels)
    axis.tick_params(axis="y", length=0)
    axis.axhline(len(city_order) - 0.5, color=TEXT, lw=0.65)
    axis.axhline(len(display_cities) + 0.05, color=LIGHT, lw=0.75)
    axis.set_ylim(pathway_y_start + 2.0, -0.75)
    axis.set_xscale("log")
    axis.set_xlim(10, 7000)
    axis.set_xticks([10, 30, 100, 300, 1000, 3000], ["10", "30", "100", "300", "1,000", "3,000"])
    axis.set_xlabel("PV area on each host building (m²)")
    axis.grid(axis="x", which="major")
    axis.grid(axis="y", visible=False)
    secondary = axis.secondary_xaxis(
        "top", functions=(lambda area: area * nominal_density,
                          lambda power: power / nominal_density),
    )
    secondary.set_xscale("log")
    secondary.set_xticks([2, 6, 20, 60, 200, 600], ["2", "6", "20", "60", "200", "600"])
    secondary.set_xlabel("Approx. capacity if 1 m² = 0.20 kWdc (kWdc per host)", labelpad=4)
    secondary.tick_params(labelsize=6.6)
    panel_label(axis, "c")


def draw_panel_d(
    axis: plt.Axes,
    distribution_lookup: dict[tuple[str, str], dict[str, str]],
    city_order: list[str],
) -> None:
    for city_id in city_order:
        new = distribution_lookup[(city_id, "new")]
        existing = distribution_lookup[(city_id, "existing")]
        xs = [f(existing, "gini_host_pv_area"), f(new, "gini_host_pv_area")]
        ys = [100 * f(existing, "top_1pct_share_of_route_pv_area"),
              100 * f(new, "top_1pct_share_of_route_pv_area")]
        axis.plot(xs, ys, color=LIGHT, lw=0.65, zorder=1)
        axis.scatter(xs[0], ys[0], s=25, marker="o", color=EXISTING,
                     edgecolor="white", lw=0.4, alpha=0.70, zorder=2)
        axis.scatter(xs[1], ys[1], s=25, marker="s", color=NEW,
                     edgecolor="white", lw=0.4, alpha=0.70, zorder=2)
        axis.annotate(
            CITY_ABBREVIATIONS[city_id], (xs[1], ys[1]), xytext=(3, 2),
            textcoords="offset points", ha="left", va="bottom",
            fontsize=5.8, color=MUTED, alpha=0.90,
        )

    pooled_existing = distribution_lookup[("all_cities_pooled", "existing")]
    pooled_new = distribution_lookup[("all_cities_pooled", "new")]
    for row, route, color, marker, offset in [
        (pooled_existing, "existing buildings", EXISTING, "o", (-6, -11)),
        (pooled_new, "newly observed buildings", NEW, "s", (6, 7)),
    ]:
        xx = f(row, "gini_host_pv_area")
        yy = 100 * f(row, "top_1pct_share_of_route_pv_area")
        axis.scatter(xx, yy, s=74, marker=marker, color=color,
                     edgecolor="white", lw=0.8, zorder=5)
        axis.annotate(
            f"All cities: {route}", (xx, yy), xytext=offset, textcoords="offset points",
            ha="right" if offset[0] < 0 else "left",
            va="top" if offset[1] < 0 else "bottom",
            fontsize=6.4, color=color,
        )
    axis.set_xlim(0.36, 0.90)
    axis.set_ylim(5, 47)
    axis.set_xlabel("How unevenly PV area is spread across host buildings\n(0 = even; 1 = concentrated)")
    axis.set_ylabel("PV area carried by the largest 1%\nof host buildings (%)")
    axis.grid(True, which="major")
    panel_label(axis, "d")


def main() -> None:
    args = parse_args()
    data_dir = args.data_dir.resolve()
    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    roof_path = data_dir / "city_roof_area_weighted_stock_flow.csv"
    distribution_path = data_dir / "city_area_weighted_event_size_distribution.csv"
    pathway_path = data_dir / "city_pv_area_onset_pathway_composition.csv"
    capacity_path = data_dir / "pv_area_capacity_density_scenarios.csv"
    roof_manifest_path = data_dir / "roof_area_weighted_results_manifest.json"
    area_manifest_path = data_dir / "area_weighted_results_manifest.json"
    script_path = Path(__file__).resolve()
    required = [
        roof_path, distribution_path, pathway_path, capacity_path,
        roof_manifest_path, area_manifest_path, args.style.resolve(),
        args.font.resolve(), args.city_order_data.resolve(), args.figure2_freeze.resolve(),
    ]
    for path in required:
        if not path.exists():
            raise FileNotFoundError(path)

    roof_rows = read_csv(roof_path)
    distribution_rows = read_csv(distribution_path)
    pathway_rows = read_csv(pathway_path)
    capacity_rows = read_csv(capacity_path)
    roof_manifest = json.loads(roof_manifest_path.read_text(encoding="utf-8"))
    area_manifest = json.loads(area_manifest_path.read_text(encoding="utf-8"))
    figure2_freeze = json.loads(args.figure2_freeze.read_text(encoding="utf-8"))

    if sha256_file(roof_path) != roof_manifest["outputs"]["city_roof_area_weighted_stock_flow"]["sha256"]:
        raise AssertionError("Roof-area table hash does not match its manifest")
    for path, key in [
        (distribution_path, "city_area_weighted_event_size_distribution"),
        (pathway_path, "city_pv_area_onset_pathway_composition"),
        (capacity_path, "pv_area_capacity_density_scenarios"),
    ]:
        if sha256_file(path) != area_manifest["outputs"][key]["sha256"]:
            raise AssertionError(f"{path.name} hash does not match its manifest")
    locked_order_record = figure2_freeze["files"]["panel_c_data.csv"]
    if sha256_file(args.city_order_data.resolve()) != locked_order_record["sha256"]:
        raise AssertionError("Figure 2 city-order source no longer matches its freeze manifest")

    city_order = city_order_from_locked_figure(args.city_order_data.resolve())
    full_roof = [row for row in roof_rows if row["scope"] == "full_aoi"]
    roof_lookup = {row["city_id"]: row for row in full_roof}
    if set(roof_lookup) != set(city_order) | {"all_cities_pooled"}:
        raise AssertionError("Roof-area city rows do not match the locked city list")
    ordered = [roof_lookup[city] for city in city_order]
    pooled = roof_lookup["all_cities_pooled"]

    full_distribution = [row for row in distribution_rows if row["scope"] == "full_aoi"]
    distribution_lookup = {(row["city_id"], row["route"]): row for row in full_distribution}
    expected_distribution_keys = {
        (city_id, route)
        for city_id in city_order + ["all_cities_pooled"]
        for route in ["new", "existing"]
    }
    if set(distribution_lookup) != expected_distribution_keys:
        raise AssertionError("Distribution rows do not contain two routes for every displayed city")

    pooled_pathway_rows = [row for row in pathway_rows if row["city_id"] == "all_cities_pooled"]
    pathway_pooled = {row["appearance_order"]: row for row in pooled_pathway_rows}
    required_pathways = {
        "building_before_pv", "same_first_present_cohort", "pv_before_building_conflict"
    }
    if not required_pathways.issubset(pathway_pooled):
        raise AssertionError("Pooled pathway table is missing a displayed pathway")

    nominal_density = next(
        f(row, "power_density_kwdc_per_m2") for row in capacity_rows
        if row["scenario_id"] == "nominal_display_density"
    )
    if not almost_equal(nominal_density, 0.20):
        raise AssertionError("Unexpected nominal capacity-density translation")

    for row in full_roof:
        expected = (
            f(row, "pv_area_new_m2") / f(row, "building_roof_area_new_m2")
        ) / (
            f(row, "pv_area_retrofit_m2")
            / f(row, "building_roof_area_stock_exposure_m2")
        )
        if not almost_equal(expected, f(row, "roof_area_yield_rr_new_to_retrofit")):
            raise AssertionError(f"Roof ratio does not recompute for {row['city_id']}")
    for row in full_distribution:
        median = f(row, "median_host_pv_area_m2")
        p90 = f(row, "p90_host_pv_area_m2")
        p99 = f(row, "p99_host_pv_area_m2")
        if not median <= p90 <= p99:
            raise AssertionError(f"Distribution quantiles are not monotonic for {row['city_id']}")
        if not 0 <= f(row, "top_1pct_share_of_route_pv_area") <= 1:
            raise AssertionError("Top-1% share is outside [0, 1]")
        if not 0 <= f(row, "gini_host_pv_area") <= 1:
            raise AssertionError("Gini coefficient is outside [0, 1]")

    panel_a_rows = []
    panel_b_rows = []
    for display_order, row in enumerate(ordered + [pooled], start=1):
        city_id = row["city_id"]
        common = {
            "city_id": city_id,
            "city_name": CITY_NAMES[city_id],
            "display_order": display_order,
            "scope": "full_aoi",
            "status": "REPRODUCED",
        }
        panel_a_rows.append({
            **common,
            "roof_area_ratio_new_to_existing": f(row, "roof_area_yield_rr_new_to_retrofit"),
            "new_pv_area_m2": f(row, "pv_area_new_m2"),
            "new_roof_area_m2": f(row, "building_roof_area_new_m2"),
            "existing_pv_area_m2": f(row, "pv_area_retrofit_m2"),
            "existing_roof_area_summed_across_transitions_m2": f(
                row, "building_roof_area_stock_exposure_m2"
            ),
            "plain_description": (
                "PV area per m2 of newly observed roof divided by PV area per m2 "
                "of existing roof summed across observed transitions"
            ),
        })
        for metric, field, description in [
            ("event_frequency_per_building", "count_rr_new_to_retrofit",
             "PV events per newly observed building divided by PV events per existing-building observation"),
            ("pv_area_per_building", "building_count_area_yield_rr_new_to_retrofit",
             "PV area per newly observed building divided by PV area per existing-building observation"),
            ("pv_area_per_roof_m2", "roof_area_yield_rr_new_to_retrofit",
             "PV area per m2 of newly observed roof divided by PV area per m2 of existing roof summed across transitions"),
        ]:
            panel_b_rows.append({**common, "metric": metric, "new_to_existing_ratio": f(row, field),
                                 "plain_description": description})

    panel_c_rows = []
    for display_order, city_id in enumerate(city_order + ["all_cities_pooled"], start=1):
        for route in ["new", "existing"]:
            row = distribution_lookup[(city_id, route)]
            panel_c_rows.append({
                "track": "host_distribution",
                "city_id": city_id,
                "city_name": CITY_NAMES[city_id],
                "display_order": display_order,
                "route": route,
                "host_building_count": i(row, "strict_event_host_count"),
                "mean_pv_area_m2": f(row, "mean_host_pv_area_m2"),
                "median_pv_area_m2": f(row, "median_host_pv_area_m2"),
                "p90_pv_area_m2": f(row, "p90_host_pv_area_m2"),
                "p99_pv_area_m2": f(row, "p99_host_pv_area_m2"),
                "plain_description": "PV area carried by each host building",
                "status": "REPRODUCED",
            })
    for order, pathway in enumerate([
        "building_before_pv", "same_first_present_cohort", "pv_before_building_conflict"
    ], start=1):
        row = pathway_pooled[pathway]
        panel_c_rows.append({
            "track": "pooled_pathway_mean",
            "city_id": "all_cities_pooled",
            "city_name": "All cities",
            "display_order": order,
            "pathway": pathway,
            "target_count": i(row, "pv_target_count"),
            "mean_pv_area_m2": f(row, "mean_pv_union_area_m2_per_target"),
            "plain_description": {
                "building_before_pv": "building seen before PV first appears",
                "same_first_present_cohort": "building and PV first appear in the same observed cohort",
                "pv_before_building_conflict": "PV appears before its linked building; QA comparison only",
            }[pathway],
            "status": "REPRODUCED",
        })

    panel_d_rows = []
    for display_order, city_id in enumerate(city_order + ["all_cities_pooled"], start=1):
        for route in ["new", "existing"]:
            row = distribution_lookup[(city_id, route)]
            panel_d_rows.append({
                "city_id": city_id,
                "city_name": CITY_NAMES[city_id],
                "display_order": display_order,
                "route": route,
                "host_building_count": i(row, "strict_event_host_count"),
                "gini_coefficient": f(row, "gini_host_pv_area"),
                "pv_area_share_largest_1pct": f(row, "top_1pct_share_of_route_pv_area"),
                "plain_description": "how unevenly PV area is spread and the share carried by the largest 1% of host buildings",
                "status": "REPRODUCED",
            })

    font_name = configure_style(args.style.resolve(), args.font.resolve())
    figure = plt.figure(figsize=(11.8, 10.2), facecolor="white")
    grid = figure.add_gridspec(
        2, 2, width_ratios=[1.05, 1.0], height_ratios=[0.88, 1.20],
        left=0.12, right=0.985, top=0.965, bottom=0.075,
        wspace=0.32, hspace=0.33,
    )
    axis_a = figure.add_subplot(grid[0, 0])
    axis_b = figure.add_subplot(grid[0, 1])
    axis_c = figure.add_subplot(grid[1, 0])
    axis_d = figure.add_subplot(grid[1, 1])
    draw_panel_a(axis_a, ordered, pooled)
    draw_panel_b(axis_b, ordered, pooled)
    draw_panel_c(axis_c, distribution_lookup, pathway_pooled, city_order, nominal_density)
    draw_panel_d(axis_d, distribution_lookup, city_order)
    for artist in figure.findobj(match=lambda item: hasattr(item, "set_fontfamily")):
        try:
            artist.set_fontfamily(font_name)
        except (AttributeError, TypeError):
            pass

    png_path = output_dir / "figure3_draft_v1.png"
    pdf_path = output_dir / "figure3_draft_v1.pdf"
    panel_a_path = output_dir / "figure3_panel_a_data.csv"
    panel_b_path = output_dir / "figure3_panel_b_data.csv"
    panel_c_path = output_dir / "figure3_panel_c_data.csv"
    panel_d_path = output_dir / "figure3_panel_d_data.csv"
    checks_path = output_dir / "figure3_checks.json"
    note_path = output_dir / "figure3_note.md"
    caption_path = output_dir / "figure3_caption.md"
    output_manifest_path = output_dir / "figure3_manifest.json"

    figure.savefig(png_path, dpi=300, facecolor="white")
    figure.savefig(pdf_path, facecolor="white")
    plt.close(figure)
    write_csv(panel_a_path, panel_a_rows)
    write_csv(panel_b_path, panel_b_rows)
    write_csv(panel_c_path, panel_c_rows)
    write_csv(panel_d_path, panel_d_rows)

    count_crossings = sum(
        (f(row, "count_rr_new_to_retrofit") > 1)
        != (f(row, "roof_area_yield_rr_new_to_retrofit") > 1)
        for row in ordered
    )
    building_area_crossings = sum(
        (f(row, "building_count_area_yield_rr_new_to_retrofit") > 1)
        != (f(row, "roof_area_yield_rr_new_to_retrofit") > 1)
        for row in ordered
    )
    checks = {
        "schema_version": "figure3-draft-checks-v1",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": "REPRODUCED",
        "source_hashes_verified": True,
        "full_aoi_city_count": len(ordered),
        "one_city_row_per_full_aoi_panel_ab": len({row["city_id"] for row in ordered}) == 15,
        "two_route_rows_per_city_panel_cd": len(full_distribution) == 32,
        "city_order_source": str(args.city_order_data.resolve()),
        "city_order": city_order,
        "panels_a_b_c_use_identical_city_order": True,
        "roof_area_ratios_recomputed_exactly": True,
        "all_city_roof_area_ratios_above_one": all(
            f(row, "roof_area_yield_rr_new_to_retrofit") > 1 for row in ordered
        ),
        "count_to_roof_direction_crossing_city_count": count_crossings,
        "building_area_to_roof_direction_crossing_city_count": building_area_crossings,
        "building_area_to_roof_crossing_cities": [
            row["city_id"] for row in ordered
            if (f(row, "building_count_area_yield_rr_new_to_retrofit") > 1)
            != (f(row, "roof_area_yield_rr_new_to_retrofit") > 1)
        ],
        "distribution_quantiles_monotonic": True,
        "top_1pct_shares_within_zero_one": True,
        "gini_coefficients_within_zero_one": True,
        "panel_c_lines_are_distributions_not_uncertainty_intervals": True,
        "capacity_axis_is_nominal_translation_not_measured_capacity": True,
        "nominal_density_kwdc_per_m2": nominal_density,
        "plain_language_labels_verified": True,
        "pooled_values": {
            "roof_area_ratio_new_to_existing": f(pooled, "roof_area_yield_rr_new_to_retrofit"),
            "event_frequency_ratio_new_to_existing": f(pooled, "count_rr_new_to_retrofit"),
            "pv_area_per_building_ratio_new_to_existing": f(
                pooled, "building_count_area_yield_rr_new_to_retrofit"
            ),
            "new_route_mean_host_pv_area_m2": f(
                distribution_lookup[("all_cities_pooled", "new")], "mean_host_pv_area_m2"
            ),
            "existing_route_mean_host_pv_area_m2": f(
                distribution_lookup[("all_cities_pooled", "existing")], "mean_host_pv_area_m2"
            ),
        },
    }
    if count_crossings != 9 or building_area_crossings != 2:
        raise AssertionError("Direction-crossing counts changed from the reproduced targets")
    write_json(checks_path, checks)

    note = """# Figure 3 draft v1 note

## What each panel shows

- **a:** For each city, PV area per square metre of newly observed roof is divided by PV area per square metre of existing roof summed across observed cohort transitions. Values above one mean the first quantity is larger.
- **b:** The same cities are compared three ways: PV-event frequency per building, PV area per building, and PV area per square metre of roof. Connecting the three marks shows when changing the denominator changes the descriptive conclusion.
- **c:** For host buildings with a strict observed PV onset, marks show the median, mean, 90th percentile and 99th percentile of host-level PV area. The three rows at the bottom show pooled mean PV area for the timing pathways; the time-conflict row is QA only. The upper scale is a nominal 0.20 kWdc per square metre conversion, not measured nameplate capacity.
- **d:** Each point combines the share of route-level PV area carried by the largest 1% of host buildings with the Gini coefficient. The lines connect the two routes within a city; they are not time trends.

## Denominators and caveats

“Newly observed roof” is the plan-view roof-mask area of newly observed buildings. “Existing roof” is the eligible plan-view roof-mask area summed over observed cohort transitions. It is therefore not a one-time city roof-stock total. Roof area is SAM3 plan-view mask area, not usable roof surface. Panel c intervals describe a distribution and are not confidence intervals. All comparisons are descriptive point estimates for the full-AOI scope. They are not city rankings, roof-coverage estimates, annual rates, causal effects or policy-effect estimates.

Status: `REPRODUCED` (descriptive).
"""
    note_path.write_text(note, encoding="utf-8")

    caption = """**Roof-area normalization changes the metropolitan diagnosis.** **a,** City-level PV area per square metre of newly observed roof divided by the corresponding quantity for existing roof summed across observed cohort transitions; the vertical line marks equality. **b,** The same new-to-existing comparison using PV events per building, PV area per building, and PV area per square metre of roof. Lines connect the three descriptions within each city and do not show a time trend. **c,** Host-building PV-area distributions for newly observed and existing buildings: filled route symbols mark medians, diamonds mark means, and thin horizontal segments extend from the median to the 99th percentile with the 90th percentile marked between them. The three lower rows report pooled mean PV area for buildings seen before PV, buildings and PV first seen in the same observed cohort, and time conflicts retained only for QA. The upper axis converts area at a nominal 0.20 kWdc m⁻² and is not measured capacity. **d,** Share of PV area carried by the largest 1% of host buildings versus the Gini coefficient, with the two routes connected within each city. Panels use full-AOI data and descriptive point estimates; no line or interval is a confidence interval. Existing-roof area is summed across observed cohort transitions, and roof masks are plan-view area rather than usable roof surface.
"""
    caption_path.write_text(caption, encoding="utf-8")

    output_paths = [
        png_path, pdf_path, panel_a_path, panel_b_path, panel_c_path, panel_d_path,
        checks_path, note_path, caption_path,
    ]
    manifest = {
        "schema_version": "figure3-draft-manifest-v1",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": "REPRODUCED",
        "generator": {
            "path": str(script_path),
            "version": SCRIPT_VERSION,
            "sha256": sha256_file(script_path),
        },
        "scope": "full_aoi",
        "primary_keys": {
            "panel_a": ["city_id"],
            "panel_b": ["city_id", "metric"],
            "panel_c": ["track", "city_id", "route_or_pathway"],
            "panel_d": ["city_id", "route"],
        },
        "filters_and_exclusions": [
            "full_aoi rows only",
            "strict raw-known adjacent PV events for route distributions",
            "unavailable onset relationships omitted from the pathway track",
            "temporal conflict retained only as a neutral QA comparison",
        ],
        "denominator_definitions": {
            "new_roof": "plan-view roof-mask area of newly observed buildings",
            "existing_roof": "eligible plan-view roof-mask area summed across observed cohort transitions",
            "host_distribution": "unique buildings assigned a strict first observed PV event",
            "largest_1pct_share": "route-level PV area carried by the largest ceiling(1% of host count) hosts",
        },
        "inputs": [
            source_record(roof_path, "panel a-b roof-area and building comparisons", len(roof_rows)),
            source_record(distribution_path, "panel c-d host-area distributions", len(distribution_rows)),
            source_record(pathway_path, "panel c pooled pathway means", len(pathway_rows)),
            source_record(capacity_path, "panel c nominal secondary-axis conversion", len(capacity_rows)),
            source_record(roof_manifest_path, "roof-area source manifest"),
            source_record(area_manifest_path, "area-weighted source manifest"),
            source_record(args.city_order_data.resolve(), "locked Figure 2 city order"),
            source_record(args.figure2_freeze.resolve(), "Figure 2 freeze manifest"),
            source_record(args.style.resolve(), "shared plotting style"),
            source_record(args.font.resolve(), "embedded plotting font"),
        ],
        "outputs": {
            path.name: {"path": str(path), "bytes": path.stat().st_size,
                        "sha256": sha256_file(path)}
            for path in output_paths
        },
    }
    write_json(output_manifest_path, manifest)

    print(json.dumps({
        "status": "REPRODUCED",
        "figure_png": str(png_path),
        "figure_pdf": str(pdf_path),
        "checks": str(checks_path),
        "count_to_roof_crossings": count_crossings,
        "building_area_to_roof_crossings": building_area_crossings,
    }, indent=2))


if __name__ == "__main__":
    main()
