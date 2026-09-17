"""One equal-flight measure for fixed-segment transport and displacement scaling.

A flight's total mass is one. At each lag it is divided over every supported
origin in its selected continuous segments. The selected segments are fixed by
maximum lag / 0.8; origins are allowed to change with lag.
"""

from __future__ import annotations

import hashlib
import json

import numpy as np

SHORT_LAGS = np.arange(1, 10)
GRID_S = 10
SUPPORT_FRACTION = 0.8
LAGS = np.unique(np.r_[np.round(np.geomspace(1, 1000, 35)).astype(int) * 10, 100, 1000])
GENERAL_LAGS = np.unique(
    np.r_[np.arange(1, 10), LAGS, np.round(np.geomspace(10000, 43200, 22) / 10) * 10]
)
ORDERS = np.array([0.25, 0.5, 0.75, 1, 1.5, 2, 2.5, 3, 3.5, 4])
PROBABILITIES = np.array([0.25, 0.5, 0.75, 0.9])
COHORT_LIMITS = (100, 1000, 10000)
FIT_RANGES = ((10, 10000), (10, 100), (100, 1000), (1000, 10000))


def selected_segments(row, maximum_lag):
    """Select whole segment identities once, using their actual grid span."""
    return [
        (int(a), int(b))
        for a, b in row["segments"]
        if (b - a - 1) * GRID_S * SUPPORT_FRACTION >= maximum_lag - 1e-9
    ]


def cohort_manifest(rows, maximum_lag):
    """Record every selected flight and segment, with a reproducible identity."""
    members = []
    for index, row in enumerate(rows):
        spans = selected_segments(row, maximum_lag)
        if not spans:
            continue
        ids = row.get("segment_ids", list(range(len(row["segments"]))))
        segments = [
            {
                "segment_id": int(sid),
                "start": int(a),
                "stop": int(b),
                "duration_s": (b - a - 1) * GRID_S,
            }
            for sid, (a, b) in zip(ids, row["segments"], strict=True)
            if (a, b) in spans
        ]
        members.append(
            {
                "flight_id": str(row["flight_id"]),
                "frame_index": index,
                "segments": segments,
            }
        )
    manifest = {
        "grid_s": GRID_S,
        "maximum_lag_s": maximum_lag,
        "support_fraction": SUPPORT_FRACTION,
        "members": members,
        "weighting": "equal flight; equal available origins within each flight",
    }
    manifest["sha256"] = hashlib.sha256(
        json.dumps(manifest, sort_keys=True).encode()
    ).hexdigest()
    return manifest


def increments(positions, segments, lag):
    """All overlapping displacements, without joining disconnected segments."""
    if lag < 1 or int(lag) != lag:
        raise ValueError("Lag must be a positive integer grid step")
    return np.concatenate(
        [
            positions[a + lag : b] - positions[a : b - lag]
            for a, b in segments
            if b - a > lag
        ]
    )


def native_short_msd(segments, lags=SHORT_LAGS):
    """Pool native origins per flight, using only exactly resolved short lags."""
    sums, counts = np.zeros(len(lags)), np.zeros(len(lags), dtype=np.int64)
    for t, xy in segments:
        if len(t) < 2:
            continue
        dt = float(np.median(np.diff(t)))
        if not np.allclose(np.diff(t), dt, rtol=1e-5, atol=1e-4):
            raise ValueError("Cleaned segment is not on a uniform native grid")
        for j, tau in enumerate(lags):
            k = round(tau / dt)
            if k < 1 or k >= len(t) or not np.isclose(k * dt, tau, atol=1e-5):
                continue
            if tau > SUPPORT_FRACTION * (t[-1] - t[0]):
                continue
            d = xy[k:] - xy[:-k]
            sums[j] += np.einsum("ij,ij->", d, d)
            counts[j] += len(d)
    return np.divide(sums, counts, out=np.full(len(lags), np.nan), where=counts > 0)


def launch_curve(segments, lags=GENERAL_LAGS):
    """Squared ENU distance from the post-trim origin on the retained parent clock.

    Interpolate within a supported native segment only. A requested elapsed time
    shorter than that segment's cadence is not measured. Gaps remain missing.
    ENU zero is the pipeline's post-trim origin, preceding final segment cuts.
    """
    out = np.full(len(lags), np.nan)
    for t, xy in segments:
        if len(t) < 2:
            continue
        dt = float(np.median(np.diff(t)))
        use = (lags >= t[0]) & (lags <= t[-1]) & (lags >= dt)
        if np.isfinite(out[use]).any():
            raise ValueError("Overlapping retained segments")
        out[use] = sum(np.interp(lags[use], t, xy[:, k]) ** 2 for k in (0, 1))
    return out


def log_fit(lags, curves, interval=(10, 10000)):
    """OLS with equal weight per saved lag; the last axis is time."""
    lags = np.asarray(lags)
    take = (lags >= interval[0]) & (lags <= interval[1])
    x = np.log10(lags[take])
    y = np.asarray(curves)[..., take]
    if len(x) < 3:
        raise ValueError("A fit needs at least three lag values")
    good = np.isfinite(y).all(axis=-1) & (y > 0).all(axis=-1)
    with np.errstate(divide="ignore", invalid="ignore"):
        y = np.log10(y)
    weights = (x - x.mean()) / np.sum((x - x.mean()) ** 2)
    slope = y @ weights
    intercept = y.mean(axis=-1) - slope * x.mean()
    residual = y - intercept[..., None] - slope[..., None] * x
    slope = np.where(good, slope, np.nan)
    return {
        "slope": slope,
        "intercept": np.where(good, intercept, np.nan),
        "rms_dex": np.where(good, np.sqrt(np.mean(residual**2, axis=-1)), np.nan),
        "lag_count": int(take.sum()),
        "interval_s": list(interval),
    }


def local_slopes(lags, curves, half_width_dex=0.25, *, expand_sparse=False):
    """Local OLS slopes, optionally filling sparse interior windows with three lags.

    The fallback changes only windows containing fewer than three points. It uses
    the nearest three lags in log time and requires two available lags on either
    side of the target, so estimates near the domain boundaries remain unchanged.
    """
    x = np.log10(lags)
    y = np.asarray(curves)
    output = np.full_like(y, np.nan)
    for i in range(len(x)):
        take = np.flatnonzero(np.abs(x - x[i]) <= half_width_dex + 1e-12)
        if len(take) < 3 and expand_sparse and 2 <= i < len(x) - 2:
            take = np.sort(np.argsort(np.abs(x - x[i]), kind="stable")[:3])
        if len(take) < 3:
            continue
        output[..., i] = log_fit(
            np.asarray(lags)[take], y[..., take], (lags[take[0]], lags[take[-1]])
        )["slope"]
    return output


def centred_excess(raw):
    """Fisher excess from signed raw moments centred at the mixture mean."""
    m1, m2, m3, m4 = np.moveaxis(np.asarray(raw), -1, 0)
    variance = m2 - m1 * m1
    fourth = m4 - 4 * m1 * m3 + 6 * m1 * m1 * m2 - 3 * m1**4
    return (
        np.divide(
            fourth, variance**2, out=np.full_like(variance, np.nan), where=variance > 0
        )
        - 3
    )
