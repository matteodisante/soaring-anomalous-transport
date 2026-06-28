#!/usr/bin/env bash
# Build the project documents.
#
#   scripts/build_docs.sh stats      # regenerate thesis/generated/*.tex from the data
#   scripts/build_docs.sh timeline   # regenerate logbook/generated/timeline.tex from git
#   scripts/build_docs.sh thesis     # stats + compile thesis/main.pdf  (public)
#   scripts/build_docs.sh logbook    # timeline + compile logbook/logbook.pdf  (private)
#   scripts/build_docs.sh all        # thesis + logbook  (default)
#   scripts/build_docs.sh clean      # remove LaTeX aux files
#
# PDFs are built reproducibly (stable bytes when content is unchanged), so the
# committed thesis PDF only changes when the document actually changes.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

# Fixed timestamp -> reproducible PDF metadata.
export SOURCE_DATE_EPOCH="$(git -C "$ROOT" log -1 --format=%ct 2>/dev/null || date +%s)"

LATEXMK_OPTS=(-pdf -quiet -interaction=nonstopmode -halt-on-error)

gen_stats()    { python3 scripts/reporting/generate_stats.py; }
gen_timeline() { python3 scripts/reporting/generate_timeline.py; }

build_thesis() {
    gen_stats
    ( cd thesis  && latexmk "${LATEXMK_OPTS[@]}" main.tex )
    echo "Built thesis/main.pdf"
}

build_logbook() {
    gen_timeline
    ( cd logbook && latexmk "${LATEXMK_OPTS[@]}" logbook.tex )
    echo "Built logbook/logbook.pdf"
}

case "${1:-all}" in
    stats)    gen_stats ;;
    timeline) gen_timeline ;;
    thesis)   build_thesis ;;
    logbook)  build_logbook ;;
    all)      build_thesis; build_logbook ;;
    clean)
        ( cd thesis  && latexmk -C main.tex    >/dev/null 2>&1 || true )
        ( cd logbook && latexmk -C logbook.tex >/dev/null 2>&1 || true )
        echo "Cleaned LaTeX aux files." ;;
    *) echo "usage: $0 {stats|timeline|thesis|logbook|all|clean}" >&2; exit 2 ;;
esac
