import numpy as np
import pandas as pd
import pytest

from soaring.analysis.preproc.resample import resample_flight
from soaring.analysis.preproc.smoothing import (
    DROP_WINDOW_TOO_WIDE,
    KINEMATIC_COLUMNS,
    SMOOTHED_COLUMNS,
    SavgolWindows,
    savgol_window,
    savgol_windows,
    smooth_flight,
    smooth_segment,
)
from soaring.analysis.preprocessing import (
    SamplingThresholds,
    SavgolParams,
    load_preproc_config,
)

SAMPLING = SamplingThresholds(
    max_gap_factor=10.0,
    max_gap_seconds=20.0,
    max_missing_fraction=0.10,
    min_segment_duration_s=90.0,
)
# The adopted parameters: p = 3, and the three timescales the July 2026 measurement
# found to coincide at 5 s (test_adopted_config_gives_one_window_for_every_channel pins
# them to configs/preprocessing.yaml).
SAVGOL = SavgolParams(
    polyorder=3,
    tau_c_horizontal_s=5.0,
    tau_c_vertical_baro_s=5.0,
    tau_c_vertical_gnss_s=5.0,
)


def _cubic_flight(duration_s=600.0, dt=1.0):
    """A flight whose every coordinate is an exact cubic in time.

    A Savitzky-Golay filter of order p reproduces any polynomial of degree <= p exactly,
    and so does each of its derivatives -- edge windows included, since the edge fit is
    exact too. A cubic track therefore has an answer the filter must return to machine
    precision, for the position, the velocity *and* the acceleration at once.
    """
    t = np.arange(0.0, duration_s + dt, dt)
    return pd.DataFrame(
        {
            "t": t,
            "E": 3.0 + 12.0 * t - 0.004 * t**2 + 1e-6 * t**3,
            "N": -5.0 + 7.0 * t + 0.002 * t**2 - 4e-7 * t**3,
            "z": 1000.0 + 1.5 * t - 0.001 * t**2 + 2e-7 * t**3,
        }
    )


def _cubic_truth(t):
    """The exact position, velocity and acceleration of :func:`_cubic_flight`."""
    return {
        "E": (3.0 + 12.0 * t - 0.004 * t**2 + 1e-6 * t**3),
        "v_E": (12.0 - 0.008 * t + 3e-6 * t**2),
        "a_E": (-0.008 + 6e-6 * t),
        "z": (1000.0 + 1.5 * t - 0.001 * t**2 + 2e-7 * t**3),
        "v_z": (1.5 - 0.002 * t + 6e-7 * t**2),
        "a_z": (-0.002 + 12e-7 * t),
    }


def _run(flight, savgol=SAVGOL, *, alt_source="baro"):
    """Stage (vi) then stage (vii), the way the pipeline chains them."""
    resampled = resample_flight(flight, SAMPLING)
    return smooth_flight(resampled, savgol, alt_source=alt_source)


# --------------------------------------------------------------------------------
# The window rule (sec:savgol item (i))
# --------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("dt", "expected", "binding_rule"),
    [
        (0.2, 25, "tau_c / dt = 25, already odd"),
        (0.5, 11, "tau_c / dt = 10, rounded up to odd"),
        (1.0, 5, "the two rules coincide: 5 samples span exactly tau_c"),
        (2.0, 5, "the floor binds already here (tau_c / dt = 2.5 < 5)"),
        (5.0, 5, "the floor binds"),
        (10.0, 5, "the floor binds"),
    ],
)
def test_the_window_follows_the_cadence_until_the_floor(dt, expected, binding_rule):
    assert savgol_window(5.0, dt, 3) == expected


def test_every_window_is_odd_and_at_least_five():
    # Odd so the window has a centre sample to evaluate at; five is the smallest window
    # on which a cubic fit is meaningfully determined (sec:savgol).
    for dt in np.linspace(0.1, 30.0, 300):
        w = savgol_window(5.0, float(dt), 3)
        assert w % 2 == 1
        assert w >= 5


