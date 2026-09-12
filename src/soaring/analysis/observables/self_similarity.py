"""Fixed-population displacement scale families and paired flight resampling.

All probability levels, coordinates and lags use the same flights and origins.
Resampling acts on entire flights, never on their overlapping increments. These
are conditional sampling intervals: site/day dependence is not modelled here.
"""

from __future__ import annotations

import math
from itertools import pairwise

import numpy as np

from .joint_distribution import measure_joint
from .segment_support import increment_starts

PROBABILITIES = np.array([0.25, 0.50, 0.75, 0.90])


def recover_positions(measured, lags_s, grid_s=10):
    """Recover saved paths from every successive first-grid increment, with checks.

    The diagnostic cache stores these increments in chronological order within
    each flight. The origin is arbitrary; cumulative summation preserves all
    displacements up to floating point summation error. Reject incomplete paths.
    """
    if "_frames" in measured:
        return measured["_frames"]
    if lags_s[0] != grid_s:
        raise ValueError("Recovery requires every successive grid increment")
    vectors = measured["vectors"][0]
    owners = measured["owners"][0]
    if np.any(np.diff(owners) < 0):
        raise ValueError("Cached owners must be in flight order")
    offsets = np.r_[0, np.cumsum(np.bincount(owners, minlength=len(measured["frame"])))]
    frames = []
    for i, row in enumerate(measured["frame"].to_dict("records")):
        increments = vectors[offsets[i] : offsets[i + 1]]
        expected = round(row["duration_s"] / grid_s)
        if len(increments) != expected or not np.isfinite(increments).all():
            raise ValueError("Cached increments do not cover the complete segment")
        frames.append((row, np.vstack((np.zeros(2), np.cumsum(increments, axis=0)))))
    return frames


def ordered_quantiles(sorted_values, weights, probabilities, *, total=None):
    """Invert a weighted empirical CDF, correcting near-atom roundoff exactly."""
    total = math.fsum(weights) if total is None else total
    cumulative = np.cumsum(weights)
    targets = np.asarray(probabilities) * total
    indexes = np.minimum(np.searchsorted(cumulative, targets), len(weights) - 1)
    # Most targets lie inside a jump. Accurate sums are only necessary near a
    # jump boundary, avoiding one Python sum over the entire sample per rank.
    tolerance = 4 * len(weights) * np.finfo(float).eps * total
    for p, (index, target) in enumerate(zip(indexes, targets, strict=True)):
        before = cumulative[index - 1] if index else 0.0
        if min(abs(cumulative[index] - target), abs(before - target)) <= tolerance:
            while index < len(weights) - 1 and math.fsum(weights[: index + 1]) < target:
                index += 1
            while index > 0 and math.fsum(weights[:index]) >= target:
                index -= 1
            indexes[p] = index
    return sorted_values[indexes]


def paired_quantiles(values, owners, flight_counts, probabilities=PROBABILITIES):
    """Recompute mixture quantiles for every draw of whole-flight multiplicities.

    Each selected flight has equal total weight, split equally over its fixed
    origins. The same multiplicity matrix must be reused for all coordinates
    and all lags. Quantiles of separate flights are never averaged.
    """
    sizes = np.bincount(owners, minlength=flight_counts.shape[1])
    if np.any(sizes == 0):
        raise ValueError("Every fixed flight must contribute origins")
    result = np.empty((len(flight_counts), values.shape[1], len(probabilities)))
    for coordinate in range(values.shape[1]):
        order = np.argsort(values[:, coordinate], kind="stable")
        ordered = values[order, coordinate]
        who = owners[order]
        result[:, coordinate] = blocked_quantiles(
            ordered, who, sizes, flight_counts, probabilities
        )
    return result


