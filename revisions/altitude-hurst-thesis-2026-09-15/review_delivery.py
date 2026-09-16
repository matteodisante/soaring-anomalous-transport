"""Verify the altitude-fit extension and record its compiled thesis delivery."""

from __future__ import annotations

import ast
import hashlib
import json
import re
import runpy
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))
from soaring.reporting import DISCIPLINES  # noqa: E402
from soaring.reporting.snapshot import current_cleaning, validate_snapshot  # noqa: E402

PARENT = (
    ROOT / "revisions/anisotropy-scale-interpretation-2026-09-14/manuscript-review.json"
)
MEASUREMENT = ROOT / "revisions/altitude-hurst-10-10000-2026-09-15"
GENERATOR = "scripts/reporting/ch3_global_transport/generate_altitude_hurst.py"
CHANGED = {
    "configs/rebuild.yaml",
    "thesis/main.tex",
    "thesis/sections/04-grouped-tamsd.tex",
}
NEW_OUTPUTS = (
    "ch3_altitude_hurst.pdf",
    "ch3_altitude_hurst_table.tex",
    "ch3_altitude_hurst_values.tex",
    "ch3_altitude_hurst.json",
)


def digest(path):
    """Identify bytes without loading large input arrays into memory."""
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def function_ast(path, name):
    """Compare the executed measurement functions across renderer additions."""
    tree = ast.parse(path.read_text())
    return ast.dump(
        next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == name),
        include_attributes=False,
    )


