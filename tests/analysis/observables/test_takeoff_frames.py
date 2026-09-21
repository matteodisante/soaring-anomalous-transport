import numpy as np
import pandas as pd
import pytest

from soaring.analysis.observables.takeoff_frames import region_labels, takeoff_frames

BOXES = {"a": (0, 2, 0, 2), "b": (1, 3, 0, 2)}


class Store:
    def __init__(self):
        self.rows = [
            {"flight_id": str(i), "segments": [(0, 5), (5, 9)], "region": "old"}
            for i in range(4)
        ]

    def __len__(self):
        return 4

    def __getitem__(self, i):
        return self.rows[i], np.zeros((9, 2))


TAKEOFFS = pd.DataFrame(
    {"flight_id": list("0123"), "lon0": [0.5, 1.5, 2.5, 9.0], "lat0": [1, 1, 1, 1]}
)


def test_first_box_wins_and_outside_is_none():
    labels = region_labels(TAKEOFFS.lon0, TAKEOFFS.lat0, BOXES)
    assert list(labels) == ["a", "a", "b", None]


def test_all_flights_in_a_box_are_relabelled_without_touching_the_store():
    out = list(takeoff_frames(Store(), TAKEOFFS, BOXES))
    assert [row["region"] for row, _ in out] == ["a", "a", "b"]
    assert Store().rows[0]["region"] == "old"


def test_cohort_members_bring_their_own_segments():
    members = [
        {"flight_id": "1", "frame_index": 1, "segments": [{"start": 5, "stop": 9}]},
        {"flight_id": "3", "frame_index": 3, "segments": [{"start": 0, "stop": 5}]},
    ]
    out = list(takeoff_frames(Store(), TAKEOFFS, BOXES, members))
    assert [(r["flight_id"], r["segments"]) for r, _ in out] == [("1", [(5, 9)])]


def test_a_cohort_segment_missing_from_the_store_is_refused():
    members = [
        {"flight_id": "1", "frame_index": 1, "segments": [{"start": 0, "stop": 9}]}
    ]
    with pytest.raises(ValueError):
        list(takeoff_frames(Store(), TAKEOFFS, BOXES, members))
