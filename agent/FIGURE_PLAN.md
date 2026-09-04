# Main-results figure production plan

## Figure contract and main-estimand decision

The paper uses **four main figures under three conclusion-led Results
sections**. The main observable is now anchor-year **PV polygon-union area**;
an explicitly scenario-based MWdc-equivalent translation is shown alongside
area where useful. Event and Building counts remain necessary denominators and
sensitivity evidence, but no longer define the main outcome.

This is an area/capacity-equivalent analysis, not a measured-nameplate analysis.
The frozen inventory has no system kWdc field. The nominal secondary scale uses
0.20 kWdc m\(^{-2}\), with 0.16 and 0.211 kWdc m\(^{-2}\) as illustrative
legacy and contemporary module-density scenarios. These constants change
totals in MWdc-equivalent but cannot change route shares, ratios, rankings, or
the three-factor identity. The sources and qualifications are frozen in
`../data_high_level/pv_area_capacity_density_scenarios.csv`.

The three Results conclusions are:

1. **PV capacity accumulated after most urban roof area was already in place.**
2. **Newly observed Buildings yield larger PV footprints and more PV area per
   risk unit, but inherited stock scale still controls total route area.**
3. **Area weighting changes the diagnosis of new-Building coupling, but the
   capacity advantage is temporally unstable and size-concentrated.**

| Results conclusion | Main figure | Analytical function |
|---|---|---|
| Capacity was layered onto inherited roof stock | Fig. 1 | Establish separate area trajectories, then link PV area to Building onset without creating a utilization rate. |
| New-route area advantages meet inherited stock scale | Fig. 2 | Establish the new route's footprint and area-yield advantages, then decompose why total area remains existing-stock dominated. |
| Area weighting changes but does not stabilize coupling | Figs. 3--4 | Show metropolitan reclassification, system-size leverage, transition switching, and tail concentration. |

The previous count-only forest plot, random-effects count synthesis, and
count-only transition heatmap move to Supplementary Information. Selected count
marks remain in the main figures only where they expose how event weighting and
area weighting answer different questions.

The existing workflow figure is a separate Methods asset and is not one of the
four main Results figures. Under the current manuscript routing it appears as
Fig. 5 in the Methods section, after Results and Discussion.

## Released evidence

The following area-weighted tables are `REPRODUCED` under
`../data_high_level/area_weighted_results_manifest.json`:

- `city_area_temporal_contrast.csv`;
- `city_pv_area_onset_pathway_composition.csv`;
- `city_area_weighted_stock_flow.csv`;
- `city_transition_area_weighted_stock_flow.csv`;
- `city_area_weighted_event_size_distribution.csv`;
- `pv_area_capacity_density_scenarios.csv`;
- `area_weighted_results_summary.csv`;
- `area_weighted_results_checks.json`.

The source PAU area trajectories and interval masses remain `REPRODUCED` under
`../data_high_level/city_pv_building_area_manifest.json`. The count-only
comparators remain `REPRODUCED` under
`../data_high_level/results_conclusion_evidence_manifest.json`.

The roof-area risk denominators are `REPRODUCED` under
`../data_high_level/roof_area_weighted_results_manifest.json`:

- `city_roof_area_weighted_stock_flow.csv`;
- `city_transition_roof_area_weighted_stock_flow.csv`;
- `roof_area_weighted_results_checks.json`.

The bundle reproduces all strict count-risk rows and PV-area numerators, maps
every full-AOI Building to positive plan-view anchor SAM3 roof-mask area,
reconciles narrow/outside mask cardinalities at Building level, and reproduces
the previously released narrow-scope Building area trajectories.

The area bundle verifies 15 cities, 67 full-AOI adjacent transitions, 440,128
PV targets, 397,181 resolved PV targets, 42,947 unavailable targets and 396,334
unique paired host Buildings. Relationship area reconciles exactly to the
trajectory area; resolved source-target area reconciles to unique-host area;
source PV polygon identities do not repeat within a city; all risk counts
reproduce the count bundle; and the largest three-factor log residual is below
\(10^{-12}\).

