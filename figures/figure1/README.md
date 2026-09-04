# Figure 1 `initial_v1` — immutable writing bundle

This directory freezes the visually approved four-panel Figure 1 on
2026-09-03. Do not edit or overwrite files in
this directory. Any later revision must use a new version directory. The evidence
status is `REPRODUCED`; `initial_v1` is a version lock, not the evidence label
`FROZEN`.

## Release files

- `figure1_initial_v1.pdf`: publication-facing native-vector composite.
- `figure1_initial_v1.png`: 300-dpi review rendering.
- `panel_a_data.csv`, `panel_b_data.csv`, and `panels_c_d_data.csv`: plotted values.
- matching checks, manifests, and notes: denominator and reconciliation records.
- `code/`: exact plotting/compositing code, dependency pins, and Arial font.
- `documents/`: interpretation and claim-ledger snapshots at freeze time.
- `freeze_manifest.json`: SHA-256 inventory for every frozen file and authoritative
  input index.

The approved page is 9.10 by 7.55 inches. Panel a spans the full width; panels
b--d have equal plotting widths below it. The composite retains vector text and
marks. City order is identical across panels. The left edge of the longest panel-b
city label (Washington DC) is optically aligned with panel a, and panel identifiers
use the shared lowercase-comma grammar.

## Results available for manuscript drafting

Panel a uses absolute area (million m²) on both axes. Stacked Building bars split
cumulative canonical SAM3 roof-mask area into baseline and post-baseline portions.
PV lines and translucent fills split cumulative resolved PV area between baseline
and later-observed hosts around the Building-baseline rail; later-host PV begins
only after its linked Building enters the record. PV-before-Building conflicts and
unavailable Building onset are excluded. Endpoint labels alone report substantive
non-conflict PV area divided by cumulative Building roof-mask area. That ratio is
a within-inventory area utilization diagnostic, not prevalence or an adoption
rate, and cohort bounds are not exact installation or construction dates.

Panel b shows post-baseline temporal composition with separate PV and Building
denominators. In the pooled row, 8.0%
of Building roof-mask area and 83.7%
of PV union area enter after baseline. The corresponding count shares are
10.9% and
94.1%. These quantities
compare temporal composition, not route-specific propensity.

Panel c decomposes pooled resolved, non-conflict PV area into
86.9% Building left-censored,
5.7%
cohort-contemporaneous, and 7.4%
between-cohort. Cohort-contemporaneous means the first-present cohort is shared;
it does not mean same-date construction and PV installation. Temporal conflicts
remain a separate QA class and are excluded from these three substantive shares.

Panel d reports non-cumulative one-year lag-bin shares of all resolved PV area.
Expected Building and PV onset uses the midpoint implied by uniform allocation
within each cohort interval. Relationships with left-censored Building onset are
excluded from lag bins and accounted for in panel c; negative PV-before-Building
conflicts are also excluded. Consequently, the pooled visible bins sum to
11.5% rather than 100%, and the largest pooled annual-bin share is
5.0%. Call this an **interval-imputed observed lag**, never an
exact installation-minus-construction lag.

## Caption-ready analytical frame

Most anchor PV area entered the observation record after most canonical urban
roof-mask area was already present. Panel a displays the separate cumulative area
trajectories; panel b quantifies their post-baseline contrast and shows count
comparators; panel c separates Building left-censoring from cohort-resolved onset
relationships; panel d displays the non-cumulative interval-imputed lag distribution
for relationships whose Building onset can be interval-resolved. All results refer
to the anchor-surviving, in-scope inventories and are descriptive.

## Wording boundaries

- Use “entered the observation record,” “cohort,” and “interval-imputed observed
  lag.”
- Define each denominator before giving a percentage.
- Do not call the panel-a absolute-area trajectories or panel-b temporal shares
  “PV utilization.” Only the explicitly labelled panel-a endpoint ratio may be
  described as a PV-area utilization diagnostic; it is not physical roof
  coverage, prevalence, an adoption rate, or a causal effect.
- Describe Building area as a plan-view SAM3 roof-mask proxy, not 3-D roof surface.
- Keep unavailable onset and PV-before-Building conflicts explicit as exclusions or
  QA accounting; never code them as zero or as substantive pathways.
