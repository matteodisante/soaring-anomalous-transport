"""Uncertainty that counts the right number of independent things.

The archive holds 155 788 paraglider flights and nothing like 155 788 independent
measurements of the atmosphere. Two wings launched from one site on one day flew the same
air: the same convective strength, the same wind, the same cloud base, often the same
thermals in the same order. Resampling flights treats them as independent and returns an
error bar that is too small --- by one to two orders of magnitude on this archive, which is
the difference between an exponent that discriminates between models and one that does not.

So the resampling unit is the **cluster**, not the flight. Which cluster is a measurement
rather than a preference: :func:`intraclass_correlation` reports how much of the variance
in a per-flight quantity sits between groups at each candidate level --- flight, day, site,
day and site together, pilot, season --- and the level to resample at is the coarsest one
that still carries most of it.

The second thing this module supplies is the lag-to-lag covariance of the estimator's
sampling error. A curve of eighty lags is not eighty independent points, because every lag
averages the same flights; without that covariance a fit reports a confidence it has not
earned, and a breakpoint null built from the residuals instead is circular whenever the
curve is bent.
"""

from __future__ import annotations

from collections.abc import Callable

import numpy as np

__all__ = [
    "cluster_bootstrap",
    "cluster_labels",
    "intraclass_correlation",
    "sampling_covariance",
]


def cluster_labels(frame: "pd.DataFrame", level: str) -> np.ndarray:
    """Integer cluster ids for a resampling level.

    Args:
        frame: Per-flight table carrying ``date``, ``takeoff``, ``pilot``, ``season``.
        level: ``"flight"``, ``"day"``, ``"site"``, ``"day_site"``, ``"pilot"`` or
            ``"season"``.

    Returns:
        One integer per row. Rows with a missing key become singleton clusters, which
        *understates* the clustering and so understates the error bar: report the share of
        such rows wherever the result is quoted.
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
    key = frame[columns[0]].astype(str)
    for extra in columns[1:]:
        key = key + "|" + frame[extra].astype(str)
    # A missing key is not a shared cluster; give each such row its own.
    unknown = frame[columns].isna().any(axis=1).to_numpy()
    # int64, not the categorical's own width. cat.codes is int8 or int16 when the level
    # count allows, and the synthetic ids assigned to missing-key rows below run past the
    # existing maximum -- past 127 they wrap and those rows join real clusters silently.
    codes = key.astype("category").cat.codes.to_numpy().astype(np.int64)
    codes[unknown] = codes.max() + 1 + np.arange(unknown.sum())
    return codes


def intraclass_correlation(values: np.ndarray, labels: np.ndarray) -> float:
    """Share of the variance of ``values`` that sits *between* clusters.

    Near zero, the clustering is irrelevant and resampling flights is fine. Near one, a
    cluster is effectively one measurement however many flights it holds. It is what
    justifies the resampling level instead of asserting it.
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
        sum(((g - g.mean()) ** 2).sum() for g in groups) / max(values.size - len(groups), 1)
    )
    # The usual one-way ANOVA estimator, with the harmonic group size.
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
    labels = np.asarray(labels)
    unique, inverse = np.unique(labels, return_inverse=True)
    members = [np.flatnonzero(inverse == i) for i in range(len(unique))]
    rng = np.random.default_rng(seed)

    with np.errstate(invalid="ignore"):
        point = statistic(np.nanmean(curves, axis=0))

    replicates = []
    for _ in range(n_resamples):
        picked = rng.integers(0, len(members), size=len(members))
        rows = np.concatenate([members[i] for i in picked])
        with np.errstate(invalid="ignore"):
            replicates.append(statistic(np.nanmean(curves[rows], axis=0)))
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
    centred = replicates - np.nanmean(replicates, axis=0)
    usable = np.isfinite(sigma) & (sigma > 0)
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
