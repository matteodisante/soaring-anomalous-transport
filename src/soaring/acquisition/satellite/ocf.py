"""Open Climate Fix copy of the SEVIRI rapid-scan archive, read chunk by chunk.

The public bucket holds one Zarr v2 store per year and kind: ``nonhrv`` (11
channels on the 3 km grid) and ``hrv`` (the 1 km visible channel). Data chunks
are 12 time steps (one hour) x 100 x 100 pixels x all channels, compressed with
blosc2. We decode only the chunks that hold a cell window, without zarr or
xarray, so a year costs ~22 GB of traffic instead of ~4.4 TB.

The HRV image is not fixed on the grid: EUMETSAT moves the HRV window east or
west between scans, by up to ~50 pixels. The store records, for each time step,
the coordinates of the columns it holds; :meth:`OcfStore.hrv_shifts` turns them
into a whole-column shift per time step against the store's static axis.

Values are not physical: OCF stored ``clip((v - min) / (max - min), 0, 1)`` with
fixed per-channel bounds (:data:`SCALING`); :func:`to_physical` undoes it.
"""

from __future__ import annotations

import json
import threading
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass

import blosc2
import numpy as np
import pyproj
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from soaring.acquisition.satellite.grid import Axis, Box

BUCKET = (
    "https://storage.googleapis.com/public-datasets-eumetsat-solar-forecasting"
    "/satellite/EUMETSAT/SEVIRI_RSS/v4"
)
FIRST_YEAR, LAST_YEAR = 2008, 2022

# Geostationary projection of every store (area definitions msg_seviri_rss_*km).
SEVIRI_RSS = pyproj.Proj(
    proj="geos", h=35785831.0, lon_0=9.5, a=6378169.0, rf=295.488065897014, sweep="y"
)

# (min, max) used by OCF to scale each channel to [0, 1]: SCALER_MINS/SCALER_MAXS
# and HRV_SCALER_MIN/MAX in openclimatefix/Satip, satip/constants.py. Checked on
# 2020-07-25: they give 230-300 K brightness temperatures and 2-63 % reflectances.
SCALING = {
    "HRV": (-1.2278595, 103.90016),
    "IR_016": (-2.5118103, 69.60857),
    "IR_039": (-64.83977, 339.15588),
    "IR_087": (63.404694, 340.26526),
    "IR_097": (2.844452, 317.86752),
    "IR_108": (199.10002, 313.2767),
    "IR_120": (-17.254883, 315.99194),
    "IR_134": (-26.29155, 274.82297),
    "VIS006": (-1.1009827, 93.786545),
    "VIS008": (-2.4184198, 101.34922),
    "WV_062": (199.57048, 249.91806),
    "WV_073": (198.95093, 286.96323),
}


def to_physical(values: np.ndarray, variables: tuple[str, ...]) -> np.ndarray:
    """Undo OCF's scaling: ``%`` reflectance or ``K`` brightness temperature.

    ``values`` has the channels along its last axis, in the order of ``variables``.
    Values OCF clipped at 0 or 1 come back as the bound, not the true value.
    """
    lo, hi = np.array([SCALING[v] for v in variables]).T
    return lo + np.asarray(values, dtype=np.float32) * (hi - lo)


class Fetcher:
    """HTTP GETs with retries, safe to share between threads, counting bytes."""

    def __init__(self, workers: int = 16, timeout_s: float = 60.0) -> None:
        """Open a session sized for ``workers`` parallel requests."""
        retry = Retry(
            total=8, backoff_factor=1.0, status_forcelist=(429, 500, 502, 503, 504)
        )
        adapter = HTTPAdapter(max_retries=retry, pool_maxsize=workers)
        self._session = requests.Session()
        self._session.mount("https://", adapter)
        self._timeout = timeout_s
        self._lock = threading.Lock()
        self.bytes = 0
        self.requests = 0

    def get(self, url: str) -> bytes | None:
        """Body of ``url``, or ``None`` when the object does not exist."""
        response = self._session.get(url, timeout=self._timeout)
        if response.status_code == 404:
            return None
        response.raise_for_status()
        with self._lock:
            self.bytes += len(response.content)
            self.requests += 1
        return response.content


@dataclass(frozen=True)
class _ArrayMeta:
    shape: tuple[int, ...]
    chunks: tuple[int, ...]
    dtype: np.dtype


