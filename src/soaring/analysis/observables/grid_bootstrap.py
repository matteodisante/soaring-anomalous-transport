"""Fixed metric cells crossed with launch-altitude class and month of year.

Grid membership depends only on the launch position, never on site names or
pairwise distances. All years share the same twelve seasonal month labels.
WGS84 UTM zone and hemisphere are part of the cell identity, covering the archive
without applying a France-only projection to flights elsewhere in the world.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from pyproj import Transformer

BANDS = ("Plains", "Hills", "Low mountains", "High mountains")


def project_launches(frame):
    """Project origins in their fixed six-degree UTM zone and hemisphere.

    Use the regular longitude partition (no Norway/Svalbard exceptions). Each
    zone's cells are implicitly clipped to that zone and hemisphere. The 50 km
    side is measured in projected metres; UTM has small ground-scale distortion.
    """
    lat = frame.lat0.to_numpy(dtype=float)
    lon = frame.lon0.to_numpy(dtype=float)
    if (
        not np.isfinite(lat).all()
        or not np.isfinite(lon).all()
        or (lat < -80).any()
        or (lat > 84).any()
        or (np.abs(lon) > 180).any()
    ):
        raise ValueError("Launch positions must be finite and within the UTM domain")
    # Canonicalise +180 and -180 to the same meridian.
    lon = (lon + 180) % 360 - 180
    zone = np.floor((lon + 180) / 6).astype(int) + 1
    epsg = np.where(lat >= 0, 32600, 32700) + zone
    x, y = np.empty(len(frame)), np.empty(len(frame))
    for code in np.unique(epsg):
        take = epsg == code
        transformer = Transformer.from_crs(4326, int(code), always_xy=True)
        x[take], y[take] = transformer.transform(lon[take], lat[take], errcheck=True)
    return pd.DataFrame(
        {"epsg": epsg, "easting_m": x, "northing_m": y}, index=frame.index
    )


def cell_membership(projected, side_km=50, shift=(0, 0)):
    """Assign each origin to one half-open metric square in the fixed grid."""
    side = float(side_km) * 1000
    shift = np.asarray(shift, dtype=float) * 1000
    if (
        not np.isfinite(side)
        or not 0 < side <= 50000
        or shift.shape != (2,)
        or not np.isfinite(shift).all()
        or (shift < 0).any()
        or (shift >= side).any()
    ):
        raise ValueError("Grid sides must be at most 50 km and shifts within one cell")
    xy = projected[["easting_m", "northing_m"]].to_numpy()
    if not np.isfinite(xy).all():
        raise ValueError("Finite projected launch coordinates are required")
    indices = np.floor((xy - shift) / side).astype(np.int64)
    result = projected[["epsg"]].copy()
    result["ix"], result["iy"] = indices.T
    result["x_min_m"], result["y_min_m"] = (indices * side + shift).T
    result["x_max_m"] = result.x_min_m + side
    result["y_max_m"] = result.y_min_m + side
    return result


def grid_season_labels(frame, cells, months=1, month_offset=0, pool_terrain=False):
    """Cross cells with altitude band and cyclic month bins, pooling all years.

    Missing dates or altitudes get singleton archive labels. Callers must fail if
    any belong to the analysed cohort. Adjacent-month unions and terrain pooling
    are diagnostic alternatives, not the requested baseline grouping.
    """
    if months not in (1, 2, 3, 4, 6, 12) or not 0 <= month_offset < months:
        raise ValueError("Month width must divide twelve and offset must be within it")
    if len(cells) != len(frame) or not cells.index.equals(frame.index):
        raise ValueError("Cells must be aligned with flight metadata")
    dates = pd.to_datetime(frame.date, format="%Y-%m-%d", errors="coerce")
    band = pd.cut(
        frame.alt0, [-np.inf, 300, 800, 1500, np.inf], labels=BANDS, right=False
    )
    if "altitude_band" in frame:
        same = band.astype("string").fillna("missing") == frame.altitude_band.astype(
            "string"
        ).fillna("missing")
        if not same.all():
            raise ValueError("Archived altitude classes disagree with launch altitude")
    missing = dates.isna().to_numpy() | band.isna().to_numpy()
    season = ((dates.dt.month - 1 - month_offset) % 12) // months
    key = cells[["epsg", "ix", "iy"]].copy()
    key["terrain"] = "all" if pool_terrain else band.astype("string")
    key["season"] = season
    labels = np.full(len(frame), -1, dtype=int)
    labels[~missing] = pd.factorize(
        pd.MultiIndex.from_frame(key.loc[~missing]), sort=True
    )[0]
    start = int(labels.max(initial=-1)) + 1
    labels[missing] = start + np.arange(missing.sum())
    return labels, missing


def group_composition(frame, labels, cohort):
    """Describe group sizes and years represented without claiming independence."""
    selected = frame.loc[np.asarray(cohort, dtype=bool), ["date"]].copy()
    selected["group"] = np.asarray(labels)[cohort]
    selected["year"] = pd.to_datetime(selected.date, errors="coerce").dt.year
    groups = selected.groupby("group")
    sizes = groups.size().to_numpy()
    years = groups.year.nunique().to_numpy()
    return {
        "groups": len(sizes),
        "flights": int(sizes.sum()),
        "singleton_groups": int(np.sum(sizes == 1)),
        "singleton_group_fraction": float(np.mean(sizes == 1)),
        "flights_in_singletons_fraction": float(np.sum(sizes == 1) / sizes.sum()),
        "flights_per_group_median": float(np.median(sizes)),
        "flights_per_group_p95": float(np.percentile(sizes, 95)),
        "largest_group_flights": int(sizes.max()),
        "largest_group_fraction": float(sizes.max() / sizes.sum()),
        "size_balance_index": float(
            sizes.sum() ** 2 / np.sum(sizes.astype(float) ** 2)
        ),
        "years_per_group_median": float(np.median(years)),
        "groups_with_multiple_years": int(np.sum(years > 1)),
    }
