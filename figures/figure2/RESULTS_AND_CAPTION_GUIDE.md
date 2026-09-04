# Figure 2 `initial_v1`: Results and caption guide

## Claim supported by the figure

Newly observed buildings carry larger anchor-PV footprints per strict
first-appearance host and higher PV-area yield per their corresponding risk
unit, but inherited-building exposure is sufficiently larger that most
strict-classified PV area remains assigned to the existing-building route.

Status: `REPRODUCED (descriptive)`. Scope: 15-city full-AOI, raw-known,
strict-adjacent cohort transitions among anchor-surviving in-scope inventories.

## All-city quantities available for writing

| Quantity | New-building route | Existing-building route or benchmark | Contrast | Frozen source |
|---|---:|---:|---:|---|
| Mean anchor PV area per strict first-appearance host | 128.83 m² | 54.59 m² | new/existing = 2.36× | `panel_a_data.csv`; `panel_a_checks.json` |
| PV area per corresponding risk unit | 1.180 m² per newly observed building | 0.539 m² per eligible existing-building cohort observation | new/existing = 2.19× | `panel_a_data.csv`; `panel_a_checks.json` |
| Route share among 359,527 strict-classified first-appearance buildings | 2.71% (9,734) | 97.29% (349,793) | — | `panel_b_data.csv`; `panel_b_checks.json` |
| Route share of 20.348 km² attributed anchor PV area on those buildings | 6.16% (1.254 km²) | 93.84% (19.094 km²) | new share rises by 3.46 percentage points and 2.28× under area weighting | `panel_b_data.csv`; `panel_b_checks.json` |
| Stock exposure, existing/new | — | 33.36× | existing-favoring | `panel_c_data.csv` |
| First-appearance intensity, existing/new | — | 1.077× | near parity, slightly existing-favoring | `panel_c_data.csv` |
| Event footprint, existing/new | — | 0.424× | equivalent to the 2.36× new-route footprint advantage | `panel_c_data.csv` |
| Total attributed PV area, existing/new | — | 15.23× | existing-favoring | `panel_c_data.csv`; `figure2_initial_v1_checks.json` |
| Observed and parity PV area per newly observed building | 1.180 m² observed | 17.967 m² required for parity with the existing route | parity/observed = 15.23× | `panel_d_data.csv`; `panel_d_checks.json` |

The rounded values above are display derivatives of the cited machine-readable
rows. Use those CSVs, rather than this prose, for macros or final numerical
typesetting.

## Denominators that must accompany the result

- Panel a x-axis: unique buildings with a strict first PV appearance in each
  route. It reports mean anchor PV footprint per event host.
- Panel a y-axis: newly observed buildings for the new route, but eligible
  existing-building cohort observations for the existing route. It reports PV
  area per risk unit, not PV area per building under a common denominator.
- Panel b: the same 359,527 strict-classified unique first-appearance buildings,
  weighted first by building count and then by attributed anchor PV area.
- Panel c: an exact existing/new identity: stock exposure × first-appearance
  intensity × event footprint = total attributed PV area.
- Panel d: both marks divide by the newly observed-building count. `Parity to
  existing` is existing-route total PV area divided by that count; it is an
  arithmetic requirement, not an observed existing-building yield.

All resolved source-PV areas converging on one unique host are summed once and
assigned to that host's first strict adjacent PV appearance. Later expansions
cannot be time-resolved and are not separate events in this figure.

## Suggested Results paragraph

Across the 15-city full-AOI sample, buildings entering the record with their
first PV appearance carried a larger mean anchor-PV footprint than the
existing-building route (128.83 versus 54.59 m² per strict first-appearance
host). After division by the corresponding risk sets, the new-building route
also carried 2.19 times as much PV area per risk unit. This size advantage did
not determine aggregate composition: eligible existing-building cohort
exposure was 33.36 times the newly observed-building exposure, while
first-appearance intensity was similar between routes (existing/new = 1.077).
Consequently, the existing-building route carried 15.23 times the attributed PV
area and accounted for 93.84% of strict-classified area. Consistent with the
larger new-route footprints, weighting the same first-appearance buildings by
PV area increased the diagnosed new-building share from 2.71% to 6.16%.

This paragraph is descriptive. If shortened, retain the distinct risk-set
denominators and first-event area-attribution caveat in the paragraph or its
immediate successor.

## Caption-ready draft

**Larger new-building PV footprints do not offset inherited-building stock
scale.** (a) City-level and all-city comparisons of mean anchor PV area among
buildings with a first PV appearance and PV area per corresponding risk unit;
the new route uses newly observed buildings, whereas the existing route uses
eligible existing-building cohort observations. (b) Route composition among
the same strict-classified first-appearance buildings, weighted by building
count and then by attributed anchor PV area. (c) Existing/new ratios decompose
total attributed PV area into stock exposure, first-appearance intensity, and
event-footprint contributions; the `All cities` row is count/area summed rather
than an unweighted city mean. (d) Observed new-route PV area per newly observed
building and the arithmetic level required to equal total existing-route PV
area. Panels c and d use descending observed new-building PV area per newly
observed building, with `All cities` last. The upper panel-d axis
is a nominal 0.20 kWdc m⁻² unit translation, not measured nameplate capacity.
Results use full-AOI strict-adjacent raw-known transitions; all anchor-year PV
area on a unique host is assigned to its first strict appearance, so later
within-host expansions are not time-resolved.

## Interpretation and wording boundaries

- Say `PV-area yield per risk unit`; do not call panel a roof utilization,
  coverage, adoption probability, or an annual hazard.
- Say `first PV appearance` or `observed cohort transition`; cohort labels are
  not installation or construction years.
- `Newly observed building` is an observed route classification, not proof that
  a structure was newly constructed at an exact date.
- `Existing building` and `new building` describe strict observed pathways; do
  not infer policy compliance or a causal effect.
- The all-city row is direct count/area pooling and is not a cross-city model.
- The city patterns have no inferential intervals here and should not be treated
  as rankings.
- The target population is anchor-surviving PV and buildings in the candidate
  scope, not a citywide historical adoption census.
- PV polygon-union area is the physical observable. The kWdc axis is only a
  constant-density equivalent and must not be described as measured capacity.
