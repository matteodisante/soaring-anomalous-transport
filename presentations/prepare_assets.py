#!/usr/bin/env python3
"""Freeze reviewed thesis results and crop vector PDFs without refitting."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import re
import shutil
import subprocess
from datetime import UTC, datetime
from pathlib import Path

from pypdf import PdfReader, PdfWriter, Transformation
from pypdf.generic import RectangleObject

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parent
# Crop coordinates are fractions (left, top, right, bottom), measured from top left.
# Curves, axes and numerical results are unchanged; the full originals are retained.
PANELS = {
    "scaling-top": ("ch3_scaling", (0, 0, 1, 0.52)),
    "memory-positive": ("ch3_velocity_memory", (0, 0, 1, 0.465)),
    "memory-signed": ("ch3_velocity_memory", (0, 0.465, 1, 1)),
    "terrain-position": ("kinematic_isotropy_terrain", (0, 0, 1, 0.31)),
    "terrain-velocity": ("kinematic_isotropy_terrain", (0, 0.312, 1, 0.625)),
    "equipment-alps": ("kinematic_isotropy_terrain_level", (0, 0, 0.495, 0.315)),
    "equipment-pyrenees": (
        "kinematic_isotropy_terrain_level",
        (0, 0.318, 0.495, 0.634),
    ),
    "defect-position": ("cleaning_real_examples", (0, 0, 1, 0.335)),
    "defect-frozen": ("cleaning_real_examples", (0, 0.333, 1, 0.667)),
    "defect-altitude": ("cleaning_real_examples", (0, 0.664, 1, 1)),
    "vertical-threshold": ("fixlevel_diagnostics", (0.32, 0, 0.651, 1)),
    "sg-fit": ("savgol_explainer", (0, 0, 0.5, 1)),
    "sg-response": ("savgol_response", (0, 0, 0.5, 1)),
}
# Reuse the original shared x-axis labels when extracting an upper panel.
# The original panels share their x limits and horizontal axes positions.
AXIS_STRIPS = {
    "memory-positive": (0.922, 1),
    "terrain-position": (0.928, 1),
    "terrain-velocity": (0.928, 1),
    "equipment-alps": (0.949, 1),
    "equipment-pyrenees": (0.949, 1),
}
# Discover the complete chapter inputs; this also includes originals for the
# additional readable crops produced by crop_chapter_panels.py.
from crop_chapter_panels import PANELS as CHAPTER_PANELS

DECKS = [(ROOT / f"chapter{chapter}.tex").read_text() for chapter in (2, 3)]
REFERENCED = set(re.findall(r"\\fig(?:\[[^\]]+\])?\{([^}]+)\}", "\n".join(DECKS)))
PANELS = {name: spec for name, spec in PANELS.items() if name + ".pdf" in REFERENCED}
ORIGINALS = sorted(
    {source for source, _ in PANELS.values()}
    | {source for source, _, _ in CHAPTER_PANELS.values()}
    | {Path(name).stem for name in REFERENCED
       if (REPO / "thesis/generated" / name).is_file()}
)
DATA = sorted(set(re.findall(r"\\input\{data/([^}]+)\}", "\n".join(DECKS)))
              | {"duration_equipment.json"})


def digest(path: Path) -> str:
    """Identify the exact bytes used by the presentation."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    """Require the completed manuscript review before freezing any slide results."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", type=Path, default=REPO / "revisions/vertical-gap-split-2026-09-11/recovery-runs/20260912T133040Z-073601cb")
    args = parser.parse_args()
    run = args.run.resolve()
    review_path = run / "review-inputs/manuscript-review.json"
    review = json.loads(review_path.read_text())
    release = json.loads((run / "review-inputs/manifest.json").read_text())
    if release["status"] != "complete" or any(s["status"] != "complete" for s in release["stages"]):
        raise ValueError("All numerical and thesis stages must be complete")
    if digest(REPO / "thesis/main.pdf") != review["pdf_sha256"]:
        raise ValueError("The canonical thesis is not the reviewed PDF")
    assets, data = ROOT / "assets", ROOT / "data"
    assets.mkdir(exist_ok=True)
    data.mkdir(exist_ok=True)
    manifest = {
        "created_utc": datetime.now(UTC).isoformat(),
        "numerical_run_id": release["run_id"],
        "cleaning_version": release["cleaning"]["pipeline_version"],
        "cleaning_source_sha256": release["cleaning"]["source_sha256"],
        "reviewed_thesis": review,
        "review_record_sha256": digest(review_path),
        "operation": "Copy reviewed current results and crop vector panels; no analysis rerun.",
        "inputs": {}, "panels": {}, "compressed_reports": {},
    }
    for name in [n + ".pdf" for n in ORIGINALS] + DATA:
        source = REPO / "thesis/generated" / name
        actual = digest(source)
        required = release["outputs"].get(name)
        if required:
            if required["historical_control"] or actual != required["sha256"]:
                raise ValueError(f"A current reviewed input is required: {name}")
        else:
            frozen = Path(release["source_root"]) / "thesis/generated" / name
            if actual != digest(frozen):
                raise ValueError(f"Supplementary report differs from completed source: {name}")
        target = (assets if source.suffix == ".pdf" else data) / name
        shutil.copy2(source, target)
        manifest["inputs"][str(source.relative_to(REPO))] = actual
    archive = REPO / "revisions/vertical-gap-split-2026-09-11/full-report-archive"
    archived = json.loads((archive / "manifest.json").read_text())
    for name, record in archived["reports"].items():
        source = archive / record["archive_name"]
        raw = gzip.decompress(source.read_bytes())
        if hashlib.sha256(raw).hexdigest() != release["outputs"][name]["sha256"] or digest(source) != record["gzip_sha256"]:
            raise ValueError(f"The complete compressed report is not verified: {name}")
        shutil.copy2(source, data / source.name)
        manifest["compressed_reports"][name] = record
        manifest["inputs"]["thesis/generated/" + name] = record["raw_sha256"]
    for name, (original, bounds) in PANELS.items():
        page = PdfReader(assets / (original + ".pdf")).pages[0]
        width, height = float(page.mediabox.width), float(page.mediabox.height)
        left, top, right, bottom = bounds
        box = RectangleObject(
            (width * left, height * (1 - bottom), width * right, height * (1 - top))
        )
        page.mediabox = box
        page.cropbox = box
        writer = PdfWriter()
        if name == "vertical-threshold":
            # The neighbouring panel's rotated y label intrudes into the crop,
            # while our own x-unit label extends farther right. Retain the full
            # x-label strip and exclude only that neighbouring label fragment.
            output = writer.add_blank_page(width=width * (right - left), height=height)
            page.cropbox.right = width * 0.643
            output.merge_transformed_page(
                page, Transformation().translate(-width * left, 0)
            )
            strip = PdfReader(assets / (original + ".pdf")).pages[0]
            strip.cropbox = RectangleObject(
                (width * 0.643, 0, width * right, height * 0.14)
            )
            output.merge_transformed_page(
                strip, Transformation().translate(-width * left, 0)
            )
        elif name in AXIS_STRIPS:
            top2, bottom2 = AXIS_STRIPS[name]
            strip = PdfReader(assets / (original + ".pdf")).pages[0]
            strip.cropbox = RectangleObject(
                (
                    width * left,
                    height * (1 - bottom2),
                    width * right,
                    height * (1 - top2),
                )
            )
            strip_h = height * (bottom2 - top2)
            output = writer.add_blank_page(
                width=width * (right - left), height=height * (bottom - top) + strip_h
            )
            output.merge_transformed_page(
                page,
                Transformation().translate(
                    -width * left, -height * (1 - bottom) + strip_h
                ),
            )
            output.merge_transformed_page(
                strip,
                Transformation().translate(-width * left, -height * (1 - bottom2)),
            )
        else:
            writer.add_page(page)
        writer.write(assets / (name + ".pdf"))
        manifest["panels"][name] = {
            "source": original + ".pdf",
            "top_left_fraction_bounds": bounds,
            "appended_original_x_axis_strip": AXIS_STRIPS.get(name),
            "neighbouring_label_fragment_excluded": name == "vertical-threshold",
            "sha256": digest(assets / (name + ".pdf")),
        }
    for name in [
        "thesis/sections/03-dataset.tex",
        "thesis/sections/04-global-transport.tex",
        "configs/preprocessing.yaml",
        "src/soaring/reporting/style.py",
    ]:
        manifest["inputs"][name] = digest(REPO / name)
    manifest["script_sha256"] = digest(Path(__file__))
    (ROOT / "source-manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )
    print(
        f"Frozen {len(ORIGINALS)} figures, {len(DATA)} numerical inputs "
        f"and {len(PANELS)} panels."
    )


if __name__ == "__main__":
    main()
