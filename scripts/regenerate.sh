#!/usr/bin/env bash
# Compatibility entry point; use --clean to rebuild from raw IGC files too.
# The Python driver checks provenance and regenerates Chapters 2, 3 and 4.
set -euo pipefail
cd "$(dirname "$0")/.."
exec "${PY:-.venv/bin/python}" scripts/rebuild_thesis.py "$@"
