import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pytest

from soaring.analysis.observables.regional_pca import PCA_LAGS_S, regional_pca
from soaring.reporting.regional_pca import pca_figure


def trajectories():
    rng = np.random.default_rng(811)
    frames = []
    for i in range(10):
        lengths = (1101 + 31 * i, 1201 + 17 * i)
        pieces = []
        for k, length in enumerate(lengths):
            steps = rng.normal(size=(length, 2)) @ np.array([[2, 1], [0, 1]])
            pieces.append(steps.cumsum(axis=0) + k * 1e8)
        row = {
            "flight_id": str(i),
            "region": "Alps",
            "segments": [(0, lengths[0]), (lengths[0], sum(lengths))],
        }
        frames.append((row, np.concatenate(pieces)))
    return frames


def test_exact_lags_match_direct_pooled_covariance_and_never_bridge_gaps():
    frames = trajectories()
    records = regional_pca(frames, ("Alps", "empty"))
    assert [r["lag_s"] for r in records] == list(PCA_LAGS_S)
    for record in records:
        stride = record["lag_s"] // 10
        blocks = []
        for metadata, xy in frames:
            for first, last in metadata["segments"]:
                segment = xy[first:last]
                sampled = segment[::stride]
                blocks.append(np.diff(sampled, axis=0))
        pooled = np.concatenate(blocks)
        assert record["n_flights"] == 10
        assert record["n_increments"] == len(pooled)
        np.testing.assert_allclose(record["mean"], pooled.mean(axis=0), atol=1e-12)
        np.testing.assert_allclose(
            record["covariance"], np.cov(pooled.T, bias=True), rtol=1e-12
        )


def test_support_is_per_flight_and_per_lag():
    frames = trajectories()
    # Seven long flights and three short ones: the last lag cannot meet N >= 8.
    frames = frames[:7] + [
        ({"flight_id": str(i), "region": "Alps"}, xy[:201])
        for i, (_, xy) in enumerate(frames[7:], start=7)
    ]
    records = regional_pca(frames, ("Alps",))
    assert [r["lag_s"] for r in records] == [10, 100, 1000]
    assert all(r["n_flights"] == 10 for r in records)


@pytest.mark.parametrize("lags", [(10, 90.5), (0,), (10, 10), (np.nan,), ()])
def test_lags_must_be_supported_by_the_coordinate_grid(lags):
    with pytest.raises(ValueError, match="multiples"):
        regional_pca([], ("Alps",), lags_s=lags)


def test_duplicate_flights_cannot_inflate_regional_support():
    frames = trajectories()
    with pytest.raises(ValueError, match="Duplicate flight"):
        regional_pca(frames + frames[:1], ("Alps",))


def test_every_lag_has_an_ellipse_marker_angle_and_legend_entry():
    records = regional_pca(trajectories(), ("Alps",))
    fig = pca_figure(records, ("Alps",))
    try:
        fig.canvas.draw()
        left, right = fig.axes
        assert len(left.patches) == 4
        markers = [line for line in right.lines if line.get_marker() == "o"]
        assert [float(line.get_xdata()[0]) for line in markers] == list(PCA_LAGS_S)
        assert len(right.texts) == 4
        assert {p.get_label() for p in left.patches} == {
            f"{lag} s; N=10" for lag in PCA_LAGS_S
        }
        assert len(right.get_legend().get_texts()) == 4
    finally:
        plt.close(fig)
