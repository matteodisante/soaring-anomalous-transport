"""Within-segment origins for compact, possibly interrupted flight trajectories."""

from __future__ import annotations

import numpy as np


def segment_ranges(row, length):
    """Return half-open coordinate ranges, preserving every recording boundary."""
    return row.get("segments", [(0, length)])


def increment_starts(row, length, lag, *, order=1, stride=None):
    """Enumerate origins whose entire increment stencil stays inside one segment."""
    stride = lag if stride is None else stride
    if lag < 1 or order < 1 or stride < 1:
        raise ValueError("lag, order and stride must be positive")
    chunks = [
        np.arange(start, stop - order * lag, stride, dtype=np.int64)
        for start, stop in segment_ranges(row, length)
        if stop - start > order * lag
    ]
    return np.concatenate(chunks) if chunks else np.empty(0, dtype=np.int64)
