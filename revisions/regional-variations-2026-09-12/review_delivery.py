"""Review the regional variation extension against the completed PCA delivery."""

from __future__ import annotations

import gzip
import hashlib
import json
import re
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
PARENT = ROOT / "revisions/regional-pca-lags-2026-09-12"


def digest(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def write(path, value):
    path.write_text(json.dumps(value, indent=2) + "\n")


def main():
    subprocess.run([sys.executable, str(HERE / "audit_numerics.py")], cwd=ROOT, check=True)
    parent_path = PARENT / "numerical-update.json"
    parent = json.loads(parent_path.read_text())
    baseline = json.loads((ROOT / parent["baseline_manifest"]).read_text())
    inherited = baseline["outputs"] | parent["outputs"]
    for name, record in inherited.items():
        assert digest(ROOT / "thesis/generated" / name) == record["sha256"], name
    figure_path = HERE / "figure-manifest.json"
    figures = json.loads(figure_path.read_text())
    raw = gzip.decompress((HERE / "report.json.gz").read_bytes())
    report = json.loads(raw)
    assert figures["report_raw_sha256"] == hashlib.sha256(raw).hexdigest()
    for name, expected in figures["sources"].items():
        assert digest(ROOT / name) == expected, name
    for name, expected in figures["outputs"].items():
        assert digest(ROOT / "thesis/generated" / name) == expected, name
    parent_review = json.loads((PARENT / "manuscript-review.json").read_text())
    for name, expected in parent_review["source_files"].items():
        if not name.startswith(("src/", "scripts/", "configs/")):
            continue
        if digest(ROOT / name) != expected:
            assert name == "configs/rebuild.yaml", name
            previous = subprocess.check_output(["git", "show", "1c9c5d0:configs/rebuild.yaml"], cwd=ROOT)
            assert hashlib.sha256(previous).hexdigest() == expected
            current = yaml.safe_load((ROOT / name).read_text())
            current["stages"] = [s for s in current["stages"] if s["id"] != "regional_variations"]
            assert current == yaml.safe_load(previous)
    producer = "scripts/reporting/ch3_global_transport/generate_regional_variations.py"
    outputs = {name: {"sha256": expected, "producer": producer, "historical_control": False}
               for name, expected in figures["outputs"].items()}
    update = {
        "status": "complete", "run_id": HERE.name,
        "parent_run_id": parent["run_id"], "parent_update_sha256": digest(parent_path),
        "baseline_run_id": baseline["run_id"], "cleaning": parent["cleaning"],
        "operation": "new regional finite-difference measurement on verified PCA coordinates; inherited numerical outputs unchanged",
        "numerical_audit_sha256": digest(HERE / "numerical-audit.json"),
        "figure_manifest_sha256": digest(figure_path), "outputs": outputs,
        "compressed_report": {"archive_name": "ch3_regional_variations.json.gz",
            "raw_sha256": hashlib.sha256(raw).hexdigest(), "raw_size_bytes": len(raw),
            "gzip_sha256": digest(HERE / "report.json.gz"),
            "gzip_size_bytes": (HERE / "report.json.gz").stat().st_size},
        "post_run_source_alignment": {
            "path": producer.replace("generate_", "measure_"),
            "executed_archive": "executed-measure-regional-variations.py.gz",
            "scope": "CLI now also resolves absolute coordinate-store paths; all non-main function ASTs and the complete measurement module are unchanged",
        },
    }
    update_path = HERE / "numerical-update.json"
    if update_path.exists():
        assert json.loads(update_path.read_text()) == update
    else:
        write(update_path, update)
    paths = set()
    for pattern in ("src/**/*.py", "scripts/**/*.py", "configs/*.yaml",
                    "thesis/sections/*.tex", "thesis/appendices/**/*.tex"):
        paths.update(ROOT.glob(pattern))
    paths.update(ROOT / n for n in ("thesis/main.tex", "thesis/references.bib", "uv.lock"))
    source_files = {str(p.relative_to(ROOT)): digest(p) for p in sorted(paths)}
    with (HERE / "manuscript-build.log").open("w") as log:
        subprocess.run(["latexmk", "-pdf", "-halt-on-error", "-interaction=nonstopmode",
                        "-cd", "thesis/main.tex"], cwd=ROOT, stdout=log, stderr=subprocess.STDOUT, check=True)
    assert source_files == {str(p.relative_to(ROOT)): digest(p) for p in sorted(paths)}
    log = (ROOT / "thesis/main.log").read_text()
    assert not re.search(r"Overfull|LaTeX Warning:|Undefined control sequence|Fatal error", log)
    pages = int(re.search(r"Output written on main.pdf \((\d+) pages", log)[1])
    review = {
        "status": "complete", "reviewed_utc": datetime.now(UTC).isoformat(),
        "numerical_run_id": HERE.name, "baseline_numerical_run_id": baseline["run_id"],
        "numerical_update_sha256": digest(update_path),
        "pdf_sha256": digest(ROOT / "thesis/main.pdf"), "pages": pages,
        "source_files": source_files,
        "generated_outputs": {n: r["sha256"] for n, r in (inherited | outputs).items()},
        "scope": "All inherited figures and values match the completed PCA delivery. New values match the full regional report; new figures were visually inspected. Regional differences are not identified as wind or Hurst estimates; standardised controls have no calibrated intervals.",
    }
    write(HERE / "manuscript-review.json", review)
    print(f"Reviewed the {pages}-page thesis and {len(outputs)} new generated inputs")


if __name__ == "__main__":
    main()