The plotted area-yield contrasts remain descriptive point estimates in the
immutable Figure 2--4 versions. Continuous PV-area uncertainty is now
`REPRODUCED` under `../data_high_level/area_uncertainty_manifest.json` using a
city-stratified source-block bootstrap with all native transitions and routes
retained under a shared block weight. Tables S5--S6 and the main text report
the interval support; the approved figures are not overwritten. Binomial Wald
intervals remain prohibited, and neither the bootstrap nor the figures relabel
the capacity-equivalent scale as measured installed capacity.

## Shared visual grammar

- White canvas (`#ffffff`), charcoal text (`#222222`), muted text
  (`#5f6363`), light rules (`#d9dddc`, `#eceeed`).
- Do not place an analytical title, subtitle or explanatory footnote inside a
  figure canvas. Analytical titles belong in the manuscript/caption, and all
  censoring, denominator and scope qualifications belong in the caption and
  figure note. Short direct facet identifiers such as city names are allowed
  because they identify marks rather than summarize a result.
- Match the retained `reference_7pairs_v2/code/revision` axis grammar: axis
  labels are 8.2-pt regular charcoal (`#222222`); tick labels are 7.0-pt muted
  charcoal (`#4a4f52`); visible axis spines are 0.6-pt neutral
  (`#b8bdbc`); and gridlines are 0.55-pt light neutral (`#d8dddc`) with a
  dotted pattern unless a panel-specific geometry requires otherwise.
- Analytical roles: new-Building route `#c97c5d`; existing-Building route
  `#2f7f6f`; area/capacity primary `#245f73`; count comparator `#9b9994`;
  conflict/QA `#b04a5a`; unavailable or low information `#d7d7d7` with hatch.
- Encode route with both hue and geometry. Encode estimand with line weight:
  thick/filled for area and thin/open for count.
- Use one stable city order across Figs. 2--4, frozen from the full-AOI
  area-yield ratio. Ordering is descriptive, not a performance ranking.
- Panel labels are lowercase plus commas (`a,`, `b,`), aligned to a common top
  edge. Follow the reference revision's regular Myriad Pro geometry at an
  approximately 9.49-pt visible height; use a regular sans-serif fallback when
  the traced vector glyph is unavailable. Panel identifiers are not bold
  headings. Use direct labels and no more than one shared legend per figure.
- Cohort labels remain opaque ordered observations. Use “observed cohort
  transition”, never installation year, construction year, or annual hazard.
- Export vector PDF and 300-dpi PNG. Every main figure writes a tidy panel CSV,
  a JSON invariant file, a manifest, a note and a caption source. No numerical
  label may be typed into plotting code.
- Unavailable or gated cells use a neutral hatch. Zero is never a missing-value
  symbol. Do not use dual axes without a direct analytical reason. Fig. 1a is
  the declared exception: both axes use million m\(^2\), the right-side PV zero
  is aligned to the Building baseline rail, and endpoint ratios are labelled
  directly. Elsewhere, a secondary axis is limited to a one-to-one translation
  from m\(^2\) to the declared nominal MWdc-equivalent scenario.

## Fig. 1 — PV capacity was layered onto inherited roof stock

### Analytical title

**Most PV area entered the record after most urban roof area was already
present.**

This compares temporal compositions in two anchor inventories and, only at the
panel-a endpoints, reports a descriptive PV-area-to-Building-roof-mask-area
utilization diagnostic. The absolute-area trajectories and panel-b temporal
shares are not themselves utilization, and no panel assigns exact installation
or construction dates.

### Panel design

- **a, Area trajectories.** Fifteen compact city axes show absolute area in
  million m\(^2\). Stacked bars partition cumulative canonical Building SAM3
  roof-mask area into baseline and post-baseline portions. Lines with
  translucent fills partition cumulative resolved PV area between baseline and
  later-observed hosts around the Building-baseline rail; later-host PV begins
  only after its linked Building enters the record. PV-before-Building conflicts
  and unavailable Building onset are excluded. The right-side PV zero is
  aligned to the Building baseline in every city. Endpoint labels report
  substantive non-conflict PV area divided by cumulative Building roof-mask
  area; only these labels are utilization, not the separate absolute-area axes.

