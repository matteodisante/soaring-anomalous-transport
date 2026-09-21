"""Independently reconstruct all 16 baseline cells and validate the saved contrasts."""

import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

OUT = Path(__file__).resolve().parent
RUN = OUT / "run"
DATA = Path("/Volumes/SSD_DISANTE/derived-audit/chapter3-fixed-20260917/para")
report = json.loads((RUN / "report.json").read_text())
frame = pd.read_parquet(DATA / "flights.parquet")
members = pd.read_parquet(RUN / "membership.parquet")
cohort = frame.cohort_10000.to_numpy(bool)
np.testing.assert_array_equal(frame.loc[cohort, "flight_id"], members.flight_id)
saved = np.load(RUN / "replicates.npz")
lags = saved["lags"]
with np.load(DATA / "msd.npz") as archive:
    take = np.flatnonzero(np.isin(archive["lags"], lags))
    np.testing.assert_array_equal(archive["lags"][take], lags)
values = np.load(DATA / "flight-msd.npy", mmap_mode="r")[cohort, 3][:, take]
draws = np.load(DATA / "cluster-draws.npy", mmap_mode="r")
owners = members.cluster.to_numpy(int)
base = report["results"]["site_day"]
direct = np.empty_like(saved["site_day_msd"]).reshape(len(draws), 16, len(lags))
for j, support in enumerate(base["support"]):
    mask = members.factorial_cell.eq(support["cell"]).to_numpy()
    assert int(mask.sum()) == support["flights"]
    assert len(np.unique(owners[mask])) == support["groups"]
    # Direct flight weights, without the production cluster-sum reducer.
    for start in range(0, len(draws), 100):
        weights = draws[start : start + 100, owners[mask]].astype(float)
        direct[start : start + 100, j] = (weights @ values[mask]) / weights.sum(
            axis=1, keepdims=True
        )
np.testing.assert_allclose(
    direct, saved["site_day_msd"].reshape(direct.shape), rtol=3e-12
)
curve_error = float(
    np.max(np.abs(direct / saved["site_day_msd"].reshape(direct.shape) - 1))
)
design_lag = np.column_stack([np.ones(len(lags)), np.log10(lags)])
observations = np.log10(direct).reshape(-1, len(lags)).T
h = (np.linalg.lstsq(design_lag, observations, rcond=None)[0][1] / 2).reshape(
    len(draws), 4, 2, 2
)
np.testing.assert_allclose(h, saved["site_day_H_10_10000"], atol=2e-14)
i, j, k = np.indices((4, 2, 2)).reshape(3, -1)
design_cell = np.column_stack([np.ones(16), i == 1, i == 2, i == 3, j, k])
fitted = design_cell @ np.linalg.lstsq(design_cell, h.reshape(-1, 16).T, rcond=None)[0]
residual = h.reshape(-1, 16) - fitted.T
main = base["windows"]["10_10000"]
np.testing.assert_allclose(
    residual[0], np.array(main["residual"]["point"]).ravel(), atol=2e-14
)
np.testing.assert_allclose(
    np.percentile(residual[1:], [5, 95], axis=0),
    np.array([main["residual"]["low"], main["residual"]["high"]]).reshape(2, 16),
    atol=2e-14,
)
joint = np.column_stack(
    [
        (h[:, :, 0, :] - h[:, :, 1, :]).reshape(-1, 8),
        (h[:, :, :, 1] - h[:, :, :, 0]).reshape(-1, 8),
        h[:, 0, 0, 0] - h[:, 0, 1, 0] - h[:, 3, 0, 0] + h[:, 3, 1, 0],
        h[:, 0, 0, 1] - h[:, 0, 1, 1] - h[:, 3, 0, 1] + h[:, 3, 1, 1],
    ]
)
joint = np.column_stack([joint, joint[:, -1] - joint[:, -2]])
sd = joint[1:].std(axis=0, ddof=1)
critical = np.quantile(np.abs((joint[1:] - joint[0]) / sd).max(axis=1), 0.9)
for col, name in enumerate(report["contract"]["contrast_family"]):
    item = main["contrasts"][name]
    np.testing.assert_allclose(
        [item["point"], item["sim_low"], item["sim_high"]],
        [
            joint[0, col],
            joint[0, col] - critical * sd[col],
            joint[0, col] + critical * sd[col],
        ],
        atol=2e-14,
    )
all_values = {}
for name in ("report.json", "membership.parquet", "replicates.npz"):
    with (RUN / name).open("rb") as stream:
        all_values[name] = hashlib.file_digest(stream, "sha256").hexdigest()
result = {
    "status": "passed",
    "cells": 16,
    "bootstrap_draws": len(draws) - 1,
    "lags": len(lags),
    "maximum_relative_curve_error": curve_error,
    "maximum_absolute_H_error": float(np.max(np.abs(h - saved["site_day_H_10_10000"]))),
    "contrasts_independently_verified": 19,
    "additive_projection": "independent least-squares design, all draws",
    "hashes": all_values,
}
(OUT / "audit.json").write_text(json.dumps(result, indent=2) + "\n")
print(json.dumps(result, indent=2))
