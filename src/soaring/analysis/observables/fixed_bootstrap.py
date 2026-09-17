"""Coupled site-day bootstrap and exact weighted quantiles with bounded memory."""

from __future__ import annotations

from itertools import pairwise

import numpy as np


def cluster_draws(labels, n_resamples=1000, seed=20260917):
    """Draw G site-day groups G times; leading row is the observed population."""
    labels = np.asarray(labels, dtype=int)
    if labels.ndim != 1 or not len(labels) or labels.min() != 0:
        raise ValueError("Expected nonempty contiguous cluster labels starting at zero")
    groups = int(labels.max()) + 1
    if len(np.unique(labels)) != groups:
        raise ValueError("Cluster labels must be contiguous")
    rng = np.random.default_rng(seed)
    draws = np.ones((n_resamples + 1, groups), dtype=np.uint16)
    for b in range(1, len(draws)):
        counts = np.bincount(rng.integers(groups, size=groups), minlength=groups)
        if counts.max() > np.iinfo(np.uint16).max:
            raise OverflowError("Bootstrap multiplicity exceeds storage width")
        draws[b] = counts
    return draws


def bootstrap_means(values, labels, draws):
    """Equal-flight means with missing support, preserving paired cluster draws."""
    values = np.asarray(values, dtype=float)
    shape = values.shape[1:]
    flat = values.reshape(len(values), -1)
    good = np.isfinite(flat)
    groups = draws.shape[1]
    sums = np.zeros((groups, flat.shape[1]))
    counts = np.zeros_like(sums)
    np.add.at(sums, labels, np.where(good, flat, 0))
    np.add.at(counts, labels, good)
    output = np.empty((len(draws), flat.shape[1]))
    # Float conversion and matrix products are bounded independently of all draws.
    for a in range(0, len(draws), 100):
        weight = draws[a : a + 100].astype(float)
        denominator = weight @ counts
        output[a : a + 100] = np.divide(
            weight @ sums,
            denominator,
            out=np.full_like(denominator, np.nan),
            where=denominator > 0,
        )
    return output.reshape((len(draws), *shape))


def mixture_quantiles(values, sizes, labels, draws, probabilities, bins=1024):
    """Invert each bootstrap equal-flight ECDF, returning observed sample values.

    Values are contiguous by flight. Weighted histograms locate the block of each
    requested rank; only those blocks are sorted. The final rank is obtained from
    the original observations and per-origin weights, never from bin centres or
    interpolated quantile values. This permits disk-backed input of any length.
    """
    sizes = np.asarray(sizes, dtype=np.int64)
    labels = np.asarray(labels, dtype=np.int64)
    probabilities = np.asarray(probabilities, dtype=float)
    if len(sizes) != len(labels) or np.any(sizes <= 0) or sizes.sum() != len(values):
        raise ValueError("Every fixed flight needs its exact positive origin count")
    if np.any((probabilities <= 0) | (probabilities >= 1)):
        raise ValueError("Probabilities must lie strictly between zero and one")
    unique, local_labels = np.unique(labels, return_inverse=True)
    weight_draws = draws[:, unique]
    groups = len(unique)
    flight_totals = np.bincount(local_labels, minlength=groups)
    totals = weight_draws.astype(float) @ flight_totals
    offsets = np.r_[0, np.cumsum(sizes)]
    maximum = float(np.max(values))
    if not np.isfinite(maximum) or np.min(values) < 0:
        raise ValueError("Quantile amplitudes must be finite and nonnegative")
    if maximum == 0:
        return np.where(
            totals[:, None] > 0, np.zeros((len(draws), len(probabilities))), np.nan
        )
    histogram = np.zeros((groups, bins))
    factor = bins / maximum

    def indices(part):
        return np.minimum((part * factor).astype(np.int64), bins - 1)

    for f, (a, b) in enumerate(pairwise(offsets)):
        histogram[local_labels[f]] += (
            np.bincount(indices(values[a:b]), minlength=bins) / sizes[f]
        )
    cumulative = np.cumsum(histogram, axis=1)
    del histogram
    masses = np.empty((len(draws), bins))
    for a in range(0, len(draws), 100):
        masses[a : a + 100] = weight_draws[a : a + 100].astype(float) @ cumulative
    del cumulative
    targets = totals[:, None] * probabilities
    # Resolve floating summation noise at exact ECDF jumps consistently to the left.
    tolerance = 128 * np.finfo(float).eps * np.maximum(totals, 1)
    target_bins = np.array(
        [
            np.searchsorted(m, row - tol, side="left")
            for m, row, tol in zip(masses, targets, tolerance, strict=True)
        ]
    )
    target_bins = np.minimum(target_bins, bins - 1)
    needed = np.zeros(bins, dtype=bool)
    needed[np.unique(target_bins)] = True
    selected_values = []
    selected_flights = []
    selected_bins = []
    for f, (a, b) in enumerate(pairwise(offsets)):
        part = values[a:b]
        ids = indices(part)
        keep = needed[ids]
        if keep.any():
            selected_values.append(part[keep])
            selected_bins.append(ids[keep])
            selected_flights.append(np.full(keep.sum(), f, dtype=np.int32))
    selected = np.concatenate(selected_values)
    who = np.concatenate(selected_flights)
    bin_id = np.concatenate(selected_bins)
    del selected_values, selected_flights, selected_bins
    order = np.argsort(selected, kind="quicksort")
    selected = selected[order]
    who = who[order]
    bin_id = bin_id[order]
    del order
    cuts = np.searchsorted(bin_id, np.arange(bins + 1))
    result = np.full((len(draws), len(probabilities)), np.nan)
    for d in range(len(draws)):
        if totals[d] == 0:
            continue
        for p, k in enumerate(target_bins[d]):
            a, b = cuts[k : k + 2]
            owners = who[a:b]
            weights = weight_draws[d, local_labels[owners]] / sizes[owners]
            base = masses[d, k - 1] if k else 0.0
            local = np.cumsum(weights)
            rank = int(
                np.searchsorted(local, targets[d, p] - base - tolerance[d], side="left")
            )
            rank = min(rank, len(local) - 1)
            # A zero-multiplicity observation cannot carry a newly crossed rank.
            while rank < len(local) - 1 and weights[rank] == 0:
                rank += 1
            result[d, p] = selected[a + rank]
    return result
