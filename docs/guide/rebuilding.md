# Rebuild the thesis after a cleaning change

Use one command from the repository root, with both archives mounted:

```bash
uv run python scripts/rebuild_thesis.py --clean --jobs 1
```

The default uses one worker, one native numerical-library thread, and low process
priority (nice 19). On macOS it also uses the background scheduling/I/O policy.
Stages run sequentially. For an eight-worker run at normal scheduling priority, use
`--jobs 8 --full-speed`. The worker limit also caps raw diagnostics, reproduction
checks and HMM restarts through `SOARING_MAX_WORKERS`; native library threads stay at
one per worker to avoid nested oversubscription.

This runs the cleaning on both complete archives, checks the resulting tables,
recomputes the transport measurements, refits and applies the phase model,
regenerates the chapter figures and tables, prepares a new annotation pack, and
compiles `thesis/main.pdf`. The ordered commands live in
`configs/rebuild.yaml`. The run includes multiple
full passes over the SSD and is expected to take hours; the duration depends on
the machine and archive. Keep the SSD attached and avoid editing analysis code
or configuration during the run.

To inspect the commands without processing data or writing outputs:

```bash
uv run python scripts/rebuild_thesis.py --clean --dry-run
```

`--no-build` stops after regenerating and checking the numerical products. Without
`--clean`, the driver requires complete tables produced by the current cleaning
code and configuration. It then recomputes downstream products. The compatibility
entry point `scripts/regenerate.sh` accepts the same options.

Running `scripts/preprocess.py` directly still performs **only cleaning**. Use
the combined command above when the purpose is to update the thesis as well.
Do not use a `--limit` sample as a replacement for the complete derived archive:
the standalone cleaner writes into that archive's `derived/` directory, and the
thesis driver rejects manifests from sampled runs.

The Git pre-commit hook checks staged whitespace without changing files or the index.
It does not regenerate statistics, compile the PDF or certify scientific results.
Perform the complete rebuild and manuscript review explicitly before staging the
finished revision. This keeps the reviewed output identities intact when changes
are divided into several commits. `scripts/build_docs.sh thesis` is only a convenience
compiler for existing inputs; it does not replace either provenance-aware command.

## Where the results go

The data roots come from `configs/para_download.yaml` and
`configs/delta_download.yaml`. Environment variables `SOARING_PARA_DATA_ROOT` and
`SOARING_DELTA_DATA_ROOT` override those paths. Both raw IGC directories and both
catalogues are required; the combined rebuild does not publish a partial thesis.

Every run gets its own directory under
`/Volumes/SSD_DISANTE/derived-audit/runs/<run-id>/`. Set `--audit-dir PATH` or
`AUDIT_DIR` to choose another persistent parent directory. Each run contains:

- `manifest.json`: commands, source fingerprint, dataset identities, stage status,
  output hashes and, after a successful build, the PDF hash;
- one log per stage;
- `arrays/`: newly measured transport arrays, isolated from older cached analyses.

The chapter figures and numerical fragments are written to `thesis/generated/`.
The new manual annotation pack goes to
`annotations/phase_labeling/<run-id>/`. Existing annotation packs and human labels
are preserved. The historical witness audit at 30 m/s is an explicitly dated
comparison of old cleaners; it is retained as a historical control and is not
presented as a measurement of the new 10 m/s archive.

## What the checks establish

Each cleaner writes `derived/run_manifest.json` with the pipeline version, exact
configuration, relevant source hashes and numerical-library versions. The four
Parquet tables are identified by row count, size, modification time and a hash of
their footer. This is a practical replacement/schema check, **not a checksum of
every trajectory value**. A seeded sample of 250 retained flights per discipline
is separately reprocessed and compared at float32 storage precision, including
the quality flags. Agreement on that sample is not proof about every flight.

An unfinished cleaning leaves `.run_incomplete`. Advisory locks prevent the
provided cleaner and rebuild driver from writing the same archive concurrently.
The driver rejects an old version, changed configuration, altered tables, a
missing required figure, or a generator that exits successfully while leaving an
old required output in place. It rechecks source and table identities between
stages. These locks do not constrain arbitrary external programs editing files.

