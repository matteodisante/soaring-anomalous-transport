"""Reproduction compares identity, quality flags and local storage precision."""

import runpy
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = runpy.run_path(str(ROOT / "scripts/check_reproducible.py"))


def frame():
    values = {key: [0.2, 100000.0] for key in SCRIPT["_NUMERIC"]}
    values.update({key: [False, False] for key in SCRIPT["_FLAGS"]})
    return pd.DataFrame(values)


def test_float32_roundtrip_is_accepted():
    fresh = frame()
    stored = fresh.copy()
    stored[SCRIPT["_NUMERIC"]] = stored[SCRIPT["_NUMERIC"]].astype("float32")
    assert SCRIPT["_disagreement"](stored, fresh) is None


def test_large_distant_coordinate_does_not_hide_local_disagreement():
    stored, fresh = frame(), frame()
    fresh.loc[0, "E"] += 0.01
    assert "float32 tolerance" in SCRIPT["_disagreement"](stored, fresh)


def test_infinities_cannot_be_declared_reproducible():
    stored, fresh = frame(), frame()
    stored.loc[0, "E"] = fresh.loc[0, "E"] = np.inf
    assert "infinite" in SCRIPT["_disagreement"](stored, fresh)


def test_missing_sg_support_flag_requires_new_cleaning():
    stored, fresh = frame(), frame()
    stored = stored.drop(columns="z_derivative_reconstructed")
    assert "missing required quality flag" in SCRIPT["_disagreement"](stored, fresh)