def test_the_floor_follows_the_order_if_the_order_ever_changes():
    # p + 2, rounded up to odd: one sample more than would determine the polynomial
    # exactly, so that it stays a least-squares fit and not an interpolation.
    assert savgol_window(5.0, 10.0, 3) == 5
    assert savgol_window(5.0, 10.0, 4) == 7
    assert savgol_window(5.0, 10.0, 5) == 7


def test_the_vertical_window_is_conditioned_on_the_altitude_source():
    # The per-channel machinery of sec:savgol item (iii), exercised with the asymmetry
    # that was expected a priori but not measured: a noisier GNSS vertical would take a
    # longer window than the barometric one.
    savgol = SavgolParams(
        polyorder=3,
        tau_c_horizontal_s=5.0,
        tau_c_vertical_baro_s=3.0,
        tau_c_vertical_gnss_s=12.0,
    )
    assert savgol_windows(savgol, 1.0, alt_source="baro") == SavgolWindows(5, 5, 3)
    assert savgol_windows(savgol, 1.0, alt_source="gnss") == SavgolWindows(5, 13, 3)
    with pytest.raises(ValueError, match="alt_source"):
        savgol_windows(savgol, 1.0, alt_source="baro_or_gnss")


def test_adopted_config_gives_one_window_for_every_channel():
    # The measured result, not an assumption: the three knees coincide at ~0.2 Hz
    # because every channel's floor is the IGC quantization, so the adopted windows are
    # equal even though the machinery keeps them apart.
    savgol = load_preproc_config().savgol
    assert savgol.polyorder == 3
    for alt_source in ("baro", "gnss"):
        windows = savgol_windows(savgol, 1.0, alt_source=alt_source)
        assert windows == SavgolWindows(horizontal=5, vertical=5, polyorder=3)


# --------------------------------------------------------------------------------
# What the filter returns
# --------------------------------------------------------------------------------


@pytest.mark.parametrize("dt", [1.0, 2.0, 5.0])
def test_a_cubic_track_is_reproduced_exactly_with_its_derivatives(dt):
    # The filter is exact on polynomials up to its own order, so this pins the whole
    # chain at once -- and, because dt varies, it pins the *units*: the fit's per-sample
    # coefficients become m/s and m/s^2 through delta = dt, the only place the cadence
    # enters (sec:savgol).
    out = _run(_cubic_flight(dt=dt))
    truth = _cubic_truth(out.fixes["t"].to_numpy())

    assert list(out.fixes.columns) == SMOOTHED_COLUMNS
    for name, expected in truth.items():
        assert out.fixes[name].to_numpy() == pytest.approx(expected, rel=1e-6, abs=1e-9)


def test_the_velocity_has_the_units_of_the_flight_not_of_the_samples():
    # The trap this guards: a 10 s logger whose velocity comes out 10x too large because
    # the fit was read in samples and never divided by dt.
    t = np.arange(0.0, 600.0, 10.0)
    flight = pd.DataFrame(
        {"t": t, "E": 20.0 * t, "N": np.zeros_like(t), "z": 1000.0 - 1.2 * t}
    )
    out = _run(flight)
    assert out.windows == SavgolWindows(5, 5, 3)
    assert out.fixes["v_E"].to_numpy() == pytest.approx(20.0)
    assert out.fixes["v_z"].to_numpy() == pytest.approx(-1.2)
    assert out.fixes["a_E"].to_numpy() == pytest.approx(0.0, abs=1e-9)


