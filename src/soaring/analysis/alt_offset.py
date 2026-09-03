r"""What the two IGC altitude channels disagree about, and what it is made of.

:mod:`soaring.analysis.altitude_noise` measures the two channels' *noise*, which is what
decides the vertical dynamics. This module measures their *offset*: the difference
``baro_alt - gnss_alt``, flight by flight, which is what decides whether a dataset built
from both channels can be read as an absolute altitude.

The question it answers is the one the mixed-source choice (thesis, ``sec:altchannel``)
leaves open. A trajectory uses one channel end to end, so no flight is ever spliced; but
the ensemble holds both kinds of flight, and if the two channels sat at systematically
different heights the pooled altitude would be bimodal by instrument rather than by
atmosphere. The objection has a natural test. The barometric altitude is a pressure read
through a standard atmosphere, so it already wanders from flight to flight as the real
atmosphere departs from that standard: if that wander is as large as the gap between the
channels, mixing them adds nothing a single-channel dataset would not already carry.

Three quantities are therefore measured per flight, over an in-flight window, and the
decomposition follows from them rather than from a model:

* the **median offset**, the constant part of the disagreement over the window;
* its **slope against height**, which isolates the term proportional to altitude. An
  altimeter reading a standard atmosphere under-reads warm air in proportion to the
  height flown, by :math:`h\,\Delta T/\bar{T}`, so this slope *is* the day's departure
  from the standard temperature profile (:func:`temperature_departure_k`), measured
  without any meteorological input;
* its **within-flight spread and drift**, which say how much of the offset survives the
  differencing that every dynamical observable performs.

What separates weather from instrument is then a grouping, not an assumption. Flights
from the same site on the same day share an air mass and a pressure setting, so what
remains between them is the instruments; flights from the same site on different days
share the geoid and the terrain, so what appears between them is the weather. The two
spreads are computed by the same function (:func:`group_scatter`) on two different keys.

Two populations are excluded, both for the same reason -- they are not two independent
channels:

* flights whose two altitude fields are byte-identical over the window
  (:data:`DUPLICATE_MIN_FRAC`), where one sensor is written into both columns;
* flights whose median offset exceeds :data:`PLAUSIBLE_MAX_M`, where one channel is
  broken rather than offset.

``pandas`` is imported at module level (as everywhere in this package); the parsing runs
in a process pool, so the per-file worker is a top-level function.
"""

from __future__ import annotations

from collections.abc import Iterable
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np
import pandas as pd

if TYPE_CHECKING:
    from numpy.typing import ArrayLike

from .altitude_noise import BARO_BORDERLINE_MARGIN, BARO_PRESENT_MIN
from .igc import parse_igc

# --- the standard atmosphere, as the altimeter uses it -------------------------------
#: Specific gas constant for dry air, J/(kg K).
R_DRY = 287.0528
#: Standard gravity, m/s^2.
G0 = 9.80665
#: ICAO sea-level temperature, K.
ISA_T0 = 288.15
#: ICAO sea-level pressure, hPa -- the reference every barometric channel here is
#: written against, since a logger has no way to know the day's actual QNH.
ISA_P0 = 1013.25
#: ICAO tropospheric lapse rate, K/m.
ISA_LAPSE = 0.0065

