"""The retention report must account for every admitted or rejected flight."""

from pathlib import Path
import runpy

import pandas as pd
import pytest


REPORT = runpy.run_path(
    str(
        Path(__file__).resolve().parents[2]
        / "scripts/reporting/ch2_dataset/generate_dataset_stats.py"
    )
)


def test_altitude_admission_precedes_later_cuts_and_counts_reconcile():
    # Ten flights: one unreadable, two fail altitude admission, one fails
    # trimming, three fail resampling, and three remain. Input order is arbitrary.
    meta = pd.DataFrame(
        {
            "drop_reason": [
                None,
                "no_segment_survived",
                "no_usable_altitude_channel",
                "fewer_than_two_fixes",
                "no_segment_survived",
                None,
                "no_sustained_flight",
                "no_usable_altitude_channel",
                None,
                "no_segment_survived",
            ]
        }
    )
    table = REPORT["cascade"](meta)
    assert table.reason.tolist() == [
        "fewer_than_two_fixes",
        "no_usable_altitude_channel",
        "no_sustained_flight",
        "no_segment_survived",
    ]
    assert table.standing.tolist() == [10, 9, 7, 6]
    assert table.removed.tolist() == [1, 2, 1, 3]
    assert table.remaining.tolist() == [9, 7, 6, 3]
    assert table.share_of_standing.tolist() == pytest.approx([10, 200 / 9, 100 / 7, 50])
    assert table.removed.sum() + table.remaining.iloc[-1] == len(meta)


def test_unmapped_failure_cannot_silently_disappear_from_the_cascade():
    meta = pd.DataFrame({"drop_reason": [None, "unmapped_recorder_failure"]})
    with pytest.raises(ValueError, match="unmapped_recorder_failure"):
        REPORT["cascade"](meta)
