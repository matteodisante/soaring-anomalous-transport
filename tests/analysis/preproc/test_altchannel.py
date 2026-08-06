import numpy as np
import pandas as pd
import pytest

from soaring.analysis.altitude_noise import BARO_PRESENT_MIN
from soaring.analysis.preproc.altchannel import adopt_alt_channel
from soaring.analysis.config import (
    AltChannelThresholds,
    load_preproc_config,
)

ALT_CHANNEL = AltChannelThresholds(baro_present_min=0.95, baro_min_range_m=30.0)


def _flight(baro, gnss=None, valid=None):
    n = len(baro)
    return pd.DataFrame(
        {
            "t": np.arange(float(n)),
            "lat": np.full(n, 45.0),
            "lon": np.full(n, 7.0),
            "valid": np.full(n, True) if valid is None else valid,
            "baro_alt": np.asarray(baro, dtype=float),
            "gnss_alt": (
                np.asarray(baro, dtype=float) + 50.0
                if gnss is None
                else np.asarray(gnss, dtype=float)
            ),
        }
    )


def test_a_live_barometric_channel_is_adopted():
    baro = 1000.0 + np.arange(100.0) * 5.0  # 495 m of range, well alive
    out, channel = adopt_alt_channel(_flight(baro), ALT_CHANNEL)

    assert channel.alt_source == "baro"
    assert channel.fallback_reason is None
    assert channel.baro_present_frac == 1.0
    assert channel.baro_range_m == pytest.approx(495.0)
    assert out["alt"].to_numpy() == pytest.approx(baro)
    # The raw channels stay: the cleaning still needs them as frozen-lock witnesses.
    assert {"baro_alt", "gnss_alt", "valid"} <= set(out.columns)


def test_an_absent_barometric_channel_falls_back_to_gnss():
    # A logger with no pressure sensor writes the whole channel as zero -- presence is
    # essentially all-or-nothing, which is why the cut can sit as high as 95 %.
    baro = np.zeros(100)
    gnss = 1200.0 + np.arange(100.0)
    out, channel = adopt_alt_channel(_flight(baro, gnss), ALT_CHANNEL)

    assert channel.alt_source == "gnss"
    assert channel.fallback_reason == "absent"
    assert channel.baro_present_frac == 0.0
    assert out["alt"].to_numpy() == pytest.approx(gnss)


def test_a_partly_filled_barometric_channel_falls_back():
    # 90 % coverage: below the 95 % cut, so the flight is sent to GNSS rather than given
    # a v_z resting on a channel with holes (sec:altchannel).
    baro = 1000.0 + np.arange(100.0) * 5.0
    baro[:10] = 0.0
    _, channel = adopt_alt_channel(_flight(baro), ALT_CHANNEL)

    assert channel.baro_present_frac == pytest.approx(0.90)
    assert channel.baro_present_frac < BARO_PRESENT_MIN
    assert channel.alt_source == "gnss"
    assert channel.fallback_reason == "absent"


def test_a_barely_present_channel_is_still_barometric_with_its_holes():
    # 96 %: present, so the flight is barometric and the four missing fixes are left
    # missing -- never back-filled from GNSS -- to be restored at resampling.
    baro = 1000.0 + np.arange(100.0) * 5.0
    baro[[10, 20, 30, 40]] = 0.0
    out, channel = adopt_alt_channel(_flight(baro), ALT_CHANNEL)

    assert channel.alt_source == "baro"
    assert channel.n_missing == 4
    assert np.isnan(out["alt"].to_numpy()[[10, 20, 30, 40]]).all()
    # Not the GNSS value at those fixes: the channels are never spliced.
    assert not np.isclose(out["alt"].to_numpy()[10], out["gnss_alt"].to_numpy()[10])


def test_a_stuck_sensor_is_treated_as_absent():
    # Present but dead: a constant non-zero reading passes the presence check and would
    # feed the segmentation a vertical velocity of identically zero.
    baro = np.full(100, 1013.0)
    gnss = 1200.0 + np.arange(100.0)
    out, channel = adopt_alt_channel(_flight(baro, gnss), ALT_CHANNEL)

    assert channel.baro_present_frac == 1.0
    assert channel.baro_range_m == 0.0
    assert channel.alt_source == "gnss"
    assert channel.fallback_reason == "stuck"
    assert out["alt"].to_numpy() == pytest.approx(gnss)


def test_the_liveness_bound_is_the_configured_one():
    sampled = load_preproc_config().alt_channel
    assert sampled.baro_min_range_m == 30.0
    baro = np.linspace(1000.0, 1029.0, 100)  # 29 m: just under the bound
    _, channel = adopt_alt_channel(_flight(baro), sampled)
    assert channel.alt_source == "gnss"
    baro = np.linspace(1000.0, 1031.0, 100)  # 31 m: just over
    _, channel = adopt_alt_channel(_flight(baro), sampled)
    assert channel.alt_source == "baro"


def test_a_missing_column_is_reported():
    with pytest.raises(ValueError, match="gnss_alt"):
        adopt_alt_channel(_flight(np.ones(10)).drop(columns=["gnss_alt"]), ALT_CHANNEL)


def test_the_presence_threshold_lives_in_the_config_and_nowhere_else():
    """One value, one home. It decides `alt_source` for every flight in the archive.

    It used to be a Python constant in `soaring.analysis.altitude_noise`, absent from
    `configs/preprocessing.yaml` and from the thesis' table of working parameters --
    in direct contradiction of the contract those three places assert between them. The
    diagnostic module still exposes it, because the figure scripts read cached scans
    rather than the config, so this test is what stops the two from drifting apart.
    """
    from soaring.analysis.altitude_noise import BARO_PRESENT_MIN
    from soaring.analysis.config import load_preproc_config

    configured = load_preproc_config().alt_channel.baro_present_min
    assert configured == BARO_PRESENT_MIN
    assert 0.0 < configured <= 1.0


def test_a_blank_barometric_field_is_absent_and_not_fully_present():
    """`nan != 0` is True, so a channel written blank used to read as 100 % present.

    The threshold is 0.95, so a blank channel passed it and the pipeline adopted an altitude
    that is not there. Four flights in the archive reached the analysis dataset that way,
    identifiable by a NaN `baro_range_m` on a flight recorded as barometric.
    """
    _, channel = adopt_alt_channel(_flight(np.full(10, np.nan)), ALT_CHANNEL)
    assert channel.baro_present_frac == 0.0
    assert channel.alt_source == "gnss"


def test_a_half_blank_barometric_field_is_half_present():
    baro = np.concatenate([np.full(5, np.nan), np.full(5, 1000.0)])
    _, channel = adopt_alt_channel(_flight(baro), ALT_CHANNEL)
    assert channel.baro_present_frac == pytest.approx(0.5)
    assert channel.alt_source == "gnss"