- **b, The temporal area gap.** A paired-dot plot connects each city's
  post-baseline share of Building roof-mask area to its post-baseline share of
  PV union area. The pooled row is area-summed across cities and separated
  visually. Thin open marks show the corresponding count-weighted shares, so
  the viewer can see that large early PV systems make the area trajectory less
  back-loaded than the event-count trajectory.

- **c, Onset-pathway composition.** A 100% stacked city bar decomposes resolved
  non-conflict PV area into Building left-censored, cohort-contemporaneous, and
  between-cohort classes. The temporal-conflict QA pathway is excluded from the
  three substantive classes and reconciled separately.

- **d, Interval-imputed observed onset lag.** For each resolved PV--Building
  relationship, PV onset minus linked-Building onset is estimated by treating
  each cohort-label-implied onset interval as uniform; the expected onset is
  therefore the interval midpoint. A left-censored PV onset is assigned to the
  first cohort upper bound. Relationships with left-censored Building onset are
  excluded from lag estimation because their unknown earlier age cannot support
  an interval-imputed lag. Each city row in the main subplot shows the
  non-cumulative PV-area share in each one-year lag bin, using all resolved PV
  area as the denominator. Thus the visible annual-bin shares are not forced to
  reach 100%. Each city retains one nonzero y-tick label reporting its maximum
  one-year-bin PV-area share; repeated zero baselines are omitted. The
  temporal-conflict QA pathway is excluded from the substantive distribution
  and reconciled separately.
  Unavailable Building onset is excluded and reconciled separately. This is not
  an installation-minus-construction date.

### Data contract

- panel a: `city_pv_building_area_trajectories.csv`;
- panel b: `city_area_temporal_contrast.csv` plus
  `city_inventory_temporal_contrast.csv` for open count marks;
- panels c--d: canonical indexed `pv_building_relationship` artifacts,
  `config/city_cohort_ranges.csv` and the generated
  `figure1_panel_c_lag_data.csv`.

Figure derivatives must retain `panel`, `city_id`, display order, source unit,
denominator and status. Do not silently compare relationship-row PV area with
unique-host Building counts in one percentage denominator.

### Required checks

1. Building baseline plus post-baseline bars conserve cumulative canonical
   Building roof-mask area; baseline-host plus later-host lines conserve
   substantive non-conflict resolved PV area. Both axes retain million m\(^2\),
   and each city's PV zero aligns with its Building baseline rail.
2. Pooled anchor totals must be read from data, not hard-coded into plotting
   code.
3. Resolved pathway areas plus unavailable area reconcile to total anchor PV
   area in every city; the pathway mean-area comparison remains in Fig. 3c and
   is not the estimand of the new Fig. 1d lag panel.
4. Resolved pathway target counts reconcile to 397,181 relationship rows;
   unavailable target counts reconcile to 42,947.
5. Source PV polygon identities are unique within city before target areas are
   added.
6. Area and count comparators retain their different units and denominators.
7. Panels c--d must reproduce 397,181 resolved targets and 42,947 unavailable
   targets, record the uniform-interval and left-censor rules, and label the
   result interval-imputed observed lag rather than exact installation or
   construction lag.

### Figure note

Define PV union area, plan-view Building SAM3 roof-mask area, the panel-a
endpoint utilization denominator, the independent panel-b temporal-composition
denominators, left/interval censoring, uniform PAU interval allocation and the
anchor-survivor boundary. State that the Building measure is neither an
authoritative parcel footprint nor three-dimensional roof surface. Status:
`REPRODUCED`.

### Frozen initial rendering

The user-approved four-panel rendering is locked as
`figures/figure1_city_trajectories/initial_v1/figure1_abcd/`. Its native-vector
PDF, 300-dpi PNG, panel data, checks, manifests, exact plotting code, Arial font,
and planning snapshots are inventoried by `freeze_manifest.json`. The bundle is
an immutable version checkpoint: revisions must use a new version directory.
Its scientific evidence status remains `REPRODUCED`; the version label
`initial_v1` does not promote the evidence to `FROZEN`.

## Fig. 2 — New-route area advantages meet inherited stock scale

### Analytical title

**Newly observed Buildings yield larger PV footprints and more PV area per
risk unit, but the inherited Building stock still carries most PV area.**

