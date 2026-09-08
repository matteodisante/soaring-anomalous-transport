import numpy as np
import pandas as pd
import pytest

from soaring.analysis.altitude_noise import BARO_PRESENT_MIN
from soaring.analysis.config import (
    AltChannelThresholds,
    load_preproc_config,
)
from soaring.analysis.preproc.altchannel import DROP_NO_ALTITUDE, adopt_alt_channel

ALT_CHANNEL = AltChannelThresholds(
    gnss_present_min=0.95,
    gnss_min_range_m=30.0,
    baro_witness_present_min=0.95,
    baro_witness_min_range_m=30.0,
)


def _flight(gnss, baro=None, valid=None):
    n = len(gnss)
    return pd.DataFrame(
        {
            "t": np.arange(float(n)),
            "lat": np.full(n, 45.0),
            "lon": np.full(n, 7.0),
            "valid": np.full(n, True) if valid is None else valid,
            "baro_alt": (
                np.asarray(gnss, dtype=float) - 50.0
                if baro is None
                else np.asarray(baro, dtype=float)
            ),
            "gnss_alt": np.asarray(gnss, dtype=float),
        }
    )


def test_the_gnss_channel_is_adopted_and_the_barometer_witnesses():
    gnss = 1000.0 + np.arange(100.0) * 5.0  # 495 m of range, well alive
    out, channel = adopt_alt_channel(_flight(gnss), ALT_CHANNEL)

    assert channel.drop_reason is None
    assert channel.gnss_present_frac == 1.0
    assert channel.gnss_range_m == pytest.approx(495.0)
    assert out["alt"].to_numpy() == pytest.approx(gnss)
    # The barometer is not adopted -- it is rated, as the witness it has become.
    assert channel.baro_witness is True
    # The raw channels stay: the cleaning still needs them as frozen-lock witnesses.
    assert {"baro_alt", "gnss_alt", "valid"} <= set(out.columns)


def test_an_absent_gnss_channel_drops_the_flight():
    # There is no second channel to fall back to any more: a flight whose adopted
    # channel is missing has no vertical coordinate at all (sec:altchannel).
    gnss = np.zeros(100)
    baro = 1000.0 + np.arange(100.0)
    out, channel = adopt_alt_channel(_flight(gnss, baro=baro), ALT_CHANNEL)

    assert channel.drop_reason == DROP_NO_ALTITUDE
    assert channel.gnss_present_frac == 0.0
    # Dropped even though the barometer is perfectly healthy: the point of one channel
    # is that a flight is never quietly measured on the other.
    assert channel.baro_witness is True
    assert np.isnan(out["alt"].to_numpy()).all()


def test_a_partly_filled_gnss_channel_drops_the_flight():
    # 90 % coverage: below the 95 % cut. A channel with holes is worse than a missing
    # one -- its v_z would rest on stretches long enough to erase transitions.
    gnss = 1000.0 + np.arange(100.0) * 5.0
    gnss[:10] = 0.0
    _, channel = adopt_alt_channel(_flight(gnss), ALT_CHANNEL)

    assert channel.gnss_present_frac == pytest.approx(0.90)
    assert channel.drop_reason == DROP_NO_ALTITUDE


def test_a_barely_present_channel_is_kept_with_its_holes():
    # 96 %: present, so the flight is admitted and the four missing fixes are left
    # missing -- never back-filled from the barometer -- to be restored at resampling.
    gnss = 1000.0 + np.arange(100.0) * 5.0
    gnss[[10, 20, 30, 40]] = 0.0
    out, channel = adopt_alt_channel(_flight(gnss), ALT_CHANNEL)

    assert channel.drop_reason is None
    assert channel.n_missing == 4
    assert np.isnan(out["alt"].to_numpy()[[10, 20, 30, 40]]).all()
    # Not the barometric value at those fixes: the channels are never spliced.
    assert not np.isclose(out["alt"].to_numpy()[10], out["baro_alt"].to_numpy()[10])


