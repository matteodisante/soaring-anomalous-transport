"""Audit the paraglider circuit split and its compiled thesis delivery."""

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
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
SCRIPT = "scripts/reporting/ch3_global_transport/generate_altitude_hurst.py"
sys.path[:0] = [str(ROOT / "src"), str((ROOT / SCRIPT).parent)]
from soaring.reporting import PARAGLIDERS  # noqa: E402
from soaring.reporting.snapshot import current_cleaning, validate_snapshot  # noqa: E402

PARENT = ROOT / "revisions/altitude-hurst-thesis-2026-09-15/manuscript-review.json"
REPLACED = {
    "ch3_altitude_hurst.pdf",
    "ch3_altitude_hurst_table.tex",
    "ch3_altitude_hurst_values.tex",
    "ch3_altitude_hurst.json",
}


def digest(path):
    """Compute an input identity without loading the full file."""
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def function_ast(path, name):
    """Read executable function structure independently of rendering edits."""
    tree = ast.parse(path.read_text())
    node = next(
        n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == name
    )
    return ast.dump(node, include_attributes=False)


def main():
    """Independently join catalogue labels and verify all task-band curve cells."""
    target = HERE / "manuscript-review.json"
    if target.exists():
        raise ValueError("Preserve the completed review; use a new record")
    parent = json.loads(PARENT.read_text())
    report = json.loads((HERE / "report.json").read_text())
    assert parent["status"] == report["status"] == "complete"
    assert report["contract"]["discipline"] == "paragliders"
    assert report["contract"]["main_requested_range_s"] == [10, 10000]
    assert set(report["results"]) == {"open", "closed"}
    sources = {name: digest(ROOT / name) for name in parent["source_files"]}
    changed = {n for n, h in sources.items() if h != parent["source_files"][n]}
    assert changed == {SCRIPT, "thesis/sections/04-grouped-tamsd.tex"}, changed
    for name, expected in parent["generated_outputs"].items():
        path = ROOT / "thesis/generated" / name
        if name in REPLACED:
            path = HERE / "before" / ("thesis__generated__" + name)
        assert digest(path) == expected, name
    for name, expected in parent["external_input_files"].items():
        assert digest(ROOT / name) == expected, name
    executed = HERE / "measurement-source.py.txt"
    assert digest(executed) == report["sources"][SCRIPT]
    for name in (
        "measure",
        "reconstruct",
        "attach_declared_tasks",
        "membership_digest",
    ):
        assert function_ast(executed, name) == function_ast(ROOT / SCRIPT, name), name
    for name, expected in report["sources"].items():
        if name != SCRIPT:
            assert digest(ROOT / name) == expected, name
    for name, identity in report["inputs"].items():
        assert digest(name) == identity["sha256"], name
        assert "msd_hang" not in name

    generator = runpy.run_path(str(ROOT / SCRIPT))
    group_path = Path(next(n for n in report["inputs"] if n.endswith("report.json.gz")))
    group_report = generator["read_report"](group_path)
    arrays = Path(
        next(n for n in report["inputs"] if n.endswith("msd_para.npz"))
    ).parent
    lags, members, values = generator["reconstruct"](
        group_report, "paragliders", arrays, {}
    )
    catalog_path = Path(next(n for n in report["inputs"] if n.endswith("catalog.csv")))
    catalog = pd.read_csv(
        catalog_path, usecols=["flight_id", "flight_type"], dtype={"flight_id": str}
    ).set_index("flight_id")
    # Independent explicit map of every declared label observed in this catalogue.
    mapping = {
        **dict.fromkeys(
            ["Dist libre", "Dist 1 pt", "Dist 2 pts", "Dist 3 pts"], "open"
        ),
        **dict.fromkeys(
            ["triangle", "triangle FAI", "Quadrilatère", "Aller-Retour"], "closed"
        ),
    }
    tasks = np.array(
        [
            mapping.get(catalog.loc[f, "flight_type"], "unknown")
            for f in members.flight_id
        ]
    )
    assert {name: int(np.sum(tasks == name)) for name in np.unique(tasks)} == report[
        "population"
    ]["task_counts"]
    table = (ROOT / "thesis/generated/ch3_altitude_hurst_table.tex").read_text()
    checks = []
    for task, entry in report["results"].items():
        assert entry["discipline"] == "paragliders"
        for band, row in entry["altitude_band"].items():
            mask = (tasks == task) & members.altitude_band.eq(band).to_numpy()
            selected = values[mask]
            finite = np.isfinite(selected)
            counts = finite.sum(axis=0)
            mean = np.nansum(selected, axis=0) / counts
            np.testing.assert_array_equal(counts, row["n_flights"])
            np.testing.assert_allclose(mean, row["mean_m2"], rtol=1e-13)
            assert int(mask.sum()) == row["n_flights_total"]
            assert (
                generator["membership_digest"](members.loc[mask, "flight_id"])
                == row["flight_ids_sha256"]
            )
            fixed_mask = mask & np.isfinite(values[:, 1, -1])
            assert (
                generator["membership_digest"](members.loc[fixed_mask, "flight_id"])
                == row["fixed_flight_ids_sha256"]
            )
            for control in range(2):
                for lag_index in (0, len(lags) - 1):
                    cluster_count = np.unique(
                        members.loc[mask, "cluster"].to_numpy()[
                            finite[:, control, lag_index]
                        ]
                    ).size
                    assert cluster_count == row["n_clusters"][control][lag_index]
            for fit in row["fits"]:
                assert fit["status"] == "ok" and fit["n_finite_resamples"] == 2000
                if fit["requested_range_s"] != [10, 10000]:
                    continue
                assert fit["n_lags"] == 59
                np.testing.assert_array_equal(fit["actual_lags_s"], lags)
                slope = np.polyfit(np.log(lags), np.log(mean[fit["control_index"]]), 1)[
                    0
                ]
                np.testing.assert_allclose(fit["h_eff"], slope / 2, atol=1e-14)
                lo, hi = fit["h_eff_percentile_95"]
                cell = rf"${fit['h_eff']:.4f}\;[{lo:.4f},\,{hi:.4f}]$"
                assert cell in table, (task, band, cell)
                checks.append({"circuit_type": task, "altitude_band": band, **fit})
    assert len(checks) == 16
    assert "Hang gliders" not in table
    assert digest(ROOT / "thesis/generated/ch3_altitude_hurst.json") == digest(
        HERE / "report.json"
    )
    assert digest(ROOT / "thesis/generated/ch3_altitude_hurst.pdf") == digest(
        HERE / "figures/altitude_msd_hurst.pdf"
    )
    snapshot = validate_snapshot(
        PARAGLIDERS.config().derived_dir, current_cleaning(ROOT)
    )
    log = (ROOT / "thesis/main.log").read_text()
    assert not re.search(
        r"Overfull|LaTeX Warning:|Undefined control sequence|Fatal error", log
    )
    aux = (ROOT / "thesis/main.aux").read_text()
    locations = {}
    for label in ("sec:altitude-hurst", "fig:altitude-hurst", "tab:altitude-hurst"):
        match = re.search(r"\\newlabel\{" + label + r"\}\{\{([^}]+)\}\{(\d+)\}", aux)
        assert match
        locations[label] = {"number": match[1], "printed_page": int(match[2])}
    info = subprocess.check_output(
        ["pdfinfo", str(ROOT / "thesis/main.pdf")], text=True
    )
    pages = int(re.search(r"^Pages:\s+(\d+)", info, re.M)[1])
    review = {
        **parent,
        "reviewed_utc": datetime.now(UTC).isoformat(),
        "parent_manuscript_review_sha256": digest(PARENT),
        "numerical_run_id": HERE.name,
        "numerical_update_sha256": digest(HERE / "report.json"),
        "source_files": sources,
        "generated_outputs": {
            **parent["generated_outputs"],
            **{n: digest(ROOT / "thesis/generated" / n) for n in REPLACED},
        },
        "changed_manuscript_sources": ["thesis/sections/04-grouped-tamsd.tex"],
        "changed_workflow_sources": [SCRIPT],
        "review_script_sha256": digest(__file__),
        "pdf_sha256": digest(ROOT / "thesis/main.pdf"),
        "pages": pages,
        "locations": locations,
        "full_range_fits": checks,
        "datasets": {"paragliders": snapshot},
        "visual_review": "Printed pages 76-78 and both standalone figures inspected",
        "validation": {
            "tests_passed": 33,
            "independent_task_join_and_means": True,
            "full_range_fits_checked": 16,
            "fitted_lags_per_curve": 59,
            "inherited_generated_outputs_unchanged": 103,
            "replaced_generated_outputs": sorted(REPLACED),
            "provenance_known_parent_warnings": parent["validation"][
                "provenance_known_parent_warnings"
            ],
        },
        "scope": (
            "Replace the altitude exponent comparison with paraglider-only open/closed "
            "circuit strata, full 10-10000 s fits and 2000 site-day bootstrap draws. "
            "Preserve all other manuscript measurements and environmental inputs."
        ),
    }
    (HERE / "renderer-source.py.txt").write_bytes((ROOT / SCRIPT).read_bytes())
    with target.open("x") as stream:
        stream.write(json.dumps(review, indent=2) + "\n")
    print(
        f"Reviewed {pages} pages and 16 paraglider circuit-altitude fits: {locations}"
    )


if __name__ == "__main__":
    main()
