"""Vertical and trajectory support for an indicative regional wind reference."""

from __future__ import annotations

import numpy as np

from .segment_support import increment_starts


def window_altitude_means(row, fixes, *, lag_s=10000, grid_s=10):
    """Average altitude along the same nonoverlapping windows as regional PCA.

    Reconstruct the declared segment grids from cleaned absolute altitude ``z``.
    Trapezoidal time integration gives every equal-duration window equal weight.
    Disconnected segments never contribute an artificial vertical interval.
    """
    if lag_s <= 0 or grid_s <= 0 or lag_s % grid_s:
        raise ValueError("Lag must be a positive multiple of the grid")
    pieces = []
    for sid, (start, stop), t0 in zip(
        row["segment_ids"], row["segments"], row["segment_start_s"], strict=True
    ):
        segment = fixes.loc[fixes.segment_id.eq(sid)]
        time = segment.t.to_numpy(dtype=float)
        altitude = segment.z.to_numpy(dtype=float)
        if (
            len(time) < 2
            or not (np.diff(time) > 0).all()
            or not np.isfinite(altitude).all()
        ):
            raise ValueError("Altitude requires a finite, ordered retained segment")
        grid = t0 + grid_s * np.arange(stop - start)
        if grid[0] < time[0] - 1e-6 or grid[-1] > time[-1] + 1e-6:
            raise ValueError("The PCA grid extends outside retained altitude support")
        pieces.append(np.interp(grid, time, altitude))
    altitude = np.concatenate(pieces)
    if len(altitude) != row["length"]:
        raise ValueError("Altitude and PCA coordinate lengths differ")
    lag = int(lag_s / grid_s)
    starts = increment_starts(row, len(altitude), lag)
    integral = np.r_[0, np.cumsum((altitude[:-1] + altitude[1:]) / 2)]
    return (integral[starts + lag] - integral[starts]) / lag


def wind_at_height(u, v, height_m, target_m, *, surface_height_m=None):
    """Interpolate E/N components between bracketing above-ground level heights.

    The last dimension indexes pressure levels in increasing height order.
    Geopotential heights must already be converted to metres. No vertical
    extrapolation or interpolation of degree angles is permitted. Missing or
    unbracketed profiles are rejected so time selections cannot silently differ.
    """
    u, v, height = (np.asarray(a, dtype=float) for a in (u, v, height_m))
    if (
        u.shape != v.shape
        or u.shape != height.shape
        or height.ndim < 1
        or height.shape[-1] < 2
        or not np.isfinite(target_m)
        or not all(np.isfinite(a).all() for a in (u, v, height))
        or not (np.diff(height, axis=-1) > 0).all()
    ):
        raise ValueError("Wind profiles require finite values and ordered heights")
    lower = np.sum(height <= target_m, axis=-1) - 1
    lower = np.clip(lower, 0, height.shape[-1] - 2)

    def take(array, index):
        return np.take_along_axis(array, index[..., None], axis=-1)[..., 0]

    z0, z1 = take(height, lower), take(height, lower + 1)
    if ((target_m < z0) | (target_m > z1)).any():
        raise ValueError("Target height is not bracketed; extrapolation is forbidden")
    if surface_height_m is not None:
        surface = np.asarray(surface_height_m, dtype=float)
        if not np.isfinite(surface).all():
            raise ValueError("Model surface heights must be finite")
        if (z0 < surface).any():
            raise ValueError("A bracketing pressure level lies below the model surface")
    fraction = (target_m - z0) / (z1 - z0)
    result = tuple(
        take(a, lower) * (1 - fraction) + take(a, lower + 1) * fraction for a in (u, v)
    )
    return result
