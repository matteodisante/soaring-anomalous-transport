"""Reduce saved Chapter 3 measurements into a standalone, immediate-redraw report."""

from __future__ import annotations

# ruff: noqa: E402
import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.spatial import cKDTree

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "src"))
from soaring.analysis.observables.fixed_bootstrap import bootstrap_means
from soaring.analysis.observables.fixed_transport import (
    FIT_RANGES,
    GENERAL_LAGS,
    LAGS,
    ORDERS,
    PROBABILITIES,
    local_slopes,
    log_fit,
)


def portable(value):
    """Convert arrays and nonfinite missing estimates to strict JSON."""
    if isinstance(value, np.ndarray) and value.ndim == 0:
        return portable(value.item())
    if isinstance(value, dict):
        return {str(k): portable(v) for k, v in value.items()}
    if isinstance(value, (tuple, list, np.ndarray)):
        return [portable(v) for v in value]
    if isinstance(value, np.generic):
        value = value.item()
    if isinstance(value, float) and not np.isfinite(value):
        return None
    return value


def summary(draws):
    """Observed estimate and central 90% pointwise percentile interval."""
    draws = np.asarray(draws)
    flat = draws[1:].reshape(len(draws) - 1, -1)
    valid = np.isfinite(flat).any(axis=0)
    band = np.full((2, flat.shape[1]), np.nan)
    band[:, valid] = np.nanpercentile(flat[:, valid], [5, 95], axis=0)
    low, high = band.reshape((2, *draws.shape[1:]))
    return {"point": draws[0], "low": low, "high": high}


def fit_summary(lags, curves, interval):
    """Refit every bootstrap curve with the same OLS lag weights."""
    fit = log_fit(lags, curves, interval)
    return {
        "exponent": summary(fit["slope"]),
        "hurst": summary(fit["slope"] / 2),
        "intercept": summary(fit["intercept"]),
        "rms_dex": summary(fit["rms_dex"]),
        "interval_s": interval,
        "lag_count": fit["lag_count"],
    }


def clusters_info(frame):
    """Describe cluster size and observed separation without asserting independence."""
    groups = frame.groupby("cluster", sort=True)
    sizes = groups.size()
    valid = frame.loc[~frame.cluster_missing]
    locations = valid.groupby("cluster").agg(
        site=("cluster_site", "first"),
        date=("cluster_date", "first"),
        lat=("lat0", "median"),
        lon=("lon0", "median"),
    )
    distances = []
    compared = 0
    for _, day in locations.groupby("date"):
        day = day.dropna(subset=["lat", "lon"])
        if len(day) < 2:
            continue
        lat, lon = np.deg2rad(day.lat), np.deg2rad(day.lon)
        sphere = np.column_stack(
            (np.cos(lat) * np.cos(lon), np.cos(lat) * np.sin(lon), np.sin(lat))
        )
        chord = cKDTree(sphere).query(sphere, k=2)[0][:, 1]
        distances.extend(2 * 6371 * np.arcsin(np.minimum(chord / 2, 1)))
        compared += len(day)
    gaps = []
    for _, site in locations.groupby("site"):
        dates = np.sort(
            pd.to_datetime(site.date).to_numpy().astype("datetime64[D]").astype(int)
        )
        gaps.extend(np.diff(dates).tolist())

    def describe(x):
        return {
            "n": len(x),
            "p10_median_p90": np.percentile(x, [10, 50, 90]) if len(x) else [None] * 3,
        }

    return {
        "flights": len(frame),
        "groups": len(sizes),
        "sites": valid.cluster_site.nunique(),
        "dates": valid.cluster_date.nunique(),
        "missing_key_flights": int(frame.cluster_missing.sum()),
        "size_min_median_p95_max": np.percentile(sizes, [0, 50, 95, 100]),
        "largest_group_flight_fraction": sizes.max() / len(frame),
        "same_day_nearest_km": describe(distances),
        "groups_without_same_day_neighbour": len(sizes) - compared,
        "previous_observed_day_gap": describe(gaps),
        "groups_without_previous_observed_day": len(sizes) - len(gaps),
    }


