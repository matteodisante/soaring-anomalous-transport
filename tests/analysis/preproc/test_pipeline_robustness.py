"""The pipeline against deliberately broken tracks: what must hold whatever arrives.

The unit tests of the other files each pin one rule on one clean case. This one goes the
other way: it builds flights out of randomly combined defects -- the ones the archive
actually holds, plus a few it has no business holding -- and asserts only the properties
the rest of the analysis is entitled to assume. Nothing here checks *what* the pipeline
decided; everything checks that whatever it decided leaves a table the next stage can
read.

Three of the bugs this session fixed would have been caught here on the first run: a
missing altitude destroying the horizontal position, an impossible step surviving inside
a segment, and a corrupt block whose exit step no rule had declared a boundary.
"""

import numpy as np
import pandas as pd
import pytest

from soaring.analysis.preproc.pipeline import FIX_TABLE_COLUMNS, run_flight
from soaring.analysis.preprocessing import load_preproc_config

CFG = load_preproc_config()
LAT0, LON0 = 45.0, 7.0
_M_PER_DEG_LAT = 111_320.0
_M_PER_DEG_LON = _M_PER_DEG_LAT * np.cos(np.radians(LAT0))
_MAX_SPEED = CFG.fix.max_horizontal_speed_mps["paragliders"]


# Long enough that the flight-level gates are not what the fuzz measures: 5000 s of
# cruise leaves well over the 40 min minimum even after a defect has eaten into it. The
# first version of this file used 2400 s, which is exactly the minimum *before* the
# ground phases are trimmed -- so every case was dropped at stage (iv) and the
# invariants below never ran at all. `test_the_fuzz_actually_reaches_the_output_table`
# is here so that cannot come back.
def _base_track(rng, n=5000, dt=1.0):
    """A flight that would pass every gate: cruise, climbs, ground at each end."""
    t = np.arange(n, dtype=float) * dt
    east = 11.0 * t + 250.0 * np.sin(2.0 * np.pi * t / 700.0)
    north = 180.0 * np.sin(2.0 * np.pi * t / 430.0) + 3.0 * t
    alt = 1400.0 + 500.0 * (1.0 - np.cos(2.0 * np.pi * t / 900.0))
    ground = max(20, int(120.0 / dt))
    east[:ground] = east[ground] + rng.normal(0.0, 0.7, ground)
    north[:ground] = north[ground] + rng.normal(0.0, 0.7, ground)
    east[-ground:] = east[-ground - 1]
    north[-ground:] = north[-ground - 1]
    alt[:ground] = alt[ground]
    alt[-ground:] = alt[-ground - 1]
    return pd.DataFrame(
        {
            "t": t,
            "lat": LAT0 + north / _M_PER_DEG_LAT,
            "lon": LON0 + east / _M_PER_DEG_LON,
            "valid": np.full(n, True),
            "baro_alt": np.round(alt),
            "gnss_alt": np.round(alt + 47.0),
        }
    )


def _somewhere(track, rng, margin=0.1):
    """A row index inside the track, never in its first or last tenth."""
    edge = max(2, int(margin * len(track)))
    return int(rng.integers(edge, max(edge + 1, len(track) - edge)))


def _spikes(track, rng):
    """Isolated position spikes, and one short burst."""
    for _ in range(rng.integers(1, 5)):
        track.loc[_somewhere(track, rng), "lat"] += (
            rng.normal(0.0, 400.0) / _M_PER_DEG_LAT
        )
    i = _somewhere(track, rng)
    track.loc[i : i + 2, "lon"] += 900.0 / _M_PER_DEG_LON
    return track


def _opening_defect(track, rng):
    """Corruption in the record's first seconds -- either end of it wrong.

    `_somewhere` never returns an index in the first tenth of a track, so nothing else
    here reaches the one place where a defect is not merely a defect: the first fix of
    the trimmed track becomes the origin of the local frame, and a rule that guesses
    wrong about which end of an impossible step is corrupt anchors the whole flight on
    the wrong point. Both ends are generated, because a rule that handles one and not
    the other is exactly what this closes.
    """
    i = int(rng.integers(1, 18))
    if rng.random() < 0.5:  # a spike after good fixes: the *later* end is wrong
        track.loc[i, "lat"] += 4000.0 / _M_PER_DEG_LAT
    else:  # a leading corrupt run: the *earlier* end is wrong
        track.loc[: i - 1, ["lat", "lon"]] = 0.0
    return track


def _null_island(track, rng):
    """Scattered runs of the (0, 0) position some loggers write."""
    for _ in range(rng.integers(2, 6)):
        i = _somewhere(track, rng)
        track.loc[i : i + int(rng.integers(2, 25)), ["lat", "lon"]] = 0.0
    return track


