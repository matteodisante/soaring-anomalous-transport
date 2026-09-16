"""Effective TAMSD exponents with whole-site-day bootstrap uncertainty.

The reported quantity is H_eff = slope / 2 for the logarithm of the equal-flight
mean TAMSD in a specified lag window. It is a descriptive scaling exponent; this
calculation does not establish the assumptions of a fractional Brownian model.
"""

from __future__ import annotations

import warnings

import numpy as np


def fit_loglog(lags, curves):
    """Return OLS slopes and natural-log intercepts along the final curve axis.

    Every supplied lag must be finite and positive, and at least two distinct
    lags are required. A curve with any nonpositive or nonfinite value receives
    NaNs: bootstrap replicates must use the complete, fixed point-estimate grid.
    The intercept is log(TAMSD / m²) at lag / s = 1 when these units are supplied.
    """
    lags = np.asarray(lags, dtype=float)
    curves = np.asarray(curves, dtype=float)
    if lags.ndim != 1 or curves.ndim < 1 or curves.shape[-1] != lags.size:
        raise ValueError("Expected aligned lag axis and curves")
    if np.any(~np.isfinite(lags) | (lags <= 0)):
        raise ValueError("Lags must be finite and positive")
    empty = np.full(curves.shape[:-1], np.nan)
    if len(lags) < 2:
        return empty.copy(), empty
    x = np.log(lags)
    centered_x = x - x.mean()
    denominator = np.sum(centered_x**2)
    if denominator == 0:
        return empty.copy(), empty
    valid = np.isfinite(curves) & (curves > 0)
    y = np.log(np.where(valid, curves, 1.0))
    # Centering y avoids roundoff cancellation for amplitude-only differences.
    centered_y = y - y.mean(axis=-1, keepdims=True)
    slope = np.sum(centered_y * centered_x, axis=-1) / denominator
    intercept = y.mean(axis=-1) - slope * x.mean()
    complete = valid.all(axis=-1)
    return np.where(complete, slope, np.nan), np.where(complete, intercept, np.nan)


