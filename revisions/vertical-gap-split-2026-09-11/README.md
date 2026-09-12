# Vertical-gap split, pipeline 2.3.0

The user requested the same bridge-or-split rule for missing altitude and temporal
gaps, with a complete rebuild and updated thesis/documentation.

## Current delivery — 12 September 2026

The complete numerical run and final manuscript review are finished. All 39 stages
in `20260912T133040Z-073601cb` completed. The reviewed thesis contains 116 pages;
its SHA-256 is `a9127a892460ff1078c5c0c8de3fcd5e66be3f5c93e838cefc1903a4071c9860`.
The source and output identities are in `release/manuscript-review.json` and
`release/manifest.json`. `reviewed-checkout.json` records publication back to the
working checkout. Viewer-only user edits remain separate from the executed science.

`chapter3-results-audit.json` independently checks full-archive support, slopes,
contrasts, marginal CDF distances and joint masses. `final-phase-review.json`
records review of all five fresh phase diagnostics. The thesis now separates
rescaling and vector-law questions from regional/environment/equipment questions,
and places duration controls before model comparisons.

The final slide sources describe only current methods and results. The complete
58-slide Chapter 2 and 75-slide Chapter 3 decks, with speaker notes, passed final
visual and provenance review in `presentations/`; no prior-version comparison is included.
They were assembled after the final thesis review, as requested.

`full-report-archive/` stores both full JSON reports in deterministic gzip files;
round-trip byte hashes agree with the recorded numerical outputs. Raw generated
JSON remains local and can be restored using `archive_full_reports.py --restore`.

The [SSD space review](ssd-space-review.md) identifies about 4.92 GiB of candidates
without deleting anything. The failed SSD parent still holds 10.47 GiB of arrays
linked by the current analysis and must not be removed as a whole.

## Implementation and recovery history

The dated records below preserve intermediate steps and interrupted attempts;
the completed run and review identified above supersede their pending statuses.

`resample_flight` now refines each temporal/mandatory segment by finite altitude
support. Separation greater than `g_max` splits the full trajectory; intermediate
horizontal fixes are excluded. Missing-altitude prefixes and suffixes are excluded
without endpoint extension. Unsupported spans remain rejected candidates in the
segment table, preserving the accounting of input fixes. Supported candidates retain
the parent clock/origin and pass the normal segment gates.

The boundary tests cover exact equality and exceedance at 1, 5 and 15 second cadences,
short-hole reconstruction masks, missing endpoints, an isolated finite reading,
mandatory boundaries inside a missing run, segment rejection and censoring. A smoothing
test now places its short missing reading inside the segment: missing terminal altitude
is intentionally excluded by the new policy.

Before rebuilding, raw flight `20171597` was independently processed through the new
pipeline. Its formerly reconstructed interval at parent times 6806–7449 s is now a
rejected incomplete candidate. Supported segments end at 6805 s and start at 7450 s;
the flight remains retained and its longest remaining reconstruction run is 1 s.
The previous saved maximum for that flight was 644 s.

`before.json` records the previous mounted archive's aggregate counts. The initial
combined rebuild `20260911T160003Z-b26eb528` failed on SSD disconnection. Standalone
cleaning subsequently completed on both archives. The first downstream run stopped
at a source-identity guard after concurrent manuscript edits. The downstream run `20260911T213634Z-7b7367f1`, under
`/Volumes/SSD_DISANTE/derived-audit/runs/`, stopped on another SSD disconnection
during stage 24 after 23 completed stages. Its final completion and manuscript
review remain pending; the recovery procedure below preserves the completed work. An isolated continuation attempt correctly refused to run while
this pipeline held the rebuild lock. See `work-in-progress.md` for coordination.
The rebuild includes local cleaning/documentation changes already present when this
task began; before/after archive differences are not an isolated causal estimate of
the vertical-gap rule alone.

Validation before rebuilding: the complete suite passed (851 tests; see `tests.log`).
The documentation built with `uv run --locked --isolated --extra docs mkdocs build
--strict`. The isolated environment kept the running rebuild environment unchanged.

