"""Tests for the IGC B-record parser (pure, no network)."""

from pathlib import Path

import numpy as np
import pytest

from soaring.analysis import igc

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "sample_flight.igc"


@pytest.fixture
def fixes():
    return igc.parse_igc(FIXTURE)


def test_row_count_and_columns(fixes):
    assert list(fixes.columns) == igc.COLUMNS
    assert len(fixes) == 4  # four B records in the fixture


def test_time_elapsed_and_monotonic(fixes):
    # 30 s cadence, clock reset to the first fix.
    assert fixes["t"].tolist() == [0.0, 30.0, 60.0, 90.0]


def test_lat_lon_decoded(fixes):
    # B1143394432469N00542796E -> 44 deg 32.469' N, 005 deg 42.796' E
    assert fixes["lat"].iloc[0] == pytest.approx(44 + 32.469 / 60.0, abs=1e-6)
    assert fixes["lon"].iloc[0] == pytest.approx(5 + 42.796 / 60.0, abs=1e-6)


def test_validity_flag(fixes):
    # third fix is a V (2-D / GNSS drop-out); the rest are A.
    assert fixes["valid"].tolist() == [True, True, False, True]


def test_both_altitude_channels(fixes):
    assert fixes["baro_alt"].tolist() == [1470.0, 1475.0, 1480.0, 1485.0]
    # the V fix zeroes the GNSS altitude but keeps a valid barometric altitude.
    assert fixes["gnss_alt"].tolist() == [1556.0, 1560.0, 0.0, 1565.0]


def test_baro_present_fraction_full(fixes):
    assert igc.baro_present_fraction(fixes) == pytest.approx(1.0)


def test_median_sampling_period(fixes):
    assert igc.median_sampling_period(fixes) == pytest.approx(30.0)


def test_southern_western_hemisphere(tmp_path):
    # a single fix at 33 deg 30.000' S, 070 deg 45.000' W
    body = "B0000003330000S07045000WA010000010500"
    p = tmp_path / "s.igc"
    p.write_bytes(("AXXX\r\n" + body + "\r\n").encode("latin-1"))
    df = igc.parse_igc(p)
    assert df["lat"].iloc[0] == pytest.approx(-(33 + 30.0 / 60.0), abs=1e-6)
    assert df["lon"].iloc[0] == pytest.approx(-(70 + 45.0 / 60.0), abs=1e-6)


def test_missing_baro_channel(tmp_path):
    # a logger with no pressure sensor writes the barometric field as 00000.
    lines = [
        "AXXX",
        "B0000004432469N00542796EA000000155600",
        "B0000304432500N00542800EA000000156000",
    ]
    p = tmp_path / "nobaro.igc"
    p.write_bytes(("\r\n".join(lines) + "\r\n").encode("latin-1"))
    df = igc.parse_igc(p)
    assert igc.baro_present_fraction(df) == pytest.approx(0.0)


def test_malformed_records_are_skipped(tmp_path):
    lines = [
        "AXXX",
        "B1143394432469N00542796EA014700155600010000",  # good
        "Bshort",  # too short: skipped
        "Bxxxxxx4432469N00542796EA014700155600010000",  # non-numeric time: skipped
        "HFDTE110910",  # not a B record
    ]
    p = tmp_path / "mixed.igc"
    p.write_bytes(("\r\n".join(lines) + "\r\n").encode("latin-1"))
    df = igc.parse_igc(p)
    assert len(df) == 1


def test_empty_file_returns_empty_frame(tmp_path):
    p = tmp_path / "empty.igc"
    p.write_bytes(b"AXXX\r\nHFDTE110910\r\nGABC\r\n")
    df = igc.parse_igc(p)
    assert len(df) == 0
    assert list(df.columns) == igc.COLUMNS


@pytest.mark.parametrize(
    ("bad_record", "reason"),
    [
        ("B1143394460469N00542796EA0147001556", "latitude minutes >= 60"),
        ("B1143394432469X00542796EA0147001556", "invalid latitude hemisphere"),
        ("B1143399100000N00542796EA0147001556", "latitude out of range (91 deg)"),
        ("B1143394432469N00560469EA0147001556", "longitude minutes >= 60"),
        ("B1143394432469N00542796XA0147001556", "invalid longitude hemisphere"),
        ("B1143394432469N18100000EA0147001556", "longitude out of range (181 deg)"),
        ("B2443394432469N00542796EA0147001556", "hour 24 is not 0-23"),
        ("B1160394432469N00542796EA0147001556", "minute 60 is not 0-59"),
        ("B1143604432469N00542796EA0147001556", "second 60 is not 0-59"),
    ],
)
def test_format_invalid_records_are_rejected(tmp_path, bad_record, reason):
    # A syntactically well-formed but semantically invalid B record (bad time-of-day or
    # an impossible lat/lon encoding) must be dropped, not silently accepted.
    good = "B1143394432469N00542796EA014700155600010000"
    p = tmp_path / "invalid.igc"
    p.write_bytes(("AXXX\r\n" + good + "\r\n" + bad_record + "\r\n").encode("latin-1"))
    df = igc.parse_igc(p)
    assert len(df) == 1, f"expected only the good record to survive ({reason})"


def test_midnight_rollover(tmp_path):
    # clock crosses midnight: 235950 -> 000010 must be +20 s, not a huge negative jump.
    lines = [
        "AXXX",
        "B2359504432469N00542796EA014700155600",
        "B0000104432469N00542796EA014700155600",
    ]
    p = tmp_path / "midnight.igc"
    p.write_bytes(("\r\n".join(lines) + "\r\n").encode("latin-1"))
    df = igc.parse_igc(p)
    assert df["t"].tolist() == [0.0, 20.0]
    assert np.all(np.diff(df["t"].to_numpy()) > 0)


def test_backward_jitter_is_not_a_new_day(tmp_path):
    # A few-second backward step is an out-of-order / corrupted fix, NOT a midnight
    # roll-over. The old "any decrease adds a day" logic turned such a glitch into a
    # +86400 s jump, manufacturing a spurious multi-hour span (the "30 h on 1100 fixes"
    # pathology). Elapsed time must stay a few seconds and non-decreasing.
    lines = [
        "AXXX",
        "B1000004432469N00542796EA014700155600",  # 10:00:00
        "B1000034432469N00542796EA014700155600",  # 10:00:03
        "B1000014432469N00542796EA014700155600",  # 10:00:01  <- 2 s backward glitch
        "B1000054432469N00542796EA014700155600",  # 10:00:05
    ]
    p = tmp_path / "jitter.igc"
    p.write_bytes(("\r\n".join(lines) + "\r\n").encode("latin-1"))
    t = igc.parse_igc(p)["t"].to_numpy()
    assert t[0] == 0.0
    assert t[-1] < 60.0  # a handful of seconds, NOT ~86400+
    assert np.all(np.diff(t) >= 0.0)  # clamped to a non-decreasing series
