"""Review grouped TAMSD results after the completed regional-variation delivery."""

from __future__ import annotations

import argparse
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
PARENT = ROOT / "revisions/regional-variations-2026-09-12"


def digest(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def write(path, value):
    path.write_text(json.dumps(value, indent=2) + "\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--numerical-only", action="store_true",
                        help="record the audited measurement before shared manuscript review")
    args = parser.parse_args()
    subprocess.run([sys.executable, str(HERE / "audit_numerics.py")], cwd=ROOT, check=True)
    parent_path = PARENT / "numerical-update.json"
    parent = json.loads(parent_path.read_text())
    parent_review = json.loads((PARENT / "manuscript-review.json").read_text())
    inherited = parent_review["generated_outputs"]
    for name, expected in inherited.items():
        assert digest(ROOT / "thesis/generated" / name) == expected, name
    for name, expected in parent_review["source_files"].items():
        if not name.startswith(("src/", "scripts/", "configs/")):
            continue
        if digest(ROOT / name) != expected:
            assert name == "configs/rebuild.yaml", name
            previous = subprocess.check_output(["git", "show", "a041fc3:configs/rebuild.yaml"], cwd=ROOT)
            assert hashlib.sha256(previous).hexdigest() == expected
            current = yaml.safe_load((ROOT / name).read_text())
            previous_config = yaml.safe_load(previous)
            parent_ids = {s["id"] for s in previous_config["stages"]}
            # Concurrent extensions may append stages, but no inherited command
            # or ordering may change. This does not certify their new outputs.
            added = [s for s in current["stages"] if s["id"] not in parent_ids]
            assert any(s["id"] == "grouped_tamsd" for s in added)
            current["stages"] = [s for s in current["stages"] if s["id"] in parent_ids]
            assert current == previous_config
    figure_path = HERE / "figure-manifest.json"
    figures = json.loads(figure_path.read_text())
    producer = "scripts/reporting/ch3_global_transport/generate_grouped_tamsd.py"
    assert digest(ROOT / producer) == figures["renderer_sha256"]
    raw = gzip.decompress((HERE / "report.json.gz").read_bytes())
    assert hashlib.sha256(raw).hexdigest() == figures["report_sha256"]
    outputs = {}
    for name, expected in figures["outputs"].items():
        assert digest(ROOT / "thesis/generated" / name) == expected, name
        outputs[name] = {"sha256": expected, "producer": producer, "historical_control": False}
    update = {
        "status": "complete", "run_id": HERE.name,
        "parent_run_id": parent["run_id"], "parent_update_sha256": digest(parent_path),
        "baseline_run_id": parent["baseline_run_id"], "cleaning": parent["cleaning"],
        "operation": "new regional and initial-altitude TAMSD grouping on verified native segment curves; inherited outputs unchanged",
        "numerical_audit_sha256": digest(HERE / "numerical-audit.json"),
        "numerical_audit_script_sha256": digest(HERE / "audit_numerics.py"),
        "figure_manifest_sha256": digest(figure_path), "outputs": outputs,
        "compressed_report": {"archive_name": "ch3_grouped_tamsd.json.gz",
            "raw_sha256": hashlib.sha256(raw).hexdigest(), "raw_size_bytes": len(raw),
            "gzip_sha256": digest(HERE / "report.json.gz"),
            "gzip_size_bytes": (HERE / "report.json.gz").stat().st_size},
    }
    update_path = HERE / "numerical-update.json"
    if update_path.exists():
        assert json.loads(update_path.read_text()) == update
    else:
        write(update_path, update)
    if args.numerical_only:
        print("Recorded audited grouped TAMSD measurement; manuscript review pending")
        return
    paths = set()
    for pattern in ("src/**/*.py", "scripts/**/*.py", "configs/*.yaml", "thesis/sections/*.tex", "thesis/appendices/**/*.tex"):
        paths.update(ROOT.glob(pattern))
    paths.update(ROOT / n for n in ("thesis/main.tex", "thesis/references.bib", "uv.lock"))
    reviewed_names = set(inherited) | set(outputs)
    unreviewed = set()
    for path in paths:
        if path.suffix != ".tex":
            continue
        for reference in re.findall(r"\{generated/([^}]+)\}", path.read_text()):
            candidate = ROOT / "thesis/generated" / reference
            for actual in (candidate, candidate.with_suffix(".tex"), candidate.with_suffix(".pdf")):
                if actual.is_file() and actual.name.startswith("ch3_") and actual.name not in reviewed_names:
                    unreviewed.add(actual.name)
    if unreviewed:
        raise ValueError("Additional chapter inputs need a combined manuscript review: " + ", ".join(sorted(unreviewed)))
    sources = {str(p.relative_to(ROOT)): digest(p) for p in sorted(paths)}
    with (HERE / "manuscript-build.log").open("w") as log:
        subprocess.run(["latexmk", "-pdf", "-halt-on-error", "-interaction=nonstopmode", "-cd", "thesis/main.tex"],
                       cwd=ROOT, stdout=log, stderr=subprocess.STDOUT, check=True)
    assert sources == {str(p.relative_to(ROOT)): digest(p) for p in sorted(paths)}
    log = (ROOT / "thesis/main.log").read_text()
    assert not re.search(r"Overfull|LaTeX Warning:|Undefined control sequence|Fatal error", log)
    pages = int(re.search(r"Output written on main.pdf \((\d+) pages", log)[1])
    write(HERE / "manuscript-review.json", {
        "status": "complete", "reviewed_utc": datetime.now(UTC).isoformat(),
        "numerical_run_id": HERE.name, "baseline_numerical_run_id": parent["baseline_run_id"],
        "numerical_update_sha256": digest(update_path), "pdf_sha256": digest(ROOT / "thesis/main.pdf"),
        "pages": pages, "source_files": sources,
        "generated_outputs": inherited | {n: r["sha256"] for n, r in outputs.items()},
        "scope": "All inherited results are unchanged. Grouped TAMSD includes all eligible flights, fixed-segment controls, site-day intervals and an explicit initial-altitude proxy. Scalar growth and population selection precede directional analysis. No causal terrain/wind effect or Hurst estimate is inferred.",
    })
    print(f"Reviewed {pages} thesis pages and {len(outputs)} new inputs")


if __name__ == "__main__":
    main()