Post-run manuscript review must check the quantitative claims about controlled
quantile ordering and ratios in Chapter 3, the final HMM likelihood gains and examples
in Chapter 4, current population counts, and the README annotation-pack link.

## SSD interruption and restart

The combined run failed after reporting 185,000 processed paraglider files: the
external SSD disconnected during a Parquet write (`errno 6`, then `errno 5`). Its
manifest failure status was recovered after reconnection; the untouched original
manifest and captured traceback are preserved here. At that failure, the interrupted
paraglider fix table had no readable footer and `.run_incomplete` remained present.
No derived output from that interrupted attempt was certified. Both raw archives
and catalogues remained intact (see `ssd-reconnection.json`); the existing hang-glider
table had not been touched. The successful standalone retry has since replaced the
derived tables and removed the incomplete markers on both archives.

Other working-tree edits occurred during the long run, outside the preprocessing
implementation. Cleaning was therefore retried with the standalone cleaner,
8 workers and one native thread each, with a local `cleaning-retry.log` and an idle
sleep assertion. After its successful completion, the complete downstream rebuild
was started without `--clean` against stable numerical/manuscript sources. This still
redoes every requested stage; it avoids tying the expensive cleaning pass to
concurrent chapter edits.

## Full Chapter 3 and joint-law review (in progress)

The default 10–10000 s reporter now streams all eligible flights and every eligible
segment, including flights crossing storage row groups. Full pools are backed by
disk, with bounded parallel flight workers; `--sample` is explicit development mode.
The fixed population is all eligible flights with at least one 20000 s segment.
Every increment and common-origin stencil stays in a single retained segment.
Full-cache summaries reference their backing arrays instead of pickling them.
Component TAMSD curves and duration cohorts share FFT results. Whole-flight
bootstrap quantiles use exact sorted-block counts; no origin subsampling was added.

Signed joint histograms at six lags now complement |E|, |N| and R. Their fixed
binning, tail cells, weights and scalar normalization are recorded. These are
resolution-dependent descriptive diagnostics, not calibrated iid tests or proof
of full process self-similarity. The thesis and guide include the exact
same-E/N/R/different-joint counterexample and primary literature on Cramér–Wold,
energy distance and operator self-similarity.

Validation so far: 149 observable/transport tests passed; an additional end-to-end
report smoke test renders the joint and marginal figures from disk-backed,
multiple-segment synthetic flights. Full archive execution follows the completed cleaning.
The full rebuild plan now calls `transport_full`; it will regenerate every product.

Full verification: 870 tests passed (223.27 s); strict MkDocs build passed.
Synthetic bootstrap benchmark: 996140 origins, 1000 flights, 401 draws, one coordinate
in 1.63 s while cleaning ran. This is not an archive-runtime estimate.
Full cache reads reject an `.incomplete` marker after interrupted collection or measurement.


Cleaning completed on both archives: 156406/186052 paraglider flights and 6094/6716
hang-glider flights retained. An additional audit initially used an invalid invariant
(`z_gap_max_s <= g_max_s`): the former counts consecutive nearest-fix flags on the
output grid, not finite-source spacing. Four flagged runs exceeded 20 s (24–30 s).
Each was reprocessed from raw data and every output point's finite-altitude bracket
was checked independently: maximum actual spans were 16 or 20 s, all within bound.
See `flagged-support-audit.json`; a deterministic irregular-grid regression test
pins this distinction. No preprocessing source was changed after the completed run.

The full structural verifier passed on both new archives. The downstream workflow
subsequently stopped during `transport_full` in run `20260911T213634Z-7b7367f1`.
The final strict MkDocs build also passed after the flag-run clarification.

## Review evidence and remaining presentation work

[Regional interpretation review](regional-interpretation-review.md) retains the
proposed equipment/wind/terrain explanation and records its mathematical and
observational limitations. It is the input for both the thesis discussion and the
supervisor slides; its conditional statements are not claims that the new regional
plots have already confirmed the old pattern. The planned Chapter 3 revision
separates distributional rescaling from regional/environment/equipment comparisons.
The two blocks must distinguish increment lag, time since takeoff, weighting and
centering.