# --- what counts as a measurable flight ----------------------------------------------
#: Fewer fixes than this and the per-flight statistics are not worth forming.
MIN_FIX = 300
#: A channel is "present" on a flight when it carries a non-zero altitude on at least
#: this share of the fixes. Deliberately the same cut the pipeline uses to choose the
#: channel (``BARO_PRESENT_MIN`` in :mod:`soaring.analysis.altitude_noise`), so this
#: diagnostic and the pre-processing agree on which flights are barometric.
PRESENT_MIN = BARO_PRESENT_MIN
#: Share of the record dropped at each end before the offset is read. The window is an
#: in-flight one on purpose: a logger switched on in a car park and off in a field
#: brackets the flight with ground fixes, where the barometer is still settling and the
#: GNSS solution is still converging, and neither says anything about the two channels
#: in the air.
EDGE_TRIM = 0.10
#: Fraction of the window at each end used for the drift statistic (median of the last
#: block minus median of the first), which is the part of the offset that a difference
#: does *not* remove.
TAIL_FRAC = 0.20
#: A flight contributes a slope only if it climbed at least this much: regressing the
#: offset on height over a 50 m band would return the noise, not the lapse.
SLOPE_MIN_RANGE_M = 300.0
#: A flight whose two channels agree byte for byte on more than this share of the window
#: carries one sensor written into two columns, not two channels.
DUPLICATE_MIN_FRAC = 0.99
#: Beyond this, a channel is broken rather than offset: no atmosphere and no reference
#: surface puts a kilometre between the two.
PLAUSIBLE_MAX_M = 1000.0
#: Fixed altitude band the cross-discipline comparison is read in, m. The offset grows
#: with height (that is the temperature term), so comparing two disciplines that fly at
#: different altitudes means comparing them inside one band.
FIXED_BAND_M = (1500.0, 2000.0)

#: Columns of the per-flight table :func:`scan_offsets` returns.
COLUMNS = [
    "flight_id", "season", "n_fix", "baro_frac", "gnss_frac", "both", "n_win",
    "dur_s", "med_offset", "iqr_offset", "drift", "slope", "frac_equal",
    "alt_med", "alt_range", "lat", "lon", "logger",
]


def scale_height_m(temperature_k: float = ISA_T0) -> float:
    """Isothermal scale height :math:`H = R_d T/g`.

    Args:
        temperature_k: Mean virtual temperature of the layer, K.

    Returns:
        The scale height in metres (about 8.4 km at the standard sea-level
        temperature).
    """
    return R_DRY * temperature_k / G0


def metres_per_hpa(
    temperature_k: float = ISA_T0, pressure_hpa: float = ISA_P0
) -> float:
    """How far an altimeter moves for a one-hectopascal error in its reference.

    From the hydrostatic relation ``dh = -H dp/p``: an altimeter set to the standard
    sea-level pressure while the real one differs by ``dp`` reports an altitude wrong by
    this much per hectopascal, essentially independently of the height flown.

    Args:
        temperature_k: Mean virtual temperature of the layer, K.
        pressure_hpa: Pressure at which the sensitivity is evaluated, hPa.

    Returns:
        Metres per hectopascal (about 8.3 at standard sea level, the familiar
        27 ft/hPa of the altimeter subscale).
    """
    return scale_height_m(temperature_k) / pressure_hpa


def isa_mean_temperature_k(altitude_m: float) -> float:
    """Mean standard-atmosphere temperature between sea level and ``altitude_m``.

    The lapse rate is constant through the troposphere, so the layer mean is the
    temperature at half the height.

    Args:
        altitude_m: Top of the layer, m.

    Returns:
        The layer-mean temperature, K.
    """
    return ISA_T0 - ISA_LAPSE * altitude_m / 2.0


def temperature_departure_k(slope: float, altitude_m: float) -> float:
    """The day's departure from the standard temperature profile, from the offset slope.

    A pressure altimeter converts pressure to height through a fixed temperature
    profile, so in air warmer than that profile by ``dT`` it under-reads by
    ``h dT/T``: the error is proportional to the height flown. The offset against a
    GNSS altitude, which has no atmospheric model in it, therefore acquires a slope of
    ``-dT/T`` against height, and inverting that slope measures ``dT``.

    Args:
        slope: ``d(baro - gnss)/dh``, dimensionless (metres per metre).
        altitude_m: Height the slope was measured over, m, which fixes the layer-mean
            temperature to divide by.

    Returns:
        The departure ``dT`` in kelvin, positive for air warmer than standard.
    """
    return -slope * isa_mean_temperature_k(altitude_m)


