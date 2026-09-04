# Urban rooftop-PV stock--flow analysis

This repository is the curated code-and-figure release for the manuscript
*Rooftop solar pathways across urban building stocks*. It preserves the main
figure outputs, the plotted machine-readable data, the analytical checks and
manifests, the plotting and paper-analysis code, and the agent workflow records
used to coordinate the paper build.

Repository: <https://github.com/PEESEgroup/US-MSA-Temporal-PV-Stduy>

## What is included

- `figures/figure1`--`figures/figure4`: approved PDF and 300-dpi PNG figures,
  plotted CSV files, checks, manifests, figure notes, and exact plotting-code
  snapshots.
- `figures/figure5`: the workflow artwork and its provenance/inspection record.
- `analysis`: the agent-authored analysis, uncertainty, sensitivity, macro, and
  static-manuscript-check scripts.
- `agent`: the scientific boundaries, claims ledger, figure plan, writing-agent
  contract, and task-state snapshot used during manuscript preparation.
- `style`: shared Matplotlib defaults.
- `release_manifest.json`: SHA-256 and byte-size inventory of this curated
  release.

The plotted data and figures are released at their recorded evidence status.
Figures 1--4 are `REPRODUCED` or `REPRODUCED (descriptive)`. Figure 5 is a
workflow illustration with `PRELIMINARY` source provenance and is not numerical
evidence.

## Scientific scope

The analysis concerns in-scope, anchor-surviving PV and Buildings in the
observed candidate domains. Cohorts are ordered observations, not exact
installation or construction dates. Existing-Building denominators are
Building--cohort or roof-area--cohort exposures. Capacity values are
constant-density DC-capacity-equivalent translations, not measured nameplate
capacity. The files in `agent/` give the complete interpretation boundaries.

## Verify the release

Python 3.10 or newer is sufficient for hash verification:

```bash
python verify_release.py
```

The command checks every tracked release file against `release_manifest.json`.
It does not rerun the upstream inventory or modify any file.

## Python environment

Create an isolated environment and install the plotting dependencies:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

The exact plotting snapshots retain their original path-aware command-line
interfaces. Consult each figure directory's README and script `--help` output.
Byte-identical reconstruction also requires the frozen derived inputs named in
the figure manifests and a licensed Arial font. The font is intentionally not
redistributed in this repository; a metrically different fallback can change
layout and hashes.

## Data availability boundary

This release contains the exact plotted CSVs and figure-level checks for the
main figures. It does not redistribute source aerial imagery, third-party
Building footprints, the upstream city-run directories, or the complete
220-MB high-level analytical table collection. Those materials remain subject
to their providers' access terms, file-size constraints, and the frozen input
manifests. Consequently, this repository supports auditing the displayed
values and the released analysis logic, but the full inventory must be obtained
through its original authorized data sources before end-to-end regeneration.

## Code map

See [analysis/README.md](analysis/README.md) for the analytical pipeline and
[figures/README.md](figures/README.md) for the figure bundles. Scripts that
construct full-AOI risk panels import the project-local `rpv_agent` onset
resolver; that upstream package is not vendored here.

## License

The repository software and documentation are released under the MIT License.
Third-party source data and assets retain their original providers' copyright,
access and reuse terms; provider-restricted inputs are not redistributed here.
