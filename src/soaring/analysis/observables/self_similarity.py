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

# The chapter's moment orders. Fractional orders below one resolve the small
# displacements that positive moments otherwise cannot weigh.
MOMENT_ORDERS = np.array([0.25, 0.5, 0.75, 1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0])

# Reference fit window, in seconds: the widest window of the chapter's lag grid whose
# quantile and moment fits stay within 0.03 dex for both disciplines. Below it the
# lower quantiles measure circling inside one thermal; above it displacement saturates
# on closed circuits. :func:`widest_windows` reproduces the choice from the curves.
REFERENCE_RANGE = (60, 2960)


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


def excess_kurtosis(values, owners, sizes, counts):
    r"""Weighted Fisher excess kurtosis of each coordinate, for every bootstrap draw.

    ``counts[d, f] / sizes[f]`` is flight ``f``'s per-origin weight on draw ``d``, the
    same convention :func:`paired_quantiles` uses. Every origin of a flight shares that
    weight, so the weighted raw moments reduce to a flight-level sum of power sums,
    computed once with :func:`numpy.bincount` (not :func:`numpy.add.at`, which
    scatter-adds the whole matrix and costs seconds rather than milliseconds here) and
    reused across all draws by one matrix product.

    Args:
        values: ``(n_origins, K)`` coordinate magnitudes at one lag.
        owners: Parent-flight index of each origin, in ``0..len(sizes)-1``.
        sizes: Origins per flight.
        counts: ``(n_draws, len(sizes))`` whole-flight multiplicities; row 0 is
            conventionally the all-ones empirical draw.

    Returns:
        ``(n_draws, K)`` excess kurtosis, ``mu4/mu2**2 - 3``, biased population moments.
    """
    n_flights = len(sizes)
    sums = np.empty((n_flights, values.shape[1], 4))
    for k in range(values.shape[1]):
        for p in range(1, 5):
            sums[:, k, p - 1] = np.bincount(owners, values[:, k] ** p, n_flights)
    weight = counts / sizes
    moments = np.einsum("df,fkp->dkp", weight, sums) / counts.sum(axis=1)[:, None, None]
    m1, m2, m3, m4 = (moments[..., p] for p in range(4))
    mu2 = m2 - m1**2
    mu4 = m4 - 4 * m1 * m3 + 6 * m1**2 * m2 - 3 * m1**4
    return mu4 / mu2**2 - 3


def log_slopes(lags_s, curves, fit_range):
    """Least-squares log-log slopes over one lag window, with residuals in dex.

    Leading axes are arbitrary; the final axes are lag, coordinate and rank or order.
    Quantiles and moments share this core so that one window and one residual
    convention govern both families of exponents.
    """
    lags_s = np.asarray(lags_s)
    keep = (lags_s >= fit_range[0]) & (lags_s <= fit_range[1])
    y = np.log(np.asarray(curves)[..., keep, :, :])
    if keep.sum() < 3 or not np.isfinite(y).all():
        raise ValueError("Fits require at least three common positive supported lags")
    x = np.log(lags_s[keep] / 1000.0)
    xc = x - x.mean()
    slope = np.sum(y * xc[:, None, None], axis=-3) / np.sum(xc**2)
    intercept = y.mean(axis=-3) - x.mean() * slope
    residual = (
        y - intercept[..., None, :, :] - x[:, None, None] * slope[..., None, :, :]
    )
    return {
        "lags_s": lags_s[keep],
        "log_lags": x,
        "log_curves": y,
        "slope": slope,
        "intercept_at_1000s": intercept,
        "rms_log10": np.sqrt(np.mean(residual**2, axis=-3)) / np.log(10),
    }


def fit_moments(lags_s, curves, fit_range, orders=MOMENT_ORDERS):
    """Fit the displacement moment spectrum over one lag window.

    Leading axes are arbitrary; the final axes are lag, coordinate, moment order.
    ``zeta`` is the log-log slope of the moment itself and ``nu`` is ``zeta/q``, the
    growth exponent per unit order. A constant ``nu`` is what one exponent predicts;
    the residual says whether a power law describes the moment at all.
    """
    fit = log_slopes(lags_s, curves, fit_range)
    return {
        "lags_s": fit["lags_s"],
        "zeta": fit["slope"],
        "nu": fit["slope"] / np.asarray(orders),
        "intercept_at_1000s": fit["intercept_at_1000s"],
        "rms_log10": fit["rms_log10"],
    }


def widest_windows(lags_s, families, tolerances, *, min_lags=5):
    """Widest lag window whose every fitted curve stays within each residual tolerance.

    ``families`` are arrays sharing the leading lag axis, from any number of
    disciplines and of both kinds. One window must serve all of them, so the criterion
    is the worst root-mean-square residual over every curve, in dex. The scan reports
    the choice a tolerance implies; it does not certify that a power law holds.
    """
    lags_s = np.asarray(lags_s)
    scanned = []
    for start in range(len(lags_s)):
        for stop in range(start + min_lags - 1, len(lags_s)):
            window = (lags_s[start], lags_s[stop])
            worst = max(
                float(np.max(log_slopes(lags_s, curves, window)["rms_log10"]))
                for curves in families
            )
            scanned.append((window, stop - start + 1, worst))
    rows = []
    for tolerance in tolerances:
        allowed = [row for row in scanned if row[2] <= tolerance]
        if not allowed:
            rows.append({"tolerance_dex": tolerance, "lags_s": None})
            continue
        window, n_lags, worst = max(allowed, key=lambda row: row[0][1] / row[0][0])
        rows.append(
            {
                "tolerance_dex": tolerance,
                "lags_s": window,
                "n_lags": n_lags,
                "decades": float(np.log10(window[1] / window[0])),
                "worst_rms_log10": worst,
            }
        )
    return rows


