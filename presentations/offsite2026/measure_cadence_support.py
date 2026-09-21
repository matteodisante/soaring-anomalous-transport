"""Slide 8: C_10000, cadence-limited support below 10 s and fixed support above.

All SSD inputs are read-only. Short lags admit segments when native dt <= tau;
endpoints between native fixes are linearly interpolated within the selected span.
At >=10 s, use the exact published common-grid estimator at a denser set of lags.
"""
from pathlib import Path
import hashlib
import json
import sys
import time

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
from soaring.analysis.derived import stream_flights
from soaring.analysis.observables.archive_diagnostics import DiskFrames
from soaring.analysis.observables.fixed_bootstrap import bootstrap_means
from soaring.analysis.observables.fixed_transport import LAGS, log_fit
from soaring.analysis.observables.transport import time_averaged_msd

HERE = Path(__file__).resolve().parent
RUN = Path("/Volumes/SSD_DISANTE/derived-audit/chapter3-fixed-20260917")
CACHE = HERE / "build/cadence-support"
CACHE.mkdir(parents=True, exist_ok=True)
LONG = np.unique(np.r_[10 * np.rint(np.geomspace(1, 1000, 501)), LAGS]).astype(int)
ALL_LAGS = np.r_[np.arange(1, 10), LONG]


def slope_operator(lags):
    """Half log-log OLS slope, +/-0.25 dex; nearest three at sparse edges."""
    x = np.log10(lags)
    weights = np.zeros((len(x), len(x)))
    windows = []
    for i, centre in enumerate(x):
        distance = np.abs(x - centre)
        take = np.flatnonzero(distance <= .25 + 1e-12)
        if len(take) < 3:
            take = np.sort(np.argsort(distance, kind="stable")[:3])
        centred = x[take] - x[take].mean()
        weights[i, take] = .5 * centred / (centred @ centred)
        windows.append([int(lags[take[0]]), int(lags[take[-1]]), len(take)])
    return weights, windows


def stats(curves):
    """Observed statistic and nominal pointwise 90% bootstrap interval."""
    return {"point": curves[0].tolist(), "low": np.percentile(curves[1:], 5, axis=0).tolist(),
            "high": np.percentile(curves[1:], 95, axis=0).tolist()}


def short_curve(flight, member):
    """Native origins, linear endpoint interpolation, no lag below native cadence."""
    wanted = {s["segment_id"]: s for s in member["segments"]}
    sums = np.zeros(9)
    counts = np.zeros(9, dtype=np.int64)
    interpolated = np.zeros(9, dtype=np.int64)
    seen = set()
    for sid, part in flight.groupby("segment_id", sort=False):
        if sid not in wanted:
            continue
        seen.add(sid)
        t = part.t.to_numpy(dtype=float)
        t = t - t[0]
        dt = float(np.median(np.diff(t)))
        assert np.allclose(np.diff(t), dt, rtol=0, atol=1e-5)
        span = wanted[sid]["duration_s"]
        assert t[-1] >= span and dt <= 10
        xy = part[["E", "N"]].to_numpy(dtype=float)
        for j, tau in enumerate(range(1, 10)):
            if dt > tau + 1e-9:
                continue
            n = int(np.searchsorted(t, span - tau + 1e-8, side="right"))
            endpoints = t[:n] + tau
            displacement = np.column_stack([np.interp(endpoints, t, xy[:, k]) for k in (0, 1)]) - xy[:n]
            sums[j] += np.einsum("ij,ij->", displacement, displacement)
            counts[j] += n
            if not np.isclose(tau / dt, round(tau / dt)):
                interpolated[j] += n
    assert seen == set(wanted)
    return np.divide(sums, counts, out=np.full(9, np.nan), where=counts > 0), counts, interpolated


