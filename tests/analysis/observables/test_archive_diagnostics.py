"""Full-archive estimators preserve flight identity and recording boundaries."""

import importlib.util
import json
from pathlib import Path

import numpy as np
import pytest

from soaring.analysis.observables.archive_diagnostics import (
    DiskFrames,
    archive_quantile_control,
    load_measurement,
    measure_archive,
    save_measurement,
    streamed_mardia,
)
from soaring.analysis.observables.global_diagnostics import mardia_excess
from soaring.analysis.observables.segment_support import increment_starts
from soaring.analysis.observables.self_similarity import (
    blocked_quantiles,
    ordered_quantiles,
)


def reporter():
    path = (
        Path(__file__).resolve().parents[3]
        / "scripts/reporting/ch3_global_transport/generate_revision_diagnostics.py"
    )
    spec = importlib.util.spec_from_file_location("revision_report", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def store(tmp_path, split=False):
    rng = np.random.default_rng(921)
    rows, positions, offset = [], [], 0
    for i, length in enumerate((2101, 2401, 2601)):
        pos = np.cumsum(rng.normal(size=(length, 2)), axis=0)
        rows.append(
            {
                "flight_id": str(i),
                "segment_id": 0,
                "segments": [[0, 50], [50, length]] if split else [[0, length]],
                "duration_s": (length - (51 if split else 1)) * 10,
                "offset": offset,
                "length": length,
            }
        )
        positions.append(pos)
        offset += length
    (tmp_path / "flights.json").write_text(json.dumps(rows))
    np.concatenate(positions).tofile(tmp_path / "positions.bin")
    return DiskFrames(tmp_path)


def test_full_single_segment_matches_legacy_and_cache(tmp_path):
    r = reporter()
    frames = store(tmp_path)
    expected = r.measure(list(frames))
    actual = measure_archive(
        frames, tmp_path, r.LAGS, r.SCALES, r.Q, r.PROBABILITIES, workers=1
    )
    actual["quantile_control"] = archive_quantile_control(
        actual, frames, r.LAGS, r.PROBABILITIES, r.QUANTILE_CONTROL_NAMES
    )
    for key in ("variations", "moments", "quantiles", "mardia"):
        np.testing.assert_allclose(actual[key], expected[key], rtol=2e-12, atol=2e-12)
    for key in (
        "quantiles",
        "flights_per_lag",
        "windows_per_lag",
        "fixed_origin_counts",
    ):
        np.testing.assert_allclose(
            actual["quantile_control"][key], expected["quantile_control"][key]
        )
    for scale in r.SCALES:
        np.testing.assert_allclose(
            actual["coarse"][scale], expected["coarse"][scale], equal_nan=True
        )
    save_measurement(actual, tmp_path)
    loaded = load_measurement(tmp_path)
    assert isinstance(loaded["vectors"][0], np.memmap)
    np.testing.assert_array_equal(loaded["vectors"][0], expected["vectors"][0])
    (tmp_path / ".incomplete").touch()
    with pytest.raises(ValueError, match="incomplete"):
        load_measurement(tmp_path)


def test_origins_never_join_segments():
    row = {"segments": [[0, 4], [4, 10]]}
    np.testing.assert_array_equal(increment_starts(row, 10, 2), [0, 4, 6])
    np.testing.assert_array_equal(increment_starts(row, 10, 2, order=2), [4])
    np.testing.assert_array_equal(
        increment_starts(row, 10, 2, stride=1), [0, 1, 4, 5, 6, 7]
    )


def test_streamed_fourth_order_matches_direct():
    x = np.random.default_rng(4).normal(size=(351, 2)) @ np.array([[2, 1], [-1, 3]])
    np.testing.assert_allclose(streamed_mardia(x, 31), mardia_excess(x), atol=1e-12)


def test_blocked_weighted_quantiles_match_reference_with_atoms():
    rng = np.random.default_rng(43)
    sizes = np.array([1040, 1133, 1001, 2400, 321])
    who = np.repeat(np.arange(5), sizes)
    values = rng.integers(0, 300, size=len(who))
    order = np.argsort(values, kind="stable")
    values, who = values[order], who[order]
    counts = np.vstack(
        [np.ones(5, dtype=int), rng.multinomial(5, [0.2] * 5, 30), [0, 0, 5, 0, 0]]
    )
    probabilities = [0.25, 0.5, 0.75, 0.9, 1]
    actual = blocked_quantiles(values, who, sizes, counts, probabilities, blocks=19)
    expected = np.array(
        [
            ordered_quantiles(
                values, c[who] / sizes[who], probabilities, total=float(c.sum())
            )
            for c in counts
        ]
    )
    np.testing.assert_array_equal(actual, expected)


def test_parallel_segments_match_serial_without_cross_gap(tmp_path):
    from soaring.analysis.observables.archive_diagnostics import (
        _flight_measure,
        _ordered_results,
    )

    frames = store(tmp_path, split=True)
    lags, scales = np.array([10, 80, 1000]), (10, 60)
    tasks = [(row, np.asarray(pos), lags, scales) for row, pos in frames]
    serial = list(_ordered_results(iter(tasks), 1))
    parallel = list(_ordered_results(iter(tasks), 2, batch_size=1))
    for a, b in zip(serial, parallel, strict=True):
        np.testing.assert_array_equal(a[0], b[0])
        for x, y in zip(a[1], b[1], strict=True):
            np.testing.assert_array_equal(x, y)
    row, pos = frames[0]
    shifted = np.array(pos)
    shifted[50:] += 1e8
    before = _flight_measure((row, pos, lags, scales))
    after = _flight_measure((row, shifted, lags, scales))
    np.testing.assert_allclose(before[0], after[0], rtol=1e-7)


def test_same_signed_marginals_and_radius_can_have_disjoint_joint_laws():
    from soaring.analysis.observables.joint_distribution import (
        histogram_distance,
        joint_mass,
    )

    # Exact counterexample: even signed marginals plus radius miss the dependence.
    a = np.array([[1, 2], [-1, -2]])
    b = np.array([[1, -2], [-1, 2]])
    np.testing.assert_array_equal(np.sort(a, axis=0), np.sort(b, axis=0))
    np.testing.assert_array_equal(np.linalg.norm(a, axis=1), np.linalg.norm(b, axis=1))
    edges = [-np.inf, -1.5, 0, 1.5, np.inf]
    assert histogram_distance(joint_mass(a, edges), joint_mass(b, edges)) == 1


def test_joint_scalar_collapse_preserves_anisotropy():
    from soaring.analysis.observables.joint_distribution import measure_joint

    t = np.arange(2101)
    frames = [
        ({"flight_id": str(i)}, np.column_stack([t * (i + 1), t * (i + 1) * 3]))
        for i in range(3)
    ]
    starts = [np.arange(100) for _ in frames]
    result = measure_joint(
        frames, starts, np.array([10, 100, 1000]), [0, 1, 2], 1, 1000
    )
    np.testing.assert_allclose(result["total_variation"], 0)
    for law in result["laws"]:
        assert np.isclose(np.sum(law["mass"]), 1)


def test_reused_tamsd_components_and_cohorts_match_direct():
    from soaring.analysis.observables.transport import (
        TAMSDAccumulator,
        time_averaged_msd,
    )

    rng = np.random.default_rng(900)
    east, north = np.cumsum(rng.normal(size=(2, 309)), axis=1)
    zero = np.zeros_like(east)
    curve = time_averaged_msd(east, zero, 5) + time_averaged_msd(zero, north, 5)
    direct, reused = (
        TAMSDAccumulator(np.geomspace(1, 1000, 40)),
        TAMSDAccumulator(np.geomspace(1, 1000, 40)),
    )
    direct.add(east, north, 5)
    reused.add_curve(curve, 5)
    np.testing.assert_allclose(
        direct.result().msd, reused.result().msd, rtol=1e-12, atol=1e-10
    )
    np.testing.assert_array_equal(direct.result().n_flights, reused.result().n_flights)


def test_collect_keeps_all_segments_across_storage_boundaries(tmp_path):
    from types import SimpleNamespace

    import pandas as pd
    import pyarrow as pa
    import pyarrow.parquet as pq

    from soaring.analysis.observables.archive_diagnostics import collect_archive
    from soaring.analysis.observables.global_diagnostics import declared_task_class

    rows = []
    for flight_id in ("11", "12"):
        for segment_id, step in ((0, 5), (1, 5), (2, 15)):
            for t in np.arange(0, 100, step):
                rows.append(
                    {
                        "flight_id": flight_id,
                        "segment_id": segment_id,
                        "t": t + segment_id * 200,
                        "E": float(t),
                        "N": float(t * 2),
                    }
                )
    pq.write_table(
        pa.Table.from_pandas(pd.DataFrame(rows)),
        tmp_path / "fixes.parquet",
        row_group_size=17,
    )
    pd.DataFrame(
        {"flight_id": ["11", "12"], "lat0": [45.0, 45.0], "lon0": [6.0, 6.0]}
    ).to_parquet(tmp_path / "flights_meta.parquet")
    pd.DataFrame(
        {"flight_id": ["11", "12"], "flight_type": ["dist libre", "triangle"]}
    ).to_csv(tmp_path / "catalog.csv", index=False)
    glider = SimpleNamespace(
        derived_dir=lambda: tmp_path,
        catalog_path=lambda: tmp_path / "catalog.csv",
        slug="test",
    )
    frames, provenance = collect_archive(
        glider,
        tmp_path / "frames",
        {"Alps": (5, 10, 43, 47)},
        declared_task_class,
        lambda p: str(p),
    )
    assert len(frames) == provenance["eligible_flights"] == 2
    assert provenance["eligible_segments"] == 4
    assert provenance["excluded_segments"]["cadence_above_10s"] == 2
    assert frames[0][0]["segment_ids"] == [0, 1]
    assert frames[1][0]["closed"]
    assert len(increment_starts(frames[0][0], len(frames[0][1]), 1)) == 18


def test_joint_and_scaling_report_renders_from_disk_frames(tmp_path):
    from soaring.reporting.self_similarity import write_report

    r = reporter()
    frames = store(tmp_path, split=True)
    measurement = measure_archive(
        frames, tmp_path, r.LAGS, r.SCALES, r.Q, r.PROBABILITIES, workers=1
    )
    measurement["quantile_control"] = archive_quantile_control(
        measurement, frames, r.LAGS, r.PROBABILITIES, r.QUANTILE_CONTROL_NAMES
    )
    result = write_report(
        {"paragliders": measurement, "hang gliders": measurement},
        {},
        {"lags_s": r.LAGS.tolist()},
        tmp_path / "report",
        n_resamples=5,
    )
    assert (tmp_path / "report/ch3_joint_para.pdf").stat().st_size > 1000
    joint = result["results"]["paragliders"]["joint"]
    np.testing.assert_allclose(np.diag(joint["total_variation"]), 0)
    assert result["results"]["paragliders"]["n_flights"] == 3


def test_chunked_regional_geometry_matches_direct_joint_covariance():
    from soaring.analysis.observables.archive_diagnostics import region_geometry
    from soaring.analysis.observables.global_diagnostics import covariance_geometry

    rng = np.random.default_rng(10)
    xy = rng.normal(size=(1800, 2)) @ np.array([[2, 0.7], [0.2, 1]])
    who = np.repeat(np.arange(18), 100)
    selected = np.arange(18) < 12
    count, actual = region_geometry(xy, who, selected, chunk_size=37)
    expected = covariance_geometry(xy[selected[who]])
    assert count == 12
    for key in ("mean", "covariance", "ratio", "correlation", "angle_deg"):
        np.testing.assert_allclose(actual[key], expected[key], atol=1e-12)