def blocked_quantiles(ordered, who, sizes, flight_counts, probabilities, blocks=256):
    """Exact inverse CDF using flight counts at sorted block boundaries.

    Only the block containing a target is expanded per draw. The boundary count
    matrix is bounded by blocks times flights, independent of the origin count.
    This changes computation, not resampling units, weights or quantile ranks.
    """
    if len(ordered) < 4096:
        return np.array(
            [
                ordered_quantiles(
                    ordered,
                    counts[who] / sizes[who],
                    probabilities,
                    total=float(counts.sum()),
                )
                for counts in flight_counts
            ]
        )
    boundaries = np.unique(np.linspace(0, len(ordered), blocks + 1, dtype=int))
    cumulative_counts = np.zeros((len(boundaries), len(sizes)), dtype=np.int64)
    for j, (start, stop) in enumerate(pairwise(boundaries)):
        cumulative_counts[j + 1] = cumulative_counts[j] + np.bincount(
            who[start:stop], minlength=len(sizes)
        )
    result = np.empty((len(flight_counts), len(probabilities)))
    all_masses = (flight_counts / sizes) @ cumulative_counts.astype(float).T
    for draw, counts in enumerate(flight_counts):
        per_origin = counts / sizes
        masses = all_masses[draw]
        targets = np.asarray(probabilities) * counts.sum()
        for p, target in enumerate(targets):
            block = np.clip(np.searchsorted(masses, target) - 1, 0, len(boundaries) - 2)
            # Resolve floating-point block-edge ties using short accurate sums
            # over flight totals; no whole-origin scan is needed.
            while (
                block > 0 and math.fsum(cumulative_counts[block] * per_origin) >= target
            ):
                block -= 1
            while (
                block < len(boundaries) - 2
                and math.fsum(cumulative_counts[block + 1] * per_origin) < target
            ):
                block += 1
            start, stop = boundaries[block : block + 2]
            base = math.fsum(cumulative_counts[block] * per_origin)
            local = per_origin[who[start:stop]]
            cumulative = np.cumsum(local) + base
            rank = min(int(np.searchsorted(cumulative, target)), len(local) - 1)
            tolerance = 8 * len(local) * np.finfo(float).eps * counts.sum()
            if (
                min(
                    abs(cumulative[rank] - target),
                    abs((cumulative[rank - 1] if rank else base) - target),
                )
                <= tolerance
            ):
                # Full fsum only for rare exact atom boundaries, matching the
                # reference convention even for unequal numbers of origins.
                index = start + rank
                while (
                    index < len(ordered) - 1
                    and math.fsum(per_origin[who[: index + 1]]) < target
                ):
                    index += 1
                while index > 0 and math.fsum(per_origin[who[:index]]) >= target:
                    index -= 1
                rank = index - start
            result[draw, p] = ordered[start + rank]
    return result


def fit_quantiles(lags_s, curves, fit_range):
    """Fit separate log slopes and one common slope with rank-specific intercepts.

    Leading axes are arbitrary; the final axes are lag, coordinate, probability.
    A shared exponent uses equal weights for every lag and probability level.
    It is a candidate scaling factor, not evidence of an exact scaling law.
    """
    lags_s = np.asarray(lags_s)
    keep = (lags_s >= fit_range[0]) & (lags_s <= fit_range[1])
    y = np.log(np.asarray(curves)[..., keep, :, :])
    if keep.sum() < 3 or not np.isfinite(y).all():
        raise ValueError("Fits require at least three common positive supported lags")
    x = np.log(lags_s[keep] / 1000.0)
    xc = x - x.mean()
    h = np.sum(y * xc[:, None, None], axis=-3) / np.sum(xc**2)
    intercept = y.mean(axis=-3) - x.mean() * h
    residual = y - intercept[..., None, :, :] - x[:, None, None] * h[..., None, :, :]
    common = h.mean(axis=-1)
    common_intercept = y.mean(axis=-3) - x.mean() * common[..., :, None]
    common_residual = (
        y
        - common_intercept[..., None, :, :]
        - x[:, None, None] * common[..., None, :, None]
    )
    return {
        "lags_s": lags_s[keep],
        "h": h,
        "intercept_at_1000s": intercept,
        "rms_log10": np.sqrt(np.mean(residual**2, axis=-3)) / np.log(10),
        "common_h": common,
        "joint_common_h": common.mean(axis=-1),
        "common_intercept_at_1000s": common_intercept,
        "common_rms_log10": np.sqrt(np.mean(common_residual**2, axis=(-3, -1)))
        / np.log(10),
    }


