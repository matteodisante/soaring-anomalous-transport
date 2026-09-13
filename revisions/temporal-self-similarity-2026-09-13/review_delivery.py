"""Review the new measurement and manuscript before preparing presentation assets."""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
PARENT = ROOT / "revisions/marginal-collapse-and-radial-shape-2026-09-13/manuscript-review.json"


def digest(path):
    """Identify complete bytes without loading coordinate stores into memory."""
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def write_new(path, value):
    """Completed audit records are immutable."""
    with path.open("x") as stream:
        stream.write(json.dumps(value, indent=2) + "\n")


def main():
    """Verify inputs, compile, then record the numerical extension and review."""
    parent = json.loads(PARENT.read_text())
    measurement = HERE / "measurement"
    report = json.loads((measurement / "report.json").read_text())
    contract = json.loads((measurement / "contract.json").read_text())
    figures = json.loads((HERE / "figure-manifest.json").read_text())
    assert report["status"] == parent["status"] == "complete"
    assert digest(measurement / "contract.json") == report["contract_sha256"]
    for name, expected in contract["sources"].items():
        assert digest(ROOT / name) == expected, name
    for name, record in report["inputs"].items():
        assert digest(name) == record["sha256"], name
    for name, expected in figures["inputs"].items():
        assert digest(measurement / name) == expected, name
    assert digest(ROOT / "scripts/reporting/ch3_global_transport/render_temporal_scaling.py") == figures["script_sha256"]
    for name, records in report["results"].items():
        slug = "para" if name == "paragliders" else "hang"
        for regime, record in records.items():
            assert digest(measurement / slug / f"{regime}.npz") == record["arrays_sha256"]
    for name, expected in parent["generated_outputs"].items():
        assert digest(ROOT / "thesis/generated" / name) == expected, name
    for name, expected in parent["external_input_files"].items():
        assert digest(ROOT / name) == expected, name
    outputs = {}
    for name, expected in figures["outputs"].items():
        assert digest(ROOT / "thesis/generated" / name) == expected, name
        outputs[name] = {"sha256": expected, "historical_control": False,
                         "producer": "scripts/reporting/ch3_global_transport/generate_temporal_scaling.py"}
    sources = {name: digest(ROOT / name) for name in parent["source_files"]}
    changed = [n for n, h in sources.items() if h != parent["source_files"][n]]
    assert set(changed) <= {"configs/rebuild.yaml", "thesis/sections/04-global-transport.tex"}, changed
    for pattern in ("scripts/reporting/ch3_global_transport/*temporal_scaling.py",):
        sources.update({str(p.relative_to(ROOT)): digest(p) for p in ROOT.glob(pattern)})
    for name in ("src/soaring/analysis/observables/temporal_scaling.py",
                 "thesis/sections/04-temporal-scaling.tex",
                 "revisions/temporal-self-similarity-2026-09-13/protocol.json"):
        sources[name] = digest(ROOT / name)
    with (HERE / "manuscript-build.log").open("w") as log:
        subprocess.run(["latexmk", "-pdf", "-halt-on-error", "-interaction=nonstopmode", "-cd", "thesis/main.tex"],
                       cwd=ROOT, stdout=log, stderr=subprocess.STDOUT, check=True)
    log = (ROOT / "thesis/main.log").read_text()
    assert not re.search(r"Overfull|LaTeX Warning:|Undefined control sequence|Fatal error", log)
    assert sources == {n: digest(ROOT / n) for n in sources}
    update = {"status": "complete", "run_id": HERE.name,
              "completed_utc": datetime.now(UTC).isoformat(),
              "parent_manuscript_review_sha256": digest(PARENT),
              "parent_generated_outputs": parent["generated_outputs"],
              "measurement_report_sha256": digest(measurement / "report.json"),
              "measurement_contract_sha256": digest(measurement / "contract.json"),
              "figure_manifest_sha256": digest(HERE / "figure-manifest.json"),
              "cleaning": report["cleaning"], "outputs": outputs,
              "operation": "New held-out signed and two-interval scaling measurement; inherited numerical outputs unchanged."}
    write_new(HERE / "numerical-update.json", update)
    review = dict(parent)
    review.update(status="complete", reviewed_utc=datetime.now(UTC).isoformat(),
                  numerical_run_id=HERE.name,
                  numerical_update_sha256=digest(HERE / "numerical-update.json"),
                  parent_manuscript_review_sha256=digest(PARENT), source_files=sources,
                  generated_outputs=parent["generated_outputs"] | figures["outputs"],
                  pdf_sha256=digest(ROOT / "thesis/main.pdf"),
                  pages=int(re.search(r"Output written on main.pdf \((\d+) pages", log)[1]),
                  review_script_sha256=digest(__file__),
                  scope="Signed marginal, spatial and two-interval projected scaling; held-out dates, common support, simultaneous bootstrap bounds and qualified intermediate-range evidence.")
    review.pop("changed_manuscript_sources", None)
    write_new(HERE / "manuscript-review.json", review)
    print(f"Reviewed {review['pages']} pages and {len(outputs)} new numerical products")


if __name__ == "__main__":
    main()