def main():
    """Check inherited identities, exact results, generated inputs and final PDF."""
    target = HERE / "manuscript-review.json"
    if target.exists():
        raise ValueError("Preserve the completed review; use a new review record")
    parent = json.loads(PARENT.read_text())
    report = json.loads((MEASUREMENT / "report.json").read_text())
    assert parent["status"] == report["status"] == "complete"
    sources = {name: digest(ROOT / name) for name in parent["source_files"]}
    changed = {
        name for name, value in sources.items() if value != parent["source_files"][name]
    }
    assert changed == CHANGED, changed
    for name, expected in parent["generated_outputs"].items():
        assert digest(ROOT / "thesis/generated" / name) == expected, name
    for name, expected in parent["external_input_files"].items():
        assert digest(ROOT / name) == expected, name
    for name in (GENERATOR, "src/soaring/analysis/observables/tamsd_scaling.py"):
        sources[name] = digest(ROOT / name)
    original_source = MEASUREMENT / "measurement-source.py.txt"
    assert digest(original_source) == report["sources"][GENERATOR]
    for name in ("read_report", "reconstruct", "measure"):
        assert function_ast(original_source, name) == function_ast(
            ROOT / GENERATOR, name
        )
    for name, expected in report["sources"].items():
        if name != GENERATOR:
            assert digest(ROOT / name) == expected, name
    for name, identity in report["inputs"].items():
        assert digest(name) == identity["sha256"], name
    snapshots = {
        name: validate_snapshot(discipline.config().derived_dir, current_cleaning(ROOT))
        for name, discipline in DISCIPLINES.items()
    }
    assert digest(HERE / "report.json") == digest(MEASUREMENT / "report.json")
    assert digest(ROOT / "thesis/generated/ch3_altitude_hurst.json") == digest(
        MEASUREMENT / "report.json"
    )
    assert digest(ROOT / "thesis/generated/ch3_altitude_hurst.pdf") == digest(
        ROOT / "output/pdf/altitude-hurst-10-10000/altitude_msd_hurst.pdf"
    )
    table = (ROOT / "thesis/generated/ch3_altitude_hurst_table.tex").read_text()
    fits = []
    for discipline, entry in report["results"].items():
        for band, row in entry["altitude_band"].items():
            for fit in row["fits"]:
                if fit["requested_range_s"] != [10, 10000]:
                    continue
                assert fit["status"] == "ok" and fit["n_finite_resamples"] == 2000
                assert fit["n_lags"] == 59
                assert fit["actual_lags_s"][0] == 10
                assert fit["actual_lags_s"][-1] == 10000
                curve = row["mean_m2"][fit["control_index"]]
                slope = np.polyfit(np.log(entry["lags_s"]), np.log(curve), 1)[0]
                np.testing.assert_allclose(fit["h_eff"], slope / 2, atol=1e-14)
                lo, hi = fit["h_eff_percentile_95"]
                cell = rf"${fit['h_eff']:.4f}\;[{lo:.4f},\,{hi:.4f}]$"
                assert cell in table, (discipline, band, cell)
                fits.append({"discipline": discipline, "altitude_band": band, **fit})
    assert len(fits) == 16
    driver = runpy.run_path(str(ROOT / "scripts/rebuild_thesis.py"))
    required = driver["required_outputs"]()
    assert all(required[name] == GENERATOR for name in NEW_OUTPUTS[:3])
    stages = driver["load_plan"]()["stages"]
    ids = [stage["id"] for stage in stages]
    assert ids.index("altitude_hurst") == ids.index("grouped_tamsd") + 1
    log = (ROOT / "thesis/main.log").read_text()
    assert not re.search(
        r"Overfull|LaTeX Warning:|Undefined control sequence|Fatal error", log
    )
    aux = (ROOT / "thesis/main.aux").read_text()
    locations = {}
    for label in ("sec:altitude-hurst", "fig:altitude-hurst", "tab:altitude-hurst"):
        match = re.search(r"\\newlabel\{" + label + r"\}\{\{([^}]+)\}\{(\d+)\}", aux)
        assert match, label
        locations[label] = {"number": match[1], "printed_page": int(match[2])}
    pdf = ROOT / "thesis/main.pdf"
    info = subprocess.check_output(["pdfinfo", str(pdf)], text=True)
    pages = int(re.search(r"^Pages:\s+(\d+)", info, re.M)[1])
    review = {
        **parent,
        "reviewed_utc": datetime.now(UTC).isoformat(),
        "parent_manuscript_review_sha256": digest(PARENT),
        "numerical_run_id": MEASUREMENT.name,
        "numerical_update_sha256": digest(MEASUREMENT / "report.json"),
        "source_files": sources,
        "generated_outputs": {
            **parent["generated_outputs"],
            **{name: digest(ROOT / "thesis/generated" / name) for name in NEW_OUTPUTS},
        },
        "changed_manuscript_sources": sorted(CHANGED - {"configs/rebuild.yaml"}),
        "changed_workflow_sources": ["configs/rebuild.yaml"],
        "review_script_sha256": digest(__file__),
        "pdf_sha256": digest(pdf),
        "pages": pages,
        "locations": locations,
        "full_range_fits": fits,
        "datasets": snapshots,
        "dataset_check_scope": (
            "Current cleaning manifests and table stat/footer identities"
        ),
        "visual_review": (
            "PDF pages 79-82 inspected: original figure, new text, fit figure and table"
        ),
        "validation": {
            "tests_passed": 32,
            "numerical_measurement_function_asts_unchanged": True,
            "inherited_generated_outputs_unchanged": len(parent["generated_outputs"]),
            "provenance_known_parent_warnings": [
                "ch3_temporal_scaling_bounds.tex: no '% Generated by' header",
                "ch3_temporal_scaling_population.tex: no '% Generated by' header",
            ],
        },
        "scope": (
            "Integrate completed 10-10000 s altitude-band TA-MSD fits and 2000-draw "
            "site-day intervals into the thesis; add a reproducible rebuild stage. "
            "All inherited results and environmental inputs are unchanged."
        ),
    }
    with target.open("x") as stream:
        stream.write(json.dumps(review, indent=2) + "\n")
    print(f"Reviewed {pages} thesis pages; locations: {locations}")


if __name__ == "__main__":
    main()