def flight_power_means(values, offsets, sizes, orders=MOMENT_ORDERS):
    """Per-flight mean of each coordinate magnitude raised to each moment order.

    Equal-weight and bootstrap moments are both linear in these means, the same way
    :func:`excess_kurtosis` reuses per-flight power sums, so one pass over the origins
    serves every draw. Origins arrive grouped by flight, so contiguous reductions
    replace one scatter-add per order.

    Args:
        values: ``(n_origins, K)`` coordinate magnitudes at one lag.
        offsets: Index in ``values`` where each flight's origins begin.
        sizes: Origins per flight.
        orders: Moment orders, all strictly positive.

    Returns:
        ``(len(sizes), K, len(orders))`` per-flight means.
    """
    means = np.empty((len(sizes), values.shape[1], len(orders)))
    for k in range(values.shape[1]):
        for j, order in enumerate(orders):
            means[:, k, j] = np.add.reduceat(values[:, k] ** order, offsets) / sizes
    return means


def fit_quantiles(lags_s, curves, fit_range):
    """Fit separate log slopes and one common slope with rank-specific intercepts.

    Leading axes are arbitrary; the final axes are lag, coordinate, probability.
    A shared exponent uses equal weights for every lag and probability level.
    It is a candidate scaling factor, not evidence of an exact scaling law.
    """
    fit = log_slopes(lags_s, curves, fit_range)
    x, y, h = fit["log_lags"], fit["log_curves"], fit["slope"]
    intercept = fit["intercept_at_1000s"]
    common = h.mean(axis=-1)
    common_intercept = y.mean(axis=-3) - x.mean() * common[..., :, None]
    common_residual = (
        y
        - common_intercept[..., None, :, :]
        - x[:, None, None] * common[..., None, :, None]
    )
    return {
        "lags_s": fit["lags_s"],
        "h": h,
        "intercept_at_1000s": intercept,
        "rms_log10": fit["rms_log10"],
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
    offsets = np.r_[0, np.cumsum(sizes)][:-1]
    replications = counts.astype(float)
    totals = replications.sum(axis=1)[:, None]
    all_quantiles = np.empty((len(counts), len(lags_s), 3, 4))
    moment_draws = np.empty((len(counts), len(lags_s), 3, len(MOMENT_ORDERS)))
    kurtosis_draws = np.empty((len(counts), len(lags_s), 3))
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
        means = flight_power_means(values, offsets, sizes)
        moment_draws[:, j] = (
            replications @ means.reshape(len(fixed), -1) / totals
        ).reshape(len(counts), 3, len(MOMENT_ORDERS))
        kurtosis_draws[:, j] = excess_kurtosis(values, owners, sizes, counts)
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
    moments = moment_draws[0]
    fit_ranges = {
        "reference": REFERENCE_RANGE,
        "full": (10, 10000),
        "intermediate": (60, 2000),
        "late_intermediate": (200, 2000),
    }
    fits = {}
    for name, limits in fit_ranges.items():
        fit = fit_quantiles(lags_s, curves, limits)
        boot = fit_quantiles(lags_s, all_quantiles[1:], limits)
        spectrum = fit_moments(lags_s, moments, limits)
        spectrum_boot = fit_moments(lags_s, moment_draws[1:], limits)
        fit["h_ci95"] = np.quantile(boot["h"], [0.025, 0.975], axis=0)
        fit["common_h_ci95"] = np.quantile(boot["common_h"], [0.025, 0.975], axis=0)
        fit["zeta"] = spectrum["zeta"]
        fit["nu"] = spectrum["nu"]
        fit["nu_ci95"] = np.quantile(spectrum_boot["nu"], [0.025, 0.975], axis=0)
        fit["moment_rms_log10"] = spectrum["rms_log10"]
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
            # A flat spectrum is what a single exponent predicts, so the span of nu
            # is the paired statistic that a linear spectrum sends to zero.
            "nu_top_minus_bottom": (
                spectrum["nu"][:, -1] - spectrum["nu"][:, 0],
                spectrum_boot["nu"][:, :, -1] - spectrum_boot["nu"][:, :, 0],
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
        "moment_orders": MOMENT_ORDERS,
        "moments_mq": moments,
        "moments_ci95": np.quantile(moment_draws[1:], [0.025, 0.975], axis=0),
        "kurtosis": kurtosis_draws[0],
        "kurtosis_ci95": np.quantile(kurtosis_draws[1:], [0.025, 0.975], axis=0),
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
