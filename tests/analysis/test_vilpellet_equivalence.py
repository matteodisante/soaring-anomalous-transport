"""The port must compute exactly what Vilpellet's own code computes.

Every quantity is compared for bitwise equality, not approximate agreement. A
transcription that agrees to eight decimals is a transcription with a bug in it: the
two implementations perform the same float64 operations in the same order, so any
difference at all means one of them departed from the other.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

import vilpellet_reference as reference

from soaring.analysis.segmentation.vilpellet import (
    build_observation_frame,
    load_vilpellet_config,
    observation_matrix,
    rolling_majority,
    viterbi,
)

CONFIG = load_vilpellet_config()
ALPHA = CONFIG.alpha_for("paragliders")
LAT0, LON0 = 45.9, 6.4
_M_PER_DEG_LAT = 111_320.0
_M_PER_DEG_LON = _M_PER_DEG_LAT * np.cos(np.radians(LAT0))

ARCHIVE = Path("/Volumes/SSD_DISANTE/paragliders/ffvl_cfd_igc/raw/igc/2021-2022")


def _synthetic_track() -> pd.DataFrame:
    """A 1 Hz flight of straight legs, spiral climbs and a reversed turn.

    The reversal matters: it is the only part of the track that separates the
    persistent-turn-sign feature from plain "is turning", so a transcription error in
    the order-statistic selection shows up here and nowhere else.
    """
    parts: list[tuple[np.ndarray, np.ndarray, np.ndarray]] = []
    east = north = 0.0
    alt = 1200.0

    def leg(seconds: int, speed: float, heading: float, climb: float):
        nonlocal east, north, alt
        step = np.arange(1, seconds + 1, dtype=float)
        e = east + speed * np.cos(heading) * step
        n = north + speed * np.sin(heading) * step
        z = alt + climb * step
        east, north, alt = e[-1], n[-1], z[-1]
        parts.append((e, n, z))

    def spiral(seconds: int, radius: float, period: float, climb: float, sense: float):
        nonlocal east, north, alt
        step = np.arange(1, seconds + 1, dtype=float)
        angle = sense * 2.0 * np.pi * step / period
        e = east + radius * (np.cos(angle) - 1.0)
        n = north + radius * np.sin(angle) * sense
        z = alt + climb * step
        east, north, alt = e[-1], n[-1], z[-1]
        parts.append((e, n, z))

    leg(420, 11.0, 0.3, -1.1)
    spiral(480, 55.0, 26.0, 1.6, +1.0)
    leg(360, 11.5, 1.2, -1.0)
    spiral(300, 48.0, 25.0, 1.4, -1.0)
    leg(300, 10.0, 2.0, -0.9)
    # Alternating senses inside one persistence window: turning, but not persistently
    # one way, which is what separates search from climb.
    for index in range(10):
        spiral(24, 40.0, 24.0, 0.1, 1.0 if index % 2 == 0 else -1.0)
    leg(420, 12.0, 2.6, -1.2)

    e = np.concatenate([p[0] for p in parts])
    n = np.concatenate([p[1] for p in parts])
    z = np.concatenate([p[2] for p in parts])
    t = np.arange(e.size, dtype=float)
    return pd.DataFrame(
        {
            "t": t,
            "lat": LAT0 + n / _M_PER_DEG_LAT,
            "lon": LON0 + e / _M_PER_DEG_LON,
            "alt": z,
        }
    )


def _compare(track: pd.DataFrame) -> None:
    """Run both implementations over one track and demand bitwise equality."""
    reference_frame, reference_obs = reference.get_regime(
        pd.DataFrame(
            {
                "time": track["t"].to_numpy(dtype=float),
                "Lat": track["lat"].to_numpy(dtype=float),
                "Long": track["lon"].to_numpy(dtype=float),
                "AltGNSS": track["alt"].to_numpy(dtype=float),
            }
        ),
        "paraglide",
    )
    frame = build_observation_frame(track, CONFIG, alpha_straight_rad=ALPHA)
    observations = observation_matrix(frame)
    path = viterbi(observations, CONFIG.parameters)
    smoothed = rolling_majority(pd.Series(path), CONFIG.majority_fixes).to_numpy()

    for reference_column, ported_column in (
        ("x", "x"),
        ("y", "y"),
        ("z", "z_enu"),
        ("radius_curvature_lat_long_sgn", "turn_increment_rad"),
        ("vertical_speed", "v_z"),
    ):
        left = reference_frame[reference_column].to_numpy(dtype=float)
        right = frame[ported_column].to_numpy(dtype=float)
        assert np.array_equal(np.isnan(left), np.isnan(right)), (
            f"{ported_column}: the two implementations leave different fixes undefined"
        )
        finite = ~np.isnan(left)
        assert np.array_equal(left[finite], right[finite]), (
            f"{ported_column}: values differ from the reference implementation"
        )

    assert np.array_equal(reference_obs, observations), (
        "the three binary features differ from the reference implementation"
    )
    assert np.array_equal(reference_frame["regime_"].to_numpy(), path), (
        "the Viterbi path differs from the reference implementation"
    )
    assert np.array_equal(reference_frame["regime"].to_numpy(), smoothed), (
        "the majority-smoothed path differs from the reference implementation"
    )


def test_port_matches_reference_on_synthetic_flight():
    track = _synthetic_track()
    assert len(track) > CONFIG.eligibility.min_fixes / 2
    _compare(track)


def test_synthetic_flight_exercises_every_feature():
    """A transcription test proves nothing if the track never fires the features."""
    frame = build_observation_frame(
        _synthetic_track(), CONFIG, alpha_straight_rad=ALPHA
    )
    observations = observation_matrix(frame)
    for column in range(observations.shape[1]):
        values = observations[:, column]
        assert values.min() == 0 and values.max() == 1, (
            f"feature {column} never changes on the synthetic track"
        )
    decoded = np.unique(viterbi(observations, CONFIG.parameters))
    assert decoded.size == 3, "the synthetic track does not visit all three states"


@pytest.mark.skipif(not ARCHIVE.is_dir(), reason="the IGC archive is not mounted")
@pytest.mark.parametrize(
    "name",
    [
        "2021-09-01_20308841.igc",
        "2021-09-01_20308851.igc",
        "2021-09-01_20308854.igc",
    ],
)
def test_port_matches_reference_on_real_flights(name):
    from soaring.analysis import igc

    fixes = igc.parse_igc(ARCHIVE / name)
    _compare(
        pd.DataFrame(
            {
                "t": fixes["t"].to_numpy(dtype=float),
                "lat": fixes["lat"].to_numpy(dtype=float),
                "lon": fixes["lon"].to_numpy(dtype=float),
                "alt": fixes["gnss_alt"].to_numpy(dtype=float),
            }
        )
    )
