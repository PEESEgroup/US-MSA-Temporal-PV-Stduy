#!/usr/bin/env python3
"""Build full-AOI raw-known RR extensions for Chicago, Seattle, and Detroit."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import build_full_aoi_rr_11city as merge_run
import build_full_aoi_rr_raw_known as raw_run


CITY_IDS = ("chicago", "seattle", "detroit")

# Frozen narrow-scope reproduction targets. The resolved-onset counts reproduce
# the preliminary table in PAPER_ANALYSIS_AGENDA 2.4; the raw-known counts apply
# the primary adjacent P-to-P stock rule in section 4.1.
EXPECTED_NARROW_RESOLVED = {
    "chicago": (118849, 498, 4464596, 28491),
    "seattle": (28600, 218, 638537, 5634),
    "detroit": (10826, 153, 404136, 2349),
}
EXPECTED_NARROW_RAW_KNOWN = {
    "chicago": (118767, 498, 4087134, 27296),
    "seattle": (28593, 218, 562160, 5346),
    "detroit": (10820, 153, 363541, 2207),
}


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

    merge_run.CITY_IDS = CITY_IDS
    merge_run.EXPECTED_NARROW.update(EXPECTED_NARROW_RESOLVED)
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

    raw_run.CITY_IDS = CITY_IDS
    raw_run.EXPECTED_NARROW_RAW.update(EXPECTED_NARROW_RAW_KNOWN)
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