A failed stage stops the sequence and leaves a failed manifest and its log. The
existing PDF may still be present; only a manifest with `status: complete` and a
matching PDF hash certifies a completed combined rebuild. There is no automatic
resume: resolve the reported failure, then run the command again. If cleaning
completed and its definition has not changed, omit `--clean` to repeat only the
downstream workflow. Intermediate arrays from the failed run remain available
for investigation.

### Identified recovery after an interruption

The September 2026 recovery is recorded under
`revisions/vertical-gap-split-2026-09-11/`. Its bounded continuation scripts preserve
the failed parent manifests, validate reused arrays and their segment support, and
repeat the full structural check after remounting the SSD. They are specific to
the recorded completed-stage prefix; they are not a general instruction to ignore
a failed source or data guard.

During that recovery, four viewer files changed while the Chapter 3 reporter was
running. The completed numerical stage was preserved, and subsequent stages run
inside the identified frozen source tree. A separate comparison verifies every
other guarded source file and the unchanged geography definitions imported by
the terrain reporter. The original broad source hash is retained as the identity
of the executed code. It is not silently replaced by the working checkout's hash.

Final manuscript review must still wait for the complete numerical chain. The
working thesis can then be reconciled with the reviewed isolated output by checking
all result hashes, manuscript bytes, source dependencies and cleaned-table identities.
The reconciliation record must state the viewer differences explicitly. An unchanged
cleaning version string alone is insufficient evidence of this agreement.

## Roadmap and manual annotations

The [roadmap](../thesis-roadmap.md) records the scientific sequence and the
questions for later chapters. It requires no action in an application.

