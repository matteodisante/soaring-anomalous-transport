#!/usr/bin/env bash
# Build the project documents.
#
#   scripts/build_docs.sh stats      # regenerate thesis/generated/*.tex from the data
#   scripts/build_docs.sh thesis     # stats + compile thesis/main.pdf  (public, default)
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

gen_stats() { python3 scripts/reporting/ch2_dataset/generate_stats.py; }

build_thesis() {
    gen_stats
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