The main plate uses a compact 2 × 2 layout (`a`--`b` above `c`--`d`). The
left-column panels a and c retain a 4.96-inch width; right-column panels b and
d use two-thirds of that width. Panels c and d are rendered together at the
same combined width with 3:2 GridSpec columns and one shared city y-axis; city
labels appear only on panel c. Panel a uses an alignment-only derivative whose
y-tick-label right edge and panel-label left edge match panel c; its frozen
data and visual content are otherwise unchanged. The upper and lower vector
pages are assembled without scaling, with 0.08 inch of verified content-free
edge whitespace removed between the rows. The final composite crops 0.373 inch
of excess left-page whitespace while retaining a 0.10-inch margin before the
leftmost rendered content.

### Panel design

- **a, New-route footprint and area-yield advantages.** A log--log scatter plot
  places mean anchor PV area among Buildings with a first PV appearance on the x-axis and
  PV area averaged over all eligible observations on the y-axis. Every city
  contributes one semi-transparent new-route point and one semi-transparent
  existing-route point; a light connector links the two route points and a city
  abbreviation labels the pair. Two larger opaque points show the
  count/area-summed 15-city pooled values and are connected for direct
  comparison with an opaque black line. Opaque route-colored dashed guides
  project each pooled point to both axes, where concise numeric value labels
  omit redundant `x =` and `y =` prefixes. Both opaque points are labelled
  “all-city”; an internal upper-centre legend maps green circles to existing
  Buildings and terracotta squares to new Buildings. The pooled points are not
  unweighted means of city estimates. New-route
  y-values use newly observed Buildings as the denominator, whereas
  existing-route y-values use eligible existing-Building cohort observations.
  The caption must state these distinct denominators; neither axis is roof
  utilization.

- **b, Area weighting increases the diagnosed new-Building share.** Two
  vertically stacked donut-style pie charts show the new- and existing-Building
  composition first when Buildings with a classified first PV appearance are
  count weighted and then when the same Buildings are weighted by their anchor
  PV area. Centre labels report the total Building count and total classified
  area; direct labels and leader lines keep the small new-Building wedges
  legible. Titles sit to the left of the corresponding pies. The upper pie's
  new-Building wedge is centered at the bottom and the lower pie's wedge at the
  top, so the wedges face one another. A vertical connector between those
  wedges carries the concise percentage-point and fold comparison. This panel
  is deliberately distinct from
  Fig. 1c: Fig. 1c partitions resolved non-conflict area by Building-onset
  censoring class, whereas Fig. 2b diagnoses the effect of count versus area
  weighting within the strict first-event route set.

- **c, Exact city contribution anatomy.** In the city order frozen by Fig. 1, a
  signed heatmap displays

  \[
  \log\frac{A_{retrofit}}{A_{new}}
  =\log\frac{N_{stock}}{N_{new}}
  +\log\frac{r_{retrofit}}{r_{new}}
  +\log\frac{\bar A_{retrofit}}{\bar A_{new}}.
  \]

  The stock term, event-intensity term and system-size term must visually sum
  to the observed area ratio. Positive cells support existing-route area
  dominance; negative cells support the new route. The count/area-summed
  `All cities` row is separated from city rows and is not a cross-city model.
  The decomposition residual remains a machine-checked invariant and is not
  displayed as a QA column. The horizontal colorbar is placed tightly beneath
  the heatmap.

- **d, Capacity-parity frontier.** In the same city order as panel c, plot the
  observed new-route PV-area yield \(A_{new}/N_{new}\) and the yield required to
  match the observed existing route, \(A_{retrofit}/N_{new}\), followed by the
  separately pooled row. Express both as PV m\(^2\) per newly observed Building
  and, on a one-to-one upper scale, nominal kWdc-equivalent per newly observed
  Building. Use the legend labels `observed new building` and `parity to
  existing` below the x-axis label; do not directly annotate the pooled points.
  `Parity to existing` is an arithmetic benchmark, not an observed
  existing-Building yield. This is arithmetic under observed denominators, not
  a forecast, mandate effect, eligibility assumption or roof-potential estimate.

### Data contract