def sigma_mad(values: ArrayLike) -> float:
    """Median absolute deviation, scaled to a standard deviation.

    The per-flight offsets have a tail of flights with a partly broken channel that no
    presence test catches, and a standard deviation follows that tail rather than the
    population. The scaled MAD (1.4826 sigma for a Gaussian) does not.

    Args:
        values: Anything ``numpy.asarray`` accepts; non-finite entries are dropped.

    Returns:
        The scaled MAD, or ``nan`` if fewer than three finite values are given.
    """
    x = np.asarray(values, dtype=float)
    x = x[np.isfinite(x)]
    if x.size < 3:
        return float("nan")
    return float(1.4826 * np.median(np.abs(x - np.median(x))))


def _logger_id(path: Path) -> str:
    """The recorder's ``A`` record: manufacturer and model, as the logger declares them.

    Read separately from the fixes because :func:`~soaring.analysis.igc.parse_igc`
    returns the ``B`` records only, and the instrument is exactly what the same-day
    grouping needs to vary.

    Args:
        path: The ``.igc`` file.

    Returns:
        The ``A`` record, truncated, or an empty string if the file has none before its
        first fix.
    """
    try:
        with path.open("rb") as handle:
            for raw in handle:
                line = raw.decode("latin-1", "replace").strip()
                if line.startswith("A"):
                    return line[:40]
                if line.startswith("B"):
                    break  # fixes have started: this file declares no recorder
    except OSError:
        pass
    return ""


def measure_flight(path: str | Path) -> dict | None:
    """The per-flight offset statistics for one IGC file.

    Every flight with enough fixes returns a row, including the ones that carry only one
    channel: they are the denominator of the availability fractions, and of the check
    that the GNSS fallback lands on a complete channel.

    Args:
        path: The ``.igc`` file.

    Returns:
        A row of :data:`COLUMNS`, or ``None`` if the file has fewer than
        :data:`MIN_FIX` fixes or cannot be parsed. Rows for flights without both
        channels carry ``both=False`` and leave the offset fields missing.
    """
    path = Path(path)
    try:
        fixes = parse_igc(path)
    except (OSError, ValueError):
        return None
    if len(fixes) < MIN_FIX:
        return None

    t = fixes["t"].to_numpy()
    baro = fixes["baro_alt"].to_numpy()
    gnss = fixes["gnss_alt"].to_numpy()
    has_baro = np.isfinite(baro) & (baro != 0.0)
    has_gnss = np.isfinite(gnss) & (gnss != 0.0)

    row: dict = dict.fromkeys(COLUMNS, np.nan)
    row.update(
        flight_id=path.stem.split("_")[-1],
        season=path.parent.name,
        n_fix=len(fixes),
        baro_frac=float(has_baro.mean()),
        gnss_frac=float(has_gnss.mean()),
        both=False,
        logger="",
    )
    if row["baro_frac"] < PRESENT_MIN or row["gnss_frac"] < PRESENT_MIN:
        return row
    row["both"] = True

    span = t[-1] - t[0]
    if span <= 0:
        return row
    window = (
        (t >= t[0] + EDGE_TRIM * span)
        & (t <= t[-1] - EDGE_TRIM * span)
        & has_baro
        & has_gnss
    )
    if int(window.sum()) < MIN_FIX // 3:
        return row

    t_w, baro_w, gnss_w = t[window], baro[window], gnss[window]
    offset = baro_w - gnss_w
    tail = max(1, int(TAIL_FRAC * offset.size))
    row.update(
        n_win=int(window.sum()),
        dur_s=float(t_w[-1] - t_w[0]),
        med_offset=float(np.median(offset)),
        iqr_offset=float(np.subtract(*np.percentile(offset, [75, 25]))),
        drift=float(np.median(offset[-tail:]) - np.median(offset[:tail])),
        frac_equal=float(np.mean(baro_w == gnss_w)),
        alt_med=float(np.median(baro_w)),
        alt_range=float(np.ptp(baro_w)),
        lat=float(np.median(fixes["lat"].to_numpy()[window])),
        lon=float(np.median(fixes["lon"].to_numpy()[window])),
        logger=_logger_id(path),
    )
    # The slope is the temperature term. It needs a climb under it: over a flat stretch
    # the regression reads the GNSS noise instead of the lapse.
    if row["alt_range"] >= SLOPE_MIN_RANGE_M:
        design = np.vstack([gnss_w, np.ones_like(gnss_w)]).T
        row["slope"] = float(np.linalg.lstsq(design, offset, rcond=None)[0][0])
    return row


