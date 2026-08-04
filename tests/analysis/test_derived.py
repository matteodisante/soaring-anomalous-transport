"""Streaming the processed table back: a flight must arrive whole, or not at all."""

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from soaring.analysis.derived import stream_flights


def _table(n_flights=5, n_fix=600, segments=1):
    """Ballistic flights at 10 m/s, written in file order, one or more segments each."""
    frames = []
    for flight in range(n_flights):
        t = np.arange(float(n_fix))
        frames.append(
            pd.DataFrame(
                {
                    "flight_id": f"f{flight}",
                    "segment_id": (t // (n_fix / segments)).astype(int),
                    "t": t,
                    "E": 10.0 * t,
                    "N": np.zeros_like(t),
                }
            )
        )
    return pd.concat(frames, ignore_index=True)


def _write(tmp_path, frame, row_group_size):
    path = tmp_path / "fixes.parquet"
    pq.write_table(
        pa.Table.from_pandas(frame, preserve_index=False),
        path,
        row_group_size=row_group_size,
    )
    return path


@pytest.mark.parametrize("row_group_size", [17, 500, 599, 600, 601, 1000, 100_000])
def test_a_flight_arrives_whole_whatever_the_row_groups(tmp_path, row_group_size):
    # The bug this module exists for: a row group is a unit of storage, and the writer
    # chooses its size with no regard for where a flight ends. Reading row groups and
    # grouping by flight_id therefore yields *fragments*, and the archive's MSD counted
    # 157134 paraglider flights where 156017 were written. The reader's answer must not
    # depend on the row-group size at all.
    frame = _table()
    flights = list(stream_flights(_write(tmp_path, frame, row_group_size)))

    assert len(flights) == 5
    assert [f["flight_id"].iloc[0] for f in flights] == [f"f{i}" for i in range(5)]
    for flight in flights:
        assert len(flight) == 600
        assert flight["flight_id"].nunique() == 1
        # File order preserved, and the index restarts, so `.iloc[0]` is the first fix.
        assert flight["t"].to_numpy() == pytest.approx(np.arange(600.0))


def test_a_flight_larger_than_a_row_group_is_still_one_flight(tmp_path):
    # Held back across several boundaries in a row, not just one.
    path = _write(tmp_path, _table(n_flights=2, n_fix=1000), row_group_size=64)
    flights = list(stream_flights(path))
    assert [len(f) for f in flights] == [1000, 1000]


def test_the_time_averaged_msd_no_longer_loses_its_longest_lags(tmp_path):
    # What the defect cost, stated as the measurement it corrupted, by running the two
    # readers over the same file. A time average is taken *within* a segment and cut at
    # half its length, so truncating a 600-sample segment into 500 + 100 does two things
    # at once: it stops answering past lag 250 where the whole segment reaches 300, and
    # it lets the 100-sample stub answer the short lags a second time. The long-lag tail
    # thins and the short lags are counted twice -- and which flights it happens to is
    # decided by the writer's buffering, not by the data.
    from soaring.analysis.observables.transport import TAMSDAccumulator

    path = _write(tmp_path, _table(n_flights=3, n_fix=600), row_group_size=500)
    lags = np.array([40.0, 260.0])

    def accumulate(flights):
        accumulator = TAMSDAccumulator(lags)
        for flight in flights:
            accumulator.add(flight["E"].to_numpy(), flight["N"].to_numpy(), 1.0)
        return accumulator.result()

    def by_row_group():
        parquet = pq.ParquetFile(path)
        for group in range(parquet.metadata.num_row_groups):
            frame = parquet.read_row_group(group).to_pandas()
            for _, fragment in frame.groupby("flight_id", sort=False):
                yield fragment

    broken = accumulate(by_row_group())
    assert broken.n_flights.tolist() == [6, 0]  # counted twice, then lost entirely
    assert np.isnan(broken.msd[1])

    fixed = accumulate(stream_flights(path, ["segment_id", "t", "E", "N"]))
    assert fixed.n_flights.tolist() == [3, 3]
    assert fixed.msd == pytest.approx((10.0 * lags) ** 2)


def test_only_the_columns_asked_for_are_read_and_flight_id_always_is(tmp_path):
    path = _write(tmp_path, _table(n_flights=2), row_group_size=250)
    flight = next(stream_flights(path, ["t", "E"]))
    assert set(flight.columns) == {"flight_id", "t", "E"}


def test_a_flight_split_across_the_file_raises_instead_of_being_yielded_twice(tmp_path):
    # The contiguity the reader relies on is the writer's, and if it ever stopped
    # holding, silently emitting the same flight twice is exactly the failure being
    # fixed here. Better to stop.
    frame = _table(n_flights=2, n_fix=100)
    scrambled = pd.concat(
        [frame.iloc[:50], frame.iloc[100:], frame.iloc[50:100]], ignore_index=True
    )
    path = _write(tmp_path, scrambled, row_group_size=40)
    with pytest.raises(ValueError, match="not contiguous"):
        list(stream_flights(path))