All panels read `city_area_weighted_stock_flow.csv`; panel d may also
read `pv_area_capacity_density_scenarios.csv`. Full AOI is primary. Narrow rows
are a target-domain sensitivity in Supplementary Fig. S5.

### Required checks

1. `PV area total = PV area new + PV area retrofit` within every city and
   pooled scope.
2. Risk counts reproduce `city_stock_flow_decomposition.csv` exactly.
3. All source-target areas on a unique host are summed once; no source PV
   target is assigned to two hosts.
4. Every weighted event has one unique host and a positive area.
5. The maximum absolute three-factor log residual is below \(10^{-12}\).
6. Panel c follows the frozen Fig. 1 city order exactly, labels the pooled row
   `All cities`, and does not display the residual as a result-like QA column.
7. Panel-a pooled footprint and area-yield ratios reproduce the component
   fields in the source table exactly.
8. Panel-b new- and existing-route shares sum to 100% under both weighting
   schemes; the displayed percentage-point and fold changes recompute from the
   plotted shares.
9. Panel d follows panel c's city order exactly; its parity-to-existing value
   divided by the observed-new-Building value reproduces the total PV-area
   existing/new ratio for every city and the separately pooled row.
10. Capacity-equivalent shares equal area shares under every constant-density
   scenario.
11. Panel d is explicitly labelled arithmetic and not roof utilization.
12. Panels c and d are rendered on one shared city y-axis; panel d does not
    repeat the city labels, and every marker pair is centered on its matching
    panel-c row.

### Figure note

Define the strict raw-known risk sets, unique-host first-event rule and area
attribution rule. All anchor-year PV area on a host is assigned to its first
strict event; later within-host expansions are not time-resolved. Give the
nominal and bounding capacity-density scenarios and state that no measured
nameplate field is present. Status: `REPRODUCED` (descriptive).

### Frozen initial rendering

Panel a is visually frozen as the immutable `panel_a_revision3` bundle at
`figures/figure2_stock_flow/panel_a_revision3/`. Its plotted data, checks,
caption, note, rendering manifest and publication outputs are inventoried by
`freeze_manifest.json`. This is a visual version lock; the scientific evidence
status remains `REPRODUCED` and the analysis is descriptive. Do not overwrite this directory after
the `LOCKED` marker is present; any later revision requires an explicit new
version directory.

The user-approved complete four-panel rendering is locked at
`figures/figure2_stock_flow/initial_v1/figure2_abcd/`. Its native-vector PDF,
300-dpi PNG, four plotted panel CSVs, checks, manifests, exact plotting code,
font, planning snapshots, and results/caption writing guide are inventoried by
`freeze_manifest.json`. The approved page is 7.893 × 9.480 inches. The bundle
is an immutable visual checkpoint: any later revision must use a new sibling
version directory. Its scientific evidence status remains `REPRODUCED
(descriptive)`; `initial_v1` is not the evidence label `FROZEN`.

## Fig. 3 — Roof-area normalization changes the metropolitan diagnosis

### Analytical title

**Newly observed and existing roof stocks differ in PV-area yield after both
Building counts and roof-mask area are made explicit.**

### Panel design

- **a, City-specific denominator diagnostic.** On aligned city rows, connected
  marks compare the count ratio
  \((Y_{new}/N_{new})/(Y_{retrofit}/N_{stock})\), the Building-count-normalized
  PV-area ratio \((A_{new}/N_{new})/(A_{retrofit}/N_{stock})\), and

  \[
  R_{roof}=\frac{A_{new}/B^{roof}_{new}}
  {A_{retrofit}/B^{roof\text{-}exposure}_{stock}}
  \]

  on a log scale. Here \(B^{roof}_{new}\) is plan-view roof-mask area entering
  the newly observed Building group, while
  \(B^{roof\text{-}exposure}_{stock}\) is eligible existing roof-mask area
  summed over native cohort transitions. A reference line at one separates
  higher newly observed from higher existing values. Connections and crossings
  show whether the comparison changes with the denominator; they are not time
  trends or uncertainty intervals. Cities are ordered descriptively by the
  plotted PV first-appearance ratio, with the pooled row last. The three
  estimands are `REPRODUCED descriptive`; all 15 city-level full-AOI
  roof-area-normalized ratios exceed one, and nine cities cross one relative to
  the count ratio. The panel is not a roof-utilization or coverage estimate.

