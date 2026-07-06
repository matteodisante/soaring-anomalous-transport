"""Parser for the ``B`` (fix) records of an IGC flight log.

An IGC file (Chapter "The dataset") stores one GPS fix per ``B`` record, at character
positions fixed by the FAI/IGC standard. This module turns a file into a tidy per-fix
table -- the basis of every downstream trajectory analysis, which so far has had only
the catalog metadata to work with.

A ``B`` record has the layout (positions are 0-based, half-open)::

    B HHMMSS DDMMmmm N DDDMMmmm E V ppppp ggggg  ...optional I-record extensions...
    0 1    7 7    15   15    24   24 25 30 30 35

so the fields read here are: UTC time ``[1:7]``, latitude ``[7:15]`` and longitude
``[15:24]`` (degrees, minutes*1000, hemisphere), the validity flag ``[24]``
(``A``/``V``), and the two altitudes in metres -- **barometric** (pressure) ``[25:30]``
then **GNSS** ``[30:35]``. A missing channel is written as zero by the standard.

The parser deliberately does *not* choose an altitude channel: it returns both, so the
pre-processing can adopt the barometric one (the thesis choice) while keeping the GNSS
one available as a per-flight fallback and for the noise diagnostics.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

# Column layout of the returned table.
COLUMNS = ["t", "lat", "lon", "valid", "baro_alt", "gnss_alt"]

# A UTC midnight roll-over makes the time of day drop by (almost) a whole day. Only a
# drop this large is treated as a new day; a smaller backward step is an out-of-order or
# corrupted fix, not a roll-over (see the unwrap logic in :func:`parse_igc`).
_MIDNIGHT_WRAP_MIN_DROP_S = 43200


def _lat(token: str) -> float:
    """Decode an 8-char latitude token ``DDMMmmmH`` into signed degrees.

    Raises:
        ValueError: If the minutes field is not a valid ``< 60`` arc-minute value, the
            hemisphere letter is not ``N``/``S``, or the decoded value falls outside
            ``[-90, 90]`` -- i.e. the token is not a valid encoding, not merely an
            unlikely one.
    """
    deg = int(token[0:2])
    minutes_raw = int(token[2:7])
    if minutes_raw >= 60000:
        raise ValueError(f"invalid latitude minutes: {token!r}")
    minutes = minutes_raw / 1000.0
    hemi = token[7]
    if hemi not in "NnSs":
        raise ValueError(f"invalid latitude hemisphere: {token!r}")
    value = deg + minutes / 60.0
    if value > 90.0:
        raise ValueError(f"latitude out of range: {token!r}")
    return -value if hemi in "Ss" else value


def _lon(token: str) -> float:
    """Decode a 9-char longitude token ``DDDMMmmmH`` into signed degrees.

    Raises:
        ValueError: If the minutes field is not a valid ``< 60`` arc-minute value, the
            hemisphere letter is not ``E``/``W``, or the decoded value falls outside
            ``[-180, 180]`` -- i.e. the token is not a valid encoding, not merely an
            unlikely one.
    """
    deg = int(token[0:3])
    minutes_raw = int(token[3:8])
    if minutes_raw >= 60000:
        raise ValueError(f"invalid longitude minutes: {token!r}")
    minutes = minutes_raw / 1000.0
    hemi = token[8]
    if hemi not in "EeWw":
        raise ValueError(f"invalid longitude hemisphere: {token!r}")
    value = deg + minutes / 60.0
    if value > 180.0:
        raise ValueError(f"longitude out of range: {token!r}")
    return -value if hemi in "Ww" else value


def _valid_time_of_day(hh: int, mm: int, ss: int) -> bool:
    """Whether ``hh:mm:ss`` is a valid 24-hour UTC time-of-day."""
    return 0 <= hh <= 23 and 0 <= mm <= 59 and 0 <= ss <= 59


def _read_lines(path: Path) -> list[str]:
    """Read an IGC file as text, tolerant of latin-1 bytes and CRLF endings."""
    raw = Path(path).read_bytes()
    text = raw.decode("latin-1", errors="replace")
    return text.replace("\r\n", "\n").replace("\r", "\n").split("\n")


def parse_igc(path: str | Path) -> pd.DataFrame:
    """Parse the ``B`` records of an IGC file into a per-fix table.

    Args:
        path: Path to the ``.igc`` file.

    Returns:
        A DataFrame with columns ``t`` (seconds elapsed from the first fix, monotonic
        with the midnight roll-over unwrapped), ``lat``/``lon`` (signed degrees, WGS84),
        ``valid`` (``True`` for an ``A`` fix, ``False`` for ``V``), and ``baro_alt``/
        ``gnss_alt`` (metres; ``0`` where the channel is absent). A record is skipped
        (not just malformed in shape) if its UTC time is not a valid 24-hour
        ``hh:mm:ss``, or if its latitude/longitude do not decode to a valid position
        (arc-minutes ``< 60``, correct hemisphere letter, within
        ``[-90, 90]``/``[-180, 180]``); this is a format-validity check, not a
        plausibility judgement on the flight dynamics, which fix-level cleaning
        (Chapter "Next steps") handles separately. A file with no valid fix yields an
        empty table with the same columns.
    """
    sec_of_day: list[int] = []
    lats: list[float] = []
    lons: list[float] = []
    valids: list[bool] = []
    baros: list[float] = []
    gnsss: list[float] = []

    for line in _read_lines(path):
        if not line.startswith("B") or len(line) < 35:
            continue
        try:
            hh, mm, ss = int(line[1:3]), int(line[3:5]), int(line[5:7])
            if not _valid_time_of_day(hh, mm, ss):
                continue  # not a ValueError (ints parsed fine): explicit range check
            lat = _lat(line[7:15])
            lon = _lon(line[15:24])
            baro = float(int(line[25:30]))
            gnss = float(int(line[30:35]))
        except ValueError:
            continue  # corrupted record: skip it rather than abort the file
        sec_of_day.append(hh * 3600 + mm * 60 + ss)
        lats.append(lat)
        lons.append(lon)
        valids.append(line[24] in "Aa")
        baros.append(baro)
        gnsss.append(gnss)

    if not sec_of_day:
        return pd.DataFrame({c: pd.Series(dtype="float64") for c in COLUMNS})

    sod = np.asarray(sec_of_day, dtype=np.int64)
    # Rebuild a monotonic elapsed time from the wall-clock time of day, which resets to
    # 0 at each UTC midnight. Only a drop of (nearly) a whole day is a real roll-over; a
    # *small* backward step is an out-of-order or corrupted fix, not a new day. The
    # naive "any decrease adds a day" would turn a few-second GPS glitch into a spurious
    # +86400 s jump, manufacturing a multi-hour gap and a wildly wrong duration. So only
    # large drops advance the day counter; any residual backward jitter is then clamped
    # (:func:`numpy.maximum.accumulate`) so the series is non-decreasing as promised.
    diffs = np.diff(sod)
    day_wraps = np.concatenate([[0], np.cumsum(diffs < -_MIDNIGHT_WRAP_MIN_DROP_S)])
    t = (sod + 86400 * day_wraps).astype(float)
    t = np.maximum.accumulate(t)
    t -= t[0]

    return pd.DataFrame(
        {
            "t": t,
            "lat": np.asarray(lats, dtype=float),
            "lon": np.asarray(lons, dtype=float),
            "valid": np.asarray(valids, dtype=bool),
            "baro_alt": np.asarray(baros, dtype=float),
            "gnss_alt": np.asarray(gnsss, dtype=float),
        },
        columns=COLUMNS,
    )


def baro_present_fraction(fixes: pd.DataFrame) -> float:
    """Fraction of fixes carrying a non-zero barometric altitude.

    A value near ``0`` means the logger has no pressure sensor (the whole ``baro_alt``
    channel is written as zero), so the flight must fall back to the GNSS altitude.

    Args:
        fixes: Table returned by :func:`parse_igc`.

    Returns:
        The fraction in ``[0, 1]`` (``0.0`` for an empty table).
    """
    if len(fixes) == 0:
        return 0.0
    return float((fixes["baro_alt"].to_numpy() != 0.0).mean())


def median_sampling_period(fixes: pd.DataFrame) -> float:
    """Median inter-fix interval in seconds (``nan`` if fewer than two fixes)."""
    if len(fixes) < 2:
        return float("nan")
    return float(np.median(np.diff(fixes["t"].to_numpy())))
