# Figure 3 `initial_v1` — immutable approved bundle

This directory freezes the user-approved three-panel Figure 3 on
2026-09-03. Do not edit or overwrite files
in this directory. Any later visual or analytical revision must use a new sibling
version directory. The evidence status remains `REPRODUCED (descriptive)`;
`initial_v1` is a visual version lock, not the evidence label `FROZEN`.

## Release files

- `figure3_initial_v1.pdf`: publication-facing native-vector figure.
- `figure3_initial_v1.png`: 300-dpi review rendering.
- `figure3_abc_data.csv`: exact tidy plotted data for panels a--c.
- `figure3_abc_checks.json`: scientific, source, and layout invariants.
- `figure3_abc_manifest.json`: source identities, hashes, filters, and outputs.
- `figure3_abc_caption.md` and `figure3_abc_note.md`: caption and interpretation boundaries.
- `source_panels/`: the three verified input panel bundles used by the composite.
- `code/`: exact plotting code, style, dependency versions, width reference, and font.
- `documents/`: agenda, paper README, Figure Plan, and claim-ledger snapshots.
- `freeze_manifest.json`: SHA-256 inventory of the immutable checkpoint.

The approved design canvas is 7.08 by
2.76 inches and is exported with zero
added crop padding. All panels share 15 city rows
plus the pooled row. Panel labels are level with the panel-b capacity-equivalent
title; `a,` is aligned to the left edge of `Washington DC`. Major-tick grids are
absent, while the retained analytical guides are solid gray.

## Scientific scope

Panel a compares new/existing ratios for PV first appearances, PV area per
Building risk unit, and PV area per corresponding plan-view roof-mask area at
risk. Panel b shows route-specific host-area distributions on a log scale with
nested percentile bands, medians, and means. Panel c shows largest-1% area shares
and Gini coefficients by route. The upper panel-b scale is a nominal 0.20 kWdc
m⁻² translation, not measured nameplate capacity.

These are descriptive full-AOI summaries. They are not uncertainty intervals,
city rankings, citywide adoption estimates, usable-roof utilization, forecasts,
or causal effects. Anchor PV area is attributed to each unique strict-event
host's first strict adjacent PV appearance.
