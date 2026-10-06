"""Where each cell window falls on a satellite's regular pixel grid."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pyproj

from soaring.acquisition.satellite.config import Cell, Config

LAMBERT93 = "EPSG:2154"


@dataclass(frozen=True)
class Axis:
    """Pixel-centre coordinates ``origin + index * step`` along one image axis.

    Attributes:
        origin: Coordinate of index 0, in projection metres.
        step: Signed pixel spacing, in projection metres.
        size: Number of pixels along the axis.
    """

    origin: float
    step: float
    size: int

    @classmethod
    def from_values(cls, values: np.ndarray) -> Axis:
        """Build an axis from its coordinate array, which must be evenly spaced."""
        values = np.asarray(values, dtype=float)
        step = (values[-1] - values[0]) / (len(values) - 1)
        expected = values[0] + step * np.arange(len(values))
        if not np.allclose(values, expected, rtol=0, atol=abs(step) * 1e-3):
            raise ValueError("Axis coordinates are not evenly spaced")
        return cls(float(values[0]), float(step), len(values))

    def index(self, coord: np.ndarray) -> np.ndarray:
        """Index of the pixel whose centre is nearest to each coordinate."""
        return np.rint((np.asarray(coord) - self.origin) / self.step).astype(int)

    def values(self, start: int, stop: int) -> np.ndarray:
        """Pixel-centre coordinates of indices ``start`` to ``stop - 1``."""
        return self.origin + self.step * np.arange(start, stop)


@dataclass(frozen=True)
class Box:
    """Pixel rectangle: rows ``[r0, r1)`` and columns ``[c0, c1)``."""

    r0: int
    r1: int
    c0: int
    c1: int


def window_outline(
    cfg: Config, cell: Cell, n: int = 41
) -> tuple[np.ndarray, np.ndarray]:
    """Longitude and latitude of points along the edge of the cell's crop window."""
    cx, cy = cfg.centre(cell)
    w = cfg.window
    west = cx - w.half_size_m - w.side_margin_m
    east = cx + w.half_size_m + w.side_margin_m
    south = cy - w.half_size_m
    north = cy + w.half_size_m + w.north_margin_m
    t = np.linspace(0.0, 1.0, n)
    xs = np.concatenate(
        [
            west + (east - west) * t,
            np.full(n, east),
            east - (east - west) * t,
            np.full(n, west),
        ]
    )
    ys = np.concatenate(
        [
            np.full(n, south),
            south + (north - south) * t,
            np.full(n, north),
            north - (north - south) * t,
        ]
    )
    to_lonlat = pyproj.Transformer.from_crs(LAMBERT93, "EPSG:4326", always_xy=True)
    lon, lat = to_lonlat.transform(xs, ys)
    return np.asarray(lon), np.asarray(lat)


def pixel_box(
    proj: pyproj.Proj, lon: np.ndarray, lat: np.ndarray, x: Axis, y: Axis
) -> Box:
    """Smallest pixel rectangle holding every point of a window outline.

    The outline of a small window maps to a convex quadrilateral on the image, so
    the rectangle spanning its extreme indices contains the whole window.
    """
    px, py = proj(lon, lat)
    cols, rows = x.index(px), y.index(py)
    return Box(
        int(rows.min()), int(rows.max()) + 1, int(cols.min()), int(cols.max()) + 1
    )
