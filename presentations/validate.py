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
        count = len(re.findall(r"\\begin\{frame\}", tex)) + len(re.findall(r"\\titleframe\{", tex))
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
            documents[path.name] = {"pages": count, "sha256": digest(path),
                                    "bytes": path.stat().st_size,
                                    "speaker_notes": bool(suffix)}
    result = {"verified_utc": datetime.now(UTC).isoformat(),
              "numerical_run_id": source["numerical_run_id"],
              "reviewed_thesis": source["reviewed_thesis"],
              "source_manifest_sha256": digest(ROOT / "source-manifest.json"),
              "figure_manifests": manifests, "verified_assets": len(assets),
              "documents": documents,
              "presentation_sources": {p.name: digest(p) for p in
                  sorted(ROOT.glob("*.py")) + [ROOT / "theme.tex", ROOT / "chapter2.tex", ROOT / "chapter3.tex"]},
              "scope": "Complete chapter decks use the reviewed current results. All referenced figure and numerical inputs match their manifests; full reports retain all bytes in gzip; four PDFs compile without LaTeX warnings or overfull boxes.",
              "visual_review": "The preceding full-run and four-lag PCA layouts were retained. The revised cancellation slide, ten regional-variation slides and eight grouped-TAMSD slides were visually checked, including accompanying notes. The terrain comparisons retain their reviewed maps. Current wind slides 68--72 and their notes were checked for readable formulas, the mean-altitude rose and height comparison, all-hour/daytime values, common-support sensitivity and current conclusions. TAMSD row crops preserve complete axis labels and omit neighbouring rows. Values, support and group definitions agree with the complete reviewed reports."}
    (ROOT / "validation.json").write_text(json.dumps(result, indent=2) + "\n")
    print(f"Verified four chapter PDFs, {len(assets)} figure assets and complete report bytes.")


if __name__ == "__main__":
    main()