- **b, Host-level PV-area distributions.** Paired
  horizontal percentile bands compare anchor PV union area on newly observed
  Building hosts and existing Building hosts. Nested bands show the 1st--99th,
  10th--90th and 25th--75th percentile ranges; a vertical line marks the median
  and an open diamond marks the mean. Band height does not encode host count.
  These are distribution summaries, not uncertainty intervals. Use m\(^2\) on
  the lower axis and the nominal kWdc-equivalent translation on the upper axis.
  The main shared-y composite retains only the city and pooled route rows so
  that all three panels use an identical city coordinate. The pooled pathway
  mean track remains a traceable standalone diagnostic in
  `figures/figure3_roof_area/panel_b_boxen_v3/` but is not displayed in the
  shared-y main plate.

- **c, Capacity concentration.** Two aligned columns use the same city rows as
  panels a--b. The left column pairs routes by the share of PV area carried by
  the largest 1% of strict-event hosts; the right column pairs routes by the
  Gini coefficient. Small `n=` labels identify newly observed-Building routes
  for which the top-1% set contains only one or two hosts. The separated pooled
  row shows that broad inequality and extreme-tail concentration need not move
  in the same direction. Connecting lines pair routes within cities and are not
  time trends or uncertainty intervals.

### Data contract

- panel a: `city_area_weighted_stock_flow.csv` plus
  `city_roof_area_weighted_stock_flow.csv`;
- panel b: `../data_host_level/city_host_pv_area_distribution.csv` and
  `city_area_weighted_event_size_distribution.csv`; the standalone pathway
  diagnostic additionally uses `city_pv_area_onset_pathway_composition.csv`;
- panel c: `city_area_weighted_event_size_distribution.csv`;
- capacity scale: `pv_area_capacity_density_scenarios.csv`.

### Required checks

1. All 15 cities appear exactly once in the full-AOI city table.
2. Area-yield ratios are recomputed from displayed areas and risk denominators.
3. Count and area marks use the identical strict risk-panel rows.
4. A direction crossing is determined from the two finite point estimates,
   without continuity corrections.
5. Distribution quantiles and top-1% shares use unique strict-event hosts and
   the same all-source host-area weights as Fig. 2.
6. Displayed means and percentile bands recompute from the unique host-building
   input key, all quantile sequences are non-decreasing, and released medians,
   90th and 99th percentiles reconcile exactly. Bands are labelled
   distributions, not confidence intervals.
7. City order is descriptive, follows panel a's PV first-appearance ratio, and
   is held fixed across all three Fig. 3 panels.
8. For every city, new and existing roof-area denominators reconcile to the
   same strict risk rows used by the count denominators; existing roof area is
   a roof-area--cohort exposure, not an anchor-year stock total.
9. Displayed \(R_{roof}\) values recompute exactly from the four displayed
   numerator/denominator components, with zero or unavailable cells marked
   unavailable rather than continuity-corrected.
10. The combined a--c plate is drawn by one script rather than assembled from
    separate pages. All analytical axes share identical city y positions,
    limits and the pooled-row separator; city labels appear once on panel a.

### Figure note

Define both Building-count-normalized “area yield” and roof-area-normalized PV
yield. The latter uses plan-view SAM3 roof-mask m\(^2\), not usable roof surface,
and the existing denominator is accumulated roof-area--cohort exposure. Neither
estimand is an annual hazard, realized roof coverage, or exact cohort capacity
addition. Status: count-normalized contrasts `REPRODUCED descriptive`;
\(R_{roof}\) `REPRODUCED descriptive`.

### Current shared-y rendering