def clustered_scaling_summary(
    values,
    labels,
    lags,
    *,
    control_names=None,
    intervals=((10, 100), (100, 1000), (1000, 10000)),
    resamples=2000,
    seed=20260915,
    min_flights=8,
    min_clusters=20,
    min_lags=3,
    min_finite_fraction=0.9,
):
    """Summarize equal-flight TAMSD curves and fit paired cluster resamples.

    ``values`` has shape (flight, control, lag), with one aligned, one-dimensional
    site-day label per flight. Whole clusters are drawn with replacement. Each
    sampled flight keeps equal weight, including when cluster sizes differ;
    draws are shared across all controls and lags. Missing cells are excluded
    from their own denominators. Negative/zero means cannot enter logarithmic
    fits.

    Each requested interval uses a fixed grid selected from the point estimate:
    positive finite means with at least ``min_flights`` contributing flights.
    A point fit requires ``min_lags`` such lags. Its percentile interval and
    bootstrap standard error require ``min_clusters`` contributing clusters at
    every selected lag and at least ``min_finite_fraction`` complete replicate
    fits. These support rules do not claim independence between site-days.

    Returns summary arrays and a flat, control-major ``fits`` list. Fit records
    use natural-log intercepts, include the selected support and explicitly
    report why uncertainty or an entire fit is unavailable. Pointwise curve
    bands apply the same cluster/finite-draw threshold at each individual cell;
    they are not simultaneous confidence bands.
    """
    values = np.asarray(values, dtype=float)
    labels = np.asarray(labels)
    lags = np.asarray(lags, dtype=float)
    if (
        values.ndim != 3
        or labels.ndim != 1
        or len(values) != len(labels)
        or lags.ndim != 1
        or values.shape[-1] != lags.size
    ):
        raise ValueError("Expected aligned flight/control/lag values and clusters")
    if np.any(~np.isfinite(lags) | (lags <= 0)) or np.any(np.diff(lags) <= 0):
        raise ValueError("Lags must be finite, positive and strictly increasing")
    if not isinstance(resamples, (int, np.integer)) or resamples < 2:
        raise ValueError("At least two integer bootstrap resamples are required")
    if min_flights < 1 or min_clusters < 1 or min_lags < 2:
        raise ValueError("Positive support and at least two fitted lags are required")
    if not 0 < min_finite_fraction <= 1:
        raise ValueError("Finite-draw fraction must lie in (0, 1]")
    intervals = tuple(tuple(bounds) for bounds in intervals)
    if any(
        len(bounds) != 2
        or not np.isfinite(bounds).all()
        or not 0 < bounds[0] < bounds[1]
        for bounds in intervals
    ):
        raise ValueError("Intervals must be finite positive increasing pairs")
    n_controls, n_lags = values.shape[1:]
    names = list(range(n_controls)) if control_names is None else list(control_names)
    if len(names) != n_controls:
        raise ValueError("Expected one name for each control")

    valid = np.isfinite(values)
    support = valid.sum(axis=0)
    point = np.divide(
        np.where(valid, values, 0).sum(axis=0),
        support,
        out=np.full(values.shape[1:], np.nan),
        where=support > 0,
    )
    clusters = np.zeros_like(support)
    samples = np.full((resamples, n_controls, n_lags), np.nan)
    n_groups = 0
    if len(values):
        _, inverse = np.unique(labels, return_inverse=True)
        n_groups = int(inverse.max()) + 1
        sums = np.zeros((n_groups, n_controls, n_lags))
        counts = np.zeros_like(sums)
        np.add.at(sums, inverse, np.where(valid, values, 0))
        np.add.at(counts, inverse, valid)
        clusters = (counts > 0).sum(axis=0)
        rng = np.random.default_rng(seed)
        for start in range(0, resamples, 16):
            size = min(16, resamples - start)
            draw = rng.multinomial(n_groups, np.full(n_groups, 1 / n_groups), size=size)
            numerator = draw @ sums.reshape(n_groups, n_controls * n_lags)
            denominator = draw @ counts.reshape(n_groups, n_controls * n_lags)
            mean = np.divide(
                numerator,
                denominator,
                out=np.full_like(numerator, np.nan),
                where=denominator > 0,
            )
            samples[start : start + size] = mean.reshape(size, n_controls, n_lags)
    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", message="All-NaN slice encountered")
        pointwise_bounds = np.nanquantile(samples, [0.025, 0.975], axis=0)
    enough = (clusters >= min_clusters) & (
        np.isfinite(samples).sum(axis=0) >= min_finite_fraction * resamples
    )
    pointwise_bounds = np.where(enough, pointwise_bounds, np.nan)

    records = []
    for control_index, name in enumerate(names):
        for low, high in intervals:
            selected = (
                (lags >= low)
                & (lags <= high)
                & np.isfinite(point[control_index])
                & (point[control_index] > 0)
                & (support[control_index] >= min_flights)
            )
            selected_support = support[control_index, selected]
            selected_clusters = clusters[control_index, selected]
            record = {
                "control": name,
                "control_index": control_index,
                "requested_range_s": [low, high],
                "actual_lags_s": lags[selected].copy(),
                "h_eff": np.nan,
                "slope": np.nan,
                "intercept_log_m2": np.nan,
                "h_eff_percentile_95": np.full(2, np.nan),
                "h_eff_bootstrap_se": np.nan,
                "n_flights": selected_support.copy(),
                "n_clusters": selected_clusters.copy(),
                "n_flights_min": int(selected_support.min()) if selected.any() else 0,
                "n_clusters_min": int(selected_clusters.min()) if selected.any() else 0,
                "n_lags": int(selected.sum()),
                "status": "insufficient_flight_support",
                "resamples": resamples,
                "n_finite_resamples": 0,
            }
            if selected.sum() >= min_lags:
                slope, intercept = fit_loglog(
                    lags[selected], point[control_index, selected]
                )
                record.update(
                    h_eff=float(slope / 2),
                    slope=float(slope),
                    intercept_log_m2=float(intercept),
                )
                replicate_slopes, _ = fit_loglog(
                    lags[selected], samples[:, control_index, :][:, selected]
                )
                h_draws = replicate_slopes[np.isfinite(replicate_slopes)] / 2
                record["n_finite_resamples"] = len(h_draws)
                if record["n_clusters_min"] < min_clusters:
                    record["status"] = "insufficient_clusters"
                elif len(h_draws) < max(2, min_finite_fraction * resamples):
                    record["status"] = "insufficient_finite_resamples"
                else:
                    record.update(
                        status="ok",
                        h_eff_percentile_95=np.quantile(h_draws, [0.025, 0.975]),
                        h_eff_bootstrap_se=float(np.std(h_draws, ddof=1)),
                    )
            records.append(record)
    return {
        "mean_m2": point,
        "n_flights": support,
        "n_clusters": clusters,
        "pointwise_95_m2": pointwise_bounds,
        "fits": records,
        "resamples": resamples,
        "seed": seed,
        "n_clusters_total": n_groups,
        "support_rules": {
            "min_flights": min_flights,
            "min_clusters": min_clusters,
            "min_lags": min_lags,
            "min_finite_fraction": min_finite_fraction,
        },
    }