class OcfStore:
    """One year and kind of the archive, with its time steps and static axes.

    Attributes:
        url: Store root.
        kind: ``"nonhrv"`` or ``"hrv"``.
        time: UTC time of every step, ``datetime64[ns]``.
        x: Static column axis (geostationary metres, increasing eastwards).
        y: Static row axis (geostationary metres, increasing northwards).
        variables: Channel names, in the order of the last data dimension.
        units: Unit of each channel: ``%`` reflectance or ``K`` brightness temperature.
        chunk_yx: Spatial chunk size, ``(rows, columns)``.
    """

    def __init__(
        self, year: int, kind: str, fetcher: Fetcher, workers: int = 16
    ) -> None:
        """Read the store's metadata, time steps, axes and channel names."""
        if not FIRST_YEAR <= year <= LAST_YEAR:
            raise ValueError(
                f"The OCF archive covers {FIRST_YEAR}-{LAST_YEAR}, not {year}"
            )
        if kind not in ("nonhrv", "hrv"):
            raise ValueError(f"Unknown kind {kind!r}")
        self.url = f"{BUCKET}/{year}_{kind}.zarr"
        self.kind = kind
        self._fetcher = fetcher
        self._workers = workers
        raw = fetcher.get(f"{self.url}/.zmetadata")
        if raw is None:
            raise FileNotFoundError(f"{self.url} has no consolidated metadata")
        self._meta = json.loads(raw)["metadata"]
        self._data = self._array_meta("data")
        self.time = self._read_1d("time").astype("datetime64[ns]")
        self.x = Axis.from_values(self._read_1d("x_geostationary"))
        self.y = Axis.from_values(self._read_1d("y_geostationary"))
        self.variables = tuple(str(v) for v in self._read_1d("variable"))
        attrs = self._meta["data/.zattrs"]
        self.units = {v: attrs.get(f"{v}_units") for v in self.variables}
        self.chunk_yx = (self._data.chunks[1], self._data.chunks[2])

    def _array_meta(self, name: str) -> _ArrayMeta:
        zarray = self._meta[f"{name}/.zarray"]
        return _ArrayMeta(
            tuple(zarray["shape"]), tuple(zarray["chunks"]), np.dtype(zarray["dtype"])
        )

    def _chunk(self, name: str, key: str, meta: _ArrayMeta) -> np.ndarray | None:
        raw = self._fetcher.get(f"{self.url}/{name}/{key}")
        if raw is None:
            return None
        buf = blosc2.decompress(raw)
        if meta.dtype.kind == "O":  # numcodecs vlen-utf8, e.g. 2009 HRV channel names
            return _vlen_utf8(buf).reshape(meta.chunks)
        return np.frombuffer(buf, dtype=meta.dtype).reshape(meta.chunks)

    def _read_1d(self, name: str) -> np.ndarray:
        # Some stores split a 1-D array into thousands of tiny chunks (2009 HRV
        # time: 7048 chunks of 12), so read them in parallel.
        meta = self._array_meta(name)
        n = -(-meta.shape[0] // meta.chunks[0])
        with ThreadPoolExecutor(self._workers) as pool:
            parts = list(pool.map(lambda k: self._chunk(name, str(k), meta), range(n)))
        missing = [k for k, part in enumerate(parts) if part is None]
        if missing:
            raise FileNotFoundError(f"{self.url}/{name}: chunks {missing[:5]} missing")
        return np.concatenate(parts)[: meta.shape[0]]

    @property
    def n_chunks_yx(self) -> tuple[int, int]:
        """Number of spatial chunks along rows and columns."""
        return (
            -(-self._data.shape[1] // self.chunk_yx[0]),
            -(-self._data.shape[2] // self.chunk_yx[1]),
        )

    def data_chunk(self, t: int, j: int, i: int) -> np.ndarray | None:
        """Chunk ``(t, j, i)`` as ``(12, rows, cols, channels)``; None if absent."""
        return self._chunk("data", f"{t}.{j}.{i}.0", self._data)

    def hrv_shifts(self, t: int) -> np.ndarray:
        """Column shift of each time step of chunk ``t`` against the static axis.

        Data column ``c`` of a step with shift ``s`` lies at static column ``c + s``.
        Steps whose recorded coordinates are missing, uneven or off the static row
        axis get NaN, and are dropped rather than guessed.
        """
        steps = self._data.chunks[0]
        if self.kind != "hrv":
            return np.zeros(steps)
        xs = self._chunk(
            "x_geostationary_coordinates",
            f"{t}.0",
            self._array_meta("x_geostationary_coordinates"),
        )
        ys = self._chunk(
            "y_geostationary_coordinates",
            f"{t}.0",
            self._array_meta("y_geostationary_coordinates"),
        )
        if xs is None or ys is None:
            return np.full(steps, np.nan)
        return np.array(
            [_row_shift(xr, yr, self.x, self.y) for xr, yr in zip(xs, ys, strict=True)]
        )


def _vlen_utf8(buf: bytes) -> np.ndarray:
    """Decode numcodecs vlen-utf8: a uint32 count, then (uint32 size, bytes) items."""
    n, pos, items = int.from_bytes(buf[:4], "little"), 4, []
    for _ in range(n):
        size = int.from_bytes(buf[pos : pos + 4], "little")
        items.append(buf[pos + 4 : pos + 4 + size].decode())
        pos += 4 + size
    return np.array(items, dtype=object)


def _row_shift(xr: np.ndarray, yr: np.ndarray, x: Axis, y: Axis) -> float:
    """Whole-column shift implied by one time step's recorded coordinates."""
    cols, rows = np.flatnonzero(np.isfinite(xr)), np.flatnonzero(np.isfinite(yr))
    if len(cols) == 0 or len(rows) == 0:
        return np.nan
    x_origin = xr[cols] - x.step * cols
    y_origin = yr[rows] - y.step * rows
    tol = abs(x.step) * 0.01
    if (
        np.ptp(x_origin) > tol
        or np.ptp(y_origin) > tol
        or abs(y_origin[0] - y.origin) > tol
    ):
        return np.nan
    shift = (x_origin[0] - x.origin) / x.step
    return float(round(shift)) if abs(shift - round(shift)) < 0.01 else np.nan


def assemble(
    get_chunk: Callable[[int, int], np.ndarray | None],
    box: Box,
    steps: np.ndarray,
    shifts: np.ndarray,
    chunk_yx: tuple[int, int],
    n_chunks_yx: tuple[int, int],
    n_channels: int,
) -> np.ndarray:
    """Cut ``box`` (static-grid pixels) out of one time chunk, for the given steps.

    Args:
        get_chunk: Returns spatial chunk ``(j, i)`` of the time chunk, or ``None``.
        box: Rows and columns on the static grid.
        steps: Step indices within the time chunk to keep.
        shifts: Column shift of every step of the time chunk (NaN: unusable).
        chunk_yx: Spatial chunk size.
        n_chunks_yx: Number of spatial chunks along each axis.
        n_channels: Channels per pixel.

    Returns:
        ``(len(steps), rows, cols, channels)`` float16, NaN where nothing was read.
    """
    cy, cx = chunk_yx
    out = np.full(
        (len(steps), box.r1 - box.r0, box.c1 - box.c0, n_channels),
        np.nan,
        dtype=np.float16,
    )
    for k, step in enumerate(steps):
        if not np.isfinite(shifts[step]):
            continue
        c0, c1 = box.c0 - int(shifts[step]), box.c1 - int(shifts[step])
        for j in range(box.r0 // cy, (box.r1 - 1) // cy + 1):
            for i in range(c0 // cx, (c1 - 1) // cx + 1):
                if not (0 <= j < n_chunks_yx[0] and 0 <= i < n_chunks_yx[1]):
                    continue
                chunk = get_chunk(j, i)
                if chunk is None:
                    continue
                r_lo, r_hi = max(box.r0, j * cy), min(box.r1, (j + 1) * cy)
                c_lo, c_hi = max(c0, i * cx), min(c1, (i + 1) * cx)
                out[k, r_lo - box.r0 : r_hi - box.r0, c_lo - c0 : c_hi - c0] = chunk[
                    step, r_lo - j * cy : r_hi - j * cy, c_lo - i * cx : c_hi - i * cx
                ]
    return out


def needed_chunks(
    box: Box,
    shifts: np.ndarray,
    steps: np.ndarray,
    chunk_yx: tuple[int, int],
    n_chunks_yx: tuple[int, int],
) -> set[tuple[int, int]]:
    """Spatial chunks that :func:`assemble` will read for these steps."""
    cy, cx = chunk_yx
    keys = set()
    for step in steps:
        if not np.isfinite(shifts[step]):
            continue
        c0, c1 = box.c0 - int(shifts[step]), box.c1 - int(shifts[step])
        for j in range(box.r0 // cy, (box.r1 - 1) // cy + 1):
            for i in range(c0 // cx, (c1 - 1) // cx + 1):
                if 0 <= j < n_chunks_yx[0] and 0 <= i < n_chunks_yx[1]:
                    keys.add((j, i))
    return keys
