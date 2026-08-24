"""Reading the processed tables back: whole flights, out of a file read in pieces.

``scripts/preprocess.py`` writes ``fixes.parquet`` one batch of flights at a time, and
the table is far too large to load (~10^9 rows over the full archive), so every
consumer streams it. Streaming a Parquet file means reading it row group by row group --
and a row group is a unit of *storage*, chosen by the writer's buffering, with no
relation to where one flight ends and the next begins.

That distinction is the reason this module exists. Reading a row group and grouping its
rows by ``flight_id`` looks like it iterates over flights, and does, right up to the
flight that happens to straddle the boundary: that one arrives as two fragments, in two
different row groups, and is processed as two flights. The consequences are not
cosmetic. The ensemble MSD counted 157134 paraglider flights where the pipeline had then
written 156017 (the archive holds 155788 today); the time-averaged MSD, which is computed *within* a segment, lost
every pair of samples spanning a boundary and every lag longer than the truncated
fragment, so the longest segments -- the ones that carry the long-lag tail, and the ones
most likely to straddle -- were the ones cut short; and the dataset verifier never
checked the step across a boundary, which is a hole in precisely the invariant it
reports as holding. All three followed from one sentence written as an assumption and
never tested: *the writer puts whole flights in a row group, so a flight is never split
across two*. PyArrow splits a written table into row groups of its own default size, and
pays no attention to what the caller batched.

:func:`stream_flights` is the correct reader, and there is one of it so that a consumer
cannot get this wrong again. It holds back the rows of the last flight in each row group
and prepends them to the next, so what it yields is always a whole flight.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import numpy as np
import pandas as pd


def stream_flights(
    path: Path | str, columns: list[str] | None = None
) -> Iterator[pd.DataFrame]:
    """Yield one whole flight at a time from a ``fixes.parquet``.

    Memory stays bounded by one row group plus one flight, whatever the size of the
    file. The rows of a flight are contiguous in the file -- the writer concatenates
    whole flights in order -- so a flight can straddle at most one boundary at a time,
    and holding back the last one is enough to reassemble it. That contiguity is not
    merely assumed: a flight_id that reappears after its rows have been yielded raises,
    because silently yielding it twice is the failure this module exists to prevent.

    Args:
        path: The ``fixes.parquet`` to read.
        columns: Columns to read, or ``None`` for all of them. ``flight_id`` is always
            read, whether or not it is asked for, since it is what delimits a flight.

    Yields:
        One ``DataFrame`` per flight, with the file's row order preserved. The frames
        carry a fresh ``RangeIndex``, so a caller may position into them without having
        to reason about where in the file they came from.

    Raises:
        ValueError: If a flight's rows are not contiguous in the file, which would mean
            the writer's ordering guarantee no longer holds.
    """
    import pyarrow.parquet as pq

    if columns is not None and "flight_id" not in columns:
        columns = ["flight_id", *columns]

    parquet = pq.ParquetFile(path)
    finished: set[str] = set()
    carry: pd.DataFrame | None = None

    def emit(frame: pd.DataFrame) -> Iterator[pd.DataFrame]:
        for flight_id, flight in frame.groupby("flight_id", sort=False):
            key = str(flight_id)
            if key in finished:
                raise ValueError(
                    f"flight {key} appears in two separate places in {path}: its rows "
                    "are not contiguous, so streaming cannot reassemble it."
                )
            finished.add(key)
            yield flight.reset_index(drop=True)

    for group in range(parquet.metadata.num_row_groups):
        frame = parquet.read_row_group(group, columns=columns).to_pandas()
        if frame.empty:
            continue
        if carry is not None:
            frame = pd.concat([carry, frame], ignore_index=True)
        # The last flight of a row group may continue in the next one. Every other flight
        # in it is complete and can go out now. What is held back is the trailing *run*,
        # not every row carrying that flight_id: selecting by id would splice together a
        # flight that appears twice in one row group, which is the discontiguity this
        # reader exists to refuse rather than to repair. Held back as a run, the earlier
        # block goes out through `emit` and the later one meets it in `finished`.
        ids = frame["flight_id"].to_numpy()
        changes = np.flatnonzero(ids[1:] != ids[:-1])
        start = int(changes[-1]) + 1 if changes.size else 0
        carry = frame.iloc[start:].reset_index(drop=True)
        yield from emit(frame.iloc[:start])

    if carry is not None and not carry.empty:
        yield from emit(carry)