def _frozen(track, rng):
    """A byte-identical run: the receiver repeating its last position."""
    i = _somewhere(track, rng, margin=0.2)
    span = int(rng.integers(5, max(6, len(track) // 8)))
    track.loc[i : i + span, "lat"] = track.loc[i, "lat"]
    track.loc[i : i + span, "lon"] = track.loc[i, "lon"]
    return track


def _time_defects(track, rng):
    """Duplicate seconds and a forward-jumped clock."""
    i = _somewhere(track, rng)
    track.loc[i, "t"] = track.loc[i - 1, "t"]
    j = _somewhere(track, rng)
    track.loc[j, "t"] = track.loc[j, "t"] + 5000.0
    return track


def _altitude_defects(track, rng):
    """Absent, out-of-band and spiking altitudes."""
    i = _somewhere(track, rng)
    track.loc[i : i + int(rng.integers(1, 40)), "baro_alt"] = 0.0
    track.loc[_somewhere(track, rng), "baro_alt"] = 40_000.0
    track.loc[_somewhere(track, rng), "baro_alt"] += 300.0
    return track


def _gaps(track, rng):
    """Whole stretches simply missing from the log."""
    for _ in range(rng.integers(1, 4)):
        i = _somewhere(track, rng, margin=0.15)
        span = int(rng.integers(5, max(6, len(track) // 8)))
        # Positional, and re-indexed each time: a second gap must not address rows the
        # first one already removed.
        track = pd.concat([track.iloc[:i], track.iloc[i + span :]]).reset_index(
            drop=True
        )
    return track


def _offset(track, rng):
    """A re-acquisition offset: the track jumps and stays."""
    i = _somewhere(track, rng, margin=0.2)
    track.loc[i:, "lat"] += rng.choice([-1.0, 1.0]) * 5000.0 / _M_PER_DEG_LAT
    return track


def _degraded(track, rng):
    """A stretch the recorder itself declares degraded."""
    i = _somewhere(track, rng, margin=0.15)
    track.loc[i : i + int(rng.integers(10, 150)), "valid"] = False
    return track


DEFECTS = [
    _spikes,
    _opening_defect,
    _null_island,
    _frozen,
    _time_defects,
    _altitude_defects,
    _gaps,
    _offset,
    _degraded,
]


def _assert_invariants(result, label):
    """Everything downstream is entitled to assume, whatever the pipeline decided."""
    meta = result.meta
    assert meta.source and meta.flight_id, label
    assert meta.n_fix_raw is not None and meta.n_fix_raw >= 0, label
    if meta.n_fix_clean is not None:
        assert 0 <= meta.n_fix_clean <= meta.n_fix_raw, label

    fixes = result.fixes
    assert result.kept == (not fixes.empty), label
    if fixes.empty:
        assert meta.drop_reason, f"{label}: dropped without a reason"
        return

    assert list(fixes.columns) == FIX_TABLE_COLUMNS, label
    kinematics = ["t", "E", "N", "z", "v_E", "v_N", "v_z", "a_E", "a_N", "a_z"]
    assert np.isfinite(fixes[kinematics].to_numpy()).all(), (
        f"{label}: nan in the output"
    )

    for (_, segment_id), segment in fixes.groupby(["flight_id", "segment_id"]):
        t = segment["t"].to_numpy()
        step = np.diff(t)
        assert (step > 0).all(), f"{label}: segment {segment_id} clock not increasing"
        assert np.allclose(step, step[0], atol=1e-3), f"{label}: grid not uniform"
        speed = (
            np.hypot(np.diff(segment["E"].to_numpy()), np.diff(segment["N"].to_numpy()))
            / step
        )
        # The bound is a statement about *measured* motion, so it is read between two
        # samples that are both measured and both centred. The other two cases are
        # reconstruction, and the table flags them for exactly this reason: at a segment
        # edge the polynomial is evaluated off-centre (sec:savgol), and across a bridged
        # gap the monotone cubic can exceed the secant it spans -- a hole crossed at
        # 42 m/s, itself legal, leaves interpolated points implying more.
        edge = segment["edge"].to_numpy(dtype=bool)
        filled = segment["interpolated"].to_numpy(dtype=bool)
        reconstructed = edge | filled
        measured = ~(reconstructed[:-1] | reconstructed[1:])
        assert (speed[measured] <= _MAX_SPEED).all(), (
            f"{label}: segment {segment_id} holds a "
            f"{speed[measured].max():.0f} m/s step between two measured samples"
        )

    # No *measured* position can be further from the origin than the bound allows in the
    # elapsed time: the flight started there. Stated in terms of the frame and the bound
    # alone, so it holds whatever the pipeline did -- and it is what catches a corrupt
    # *origin fix*, which leaves every individual step plausible.
    #
    # "Measured" is the same qualification the step bound above carries, and it belongs
    # here for the same reason. Without it the check fails on 188 samples of the real
    # archive, every one an interpolated grid point at t = 5 to 15 s: there v_max t is
    # only a couple of hundred metres, and the monotone cubic bridging the flight's
    # first gap lands 50 to 190 m beyond it. The wing was somewhere in between; the
    # interpolant guessed, and a guess is not a claim about measured motion.
    ordered = fixes.sort_values("t")
    reach = np.hypot(ordered["E"].to_numpy(), ordered["N"].to_numpy())
    allowed = _MAX_SPEED * ordered["t"].to_numpy() + 50.0
    invented = ordered["interpolated"].to_numpy(dtype=bool) | ordered["edge"].to_numpy(
        dtype=bool
    )
    beyond = (reach > allowed) & ~invented
    assert not beyond.any(), (
        f"{label}: a measured position sits {reach[beyond].max() / 1000:.0f} km from "
        f"the origin, out of reach at {_MAX_SPEED:.0f} m/s"
    )

    first = ordered.iloc[0]
    if first["segment_id"] == 0:
        # The frame's origin is that fix, up to the metres the smoothing moves an edge
        # sample; only a flight whose first segment was dropped starts elsewhere.
        assert abs(first["t"]) < 1e-6, label
        assert abs(first["E"]) < 50.0 and abs(first["N"]) < 50.0, label


def _fuzzed(seed):
    """One flight built from a seeded combination of defects, and its label."""
    rng = np.random.default_rng(seed)
    chosen = rng.choice(len(DEFECTS), size=int(rng.integers(1, 5)), replace=False)
    track = _base_track(rng)
    for index in chosen:
        track = DEFECTS[index](track, rng)
    return track, f"seed {seed}: " + ", ".join(DEFECTS[i].__name__ for i in chosen)


@pytest.mark.parametrize("seed", range(60))
def test_the_pipeline_survives_any_combination_of_defects(seed):
    track, label = _fuzzed(seed)
    result = run_flight(
        track, CFG, source="paraglider", flight_id=str(seed), discipline="paragliders"
    )
    _assert_invariants(result, label)


def test_the_fuzz_actually_reaches_the_output_table():
    """The invariants above are only tested on cases that produce one.

    A suite whose every case is dropped at an early gate passes without executing a
    single assertion about the trajectory table -- which is what this file did until the
    base track was made long enough to clear the flight-level cuts. Asserting that most
    cases survive is what keeps the rest of the file honest.
    """
    kept = sum(
        run_flight(
            _fuzzed(seed)[0],
            CFG,
            source="paraglider",
            flight_id=str(seed),
            discipline="paragliders",
        ).kept
        for seed in range(60)
    )
    assert kept >= 30, f"only {kept}/60 fuzzed flights produced a table"


@pytest.mark.parametrize(
    ("name", "track"),
    [
        (
            "empty",
            pd.DataFrame(
                {c: [] for c in ["t", "lat", "lon", "valid", "baro_alt", "gnss_alt"]}
            ),
        ),
        (
            "one fix",
            pd.DataFrame(
                {
                    "t": [0.0],
                    "lat": [45.0],
                    "lon": [7.0],
                    "valid": [True],
                    "baro_alt": [1000.0],
                    "gnss_alt": [1050.0],
                }
            ),
        ),
    ],
)
def test_degenerate_input_is_refused_and_not_crashed_on(name, track):
    result = run_flight(
        track, CFG, source="paraglider", flight_id=name, discipline="paragliders"
    )
    assert not result.kept
    assert result.meta.drop_reason
    _assert_invariants(result, name)


@pytest.mark.parametrize("dt", [0.5, 1.0, 2.0, 5.0, 10.0, 30.0])
def test_every_cadence_in_the_archive_is_handled(dt):
    # From the 2 Hz loggers to the thin tail past 20 s: each must either produce a
    # readable table or refuse with a reason, never an exception and never a segment
    # the smoothing could not have filtered.
    rng = np.random.default_rng(7)
    track = _spikes(_base_track(rng, n=int(3000 / dt), dt=dt), rng)
    result = run_flight(
        track, CFG, source="paraglider", flight_id=f"dt{dt}", discipline="paragliders"
    )
    _assert_invariants(result, f"dt = {dt}")