def reduce_discipline(directory):
    """Check cohort identity across every lag and assemble curves and fit statistics."""
    tab = pd.read_parquet(directory / "flights.parquet")
    draws = np.load(directory / "cluster-draws.npy", mmap_mode="r")
    with np.load(directory / "msd.npz") as saved:
        msd = {k: saved[k] for k in saved.files}
    m_lags = msd["lags"]
    common = np.searchsorted(m_lags, LAGS)
    m = msd["curves"]
    flight_msd = np.load(directory / "flight-msd.npy", mmap_mode="r")
    labels = tab.cluster.to_numpy()
    group_support = np.array(
        [
            [
                len(np.unique(labels[np.isfinite(flight_msd[:, c, j])]))
                for j in range(len(m_lags))
            ]
            for c in range(4)
        ]
    )
    msd_band = summary(m)
    for key in ("low", "high"):
        msd_band[key][group_support < 20] = np.nan
    output = {
        "eligible_flights": len(tab),
        "eligible_task_counts": tab.task.value_counts().to_dict(),
        "bootstrap_groups": draws.shape[1],
        "resamples": len(draws) - 1,
        "lags": LAGS,
        "msd_lags": m_lags,
        "msd": msd_band,
        "msd_support": msd["support"],
        "msd_group_support": group_support,
        "cohorts": {},
        "groups": {},
        "fits": {},
    }
    audit = json.loads((directory / "input-audit.json").read_text())
    if audit["status"] != "passed":
        raise ValueError("Full coordinate verification is required before publication")
    for record in audit["inputs"].values():
        stat = Path(record["path"]).stat()
        if (stat.st_size, stat.st_mtime_ns) != (record["size"], record["mtime_ns"]):
            raise ValueError(f"Input changed since coordinate audit: {record['path']}")
    output["input_audit"] = audit
    for c, limit in enumerate((100, 1000, 10000), 1):
        manifest = json.loads((directory / f"cohort-{limit}.json").read_text())
        frame = tab.loc[tab[f"cohort_{limit}"]]
        output["cohorts"][str(limit)] = {
            "flights": len(frame),
            "segments": sum(len(r["segments"]) for r in manifest["members"]),
            "sha256": manifest["sha256"],
            "groups": frame.cluster.nunique(),
            "task_counts": frame.task.value_counts().to_dict(),
            "altitude_counts": frame.altitude_band.value_counts().to_dict(),
            "fit": fit_summary(m_lags, m[:, c], (10, limit)),
        }
    for c in (0, 1, 2):
        with np.errstate(divide="ignore", invalid="ignore"):
            ratio = m[:, c] / m[:, 3]
        output.setdefault("cohort_ratios", {})[str(c)] = summary(ratio)
    for interval in FIT_RANGES:
        key = f"{interval[0]}-{interval[1]}"
        output["fits"][key] = fit_summary(m_lags, m[:, 3], interval)
    output["fixed_local_h"] = summary(local_slopes(LAGS, m[:, 3, common]) / 2)
    for task in ("open", "closed"):
        for i, band in enumerate(
            ("Plains", "Hills", "Low mountains", "High mountains")
        ):
            key = f"{task}_{i}"
            keep = (tab.task.eq(task) & tab.altitude_band.eq(band)).fillna(False)
            frame = tab.loc[keep & tab.cohort_10000]
            output["groups"][key] = {
                "task": task,
                "altitude": band,
                "candidate_flights": int(keep.sum()),
                "flights": len(frame),
                "clusters": frame.cluster.nunique(),
                "curve": summary(msd[key][:, common]),
                "fit": fit_summary(LAGS, msd[key][:, common], (10, 10000)),
                "amplitude_10000_m2": summary(msd[key][:, common[-1]]),
            }
    contrasts = {}
    for i in range(4):
        a = log_fit(LAGS, msd[f"open_{i}"][:, common])["slope"] / 2
        b = log_fit(LAGS, msd[f"closed_{i}"][:, common])["slope"] / 2
        contrasts[f"open_minus_closed_{i}"] = summary(a - b)
    for task in ("open", "closed"):
        for i in (0, 1):
            for j in (2, 3):
                a = log_fit(LAGS, msd[f"{task}_{i}"][:, common])["slope"] / 2
                b = log_fit(LAGS, msd[f"{task}_{j}"][:, common])["slope"] / 2
                contrasts[f"{task}_{i}_minus_{j}"] = summary(a - b)
    output["hurst_contrasts"] = contrasts
    main = json.loads((directory / "cohort-10000.json").read_text())
    moments = []
    quantiles = []
    kurtosis = []
    origin_counts = []
    for tau in LAGS:
        with np.load(directory / f"lag-{tau}.npz") as row:
            assert str(row["cohort_sha256"]) == main["sha256"]
            np.testing.assert_array_equal(
                row["flight_indices"], [x["frame_index"] for x in main["members"]]
            )
            moments.append(row["moments"])
            quantiles.append(row["quantiles"])
            kurtosis.append(row["kurtosis"])
            origin_counts.append(int(row["origins"].sum()))
    moments = np.stack(moments, axis=1)
    quantiles = np.stack(quantiles, axis=1)
    kurtosis = np.stack(kurtosis, axis=1)
    q2 = int(np.flatnonzero(ORDERS == 2)[0])
    np.testing.assert_allclose(
        moments[:, :, 2, q2], m[:, 3, common], rtol=1e-9, atol=1e-5
    )
    output["moments"] = summary(moments)
    output["quantiles"] = summary(quantiles)
    output["kurtosis"] = summary(kurtosis)
    ratio = quantiles[:, :, :, 0] / quantiles[:, :, :, 3]
    output["quantile_ratio"] = summary(ratio)
    output["origin_counts"] = origin_counts
    output["scaling_fits"] = {}
    for interval in FIT_RANGES:
        qfit = log_fit(LAGS, np.moveaxis(quantiles, 1, -1), interval)
        spectrum = log_fit(LAGS, np.moveaxis(moments, 1, -1), interval)
        delta = qfit["slope"][:, :, 0] - qfit["slope"][:, :, 3]
        ratio_slope = log_fit(LAGS, np.moveaxis(ratio, 1, -1), interval)["slope"]
        np.testing.assert_allclose(delta, ratio_slope, atol=1e-12)
        zeta = spectrum["slope"]
        nu = (zeta * ORDERS).sum(axis=-1) / (ORDERS**2).sum()
        deviation = zeta - nu[:, :, None] * ORDERS
        output["scaling_fits"][f"{interval[0]}-{interval[1]}"] = {
            "quantile_h": summary(qfit["slope"]),
            "quantile_rms_dex": summary(qfit["rms_dex"]),
            "H25_minus_H90": summary(delta),
            "zeta": summary(zeta),
            "moment_rms_dex": summary(spectrum["rms_dex"]),
            "common_moment_h": summary(nu),
            "zeta_minus_qH": summary(deviation),
            "H4_minus_H025": summary(
                zeta[:, :, -1] / ORDERS[-1] - zeta[:, :, 0] / ORDERS[0]
            ),
        }
    np.savez_compressed(
        directory / "scaling-draws.npz",
        lags=LAGS,
        moments=moments,
        quantiles=quantiles,
        kurtosis=kurtosis,
        cohort_sha256=main["sha256"],
    )
    interp = pd.read_parquet(directory / "interpolation.parquet")
    output["interpolation"] = {}
    for label, limit in [
        ("eligible", None),
        ("100", 100),
        ("1000", 1000),
        ("10000", 10000),
    ]:
        part = interp.loc[interp.grid_points >= 2]
        if limit is not None:
            part = part.loc[part.grid_span_s * 0.8 >= limit - 1e-9]
        cols = [
            "native_fixes",
            "grid_points",
            "grid_exact",
            "grid_interpolated",
            "grid_exact_previously_interpolated",
            "native_interpolated",
        ]
        counts = {c: int(part[c].sum()) for c in cols}
        counts.update(flights=part.flight_id.nunique(), segments=len(part))
        if limit is not None:
            assert counts["flights"] == output["cohorts"][label]["flights"]
            assert counts["segments"] == output["cohorts"][label]["segments"]
        counts["new_interpolation_fraction"] = (
            counts["grid_interpolated"] / counts["grid_points"]
        )
        output["interpolation"][label] = counts
    output["cluster_diagnostics"] = clusters_info(tab.loc[tab.cohort_10000])
    with np.load(directory / "native.npz") as native:
        ids = native["flight_ids"]
        launch = native["launch"]
        short = native["short_tamsd"]
    good = np.isfinite(launch).sum(axis=0) > 0
    mean = np.full(len(GENERAL_LAGS), np.nan)
    scatter = np.full((3, len(GENERAL_LAGS)), np.nan)
    mean[good] = np.nanmean(launch[:, good], axis=0)
    scatter[:, good] = np.nanpercentile(launch[:, good], [5, 50, 95], axis=0)
    index = pd.Index(ids).get_indexer(tab.flight_id)
    assert np.all(index >= 0)
    short_draws = bootstrap_means(short[index], tab.cluster.to_numpy(), draws)
    general = np.concatenate((short_draws, m[:, 0]), axis=1)
    general_groups = np.r_[
        [len(np.unique(labels[np.isfinite(short[index, j])])) for j in range(9)],
        group_support[0],
    ]
    general_band = summary(general)
    for key in ("low", "high"):
        general_band[key][general_groups < 20] = np.nan
    output["general"] = {
        "lags": GENERAL_LAGS,
        "retained_flights": len(ids),
        "ensemble_mean": mean,
        "ensemble_p5_median_p95": scatter,
        "ensemble_support": np.isfinite(launch).sum(axis=0),
        "tamsd": general_band,
        "tamsd_group_support": general_groups,
        "minimum_groups_for_descriptive_band": 20,
        "tamsd_support": np.r_[
            np.isfinite(short[index]).sum(axis=0), msd["support"][0]
        ],
        "ensemble_local_h": local_slopes(GENERAL_LAGS, mean) / 2,
        "ensemble_median_local_h": local_slopes(GENERAL_LAGS, scatter[1]) / 2,
        "tamsd_local_h": summary(local_slopes(GENERAL_LAGS, general) / 2),
        "tamsd_global_fit": fit_summary(GENERAL_LAGS, general, (10, 10000)),
        "ensemble_global_fit": log_fit(GENERAL_LAGS, mean),
    }
    for limit in (100, 1000):
        output["cohorts"][str(limit)]["main_fit_on_same_range"] = fit_summary(
            m_lags, m[:, 3], (10, limit)
        )
    return output


def main():
    """Write plotting-ready strict JSON and retain the full bootstrap draws on SSD."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, required=True)
    args = parser.parse_args()
    results = {slug: reduce_discipline(args.data / slug) for slug in ("para", "hang")}
    report = {
        "status": "complete",
        "estimator": (
            "equal flight, all overlapping origins within fixed selected segments"
        ),
        "cohort_support_fraction": 0.8,
        "lags_s": LAGS,
        "orders": ORDERS,
        "probabilities": PROBABILITIES,
        "fit_ranges_s": FIT_RANGES,
        "bootstrap": {
            "resamples": results["para"]["resamples"],
            "seed": 20260917,
            "unit": "catalog date and normalized takeoff site + department",
            "percentiles": [5, 95],
            "nominal_pointwise_coverage": 0.9,
        },
        "results": results,
    }
    target = args.data / "report.json"
    temp = target.with_suffix(".tmp")
    temp.write_text(json.dumps(portable(report), indent=2, allow_nan=False) + "\n")
    temp.replace(target)
    print("Saved immediate-redraw report:", target, flush=True)


if __name__ == "__main__":
    main()
