#!/usr/bin/env python3
"""Build the immutable Los Angeles full-AOI merge and raw-known RR extension."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import build_full_aoi_rr_11city as merge_run
import build_full_aoi_rr_raw_known as raw_run


CITY_ID = "los_angeles"
EXPECTED_NARROW_RESOLVED = (138166, 2903, 6701621, 96760)
EXPECTED_NARROW_RAW_KNOWN = (137688, 2903, 5791295, 92335)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results-index", type=Path, required=True)
    parser.add_argument("--outside-root", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    state_merge_root = args.output_root / "state_merge"
    raw_known_root = args.output_root / "raw_known"

    merge_run.CITY_IDS = (CITY_ID,)
    merge_run.EXPECTED_NARROW[CITY_ID] = EXPECTED_NARROW_RESOLVED
    sys.argv = [
        "scripts/build_full_aoi_rr_11city.py",
        "--results-index",
        str(args.results_index),
        "--outside-root",
        str(args.outside_root),
        "--output-root",
        str(state_merge_root),
    ]
    merge_run.main()

    raw_run.CITY_IDS = (CITY_ID,)
    raw_run.EXPECTED_NARROW_RAW[CITY_ID] = EXPECTED_NARROW_RAW_KNOWN
    sys.argv = [
        "scripts/build_full_aoi_rr_raw_known.py",
        "--source-merge-root",
        str(state_merge_root),
        "--output-root",
        str(raw_known_root),
    ]
    raw_run.main()


if __name__ == "__main__":
    main()
