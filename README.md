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

## PV-segmentation checkpoints

The deployed city-adapted **SegFormer-B5 checkpoints for all 15 study cities**
are available in the [city PV checkpoint release](https://github.com/PEESEgroup/US-MSA-Temporal-PV-Stduy/releases/tag/city-pv-checkpoints-v1).
The weights use a uniform city-based layout and the shared model-adaptation
and PV-segmentation workflow described in Methods and Supplementary Table S13.

| Archive | Cities |
|---|---|
| [Part 1](https://github.com/PEESEgroup/US-MSA-Temporal-PV-Stduy/releases/download/city-pv-checkpoints-v1/city-pv-checkpoints-v1-part-01.zip) | Atlanta, Boston, Charlotte, Chicago, Dallas |
| [Part 2](https://github.com/PEESEgroup/US-MSA-Temporal-PV-Stduy/releases/download/city-pv-checkpoints-v1/city-pv-checkpoints-v1-part-02.zip) | Denver, Detroit, Los Angeles, Miami, Minneapolis |
| [Part 3](https://github.com/PEESEgroup/US-MSA-Temporal-PV-Stduy/releases/download/city-pv-checkpoints-v1/city-pv-checkpoints-v1-part-03.zip) | New York City, Philadelphia, Phoenix, Seattle, Washington DC |

Each ZIP is approximately 1.69 GB; all three total approximately 5.08 GB.
The ZIPs are independently extractable, not split volumes. Download all three
for the complete collection, or select the archive containing the desired city.
Extract into the same directory to obtain
`checkpoints/<city_id>/segformer_b5.pth`.

The release also provides:

- [checkpoint_inventory.csv](https://github.com/PEESEgroup/US-MSA-Temporal-PV-Stduy/releases/download/city-pv-checkpoints-v1/checkpoint_inventory.csv): city-to-file mapping, byte sizes and per-checkpoint SHA-256 values.
- [SHA256SUMS.txt](https://github.com/PEESEgroup/US-MSA-Temporal-PV-Stduy/releases/download/city-pv-checkpoints-v1/SHA256SUMS.txt): checksums for the downloaded release assets.
- [Model README](https://github.com/PEESEgroup/US-MSA-Temporal-PV-Stduy/releases/download/city-pv-checkpoints-v1/README.md): package scope and use guidance.

After downloading all assets into one directory, verify them with
`sha256sum -c SHA256SUMS.txt`. The repository's `verify_release.py` checks the
code-and-figure files; the checkpoint assets have their own checksum inventory.

These files are the deployed PV-segmentation weights, not SAM 3 foundation
weights or a full training-resumption environment. Use a compatible
SegFormer-B5 implementation and the study's preprocessing. Source imagery,
training labels and the end-to-end inference environment are not included in
the model release. Weight availability does not extend the manuscript's
reported evaluation scope.

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
