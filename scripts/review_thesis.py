#!/usr/bin/env python3
"""Compile a manuscript revision against an unchanged, completed numerical rebuild.

Use after interpreting fresh results. Numerical code, configurations, source tables and
all previously recorded generated results must still match the completed run. The
original manifest is preserved; a separate review record identifies the revised PDF.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import runpy
import shutil
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from soaring.reporting import DISCIPLINES  # noqa: E402
from soaring.reporting.snapshot import (  # noqa: E402
    current_cleaning,
    source_hash,
    validate_snapshot,
    write_json,
)

DRIVER = runpy.run_path(str(ROOT / "scripts/rebuild_thesis.py"))


def validate_results(root: Path, manifest: dict, required: set[str]) -> None:
    """Reject incomplete runs, numerical changes, new inputs and altered results."""
    if manifest.get("status") != "complete" or not manifest.get("pdf_sha256"):
        raise ValueError("A complete numerical rebuild with a compiled PDF is required")
    if DRIVER["numerical_source_hash"](root) != manifest.get("numerical_source_sha256"):
        raise ValueError("Numerical sources changed; a numerical rebuild is required")
    outputs = manifest.get("outputs", {})
    if not required.issubset(outputs):
        raise ValueError(
            "The manuscript uses results absent from the completed rebuild"
        )
    for name, record in outputs.items():
        path = root / "thesis/generated" / name
        if (
            not path.is_file()
            or hashlib.sha256(path.read_bytes()).hexdigest() != record["sha256"]
        ):
            raise ValueError(
                f"Generated result changed since the numerical rebuild: {name}"
            )


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--run", type=Path, required=True, help="completed run directory"
    )
    args = parser.parse_args(argv)
    run = args.run.resolve()
    path = run / "manifest.json"
    manifest = json.loads(path.read_text())
    required = set(DRIVER["required_outputs"]())
    validate_results(ROOT, manifest, required)
    cleaning = current_cleaning(ROOT)
    for name, discipline in DISCIPLINES.items():
        snapshot = validate_snapshot(discipline.config().derived_dir, cleaning)
        if snapshot != manifest["datasets"].get(name):
            raise ValueError(f"{name}: source archive differs from the completed run")
    manuscript_hash = source_hash(ROOT)
    pdf = ROOT / "thesis/main.pdf"
    original = run / "thesis-before-review.pdf"
    if not original.exists() and pdf.is_file():
        if hashlib.sha256(pdf.read_bytes()).hexdigest() == manifest["pdf_sha256"]:
            shutil.copy2(pdf, original)
    DRIVER["_run"](
        [
            "latexmk",
            "-pdf",
            "-halt-on-error",
            "-interaction=nonstopmode",
            "-cd",
            "thesis/main.tex",
        ],
        run / "manuscript-review.log",
    )
    validate_results(ROOT, manifest, set(DRIVER["required_outputs"]()))
    if source_hash(ROOT) != manuscript_hash:
        raise ValueError("Manuscript changed during compilation")
    for name, discipline in DISCIPLINES.items():
        if (
            validate_snapshot(discipline.config().derived_dir, cleaning)
            != manifest["datasets"][name]
        ):
            raise ValueError(f"{name}: source archive changed during compilation")
    review = {
        "reviewed_utc": datetime.now(UTC).isoformat(),
        "numerical_run_id": manifest["run_id"],
        "numerical_manifest_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "source_sha256": manuscript_hash,
        "numerical_source_sha256": manifest["numerical_source_sha256"],
        "pdf_sha256": hashlib.sha256(pdf.read_bytes()).hexdigest(),
        "scope": "Manuscript revision; numerical sources, generated results and datasets unchanged",
    }
    write_json(run / "manuscript-review.json", review)
    print(f"Reviewed PDF recorded in {run / 'manuscript-review.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
