# Writing agent contract and evidence index

## Mission

Write a new English-language manuscript for a Nature Portfolio urban-research
audience, with **Nature Cities Article** as the first-choice target. The paper
asks how newly observed Building flows and inherited Building stocks jointly
shape the amount, timing and route of anchor-surviving rooftop-PV area across 15
cities.

This manuscript starts from this directory. Ignore the retired scaffold at
`../manuscript.tex`; do not copy its prose, captions, title, outline or numerical
macros. The read-only paper at `../../reference_7pairs_v2/clean/` supplies
rhetorical and TeX style only, except that the user has explicitly authorized
its `rpv.bib` bibliography as the seed for `references.bib`.

## Mandatory startup sequence

Before every substantive writing session:

1. Read `../../PAPER_ANALYSIS_AGENDA.md` for current estimands, interpretation
   and scientific stopping rules.
2. Read `../README.md` for the paper architecture and evidence-status vocabulary.
3. Read `../CLAIMS_EVIDENCE_MATRIX.md` and identify the claim IDs being drafted.
4. Read `../FIGURE_PLAN.md` for the live panel and caption contract.
5. Read `../figures/v1/WRITING_AGENT_INDEX.md` for final figure mappings and
   figure-specific evidence files.
6. Read `state_machine.json`, select a permitted TODO, and update it when the
   task state changes.
7. Inspect the cited machine-readable CSVs, checks and owning manifests before
   inserting any result.

Data identity is governed by `../../results/major_results_index.json`,
`../../results/artifact_results_index.csv` and the passing owning manifests.
Scientific interpretation is governed by `../../PAPER_ANALYSIS_AGENDA.md`.
Record disagreements rather than silently choosing one source.

## Nature Cities Article contract

The following target was checked against the official Nature Cities content and
submission pages on 2026-09-03. Recheck before submission because journal rules
can change.

- Content type: Article, substantial primary research of broad interest to
  urban-focused researchers.
- Title: no more than 90 characters including spaces; avoid punctuation and
  active verbs.
- Abstract: no more than 150 words and no references.
- Main text: no more than 3,500 words, organized as an unheaded Introduction,
  Results and Discussion.
- Methods: a separate section after the main text, no more than 3,000 words.
- References: normally up to 50, in Nature style.
- Display items: no more than eight figures and/or tables. This scaffold uses
  five main-text figures and no main table.
- Results, Discussion and Methods use topical subheadings.
- Avoid footnotes and endnotes.
- Initial submission may be TeX/LaTeX but requires a compiled PDF.
- The submission package normally contains the manuscript, cover letter and,
  where needed, Supplementary Information.

Official pages:

- https://www.nature.com/natcities/content
- https://www.nature.com/natcities/submission-guidelines/preparing-your-submission
- https://www.nature.com/natcities/submission-guidelines/initial-formatting

The TeX grammar follows the clean reference manuscript: compact `article`
layout, Times-like text, superscript numeric `natbib` citations, conclusion-led
subsections, figure-led Results, full analytical captions, Discussion before
Methods, and `sn-nature` bibliography formatting. Do not transfer the reference
paper's empirical facts, prose, figure logic or claims.

## Manuscript architecture

The assembly order is fixed unless the user changes it:

1. Title, authors and unreferenced abstract.
2. Unheaded Introduction.
3. Results conclusion 1: temporal layering and censored observed lag — Fig. 1.
4. Results conclusion 2: new-route size/yield advantage versus inherited stock
   scale — Fig. 2.
5. Results conclusion 3: city denominator shifts, host-size concentration and
   observed transition switching — Figs. 3–4.
6. Discussion: conceptual contribution, implications, alternative mechanisms
   and limitations.
7. Methods, placed after Results and Discussion — Fig. 5 appears in the opening
   workflow subsection.
8. Data availability and code availability.
9. References.

The abstract is written last and follows five moves: urban problem; data and
design; principal stock--flow result; city and transition heterogeneity;
bounded implication.

## Core claim map

- C0 is `FROZEN`: indexed study scale and release identity.
- C1–C8, C10 and C14 are `REPRODUCED`: they may support Results with their
  declared denominators and limitations.
- C8 uses reproduced continuous-area source-block bootstrap intervals. The
  observed-city aggregate is supported, while city and transition directions
  retain the interval heterogeneity and target-population limits recorded in
  the claims matrix and Tables S5--S6.
- C9 is `PLANNED`: measured-nameplate calibration. Until released, use
  `DC-capacity-equivalent`, never measured or estimated installed capacity.
