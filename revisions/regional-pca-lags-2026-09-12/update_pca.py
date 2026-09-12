"""Recompute only regional PCA from verified full-archive coordinate stores.

The completed cleaning and other Chapter 3 measurements are inherited explicitly.
No existing run manifest is edited and no bootstrap or cleaning job is repeated.
"""

from __future__ import annotations

import copy
import gzip
import hashlib
import importlib.util
import json
import re
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
BASE = ROOT / "revisions/vertical-gap-split-2026-09-11"
OUT = ROOT / "thesis/generated"
sys.path.insert(0, str(ROOT / "src"))
from soaring.analysis.observables.archive_diagnostics import DiskFrames
from soaring.analysis.observables.regional_pca import PCA_LAGS_S, regional_pca
from soaring.reporting import DISCIPLINES
from soaring.reporting.regional_pca import pca_figure, pca_macros


def sha(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def write(path, value):
    Path(path).write_text(json.dumps(value, indent=2) + "\n")


def main():
    start = time.perf_counter()
    manifest_path = HERE / "numerical-update.json"
    if manifest_path.exists():
        raise RuntimeError("This completed focused run is immutable; use a new revision directory")
    baseline_path = BASE / "release/manifest.json"
    baseline = json.loads(baseline_path.read_text())
    assert baseline["status"] == "complete"
    # Verify every inherited generated input before updating the three PCA products.
    for name, record in baseline["outputs"].items():
        if sha(OUT / name) != record["sha256"]:
            raise ValueError(f"Baseline output differs: {name}")
    reporter_path = ROOT / "scripts/reporting/ch3_global_transport/generate_revision_diagnostics.py"
    spec = importlib.util.spec_from_file_location("reporter", reporter_path)
    reporter = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(reporter)
    original = json.loads((OUT / "ch3_revision.json").read_text())
    old_contract = original["measurement_contract"]
    current_contract = reporter.measurement_contract(
        old_contract["para_groups"], old_contract["hang_groups"], old_contract["per_group"]
    )
    assert reporter.jsonable(current_contract) == old_contract, "Other estimators changed"
    sources = [
        reporter_path,
        ROOT / "src/soaring/analysis/observables/regional_pca.py",
        ROOT / "src/soaring/analysis/observables/segment_support.py",
        ROOT / "src/soaring/analysis/observables/archive_diagnostics.py",
        ROOT / "src/soaring/reporting/regional_pca.py",
        ROOT / "src/soaring/reporting/style.py", Path(__file__),
    ]
    source_hashes = {str(p.relative_to(ROOT)): sha(p) for p in sources}
    duplicates = json.loads((BASE / "ssd-duplicate-verification.json").read_text())["files"]
    expected_inputs = {r["local_copy"]: r["local_identity"] for r in duplicates}
    arrays = BASE / "recovery-runs/20260912T104500Z-5cfc4e8c/arrays"
    inputs, results, comparisons, timings = {}, {}, {}, {}
    for name, glider in DISCIPLINES.items():
        directory = arrays / f"ch3-full-{glider.slug}"
        for filename in ("flights.json", "positions.bin"):
            path = directory / filename
            expected = expected_inputs[str(path)]
            stat = path.stat()
            actual = sha(path)
            if actual != expected["sha256"] or stat.st_size != expected["bytes"]:
                raise ValueError(f"Coordinate store differs from completed run: {path}")
            inputs[str(path.relative_to(ROOT))] = {
                "sha256": actual, "bytes": stat.st_size, "mtime_ns": stat.st_mtime_ns,
            }
        frames = DiskFrames(directory)
        assert len(frames) == original["results"][name]["n_flights"]
        for row, old_row in zip(frames.rows, original["provenance"][name]["flights"], strict=True):
            for key in ("flight_id", "region", "segments", "offset", "length"):
                assert row[key] == old_row[key], (name, row["flight_id"], key)
        print(f"Verified {len(frames)} {name}; measuring {PCA_LAGS_S} s", flush=True)
        measured_at = time.perf_counter()
        results[name] = regional_pca(frames, reporter.REGIONS)
        timings[name] = time.perf_counter() - measured_at
        comparisons[name] = []
        for row in results[name]:
            if row["lag_s"] not in (10, 10000):
                continue
            old = next(r for r in original["results"][name]["pca"]
                       if (r["region"], r["lag_s"]) == (row["region"], row["lag_s"]))
            assert row["n_flights"] == old["n_flights"]
            for key in ("mean", "covariance", "ratio", "correlation"):
                np.testing.assert_allclose(row[key], old[key], rtol=1e-9, atol=1e-9)
            axis_difference = abs((row["angle_deg"] - old["angle_deg"] + 90) % 180 - 90)
            assert axis_difference < 1e-7
            comparisons[name].append({"region": row["region"], "lag_s": row["lag_s"],
                                      "n_flights": row["n_flights"], "axis_difference_deg": axis_difference,
                                      "covariance_max_absolute_difference": float(np.max(np.abs(
                                          np.array(row["covariance"]) - old["covariance"])))})
        print(f"Completed {name} in {timings[name]:.1f} s; shared lags match baseline", flush=True)
    for relative, identity in inputs.items():
        stat = (ROOT / relative).stat()
        assert (stat.st_size, stat.st_mtime_ns) == (identity["bytes"], identity["mtime_ns"])
    assert {str(p.relative_to(ROOT)): sha(p) for p in sources} == source_hashes
    update = {
        "kind": "regional PCA only; all other measurements inherited",
        "baseline_run_id": baseline["run_id"],
        "baseline_report_sha256": sha(OUT / "ch3_revision.json"),
        "lags_s": PCA_LAGS_S, "grid_s": 10,
        "reference_lag_s": 1000, "estimator": "centred pooled-origin population covariance; within-segment nonoverlapping increments; all eligible flights",
        "sources": source_hashes,
        "inherited_code_provenance": "The report's code_sha256 and measurement_contract identify the inherited non-PCA measurements. This record identifies the separately recomputed PCA.",
    }
    revised = copy.deepcopy(original)
    for name, rows in results.items():
        revised["results"][name]["pca"] = rows
    revised["regional_pca_lags_s"] = list(PCA_LAGS_S)
    revised["regional_pca_update"] = update
    # Remove just the authorised changes, then compare every other value and identity.
    check = copy.deepcopy(revised)
    for name in results:
        check["results"][name]["pca"] = original["results"][name]["pca"]
    del check["regional_pca_lags_s"], check["regional_pca_update"]
    assert check == original
    write(OUT / "ch3_revision.json", revised)
    macros = pca_macros(revised["results"], DISCIPLINES)
    macro_path = OUT / "ch3_revision.tex"
    text = macro_path.read_text()
    text = "".join(line for line in text.splitlines(keepends=True)
                   if not re.match(r"\\newcommand\{\\StatRev(?:Para|Hang)Pca", line))
    text += "".join("\\newcommand{\\" + key + "}{" + value + "}\n" for key, value in macros.items())
    macro_path.write_text(text)
    fig = pca_figure(results["paragliders"], reporter.REGIONS)
    fig.canvas.draw()
    fig.savefig(OUT / "ch3_pca.pdf", metadata=reporter.PDF_META, bbox_inches="tight", pad_inches=.05)
    plt.close(fig)
    changed = {"ch3_revision.json", "ch3_revision.tex", "ch3_pca.pdf"}
    for name, record in baseline["outputs"].items():
        if name not in changed:
            assert sha(OUT / name) == record["sha256"], name
    raw = (OUT / "ch3_revision.json").read_bytes()
    archived = HERE / "ch3_revision.json.gz"
    archived.write_bytes(gzip.compress(raw, mtime=0))
    report_record = {"archive_name": archived.name, "raw_sha256": hashlib.sha256(raw).hexdigest(),
                     "raw_size_bytes": len(raw), "gzip_sha256": sha(archived),
                     "gzip_size_bytes": archived.stat().st_size}
    write(HERE / "regional-pca.json", results)
    write(manifest_path, {
        "status": "complete", "completed_utc": datetime.now(UTC).isoformat(),
        "run_id": HERE.name, "baseline_manifest": str(baseline_path.relative_to(ROOT)),
        "baseline_manifest_sha256": sha(baseline_path), "baseline_run_id": baseline["run_id"],
        "cleaning": baseline["cleaning"], "operation": update,
        "coordinate_inputs": inputs, "measurement_seconds": timings,
        "shared_lag_validation": comparisons, "all_non_pca_report_values_unchanged": True,
        "inherited_outputs_verified": len(baseline["outputs"]) - len(changed),
        "outputs": {name: {"sha256": sha(OUT / name), "historical_control": False}
                    for name in sorted(changed)},
        "compressed_report": report_record, "elapsed_seconds": time.perf_counter() - start,
    })
    print(f"Completed focused PCA update in {time.perf_counter() - start:.1f} s", flush=True)


if __name__ == "__main__":
    main()
