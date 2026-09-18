"""Sensitivity of equal-flight uncertainty to calendar-block resampling.

Blocks contain every site in a non-overlapping interval of real calendar days.
Changing block size changes the resampling unit, never the flight estimator.
Stability of its standard error is a sensitivity check, not an independence test.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from soaring.analysis.observables.fixed_transport import log_fit

CALENDAR_ANCHOR = "2000-01-01"
DIAGNOSTIC_LAGS = (100, 1000, 10000)
STATISTICS = ("msd_100", "msd_1000", "msd_10000", "hurst")


def calendar_blocks(dates, days, offset=0):
    """Label occupied calendar intervals, returning a mask for unknown dates.

    Missing dates get separate labels for archive-level draws. Callers must reject
    missing dates in the analysed cohort: singleton treatment cannot validate their
    temporal independence. Empty intervals consume calendar time but are not
    sampling units, just as empty site-day groups are absent from the baseline.
    """
    if not isinstance(days, (int, np.integer)) or days < 1:
        raise ValueError("Block duration must be a positive integer number of days")
    if not isinstance(offset, (int, np.integer)) or not 0 <= offset < days:
        raise ValueError("Offset must be an integer in [0, days)")
    dates = pd.to_datetime(pd.Series(dates), format="%Y-%m-%d", errors="coerce")
    missing = dates.isna().to_numpy()
    elapsed = (dates - pd.Timestamp(CALENDAR_ANCHOR)).dt.days
    keys = (elapsed[~missing].to_numpy(dtype=np.int64) - offset) // days
    labels = np.full(len(dates), -1, dtype=np.int64)
    labels[~missing] = np.unique(keys, return_inverse=True)[1]
    first_unknown = int(labels.max(initial=-1)) + 1
    labels[missing] = first_unknown + np.arange(missing.sum())
    return labels, missing


def boundary_offsets(days):
    """Use the anchor and two approximately equally spaced boundary shifts."""
    return sorted({0, days // 3, (2 * days) // 3})


def block_support(labels, cohort):
    """Count contributing blocks and describe unequal flight mass per block.

    The inverse squared mass sum is a size-balance diagnostic, not an estimate of
    the number of statistically independent observations.
    """
    labels = np.asarray(labels)
    cohort = np.asarray(cohort, dtype=bool)
    if labels.ndim != 1 or cohort.shape != labels.shape or not cohort.any():
        raise ValueError("Expected labels and a nonempty matching cohort mask")
    _, sizes = np.unique(labels[cohort], return_counts=True)
    mass = sizes / sizes.sum()
    return {
        "archive_blocks": len(np.unique(labels)),
        "contributing_blocks": len(sizes),
        "cohort_flights": int(sizes.sum()),
        "flights_per_block_median": float(np.median(sizes)),
        "flights_per_block_p95": float(np.percentile(sizes, 95)),
        "largest_block_fraction": float(mass.max()),
        "size_balance_index": float(1 / np.sum(mass**2)),
    }


def diagnostic_statistics(lags, curves):
    """Extract three MSD levels and refit H on each entire bootstrap curve."""
    lags = np.asarray(lags)
    curves = np.asarray(curves)
    if curves.ndim != 2 or curves.shape[1] != len(lags):
        raise ValueError("Expected a replicate-by-lag matrix")
    indices = []
    for lag in DIAGNOSTIC_LAGS:
        matches = np.flatnonzero(lags == lag)
        if len(matches) != 1:
            raise ValueError(f"Expected exactly one lag at {lag} s")
        indices.append(matches[0])
    return np.column_stack(
        [curves[:, indices], log_fit(lags, curves, (10, 10000))["slope"] / 2]
    )


def uncertainty_summary(statistics):
    """Summarise bootstrap SEs and intervals, excluding the observed row.

    Monte Carlo SE quantifies simulation error in the estimated bootstrap SD via
    the fourth central moment and a delta approximation. It is not sampling error
    in the blocking diagnostic itself and does not validate interval coverage.
    """
    statistics = np.asarray(statistics, dtype=float)
    if statistics.ndim != 2 or statistics.shape[1] != len(STATISTICS):
        raise ValueError("Expected four diagnostics, with observed values first")
    output = {}
    for j, name in enumerate(STATISTICS):
        sample = statistics[1:, j]
        sample = sample[np.isfinite(sample)]
        if len(sample) < 2:
            raise ValueError(f"Insufficient bootstrap support for {name}")
        variance = float(np.var(sample, ddof=1))
        se = np.sqrt(variance)
        fourth = np.mean((sample - sample.mean()) ** 4)
        variance_mc = max(
            0.0,
            (fourth - (len(sample) - 3) / (len(sample) - 1) * variance**2)
            / len(sample),
        )
        lo, hi = np.percentile(sample, [5, 95])
        output[name] = {
            "point": float(statistics[0, j]),
            "se": float(se),
            "se_monte_carlo": float(np.sqrt(variance_mc) / (2 * se)) if se else 0.0,
            "low": float(lo),
            "high": float(hi),
            "valid_replicates": len(sample),
            "invalid_replicates": int(len(statistics) - 1 - len(sample)),
        }
    return output


def diagnostic_influence(lags, values):
    """Per-flight contributions for relative MSDs and the fitted H.

    A sample average of these centred contributions is the first-order change
    in the statistic. MSD contributions are exact, divided by the observed MSD.
    H uses the derivative of the fit to the population curve, not per-flight fits.
    """
    lags = np.asarray(lags, dtype=float)
    values = np.asarray(values, dtype=float)
    if (
        values.ndim != 2
        or values.shape[1] != len(lags)
        or len(values) < 2
        or not np.isfinite(values).all()
        or (values < 0).any()
    ):
        raise ValueError("Expected finite nonnegative flight-by-lag MSDs")
    means = values.mean(axis=0)
    if (means <= 0).any():
        raise ValueError("Positive population MSDs are required")
    relative = values / means - 1
    take = (lags >= 10) & (lags <= 10000)
    x = np.log(lags[take])
    if len(x) < 3 or np.ptp(x) == 0:
        raise ValueError("H needs at least three fit lags")
    weights = (x - x.mean()) / (2 * np.sum((x - x.mean()) ** 2))
    indices = []
    for lag in DIAGNOSTIC_LAGS:
        matches = np.flatnonzero(lags == lag)
        if len(matches) != 1:
            raise ValueError(f"Expected exactly one lag at {lag} s")
        indices.append(matches[0])
    return np.column_stack([relative[:, indices], relative[:, take] @ weights])


def daily_contributions(dates, contributions, *, centre_months=False):
    """Sum flight contributions on the full calendar, retaining empty dates.

    An empty date contributes zero to the observed estimator; this is not an
    imputed flight value. Optional month-of-year centring is flight-weighted and
    pooled across years. It is a composition sensitivity check, not a replacement
    estimator or a claim to have removed all nonstationarity.
    """
    dates = pd.to_datetime(pd.Series(dates), format="%Y-%m-%d", errors="coerce")
    values = np.asarray(contributions, dtype=float).copy()
    if dates.isna().any():
        raise ValueError("Every analysed flight needs a valid date")
    if (
        values.ndim != 2
        or len(values) != len(dates)
        or not len(dates)
        or not np.isfinite(values).all()
    ):
        raise ValueError("Expected finite contributions matching the flight dates")
    month = dates.dt.month.to_numpy() - 1
    counts_by_month = np.bincount(month, minlength=12)
    monthly = np.zeros((12, values.shape[1]))
    np.add.at(monthly, month, values)
    np.divide(
        monthly,
        counts_by_month[:, None],
        out=monthly,
        where=counts_by_month[:, None] > 0,
    )
    if centre_months:
        values -= monthly[month]
    calendar = pd.date_range(dates.min(), dates.max(), freq="D")
    offsets = (dates - calendar[0]).dt.days.to_numpy()
    daily = np.zeros((len(calendar), values.shape[1]))
    np.add.at(daily, offsets, values)
    counts = np.bincount(offsets, minlength=len(calendar))
    return calendar, daily, counts, monthly


def daily_correlogram(daily, counts, max_days):
    """Normalised autocovariance sums and their Bartlett cumulative diagnostic.

    rho(h) = sum_d U_d U_(d+h) / sum_d U_d^2. The same denominator is used at
    every separation, without pairwise renormalisation, so covariance contributions
    sum consistently. Actual calendar gaps and unequal daily flight mass remain.
    The cumulative factor at L is 1 + 2 sum_(h<L) (1-h/L) rho(h), a variance
    ratio relative to independent *days*, not to independent flights or site-days.
    It is a diagnostic, not a calibrated confidence interval or an independence test.
    """
    daily = np.asarray(daily, dtype=float)
    counts = np.asarray(counts)
    if (
        daily.ndim != 2
        or counts.shape != (len(daily),)
        or not np.isfinite(daily).all()
        or (counts < 0).any()
        or not isinstance(max_days, (int, np.integer))
        or not 1 <= max_days < len(daily)
    ):
        raise ValueError("Expected daily vectors and a separation within the calendar")
    # The input is centred at the flight level. Do not turn empty dates into
    # nonzero values by subtracting an observed-day mean here.
    scale = np.sum(daily**2, axis=0)
    if (scale <= 0).any():
        raise ValueError("A correlogram needs nonzero daily variation")
    rho = np.ones((max_days + 1, daily.shape[1]))
    pairs = np.zeros(max_days + 1, dtype=int)
    pairs[0] = np.count_nonzero(counts)
    occupied = counts > 0
    for h in range(1, max_days + 1):
        rho[h] = np.sum(daily[:-h] * daily[h:], axis=0) / scale
        pairs[h] = np.count_nonzero(occupied[:-h] & occupied[h:])
    factor = np.ones_like(rho)
    for length in range(2, max_days + 1):
        taper = 1 - np.arange(1, length) / length
        factor[length] += 2 * taper @ rho[1:length]
    return {"rho": rho, "occupied_pairs": pairs, "variance_factor": factor}