- C11 is `PLANNED`: context-to-risk-panel analysis. Keep contextual mechanisms
  out of the main Results unless the release gate passes.
- C12 has `REPRODUCED` partial validation: full/narrow risk-frame sensitivity,
  frozen candidate-bridge scenarios and unknown/unavailable accounting. Retain
  “in-scope, anchor-surviving PV and Buildings” throughout because
  non-candidate PV and historical disappearance remain unidentifiable.
- C13 is `BLOCKED`: no mandate, code, permit, incentive or policy causal claim.

## Figure map

All manuscript figures are read from `../figures/v1/`. Never overwrite them.

| Figure | File | Main location | Function |
|---|---|---|---|
| Fig. 1 | `fig_1.pdf` | Results 1 | Separate Building/PV area trajectories, temporal composition, onset classes and interval-imputed observed lag |
| Fig. 2 | `fig_2.pdf` | Results 2 | Event-host size, PV-area yield, route composition, exact three-factor anatomy and parity arithmetic |
| Fig. 3 | `fig_3.pdf` | Results 3 | Count/Building-area/roof-area denominator shifts and host-area distribution/concentration |
| Fig. 4 | `fig_4.pdf` | Results 3 | Native-transition roof-normalized ratios, diagnostic disagreement and observed switching |
| Fig. 5 | `fig_5.pdf` | Methods | Study area, model adaptation, independent temporal inference, linkage, censored onset and outputs |

`../figures/v1/WRITING_AGENT_INDEX.md` is the detailed figure gateway. It links
to every canonical caption, note, plotted CSV, check, source manifest and freeze
manifest. Fig. 5 currently lacks a canonical source bundle and figure manifest;
its provenance is an explicit TODO and its content must not be used as numerical
evidence.

## Scientific invariants

- Keep Building and PV evidence separate until the frozen anchor linkage.
- A cohort is an opaque ordered observation, not a year. Onset is left- or
  interval-censored.
- Never convert `U` to `A` or bridge unknown observations in the strict-adjacent
  primary analysis.
- Use raw-known `A/P` transitions for the primary risk panel. Resolved or
  persistence-imputed sequences are sensitivity analyses.
- Distinguish Building targets, Building--cohort exposures, PV targets, PV
  events, relationship rows and unique paired Buildings in every denominator.
- Composition is not propensity. Route shares among observed hosts do not show
  which risk group is more likely to add PV.
- The target population is anchor-surviving PV and Buildings in the relevant
  Anchor AOI or candidate scope. Do not call any event proportion a citywide
  historical adoption rate.
- `same_first_present_cohort` means cohort-contemporaneous, not installation at
  construction, code compliance or building-integrated PV.
- `pv_before_building_conflict` is a temporal-consistency diagnostic.
- All resolved source-PV areas converging on one unique host are summed once and
  attributed to that host's first strict adjacent PV event. This is not the true
  PV area installed during that cohort, and later expansions are not resolved.
- PV polygon-union area is the physical observable. A constant-density kWdc
  conversion is a `DC-capacity-equivalent` scenario.
- City order and point estimates are descriptive, not performance rankings.
- Distribution bands are not uncertainty intervals. Continuous-area contrasts
  receive no binomial Wald intervals.
- Use causal language only after a defined intervention, comparison group,
  identifying assumptions, pre-trend assessment and placebo or negative control.

## Number and table control

Never type a scientific result directly into TeX from memory, a console, an
agenda, a figure README or this agent file.

- Generate all numerical macros into `generated/results_macros.tex`.
- Keep a source CSV beside each generated `.tex` table.
- The generator manifest must record input paths, SHA-256 values, row counts,
  primary keys, filters, exclusions, denominator definitions, cohort order,
  code version and output hashes.
- Use only the evidence-status labels `FROZEN`, `REPRODUCED`, `PRELIMINARY`,
  `PLANNED` and `BLOCKED` in scientific notes.
- Retain `\draftnote{...}` until the underlying value and wording are generated,
  checked and reconciled.
- Define the denominator before every percentage, rate ratio or yield ratio.
- Use booktabs and no vertical rules. Mark unavailable estimates with an em dash
  and an explanatory note, never zero.

## Reference policy

`references.bib` is a local copy of
`../../reference_7pairs_v2/clean/rpv.bib`, initialized with 35 entries on
2026-09-03. It is a seed, not an approved citation set.

- Cite only entries whose relevance and metadata have been checked against the
  primary paper, official report, dataset or policy source.
- Append new verified references to `references.bib`; preserve stable BibTeX
  keys once cited.
