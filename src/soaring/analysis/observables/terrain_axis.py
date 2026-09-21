"""Orientation of the high-terrain footprint inside a geographic box."""

from __future__ import annotations

from itertools import pairwise

import numpy as np

from ..preproc.enu import geodetic_to_enu


def footprint_axis(lon, lat, elevation, box, threshold_m):
    """Long axis of the elevation cells at or above ``threshold_m`` inside ``box``.

    ``lon``, ``lat`` and ``elevation`` are equally shaped grids and ``box`` is
    (west, east, south, north), inclusive. Cell centres go to local East/North
    metres tangent at the box centre, at zero height, and carry the weight
    cos(latitude) as an approximate relative area. The axis is the larger
    eigenvector of the weighted covariance, counterclockwise from east modulo 180
    degrees; ``ratio`` is the larger over the smaller eigenvalue. Elevation above
    the threshold adds no weight.
    """
    west, east, south, north = box
    chosen = (
        (lon >= west)
        & (lon <= east)
        & (lat >= south)
        & (lat <= north)
        & np.isfinite(elevation)
        & (elevation >= threshold_m)
    )
    if chosen.sum() < 3:
        raise ValueError("Too few terrain cells above the threshold")
    e, n, _ = geodetic_to_enu(
        lat[chosen],
        lon[chosen],
        np.zeros(chosen.sum()),
        (north + south) / 2,
        (west + east) / 2,
        0,
    )
    xy = np.column_stack((e, n)) / 1000
    weights = np.cos(np.deg2rad(lat[chosen]))
    mean = np.average(xy, axis=0, weights=weights)
    centred = xy - mean
    covariance = (centred * weights[:, None]).T @ centred / weights.sum()
    values, vectors = np.linalg.eigh(covariance)
    if values[0] <= 0:
        raise ValueError("The terrain footprint is degenerate")
    axis = vectors[:, -1]
    return {
        "angle_deg": float(np.degrees(np.arctan2(axis[1], axis[0])) % 180),
        "ratio": float(values[-1] / values[0]),
        "centre_km": mean.tolist(),
        "cells": int(chosen.sum()),
    }


# Rules fixed before any flight was compared with a terrain axis. A box qualifies
# when its crest footprint is a substantial, elongated, straight band whose axis
# survives a change of elevation threshold and small shifts of the box edges.
BOX_RULES = {
    "primary_threshold_m": 2000,
    "sensitivity_thresholds_m": (1500, 2500),
    "min_cells": 400,
    "min_ratio": 2.5,
    "max_threshold_spread_deg": 10.0,
    "edge_shift_deg": 0.2,
    "max_edge_spread_deg": 10.0,
    "max_bend_deg": 10.0,
    "min_side_deg": 0.8,
    "min_area_deg2": 1.5,
    "grid_step_deg": 0.2,
}


def axis_spread(angles):
    """Largest deviation of undirected axes from their circular mean, in degrees."""
    doubled = np.deg2rad(2 * np.asarray(angles, dtype=float))
    mean = np.degrees(np.arctan2(np.sin(doubled).mean(), np.cos(doubled).mean())) / 2
    return float(max(abs((a - mean + 90) % 180 - 90) for a in angles))


def chain_bend(lon, lat, elevation, box, threshold_m):
    """Change of direction of the footprint along its own long axis, in degrees.

    The footprint is cut into thirds of equal cell count along the long axis. The
    bend is the angle between the segment joining the first two third-centroids
    and the one joining the last two: zero for a straight band, large for a chain
    that turns inside the box.
    """
    west, east, south, north = box
    chosen = (
        (lon >= west)
        & (lon <= east)
        & (lat >= south)
        & (lat <= north)
        & np.isfinite(elevation)
        & (elevation >= threshold_m)
    )
    e, n, _ = geodetic_to_enu(
        lat[chosen],
        lon[chosen],
        np.zeros(chosen.sum()),
        (north + south) / 2,
        (west + east) / 2,
        0,
    )
    xy = np.column_stack((e, n)) / 1000
    weights = np.cos(np.deg2rad(lat[chosen]))
    centred = xy - np.average(xy, axis=0, weights=weights)
    covariance = (centred * weights[:, None]).T @ centred / weights.sum()
    axis = np.linalg.eigh(covariance)[1][:, -1]
    along = centred @ axis
    across = centred @ np.array([-axis[1], axis[0]])
    cuts = np.quantile(along, [0, 1 / 3, 2 / 3, 1])
    centroids = []
    for lo, hi in pairwise(cuts):
        part = (along >= lo) & (along <= hi)
        centroids.append(
            (
                np.average(along[part], weights=weights[part]),
                np.average(across[part], weights=weights[part]),
            )
        )
    first = np.subtract(centroids[1], centroids[0])
    second = np.subtract(centroids[2], centroids[1])
    cross = first[0] * second[1] - first[1] * second[0]
    return float(abs(np.degrees(np.arctan2(cross, first @ second))))