Manual annotation is the independent evidence needed to assess whether phase
labels correspond to the intended behaviours. A numerically stable HMM and
plausible plots do not establish classification accuracy. Use the **new pack
printed at the end of the rebuild**, following the
[annotation instructions](https://github.com/matteodisante/soaring-anomalous-transport/blob/main/annotations/phase_labeling/README.md). Start with
the training split to settle the labelling convention. Keep the final test split
separate from tuning. Existing packs carry provenance checks and are refused by
the labeler if their mounted source has changed.

The September 10 audit and regeneration status are recorded in
[the audit log](https://github.com/matteodisante/soaring-anomalous-transport/blob/main/revisions/correctness-audit-2026-09-10.md).
A completed computational rebuild does not replace independent phase annotation.

## Reviewing the manuscript after a completed run

Fresh numbers must be interpreted before the prose is final. After changing authored
text only, compile with:

```bash
uv run python scripts/review_thesis.py --run /Volumes/SSD_DISANTE/derived-audit/runs/<run-id>
```

This requires a completed numerical run and verifies its code/configuration hash,
source-table identities and hashes of generated results. It rejects new unrecorded
figure inputs and changed numerical products. The original manifest remains unchanged;
`manuscript-review.json` records the revised source and PDF hashes and links them to that
numerical run. A changed numerical calculation requires a rebuild. The source hash
also includes rendering code, so a drawing-only edit is rejected by the same check
unless a separate, explicit review proves the unchanged calculations and records
the new presentation hashes. Such a review must preserve the original sources,
outputs and execution manifest; it cannot establish equivalence by merely replacing
a hash. The September 11 palette and layout proofs under `revisions/` document these
specific exceptions. They do not authorize relabelling results after an algorithm change.

The September 12 regional PCA follow-up has its own numerical record at
`revisions/regional-pca-lags-2026-09-12/numerical-update.json`. It verifies the
full-archive coordinate stores by SHA-256, computes centred regional covariances
at exactly 10, 100, 1000 and 10,000 s, and rebuilds the PCA figure and reference
table. Shared 10-s and 10,000-s results are checked against the original run.
Every non-PCA report value and the other 74 generated inputs remain unchanged.
Its separate manuscript review records that lineage; it does not claim a new
execution of cleaning, distribution fits or bootstrap calculations. A future
complete rebuild uses the same exact-lag PCA implementation directly.

The regional finite-difference extension is recorded separately in
`revisions/regional-variations-2026-09-12/numerical-update.json`. It preserves
that PCA revision and all earlier generated inputs, then adds three difference
orders, directional moments, distribution summaries and site-day uncertainty.
Its reviewed manuscript and presentation inputs include both numerical updates.
The `regional_variations` rebuild stage runs after `transport_full` and uses
the newly generated full coordinate stores. It needs no additional raw-data pass.
For a focused measurement from the verified September 12 stores:

```bash
.venv/bin/python scripts/reporting/ch3_global_transport/measure_regional_variations.py \
  --out /path/to/a/new/regional-variation-run
```

Use a new output directory for a new measurement; preserve completed reports.
The regional revision record, `revisions/regional-variations-2026-09-12/README.md`,
documents rendering, independent numerical checks, manuscript review and slide
preparation. Its measurements took 168 seconds on the delivery machine using
four workers and 500 bootstrap replicates; this is not a timing estimate for
the full cleaning and thesis rebuild.

The `grouped_tamsd` stage reuses the identified native segment curves after
`msd_measure`. It groups the full eligible population by the three take-off
regions and four cleaned-origin GNSS altitude bands. Its second control fixes
long segments across the full lag grid. The focused delivery and numerical audit
are recorded in `revisions/grouped-tamsd-2026-09-12/`; the report preserves full
membership, support and site-day intervals. Its approximately ten-second runtime
uses already measured TAMSD arrays and does not include cleaning or the native
FFT measurements. The initial-altitude labels must not be interpreted as measured
terrain classes or substituted for the raw-first-altitude map's grouping.

The final September 11 review also corrected an omitted altitude-admission row in
the rejection cascade. That was a numerical report error, not a plotting-only edit.
The report was regenerated from unchanged flight metadata and checked against an
independent census; all other generated outputs and both dataset identities were
verified before recording the correction. No trajectory, transport statistic or
phase label changed. The original manifests and the distinct report-correction
proof remain preserved under `revisions/` and in the SSD run directory.
The final run manifest links the manuscript review to its immutable input manifest;
`executed_pdf_sha256` preserves the original execution PDF identity, while
`pdf_sha256` identifies the final reviewed PDF.

Offline compilation with `scripts/build_docs.sh thesis` can support manuscript and
layout review, but cannot close the source-archive check. While the SSD is unavailable,
keep that review pending and preserve the original execution PDF for reconciliation
when the archive is mounted again.

## Recorded documentation-only correction

The 10 September cleaner review corrected comments and docstrings after the raw
cleaning completed. The proof in `revisions/cleaner-documentation-2026-09-10/README.md`
preserves both source versions and original execution manifests, verifies identical
executable ASTs, and reconstructs the original whole-source hash to check every other
file. The SSD manifests retain `executed_cleaning` and link the explicit documentation
review; `cleaning` identifies the current, algorithmically identical definition.
No cleaned values or thresholds changed. This is a recorded exception with evidence,
not permission to relabel old outputs after an algorithm change.

The `terrain_axes` and `channel_wind` stages run after the current flight report.
They use frozen independent ETOPO and ERA5 inputs included in the repository;
rebuilding these comparisons requires no weather download. They produce eight
small figure, macro and JSON outputs, each identifying the current flight report.
The environmental record at `revisions/environment-axis-integration-2026-09-12/`
links the grouped-TAMSD numerical record and the earlier full-run lineage. Its
combined manuscript review checks all 89 inherited outputs and eight new outputs,
source identities, external input hashes and the unchanged cleaning manifests.
It explicitly distinguishes table stat/footer validation from a new full-byte
checksum of the cleaned trajectories. The slide preparation command requires
`--environment-update` with this record, in addition to its three parent flags.

The nine hourly ERA5 API responses are preserved as gzip in
`revisions/channel-wind-2026-09-12/`. `fetch_wind.py` verifies them offline by
default; `--download-to NEW_DIRECTORY` makes a separate new download without
changing the scientific input archive. The directory README documents source
attribution, returned grid cells, angle convention and reuse in standard Python.
