"""Reproduce Chapter 3 from cleaned data, or redraw directly from saved results."""

from __future__ import annotations

# ruff: noqa: E402
import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))
from audit_ch3_inputs import signature

from soaring.analysis.observables.archive_diagnostics import collect_archive
from soaring.analysis.observables.global_diagnostics import declared_task_class
from soaring.reporting import DISCIPLINES


def run(name, *args):
    """Execute each checked stage with the active Python environment."""
    subprocess.run(
        [sys.executable, str(HERE / name), *map(str, args)], check=True, cwd=ROOT
    )


def main():
    """Keep full measurement and colour/layout-only redraw separate."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, required=True)
    parser.add_argument("--reuse-coordinates", type=Path)
    parser.add_argument("--redraw", action="store_true")
    parser.add_argument(
        "--conditional-out",
        type=Path,
        help="Also measure/redraw Section 3.2 in this separate output directory",
    )
    parser.add_argument("--publish", type=Path, default=ROOT / "thesis/generated")
    args = parser.parse_args()
    if not args.redraw:
        coordinates = args.reuse_coordinates or args.data / "coordinates"
        for slug in ("para", "hang"):
            g = next(g for g in DISCIPLINES.values() if g.slug == slug)
            directory = coordinates / f"ch3-full-{slug}"
            if not (directory / "flights.json").exists():
                if args.reuse_coordinates:
                    raise FileNotFoundError(directory)
                if (directory / ".incomplete").exists():
                    raise RuntimeError(
                        "Interrupted coordinate collection; choose a fresh directory"
                    )
                _, provenance = collect_archive(
                    g, directory, {}, declared_task_class, signature
                )
                (directory / "collection.json").write_text(
                    json.dumps(provenance, indent=2) + "\n"
                )
                (directory / ".incomplete").unlink(missing_ok=True)
            out = args.data / slug
            if not (out / "native.npz").exists():
                run("prepare_ch3_native.py", "--out", args.data, "--discipline", slug)
            if not (out / "input-audit.json").exists():
                run(
                    "audit_ch3_inputs.py",
                    "--data",
                    args.data,
                    "--coordinates",
                    coordinates,
                    "--discipline",
                    slug,
                )
            run(
                "measure_ch3_fixed.py",
                "--out",
                args.data,
                "--coordinates",
                coordinates,
                "--discipline",
                slug,
            )
        run("summarize_ch3_fixed.py", "--data", args.data)
    run("render_ch3_fixed.py", "--data", args.data, "--publish", args.publish)
    if args.conditional_out:
        conditional_args = [
            "--out",
            args.conditional_out,
            "--publish",
            args.publish,
        ]
        if args.redraw or (args.conditional_out / "report.json").exists():
            conditional_args.append("--redraw")
        else:
            conditional_args.extend(["--data", args.data])
        run("conditional_ch3_transport.py", *conditional_args)


if __name__ == "__main__":
    main()
