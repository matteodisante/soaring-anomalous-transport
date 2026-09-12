"""Crop readable TAMSD rows from the reviewed vector figures."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from pypdf import PdfReader, PdfWriter
from pypdf.generic import RectangleObject

ROOT = Path(__file__).resolve().parent


def digest(path):
    """Identify the complete bytes of each source or output."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    """Crop three vector rows from each of the two grouped TAMSD figures."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--figure-manifest",
        type=Path,
        help="verified numerical figures for layout before manuscript review",
    )
    args = parser.parse_args()
    if args.figure_manifest:
        figures = json.loads(args.figure_manifest.read_text())
        expected = {
            name: {"sha256": value} for name, value in figures["outputs"].items()
        }
    else:
        source = json.loads((ROOT / "source-manifest.json").read_text())
        expected = source["grouped_tamsd_update"]["outputs"]
    inputs, outputs = {}, {}
    for grouping in ("regions", "altitude"):
        path = ROOT / "assets" / f"ch3_tamsd_{grouping}.pdf"
        assert digest(path) == expected[path.name]["sha256"]
        inputs[str(path.relative_to(ROOT))] = digest(path)
        for row, label in enumerate(("growth", "velocity", "support")):
            page = PdfReader(path).pages[0]
            width = float(page.mediabox.width)
            height = float(page.mediabox.height)
            assert abs(height - 561.6) < 0.01
            # Bounds include each row's x labels and exclude the previous row's.
            intervals = (
                ((0, 195), (197, 378), (380, height))
                if grouping == "regions"
                else ((0, 195), (197, 376), (378, height))
            )
            top, bottom = intervals[row]
            box = RectangleObject((0, height - bottom, width, height - top))
            page.mediabox = box
            page.cropbox = box
            writer = PdfWriter()
            writer.add_page(page)
            target = ROOT / "assets" / f"tamsd-{grouping}-{label}.pdf"
            with target.open("wb") as stream:
                writer.write(stream)
            outputs[target.name] = digest(target)
    manifest = {
        "operation": "vector row crops; no numerical measurement or fit",
        "inputs": inputs,
        "outputs": outputs,
        "script_sha256": digest(Path(__file__)),
    }
    (ROOT / "tamsd-panel-manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n"
    )
    print(f"Prepared {len(outputs)} TAMSD panels")


if __name__ == "__main__":
    main()