def test_smoothing_beats_finite_differences_on_a_noisy_track():
    # Why the filter is there at all: differencing raw coordinates amplifies the
    # high-frequency noise, and the same window that smooths the position returns a
    # velocity from a fit rather than from a difference. The gain on white noise is
    # real but not dramatic at w = 5, p = 3 -- a cubic spends its degrees of freedom on
    # curvature, which is exactly the trade sec:savgol makes on purpose (item (ii)):
    # what p = 3 buys is a velocity that responds to the acceleration varying across
    # the window, not the lowest possible variance.
    rng = np.random.default_rng(20260803)
    t = np.arange(0.0, 900.0)
    clean = 15.0 * t
    noisy = clean + rng.normal(0.0, 2.0, t.size)  # ~2 m of GPS noise per fix
    flight = pd.DataFrame(
        {"t": t, "E": noisy, "N": np.zeros_like(t), "z": np.full(t.size, 1000.0)}
    )
    out = _run(flight)
    interior = out.fixes[~out.fixes["edge"]]

    finite_difference = np.diff(noisy)  # dt = 1 s, so this is already m/s
    naive = float(np.std(finite_difference - 15.0))
    filtered = float(np.std(interior["v_E"].to_numpy() - 15.0))
    assert naive == pytest.approx(2.0 * np.sqrt(2.0), rel=0.1)  # sqrt(2) sigma / dt
    assert filtered < 0.75 * naive
    # The position is pulled towards the truth too, not merely differentiated.
    residual = interior["E"].to_numpy() - clean[~out.fixes["edge"].to_numpy()]
    assert float(np.std(residual)) < 2.0


def test_a_thermal_circle_returns_its_own_speed_and_centripetal_acceleration():
    # The regime the analysis actually lives in: a 200 m circle at a 60 s period. The
    # circle is not a cubic, so the filter does attenuate it -- but its window is twelve
    # times shorter than the period, so the attenuation stays well under a percent.
    radius, period = 200.0, 60.0
    omega = 2.0 * np.pi / period
    t = np.arange(0.0, 600.0)
    flight = pd.DataFrame(
        {
            "t": t,
            "E": radius * np.sin(omega * t),
            "N": radius * (1.0 - np.cos(omega * t)),
            "z": 1000.0 + 2.0 * t,
        }
    )
    out = _run(flight)
    interior = out.fixes[~out.fixes["edge"]]

    speed = np.hypot(interior["v_E"], interior["v_N"])
    centripetal = np.hypot(interior["a_E"], interior["a_N"])
    assert speed.to_numpy() == pytest.approx(omega * radius, rel=0.01)
    assert centripetal.to_numpy() == pytest.approx(omega**2 * radius, rel=0.02)
    assert interior["v_z"].to_numpy() == pytest.approx(2.0, rel=1e-3)


# --------------------------------------------------------------------------------
# Segment boundaries (sec:savgol, "The window never crosses a segment boundary")
# --------------------------------------------------------------------------------


def test_the_window_never_crosses_a_segment_boundary():
    # Two segments with opposite motion, split by a gap. If the filter ran across the
    # boundary, the samples on either side would be contaminated by the other segment;
    # because each segment is exactly linear, contamination is visible to machine
    # precision.
    t_a = np.arange(0.0, 300.0)
    t_b = np.arange(400.0, 700.0)
    t = np.concatenate([t_a, t_b])
    east = np.concatenate([10.0 * t_a, -10.0 * (t_b - 400.0)])
    flight = pd.DataFrame(
        {"t": t, "E": east, "N": np.zeros_like(t), "z": np.full(t.size, 1000.0)}
    )
    out = _run(flight)

    first = out.fixes[out.fixes["segment_id"] == 0]
    second = out.fixes[out.fixes["segment_id"] == 1]
    assert first["v_E"].to_numpy() == pytest.approx(10.0)
    assert second["v_E"].to_numpy() == pytest.approx(-10.0)
    # ...including the samples right at the boundary, where a shared window would show.
    assert first["v_E"].iloc[-1] == pytest.approx(10.0)
    assert second["v_E"].iloc[0] == pytest.approx(-10.0)


def test_the_off_centre_samples_are_flagged_at_each_segment_edge():
    # sec:savgol: near a boundary the polynomial is fitted on the nearest full window
    # and evaluated off-centre, which is an extrapolation and carries more variance.
    # Those samples are marked, so an observable sensitive to it can skip them.
    out = _run(_cubic_flight(duration_s=300.0))
    edge = out.fixes["edge"].to_numpy()

    assert out.windows.horizontal == 5
    assert edge[:2].all() and edge[-2:].all()  # w // 2 = 2 samples at each end
    assert not edge[2:-2].any()
    assert int(edge.sum()) == 4