def _measure_str(path_str: str) -> dict | None:
    """Worker wrapper: a top-level function taking a picklable argument."""
    return measure_flight(path_str)


def scan_offsets(paths: Iterable[str | Path], *, n_jobs: int = 1) -> pd.DataFrame:
    """Measure a set of IGC files, in parallel.

    Args:
        paths: The ``.igc`` files to measure.
        n_jobs: Worker processes; ``1`` runs in this one, which is what the tests use.

    Returns:
        One row per usable file, with the columns of :data:`COLUMNS`. Files too short
        or too broken to parse are absent, so the row count is not the file count.
    """
    items = [str(p) for p in paths]
    if n_jobs <= 1:
        rows = [row for row in map(_measure_str, items) if row is not None]
    else:
        with ProcessPoolExecutor(max_workers=n_jobs) as pool:
            rows = [
                row
                for row in pool.map(_measure_str, items, chunksize=16)
                if row is not None
            ]
    return pd.DataFrame(rows, columns=COLUMNS)


def independent(table: pd.DataFrame) -> pd.Series:
    """Flights carrying two genuinely independent altitude channels.

    Both channels present, an offset that was actually read, and neither of the two
    disqualifications the module docstring names: a duplicated channel
    (:data:`DUPLICATE_MIN_FRAC`) and a broken one (:data:`PLAUSIBLE_MAX_M`).

    Args:
        table: A :func:`scan_offsets` table.

    Returns:
        A boolean mask over its rows.
    """
    return (
        table["both"].fillna(False).astype(bool)
        & table["med_offset"].notna()
        & (table["frac_equal"] <= DUPLICATE_MIN_FRAC)
        & (table["med_offset"].abs() < PLAUSIBLE_MAX_M)
    )


def group_scatter(
    table: pd.DataFrame,
    keys: list[str],
    *,
    min_flights: int = 3,
    min_loggers: int = 1,
) -> pd.DataFrame:
    """Spread of the per-flight offset within groups of comparable flights.

    The whole separation of weather from instrument is this function called on two
    keys. Grouped by site and day, the flights share an air mass and a pressure
    setting, so what is left is the instruments; grouped by site alone, they share the
    reference surface and the terrain, so what appears is the atmosphere.

    Args:
        table: A :func:`scan_offsets` table, already restricted to
            :func:`independent` flights and carrying the grouping columns.
        keys: Columns to group by (e.g. ``["site"]`` or ``["site", "date"]``).
        min_flights: Groups smaller than this are dropped: a scale estimate from two
            flights is not one.
        min_loggers: Distinct ``logger`` values a group must contain. Set to 3 for the
            same-day grouping, where the claim being measured is about *instruments*
            and a group of flights from one recorder cannot support it.

    Returns:
        One row per surviving group: ``n``, ``n_loggers``, ``sigma`` (the scaled MAD of
        the offsets) and ``span`` (their full range).
    """
    rows = []
    for _, block in table.dropna(subset=keys).groupby(keys, sort=True):
        n_loggers = int(block["logger"].nunique())
        if len(block) < min_flights or n_loggers < min_loggers:
            continue
        rows.append(
            {
                "n": len(block),
                "n_loggers": n_loggers,
                "sigma": sigma_mad(block["med_offset"]),
                "span": float(np.ptp(block["med_offset"].to_numpy())),
            }
        )
    return pd.DataFrame(rows, columns=["n", "n_loggers", "sigma", "span"])


