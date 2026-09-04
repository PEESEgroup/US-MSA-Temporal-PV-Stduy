# Analysis code

The scripts are grouped here as a compact record of the paper-analysis pipeline.
They are snapshots of the code used in the full workspace and retain manifest,
hash, primary-key, denominator, and output-QA checks.

## Main pipeline

1. `build_results_index.py` records the frozen artifact entry points.
2. `build_results_conclusion_evidence.py` constructs count-based pathway and
   stock--flow evidence.
3. `build_area_weighted_results.py` adds host-attributed PV union area and the
   exact three-factor decomposition.
4. `build_roof_area_weighted_stock_flow.py` adds route-specific plan-view
   roof-area denominators.
5. `build_host_pv_area_distribution.py` constructs event-host area
   distributions and concentration summaries.
6. `build_area_block_bootstrap.py` produces source-block bootstrap uncertainty.
7. `build_c12_partial_validation.py` produces full/narrow, candidate-bridge,
   and unknown/unavailable sensitivity accounting.
8. `build_results_macros.py` converts released machine-readable values into
   traceable manuscript macros.
9. `check_static_tex.py` checks the active TeX trees and release connections.

The remaining scripts build city-group risk-panel releases or supporting
diagnostics. Run `python analysis/<script>.py --help` before execution. Default
paths reflect the original workspace; pass explicit input and output paths when
using another layout.

The full risk-panel builders require the separately maintained `rpv_agent`
package and frozen city artifacts. Their absence is intentional: this curated
repository is a paper-code release, not a redistribution of upstream imagery or
production inventories.
