#!/usr/bin/env python3
"""Freeze thesis results for the talks and crop vector PDFs without refitting."""

from __future__ import annotations

import argparse
import hashlib
import json
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
    "vertical-spike": ("vertical_median_explainer", (0, 0.32, 1, 0.667)),
    "vertical-sustained": ("vertical_median_explainer", (0, 0.661, 1, 1)),
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
ORIGINALS = sorted(
    {source for source, _ in PANELS.values()}
    | {
        "ch3_quantile_control",
        "quantile_scaling_schematic",
        "closed_loop_schematic",
        "savgol_spectrum",
        "prelim_map",
        "sampling_intervals",
    }
)
DATA = [
    "ch3_revision.tex",
    "ch3_revision.json",
    "duration_equipment.tex",
    "duration_equipment.json",
    "duration_equipment_table.tex",
    "kinematic_isotropy.tex",
    "kinematic_isotropy.json",
    "msd.tex",
    "pipeline_census.tex",
    "dataset_stats.tex",
    "stats.tex",
    "cleaning_real_examples.json",
    "cleaning_witness_audit.json",
]


def digest(path: Path) -> str:
    """Identify the exact bytes used by the presentation."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    """Copy current inputs and record their provenance without accessing the SSD."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--panels-only", action="store_true", help="Recrop the already frozen PDFs"
    )
    args = parser.parse_args()
    assets, data = ROOT / "assets", ROOT / "data"
    assets.mkdir(exist_ok=True)
    data.mkdir(exist_ok=True)
    manifest = {
        "created_utc": datetime.now(UTC).isoformat(),
        "git_head": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=REPO, text=True
        ).strip(),
        "source_state": "Working-tree snapshot, including uncommitted edits.",
        "operation": "Copy existing results and crop vector panels; no analysis rerun.",
        "inputs": {},
        "panels": {},
    }
    if args.panels_only:
        manifest = json.loads((ROOT / "source-manifest.json").read_text())
    elif (ROOT / "source-manifest.json").exists():
        previous = json.loads((ROOT / "source-manifest.json").read_text())
        if "style_reference" in previous:
            manifest["style_reference"] = previous["style_reference"]
    for name in [] if args.panels_only else [n + ".pdf" for n in ORIGINALS] + DATA:
        source = REPO / "thesis" / "generated" / name
        target = (assets if source.suffix == ".pdf" else data) / name
        shutil.copy2(source, target)
        manifest["inputs"][str(source.relative_to(REPO))] = digest(source)
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
    if not args.panels_only:
        for name in [
            "thesis/sections/03-dataset.tex",
            "thesis/sections/04-global-transport.tex",
            "configs/preprocessing.yaml",
            "src/soaring/reporting/style.py",
        ]:
            manifest["inputs"][name] = digest(REPO / name)
    (ROOT / "source-manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )
    print(
        f"Frozen {len(ORIGINALS)} figures, {len(DATA)} numerical inputs "
        f"and {len(PANELS)} panels."
    )


if __name__ == "__main__":
    main()