def test_a_stuck_gnss_sensor_is_treated_as_absent():
    # Present but dead: a constant non-zero reading passes the presence check and would
    # feed the segmentation a vertical velocity of identically zero.
    gnss = np.full(100, 1200.0)
    _, channel = adopt_alt_channel(_flight(gnss), ALT_CHANNEL)

    assert channel.gnss_present_frac == 1.0
    assert channel.gnss_range_m == 0.0
    assert channel.drop_reason == DROP_NO_ALTITUDE


def test_the_liveness_bound_is_the_configured_one():
    sampled = load_preproc_config().alt_channel
    assert sampled.gnss_min_range_m == 30.0
    gnss = np.linspace(1000.0, 1029.0, 100)  # 29 m: just under the bound
    _, channel = adopt_alt_channel(_flight(gnss), sampled)
    assert channel.drop_reason == DROP_NO_ALTITUDE
    gnss = np.linspace(1000.0, 1031.0, 100)  # 31 m: just over
    _, channel = adopt_alt_channel(_flight(gnss), sampled)
    assert channel.drop_reason is None


def test_an_absent_barometer_costs_the_witness_and_nothing_else():
    """The flight is measured exactly as any other; only the frozen-lock test weakens.

    This is the whole point of demoting the barometer rather than dropping it: a logger
    with no pressure sensor is no longer a differently-measured flight, it is a flight
    whose frozen-lock rule has one fewer signature to work with (sec:fixlevel).
    """
    gnss = 1000.0 + np.arange(100.0) * 5.0
    out, channel = adopt_alt_channel(_flight(gnss, baro=np.zeros(100)), ALT_CHANNEL)

    assert channel.drop_reason is None
    assert channel.baro_witness is False
    assert channel.baro_present_frac == 0.0
    assert out["alt"].to_numpy() == pytest.approx(gnss)


def test_a_stuck_barometer_cannot_witness():
    # Present but dead. A flat reading is exactly what the frozen-lock witness looks
    # for, so a stuck sensor would witness every candidate run and cut genuine climbs.
    gnss = 1000.0 + np.arange(100.0) * 5.0
    stuck_baro = np.full(100, 1013.0)
    _, channel = adopt_alt_channel(_flight(gnss, baro=stuck_baro), ALT_CHANNEL)

    assert channel.baro_present_frac == 1.0
    assert channel.baro_range_m == 0.0
    assert channel.baro_witness is False


def test_a_missing_column_is_reported():
    with pytest.raises(ValueError, match="gnss_alt"):
        adopt_alt_channel(_flight(np.ones(10)).drop(columns=["gnss_alt"]), ALT_CHANNEL)


def test_the_presence_threshold_lives_in_the_config_and_nowhere_else():
    """One value, one home. It gates every flight in the archive.

    It used to be a Python constant in `soaring.analysis.altitude_noise`, absent from
    `configs/preprocessing.yaml` and from the thesis' table of working parameters --
    in direct contradiction of the contract those three places assert between them. The
    diagnostic module still exposes it, because the figure scripts read cached scans
    rather than the config, so this test is what stops the two from drifting apart.
    """
    configured = load_preproc_config().alt_channel
    assert configured.gnss_present_min == BARO_PRESENT_MIN
    assert configured.baro_witness_present_min == BARO_PRESENT_MIN
    assert 0.0 < configured.gnss_present_min <= 1.0


def test_a_blank_gnss_field_is_absent_and_not_fully_present():
    """`nan != 0` is True, so a channel written blank used to read as 100 % present.

    The threshold is 0.95, so a blank channel passed it and the pipeline adopted an
    altitude that is not there. Four flights in the archive reached the analysis dataset
    that way, identifiable by a NaN range on a flight recorded as having a channel.
    """
    _, channel = adopt_alt_channel(_flight(np.full(10, np.nan)), ALT_CHANNEL)
    assert channel.gnss_present_frac == 0.0
    assert channel.drop_reason == DROP_NO_ALTITUDE


def test_a_half_blank_gnss_field_is_half_present():
    gnss = np.concatenate([np.full(5, np.nan), np.full(5, 1000.0)])
    _, channel = adopt_alt_channel(_flight(gnss), ALT_CHANNEL)
    assert channel.gnss_present_frac == pytest.approx(0.5)
    assert channel.drop_reason == DROP_NO_ALTITUDE