def test_a_segment_too_short_for_the_window_is_dropped_alone():
    # The segment gate of stage (vi) guarantees the window fits up to dt = 22.5 s; in
    # the thin tail of slower loggers it does not, and the segment is dropped with its
    # reason rather than silently smoothed with a narrower window.
    dt = 30.0
    t = np.concatenate([np.arange(0.0, 331.0, dt), np.arange(600.0, 691.0, dt)])
    flight = pd.DataFrame(
        {"t": t, "E": 10.0 * t, "N": np.zeros_like(t), "z": 1000.0 + 0.5 * t}
    )
    out = _run(flight)

    assert out.segments["kept"].tolist() == [True, False]
    assert out.segments.loc[1, "drop_reason"] == DROP_WINDOW_TOO_WIDE
    assert out.segments.loc[1, "n_fix"] == 0
    assert out.fixes["segment_id"].unique().tolist() == [0]
    assert out.drop_reason is None


def test_a_flight_whose_every_segment_is_too_short_is_dropped():
    dt = 30.0
    t = np.arange(0.0, 121.0, dt)  # 5 grid points... but the gate needs 5, so shrink
    flight = pd.DataFrame(
        {"t": t[:4], "E": 10.0 * t[:4], "N": np.zeros(4), "z": 1000.0 + 0.5 * t[:4]}
    )
    out = smooth_flight(
        resample_flight(flight, SamplingThresholds(10.0, 20.0, 0.10, 60.0)), SAVGOL
    )
    assert out.drop_reason == DROP_WINDOW_TOO_WIDE
    assert out.fixes.empty
    assert list(out.fixes.columns) == SMOOTHED_COLUMNS


def test_a_flight_already_dropped_upstream_passes_through_with_its_own_reason():
    # Stage (vii) must not overwrite the verdict of stage (vi), nor try to configure a
    # filter for a flight that has no cadence to configure it from.
    one_fix = pd.DataFrame({"t": [0.0], "E": [0.0], "N": [0.0], "z": [1000.0]})
    out = smooth_flight(resample_flight(one_fix, SAMPLING), SAVGOL)

    assert out.drop_reason == "no_native_cadence"
    assert out.windows is None
    assert out.fixes.empty


# --------------------------------------------------------------------------------
# What the stage carries and what it replaces
# --------------------------------------------------------------------------------


def test_the_stored_position_is_the_filtered_one_and_the_flags_survive():
    # Design principle: only the filter's outputs are stored, never a raw and a filtered
    # copy of the same quantity. The two per-sample cautions travel together.
    flight = _cubic_flight(duration_s=300.0)
    flight["hampel_flagged"] = flight["t"] == 100.0
    holed = flight[flight["t"] != 150.0].reset_index(drop=True)
    out = _run(holed)

    assert list(out.fixes.columns) == [*SMOOTHED_COLUMNS, "hampel_flagged"]
    assert out.fixes["interpolated"].sum() == 1
    assert out.fixes.loc[out.fixes["t"] == 150.0, "interpolated"].item() is True
    assert out.fixes["hampel_flagged"].sum() == 1
    # E is now the smoothed position: on a cubic track it still equals the truth --
    # to a third of a millimetre, the trace of the one grid point PCHIP had to
    # reconstruct, which is not exact on a cubic the way the filter itself is.
    truth = _cubic_truth(out.fixes["t"].to_numpy())
    assert out.fixes["E"].to_numpy() == pytest.approx(truth["E"], abs=1e-3)


def test_smooth_segment_refuses_a_segment_it_cannot_fit_a_window_into():
    short = pd.DataFrame(
        {
            "t": np.arange(4.0),
            "E": np.zeros(4),
            "N": np.zeros(4),
            "z": np.full(4, 1000.0),
        }
    )
    with pytest.raises(ValueError, match="shorter than the 5-sample"):
        smooth_segment(short, SavgolWindows(5, 5, 3), 1.0)


