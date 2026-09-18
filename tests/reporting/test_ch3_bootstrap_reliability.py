"""Saved-run alignment must be checked before regrouping flight curves."""

import json
import runpy
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from soaring.analysis.observables.fixed_bootstrap import bootstrap_means, cluster_draws
from soaring.analysis.observables.fixed_transport import LAGS, cohort_manifest

MODULE = runpy.run_path(
    str(
        Path(__file__).resolve().parents[2]
        / "scripts/tesi/ch03_fixed_transport/check_bootstrap_reliability.py"
    )
)


@pytest.fixture
def saved_run(tmp_path):
    directory = tmp_path / "para"
    directory.mkdir()
    labels = np.array([0, 0, 1, 2, 3])
    rows = [{"flight_id": str(i), "segments": [(0, 1251)]} for i in range(5)]
    manifest = cohort_manifest(rows, 10000)
    (directory / "cohort-10000.json").write_text(json.dumps(manifest))
    frame = pd.DataFrame(
        {
            "flight_id": [str(i) for i in range(5)],
            "cohort_10000": True,
            "cluster": labels,
            "date": [
                "2000-01-01",
                "2000-01-01",
                "2000-01-02",
                "2000-01-05",
                "2000-01-12",
            ],
        }
    )
    frame.to_parquet(directory / "flights.parquet", index=False)
    curves = LAGS[None, :] ** np.linspace(1, 1.8, 5)[:, None]
    values = np.repeat(curves[:, None, :], 4, axis=1)
    draws = cluster_draws(labels, 30, 55)
    boot = bootstrap_means(values, labels, draws)
    np.save(directory / "flight-msd.npy", values)
    np.save(directory / "cluster-draws.npy", draws)
    np.savez(directory / "msd.npz", lags=LAGS, curves=boot)
    reference = {
        "results": {
            "para": {
                "msd_lags": LAGS.tolist(),
                "msd": {"point": boot[0].tolist()},
                "resamples": 30,
            }
        }
    }
    return tmp_path, reference


def test_loading_reconstructs_all_saved_baseline_replicates(saved_run):
    path, reference = saved_run
    frame, cohort, values, baseline, provenance = MODULE["load_inputs"](
        path, "para", reference
    )
    assert len(frame) == len(values) == cohort.sum() == 5
    np.testing.assert_allclose(baseline[0], values.mean(axis=0))
    assert provenance["cohort_sha256"]


def test_reordered_metadata_is_rejected(saved_run):
    path, reference = saved_run
    source = path / "para/flights.parquet"
    frame = pd.read_parquet(source).iloc[::-1].reset_index(drop=True)
    frame.to_parquet(source, index=False)
    with pytest.raises(AssertionError):
        MODULE["load_inputs"](path, "para", reference)


def test_missing_cohort_date_is_not_silently_dropped(saved_run):
    path, reference = saved_run
    source = path / "para/flights.parquet"
    frame = pd.read_parquet(source)
    frame.loc[0, "date"] = "0000-00-00"
    frame.to_parquet(source, index=False)
    with pytest.raises(ValueError, match="Missing cohort dates"):
        MODULE["load_inputs"](path, "para", reference)


def test_changed_bootstrap_replicates_are_rejected(saved_run):
    path, reference = saved_run
    source = path / "para/msd.npz"
    with np.load(source) as saved:
        curves = saved["curves"]
    curves[1, 3, 0] *= 2
    np.savez(source, lags=LAGS, curves=curves)
    with pytest.raises(AssertionError):
        MODULE["load_inputs"](path, "para", reference)


def test_daily_report_preserves_estimator_and_redraws_all_diagnostics(
    saved_run, tmp_path, monkeypatch
):
    import shutil

    path, reference = saved_run
    reference["status"] = "complete"
    reference["results"]["hang"] = reference["results"]["para"]
    (path / "report.json").write_text(json.dumps(reference))
    shutil.copytree(path / "para", path / "hang")
    scripts = Path(__file__).resolve().parents[2] / "scripts/tesi/ch03_fixed_transport"
    monkeypatch.syspath_prepend(str(scripts))
    module = runpy.run_path(str(scripts / "check_daily_dependence.py"))
    output = tmp_path / "daily"
    output.mkdir()
    report = module["measure"](path, output, 4)
    for slug in ("para", "hang"):
        result = report["results"][slug]
        assert result["flights"] == 5
        assert result["calendar_days"] == 12
        assert result["occupied_days"] == 4
        assert np.asarray(result["variants"]["raw"]["rho"]).shape == (5, 4)
        with np.load(output / f"{slug}-daily.npz") as saved:
            np.testing.assert_allclose(saved["raw"].sum(axis=0), 0, atol=1e-13)
            assert saved["flight_counts"].sum() == 5
    # The portable JSON contains everything needed to redraw; no cached arrays
    # or original flight files are accessed by rendering.
    portable = json.loads(json.dumps(report, allow_nan=False))
    module["render"](portable, output)
    csv = pd.read_csv(output / f"{module['PREFIX']}.csv")
    assert len(csv) == 2 * 2 * 4 * 5
    assert set(csv.statistic) == {"msd_100", "msd_1000", "msd_10000", "hurst"}
    assert (output / f"{module['PREFIX']}.pdf").stat().st_size > 0


def test_grid_report_keeps_all_flights_and_exports_reusable_cells(
    saved_run, tmp_path, monkeypatch
):
    import shutil

    path, reference = saved_run
    source = path / "para/flights.parquet"
    frame = pd.read_parquet(source)
    frame["lat0"] = 45.0
    frame["lon0"] = [5.0, 5.0, 5.0, 6.2, 8.0]
    frame["alt0"] = [1000.0, 1000.0, 1600.0, 1000.0, 100.0]
    frame["altitude_band"] = [
        "Low mountains",
        "Low mountains",
        "High mountains",
        "Low mountains",
        "Plains",
    ]
    frame.to_parquet(source, index=False)
    reference["status"] = "complete"
    reference["results"]["hang"] = reference["results"]["para"]
    (path / "report.json").write_text(json.dumps(reference))
    shutil.copytree(path / "para", path / "hang")
    before = source.read_bytes()
    scripts = Path(__file__).resolve().parents[2] / "scripts/tesi/ch03_fixed_transport"
    monkeypatch.syspath_prepend(str(scripts))
    module = runpy.run_path(str(scripts / "check_grid_bootstrap.py"))
    output = tmp_path / "grid"
    output.mkdir()
    report = module["measure"](path, output, [5, 6])
    assert source.read_bytes() == before
    assert report["grid"]["side_m"] == 50000
    assert len(report["cells"]) == report["occupied_archive_cells"]
    for slug, result in report["results"].items():
        assert len(result["configurations"]) == 36
        membership = pd.read_parquet(output / f"{slug}-membership.parquet")
        assert len(membership) == 5
        np.testing.assert_array_equal(membership.flight_id, frame.flight_id)
        with np.load(output / f"{slug}-replicates.npz") as replicates:
            observed = replicates["site_day_reference"][0]
            for config in result["configurations"]:
                assert config["side_km"] <= 50
                assert config["support"]["flights"] == 5
                np.testing.assert_allclose(
                    replicates[config["replicate_key"]][0], observed
                )
                assert config["statistics"]["hurst"]["invalid_replicates"] == 0
    portable = json.loads(json.dumps(report, allow_nan=False))
    module["render"](portable, output)
    for suffix in (
        ".pdf",
        ".csv",
        "_values.tex",
        "_support.tex",
        "_cells.csv",
        "_grid.json",
    ):
        assert (output / f"{module['PREFIX']}{suffix}").stat().st_size > 0
