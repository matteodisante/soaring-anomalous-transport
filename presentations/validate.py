"""Verify the delivered chapter PDFs, current inputs and figure provenance.

Run with pypdf available. This checks saved evidence and compiled documents;
it neither reads flight trajectories nor repeats numerical measurements.
"""
from __future__ import annotations

import gzip
import hashlib
import json
import re
from datetime import UTC, datetime
from pathlib import Path

from pypdf import PdfReader

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parent


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    source = json.loads((ROOT / "source-manifest.json").read_text())
    if digest(REPO / "thesis/main.pdf") != source["reviewed_thesis"]["pdf_sha256"]:
        raise ValueError("The thesis changed after presentation input review")
    for name, expected in source["reviewed_thesis"]["source_files"].items():
        if digest(REPO / name) != expected:
            raise ValueError(f"Reviewed thesis or numerical source changed: {name}")
    for name, expected in source.get("environment_update", {}).get("external_input_files", {}).items():
        if digest(REPO / name) != expected:
            raise ValueError(f"Archived environmental input changed: {name}")
    for name, expected in source.get("wind_altitude_update", {}).get("external_input_files", {}).items():
        if digest(REPO / name) != expected:
            raise ValueError(f"Archived pressure-level or altitude input changed: {name}")
    assets = {}
    data = {}
    for name, expected in source["inputs"].items():
        path = REPO / name
        if path.is_file() and digest(path) != expected:
            raise ValueError(f"A recorded manuscript input changed: {name}")
        if name.startswith("thesis/generated/"):
            (assets if name.endswith(".pdf") else data)[Path(name).name] = expected
    for name, record in source["panels"].items():
        assets[name + ".pdf"] = record["sha256"]
    manifests = {}
    figure_manifests = ["figure-manifest.json", "supervisor-panel-manifest.json",
                        "supervisor-map-manifest.json", "supervisor-gate-manifest.json"]
    if source.get("regional_variations_update"):
        figure_manifests.append("variation-panel-manifest.json")
    if source.get("grouped_tamsd_update"):
        figure_manifests.append("tamsd-panel-manifest.json")
    for name in figure_manifests:
        path = ROOT / name
        record = json.loads(path.read_text())
        if name in ("variation-panel-manifest.json", "tamsd-panel-manifest.json"):
            renderer = "render_tamsd_panels.py" if name.startswith("tamsd") else "render_variation_panels.py"
            if digest(ROOT / renderer) != record["script_sha256"]:
                raise ValueError(f"Panel renderer changed after rendering: {renderer}")
            for input_name, expected in record["inputs"].items():
                if digest(ROOT / input_name) != expected:
                    raise ValueError(f"Variation panel input changed: {input_name}")
        manifests[name] = digest(path)
        for output, value in record["outputs"].items():
            expected = value["sha256"] if isinstance(value, dict) else value
            if output in assets and assets[output] != expected:
                raise ValueError(f"Conflicting figure provenance: {output}")
            assets[output] = expected
    crop_path = ROOT / "panel-crop-manifest.json"
    for name, record in json.loads(crop_path.read_text()).items():
        if digest(REPO / record["source"]) != record["source_sha256"]:
            raise ValueError(f"Crop source changed: {name}")
        assets[name + ".pdf"] = record["output_sha256"]
    manifests[crop_path.name] = digest(crop_path)
    for name, expected in assets.items():
        if digest(ROOT / "assets" / name) != expected:
            raise ValueError(f"Figure differs from its manifest: {name}")
    for name, record in source["compressed_reports"].items():
        path = ROOT / "data" / record["archive_name"]
        raw = gzip.decompress(path.read_bytes())
        if (digest(path) != record["gzip_sha256"] or
                hashlib.sha256(raw).hexdigest() != record["raw_sha256"] or
                len(raw) != record["raw_size_bytes"]):
            raise ValueError(f"Full report bytes differ: {name}")
    documents = {}
    forbidden = re.compile(r"2\.0\.[01]|2\.2\.0|whole-record rule|"
                           r"historical comparison|older slides|formerly reconstructed", re.I)
    for chapter in (2, 3):
        tex = (ROOT / f"chapter{chapter}.tex").read_text()
        numbered_count = (
            len(re.findall(r"\\begin\{frame\}", tex))
            + (1 if chapter == 3 else len(re.findall(r"\\titleframe\{", tex)))
        )
        divider_count = len(re.findall(r"\\subsectionframe\{", tex))
        count = numbered_count + divider_count
        if forbidden.search(tex):
            raise ValueError("The chapter includes superseded implementation narrative")
        referenced = set(re.findall(r"\\fig(?:\[[^\]]+\])?\{([^}]+)\}", tex))
        if not referenced.issubset(assets):
            raise ValueError(f"Missing figure provenance: {referenced - assets.keys()}")
        for name in re.findall(r"\\input\{data/([^}]+)\}", tex):
            if digest(ROOT / "data" / name) != data[name]:
                raise ValueError(f"Slide values differ from thesis input: {name}")
        for suffix in ("", "-notes"):
            stem = f"chapter{chapter}{suffix}"
            path = ROOT / (stem + ".pdf")
            reader = PdfReader(path)
            if len(reader.pages) != count:
                raise ValueError(f"Unexpected page count: {stem}")
            width = float(reader.pages[0].mediabox.width)
            if abs(width - (907.087 if suffix else 453.543)) > .01:
                raise ValueError(f"Incorrect slide/notes layout: {stem}")
            text = "\n".join(page.extract_text() for page in reader.pages)
            if forbidden.search(text):
                raise ValueError(f"Superseded content in compiled PDF: {stem}")
            log = (ROOT / "build" / stem / (stem + ".log")).read_text()
            if re.search(r"Overfull|Undefined control sequence|Fatal error|LaTeX Warning:", log):
                raise ValueError(f"Unresolved LaTeX problem: {stem}")
            documents[path.name] = {"pages": count,
                                    "numbered_slides": numbered_count,
                                    "subsection_dividers": divider_count,
                                    "sha256": digest(path),
                                    "bytes": path.stat().st_size,
                                    "speaker_notes": bool(suffix)}
    focused_tex = (ROOT / "chapter3-section35.tex").read_text()
    focused_numbered = len(re.findall(r"\\begin\{frame\}", focused_tex)) + 1
    focused_dividers = len(re.findall(r"\\subsectionframe\{", focused_tex))
    focused_count = focused_numbered + focused_dividers
    focused_sections = re.findall(r"\\subsectionframe\{([^}]+)\}", focused_tex)
    if focused_sections != ["3.5.1", "3.5.2", "3.5.3"]:
        raise ValueError(f"Unexpected subsection in focused deck: {focused_sections}")
    referenced = set(re.findall(r"\\fig(?:\[[^\]]+\])?\{([^}]+)\}", focused_tex))
    if not referenced.issubset(assets):
        raise ValueError(f"Missing focused figure provenance: {referenced - assets.keys()}")
    # Every figure from the three requested thesis subsections must appear whole;
    # cropped panels supplement these figures and never replace missing panels.
    expected_figures = {
        "prelim_isotropy.pdf": "3.20", "ch3_pca.pdf": "3.21",
        "ch3_terrain_axes.pdf": "3.22", "ch3_channel_wind.pdf": "3.23",
        "kinematic_isotropy_terrain.pdf": "3.24",
        "kinematic_isotropy_terrain_level.pdf": "3.25",
        "kinematic_isotropy_flat_level.pdf": "3.26",
    }
    direct_figures = set(re.findall(
        r"\\includegraphics(?:\[[^\]]+\])?\{\.\./thesis/generated/([^}]+)\}",
        focused_tex,
    ))
    if direct_figures | (referenced & expected_figures.keys()) != expected_figures.keys():
        raise ValueError("The focused deck must contain exactly thesis Figures 3.20--3.26")
    reviewed_outputs = source["reviewed_thesis"]["generated_outputs"]
    focused_figures = {}
    for name, number in expected_figures.items():
        path = REPO / "thesis/generated" / name
        if digest(path) != reviewed_outputs[name]:
            raise ValueError(f"Focused thesis figure changed since review: {name}")
        focused_figures[number] = {"source": str(path.relative_to(REPO)),
                                  "sha256": digest(path)}
    for name in re.findall(r"\\input\{data/([^}]+)\}", focused_tex):
        if digest(ROOT / "data" / name) != data[name]:
            raise ValueError(f"Focused slide values differ from thesis input: {name}")
    for name in re.findall(r"\\input\{\.\./thesis/generated/([^}]+)\}", focused_tex):
        if digest(REPO / "thesis/generated" / name) != reviewed_outputs[name]:
            raise ValueError(f"Focused numerical input differs from reviewed thesis: {name}")
    for suffix in ("", "-notes"):
        stem = f"chapter3-section35{suffix}"
        path = ROOT / (stem + ".pdf")
        reader = PdfReader(path)
        if len(reader.pages) != focused_count:
            raise ValueError(f"Unexpected page count: {stem}")
        width = float(reader.pages[0].mediabox.width)
        if abs(width - (907.087 if suffix else 453.543)) > .01:
            raise ValueError(f"Incorrect slide/notes layout: {stem}")
        text = "\n".join(page.extract_text() for page in reader.pages)
        if forbidden.search(text):
            raise ValueError(f"Superseded content in compiled PDF: {stem}")
        log = (ROOT / "build" / stem / (stem + ".log")).read_text()
        if re.search(r"Overfull|Undefined control sequence|Fatal error|LaTeX Warning:", log):
            raise ValueError(f"Unresolved LaTeX problem: {stem}")
        documents[path.name] = {"pages": focused_count,
                                "numbered_slides": focused_numbered,
                                "subsection_dividers": focused_dividers,
                                "sha256": digest(path),
                                "bytes": path.stat().st_size,
                                "speaker_notes": bool(suffix)}
    result = {"verified_utc": datetime.now(UTC).isoformat(),
              "numerical_run_id": source["numerical_run_id"],
              "reviewed_thesis": source["reviewed_thesis"],
              "source_manifest_sha256": digest(ROOT / "source-manifest.json"),
              "figure_manifests": manifests, "verified_assets": len(assets),
              "documents": documents,
              "focused_thesis_figures": focused_figures,
              "presentation_sources": {p.name: digest(p) for p in
                  sorted(ROOT.glob("*.py")) + [ROOT / "theme.tex", ROOT / "chapter2.tex", ROOT / "chapter3.tex", ROOT / "chapter3-section35.tex"]},
              "scope": "Complete chapter decks and the Section 3.5 focused deck use the reviewed current results. All referenced figure and numerical inputs match their manifests; full reports retain all bytes in gzip; six PDFs compile without LaTeX warnings or overfull boxes.",
              "visual_review": "Chapter 3 slides 59--65 explain the signed four-component temporal observable, fixed support, training-only quantile fit, held-out projected CDFs, paired date bootstrap, intermediate-range results and limits. Slides 60--61 and the new result panels were inspected for readable formulas and plots. The focused deck follows thesis subsections 3.5.1, 3.5.2 and 3.5.3 in order. Figures 3.20--3.26 appear whole, with supplementary enlargements and visible commentary. The original 40-page focused deck was inspected as a contact sheet. The two added France-map slides (5--6) and their notes were inspected individually: captions explain the launch-density grid and regional boxes, then raw first-fix altitude bands, colour, marker area and busiest-cell crosses. "
                  "Four further slides in both Chapter 3 decks develop the observed ratio trend, terrain-exploration scales, an illustrative coherent-wind model and lag-wise whitening. The terrain time and parameters are explicitly defined. The separate directional-memory slide was removed from both decks at the author's request; that counterexample remains in the thesis. The added slides and their notes were inspected for readable equations and matched wording; the corresponding thesis discussion was inspected after compilation. "
                  f"The current focused deck has {focused_count} pages, {focused_dividers} subsection dividers and {focused_numbered} numbered slides. "
                  "Values and populations agree with the reviewed thesis and complete measurement report. Existing marginal-collapse, Hurst-limit and wind results remain unchanged. The discussion-question layout already present in the workspace was preserved."}
    (ROOT / "validation.json").write_text(json.dumps(result, indent=2) + "\n")
    print(f"Verified six presentation PDFs, {len(assets)} figure assets and complete report bytes.")


if __name__ == "__main__":
    main()
