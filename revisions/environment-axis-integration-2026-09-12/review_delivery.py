"""Review independent environmental references and their current thesis integration.

The grouped TAMSD measurement and regional-variation review are immutable parents.
This record reviews the combined manuscript, including both concurrent extensions.
It does not recalculate or relabel any inherited flight measurement.
"""
from __future__ import annotations

import ast
import gzip
import hashlib
import json
import re
import runpy
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
PARENT = ROOT / "revisions/grouped-tamsd-2026-09-12"
VARIATIONS = ROOT / "revisions/regional-variations-2026-09-12"
BASE = ROOT / "revisions/vertical-gap-split-2026-09-11/recovery-runs/20260912T133040Z-073601cb/review-inputs/manifest.json"
sys.path.insert(0, str(ROOT / "src"))
from soaring.reporting.snapshot import current_cleaning, validate_snapshot


def digest(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def write(path, value):
    path.write_text(json.dumps(value, indent=2) + "\n")


def main():
    parent_path = PARENT / "numerical-update.json"
    parent = json.loads(parent_path.read_text())
    earlier = json.loads((VARIATIONS / "manuscript-review.json").read_text())
    baseline = json.loads(BASE.read_text())
    assert parent["status"] == "complete"
    assert parent["parent_update_sha256"] == digest(VARIATIONS / "numerical-update.json")
    assert parent["numerical_audit_sha256"] == digest(PARENT / "numerical-audit.json")
    assert parent["numerical_audit_script_sha256"] == digest(PARENT / "audit_numerics.py")
    assert parent["figure_manifest_sha256"] == digest(PARENT / "figure-manifest.json")
    figure = json.loads((PARENT / "figure-manifest.json").read_text())
    assert figure["renderer_sha256"] == digest(ROOT / "scripts/reporting/ch3_global_transport/generate_grouped_tamsd.py")
    raw = gzip.decompress((PARENT / "report.json.gz").read_bytes())
    assert hashlib.sha256(raw).hexdigest() == parent["compressed_report"]["raw_sha256"]
    for name, expected in json.loads(raw)["sources"].items():
        assert digest(ROOT / name) == expected, name
    inherited = earlier["generated_outputs"] | {n: r["sha256"] for n, r in parent["outputs"].items()}
    for name, expected in inherited.items():
        assert digest(ROOT / "thesis/generated" / name) == expected, name
    # All existing computation is unchanged; only three declared stages are added.
    for name, expected in earlier["source_files"].items():
        if not name.startswith(("src/", "scripts/", "configs/")):
            continue
        if digest(ROOT / name) != expected:
            assert name == "configs/rebuild.yaml", name
            previous = subprocess.check_output(["git", "show", "a041fc3:" + name], cwd=ROOT)
            assert hashlib.sha256(previous).hexdigest() == expected
            current = yaml.safe_load((ROOT / name).read_text())
            added = {"terrain_axes", "channel_wind", "grouped_tamsd"}
            assert added <= {s["id"] for s in current["stages"]}
            current["stages"] = [s for s in current["stages"] if s["id"] not in added]
            assert current == yaml.safe_load(previous)
    cleaning = current_cleaning(ROOT)
    assert cleaning == baseline["cleaning"] == parent["cleaning"]
    for discipline, directory in (
        ("paragliders", "/Volumes/SSD_DISANTE/paragliders/ffvl_cfd_igc/derived"),
        ("hang gliders", "/Volumes/SSD_DISANTE/hang_gliders/delta_cfd_igc/derived"),
    ):
        assert validate_snapshot(Path(directory), cleaning) == baseline["datasets"][discipline]
    subprocess.run([sys.executable, str(ROOT / "revisions/channel-wind-2026-09-12/fetch_wind.py")], check=True)
    outputs = {}
    for stem, report_name in (("terrain_axis", "ch3_terrain_axes.json"), ("channel_wind", "ch3_channel_wind.json")):
        producer = f"scripts/reporting/ch3_global_transport/generate_{stem}_comparison.py"
        report = json.loads((ROOT / "thesis/generated" / report_name).read_text())
        assert report["producer_sha256"] == digest(ROOT / producer)
        assert report["flight_report_sha256"] == inherited["ch3_revision.json"]
        names = next(ast.literal_eval(n.value) for n in ast.parse((ROOT / producer).read_text()).body
                     if isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "GENERATED_OUTPUTS" for t in n.targets))
        for name in names:
            outputs[name] = {"sha256": digest(ROOT / "thesis/generated" / name), "producer": producer, "historical_control": False}
    external = {}
    for directory in ("terrain-axis-2026-09-12", "channel-wind-2026-09-12"):
        for path in sorted((ROOT / "revisions" / directory).iterdir()):
            if path.is_file() and path.suffix in {".nc", ".gz", ".json", ".py"}:
                external[str(path.relative_to(ROOT))] = digest(path)
    wind = json.loads((ROOT / "thesis/generated/ch3_channel_wind.json").read_text())
    assert wind["input_manifest_sha256"] == digest(ROOT / wind["input_manifest"])
    merged = inherited | {n: r["sha256"] for n, r in outputs.items()}
    required = runpy.run_path(str(ROOT / "scripts/rebuild_thesis.py"))["required_outputs"]()
    assert set(required) <= set(merged), set(required) - set(merged)
    update = {
        "status": "complete", "run_id": HERE.name,
        "parent_run_id": parent["run_id"], "parent_update_sha256": digest(parent_path),
        "baseline_run_id": baseline["run_id"], "cleaning": cleaning,
        "operation": "Publish independent ETOPO footprint axes and archived ERA5 climatology against unchanged current flight PCA; no flight measurement or cleaning rerun",
        "outputs": outputs, "external_input_files": external,
        "inherited_generated_outputs": inherited,
        "cleaned_snapshot_check": "Current code, configuration, packages and full cleaning manifests match the completed run; table sizes, timestamps, footers and row counts checked, not a fresh full-byte hash of 44 GB",
    }
    update_path = HERE / "numerical-update.json"
    if update_path.exists():
        assert json.loads(update_path.read_text()) == update, "Create a new revision for changed measured inputs"
    else:
        write(update_path, update)
    paths = set()
    for pattern in ("src/**/*.py", "scripts/**/*.py", "configs/*.yaml", "thesis/sections/*.tex", "thesis/appendices/**/*.tex"):
        paths.update(ROOT.glob(pattern))
    paths.update(ROOT / n for n in ("thesis/main.tex", "thesis/references.bib", "uv.lock"))
    sources = {str(p.relative_to(ROOT)): digest(p) for p in sorted(paths)}
    with (HERE / "manuscript-build.log").open("w") as log:
        subprocess.run(["latexmk", "-pdf", "-halt-on-error", "-interaction=nonstopmode", "-cd", "thesis/main.tex"], cwd=ROOT, stdout=log, stderr=subprocess.STDOUT, check=True)
    assert sources == {str(p.relative_to(ROOT)): digest(p) for p in sorted(paths)}
    log = (ROOT / "thesis/main.log").read_text()
    assert not re.search(r"Overfull|LaTeX Warning:|Undefined control sequence|Fatal error", log)
    pages = int(re.search(r"Output written on main.pdf \((\d+) pages", log)[1])
    write(HERE / "manuscript-review.json", {
        "status": "complete", "reviewed_utc": datetime.now(UTC).isoformat(),
        "numerical_run_id": HERE.name, "baseline_numerical_run_id": baseline["run_id"],
        "numerical_update_sha256": digest(update_path), "pdf_sha256": digest(ROOT / "thesis/main.pdf"),
        "pages": pages, "source_files": sources, "generated_outputs": merged,
        "external_input_files": external,
        "scope": "Combined manuscript review includes audited grouped TAMSD and independent environmental references. Pyrenean alignment is strong; Alpine axes differ by about 18 degrees. Annual coastal wind alignment is sensitive to warm daytime selection. Methods, archive reuse and causal limits are explicit. Existing numerical outputs are byte-identical to reviewed parents.",
    })
    print(f"Reviewed {pages} pages, {len(inherited)} inherited and {len(outputs)} new outputs")


if __name__ == "__main__":
    main()
