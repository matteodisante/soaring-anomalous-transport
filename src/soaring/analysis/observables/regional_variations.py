"""Regional finite differences with explicit support, weights and uncertainty.

Three estimators are retained: each order's available origins, origins shared by
orders 1--3 at each lag, and origins shared by orders and lags up to a declared
maximum. Every stencil stays within a recorded segment. Flight moments are saved
before pooling so uncertainty and population controls need no trajectory reread.
No finite-range slope is identified automatically with a Hurst parameter.
"""

from __future__ import annotations

from collections import deque
from concurrent.futures import ProcessPoolExecutor
from itertools import islice
from pathlib import Path

import numpy as np

from .segment_support import increment_starts, segment_ranges

VARIANTS = ("available", "matched", "common")
REGIONS = ("Alps", "Pyrenees", "Channel Coast")
LAGS_S = np.array(
    [
        10,
        20,
        30,
        50,
        70,
        100,
        150,
        200,
        300,
        500,
        700,
        1000,
        1500,
        2000,
        3000,
        5000,
        7000,
        10000,
    ],
    dtype=int,
)
DISTRIBUTION_LAGS_S = (10, 100, 1000, 10000)
# Zero and both tails are retained. Quantiles are reported as bin bounds.
CHANGE_EDGES = np.r_[0.0, np.geomspace(1e-5, 1e3, 401), np.inf]


def vector_moments(vectors):
    """Return mean E/N and centred population covariance EE/EN/NN."""
    if not len(vectors):
        return np.full(5, np.nan)
    mean = vectors.mean(axis=0)
    residual = vectors - mean
    covariance = residual.T @ residual / len(vectors)
    return np.r_[mean, covariance[0, 0], covariance[0, 1], covariance[1, 1]]


