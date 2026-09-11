"""Resampling of flight clusters and covariance across sampled times.

Flights sharing a launch site and date may have common environmental influences.
Resampling whole groups preserves their observed within-group dependence. It still
assumes the chosen clusters can be resampled independently; dependence across sites,
dates or repeated pilots can remain. Intraclass correlation is a diagnostic under
a one-way random-intercept model, not a proof of an adequate resampling unit.

Bootstrap draws retain every flight in each selected cluster. Unequal cluster sizes
therefore affect the flight-weighted mean; clusters are not given equal mean weight.
"""

from __future__ import annotations

import os
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    import pandas as pd

__all__ = [
    "cluster_bootstrap",
    "cluster_labels",
    "intraclass_correlation",
    "sampling_covariance",
]


def cluster_labels(frame: pd.DataFrame, level: str) -> np.ndarray:
    """Integer cluster ids for a resampling level.

    Args:
        frame: Per-flight table carrying ``date``, ``takeoff``, ``pilot``, ``season``.
        level: ``"flight"``, ``"day"``, ``"site"``, ``"day_site"``, ``"pilot"`` or
            ``"season"``.

    Returns:
        One integer per row. Rows with a missing or blank key become singleton clusters.
        Their dependence cannot be reconstructed from these metadata; report their
        share, since treating them separately can miss shared environmental effects.
    """
    if level == "flight":
        return np.arange(len(frame))
    columns = {
        "day": ["date"],
        "site": ["takeoff"],
        "day_site": ["date", "takeoff"],
        "pilot": ["pilot"],
        "season": ["season"],
    }[level]
    missing = [c for c in columns if c not in frame]
    if missing:
        raise KeyError(f"level {level!r} needs column(s) {missing}")
    import pandas as pd

    if frame.empty:
        return np.empty(0, dtype=np.int64)
    keys = frame[columns].astype("string").apply(lambda col: col.str.strip())
    # A missing key is not a shared cluster; give each such row its own.
    unknown = (keys.isna() | keys.eq("").fillna(False)).any(axis=1).to_numpy()
    # int64, not the categorical's own width. cat.codes is int8 or int16 when the level
    # count allows, and the synthetic ids assigned to missing-key rows below run past the
    # existing maximum -- past 127 they wrap and those rows join real clusters silently.
    codes = np.full(len(frame), -1, dtype=np.int64)
    codes[~unknown] = pd.factorize(
        pd.MultiIndex.from_frame(keys.loc[~unknown]), sort=True
    )[0]
    codes[unknown] = codes.max() + 1 + np.arange(unknown.sum())
    return codes


def intraclass_correlation(values: np.ndarray, labels: np.ndarray) -> float:
    """ANOVA estimate of a random-intercept variance fraction, truncated at zero.

    It diagnoses shared cluster variation under that model. A small estimate neither
    establishes independence nor rules out dependence in other observables or scales.
    """
    values = np.asarray(values, dtype=float)
    good = np.isfinite(values)
    values, labels = values[good], np.asarray(labels)[good]
    if values.size < 3:
        return float("nan")
    order = np.argsort(labels)
    values, labels = values[order], labels[order]
    edges = np.flatnonzero(np.diff(labels)) + 1
    groups = np.split(values, edges)
    sizes = np.array([g.size for g in groups], dtype=float)
    if (sizes > 1).sum() < 2:
        return 0.0
    means = np.array([g.mean() for g in groups])
    grand = values.mean()
    between = float((sizes * (means - grand) ** 2).sum() / max(len(groups) - 1, 1))
    within = float(
        sum(((g - g.mean()) ** 2).sum() for g in groups)
        / max(values.size - len(groups), 1)
    )
    # One-way ANOVA effective group size for unequal groups (not their harmonic mean).
    n0 = (values.size - (sizes**2).sum() / values.size) / max(len(groups) - 1, 1)
    if n0 <= 0 or between + within <= 0:
        return 0.0
    variance_between = max((between - within) / n0, 0.0)
    return float(variance_between / (variance_between + within))


