"""Held-out signed and two-interval scaling on fixed segment support.

The finite set of projected CDFs is a diagnostic, not an omnibus test of a
four-dimensional law. Date resampling preserves all measured lag contrasts.
"""

from __future__ import annotations

import hashlib
import itertools

import numpy as np

from .segment_support import increment_starts


def projection_directions():
    """Return fixed unit axes and all pairwise sums/differences, with labels."""
    axes = np.eye(4)
    labels = ["E1", "N1", "E2", "N2"]
    directions, names = list(axes), labels.copy()
    for i, j in itertools.combinations(range(4), 2):
        for sign, symbol in ((1, "+"), (-1, "-")):
            directions.append((axes[i] + sign * axes[j]) / np.sqrt(2))
            names.append(f"({labels[i]}{symbol}{labels[j]})/sqrt(2)")
    return np.asarray(directions), names


def training_day(date):
    """Assign a complete, validated calendar date to one reproducible role."""
    return hashlib.sha256(f"temporal-scaling-v1:{date}".encode()).digest()[0] % 2 == 0


def two_increments(row, xy, lag_steps, max_lag_steps):
    """Use exactly the same supported origins at every lag, without gap bridges."""
    starts = increment_starts(row, len(xy), max_lag_steps, order=2, stride=1)
    if not len(starts):
        return np.empty((0, 4))
    middle = xy[starts + lag_steps]
    return np.column_stack((middle - xy[starts], xy[starts + 2 * lag_steps] - middle))


def cdf_features(values, directions, thresholds):
    """Flight probability masses F(z)=P(projection <= z) on a fixed grid."""
    if not len(values):
        raise ValueError("A flight must have common origins")
    result = np.empty((len(directions), len(thresholds)))
    for j, direction in enumerate(directions):
        # side='left' puts equality in the <= CDF, including exact zero atoms.
        bins = np.searchsorted(thresholds, values @ direction, side="left")
        result[j] = np.cumsum(np.bincount(bins, minlength=len(thresholds) + 1))[:-1]
    return result / len(values)


def magnitude_histograms(values, edges):
    """Equal-origin, per-flight histograms, including underflow and overflow."""
    magnitudes = np.column_stack(
        (np.abs(values[:, :2]), np.linalg.norm(values[:, :2], axis=1))
    )
    hist = np.empty((3, len(edges) + 1))
    for j in range(3):
        hist[j] = np.bincount(
            np.searchsorted(edges, magnitudes[:, j], side="right"),
            minlength=len(edges) + 1,
        ) / len(values)
    return hist


def fit_histogram_quantiles(histograms, edges, lags, probabilities):
    """Fit training inverse-CDF quantiles with explicit log-bin resolution."""
    cdf = np.cumsum(histograms, axis=-1)
    cdf /= cdf[..., -1, None]
    ranks = np.asarray(probabilities)
    indexes = (cdf[..., None] < ranks).sum(axis=-2)
    if np.any(indexes == 0) or np.any(indexes >= len(edges)):
        raise ValueError("A training quantile is outside the finite histogram grid")
    quantiles = np.sqrt(edges[indexes - 1] * edges[indexes])
    x = np.log(np.asarray(lags, dtype=float))
    centred = x - x.mean()
    slopes = np.einsum("l,lcq->cq", centred, np.log(quantiles)) / (centred @ centred)
    # Every log-quantile has deterministic absolute error <= half a bin width.
    log_error = np.max(np.diff(np.log(edges))) / 2
    slope_error = log_error * np.abs(centred).sum() / (centred @ centred)
    return {
        "quantiles_m": quantiles.tolist(),
        "slopes": slopes.tolist(),
        "common_h": float(slopes.mean()),
        "reference_radius_m": float(quantiles[0, 2, list(probabilities).index(0.5)]),
        "quantile_relative_resolution": float(np.expm1(log_error)),
        "h_absolute_resolution_bound": float(slope_error),
    }


def simultaneous_contrasts(day_sums, day_counts, *, resamples, seed):
    """Paired date-bootstrap uniform errors for all lag pairs/features.

    Day totals are sums of flight CDFs, not pooled origins. Cluster sizes enter
    both numerator and denominator, preserving equal flight weights.
    """
    sums = np.asarray(day_sums, dtype=float)
    counts = np.asarray(day_counts, dtype=float)
    if sums.shape[0] != len(counts) or np.any(counts <= 0) or len(counts) < 2:
        raise ValueError("Need at least two nonempty date clusters")
    mean = sums.sum(axis=0) / counts.sum()
    pairs = np.array(list(itertools.combinations(range(mean.shape[0]), 2)))
    observed = mean[pairs[:, 0]] - mean[pairs[:, 1]]
    rng = np.random.default_rng(seed)
    errors = np.empty(resamples)
    flattened = sums.reshape(len(counts), -1)
    for b in range(resamples):
        weights = np.bincount(
            rng.integers(len(counts), size=len(counts)), minlength=len(counts)
        )
        estimate = (weights @ flattened / (weights @ counts)).reshape(mean.shape)
        errors[b] = np.max(
            np.abs(estimate[pairs[:, 0]] - estimate[pairs[:, 1]] - observed)
        )
    radius = float(np.quantile(errors, 0.95, method="higher"))
    return mean, observed, radius, errors
