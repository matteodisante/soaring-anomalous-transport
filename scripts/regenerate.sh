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
#  11. shape    -- the fourth traversal: the increments themselves, for the moment
#                  spectrum and the velocity memory. A full pass over the fix table.
#  12. shapefig -- their reduction into tab:shape and \StatShape*: the tail exponent of
#                  the autocorrelation, and the matched Gaussian null the non-Gaussianity
#                  is read against.
#  13. propagator -- the fifth traversal: histograms of the increments per lag, per
#                  component and per native cadence, from which the exponent is read off the
#                  bulk rather than off a moment, and the scaling collapse is tested rather
#                  than assumed. Twelve minutes over both archives: histograms only, no
#                  per-segment decomposition, which is what makes it the cheap traversal.
#  14. edge     -- the sixth traversal, and the only subsampled one: the ensemble MSD
#                  computed twice on the same flights, once over all samples and once over
#                  interior ones, to measure what the edge-flagged samples do to the curve
#                  rather than assert it. A subsample suffices because the effect is a
#                  property of the segment ends, which every flight has.
#  15. circling -- the velocity autocorrelation at native cadence on the 1 Hz segments. The
#                  shape pass evaluates every integer lag and then keeps only its geometric
#                  grid, whose floor is 60 s, so the circling period at ~21 s falls below the
#                  first lag it retains. Cheap: one histogram-free average over a subsample.
#  16. contract -- every macro the thesis quotes must now exist. An undefined one inside
#                  \SI{} is a *fatal* LaTeX error, not a warning, so this runs before the
#                  build and its failure is the useful message.
#  17. build    -- the thesis.
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

# The pgrep above catches a run that is still going. This catches the worse case: one that
# died halfway and left no process behind, so the tables disagree about which run they
# describe and nothing is around to say so.
for root in "${SOARING_PARA_DATA_ROOT:-}" "${SOARING_DELTA_DATA_ROOT:-}"; do
    if [[ -n "$root" && -f "$root/derived/.run_incomplete" ]]; then
        echo "refusing to run: $root/derived/ is from an unfinished preprocess.py run." >&2
        cat "$root/derived/.run_incomplete" >&2
        echo "Re-run scripts/preprocess.py for that archive; the marker clears itself." >&2
        exit 1
    fi
done

step() { printf '\n=== %s ===\n' "$1"; }

step "1/17  invariants (verify_dataset.py)"
"$PY" scripts/verify_dataset.py

step "2/17  pipeline census -> StatPipe*, tab:pipecensus"
"$PY" scripts/reporting/generate_pipeline_census.py

step "3/17  MSD -> fig:msd, msd_curve.csv, StatMsd*   (the slow one)"
"$PY" scripts/reporting/generate_msd_figure.py

step "4/17  raw-archive census -> StatScan*, Preproc*"
"$PY" scripts/reporting/generate_census_stats.py

step "5/17  MSD audit pass -> per-flight positions at every lag"
"$PY" scripts/reporting/audit_msd.py --out "$AUDIT_DIR"

step "6/17  audit report -> StatAudit*"
"$PY" scripts/reporting/audit_msd_report.py --audit-dir "$AUDIT_DIR"

step "7/17  preliminary characterization -> fig:prelim-*, StatPrelim*"
"$PY" scripts/reporting/generate_prelim_figure.py --audit-dir "$AUDIT_DIR"

step "8/17  dataset statistics -> tab:cascade, fig:seasons, StatData*"
"$PY" scripts/reporting/generate_dataset_stats.py

step "9/17  filtered variations -> per-flight curves, one per filter order"
"$PY" scripts/reporting/measure_variations.py --out "$AUDIT_DIR"

step "10/17  transport measurement -> tab:orderscan, fig:transport, StatVar*"
"$PY" scripts/reporting/generate_transport_figure.py --audit-dir "$AUDIT_DIR"

step "11/17  shape pass -> increments and velocity memory"
"$PY" scripts/reporting/measure_shape.py --out "$AUDIT_DIR"

step "12/17  shape measurement -> tab:shape, fig:shape, StatShape*"
"$PY" scripts/reporting/generate_shape_figure.py --audit-dir "$AUDIT_DIR"

step "13/17  propagator -- the increments themselves, for the exponent read off the bulk"
"$PY" scripts/reporting/measure_propagator.py --out "$AUDIT_DIR"
"$PY" scripts/reporting/generate_propagator_figure.py --audit-dir "$AUDIT_DIR"

step "14/17  edge-sample effect -> StatEdge*, the size of what the MSD reads and the verifier does not"
"$PY" scripts/reporting/measure_edge_effect.py

step "15/17  circling -> StatCircling*, the VACF at native cadence, below the shape pass's grid"
"$PY" scripts/reporting/measure_circling.py

step "16/17  macro contract: everything the thesis quotes must exist"
"$PY" scripts/reporting/check_generated_macros.py
"$PY" scripts/reporting/generate_provenance.py

if [[ "${1:-}" == "--no-build" ]]; then
    echo $'\nskipping the thesis build (--no-build).'
    exit 0
fi

step "17/17  thesis"
cd thesis && latexmk -pdf -interaction=nonstopmode main.tex >/dev/null
echo "built thesis/main.pdf"