def cdf_distance(first, first_weights, second, second_weights):
    """Exact supremum distance between two weighted ECDFs; no iid KS p-value."""
    grid = np.union1d(first, second)
    cdfs = []
    for values, weights in ((first, first_weights), (second, second_weights)):
        order = np.argsort(values, kind="stable")
        cumulative = np.r_[0, np.cumsum(weights[order]) / math.fsum(weights)]
        cdfs.append(cumulative[np.searchsorted(values[order], grid, side="right")])
    return float(np.max(np.abs(cdfs[0] - cdfs[1])))


def positive_histogram(values, weights, edges):
    """Probability masses over full positive support, recording a possible zero atom."""
    total = math.fsum(weights)
    positive = values > 0
    mass = (
        np.histogram(values[positive], bins=edges, weights=weights[positive])[0] / total
    )
    zero = math.fsum(weights[~positive]) / total
    if not np.isclose(mass.sum() + zero, 1, atol=1e-10):
        raise ValueError("Histogram edges omit probability mass")
    return mass, zero


def measure_scaling(frames, lags_s, *, n_resamples=400, seed=20260911, progress=None):
    """Measure absolute and squared laws on fixed long flights and common origins."""
    lags_s = np.asarray(lags_s)
    longest = int(lags_s[-1] // 10)
    fixed = [
        (row, pos)
        for row, pos in frames
        if row.get("duration_s", (len(pos) - 1) * 10) >= 20000
    ]
    if len(fixed) < 3:
        raise ValueError("At least three segments of 20000 s are required")
    starts_by_flight = [
        increment_starts(row, len(pos), longest, stride=1) for row, pos in fixed
    ]
    sizes = np.array([len(starts) for starts in starts_by_flight])
    owners = np.repeat(np.arange(len(fixed)), sizes)
    weights = 1.0 / sizes[owners]
    rng = np.random.default_rng(seed)
    counts = rng.multinomial(
        len(fixed), np.full(len(fixed), 1 / len(fixed)), n_resamples
    )
    # The leading all-ones draw is the original equal-flight empirical law.
    counts = np.vstack((np.ones(len(fixed), dtype=int), counts))
    all_quantiles = np.empty((len(counts), len(lags_s), 3, 4))
    dense_probabilities = np.unique(np.r_[np.linspace(0.01, 0.99, 99), PROBABILITIES])
    dense = np.empty((len(lags_s), 3, len(dense_probabilities)))
    chosen = np.unique(
        [np.argmin(abs(lags_s - t)) for t in (10, 80, 320, 1000, 3000, 10000)]
    )
    samples = {}
    for j, tau in enumerate(lags_s):
        lag = int(tau // 10)
        xy = np.concatenate(
            [
                pos[starts + lag] - pos[starts]
                for (_, pos), starts in zip(fixed, starts_by_flight, strict=True)
            ]
        )
        values = np.column_stack((np.abs(xy), np.linalg.norm(xy, axis=1)))
        all_quantiles[:, j] = paired_quantiles(values, owners, counts)
        for coordinate in range(3):
            order = np.argsort(values[:, coordinate], kind="stable")
            dense[j, coordinate] = ordered_quantiles(
                values[order, coordinate], weights[order], dense_probabilities
            )
        if j in chosen:
            if hasattr(frames, "directory"):
                sample = np.lib.format.open_memmap(
                    frames.directory / f"scaling-values-{j}.npy",
                    mode="w+",
                    dtype="float64",
                    shape=values.shape,
                )
                sample[:] = values
                sample.flush()
                samples[j] = sample
            else:
                samples[j] = values
        if progress:
            progress(
                f"lag {tau:g} s: {len(fixed)} flights, {len(owners)} fixed origins"
            )
    curves = all_quantiles[0]
    fit_ranges = {
        "full": (10, 10000),
        "intermediate": (60, 2000),
        "late_intermediate": (200, 2000),
    }
    fits = {}
    for name, limits in fit_ranges.items():
        fit = fit_quantiles(lags_s, curves, limits)
        boot = fit_quantiles(lags_s, all_quantiles[1:], limits)
        fit["h_ci95"] = np.quantile(boot["h"], [0.025, 0.975], axis=0)
        fit["common_h_ci95"] = np.quantile(boot["common_h"], [0.025, 0.975], axis=0)
        # Paired differences, not visual comparisons of marginal intervals.
        contrasts = {
            "north_minus_east": (
                fit["h"][1] - fit["h"][0],
                boot["h"][:, 1] - boot["h"][:, 0],
            ),
            "radial_minus_east": (
                fit["h"][2] - fit["h"][0],
                boot["h"][:, 2] - boot["h"][:, 0],
            ),
            "radial_minus_north": (
                fit["h"][2] - fit["h"][1],
                boot["h"][:, 2] - boot["h"][:, 1],
            ),
            "p90_minus_p25": (
                fit["h"][:, 3] - fit["h"][:, 0],
                boot["h"][:, :, 3] - boot["h"][:, :, 0],
            ),
        }
        fit["contrasts"] = {
            key: {"estimate": value, "ci95": np.quantile(draws, [0.025, 0.975], axis=0)}
            for key, (value, draws) in contrasts.items()
        }
        fits[name] = fit
    laws = []
    for k in range(3):
        low = min(
            np.min(v[:, k], where=v[:, k] > 0, initial=np.inf) for v in samples.values()
        )
        high = max(v[:, k].max() for v in samples.values())
        edges = np.geomspace(low * (1 - 1e-10), high * (1 + 1e-10), 101)
        histograms = [
            positive_histogram(samples[j][:, k], weights, edges) for j in chosen
        ]
        common_h = fits["full"]["common_h"][k]
        pairs = []
        for a, first in enumerate(chosen):
            for second in chosen[a + 1 :]:
                pair = {"lags_s": [lags_s[first], lags_s[second]]}
                for name, scales in (
                    ("power", (lags_s / 1000.0) ** common_h),
                    ("median", curves[:, k, 1]),
                ):
                    pair[name] = cdf_distance(
                        samples[first][:, k] / scales[first],
                        weights,
                        samples[second][:, k] / scales[second],
                        weights,
                    )
                pairs.append(pair)
        laws.append(
            {
                "edges_m": edges,
                "mass": np.array([h[0] for h in histograms]),
                "zero_mass": np.array([h[1] for h in histograms]),
                "squared_edges_m2": edges**2,
                "cdf_distances": pairs,
            }
        )
    joint_h = fits["full"]["joint_common_h"]
    reference = int(np.argmin(abs(lags_s - 1000)))
    reference_scale = curves[reference, 2, 1] / (lags_s[reference] / 1000.0) ** joint_h
    joint = measure_joint(
        fixed, starts_by_flight, lags_s, chosen, joint_h, reference_scale
    )
    return {
        "lags_s": lags_s,
        "probabilities": PROBABILITIES,
        "flight_ids": [row["flight_id"] for row, _ in fixed],
        "segment_ids": [
            row.get("segment_ids", [row["segment_id"]]) for row, _ in fixed
        ],
        "origin_counts": sizes,
        "n_flights": len(fixed),
        "n_origins": len(owners),
        "quantiles_m": curves,
        "quantiles_m2": curves**2,
        "dense_probabilities": dense_probabilities,
        "dense_quantiles_m": dense,
        "fits": fits,
        "display_lag_indexes": chosen,
        "laws": laws,
        "joint": joint,
        "bootstrap": {
            "unit": "whole flight",
            "resamples": n_resamples,
            "seed": seed,
            "interval": "pointwise percentile 95%; conditional, no site/day clustering",
        },
    }
