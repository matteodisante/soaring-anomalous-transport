"""Origin dependence of the increment law within fixed-cohort segments.

Stationary increments require the law of X(t+tau) - X(t) to be free of t. This
module splits each segment's admissible origins into three contiguous blocks of
equal size and measures the same amplitude statistics separately in each. The
early and late blocks always carry identical origin counts, so every flight
contributes to both and the contrast is paired within flights.

A resolved departure of the late/early ratio from one refutes increment
stationarity for these segments. It does not identify a mechanism: flight-phase
structure, evolving wind and pilot behaviour all produce origin dependence, and
none of them is the waiting-time ageing of a subordinated walk.
"""

from __future__ import annotations

import numpy as np

# Early, middle and late blocks of the admissible origins inside one segment.
BLOCKS = ("early", "middle", "late")
# Radial amplitude moments; both scale as a power of tau under self-similarity.
STATISTICS = ("m1", "m2")


def origin_blocks(count):
    """Split admissible origins into three contiguous blocks, balancing the ends.

    The early and late blocks receive floor(count/3) origins each. The remainder
    stays in the middle, which keeps the paired contrast exactly balanced at
    every lag. A segment with fewer than three admissible origins contributes
    nothing.
    """
    size = int(count) // 3
    if size < 1:
        return None
    return (0, size), (size, int(count) - size), (int(count) - size, int(count))


def segment_sums(positions, start, stop, lag):
    """Accumulate per-block origin counts, amplitude sums and mean origin times.

    Displacements never cross the segment boundary. Origin times are grid steps
    measured from the segment start, so the caller converts them with the grid.
    """
    count = stop - start - lag
    blocks = origin_blocks(count) if count > 0 else None
    if blocks is None:
        return None
    step = positions[start + lag : stop] - positions[start : stop - lag]
    radial = np.hypot(step[:, 0], step[:, 1])
    counts = np.empty(3)
    sums = np.empty((3, len(STATISTICS)))
    times = np.empty(3)
    for b, (a, z) in enumerate(blocks):
        part = radial[a:z]
        counts[b] = z - a
        sums[b, 0] = part.sum()
        sums[b, 1] = np.einsum("i,i->", part, part)
        times[b] = 0.5 * (a + z - 1)
    return counts, sums, times


def flight_statistics(positions, spans, lag):
    """Pool a flight's selected segments by origin count inside each block.

    Returns per-block means of the first and second radial moments, the origin
    counts behind them and the mean origin time in grid steps. Flights whose
    segments cannot supply three origins at this lag return no support.
    """
    counts = np.zeros(3)
    sums = np.zeros((3, len(STATISTICS)))
    weighted_times = np.zeros(3)
    for start, stop in spans:
        piece = segment_sums(positions, int(start), int(stop), int(lag))
        if piece is None:
            continue
        block_counts, block_sums, block_times = piece
        counts += block_counts
        sums += block_sums
        weighted_times += block_counts * block_times
    if counts.min() <= 0:
        return None
    return (
        sums / counts[:, None],
        counts,
        weighted_times / counts,
    )


def ratio_statistics(means):
    """Late-over-early ratios for every statistic, with one under stationarity.

    Means have shape (draw, block, statistic, lag) and the block axis follows
    BLOCKS. Ratios are formed inside each bootstrap replicate, which preserves
    the pairing between the two blocks of the same flights.
    """
    means = np.asarray(means, dtype=float)
    early = means[:, BLOCKS.index("early")]
    late = means[:, BLOCKS.index("late")]
    return np.divide(
        late,
        early,
        out=np.full_like(late, np.nan),
        where=np.isfinite(early) & (early > 0),
    )


def interval(samples, level=0.95):
    """Percentile interval from the replicate axis, with the observed row first."""
    samples = np.asarray(samples, dtype=float)
    tail = 0.5 * (1 - level)
    bounds = np.nanquantile(samples[1:], [tail, 1 - tail], axis=0)
    return {
        "point": samples[0],
        "lower": bounds[0],
        "upper": bounds[1],
        "excludes_one": (bounds[0] > 1) | (bounds[1] < 1),
    }