def cluster_bootstrap(
    curves: np.ndarray,
    labels: np.ndarray,
    statistic: Callable[[np.ndarray], float],
    *,
    n_resamples: int = 200,
    seed: int = 0,
) -> tuple[float, np.ndarray]:
    """Resample whole clusters with replacement and recompute a statistic.

    Args:
        curves: ``(n_flights, n_lags)``, ``nan`` where a flight does not cover a lag.
        labels: Cluster id per flight.
        statistic: Callable taking the ensemble-mean curve and returning a scalar or an
            array. It is applied to each resampled ensemble.
        n_resamples: How many resamples.
        seed: Base seed.

    Returns:
        ``(point, replicates)`` -- the statistic on the full sample, and its value on each
        resample.
    """
    curves = np.asarray(curves, dtype=np.float64)
    labels = np.asarray(labels)
    if curves.ndim < 1 or curves.shape[0] != labels.size or labels.ndim != 1:
        raise ValueError("Each flight curve needs exactly one cluster label")
    if not labels.size or n_resamples < 1:
        raise ValueError("Bootstrap needs observations and a positive resample count")
    if np.isinf(curves).any():
        raise ValueError("Curves must be finite or NaN, never infinite")
    unique, inverse = np.unique(labels, return_inverse=True)
    order = np.argsort(inverse, kind="stable")
    starts = np.r_[0, np.flatnonzero(np.diff(inverse[order])) + 1]
    values = curves[order].reshape(labels.size, -1)
    valid = ~np.isnan(values)
    sums = np.add.reduceat(np.where(valid, values, 0.0), starts, axis=0)
    counts = np.add.reduceat(valid.astype(np.float64), starts, axis=0)
    del values, valid, order
    rng = np.random.default_rng(seed)

    def from_totals(total, number):
        mean = np.divide(
            total, number, out=np.full_like(total, np.nan), where=number > 0
        )
        return statistic(mean.reshape(curves.shape[1:]))

    point = from_totals(sums.sum(axis=0), counts.sum(axis=0))
    # Cluster sufficient statistics give the same resampled flight mean without
    # allocating a copy of every flight curve on every draw.
    multiplicities = [
        np.bincount(
            rng.integers(0, len(unique), size=len(unique)), minlength=len(unique)
        ).astype(np.float64)
        for _ in range(n_resamples)
    ]

    def resampled(weights):
        return from_totals(weights @ sums, weights @ counts)

    workers = min(n_resamples, max(1, int(os.environ.get("SOARING_MAX_WORKERS", "1"))))
    if workers == 1:
        replicates = [resampled(weights) for weights in multiplicities]
    else:
        with ThreadPoolExecutor(max_workers=workers) as pool:
            replicates = list(pool.map(resampled, multiplicities))
    return point, np.asarray(replicates)


def sampling_covariance(
    curves: np.ndarray, labels: np.ndarray, *, n_resamples: int = 200, seed: int = 0
) -> dict:
    """Per-lag sampling error of ``log10`` of the mean curve, and its lag-to-lag correlation.

    This is what a breakpoint null has to be built from. Reading the noise scale off the
    residuals about a straight line instead is circular whenever the curve is genuinely
    bent: the curvature enters the surrogate as noise and the test compares the curve
    against copies of its own structure.

    Returns:
        ``{"sigma_dex", "autocorrelation", "n_clusters"}``.
    """

    def as_log(curve):
        with np.errstate(divide="ignore", invalid="ignore"):
            return np.log10(np.where(curve > 0, curve, np.nan))

    _, replicates = cluster_bootstrap(
        curves, labels, as_log, n_resamples=n_resamples, seed=seed
    )
    sigma = np.nanstd(replicates, axis=0)
    # Standardised before pooling, because the lags do not share a scale: sigma runs over two
    # orders of magnitude across the full grid, so a correlation taken on the raw deviations is
    # dominated by the loudest lags and reads far below the truth. On an exact AR(1) with
    # rho = 0.90 and one lag forty times noisier, pooling raw returns 0.05 and standardising
    # returns 0.885. The floor is relative rather than ``> 0`` so that a lag whose sigma has
    # collapsed to rounding is dropped instead of being amplified into pure noise.
    usable = np.isfinite(sigma) & (sigma > 1e-6 * np.nanmedian(sigma))
    centred = (replicates - np.nanmean(replicates, axis=0)) / np.where(
        usable, sigma, np.nan
    )
    if usable.sum() > 3:
        a = centred[:, usable][:, :-1].ravel()
        b = centred[:, usable][:, 1:].ravel()
        good = np.isfinite(a) & np.isfinite(b)
        rho = float(np.corrcoef(a[good], b[good])[0, 1]) if good.sum() > 10 else 0.0
    else:
        rho = 0.0
    return {
        "sigma_dex": sigma,
        "autocorrelation": rho,
        "n_clusters": int(np.unique(labels).size),
    }