def box_reliability(lon, lat, elevation, box, rules=BOX_RULES):
    """Terrain-only reliability of one box, or ``None`` when it fails a rule.

    Returns the primary axis with its elongation, the spread of the axis across
    the sensitivity thresholds and across edge shifts, and the chain bend.
    """
    primary = rules["primary_threshold_m"]
    try:
        main = footprint_axis(lon, lat, elevation, box, primary)
    except ValueError:
        return None
    if main["cells"] < rules["min_cells"] or main["ratio"] < rules["min_ratio"]:
        return None
    angles = [main["angle_deg"]]
    for threshold in rules["sensitivity_thresholds_m"]:
        try:
            angles.append(
                footprint_axis(lon, lat, elevation, box, threshold)["angle_deg"]
            )
        except ValueError:
            return None
    threshold_spread = axis_spread(angles)
    if threshold_spread > rules["max_threshold_spread_deg"]:
        return None
    bend = chain_bend(lon, lat, elevation, box, primary)
    if bend > rules["max_bend_deg"]:
        return None
    shifted = [main["angle_deg"]]
    shift = rules["edge_shift_deg"]
    for edge in range(4):
        for delta in (-shift, shift):
            moved = list(box)
            moved[edge] += delta
            if (
                moved[1] - moved[0] < rules["min_side_deg"] / 2
                or moved[3] - moved[2] < rules["min_side_deg"] / 2
            ):
                continue
            try:
                shifted.append(
                    footprint_axis(lon, lat, elevation, tuple(moved), primary)[
                        "angle_deg"
                    ]
                )
            except ValueError:
                return None
    edge_spread = axis_spread(shifted)
    if edge_spread > rules["max_edge_spread_deg"]:
        return None
    return {
        "box": tuple(float(v) for v in box),
        "angle_deg": main["angle_deg"],
        "ratio": main["ratio"],
        "cells": main["cells"],
        "centre_km": main["centre_km"],
        "threshold_angles_deg": {
            str(t): a
            for t, a in zip(
                (primary, *rules["sensitivity_thresholds_m"]), angles, strict=True
            )
        },
        "threshold_spread_deg": threshold_spread,
        "edge_spread_deg": edge_spread,
        "bend_deg": bend,
        "area_deg2": float((box[1] - box[0]) * (box[3] - box[2])),
    }


def select_boxes(lon, lat, elevation, domain, *, supported=None, rules=BOX_RULES):
    """Disjoint boxes inside ``domain`` whose terrain direction can be estimated.

    Every rectangle on a regular grid of edges that meets the size rules and
    ``box_reliability`` is a candidate, and ``supported(box)`` may add a data-count
    requirement that does not involve any direction. Candidates are ranked by the
    largest of their three instabilities (threshold spread, edge spread, bend),
    then by area, and taken greedily when they share no area with a chosen box.
    """
    west, east, south, north = domain
    step = rules["grid_step_deg"]
    xs = np.round(np.arange(west, east + step / 2, step), 6)
    ys = np.round(np.arange(south, north + step / 2, step), 6)
    found = []
    for w in xs:
        for e in xs[xs >= w + rules["min_side_deg"] - 1e-9]:
            for s in ys:
                for n in ys[ys >= s + rules["min_side_deg"] - 1e-9]:
                    if (e - w) * (n - s) < rules["min_area_deg2"] - 1e-9:
                        continue
                    box = (float(w), float(e), float(s), float(n))
                    if supported is not None and not supported(box):
                        continue
                    record = box_reliability(lon, lat, elevation, box, rules)
                    if record is not None:
                        found.append(record)

    def instability(record):
        return max(
            record["threshold_spread_deg"],
            record["edge_spread_deg"],
            record["bend_deg"],
        )

    chosen = []
    for record in sorted(
        found, key=lambda r: (instability(r), -r["area_deg2"], r["box"])
    ):
        a = record["box"]
        if any(
            min(a[1], b["box"][1]) > max(a[0], b["box"][0]) + 1e-9
            and min(a[3], b["box"][3]) > max(a[2], b["box"][2]) + 1e-9
            for b in chosen
        ):
            continue
        chosen.append(record)
    return sorted(chosen, key=lambda r: r["box"])
