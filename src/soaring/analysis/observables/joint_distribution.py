"""Signed bivariate displacement laws on shared bins and a fixed population.

The histogram distance is descriptive and resolution dependent. It detects changes
hidden by coordinate and radial marginals, but zero distance at finite resolution
is not proof of joint equality, process self-similarity, or isotropy. No iid p-value
is attached to overlapping, paired origins.
"""

from __future__ import annotations

import numpy as np


def joint_mass(vectors, edges, weights=None):
    """Return a normalized signed 2D histogram, including explicit tail cells."""
    vectors = np.asarray(vectors)
    if vectors.ndim != 2 or vectors.shape[1] != 2 or not np.isfinite(vectors).all():
        raise ValueError("Finite signed bivariate vectors are required")
    mass = np.histogram2d(
        vectors[:, 0], vectors[:, 1], bins=(edges, edges), weights=weights
    )[0]
    total = len(vectors) if weights is None else np.sum(weights)
    if total <= 0 or not np.isclose(mass.sum(), total):
        raise ValueError("Joint histogram must cover the entire positive-weight sample")
    return mass / total


def histogram_distance(first, second):
    """Total variation of the two discretized joint laws, between zero and one."""
    return float(np.abs(np.asarray(first) - np.asarray(second)).sum() / 2)


def measure_joint(fixed, starts_by_flight, lags_s, chosen, exponent, reference_scale):
    """Use every fixed origin, equal flight mass, and one scalar power rescaling.

    Geographic axes and bin edges stay identical across lags. The reference scale
    is the radial median at the chosen lag closest to 1000 s, adjusted to 1000 s.
    No recentering or independent lag-wise whitening can erase drift or shape change.
    """
    if not np.isfinite(reference_scale) or reference_scale <= 0:
        raise ValueError("A positive common reference scale is required")
    interior = np.linspace(-6, 6, 65)
    edges = np.r_[-np.inf, interior, np.inf]
    laws = []
    for j in chosen:
        lag = int(lags_s[j] // 10)
        scale = reference_scale * (lags_s[j] / 1000.0) ** exponent
        mass = np.zeros((len(edges) - 1, len(edges) - 1))
        mean, second = np.zeros(2), np.zeros((2, 2))
        for (_, pos), starts in zip(fixed, starts_by_flight, strict=True):
            xy = (pos[starts + lag] - pos[starts]) / scale
            mass += joint_mass(xy, edges) / len(fixed)
            mean += xy.mean(axis=0) / len(fixed)
            second += xy.T @ xy / len(xy) / len(fixed)
        tail = 1 - mass[1:-1, 1:-1].sum()
        laws.append(
            {
                "lag_s": int(lags_s[j]),
                "mass": mass,
                "tail_mass": float(max(0, tail)),
                "mean": mean,
                "covariance": second - np.outer(mean, mean),
            }
        )
    distances = np.array(
        [[histogram_distance(a["mass"], b["mass"]) for b in laws] for a in laws]
    )
    return {
        "exponent": float(exponent),
        "reference_scale_m": float(reference_scale),
        "interior_edges": interior,
        "tail_cells": True,
        "laws": laws,
        "total_variation": distances,
        "interpretation": (
            "descriptive distance of discretized signed joint laws; no iid p-value"
        ),
    }
