"""Tests for soaring.viewer.data (Qt-free logic layer)."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

from soaring.acquisition.ffvl.config import Config
from soaring.analysis.config import load_preproc_config
from soaring.analysis.preproc.altchannel import adopt_alt_channel
from soaring.analysis.preproc.enu import LocalFrame
from soaring.analysis.preproc.pipeline import run_flight
from soaring.reporting import disciplines as disciplines_mod
from soaring.viewer import data as viewer_data
from soaring.viewer.data import (
    PhaseTrack,
    RawTrack,
    cleaned_to_geographic,
    format_dms,
    frame_from_meta,
    load_cleaned,
    load_flight_phases,
    load_raw,
    raw_only_frame,
    raw_to_enu,
    resolve_discipline,
)

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "sample_flight.igc"
CFG = load_preproc_config()

# Mirrors tests/analysis/preproc/test_pipeline.py's synthetic-track convention.
LAT0, LON0 = 45.0, 7.0
_M_PER_DEG_LAT = 111_320.0
_M_PER_DEG_LON = _M_PER_DEG_LAT * np.cos(np.radians(LAT0))


def _xc_track(duration_s=3000.0, ground_s=120.0):
    n_air = int(duration_s)
    t_air = np.arange(n_air, dtype=float)
    east = 12.0 * t_air
    north = 200.0 * np.sin(2.0 * np.pi * t_air / 600.0)
    alt = 1200.0 + 400.0 * (1.0 - np.cos(2.0 * np.pi * t_air / 900.0))

    ground = int(ground_s)
    t = np.arange(n_air + 2 * ground, dtype=float)
    east = np.concatenate([np.zeros(ground), east, np.full(ground, east[-1])])
    north = np.concatenate([np.zeros(ground), north, np.full(ground, north[-1])])
    alt = np.concatenate([np.full(ground, alt[0]), alt, np.full(ground, alt[-1])])
    return pd.DataFrame(
        {
            "t": t,
            "lat": LAT0 + north / _M_PER_DEG_LAT,
            "lon": LON0 + east / _M_PER_DEG_LON,
            "valid": np.full(t.size, True),
            "baro_alt": alt - 50.0,
            "gnss_alt": alt,
        }
    )


def test_load_raw_from_fixture_adds_alt_column():
    raw = load_raw(FIXTURE, CFG)
    assert isinstance(raw, RawTrack)
    assert "alt" in raw.fixes.columns
    assert len(raw.fixes) == 4


def test_load_cleaned_from_a_too_short_fixture_is_dropped_but_still_informative():
    # Four fixes / 90 s is far below any plausible flight-level minimum: the pipeline
    # drops it, which is exactly the "raw still shows, with a reason" case the viewer
    # has to handle gracefully rather than treating as an error.
    result = load_cleaned(
        FIXTURE, CFG, source="paraglider", flight_id="fixture", discipline="paragliders"
    )
    assert result.kept is False
    assert result.meta.drop_reason is not None


def test_format_dms_round_trip_and_hemispheres():
    assert format_dms(44 + 32.469 / 60.0, "lat") == "44°32′28.14″N"  # noqa: RUF001
    assert format_dms(-(5 + 42.796 / 60.0), "lon") == "5°42′47.76″W"  # noqa: RUF001


def test_raw_to_enu_uses_the_given_frame_not_a_freshly_computed_one():
    # The frame's origin is the cleaned trajectory's, not the raw track's own first
    # row -- so raw_to_enu must project against *that* origin, wherever it sits
    # relative to the raw track's own start.
    frame = LocalFrame(lat0_deg=45.0, lon0_deg=7.0, alt0_m=1000.0)
    dummy_fixes = pd.DataFrame({"baro_alt": [0.0, 0.0], "gnss_alt": [900.0, 1000.0]})
    dummy_channel = adopt_alt_channel(dummy_fixes, CFG.alt_channel)[1]
    fixes = pd.DataFrame(
        {
            "t": [0.0, 10.0],
            "lat": [44.5, 45.0],  # row 0 is far from the frame's origin
            "lon": [6.5, 7.0],  # row 1 IS exactly the frame's origin
            "alt": [900.0, 1000.0],
        }
    )
    raw = RawTrack(fixes=fixes, alt_channel=dummy_channel)
    projected = raw_to_enu(raw, frame)

    assert projected["E"].iloc[1] == pytest.approx(0.0, abs=1e-6)
    assert projected["N"].iloc[1] == pytest.approx(0.0, abs=1e-6)
    assert abs(projected["E"].iloc[0]) > 1000.0 or abs(projected["N"].iloc[0]) > 1000.0
    # z keeps the real measured altitude, never the rotation's "up".
    assert projected["z"].tolist() == [900.0, 1000.0]


def test_frame_from_meta_matches_the_pipelines_own_origin_and_raw_lands_on_it():
    fixes = _xc_track()
    cleaned = run_flight(
        fixes, CFG, source="paraglider", flight_id="42", discipline="paragliders"
    )
    assert cleaned.kept

    frame = frame_from_meta(cleaned.meta)
    assert frame is not None
    assert frame.lat0_deg == pytest.approx(cleaned.meta.lat0)
    assert frame.lon0_deg == pytest.approx(cleaned.meta.lon0)

    with_alt, channel = adopt_alt_channel(fixes, CFG.alt_channel)
    raw = RawTrack(fixes=with_alt, alt_channel=channel)
    projected = raw_to_enu(raw, frame)

    # The synthetic track's ground phase sits still at the same spot the free flight
    # starts from, so the raw fix at the trimmed origin's recorded time must land
    # exactly on (0, 0) -- the same origin the cleaned trajectory's own first fix does.
    origin_t = cleaned.meta.ground_phase_start_s
    row_idx = (projected["t"] - origin_t).abs().idxmin()
    assert projected["E"].iloc[row_idx] == pytest.approx(0.0, abs=1.0)
    assert projected["N"].iloc[row_idx] == pytest.approx(0.0, abs=1.0)


def test_cleaned_to_geographic_lands_back_on_the_original_geography():
    fixes = _xc_track()
    cleaned = run_flight(
        fixes, CFG, source="paraglider", flight_id="42", discipline="paragliders"
    )
    assert cleaned.kept
    frame = frame_from_meta(cleaned.meta)
    assert frame is not None

    geographic = cleaned_to_geographic(cleaned.fixes, frame)
    assert {"lat", "lon", "alt", "segment_id"} <= set(geographic.columns)
    # The trajectory's own first fix is the frame's origin (E = N = 0): its recovered
    # (lat, lon) must be the origin's, to a small fraction of the pipeline's own
    # projection error (centimetres at flight scale, see soaring.viewer.geodesy).
    assert geographic["lat"].iloc[0] == pytest.approx(frame.lat0_deg, abs=1e-6)
    assert geographic["lon"].iloc[0] == pytest.approx(frame.lon0_deg, abs=1e-6)
    # A point away from the origin must move away in (lat, lon) too, in the direction
    # the synthetic track actually flew (east and, at its extreme, well north).
    assert geographic["lon"].iloc[-1] > geographic["lon"].iloc[0]


def test_frame_from_meta_is_none_for_a_flight_dropped_before_the_local_frame_stage():
    result = load_cleaned(
        FIXTURE, CFG, source="paraglider", flight_id="fixture", discipline="paragliders"
    )
    assert not result.kept
    assert frame_from_meta(result.meta) is None


def test_raw_only_frame_falls_back_when_the_pipeline_never_got_that_far():
    # Same fixture as the test above: dropped before stage (v), so frame_from_meta is
    # None -- exactly the situation raw_only_frame exists for.
    raw = load_raw(FIXTURE, CFG)
    frame = raw_only_frame(raw)
    assert frame is not None
    # Its own first fix, per soaring.analysis.preproc.enu.to_local_frame.
    assert frame.lat0_deg == pytest.approx(raw.fixes["lat"].iloc[0])
    assert frame.lon0_deg == pytest.approx(raw.fixes["lon"].iloc[0])


def test_raw_only_frame_is_none_for_an_empty_track():
    empty = RawTrack(
        fixes=pd.DataFrame(columns=["t", "lat", "lon", "alt"]),
        alt_channel=adopt_alt_channel(
            pd.DataFrame({"baro_alt": [], "gnss_alt": []}), CFG.alt_channel
        )[1],
    )
    assert raw_only_frame(empty) is None


def test_resolve_discipline(tmp_path, monkeypatch):
    para_root = tmp_path / "para_root"
    hang_root = tmp_path / "hang_root"
    para_root.mkdir()
    hang_root.mkdir()

    def fake_config(self):
        root = para_root if self.name == "paragliders" else hang_root
        return Config(
            data_root=root, season_start=2020, season_end=2021, base_url="https://x"
        )

    monkeypatch.setattr(disciplines_mod.Discipline, "config", fake_config)

    igc_file = para_root / "raw" / "igc" / "2020-2021" / "2020-01-01_1.igc"
    igc_file.parent.mkdir(parents=True)
    igc_file.touch()

    assert resolve_discipline(igc_file).name == "paragliders"
    assert resolve_discipline(hang_root / "elsewhere.igc").name == "hang gliders"
    assert resolve_discipline(tmp_path / "outside.igc") is None


def test_load_flight_phases_decodes_only_selected_flight_and_splits_runs(
    tmp_path, monkeypatch
):
    root = tmp_path / "archive"
    model_dir = root / "derived" / "segmentation" / "model"
    model_dir.mkdir(parents=True)
    (model_dir / "metadata.json").write_text("{}", encoding="utf-8")
    (model_dir / "gaussian_hmm.pkl").touch()
    discipline = next(iter(disciplines_mod.DISCIPLINES.values()))
    monkeypatch.setattr(
        disciplines_mod.Discipline,
        "config",
        lambda self: Config(
            data_root=root,
            season_start=2020,
            season_end=2021,
            base_url="https://x",
        ),
    )
    artifact = SimpleNamespace(
        mapping_method="provisional-emission-signatures",
        config=SimpleNamespace(decision_step_s=10.0),
    )
    monkeypatch.setattr(viewer_data, "_load_phase_artifact", lambda *_: artifact)
    decoded = pd.DataFrame(
        {
            "segment_id": [0, 0, 0, 0, 1],
            "t": [0.0, 10.0, 20.0, 50.0, 0.0],
            "phase": ["transition", "transition", "search", "search", "search"],
        }
    )
    decoded["phase"] = decoded["phase"].astype("string[pyarrow]")
    monkeypatch.setattr(
        "soaring.analysis.segmentation.pipeline.segment_flight",
        lambda fixes, fitted: decoded.copy(),
    )
    one_flight = decoded[["segment_id", "t"]].copy()
    one_flight["source"] = "paraglider"
    one_flight["flight_id"] = "selected"

    result = load_flight_phases(one_flight, discipline)

    assert isinstance(result, PhaseTrack)
    assert result.mapping_method == "provisional-emission-signatures"
    assert result.fixes["phase_run"].tolist() == [0, 0, 1, 2, 3]


def test_load_flight_phases_is_optional_when_model_is_unreachable(
    tmp_path, monkeypatch
):
    discipline = next(iter(disciplines_mod.DISCIPLINES.values()))
    monkeypatch.setattr(
        disciplines_mod.Discipline,
        "config",
        lambda self: Config(
            data_root=tmp_path / "missing",
            season_start=2020,
            season_end=2021,
            base_url="https://x",
        ),
    )
    assert load_flight_phases(pd.DataFrame(), discipline) is None


def test_phase_overlay_preserves_native_vertices_and_uncovered_segments():
    cleaned = pd.DataFrame(
        {
            "segment_id": [0] * 61 + [1] * 3,
            "t": [*range(61), 0, 1, 2],
            "E": np.cos(np.arange(64)),
            "N": np.sin(np.arange(64)),
            "z": np.arange(64),
        }
    )
    points = pd.DataFrame(
        {
            "segment_id": [0] * 4,
            "t": [0.0, 10.0, 20.0, 50.0],
            "phase": ["unclassified", "climb", "search", "climb"],
            # Decision coordinates must never replace the cleaned coordinates.
            "E": [999.0] * 4,
        }
    )
    result = viewer_data.phases_on_cleaned_fixes(cleaned, points, decision_step_s=10.0)
    pd.testing.assert_frame_equal(result[cleaned.columns], cleaned)
    assert result.loc[4, "phase"] == "unclassified"
    assert result.loc[5:14, "phase"].eq("climb").all()
    assert result.loc[15:24, "phase"].eq("search").all()
    assert result.loc[25:44, "phase"].eq("unclassified").all()
    assert result.loc[45:54, "phase"].eq("climb").all()
    assert result.loc[55:, "phase"].eq("unclassified").all()
    assert result.loc[60, "track_run"] != result.loc[61, "track_run"]
