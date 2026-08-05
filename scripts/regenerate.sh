#!/usr/bin/env bash
# Regenerate everything that descends from the processed dataset, in the one order that
# is correct, after `scripts/preprocess.py` has finished.
#
# It exists because the ordering is a real constraint and getting it wrong is silent. The
# generators read `<data_root>/derived/`, which `preprocess.py` rewrites in place and only
# completes at the end of each discipline: `flights_meta.parquet` and `segments.parquet`
# are written after the last flight, so while a run is in flight the disk holds a partial
# `fixes.parquet` beside metadata from the *previous* run. Reading that produces numbers
# that are wrong and look fine. It happened once, and the guard below is the answer.
#
# The order itself:
#   1. verify   -- check the tables against the invariants of Ch. 2 before anything is
#                  derived from them. A failure here invalidates everything downstream,
#                  so it comes first and stops the script.
#   2. census   -- the \StatPipe* macros and the cascade table, from flights_meta.
#   3. MSD      -- the figure, the curve CSV and the \StatMsd* macros. The long one
#                  (~20 min on the paraglider archive), since it streams every fix.
#   4. scan     -- the \StatScan* and \Preproc* macros, from the cached raw-archive scan.
#                  Independent of the run, but re-exported here so a threshold edit in
#                  the YAML reaches the thesis in the same pass.
#   5. audit    -- one more streaming pass, keeping each flight's position at every lag
#                  instead of only the average over flights. It is what lets the audit
#                  ask whether the averaged curve's shape survives a fixed cadence, a
#                  fixed duration and the removal of the common heading -- questions the
#                  averaged curve cannot be asked after the fact. Comparable in cost to
#                  step 3.
#   6. report   -- the \StatAudit* macros, reduced from step 5 and from the curve CSV.
#   7. prelim   -- Sec. 2.8: the retained-ensemble figures and the \StatPrelim* macros.
#                  Reads step 5's arrays, not the fix table, which is what makes a
#                  stratified MSD a row selection rather than another 43 GB scan.
#   8. dataset  -- the discard cascade with its running remainder, and the survivors
#                  per season. Reads flights_meta and the catalogue; seconds.
#   9. variations -- the third full traversal, keeping one filtered-variation curve per
#                  flight per filter order. ~25 min. It is what lets step 10 stratify by
#                  cadence, wing class, season and task without touching the fix table.
#  10. transport -- Chapter 3's measurement: the order scan, its uncertainty, the
#                  stratifications and the regime fit. Minutes.
#  11. shape    -- the third traversal: the increments themselves, for the moment
#                  spectrum, the velocity memory and the persistence runs. The longest
#                  step by far: ~2.5 h on the paraglider archive, since the persistence
#                  runs are decomposed per segment at three thresholds.
#  12. shapefig -- their reduction into tab:shape and \StatShape*. Not instant like the
#                  other reductions: the Clauset-Shalizi-Newman cut-off scans every
#                  distinct run length as a candidate and measures a KS distance on the
#                  tail at each, which on the paragliders' ~3e6 runs is ~15 min. The scan
#                  is exact and the cost is the price of not choosing the cut-off by eye.
#  13. propagator -- the fourth traversal: histograms of the increments per lag, per
#                  component and per native cadence, from which the exponent is read off the
#                  bulk rather than off a moment, and the scaling collapse is tested rather
#                  than assumed. Twelve minutes over both archives: histograms only, no
#                  per-segment decomposition, which is what makes it the cheap traversal.
#  14. contract -- every macro the thesis quotes must now exist. An undefined one inside
#                  \SI{} is a *fatal* LaTeX error, not a warning, so this runs before the
#                  build and its failure is the useful message.
#  15. build    -- the thesis.
#
# Usage:
#   SOARING_PARA_DATA_ROOT=... SOARING_DELTA_DATA_ROOT=... scripts/regenerate.sh [--no-build]
set -euo pipefail

cd "$(dirname "$0")/.."
PY=${PY:-.venv/bin/python}
export PYTHONPATH=src
# The audit pass writes one row per flight and one column per lag -- a few hundred MB per
# discipline, an analysis product rather than a thesis one, so it lives outside the repo.
AUDIT_DIR=${AUDIT_DIR:-${TMPDIR:-/tmp}/soaring-audit}

if pgrep -f "scripts/preprocess.py" >/dev/null 2>&1; then
    echo "refusing to run: scripts/preprocess.py is still writing to the SSD." >&2
    echo "The derived tables are incomplete until it finishes; wait for it." >&2
    exit 1
fi

step() { printf '\n=== %s ===\n' "$1"; }

step "1/16  invariants (verify_dataset.py)"
"$PY" scripts/verify_dataset.py

step "2/16  pipeline census -> StatPipe*, tab:pipecensus"
"$PY" scripts/reporting/generate_pipeline_census.py

step "3/16  MSD -> fig:msd, msd_curve.csv, StatMsd*   (the slow one)"
"$PY" scripts/reporting/generate_msd_figure.py

step "4/16  raw-archive census -> StatScan*, Preproc*"
"$PY" scripts/reporting/generate_census_stats.py

step "5/16  MSD audit pass -> per-flight positions at every lag"
"$PY" scripts/reporting/audit_msd.py --out "$AUDIT_DIR"

step "6/16  audit report -> StatAudit*"
"$PY" scripts/reporting/audit_msd_report.py --audit-dir "$AUDIT_DIR"

step "7/16  preliminary characterization -> fig:prelim-*, StatPrelim*"
"$PY" scripts/reporting/generate_prelim_figure.py --audit-dir "$AUDIT_DIR"

step "8/16  dataset statistics -> tab:cascade, fig:seasons, StatData*"
"$PY" scripts/reporting/generate_dataset_stats.py

step "9/16  filtered variations -> per-flight curves, one per filter order"
"$PY" scripts/reporting/measure_variations.py --out "$AUDIT_DIR"

step "10/16  transport measurement -> tab:orderscan, fig:transport, StatVar*"
"$PY" scripts/reporting/generate_transport_figure.py --audit-dir "$AUDIT_DIR"

step "11/16  shape pass -> increments, velocity memory, persistence runs"
"$PY" scripts/reporting/measure_shape.py --out "$AUDIT_DIR"

step "12/16  shape measurement -> tab:shape, fig:shape, StatShape*"
"$PY" scripts/reporting/generate_shape_figure.py --audit-dir "$AUDIT_DIR"

step "13/16  propagator -- the increments themselves, for the exponent read off the bulk"
"$PY" scripts/reporting/measure_propagator.py --out "$AUDIT_DIR"
"$PY" scripts/reporting/generate_propagator_figure.py --audit-dir "$AUDIT_DIR"

step "14/16  edge-sample effect -> StatEdge*, the size of what the MSD reads and the verifier does not"
"$PY" scripts/reporting/measure_edge_effect.py

step "15/16  macro contract: everything the thesis quotes must exist"
"$PY" scripts/reporting/check_generated_macros.py

if [[ "${1:-}" == "--no-build" ]]; then
    echo $'\nskipping the thesis build (--no-build).'
    exit 0
fi

step "16/16  thesis"
cd thesis && latexmk -pdf -interaction=nonstopmode main.tex >/dev/null
echo "built thesis/main.pdf"
