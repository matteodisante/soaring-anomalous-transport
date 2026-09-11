"""Check the fresh report's weighting and constant-drift cancellation."""

import runpy
from pathlib import Path

import numpy as np
import pytest


def test_equal_flight_variation_and_pooled_moment_have_distinct_weights():
    root = Path(__file__).resolve().parents[2]
    report = runpy.run_path(
        str(
            root
            / "scripts/reporting/ch3_global_transport/generate_revision_diagnostics.py"
        )
    )
    frames = []
    for identifier, (duration, speed) in enumerate(((1200, 1), (2400, 3))):
        times = np.arange(0, duration + 1, 10)
        position = np.column_stack([speed * times, np.zeros(len(times))])
        frames.append(({"flight_id": str(identifier)}, position))
    measured = report["measure"](frames)
    j = int(np.flatnonzero(report["LAGS"] == 10)[0])
    q = int(np.flatnonzero(report["Q"] == 2)[0])
    equal_flight = measured["variations"][:, 0, j].mean()
    assert equal_flight == pytest.approx(5 * 10**2)
    assert measured["moments"][j, q] == pytest.approx((120 + 9 * 240) / 360 * 10**2)
    second = measured["variations"][:, 1]
    assert np.all(second[np.isfinite(second)] == 0)


def test_measurement_cache_rejects_changed_estimator_or_any_source(tmp_path):
    """Metadata and task inputs invalidate measurements as well as position data."""
    import copy

    root = Path(__file__).resolve().parents[2]
    report = runpy.run_path(
        str(
            root
            / "scripts/reporting/ch3_global_transport/generate_revision_diagnostics.py"
        )
    )
    contract = report["measurement_contract"](24, 12, 40)
    paths = {name: tmp_path / name for name in ("fixes", "metadata", "tasks")}
    for path in paths.values():
        path.write_text("original")
    cached = {
        "contract": contract,
        "measured": {},
        "provenance": {
            "paragliders": {
                "inputs": {
                    name: report["file_signature"](path) for name, path in paths.items()
                }
            }
        },
    }
    assert report["validate_cache"](cached, contract) == ({}, cached["provenance"])
    changed = copy.deepcopy(contract)
    changed["estimator_sha256"] = "different estimator"
    with pytest.raises(RuntimeError, match="obsolete"):
        report["validate_cache"](cached, changed)
    with pytest.raises(RuntimeError, match="obsolete"):
        report["validate_cache"](cached, report["measurement_contract"](1, 12, 40))
    for path in paths.values():
        changed_cache = copy.deepcopy(cached)
        path.write_text("a revised source")
        with pytest.raises(RuntimeError, match="input changed"):
            report["validate_cache"](changed_cache, contract)
        cached["provenance"]["paragliders"]["inputs"][path.name] = report[
            "file_signature"
        ](path)


def test_fixed_population_quantiles_do_not_confuse_survival_with_scaling():
    root = Path(__file__).resolve().parents[2]
    report = runpy.run_path(
        str(
            root
            / "scripts/reporting/ch3_global_transport/generate_revision_diagnostics.py"
        )
    )
    # Every flight is exactly ballistic. Short fast flights disappear at large lag.
    # Replication supplies ample support at every lag, without altering the oracle.
    frames = []
    for _ in range(20):
        for duration, speed in ((5000, 4.0), (20000, 1.0), (20000, 1.0)):
            times = np.arange(0, duration + 1, 10.0)
            frames.append(({}, np.column_stack((speed * times, speed * times))))
    controlled = report["quantile_population_control"](frames)
    quantiles = controlled["quantiles"]
    np.testing.assert_array_equal(controlled["flights_per_lag"][3], 40)
    np.testing.assert_array_equal(controlled["windows_per_lag"][3], 40 * 1001)
    expected = np.sqrt(2) * report["LAGS"][:, None] * np.ones((1, 4))
    np.testing.assert_allclose(quantiles[3, :, 2], expected)
    # A changing mix creates a smaller apparent upper-quantile slope despite H=1 in every flight.
    slope = report["log_slope"](report["LAGS"], quantiles[0, :, 2, 3])[0]
    assert slope < 0.98
    for p in range(4):
        assert report["log_slope"](report["LAGS"], quantiles[3, :, 2, p])[
            0
        ] == pytest.approx(1.0)
