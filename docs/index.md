# Soaring anomalous transport

This repository connects a thesis on soaring-flight dynamics to the code and recordings
behind its results. It covers acquisition from FFVL, trajectory cleaning, global transport
observables and probabilistic flight-phase segmentation.

Start with the [repository README](https://github.com/matteodisante/soaring-anomalous-transport/blob/main/README.md)
for the manuscript structure and commands. The [research roadmap](thesis-roadmap.md)
records the later phase-conditioned analysis, solo/group comparison, stochastic modelling
and thermal-route questions.

## Follow the data

| Step | Documentation |
|---|---|
| Acquire IGC files and metadata | [Data source](guide/data-source.md), [downloading](guide/downloading.md) |
| Understand a flight's identity | [IGC file to flight](guide/igc-to-flight.md) |
| Clean and resample trajectories | [Preprocessing pipeline](guide/preprocessing-pipeline.md) |
| Read the processed tables | [SSD layout and schemas](guide/data-on-disk.md) |
| Measure motion before segmentation | [Global transport](guide/global-transport.md) |
| Infer and evaluate flight phases | [Segmentation](guide/flight-phase-segmentation.md) |
| Rebuild the scientific results | [Complete workflow](guide/rebuilding.md) |
| Trace a figure or numerical value | [Generated provenance](guide/provenance.md) |

Raw recordings and large derived tables live on the SSD. Small season summaries, map
geometry and generated manuscript fragments live in the repository. Each combined rebuild
writes fresh intermediate arrays and logs under `derived-audit/runs/<run-id>/` on the SSD.
The disk's generated README inventories what is actually present.

## Reproducibility and scientific validation

The complete workflow rejects incomplete cleaning, changed code or parameters, altered
tables and missing or stale required figures. It records source fingerprints, table
identities, stage results and the final PDF hash. These checks establish which computation
produced a result. They do not establish the physical validity of every retained fix or
prove that a stochastic model is correct.

Generated numerical macros are checked against their uses in the manuscript. The
[figure conventions](guide/figures.md) specify colours, dimensions, support counts and
band meanings. The [bibliography audit](guide/bibliography.md) distinguishes inspected
primary sources from metadata-only checks.

For setup, see [installation](guide/installation.md). The [script guide](guide/scripts.md)
lists entry points, and the [API reference](reference.md) is built from package docstrings.
