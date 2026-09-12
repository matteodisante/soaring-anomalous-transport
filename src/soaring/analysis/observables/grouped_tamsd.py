"""Equal-flight TAMSD summaries with paired site-day uncertainty."""

from __future__ import annotations

import warnings

import numpy as np


def mean_and_support(values):
    """Average finite flight curves without giving missing lags zero weight."""
    values = np.asarray(values, dtype=float)
    support = np.isfinite(values).sum(axis=0)
    mean = np.divide(
        np.nansum(values, axis=0),
        support,
        out=np.full(values.shape[1:], np.nan),
        where=support > 0,
    )
    return mean, support


def clustered_summary(values, labels, *, resamples=500, seed=20260913):
    """Resample complete site-days jointly over lag and population controls.

    Values have shape (flight, control, lag). Every flight has equal weight
    within each finite cell. Group sizes need not be equal; individual origins
    and segments are never bootstrap observations.
    """
    values = np.asarray(values, dtype=float)
    if values.ndim != 3 or len(values) != len(labels) or resamples < 2:
        raise ValueError("Expected aligned flight/control/lag values and clusters")
    point, support = mean_and_support(values)
    if not len(values):
        return {
            "mean_m2": point,
            "n_flights": support,
            "n_clusters": np.zeros_like(support),
            "pointwise_95_m2": np.full((2, *point.shape), np.nan),
        }
    _, inverse = np.unique(labels, return_inverse=True)
    n_groups = int(inverse.max()) + 1
    valid = np.isfinite(values)
    sums = np.zeros((n_groups, *values.shape[1:]))
    counts = np.zeros_like(sums)
    np.add.at(sums, inverse, np.where(valid, values, 0))
    np.add.at(counts, inverse, valid)
    clusters = (counts > 0).sum(axis=0)
    rng = np.random.default_rng(seed)
    samples = np.full((resamples, *point.shape), np.nan)
    for start in range(0, resamples, 16):
        size = min(16, resamples - start)
        draw = rng.multinomial(n_groups, np.full(n_groups, 1 / n_groups), size=size)
        numerator = draw @ sums.reshape(n_groups, -1)
        denominator = draw @ counts.reshape(n_groups, -1)
        mean = np.divide(
            numerator,
            denominator,
            out=np.full_like(numerator, np.nan),
            where=denominator > 0,
        )
        samples[start : start + size] = mean.reshape(size, *point.shape)
    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", message="All-NaN slice encountered")
        bounds = np.nanquantile(samples, [0.025, 0.975], axis=0)
    enough = (clusters >= 20) & (np.isfinite(samples).sum(axis=0) >= 0.9 * resamples)
    bounds = np.where(enough, bounds, np.nan)
    return {
        "mean_m2": point,
        "n_flights": support,
        "n_clusters": clusters,
        "pointwise_95_m2": bounds,
    }


def decade_slopes(curve, lags, intervals=((10, 100), (100, 1000), (1000, 10000))):
    """Describe separate lag ranges; the fitted slopes are not Hurst estimates."""
    records = []
    curve, lags = np.asarray(curve), np.asarray(lags)
    for low, high in intervals:
        good = (lags >= low) & (lags <= high) & np.isfinite(curve) & (curve > 0)
        slope = (
            float(np.polyfit(np.log(lags[good]), np.log(curve[good]), 1)[0])
            if good.sum() >= 3
            else np.nan
        )
        records.append(
            {
                "requested_range_s": [low, high],
                "actual_lags_s": lags[good],
                "slope": slope,
            }
        )
    return records
