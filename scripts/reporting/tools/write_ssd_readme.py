#!/usr/bin/env python3
"""Generate the SSD README from directories, file sizes and Parquet metadata.

The inventory never reads trajectory values or changes data. Unknown directories
are listed without inspecting their contents. Run after a completed rebuild.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "src"))
from soaring.reporting import DISCIPLINES  # noqa: E402

_TABLES = {
    "fixes.parquet": "retained trajectories on each flight's native-rate grid",
    "flights_meta.parquet": "every attempted flight, decisions and stage counters",
    "segments.parquet": "retained and rejected segments, with coverage diagnostics",
    "suspect_intervals.parquet": "flagged slow/flat intervals; the proposed waiting-time sensitivity analysis is not implemented",
    "track_scan.parquet": "raw per-flight census cache",
    "alt_offset_scan.parquet": "sampled paired altitude offsets",
    "fixlevel_scan.parquet": "streamed raw diagnostic values",
    "psd_sample.npz": "paired-channel raw altitude PSD sample and its selection policy",
    "savgol_psd_sample.npz": "raw horizontal and vertical PSD samples used to discuss smoothing",
    "run_manifest.json": "cleaning definition, completion state and identities of all four cleaned tables",
    ".run_incomplete": "cleaning is unfinished: do not use the four tables as a complete dataset",
    ".preprocess.lock": "advisory lock file; its presence alone does not mean a process is running",
}


def _human(size):
    size = float(size)
    for unit in ("B", "KiB", "MiB", "GiB", "TiB"):
        if size < 1024 or unit == "TiB":
            return f"{size:.0f} {unit}" if unit == "B" else f"{size:.1f} {unit}"
        size /= 1024
    raise AssertionError("unreachable")


def _tree_size(path):
    """Count regular files without following symlinks or counting AppleDouble copies."""
    total = count = 0
    if path.is_dir():
        for directory, _, files in os.walk(path, followlinks=False):
            for name in files:
                item = Path(directory) / name
                if name.startswith("._") or item.is_symlink():
                    continue
                total += item.stat().st_size
                count += 1
    return total, count


def _rows(path):
    if path.suffix != ".parquet":
        return "—"
    import pyarrow.parquet as pq

    try:
        return f"{pq.read_metadata(path).num_rows:,}"
    except (OSError, ValueError):
        return "unreadable / incomplete"


def _files(directory):
    return sorted(
        (p for p in directory.iterdir() if p.is_file() and not p.name.startswith("._")),
        key=lambda p: p.name,
    )


def _describe(discipline):
    glider = DISCIPLINES[discipline]
    cfg = glider.config()
    root = cfg.data_root
    lines = [
        f"## {discipline.capitalize()}",
        "",
        f"Root: `{root}`.",
        "",
        "| Directory | Files | Size | Contents |",
        "|---|---:|---:|---|",
    ]
    descriptions = {
        "raw": "downloaded IGC tracks and original season XML; preserve and back up",
        "catalog": "catalogue reconstructed from source XML, with acquisition state",
        "derived": "cleaned tables, diagnostic caches and fitted segmentation products",
        "logs": "acquisition logs",
    }
    for directory in sorted(root.iterdir()):
        if not directory.is_dir() or directory.name.startswith("."):
            continue
        if directory.name in descriptions:
            size, count = _tree_size(directory)
            lines.append(
                f"| `{directory.name}/` | {count:,} | {_human(size)} | {descriptions[directory.name]} |"
            )
        else:
            lines.append(
                f"| `{directory.name}/` | — | — | additional directory; contents not inspected |"
            )
    lines += [
        "",
        "The actual raw-data subdirectories are: "
        + ", ".join(
            f"`raw/{p.name}/`" for p in sorted((root / "raw").iterdir()) if p.is_dir()
        )
        + ".",
        "",
    ]
    derived = cfg.derived_dir
    if not derived.exists():
        return lines + ["No processed tables are present.", ""]
    incomplete = (derived / ".run_incomplete").exists()
    manifest_path = derived / "run_manifest.json"
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text())
        version = manifest.get("cleaning", {}).get("pipeline_version", "unknown")
        status = "unfinished" if incomplete else manifest.get("status", "unknown")
        lines += [
            f"Cleaning manifest: **{status}**, pipeline **{version}**. "
            f"Run identifier: `{manifest.get('run_id', 'not recorded')}`.",
            "",
        ]
    elif incomplete:
        lines += [
            "**Cleaning is unfinished.** The tables are not a complete snapshot.",
            "",
        ]
    else:
        lines += [
            "No cleaning manifest is present; completeness and source agreement are unverified.",
            "",
        ]
    lines += [
        "### Files directly in `derived/`",
        "",
        "| File | Rows | Size | Purpose |",
        "|---|---:|---:|---|",
    ]
    for path in _files(derived):
        rows = (
            "in progress"
            if incomplete
            and path.name
            in {
                "fixes.parquet",
                "flights_meta.parquet",
                "segments.parquet",
                "suspect_intervals.parquet",
            }
            else _rows(path)
        )
        lines.append(
            f"| `{path.name}` | {rows} | {_human(path.stat().st_size)} | {_TABLES.get(path.name, 'additional generated file; inspect its metadata before reuse')} |"
        )
    lines += ["", "### Subdirectories of `derived/`", ""]
    for directory in sorted(derived.iterdir()):
        if not directory.is_dir() or directory.name.startswith("."):
            continue
        lines += [f"`{directory.name}/`", ""]
        if directory.name == "segmentation":
            lines += [
                "Fitted HMMs, their training provenance, decoded phase products and coverage. "
                "These require `segment_flights.py train`, `apply` and `coverage`; cleaning alone does not regenerate them.",
                "",
            ]
        lines += ["| File | Rows | Size |", "|---|---:|---:|"]
        for path in _files(directory):
            lines.append(
                f"| `{path.name}` | {_rows(path)} | {_human(path.stat().st_size)} |"
            )
        for child in sorted(directory.iterdir()):
            if child.is_dir() and not child.name.startswith("."):
                lines.append(f"| `{child.name}/` | — | directory |")
        lines.append("")
    return lines


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("/Volumes/SSD_DISANTE"))
    args = parser.parse_args(argv)
    if not args.root.is_dir():
        parser.error(f"Data disk is not mounted: {args.root}")
    # Reject a misleading inventory of configured archives outside the requested disk.
    for glider in DISCIPLINES.values():
        if not glider.config().data_root.resolve().is_relative_to(args.root.resolve()):
            parser.error(f"{glider.name} data root is outside {args.root}")
    lines = [
        "# Soaring flight data",
        "",
        "External data for `matteodisante/soaring-anomalous-transport`. This inventory is generated "
        "from the mounted disk by `scripts/reporting/tools/write_ssd_readme.py`.",
        "",
        f"Generated {datetime.now().astimezone().isoformat(timespec='seconds')}.",
        "",
        "## Disk root",
        "",
        "| Entry | Purpose |",
        "|---|---|",
    ]
    known = {
        "paragliders": "paraglider archive",
        "hang_gliders": "hang-glider archive",
        "derived-audit": "analysis arrays, audit logs and rebuild manifests",
        "README.md": "this generated inventory",
    }
    for path in sorted(args.root.iterdir()):
        if path.name.startswith("."):
            continue
        label = path.name + ("/" if path.is_dir() else "")
        lines.append(
            f"| `{label}` | {known.get(path.name, 'outside the thesis data workflow; contents not inspected')} |"
        )
    lines += [
        "",
        "Hidden macOS indexing, trash and filesystem directories are omitted.",
        "",
        "## Connecting the repository",
        "",
        "Default paths are in `configs/para_download.yaml` and `configs/delta_download.yaml`. "
        "Environment variables override them when the disk mounts elsewhere:",
        "",
        "```bash",
        f"export SOARING_PARA_DATA_ROOT='{DISCIPLINES['paragliders'].config().data_root}'",
        f"export SOARING_DELTA_DATA_ROOT='{DISCIPLINES['hang gliders'].config().data_root}'",
        "```",
        "",
        "Preserve raw downloads, catalogues containing acquisition state, human labels and run records. "
        "Cleaned tables can be regenerated from the raw tracks with the recorded code, configuration and dependencies. "
        "Diagnostic caches, transport arrays and segmentation need their respective reporting and fitting steps. "
        "The complete sequence is `uv run python scripts/rebuild_thesis.py --clean --jobs 8 --full-speed`.",
        "",
        "Schema and mathematical conventions: `docs/guide/data-on-disk.md`, "
        "`docs/guide/preprocessing-pipeline.md` and `docs/guide/rebuilding.md` in the repository.",
        "",
    ]
    for discipline in DISCIPLINES:
        lines += _describe(discipline)
    audit = args.root / "derived-audit"
    if audit.is_dir():
        lines += [
            "## `derived-audit/`",
            "",
            "Intermediate arrays are inputs to figure and table generators. They depend on a specific "
            "cleaned archive and must not be mixed across cleaning runs. `runs/<run-id>/` contains "
            "fresh `arrays/`, one log per stage and `manifest.json`. A completed manifest records "
            "source and table identities, generated-output hashes and the built PDF hash. "
            "`cleaning/` holds standalone cleaning logs. Older arrays outside `runs/` are not "
            "evidence that the current thesis was rebuilt.",
            "",
            "Actual entries:",
            "",
        ]
        lines += [
            f"- `{p.name}{'/' if p.is_dir() else ''}`"
            for p in sorted(audit.iterdir())
            if not p.name.startswith(".")
        ]
        run_root = audit / "runs"
        if run_root.is_dir():
            lines += ["", "| Rebuild run | State at inventory time |", "|---|---|"]
            for path in sorted(run_root.glob("*/manifest.json")):
                manifest = json.loads(path.read_text())
                lines.append(
                    f"| `{path.parent.name}` | {manifest.get('status', 'unknown')} |"
                )
        lines.append("")
    lines += [
        "## Reading trajectories",
        "",
        "Stream `fixes.parquet`; storage row groups can split a flight. This reader restores complete flights:",
        "",
        "```python",
        "from soaring.analysis.derived import stream_flights",
        "",
        "for flight in stream_flights(root / 'derived' / 'fixes.parquet',",
        "                             ['segment_id', 't', 'E', 'N']):",
        "    ...",
        "```",
        "",
        "Time is elapsed from the trimmed flight origin. Segments retain their parent's clock and local "
        "east–north frame. Form increments within one retained segment. The quality flags distinguish "
        "missing-position interpolation, reconstructed altitude, affected vertical derivatives and filter edges.",
        "",
        "Manual annotation packs live in the repository under `annotations/phase_labeling/`, "
        "with their source provenance. They are not reproduced by cleaning and human labels must be preserved.",
        "",
    ]
    out = args.root / "README.md"
    temporary = out.with_suffix(".md.tmp")
    temporary.write_text("\n".join(lines) + "\n")
    temporary.replace(out)
    print(f"Wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
