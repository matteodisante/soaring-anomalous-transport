"""Centred regional displacement covariances at exact physical lags."""

from __future__ import annotations

import numpy as np

from .segment_support import increment_starts

PCA_LAGS_S = (10, 100, 1000, 10000)
PCA_REFERENCE_LAG_S = 1000


def regional_pca(frames, regions, *, lags_s=PCA_LAGS_S, grid_s=10):
    """Pool all within-segment, nonoverlapping origins, without flight subsampling.

    ``frames`` contains one (metadata, E/N coordinates) pair per flight, on the
    declared grid. Segment ranges index the compact coordinates; increments
    never join different segments. Each supported origin has equal weight.
    Centred scatter matrices are merged flight by flight to bound memory and
    avoid subtracting large raw second moments. Eight contributing flights are
    required for display, independently at each lag.
    """
    lags_s = tuple(lags_s)
    if (
        not np.isfinite(grid_s)
        or grid_s <= 0
        or not lags_s
        or len(set(lags_s)) != len(lags_s)
        or any(not np.isfinite(t) or t <= 0 or t % grid_s for t in lags_s)
    ):
        raise ValueError("PCA lags must be distinct positive multiples of the grid")
    states = {
        (region, tau): [0, 0, np.zeros(2), np.zeros((2, 2))]
        for region in regions
        for tau in lags_s
    }
    seen = set()
    for row, positions in frames:
        flight_id = str(row["flight_id"])
        if flight_id in seen:
            raise ValueError(f"Duplicate flight in regional PCA: {flight_id}")
        seen.add(flight_id)
        name = row["region"]
        if name not in regions:
            continue
        if (
            positions.ndim != 2
            or positions.shape[1] != 2
            or not np.isfinite(positions).all()
        ):
            raise ValueError(
                f"Regional PCA requires finite E/N coordinates: {flight_id}"
            )
        for tau in lags_s:
            lag = int(tau / grid_s)
            starts = increment_starts(row, len(positions), lag)
            n = len(starts)
            if not n:
                continue
            vectors = positions[starts + lag] - positions[starts]
            mean = vectors.mean(axis=0)
            centred = vectors - mean
            count, flights, old_mean, scatter = states[name, tau]
            total = count + n
            delta = mean - old_mean
            states[name, tau] = [
                total,
                flights + 1,
                old_mean + delta * (n / total),
                scatter
                + centred.T @ centred
                + np.outer(delta, delta) * (count * n / total),
            ]
    output = []
    for (name, tau), (count, flights, mean, scatter) in states.items():
        if flights < 8:
            continue
        covariance = scatter / count
        values, vectors = np.linalg.eigh(covariance)
        if values[0] <= 0:
            continue
        axis = vectors[:, -1]
        output.append(
            {
                "region": name,
                "lag_s": int(tau),
                "n_flights": flights,
                "n_increments": count,
                "mean": mean.tolist(),
                "covariance": covariance.tolist(),
                "ratio": float(values[-1] / values[0]),
                "angle_deg": float(np.degrees(np.arctan2(axis[1], axis[0])) % 180),
                "correlation": float(
                    covariance[0, 1] / np.sqrt(covariance[0, 0] * covariance[1, 1])
                ),
            }
        )
    return output
