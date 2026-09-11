#!/bin/bash
# Open the existing Python viewer from this checkout, without rebuilding the archive.
set -euo pipefail
talk_dir="$(cd -- "$(dirname -- "$0")" && pwd)"
repo_dir="$(cd -- "$talk_dir/.." && pwd)"
viewer_python="$repo_dir/.venv/bin/python"
export PYTHONPATH="$repo_dir/src${PYTHONPATH:+:$PYTHONPATH}"
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
export VECLIB_MAXIMUM_THREADS=1 NUMEXPR_NUM_THREADS=1

if [[ ! -x "$viewer_python" ]]; then
  printf '%s\n' 'Missing repository .venv. From the repo, run: uv sync --group viewer' >&2
  exit 1
fi
"$viewer_python" -c 'import PyQt6.QtWidgets, soaring.viewer.app'
if [[ "${1:-}" == "--check" ]]; then
  printf '%s\n' 'Viewer dependencies and repository import are available.'
  exit 0
fi

if [[ -f "$talk_dir/viewer-link.pid" ]]; then
  previous_pid="$(cat "$talk_dir/viewer-link.pid")"
  if [[ "$previous_pid" =~ ^[0-9]+$ ]] && kill -0 "$previous_pid" 2>/dev/null; then
    previous_command="$(ps -p "$previous_pid" -o command=)"
    if [[ "$previous_command" == *"soaring.viewer.app"* ]]; then
      printf '%s\n' 'The viewer launched from these slides is already running.'
      exit 0
    fi
  fi
fi
cd -- "$repo_dir"
printf '%s\n' "$$" > "$talk_dir/viewer-link.pid"
exec "$viewer_python" -m soaring.viewer.app >> "$talk_dir/viewer-link.log" 2>&1
