"""Tests for the barometric-against-GNSS offset measurement.

The synthetic flights below are built from the physics the module claims to invert: a
barometric channel that under-reads a warm atmosphere in proportion to height, against a
GNSS channel displaced by a constant reference-surface offset. What the tests check is
that the measured slope returns the temperature departure that was put in, and that the
three exclusions (one channel, a duplicated channel, a broken one) each remove exactly
the flights they are meant to.
"""

import numpy as np
import pandas as pd
import pytest

from soaring.analysis import alt_offset

# R_d T / g at the ICAO sea-level temperature, computed here from the constants rather
# than imported, so the assertion is not the implementation restated.
SCALE_HEIGHT_ISA = 287.0528 * 288.15 / 9.80665


# --------------------------------------------------------------------------- #
# the standard atmosphere the offset is read against
# --------------------------------------------------------------------------- #
def test_scale_height_at_standard_temperature():
    assert alt_offset.scale_height_m() == pytest.approx(SCALE_HEIGHT_ISA, rel=1e-12)
    assert alt_offset.scale_height_m() == pytest.approx(8434.5, abs=0.5)


def test_scale_height_grows_with_temperature():
    assert alt_offset.scale_height_m(300.0) > alt_offset.scale_height_m(280.0)


def test_metres_per_hectopascal_is_the_altimeter_subscale():
    # The familiar 27 ft/hPa: about 8.3 m of altitude per hectopascal of QNH error.
    assert alt_offset.metres_per_hpa() == pytest.approx(8.32, abs=0.02)
    # And the number the thesis quotes for a 10 hPa departure.
    assert 10 * alt_offset.metres_per_hpa() == pytest.approx(83.0, abs=1.0)


def test_isa_mean_temperature_is_the_midpoint_temperature():
    # Constant lapse rate: the layer mean is the temperature at half the height.
    assert alt_offset.isa_mean_temperature_k(0.0) == pytest.approx(288.15)
    assert alt_offset.isa_mean_temperature_k(2000.0) == pytest.approx(
        288.15 - 0.0065 * 1000.0
    )


def test_temperature_departure_inverts_the_slope():
    # Air 10 K warmer than standard makes the altimeter under-read by h*dT/T, i.e. a
    # slope of -dT/T in (baro - gnss) against height.
    altitude, departure = 2000.0, 10.0
    slope = -departure / alt_offset.isa_mean_temperature_k(altitude)
    assert alt_offset.temperature_departure_k(slope, altitude) == pytest.approx(
        departure
    )


def test_temperature_departure_signs():
    # Warmer than standard -> the barometric channel falls away from the GNSS one.
    assert alt_offset.temperature_departure_k(-0.03, 1500.0) > 0
    assert alt_offset.temperature_departure_k(+0.03, 1500.0) < 0


# --------------------------------------------------------------------------- #
# sigma_mad
# --------------------------------------------------------------------------- #
def test_sigma_mad_matches_the_deviation_of_a_clean_sample():
    rng = np.random.default_rng(0)
    x = rng.normal(loc=-90.0, scale=50.0, size=20_000)
    assert alt_offset.sigma_mad(x) == pytest.approx(50.0, rel=0.05)


def test_sigma_mad_ignores_a_tail_that_a_standard_deviation_follows():
    """The reason it is used: a handful of broken channels must not set the scale."""
    clean = np.zeros(1000)
    clean[:999] = np.linspace(-1.0, 1.0, 999)
    contaminated = np.append(clean, [1e5] * 20)
    assert alt_offset.sigma_mad(contaminated) < 1.0
    assert np.std(contaminated) > 1000.0


def test_sigma_mad_drops_non_finite_and_refuses_a_tiny_sample():
    assert alt_offset.sigma_mad([1.0, np.nan, 2.0, 3.0, np.inf]) > 0
    assert np.isnan(alt_offset.sigma_mad([1.0, 2.0]))


# --------------------------------------------------------------------------- #
# measure_flight, on synthetic tracks
# --------------------------------------------------------------------------- #
def _write_flight(tmp_path, baro, gnss, *, name="t.igc", header="AXXX test"):
    """One IGC file at 1 Hz from two altitude series, 45 deg N 7 deg E."""
    lines = [header]
    for i, (b, g) in enumerate(zip(baro, gnss, strict=True)):
        hh, mm, ss = i // 3600, (i % 3600) // 60, i % 60
        lines.append(
            f"B{hh:02d}{mm:02d}{ss:02d}4530000N00730000EA{int(b):05d}{int(g):05d}"
        )
    path = tmp_path / name
    path.write_text("\n".join(lines) + "\n")
    return path