The user-approved one-script vector composite is frozen as the immutable
`figures/figure3_roof_area/initial_v1/figure3_abc/` bundle. It contains the
vector PDF, 300-dpi PNG, tidy plotted CSV, invariant checks, source manifest,
caption, figure note, exact code and document snapshots, plus a SHA-256 freeze
manifest. All panels use panel a's fixed city order and a shared y coordinate;
city labels appear once, while visible y ticks mark every row on panels a--c.
Each legend is centered beneath its panel label and uses common typography and
spacing; panel a remains one line. External spines are black and solid, major
tick grids are absent, and the retained analytical guides are solid `#b8bdbc`.
The design canvas is 7.08 by 2.76 inches and is tightly cropped with zero added
padding. Panel labels align vertically with `Capacity-equivalent (kWdc /
building)`, with `a,` aligned to the left edge of `Washington DC`. The composite
omits the standalone pooled pathway-mean track, which remains documented in the
panel-b source bundle. Status: `REPRODUCED (descriptive)`; `initial_v1` is a
visual version lock, not the evidence label `FROZEN`.

## Fig. 4 — Capacity coupling changes across observed transitions

### Analytical title

**The new-Building capacity advantage changes sign across observed
transitions.**

### Panel design

- **a, Transition-level roof-area-normalized map.** A city-by-native-transition
  heatmap shows
  \(\log_2[(A_{new}/B^{roof}_{new})/(A_{retrofit}/B^{roof}_{stock})]\), centered
  at zero. At transition level, \(B^{roof}_{stock}\) is eligible existing
  roof-mask area at the start of that transition, not the cross-transition sum.
  Every city retains its original adjacent cohort grid. Cells failing the
  prespecified event/roof-area denominator gate receive a neutral hatch. This
  panel's source table is `REPRODUCED`. The gate is frozen before first render
  in `figures/figure4_transition_dynamics/transition_information_gate_v1.json`:
  both routes require at least 10 strict first-event hosts, positive PV-area
  numerators and positive roof-area risk denominators, and finite positive
  count, Building-area and roof-area ratios. The user-approved rendering is
  visually frozen in `figures/figure4_transition_dynamics/draft_v1/`; its
  scientific evidence status remains `REPRODUCED descriptive`.

- **b, Where weighting changes the sign.** Aligned symbols distinguish cells
  where count RR, Building-count-normalized area-yield ratio, and \(R_{roof}\)
  do not lie on the same side of one. Exact counts must be generated from the
  released tables; the existing count-versus-area comparison remains visible
  alongside the `REPRODUCED descriptive` roof-area extension.

- **c, Rates and sizes behind the ratio.** Selected or small-multiple city rows
  show four aligned transition series: count event proportions for the two
  routes and mean PV area per event for the two routes. This distinguishes a
  frequency-driven switch from a size-driven switch. Do not use an unlabeled
  dual axis; use aligned tracks.

- **d, Temporal stability summary.** For every city, report the numbers of
  gate-eligible roof-area-normalized transitions above and below one, the share
  of eligible strict PV area in its largest transition, and whether a
  roof-area-normalized direction switch is observed. A weaker aligned symbol
  reports switching for the Building-count-normalized area-yield ratio so that
  the 11-city ungated result is not silently substituted for the panel-a
  estimand. The category is a summary of observed cells, not a permanent city
  type or policy response.

### Data contract

All primary panels derive from
`city_transition_area_weighted_stock_flow.csv`; panels a--b additionally require
`city_transition_roof_area_weighted_stock_flow.csv`. Panel d may write a
figure-specific aggregate table, but every aggregate must reconcile back to
the transition rows. The matching count transition table is used only to
verify and display sign disagreement.

### Required checks

1. Exactly 67 full-AOI adjacent transitions appear across 15 cities.
2. Native cohort order matches each owning risk-run input manifest.
3. No transition is interpreted as one year without verified capture dates.
4. Area-yield and count directions are computed from unrounded displayed
   values.
5. The sparse-information gate is frozen before inspecting the rendered
   heatmap; changing it requires a sensitivity panel. The main threshold is 10
   strict first-event hosts per route; 5 and 20 are reserved sensitivity
   thresholds.
6. City switch labels use finite eligible roof-area-yield cells, retain the
   number of supporting transitions, and distinguish the roof-normalized
   primary result from the Building-count-normalized comparator.
7. Transition area sums reconcile to each city total in Fig. 2.

### Figure note

Define transition eligibility, both area-yield ratios, count/area
sign-disagreement symbol, information mask and aggregation rule. State that
cohort intervals may have unequal duration and that switching does not identify
annual volatility, policy response or causal mechanism. Status: `REPRODUCED
descriptive`; the approved immutable bundle applies the prespecified
information gate.