- Prefer primary research and authoritative data/method sources.
- Do not copy citation clusters from the reference manuscript without checking
  whether every source supports the new sentence.
- Do not use the reference manuscript as evidence for this study.
- The abstract remains unreferenced.
- Keep the main reference list near the Nature Cities guideline of 50; route
  essential technical detail to Methods or Supplementary Information rather
  than padding the Introduction.

## Writing style

- Open every Results subsection with the scientific result, not a procedural
  recap.
- Move from aggregate pattern to exact stock--flow decomposition, then city
  heterogeneity, then transition heterogeneity and interpretation.
- Pair every strong claim with scope and its most relevant limitation in the
  same or immediately following paragraph.
- Separate observation from explanation. Use “is consistent with” for mechanism
  hypotheses unless a design identifies them.
- Prefer concrete nouns and verbs. Avoid “novel,” “groundbreaking,” “proves,”
  “reveals the cause” and generic assertions of robustness.
- Use the terms Building, PV, newly observed Building, existing-Building risk
  set, observed cohort transition and PV-area yield consistently.
- Write for a broad urban-research audience: introduce the urban consequence
  before remote-sensing or statistical machinery.
- Captions begin with one analytical sentence and then define every panel in
  order, including denominator, units, interval type and caveats.
- Do not repeat Methods details in Results unless they are necessary to
  understand the estimand.

## State-machine protocol

`state_machine.json` is the operational source of truth for writing progress.
Workflow status and scientific evidence status are different fields.

For each working session:

1. Confirm the current state and its permitted tasks.
2. Change one task to `IN_PROGRESS` before making material edits.
3. Make the smallest coherent edit and run the task-specific QA.
4. Set the task to `DONE`, `BLOCKED` or `DEFERRED`; record evidence, outputs and
   the reason.
5. Advance `current_state` only when every exit criterion for the current state
   is satisfied.
6. Append a history record and update `updated_utc`.

Do not mark submission readiness while any required `\draftnote`, broken
citation, ungenerated result, figure/caption mismatch or unresolved scientific
release gate affects a main claim.

## File map

- `main.tex`: clean manuscript assembly file.
- `sections/00_title_abstract.tex`: title, authors and abstract.
- `sections/01_introduction.tex`: unheaded Introduction.
- `sections/02_results.tex`: three conclusion-led Results subsections and Figs. 1–4.
- `sections/03_discussion.tex`: Discussion.
- `sections/04_methods.tex`: Methods and Fig. 5.
- `sections/05_backmatter.tex`: availability and declarations.
- `captions/`: one caption source per figure.
- `scripts/build_results_macros.py`: rebuilds the main-text numerical macros,
  per-macro provenance, QA checks and manifest from frozen/indexed evidence.
- `generated/results_macros.tex`: 89 display-formatted numerical macros loaded
  by `main.tex`; percent macros already include the TeX percent sign.
- `generated/results_macros_source.csv`: one-row-per-macro unrounded value,
  source hash, selector/expression, denominator, boundary, claim ID and status.
- `generated/results_macros_checks.json`: machine-readable accounting and
  source-binding checks; it must report `status: pass` before use.
- `generated/results_macros_manifest.json`: complete input/output hashes,
  primary keys, row counts, filters, denominators, cohort order and code hash.
- `generated/`: machine-generated macros and tables only; never edit its
  scientific values by hand.
- `references.bib`: reusable and extensible local bibliography.
- `supplementary.tex`: new Supplementary Information scaffold.
- `state_machine.json`: workflow state, TODOs, gates and history.
- `sn-nature.bst`: Nature bibliography style copied from the clean reference.

## QA before any section is called complete

1. Re-run the smallest relevant analysis or macro-generation command.
2. Verify identities, denominators, missingness and stock--flow accounting.
3. Check every number against a generated table and manifest.
4. Check each citation against its primary source and BibTeX metadata.
5. Ensure the prose and caption match the frozen plotted data and panel order.
6. Search for stale markers and prohibited wording.
7. Compile `main.tex` and `supplementary.tex` twice when a TeX engine is
   available; otherwise run brace, input, label/reference and citation-key
   checks and record the limitation.
8. Update `../CLAIMS_EVIDENCE_MATRIX.md` if claim wording, evidence or status
   changes.
9. Update `state_machine.json`.

A section is complete only when its claims are `REPRODUCED` or explicitly
bounded hypotheses/limitations, all numbers are generated and traceable,
captions agree with source tables, citations are verified, and no unresolved
draft marker remains in that section.
