"""Flights of a coordinate store grouped by take-off box, optionally within a cohort."""

from __future__ import annotations

import numpy as np


def region_labels(lon0, lat0, regions):
    """Name the first inclusive (west, east, south, north) box holding each take-off.

    Flights outside every box get ``None``. Boxes are tested in the order given.
    """
    lon0, lat0 = np.asarray(lon0, dtype=float), np.asarray(lat0, dtype=float)
    labels = np.full(len(lon0), None, dtype=object)
    for name, (west, east, south, north) in regions.items():
        inside = (
            (lon0 >= west)
            & (lon0 <= east)
            & (lat0 >= south)
            & (lat0 <= north)
            & (labels == None)  # noqa: E711 - elementwise on an object array
        )
        labels[inside] = name
    return labels


def takeoff_frames(coordinates, takeoffs, regions, members=None):
    """Yield (row, positions) for flights whose take-off lies in ``regions``.

    ``coordinates`` is a DiskFrames-like sequence and ``takeoffs`` a table with
    ``flight_id``, ``lon0`` and ``lat0`` in the same order. Each yielded row is a
    copy whose ``region`` is the take-off box. With ``members`` (a cohort manifest's
    member list) only those flights are yielded and their segments are the
    cohort's own, each of which must be a stored segment, so a fixed population
    keeps the same flights and the same segments at every lag.
    """
    if len(takeoffs) != len(coordinates):
        raise ValueError("Take-off table and coordinate store differ in length")
    labels = region_labels(takeoffs.lon0, takeoffs.lat0, regions)
    if members is None:
        chosen = [(int(i), None) for i in np.flatnonzero(labels != None)]  # noqa: E711
    else:
        chosen = [
            (m["frame_index"], m)
            for m in members
            if labels[m["frame_index"]] is not None
        ]
    for i, member in chosen:
        row, positions = coordinates[i]
        flight_id = str(takeoffs.flight_id.iloc[i])
        if str(row["flight_id"]) != flight_id:
            raise ValueError(f"Coordinate store and take-offs disagree at {i}")
        row = dict(row, region=labels[i])
        if member is not None:
            if member["flight_id"] != flight_id:
                raise ValueError(f"Cohort and take-offs disagree at {i}")
            segments = [(s["start"], s["stop"]) for s in member["segments"]]
            if not set(segments) <= {tuple(s) for s in row["segments"]}:
                raise ValueError(f"Cohort segment absent from the coordinates: {i}")
            row["segments"] = segments
        yield row, positions