### Frozen rendering

The user-approved four-panel rendering is locked in place at
`figures/figure4_transition_dynamics/draft_v1/`. Its vector PDF, 300-dpi PNG,
four panel CSVs, checks, source manifest, caption, note, exact plotting code,
font, information-gate and planning snapshots are inventoried by
`freeze_manifest.json`; the `LOCKED` marker prevents the default plotting
command from overwriting it. The approved page is 8.85 × 6.30 inches. Panels a
and b share the city axis, panels c and d form the aligned lower row, the shared
legend occupies the inter-row gap, and all city labels are black. Any later
visual or analytical revision must use a new sibling version directory. This
is a visual version lock only: the evidence remains `REPRODUCED (descriptive)`,
not `FROZEN`.

## Supplementary and Extended Data routing

The following remain necessary but do not consume a main-figure slot:

1. complete count-only trajectory, pathway and cohort-step figures;
2. count-only city RR/RD forest, descriptive random-effects synthesis and
   leave-one-city-out analysis;
3. count-only transition heatmap and stability classes;
4. narrow versus full-AOI area and count comparisons (`REPRODUCED` in Table S7);
5. raw `P/A/U`, rejected-positive, left-censoring and unavailable accounting
   (the `U`/unavailable component is `REPRODUCED` in Table S9);
6. alternative attribution using only the selected earliest source PV target,
   plus explicit multi-source host accounting;
7. capacity-density scenarios and any future permit/PTO nameplate calibration;
8. candidate-bridge sensitivity (`REPRODUCED` in Table S8), plus still
   unidentifiable anchor-survival disappearance, non-candidate PV and
   capture-date validation;
9. spatial clustering, block bootstrap, sparse cells and influence analysis;
10. context crosswalk coverage and policy-source evidence matrices.

## Conditional fourth Results section / sixth main-text figure

Do not add a fourth conclusion merely because contextual data exist. Because
the workflow is now Fig. 5 in Methods, an optional context result would be
Fig. 6 and is justified only if either:

- local permit, interconnection or PTO data calibrate area to measured kWdc
  across a defensible multi-city subset and materially revise the route
  contrast; or
- a prespecified one-Building-to-one-context join passes coverage, missingness,
  duplication, clustering and model gates and explains an interpretable part
  of the area-yield heterogeneity.

Until then, the MWdc values remain transparent equivalents and context remains
Supplementary or `PLANNED`.

## Production order and release gates

1. **Fig. 1:** promote the existing area trajectory panel; generate the
   temporal-gap and area-pathway panels from the released tables.
2. **Fig. 2:** render the released full-AOI area stock--flow table and verify the
   three-factor identity and capacity translation.
3. **Fig. 3:** complete. The approved `initial_v1/figure3_abc` bundle is an
   immutable visual checkpoint with fixed city order, area-yield and count
   comparators, and host-area distributions without inferential intervals.
4. **Continuous-outcome uncertainty:** complete. The 5,000-replicate primary
   source-block bootstrap, 2×/4× cluster sensitivities, alternate seed,
   replicate-count checks, city/transition tables, Tables S5--S6, checks and
   manifest are `REPRODUCED`. Any future interval rendering must use a new
   sibling figure version rather than overwrite the approved point-estimate
   figures.
5. **Fig. 4:** complete. The approved `draft_v1` is an immutable visual
   checkpoint and retains the prespecified transition information gate;
   5/20-event sensitivity renders, if produced, must use new sibling versions.
6. **Validation before abstract promotion:** complete nameplate calibration or
   retain “capacity-equivalent.” C12 follows the accepted partial-validation
   route: Tables S7--S9 are `REPRODUCED`, while the abstract and all main claims
   remain bounded to in-scope, anchor-surviving PV and Buildings because
   non-candidate PV and historical disappearance are unidentifiable.

Every caption begins with the analytical conclusion, defines panels in order,
names the denominator and physical unit, distinguishes distributional whiskers
from uncertainty, and ends with the in-scope, anchor-surviving target and
capacity-equivalent caveats.