def measure(slug):
    started = time.monotonic()
    directory = RUN / slug
    cohort = json.loads((directory / "cohort-10000.json").read_text())
    members = cohort["members"]
    ids = [m["flight_id"] for m in members]
    selected = {m["flight_id"]: m for m in members}
    index = {fid: i for i, fid in enumerate(ids)}
    tab = pd.read_parquet(directory / "flights.parquet").set_index("flight_id").loc[ids]
    native = json.loads((directory / "native-provenance.json").read_text())
    source = Path(native["source"])
    assert source.stat().st_size == native["size"]
    assert source.stat().st_mtime_ns == native["mtime_ns"]
    identity = {"cohort_sha256": cohort["sha256"], "source": native, "lags": ALL_LAGS.tolist(),
                "short_rule": "native origins; dt<=tau; linear endpoints; published selected segment spans"}
    fingerprint = hashlib.sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest()
    cache = CACHE / f"{slug}-flight-msd.npz"
    if cache.exists():
        stored = np.load(cache)
        assert str(stored["fingerprint"]) == fingerprint
        values = stored["values"]
        added_interpolation = stored["added_interpolation"]
    else:
        values = np.full((len(ids), len(ALL_LAGS)), np.nan)
        added_interpolation = np.zeros(9, dtype=np.int64)
        reused = set()
        # Optional reuse of the validated all-native-1-s calculation. These lags
        # require no added interpolation and use the same origins and exact spans.
        previous = HERE / "build/native-fixed"
        if (previous / f"{slug}-flight-msd.npz").exists():
            prior = json.loads((previous / f"{slug}-selection.json").read_text())
            assert prior["cohort_sha256"] == cohort["sha256"] and prior["source"] == native
            old = np.load(previous / f"{slug}-flight-msd.npz")
            assert str(old["fingerprint"]) == hashlib.sha256(json.dumps(prior, sort_keys=True).encode()).hexdigest()
            old_values = old["values"]
            for row, member in enumerate(prior["selection"]):
                fid = member["flight_id"]
                assert member == selected[fid]
                values[index[fid], :9] = old_values[row, :9]
                reused.add(fid)
            print(f"{slug}: reused {len(reused)} native-1-s flight curves", flush=True)
        remaining = set(ids) - reused
        n_done = 0
        for flight in stream_flights(source, ["segment_id", "t", "E", "N"]):
            fid = str(flight.flight_id.iloc[0])
            if fid not in remaining:
                continue
            curve, counts, interpolation = short_curve(flight, selected[fid])
            values[index[fid], :9] = curve
            added_interpolation += interpolation
            n_done += 1
            if n_done % 2000 == 0:
                print(f"{slug}: short lags {n_done}/{len(remaining)}, {time.monotonic()-started:.0f}s", flush=True)
        assert n_done == len(remaining)
        provenance = json.loads((directory / "measurement-provenance.json").read_text())
        frames = DiskFrames(provenance["coordinates"])
        for i, member in enumerate(members):
            row, positions = frames[member["frame_index"]]
            assert row["flight_id"] == member["flight_id"]
            sums = np.zeros(len(LONG))
            counts = np.zeros(len(LONG))
            for segment in member["segments"]:
                a, b = segment["start"], segment["stop"]
                assert (b-a-1)*10 == segment["duration_s"]
                xy = positions[a:b]
                curve = time_averaged_msd(xy[:, 0], xy[:, 1], 10)
                n = b-a-LONG//10
                assert np.all(n > 0)
                sums += curve[LONG//10] * n
                counts += n
            values[i, 9:] = sums / counts
            if (i+1) % 10000 == 0:
                print(f"{slug}: dense common-grid MSD {i+1}/{len(ids)}", flush=True)
        np.savez_compressed(cache, fingerprint=fingerprint, values=values, added_interpolation=added_interpolation)
    # Every existing published point must be reproduced for every selected flight.
    old_lags = np.load(directory / "msd.npz")["lags"]
    old_values = np.load(directory / "flight-msd.npy", mmap_mode="r")
    expected = old_values[[m["frame_index"] for m in members], 3][:, np.searchsorted(old_lags, LAGS)]
    np.testing.assert_allclose(values[:, np.searchsorted(ALL_LAGS, LAGS)], expected, rtol=1e-9, atol=1e-5)
    assert np.isfinite(values[:, 9:]).all()
    support = np.isfinite(values).sum(axis=0)
    assert np.all(np.diff(support) >= 0) and np.all(support[9:] == len(ids))
    labels = tab.cluster.to_numpy()
    unique, local_labels = np.unique(labels, return_inverse=True)
    draws = np.load(directory / "cluster-draws.npy", mmap_mode="r")
    curves = bootstrap_means(values, local_labels, draws[:, unique])
    np.testing.assert_allclose(curves[0], np.nanmean(values, axis=0), rtol=1e-12)
    weights, windows = slope_operator(ALL_LAGS)
    h = np.log10(curves) @ weights.T
    fit = log_fit(LAGS, curves[:, np.searchsorted(ALL_LAGS, LAGS)])["slope"] / 2
    assert np.isfinite(h).all()
    reference = json.loads((ROOT / "thesis/generated/ch3_transport_report.json").read_text())["results"][slug]
    np.testing.assert_allclose(fit[0], reference["fits"]["10-10000"]["hurst"]["point"], rtol=1e-10)
    np.savez_compressed(CACHE / f"{slug}-bootstrap.npz", lags=ALL_LAGS, curves=curves, local_h=h)
    print(f"{slug}: complete; N(1..10s)={support[:10].tolist()}, H={fit[0]:.6f}", flush=True)
    return {"flights": len(ids), "segments": sum(len(m["segments"]) for m in members),
            "site_day_groups": len(unique), "support": support.tolist(),
            "added_interpolated_endpoints_1_9s": added_interpolation.tolist(),
            "msd": stats(curves), "local_h": stats(h), "fit_10_10000": stats(fit),
            "identity": identity, "fingerprint": fingerprint,
            "validation": "All per-flight thesis MSD points and full-cohort fit reproduced; support monotone and constant from 10 s"}


if __name__ == "__main__":
    results = {slug: measure(slug) for slug in ("hang", "para")}
    report = {"lags_s": ALL_LAGS.tolist(), "results": results,
              "cohort": "Published C_10000; cadence-limited support only below 10 s",
              "short_rule": "dt_native <= tau; native origins; endpoint interpolation within each selected segment span",
              "long_rule": "Published 10 s grid and exact fixed flights/segments, with additional evaluated multiples of 10 s",
              "local_h": "half OLS log-log slope within +/-0.25 dex; nearest three measured lags if sparse, including endpoints",
              "local_h_windows_s": slope_operator(ALL_LAGS)[1],
              "short_slope_caveat": "Below 10 s and in windows crossing 10 s, slope includes changes in cadence composition",
              "bootstrap": "Original 1000 coupled archive site-day draws; 5th and 95th percentiles",
              "fit": "Original 33 lags over 10-10000 s; unchanged published fits",
              "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    (HERE / "cadence-support-report.json").write_text(json.dumps(report, indent=2)+"\n")
    print("Saved cadence-support-report.json", flush=True)
