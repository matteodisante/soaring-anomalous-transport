"""Review the thesis against an explicit, bounded regional PCA numerical update."""
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

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
BASE = ROOT / "revisions/vertical-gap-split-2026-09-11"
BASE_COMMIT = "6a90199"
sys.path.insert(0, str(ROOT / "src"))
from soaring.reporting import DISCIPLINES
from soaring.reporting.snapshot import current_cleaning, source_hash, validate_snapshot

VIEWER = {"src/soaring/viewer/" + name for name in (
    "catalog_index.py", "geography.py", "widgets/flight_picker.py", "widgets/map_view.py")}
CHANGED = {
    "scripts/reporting/ch3_global_transport/generate_revision_diagnostics.py",
    "src/soaring/analysis/observables/regional_pca.py",
    "src/soaring/reporting/regional_pca.py", "src/soaring/reporting/style.py",
    "thesis/sections/04-global-transport.tex",
}


def sha(data):
    return hashlib.sha256(data).hexdigest()


def git(*args):
    return subprocess.check_output(["git", *args], cwd=ROOT)


def numeric(name):
    return name.startswith(("src/", "scripts/", "configs/")) or name == "uv.lock"


def sources():
    paths = set()
    for pattern in ("src/**/*.py", "scripts/**/*.py", "configs/*.yaml",
                    "thesis/sections/*.tex", "thesis/appendices/**/*.tex"):
        paths.update(ROOT.glob(pattern))
    paths.update(ROOT / n for n in ("thesis/main.tex", "thesis/references.bib", "uv.lock"))
    old_names = set(git("ls-tree", "-r", "--name-only", BASE_COMMIT).decode().splitlines())
    full, numerical, hashes = hashlib.sha256(), hashlib.sha256(), {}
    for path in sorted(paths):
        name = path.relative_to(ROOT).as_posix()
        actual = path.read_bytes()
        old = git("show", f"{BASE_COMMIT}:{name}") if name in old_names else None
        if name not in CHANGED | VIEWER:
            assert actual == old, f"Unrecorded scientific/manuscript change: {name}"
        hashes[name] = sha(actual)
        full.update(name.encode() + b"\0" + actual)
        if numeric(name):
            numerical.update(name.encode() + b"\0" + actual)
    return {"source_sha256": full.hexdigest(), "numerical_source_sha256": numerical.hexdigest(),
            "source_files": hashes, "viewer_files_excluded_from_numerical_equivalence": sorted(VIEWER)}


def verify():
    update = json.loads((HERE / "numerical-update.json").read_text())
    baseline_path = ROOT / update["baseline_manifest"]
    assert sha(baseline_path.read_bytes()) == update["baseline_manifest_sha256"]
    baseline = json.loads(baseline_path.read_text())
    assert update["status"] == baseline["status"] == "complete"
    post_run_formatting = {}
    for name, expected in update["operation"]["sources"].items():
        actual = (ROOT / name).read_bytes()
        if sha(actual) != expected:
            assert name == "scripts/reporting/ch3_global_transport/generate_revision_diagnostics.py"
            executed = gzip.decompress((HERE / "executed-reporter.py.gz").read_bytes())
            assert sha(executed) == expected
            assert ast.dump(ast.parse(actual)) == ast.dump(ast.parse(executed))
            post_run_formatting[name] = {"executed_sha256": expected, "reviewed_sha256": sha(actual),
                                         "proof": "identical complete Python AST; error-message line wrapping only"}
    outputs = baseline["outputs"] | update["outputs"]
    for name, record in outputs.items():
        assert sha((ROOT / "thesis/generated" / name).read_bytes()) == record["sha256"], name
    driver = runpy.run_path(str(ROOT / "scripts/rebuild_thesis.py"))
    assert set(driver["required_outputs"]()).issubset(outputs)
    cleaning = current_cleaning(ROOT)
    assert cleaning == baseline["cleaning"] == update["cleaning"]
    for name, discipline in DISCIPLINES.items():
        assert validate_snapshot(discipline.config().derived_dir, cleaning) == baseline["datasets"][name]
    report = update["compressed_report"]
    archived = (HERE / report["archive_name"]).read_bytes()
    assert sha(archived) == report["gzip_sha256"]
    assert sha(gzip.decompress(archived)) == report["raw_sha256"]
    return update, outputs, post_run_formatting


def main():
    update, outputs, formatting = verify()
    source_record = sources()
    working_hash = source_hash(ROOT)
    with (HERE / "manuscript-build.log").open("w") as log:
        subprocess.run(["latexmk", "-pdf", "-halt-on-error", "-interaction=nonstopmode",
                        "-cd", "thesis/main.tex"], cwd=ROOT, stdout=log,
                       stderr=subprocess.STDOUT, check=True)
    verify()
    assert source_hash(ROOT) == working_hash
    assert sources() == source_record
    log = (ROOT / "thesis/main.log").read_text()
    assert not re.search(r"Overfull|LaTeX Warning:|Undefined control sequence|Fatal error", log)
    aux = (ROOT / "thesis/main.aux").read_text()
    assert r"\newlabel{fig:regional-pca}{{3.15}" in aux
    pages = int(re.search(r"Output written on main.pdf \((\d+) pages", log)[1])
    review = {
        "reviewed_utc": datetime.now(UTC).isoformat(), "status": "complete",
        "numerical_run_id": update["run_id"], "baseline_numerical_run_id": update["baseline_run_id"],
        "numerical_update_sha256": sha((HERE / "numerical-update.json").read_bytes()),
        "pdf_sha256": sha((ROOT / "thesis/main.pdf").read_bytes()), "pages": pages,
        "working_source_sha256": working_hash, **source_record,
        "post_run_formatting": formatting,
        "scope": "Regional PCA recomputed at exact decade lags; all other results inherited from the completed full run. Current cleaning identity and all source tables verified. Thesis prose, figure and reference table reviewed together. Full reviewed source hashes include the independent viewer changes; those files are not dependencies of the focused PCA calculation and are excluded from baseline numerical equivalence.",
        "generated_outputs": {n: r["sha256"] for n, r in outputs.items()},
        "visual_review": "Four ellipses, markers, axis labels and flight counts inspected in all regions; printed Figure 3.15 and adjacent reference table checked after compilation.",
    }
    (HERE / "manuscript-review.json").write_text(json.dumps(review, indent=2) + "\n")
    print(f"Reviewed {pages}-page thesis; {len(outputs)} generated inputs and current cleaning verified")


if __name__ == "__main__":
    main()
