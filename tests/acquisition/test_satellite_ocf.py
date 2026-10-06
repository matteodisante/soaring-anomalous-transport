"""Tests for decoding HRV shifts and assembling windows from Zarr chunks."""

import numpy as np

from soaring.acquisition.satellite.grid import Axis, Box
from soaring.acquisition.satellite.ocf import (
    _row_shift,
    _vlen_utf8,
    assemble,
    needed_chunks,
    to_physical,
)

X = Axis(-2709363.95, 1000.134, 5548)
Y = Axis(1395187.42, 1000.134, 4176)


def _coords(axis, origin, valid):
    values = np.full(axis.size, np.nan)
    values[valid] = origin + axis.step * np.arange(axis.size)[valid]
    return values


def test_row_shift_reads_the_origin_from_any_valid_column():
    valid = np.zeros(X.size, bool)
    valid[300:400] = valid[2000:2100] = True
    xr = _coords(X, X.origin + 25 * X.step, valid)
    yr = _coords(Y, Y.origin, np.arange(Y.size) > 2200)
    assert _row_shift(xr, yr, X, Y) == 25


def test_row_shift_rejects_missing_uneven_or_misplaced_rows():
    yr = _coords(Y, Y.origin, np.ones(Y.size, bool))
    assert np.isnan(_row_shift(np.full(X.size, np.nan), yr, X, Y))
    xr = _coords(X, X.origin, np.ones(X.size, bool))
    xr[10:] += 500.0
    assert np.isnan(_row_shift(xr, yr, X, Y))
    xr = _coords(X, X.origin, np.ones(X.size, bool))
    assert np.isnan(_row_shift(xr, yr + 3000.0, X, Y))


def _chunked(full, cy=100, cx=100):
    steps, ny, nx, nv = full.shape
    padded = np.full(
        (steps, -(-ny // cy) * cy, -(-nx // cx) * cx, nv), np.nan, np.float16
    )
    padded[:, :ny, :nx] = full
    calls = []

    def get(j, i):
        calls.append((j, i))
        return padded[:, j * cy : (j + 1) * cy, i * cx : (i + 1) * cx]

    return get, calls, (-(-ny // cy), -(-nx // cx))


def test_assemble_crosses_chunks_and_applies_shifts():
    rng = np.random.default_rng(0)
    full = rng.normal(size=(12, 250, 330, 2)).astype(np.float16)
    get, calls, n = _chunked(full)
    box = Box(95, 130, 190, 215)
    shifts = np.zeros(12)
    shifts[3], shifts[4] = 5, np.nan
    steps = np.array([0, 3, 4])
    out = assemble(get, box, steps, shifts, (100, 100), n, 2)
    np.testing.assert_array_equal(out[0], full[0, 95:130, 190:215])
    np.testing.assert_array_equal(out[1], full[3, 95:130, 185:210])
    assert np.isnan(out[2].astype(float)).all()
    assert set(calls) == needed_chunks(box, shifts, steps, (100, 100), n)


def test_assemble_leaves_missing_chunks_as_nan():
    full = np.ones((12, 250, 330, 1), np.float16)
    get, _, n = _chunked(full)
    out = assemble(
        lambda j, i: None if i == 2 else get(j, i),
        Box(0, 10, 195, 205),
        np.array([0]),
        np.zeros(12),
        (100, 100),
        n,
        1,
    )
    assert (out[0, :, :5] == 1).all() and np.isnan(out[0, :, 5:].astype(float)).all()


def test_to_physical_inverts_the_ocf_scaling():
    out = to_physical(np.array([[0.0, 1.0], [0.5, 0.5]]), ("IR_108", "VIS006"))
    np.testing.assert_allclose(out[0], [199.10002, 93.786545], rtol=1e-6)
    np.testing.assert_allclose(out[1, 0], (199.10002 + 313.2767) / 2, rtol=1e-6)


def test_vlen_utf8_decodes_channel_names():
    items = [b"HRV", b"IR_108"]
    buf = len(items).to_bytes(4, "little") + b"".join(
        len(b).to_bytes(4, "little") + b for b in items
    )
    assert _vlen_utf8(buf).tolist() == ["HRV", "IR_108"]