def fallback_completeness(table: pd.DataFrame) -> tuple[int, int]:
    """How often the GNSS fallback lands on a complete channel.

    The pipeline sends a flight without a barometric channel to GNSS
    (``sec:altchannel``) without ever checking that the channel it falls back to is
    itself complete -- a gap the implementation appendix admits, because the cached
    track scan carries no GNSS-completeness column. This scan does carry one.

    Args:
        table: A :func:`scan_offsets` table, over the whole sample and not only the
            two-channel flights.

    Returns:
        ``(complete, fallback)``: the number of barometric-absent flights whose GNSS
        channel covers at least :data:`PRESENT_MIN` of their fixes, and the number of
        barometric-absent flights.
    """
    fallback = table["baro_frac"] < PRESENT_MIN
    complete = fallback & (table["gnss_frac"] >= PRESENT_MIN)
    return int(complete.sum()), int(fallback.sum())


def borderline_gnss_advantage(table: pd.DataFrame) -> tuple[int, int]:
    """Whether the fallback improves on the channel it leaves, in the borderline band.

    Away from the cut the fallback needs no defence: a barometric channel written as
    zero throughout says nothing about a GNSS solution computed independently. The band
    just under the cut is the one where it does, since a flight present on nine tenths
    of its fixes has a defect rather than no sensor, and the pipeline sends it to GNSS
    without ever comparing the two (``impl:altchannel``). The comparison is one column
    against another, and both are in this scan.

    Args:
        table: A :func:`scan_offsets` table over the whole sample.

    Returns:
        ``(better, borderline)``: within the band
        ``[PRESENT_MIN - BARO_BORDERLINE_MARGIN, PRESENT_MIN)``, the number of flights
        whose GNSS channel covers at least as many fixes as their barometric one, and
        the number of flights in the band.
    """
    frac = table["baro_frac"]
    band = (frac >= PRESENT_MIN - BARO_BORDERLINE_MARGIN) & (frac < PRESENT_MIN)
    better = band & (table["gnss_frac"] >= frac)
    return int(better.sum()), int(band.sum())


def recorder_make(logger: pd.Series) -> pd.Series:
    """The recorder's make, from the ``A`` record's manufacturer code.

    The IGC ``A`` record is ``A`` followed by a three-character manufacturer code, then
    a unique-ID field and free text (the FAI/IGC specification), so the full record
    identifies a *device* and its first four characters identify a *make*. Both
    groupings are used here: the device is what "three distinct recorders on the same
    day" counts, and the make is what :func:`between_group_spread` compares.

    Args:
        logger: The ``logger`` column of a :func:`scan_offsets` table.

    Returns:
        The four-character prefix, empty where the file declared no recorder.
    """
    return logger.fillna("").str.slice(0, 4)


def between_group_spread(
    table: pd.DataFrame, key: str, *, min_flights: int = 50
) -> tuple[int, float, float]:
    """How far apart whole groups of flights sit, rather than flights within a group.

    :func:`group_scatter` answers what varies inside a group; this answers what varies
    between them, which is the question a recorder model raises. It is an upper bound on
    the instrument-family effect and not a measurement of it: a recorder model is also a
    period, a price and a set of sites, and this scan holds no way to hold those fixed.

    Args:
        table: A :func:`scan_offsets` table, restricted to :func:`independent` flights.
        key: The column defining a group (``"logger"``).
        min_flights: Groups smaller than this are ignored, so a model carried by a
            handful of flights cannot set the spread.

    Returns:
        ``(n_groups, sigma, span)``: the number of groups kept, the scaled MAD of their
        median offsets, and the full range of those medians.
    """
    medians = (
        table.dropna(subset=[key, "med_offset"])
        .groupby(key)["med_offset"]
        .agg(["median", "size"])
    )
    medians = medians[medians["size"] >= min_flights]["median"]
    if len(medians) < 2:
        return len(medians), float("nan"), float("nan")
    return len(medians), sigma_mad(medians), float(np.ptp(medians.to_numpy()))