[Paired PSD audit](paired-psd-audit.json) identifies the newly generated spectral
caches and checks paired channel arrays, high-frequency floors and their tails.
The diagnostic uses raw paired blocks with linear resampling and Welch detrending,
not the pipeline's Savitzky–Golay output. Similar medians do not imply identical
between-flight distributions or identical per-flight channel spectra.

After the relevant fresh stages complete, run:

```bash
.venv/bin/python revisions/vertical-gap-split-2026-09-11/audit_regional_contrasts.py \
  --run /Volumes/SSD_DISANTE/derived-audit/runs/20260911T213634Z-7b7367f1
.venv/bin/python revisions/vertical-gap-split-2026-09-11/audit_full_chapter3.py \
  --run /Volumes/SSD_DISANTE/derived-audit/runs/20260911T213634Z-7b7367f1
```

Both reject stale or unfinished inputs. The regional extraction is descriptive,
not a significance test. Final numerical reconciliation, chapter reorganization,
complete Chapter 2/3 supervisor decks, reviewed compilation and local commits remain
pending until the full numerical recovery finishes. The supplementary trimming
census has completed and reproduced both caches and all three generated outputs
exactly; see `trimming-refresh.json`.

The [controlled PSD comparison](psd-selection-comparison.json), produced by
[compare_psd_selection.py](compare_psd_selection.py), isolates the earlier whole-trace
selection rule from the current paired-valid-block rule. Both use the same raw
sample, current decoder and Welch estimator; the current spectra reproduce the
fresh canonical caches. Even on the same 2008 flights, the GNSS per-flight
high-frequency-floor 90th percentile changes from 3.758 to 0.590 m²/Hz. This is
an interval-selection sensitivity, not an effect of Savitzky–Golay smoothing or a
measurement of a change in physical sensor noise. Raw input hashes are recorded.


## Second SSD interruption: validated continuation

`ssd-disconnection-20260912.json` and its companion log preserve the SIGBUS failure
of the Chapter 3 reporter. The cleaner had already completed and this stage was
only reading the canonical cleaned tables. The absence of a final error write on
the disconnected SSD left the parent manifest reporting `running`; that status is
stale. Data integrity after remount must be checked before reuse.

`resume_after_ssd_disconnect.py --prepare` requires the original source, cleaning
configuration, dataset identity and full measurement contract. It copies position
arrays, metadata and completed-stage logs internally, hashes every reused input,
checks binary sizes, finite values, owner ordering and segment indices, and compares
saved increments against positions for 25 spaced flights plus the longest flight at
every lag. Baseline increment pools remain read-only links to the SSD; bootstrap
coordinates and new display arrays, logs and manifests use the internal disk.
The space check includes six full display arrays per discipline and a reserve.

`--run` reacquires exclusive locks, rechecks every staged input hash, and repeats
`scripts/verify_dataset.py` on the full cleaned archive before executing stages
24–39. It calls the unchanged canonical Chapter 3 reporter with `--reuse`.
The original parent manifest bytes are preserved; after archive verification, its
stale running status is explicitly changed to failed with a link to the recovery.
A failed recovery records its failure locally. The in-memory partial bootstrap
calculations from the interrupted process must be recomputed.

Run from the repository root, after the SSD is mounted:

```bash
caffeinate -im .venv/bin/python -u   revisions/vertical-gap-split-2026-09-11/resume_after_ssd_disconnect.py --prepare
caffeinate -im .venv/bin/python -u   revisions/vertical-gap-split-2026-09-11/resume_after_ssd_disconnect.py --run
```

The two commands are sequential. The run path is recorded in `recovery-run.json`;
use that path for the final Chapter 3 audit and manuscript review, rather than the
interrupted parent's path above. `caffeinate -im` prevents idle system/disk sleep;
it does not establish or resolve the cause of a physical disconnection.

Local fault injection in `test_recovery_integrity.py` passes ten cases covering
segmented increments, truncated/appended pools, a finite cross-gap increment,
non-finite coordinates, corrupt owners/segment metadata, incomplete stores, changed
staged bytes and redirected links. These tests do not certify the SSD; the real
preparation and full structural verification remain required.