def flight_variations(row, positions, lags_s, *, grid_s=10, common_max_s=1000):
    """Measure one flight and retain second-difference distributions at four lags.

    Available and matched stencils start every tau, independently in each
    segment; stencils of orders two and three consequently overlap. Common
    origins start every grid step and support 3 * common_max_s at every lag.
    """
    lags_s = np.asarray(lags_s)
    if (
        grid_s <= 0
        or common_max_s <= 0
        or common_max_s % grid_s
        or lags_s.ndim != 1
        or not len(lags_s)
        or np.any(~np.isfinite(lags_s))
        or np.any(lags_s <= 0)
        or np.any(lags_s % grid_s)
        or np.any(np.diff(lags_s) <= 0)
    ):
        raise ValueError("Lags must be increasing positive multiples of the grid")
    if (
        positions.ndim != 2
        or positions.shape[1] != 2
        or not np.isfinite(positions).all()
    ):
        raise ValueError("Finite E/N coordinates are required")
    moments = np.full((3, len(lags_s), 3, 5), np.nan)
    counts = np.zeros((3, len(lags_s), 3), dtype=np.int32)
    histograms = {}
    common = increment_starts(
        row,
        len(positions),
        int(common_max_s // grid_s),
        order=3,
        stride=1,
    )
    for j, tau in enumerate(lags_s):
        lag = int(tau // grid_s)
        pieces = [[[] for _ in range(3)] for _ in range(2)]
        for start, stop in segment_ranges(row, len(positions)):
            coarse = positions[start:stop:lag]
            shared = max(len(coarse) - 3, 0)
            for p in range(3):
                values = np.diff(coarse, n=p + 1, axis=0)
                pieces[0][p].append(values)
                pieces[1][p].append(values[:shared])
        for variant in range(3):
            if variant == 2:
                if tau > common_max_s or not len(common):
                    continue
                coarse = np.stack([positions[common + k * lag] for k in range(4)])
            for p in range(3):
                values = (
                    np.diff(coarse, n=p + 1, axis=0)[0]
                    if variant == 2
                    else np.concatenate(pieces[variant][p])
                )
                counts[variant, j, p] = len(values)
                moments[variant, j, p] = vector_moments(values)
                if p == 1 and tau in DISTRIBUTION_LAGS_S and len(values):
                    change = np.linalg.norm(values, axis=1) / tau
                    probability = np.histogram(change, CHANGE_EDGES)[0] / len(values)
                    energy = np.histogram(change, CHANGE_EDGES, weights=change**2)[0]
                    histograms[variant, int(tau)] = (probability, energy / len(values))
    return moments, counts, histograms


def _measure_batch(batch):
    """Amortise process scheduling while bounding queued coordinates and results."""
    return [
        flight_variations(row, xy, lags, common_max_s=limit)
        for row, xy, lags, limit in batch
    ]


def _measure_results(frames, lags_s, common_max_s, workers):
    """Yield results in flight order with at most two small batches per worker."""
    tasks = (
        (row, np.asarray(xy), lags_s, common_max_s)
        for row, xy in frames
        if row["region"] in REGIONS
    )
    if workers == 1:
        for task in tasks:
            yield _measure_batch([task])[0]
        return
    if workers < 1:
        raise ValueError("At least one worker is required")
    with ProcessPoolExecutor(max_workers=workers) as pool:
        pending = deque()
        for _ in range(2 * workers):
            batch = list(islice(tasks, 8))
            if batch:
                pending.append(pool.submit(_measure_batch, batch))
        while pending:
            yield from pending.popleft().result()
            batch = list(islice(tasks, 8))
            if batch:
                pending.append(pool.submit(_measure_batch, batch))


def measure_regional_variations(
    frames,
    directory,
    *,
    lags_s=LAGS_S,
    common_max_s=1000,
    workers=1,
):
    """Save bounded-memory per-flight statistics from every eligible regional flight."""
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    if (directory / "moments.npy").exists():
        raise FileExistsError("Use a fresh directory for a new measurement")
    rows = [row for row, _ in frames if row["region"] in REGIONS]
    ids = [row["flight_id"] for row in rows]
    if len(ids) != len(set(ids)):
        raise ValueError("Duplicate regional flight")
    shape = (len(rows), len(VARIANTS), len(lags_s), 3)
    moments = np.lib.format.open_memmap(
        directory / "moments.npy",
        mode="w+",
        dtype="float64",
        shape=(*shape, 5),
    )
    counts = np.lib.format.open_memmap(
        directory / "counts.npy",
        mode="w+",
        dtype="int32",
        shape=shape,
    )
    histograms = {}
    measured = _measure_results(frames, lags_s, common_max_s, workers)
    for index, (row, (stats, support, hist)) in enumerate(
        zip(rows, measured, strict=True)
    ):
        moments[index], counts[index] = stats, support
        for (variant, tau), (probability, energy) in hist.items():
            key = (row["region"], VARIANTS[variant], tau)
            if key not in histograms:
                histograms[key] = [0, np.zeros_like(probability), np.zeros_like(energy)]
            state = histograms[key]
            state[0] += 1
            state[1] += probability
            state[2] += energy
        if (index + 1) % 10000 == 0:
            print(f"Regional variations: {index + 1}/{len(rows)} flights", flush=True)
    moments.flush()
    counts.flush()
    distributions = []
    for (region, variant, tau), (n, probability, energy) in histograms.items():
        probability, energy = probability / n, energy / n
        quantiles = {}
        cumulative = np.cumsum(probability)
        for q in (0.5, 0.9, 0.99):
            k = min(np.searchsorted(cumulative, q), len(probability) - 1)
            quantiles[str(q)] = CHANGE_EDGES[k : k + 2].tolist()
        k = min(np.searchsorted(cumulative, 0.9), len(energy) - 1)
        total = energy.sum()
        tail = (
            [energy[k + 1 :].sum() / total, energy[k:].sum() / total]
            if total
            else [0, 0]
        )
        distributions.append(
            {
                "region": region,
                "variant": variant,
                "lag_s": tau,
                "n_flights": n,
                "probability": probability.tolist(),
                "change_squared_contribution": energy.tolist(),
                "quantile_bin_bounds_m_s": quantiles,
                "upper_decile_energy_share_bounds": tail,
            }
        )
    return rows, moments, counts, distributions


def mixture_moments(stats, weights=None):
    """Pool flight distributions, retaining between-flight mean variability.

    The last dimension stores mean E/N and covariance EE/EN/NN. Missing flight
    cells have NaN moments; weights are renormalised independently per cell.
    """
    stats = np.asarray(stats)
    if weights is None:
        weights = np.ones(len(stats))
    weights = np.asarray(weights, dtype=float)
    if (
        weights.shape != (len(stats),)
        or np.any(~np.isfinite(weights))
        or np.any(weights < 0)
    ):
        raise ValueError("One finite nonnegative weight is required per flight")
    valid = np.isfinite(stats).all(axis=-1)
    weight = weights.reshape((-1,) + (1,) * (valid.ndim - 1)) * valid
    denominator = weight.sum(axis=0)
    with np.errstate(invalid="ignore", divide="ignore"):
        mean = (
            np.nansum(stats[..., :2] * weight[..., None], axis=0)
            / denominator[..., None]
        )
        delta = stats[..., :2] - mean
        centred = stats[..., 2:] + np.stack(
            [delta[..., 0] ** 2, delta[..., 0] * delta[..., 1], delta[..., 1] ** 2],
            axis=-1,
        )
        covariance = (
            np.nansum(centred * weight[..., None], axis=0) / denominator[..., None]
        )
    return np.concatenate([mean, covariance], axis=-1)


def moment_diagnostics(moments):
    """Convert vector moments to raw variation, covariance anisotropy and axis."""
    moments = np.asarray(moments)
    mean, cov = moments[..., :2], moments[..., 2:]
    trace = cov[..., 0] + cov[..., 2]
    spread = np.hypot(cov[..., 0] - cov[..., 2], 2 * cov[..., 1])
    lower, upper = (trace - spread) / 2, (trace + spread) / 2
    ratio = np.divide(
        upper,
        lower,
        out=np.full_like(trace, np.nan),
        where=lower > 1e-12 * np.maximum(trace, 1),
    )
    angle = (
        np.degrees(0.5 * np.arctan2(2 * cov[..., 1], cov[..., 0] - cov[..., 2])) % 180
    )
    angle = np.where(spread > 1e-12 * np.maximum(trace, 1), angle, np.nan)
    return {
        "variation": trace + (mean**2).sum(axis=-1),
        "covariance_trace": trace,
        "anisotropy": ratio,
        "axis_deg": angle,
    }


def bootstrap_moments(stats, labels, *, n_resamples=500, seed=20260912):
    """Resample site--day clusters jointly across every lag and order.

    Cluster sums of shifted raw moments avoid repeatedly reading trajectories
    and avoid subtracting large unshifted position moments. Flights receive
    equal weight; cluster sizes remain unequal. Unsupported cells stay NaN.
    """
    stats = np.asarray(stats)
    _, inverse = np.unique(labels, return_inverse=True)
    n_clusters = int(inverse.max()) + 1 if len(inverse) else 0
    if not n_clusters or n_resamples < 2:
        raise ValueError("Clusters and at least two bootstrap replicates are required")
    point = mixture_moments(stats)
    centre = np.nan_to_num(point[..., :2])
    valid = np.isfinite(stats).all(axis=-1)
    shifted = stats[..., :2] - centre
    raw = np.concatenate(
        [
            shifted,
            stats[..., 2:]
            + np.stack(
                [
                    shifted[..., 0] ** 2,
                    shifted[..., 0] * shifted[..., 1],
                    shifted[..., 1] ** 2,
                ],
                axis=-1,
            ),
            valid[..., None],
        ],
        axis=-1,
    )
    raw = np.where(valid[..., None], raw, 0)
    sums = np.zeros((n_clusters, *raw.shape[1:]))
    np.add.at(sums, inverse, raw)
    replicates = np.full((n_resamples, *point.shape), np.nan)
    rng = np.random.default_rng(seed)
    for start in range(0, n_resamples, 32):
        size = min(32, n_resamples - start)
        draws = rng.multinomial(
            n_clusters, np.full(n_clusters, 1 / n_clusters), size=size
        )
        aggregate = (draws @ sums.reshape(n_clusters, -1)).reshape(size, *raw.shape[1:])
        with np.errstate(invalid="ignore", divide="ignore"):
            mean = aggregate[..., :2] / aggregate[..., 5, None]
            covariance = aggregate[..., 2:5] / aggregate[..., 5, None] - np.stack(
                [mean[..., 0] ** 2, mean[..., 0] * mean[..., 1], mean[..., 1] ** 2],
                axis=-1,
            )
        replicates[start : start + size] = np.concatenate(
            [mean + centre, covariance], axis=-1
        )
    return point, replicates


def common_stratum_weights(metadata, eligible, *, minimum_per_region=10):
    """Standardise regions to common task/duration/period/equipment strata.

    Only complete strata with at least the declared number of eligible flights
    in each region survive. Target mass is proportional to the smallest regional
    count in each stratum. This descriptive control does not match weather or
    pilot identity and does not provide a causal estimate.
    """
    import pandas as pd

    keys = ["task_group", "duration_band", "period", "equipment_group"]
    frame = metadata.copy()
    good = np.asarray(eligible) & frame[keys].notna().all(axis=1).to_numpy()
    strata = (
        frame.loc[good]
        .groupby([*keys, "region"], observed=True)
        .size()
        .unstack("region", fill_value=0)
    )
    strata = strata.reindex(columns=REGIONS, fill_value=0)
    strata = strata.loc[(strata >= minimum_per_region).all(axis=1)]
    weights = np.zeros(len(frame))
    if strata.empty:
        return weights, {"n_strata": 0, "minimum_per_region": minimum_per_region}
    mass = strata.min(axis=1)
    mass = mass / mass.sum()
    records = []
    for key, target in mass.items():
        match = (
            good & (frame[keys] == pd.Series(key, index=keys)).all(axis=1).to_numpy()
        )
        for region in REGIONS:
            mask = match & frame.region.eq(region).to_numpy()
            weights[mask] = target / mask.sum()
        records.append(
            {
                "stratum": list(key),
                "target_mass": float(target),
                "regional_counts": {g: int(strata.loc[key, g]) for g in REGIONS},
            }
        )
    return weights, {
        "n_strata": len(strata),
        "minimum_per_region": minimum_per_region,
        "strata": records,
        "target": "normalised minimum regional stratum count",
    }