def test_the_kinematic_columns_are_the_ones_the_schema_promises():
    out = _run(_cubic_flight(duration_s=200.0))
    assert KINEMATIC_COLUMNS == ["v_E", "v_N", "v_z", "a_E", "a_N", "a_z"]
    assert set(KINEMATIC_COLUMNS) <= set(out.fixes.columns)
    assert np.all(np.isfinite(out.fixes[KINEMATIC_COLUMNS].to_numpy()))


def test_the_filter_does_not_eat_the_displacement_it_is_meant_to_measure():
    """The fourth acceptance criterion of sec:savgol, on the observable itself.

    The window is floored at five samples, so in *seconds* it is 5*dt for any logger
    slower than 1 Hz -- 150 s at a 30 s cadence, which reaches the lower end of the
    range the MSD exponent is fitted over. Whether that matters is a question about the
    observable, not about the window: a cubic Savitzky-Golay filter reproduces a locally
    cubic trajectory exactly, and a strongly correlated trajectory is locally close to
    cubic, so it should pass through untouched.

    Read the way the pipeline reads it. The frame origin is the *raw* first fix, exactly
    (0, 0) by construction (sec:enu), and the stored coordinates are the smoothed ones,
    so the observable is |r_smoothed(t)|^2. Using the smoothed *first sample* as the
    reference instead adds that one edge sample's variance to every lag and reads as a
    spurious excess; the first version of this test did exactly that.
    """
    from scipy.signal import savgol_filter

    def ratio(alpha, window, noise, trials=400, n=128, seed=7):
        """Measured MSD over true MSD, per lag, for a process of known exponent."""
        rng = np.random.default_rng(seed)
        hurst = alpha / 2.0
        t = np.arange(1, n + 1, dtype=float)
        cov = 0.5 * (
            t[:, None] ** (2 * hurst)
            + t[None, :] ** (2 * hurst)
            - np.abs(t[:, None] - t[None, :]) ** (2 * hurst)
        )
        chol = np.linalg.cholesky(cov + 1e-9 * np.eye(n))
        true = np.zeros(n)
        measured = np.zeros(n)
        for _ in range(trials):
            walk = np.vstack([[0.0, 0.0], chol @ rng.normal(size=(n, 2))])
            seen = walk + rng.normal(0.0, noise, walk.shape)
            filtered = np.column_stack(
                [savgol_filter(seen[:, k], window, 3, mode="interp") for k in (0, 1)]
            )
            true += walk[1:, 0] ** 2 + walk[1:, 1] ** 2
            measured += filtered[1:, 0] ** 2 + filtered[1:, 1] ** 2
        return measured / true

    # (1) The filter alone, on the regime the archive shows: transparent.
    clean = ratio(1.8, savgol_window(5.0, 1.0, 3), noise=0.0)
    assert abs(clean[1] - 1.0) < 0.03, "two samples: the filter should barely be felt"
    assert np.abs(clean[2:] - 1.0).max() < 0.01, (
        f"from three samples on the filter moves the MSD by "
        f"{100 * np.abs(clean[2:] - 1.0).max():.2f} %"
    )

    # (2) With measurement noise the short-lag MSD is *inflated*, not suppressed: an
    # independent error of sd sigma per component adds ~2 sigma^2 at every lag, which
    # dominates wherever the true displacement is of that order. The floor decays as the
    # motion grows past it, and it is what makes the first decade of the MSD figure an
    # instrument reading rather than a transport one.
    noisy = ratio(1.8, savgol_window(5.0, 1.0, 3), noise=3.0)
    assert noisy[0] > 4.0 and noisy[63] < 1.02
    # Decaying, checked on coarse checkpoints rather than sample by sample: at 400 walks
    # the ratio carries its own sampling noise, and demanding strict monotonicity of a
    # noisy sequence is an invariant about the estimator, not about the floor.
    checkpoints = [noisy[0], noisy[4], noisy[11], noisy[23], noisy[63]]
    assert checkpoints == sorted(checkpoints, reverse=True), (
        f"the noise floor should decay with the lag, got {checkpoints}"
    )

    # (3) And smoothing is what pulls that floor down, which is why it is applied.
    wider = ratio(1.8, 11, noise=3.0)
    assert wider[0] < noisy[0]