def _climb(n=1200, top=2000.0):
    """A flight climbing from 200 m to `top` and levelling off in the second half."""
    ramp = np.linspace(200.0, top, n // 2)
    return np.concatenate([ramp, np.full(n - n // 2, top)])


def test_measure_flight_recovers_a_constant_offset(tmp_path):
    truth = _climb()
    path = _write_flight(tmp_path, truth - 90.0, truth)
    row = alt_offset.measure_flight(path)
    assert row["both"] is True
    assert row["med_offset"] == pytest.approx(-90.0, abs=1.0)
    assert row["iqr_offset"] == pytest.approx(0.0, abs=1.0)
    assert row["slope"] == pytest.approx(0.0, abs=1e-3)


def test_measure_flight_recovers_the_temperature_departure(tmp_path):
    """The whole decomposition: a warm-day scale error read back as kelvin."""
    truth = _climb()
    departure = 10.0
    factor = departure / alt_offset.isa_mean_temperature_k(float(np.median(truth)))
    path = _write_flight(tmp_path, truth * (1.0 - factor), truth)
    row = alt_offset.measure_flight(path)
    recovered = alt_offset.temperature_departure_k(row["slope"], row["alt_med"])
    assert recovered == pytest.approx(departure, rel=0.1)


def test_measure_flight_reads_an_in_flight_window(tmp_path):
    """Ground fixes at both ends must not enter: the barometer is still settling."""
    truth = _climb(n=1000)
    baro = truth - 90.0
    baro[:60] -= 400.0  # a settling sensor before take-off
    baro[-60:] -= 400.0
    path = _write_flight(tmp_path, baro, truth)
    row = alt_offset.measure_flight(path)
    assert row["med_offset"] == pytest.approx(-90.0, abs=2.0)


def test_measure_flight_reports_drift(tmp_path):
    truth = np.full(1200, 1500.0)
    drift = np.linspace(0.0, 40.0, 1200)
    path = _write_flight(tmp_path, truth - 90.0 + drift, truth)
    row = alt_offset.measure_flight(path)
    # 40 m over the record; the window drops 10% at each end and compares the
    # medians of its first and last fifth, so what is left is most of the ramp.
    assert row["drift"] == pytest.approx(25.0, abs=6.0)


def test_measure_flight_flags_a_duplicated_channel(tmp_path):
    truth = _climb()
    row = alt_offset.measure_flight(_write_flight(tmp_path, truth, truth))
    assert row["frac_equal"] == pytest.approx(1.0)
    assert row["both"] is True  # present on both counts, but not two channels


def test_measure_flight_without_a_barometer(tmp_path):
    truth = _climb()
    path = _write_flight(tmp_path, np.zeros_like(truth), truth)
    row = alt_offset.measure_flight(path)
    assert row["both"] is False
    assert row["baro_frac"] == pytest.approx(0.0)
    assert row["gnss_frac"] == pytest.approx(1.0)
    assert np.isnan(row["med_offset"])  # nothing to compare


def test_measure_flight_skips_a_short_file(tmp_path):
    truth = np.full(50, 1500.0)
    assert alt_offset.measure_flight(_write_flight(tmp_path, truth, truth)) is None


def test_measure_flight_withholds_a_slope_without_a_climb(tmp_path):
    """Over a flat stretch the regression would read noise, so it is not run."""
    truth = np.full(1200, 1500.0)
    row = alt_offset.measure_flight(_write_flight(tmp_path, truth - 90.0, truth))
    assert row["alt_range"] < alt_offset.SLOPE_MIN_RANGE_M
    assert np.isnan(row["slope"])


def test_measure_flight_records_the_recorder(tmp_path):
    truth = _climb()
    path = _write_flight(tmp_path, truth - 90.0, truth, header="AXCT Cpilot")
    assert alt_offset.measure_flight(path)["logger"].startswith("AXCT")


def test_scan_offsets_returns_one_row_per_usable_file(tmp_path):
    truth = _climb()
    paths = [
        _write_flight(tmp_path, truth - 90.0, truth, name="a.igc"),
        _write_flight(tmp_path, truth - 40.0, truth, name="b.igc"),
        _write_flight(tmp_path, np.full(50, 1500.0), np.full(50, 1500.0), name="c.igc"),
    ]
    table = alt_offset.scan_offsets(paths)
    assert list(table.columns) == alt_offset.COLUMNS
    assert len(table) == 2  # the 50-fix file is too short to measure


# --------------------------------------------------------------------------- #
# the exclusions, and the two groupings
# --------------------------------------------------------------------------- #
def _table(**overrides):
    base = pd.DataFrame(
        {
            "both": [True, True, True, False, True],
            "med_offset": [-90.0, -40.0, 0.0, np.nan, -5000.0],
            "frac_equal": [0.0, 0.02, 1.0, np.nan, 0.0],
        }
    )
    return base.assign(**overrides)


def test_independent_keeps_only_two_real_channels():
    keep = alt_offset.independent(_table())
    # kept: the two genuine offsets. dropped: the duplicated channel, the
    # single-channel flight, and the one whose offset is a broken sensor.
    assert keep.tolist() == [True, True, False, False, False]


def test_group_scatter_needs_enough_flights_and_recorders():
    table = pd.DataFrame(
        {
            "site": ["A"] * 4 + ["B"] * 3,
            "date": ["d"] * 4 + ["d"] * 3,
            "logger": ["L1", "L2", "L3", "L4", "L1", "L1", "L1"],
            "med_offset": [-100.0, -90.0, -110.0, -95.0, -50.0, -60.0, -70.0],
        }
    )
    # Site B has three flights but one recorder: it cannot speak about instruments.
    groups = alt_offset.group_scatter(
        table, ["site", "date"], min_flights=3, min_loggers=3
    )
    assert len(groups) == 1
    assert groups["n"].iloc[0] == 4
    assert groups["span"].iloc[0] == pytest.approx(20.0)
    # Without the recorder requirement both groups qualify.
    assert len(alt_offset.group_scatter(table, ["site"], min_flights=3)) == 2


def test_group_scatter_drops_groups_that_are_too_small():
    table = pd.DataFrame(
        {"site": ["A", "A", "B"], "logger": list("xyz"), "med_offset": [1.0, 2.0, 3.0]}
    )
    assert alt_offset.group_scatter(table, ["site"], min_flights=3).empty


def test_fallback_completeness_counts_only_the_barometerless():
    table = pd.DataFrame(
        {
            "baro_frac": [1.0, 0.0, 0.0, 0.3],
            "gnss_frac": [1.0, 1.0, 0.4, 0.99],
        }
    )
    complete, fallback = alt_offset.fallback_completeness(table)
    assert fallback == 3  # three flights have no usable barometric channel
    assert complete == 2  # two of them carry a complete GNSS one
