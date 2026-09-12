"""Review the focused wind-height extension without changing its completed parent."""

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
import yaml

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
PARENT = ROOT / "revisions/environment-axis-integration-2026-09-12"
BASE = (
    ROOT
    / "revisions/vertical-gap-split-2026-09-11/recovery-runs"
    / "20260912T133040Z-073601cb/review-inputs/manifest.json"
)
sys.path.insert(0, str(ROOT / "src"))
from soaring.analysis.observables.wind_reference import wind_at_height  # noqa: E402
from soaring.reporting.snapshot import current_cleaning, validate_snapshot  # noqa: E402


def digest(path):
    """Identify complete saved file bytes."""
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def write(path, value):
    """Save a readable provenance record."""
    path.write_text(json.dumps(value, indent=2) + "\n")


def main():
    """Verify inherited results, new inputs and the compiled manuscript."""
    parent_path = PARENT / "numerical-update.json"
    parent = json.loads(parent_path.read_text())
    earlier = json.loads((PARENT / "manuscript-review.json").read_text())
    baseline = json.loads(BASE.read_text())
    assert parent["status"] == earlier["status"] == "complete"
    assert earlier["numerical_update_sha256"] == digest(parent_path)
    replaced = {
        "ch3_channel_wind.json",
        "ch3_channel_wind.pdf",
        "ch3_channel_wind_values.tex",
    }
    inherited = {
        n: h for n, h in earlier["generated_outputs"].items() if n not in replaced
    }
    for name, expected in inherited.items():
        assert digest(ROOT / "thesis/generated" / name) == expected, name
    for name, expected in earlier["external_input_files"].items():
        assert digest(ROOT / name) == expected, name
    producer = (
        "scripts/reporting/ch3_global_transport/generate_channel_wind_comparison.py"
    )
    for name, expected in earlier["source_files"].items():
        if not name.startswith(("src/", "scripts/", "configs/")):
            continue
        if digest(ROOT / name) != expected:
            assert name in {producer, "configs/rebuild.yaml"}, name
            if name == "configs/rebuild.yaml":
                previous = subprocess.check_output(
                    ["git", "show", "85105df:" + name], cwd=ROOT
                )
                assert hashlib.sha256(previous).hexdigest() == expected
                current = yaml.safe_load((ROOT / name).read_text())
                current["stages"] = [
                    s for s in current["stages"] if s["id"] != "channel_flight_altitude"
                ]
                assert current == yaml.safe_load(previous)
    cleaning = current_cleaning(ROOT)
    assert cleaning == baseline["cleaning"] == parent["cleaning"]
    for discipline, directory in (
        ("paragliders", "/Volumes/SSD_DISANTE/paragliders/ffvl_cfd_igc/derived"),
        ("hang gliders", "/Volumes/SSD_DISANTE/hang_gliders/delta_cfd_igc/derived"),
    ):
        assert (
            validate_snapshot(Path(directory), cleaning)
            == baseline["datasets"][discipline]
        )
    altitude_path = ROOT / "thesis/generated/ch3_channel_flight_altitude.json"
    altitude = json.loads(altitude_path.read_text())
    assert digest(altitude_path) == digest(HERE / "flight-altitude.json")
    for name, expected in altitude["sources"].items():
        assert digest(ROOT / name) == expected, name
    windows = [h for row in altitude["flights"] for h in row["window_mean_altitudes_m"]]
    assert len(altitude["flights"]) == 1680 and len(windows) == 2013
    assert np.mean(windows) == altitude["mean_altitude_m"]
    old = json.loads((HERE / "parent-channel-wind.json").read_text())
    assert (
        digest(HERE / "parent-channel-wind.json")
        == earlier["generated_outputs"]["ch3_channel_wind.json"]
    )
    wind = json.loads((ROOT / "thesis/generated/ch3_channel_wind.json").read_text())
    for key, estimate in old["estimates"].items():
        assert wind["estimates"][key] == estimate, key
    assert wind["producer_sha256"] == digest(ROOT / producer)
    assert wind["flight_altitude_sha256"] == digest(altitude_path)
    assert wind["flight_report_sha256"] == inherited["ch3_revision.json"]
    manifest_path = HERE / "pressure-input-manifest.json"
    manifest = json.loads(manifest_path.read_text())
    assert wind["pressure_input_manifest_sha256"] == digest(manifest_path)
    assert (
        digest(HERE / "pressure-wind.npz")
        == manifest["files_sha256"]["pressure-wind.npz"]
    )
    # Independently check random profiles using scalar interpolation, including
    # their hourly height conversion, instead of the vectorised bracket search.
    with np.load(HERE / "pressure-wind.npz") as data:
        geopotential_h = data["z"].astype(float) / 9.80665
        height = 6371000 * geopotential_h / (6371000 - geopotential_h)
        target = altitude["mean_altitude_m"]
        u, v = wind_at_height(data["u"], data["v"], height, target)
        generator = np.random.default_rng(20260913)
        for _ in range(500):
            i, j = generator.integers(9), generator.integers(87672)
            np.testing.assert_allclose(
                u[i, j], np.interp(target, height[i, j], data["u"][i, j]), atol=1e-12
            )
            np.testing.assert_allclose(
                v[i, j], np.interp(target, height[i, j], data["v"][i, j]), atol=1e-12
            )
        weights = np.cos(np.deg2rad(data["latitude"]))
        np.testing.assert_allclose(
            wind["estimates"]["height_all_hours"]["mean_east_ms"],
            np.sum(u * weights[:, None]) / (87672 * weights.sum()),
            atol=1e-12,
        )
        assert wind["estimates"]["height_daytime"]["hours_per_cell"] == 32877
        assert wind["estimates"]["height_warm_daytime"]["hours_per_cell"] == 16470
    assert wind["vertical_coverage"]["sensitivity_excluded_hours_per_cell"] == 868
    assert wind["vertical_coverage"]["sensitivity_common_hours_per_cell"] == 86804
    for item in wind["height_sensitivity"].values():
        assert item["estimates"]["all_hours"]["hours_per_cell"] == 86804
    write(
        HERE / "numerical-audit.json",
        {
            "status": "complete",
            "altitude_flights": 1680,
            "altitude_windows": 2013,
            "scalar_profile_checks": 500,
            "surface_estimates_unchanged": True,
            "sensitivity_common_hours_per_cell": 86804,
            "sensitivity_excluded_hours_per_cell": 868,
            "all_profiles_bracketed_above_ground": wind["vertical_coverage"][
                "all_profiles_bracketed_above_ground"
            ],
            "flight_report_unchanged": True,
            "pressure_inputs_sha256": digest(HERE / "pressure-wind.npz"),
        },
    )
    outputs = {}
    for script in (
        producer,
        "scripts/reporting/ch3_global_transport/measure_channel_flight_altitude.py",
    ):
        names = next(
            ast.literal_eval(n.value)
            for n in ast.parse((ROOT / script).read_text()).body
            if isinstance(n, ast.Assign)
            and any(
                isinstance(t, ast.Name) and t.id == "GENERATED_OUTPUTS"
                for t in n.targets
            )
        )
        for name in names:
            outputs[name] = {
                "sha256": digest(ROOT / "thesis/generated" / name),
                "producer": script,
                "historical_control": False,
            }
    external = dict(earlier["external_input_files"])
    for name in (
        "pressure-wind.npz",
        "pressure-input-manifest.json",
        "flight-altitude.json",
        "fetch_pressure_wind.py",
    ):
        path = HERE / name
        external[str(path.relative_to(ROOT))] = digest(path)
    merged = inherited | {n: r["sha256"] for n, r in outputs.items()}
    required = runpy.run_path(str(ROOT / "scripts/rebuild_thesis.py"))[
        "required_outputs"
    ]()
    assert set(required) <= set(merged), set(required) - set(merged)
    update = {
        "status": "complete",
        "run_id": HERE.name,
        "parent_run_id": parent["run_id"],
        "parent_update_sha256": digest(parent_path),
        "baseline_run_id": baseline["run_id"],
        "cleaning": cleaning,
        "operation": (
            "Mean altitude on exact coastal PCA windows and independent ERA5 "
            "pressure-level wind interpolation; previous surface estimates and "
            "all flight transport measurements unchanged"
        ),
        "outputs": outputs,
        "external_input_files": external,
        "parent_generated_outputs": earlier["generated_outputs"],
        "numerical_audit_sha256": digest(HERE / "numerical-audit.json"),
    }
    update_path = HERE / "numerical-update.json"
    if update_path.exists():
        assert json.loads(update_path.read_text()) == update
    else:
        write(update_path, update)
    paths = set()
    for pattern in (
        "src/**/*.py",
        "scripts/**/*.py",
        "configs/*.yaml",
        "thesis/sections/*.tex",
        "thesis/appendices/**/*.tex",
    ):
        paths.update(ROOT.glob(pattern))
    paths.update(
        ROOT / n for n in ("thesis/main.tex", "thesis/references.bib", "uv.lock")
    )
    sources = {str(p.relative_to(ROOT)): digest(p) for p in sorted(paths)}
    with (HERE / "manuscript-build.log").open("w") as log:
        subprocess.run(
            [
                "latexmk",
                "-pdf",
                "-halt-on-error",
                "-interaction=nonstopmode",
                "-cd",
                "thesis/main.tex",
            ],
            cwd=ROOT,
            stdout=log,
            stderr=subprocess.STDOUT,
            check=True,
        )
    assert sources == {str(p.relative_to(ROOT)): digest(p) for p in sorted(paths)}
    log = (ROOT / "thesis/main.log").read_text()
    assert not re.search(
        r"Overfull|LaTeX Warning:|Undefined control sequence|Fatal error", log
    )
    pages = int(re.search(r"Output written on main.pdf \((\d+) pages", log)[1])
    write(
        HERE / "manuscript-review.json",
        {
            "status": "complete",
            "reviewed_utc": datetime.now(UTC).isoformat(),
            "numerical_run_id": HERE.name,
            "baseline_numerical_run_id": baseline["run_id"],
            "numerical_update_sha256": digest(update_path),
            "pdf_sha256": digest(ROOT / "thesis/main.pdf"),
            "pages": pages,
            "source_files": sources,
            "generated_outputs": merged,
            "external_input_files": external,
            "scope": (
                "Coastal wind is evaluated at mean altitude of the exact PCA windows. "
                "Annual all-hour and daytime references are separated from seasonal "
                "checks. Pressure-level interpolation, GNSS datum approximation, "
                "height sensitivity and limits of causal interpretation are explicit. "
                "Other numerical results are unchanged."
            ),
        },
    )
    print(
        f"Reviewed {pages} pages, {len(inherited)} inherited and "
        f"{len(outputs)} wind/altitude outputs"
    )


if __name__ == "__main__":
    main()
