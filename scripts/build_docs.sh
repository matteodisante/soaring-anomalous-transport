#!/usr/bin/env bash
# Build the project documents.
#
#   scripts/build_docs.sh stats      # regenerate acquisition statistics only
#   scripts/build_docs.sh thesis     # compile existing thesis inputs (default)
#   scripts/build_docs.sh clean      # remove LaTeX aux files
#
# This convenience compiler does not validate numerical freshness or record a
# manuscript review. Use rebuild_thesis.py/review_thesis.py for the audited workflow.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

# Pin metadata to the latest commit; without Git, use the current time. This is
# not a promise of identical PDF bytes across different commits or environments.
export SOURCE_DATE_EPOCH="$(git -C "$ROOT" log -1 --format=%ct 2>/dev/null || date +%s)"

LATEXMK_OPTS=(-pdf -quiet -interaction=nonstopmode -halt-on-error)

gen_stats() { python3 scripts/reporting/ch2_dataset/generate_stats.py; }

build_thesis() {
    ( cd thesis  && latexmk "${LATEXMK_OPTS[@]}" main.tex )
    echo "Built thesis/main.pdf"
}

case "${1:-thesis}" in
    stats)    gen_stats ;;
    thesis)   build_thesis ;;
    clean)
        ( cd thesis  && latexmk -C main.tex    >/dev/null 2>&1 || true )
        echo "Cleaned LaTeX aux files." ;;
    *) echo "usage: $0 {stats|thesis|clean}" >&2; exit 2 ;;
esac
