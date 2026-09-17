"""Measure Chapter 3 with fixed segments and one coupled equal-flight bootstrap.

Stages are restartable. Curves and bootstrap draws on SSD suffice for redraw;
large increment arrays exist only as one-lag scratch files and are then removed.
"""

from __future__ import annotations

# ruff: noqa: E402 -- direct checkout execution after adding src/ to sys.path
import argparse
import hashlib
import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "src"))
from soaring.analysis.observables.archive_diagnostics import DiskFrames
from soaring.analysis.observables.fixed_bootstrap import (
    bootstrap_means,
    cluster_draws,
    mixture_quantiles,
)
from soaring.analysis.observables.fixed_transport import (
    COHORT_LIMITS,
    GENERAL_LAGS,
    LAGS,
    ORDERS,
    PROBABILITIES,
    centred_excess,
    cohort_manifest,
    increments,
)
from soaring.analysis.observables.global_diagnostics import declared_task_class
from soaring.analysis.observables.transport import time_averaged_msd
from soaring.analysis.stats.bootstrap import cluster_labels
from soaring.reporting import DISCIPLINES

BANDS = ("Plains", "Hills", "Low mountains", "High mountains")


def write_json(path, value):
    """Publish finite JSON through an atomic rename."""

    def encode(x):
        if isinstance(x, np.ndarray):
            return x.tolist()
        if isinstance(x, np.generic):
            return x.item()
        if isinstance(x, Path):
            return str(x)
        raise TypeError(type(x))

    temp = path.with_suffix(".tmp")
    temp.write_text(json.dumps(value, indent=2, default=encode) + "\n")
    temp.replace(path)


def prepare(g, frames, out, n_resamples):
    """Join identities once and persist the shared bootstrap design."""
    cat = pd.read_csv(
        g.catalog_path(), dtype={"flight_id": str}, low_memory=False
    ).set_index("flight_id")
    meta = pd.read_parquet(g.config().derived_dir / "flights_meta.parquet").set_index(
        "flight_id"
    )
    meta.index = meta.index.astype(str)
    ids = [r["flight_id"] for r in frames.rows]
    tab = cat.reindex(ids)[
        ["date", "takeoff", "dept", "flight_type", "wing_class", "wing"]
    ].reset_index()
    for col in ["lat0", "lon0", "alt0", "duration_flight_s", "dt_native_s"]:
        tab[col] = meta.reindex(ids)[col].to_numpy()
    tab["task"] = tab.flight_type.map(declared_task_class)
    tab["altitude_band"] = pd.cut(
        tab.alt0, [-np.inf, 300, 800, 1500, np.inf], labels=BANDS, right=False
    ).astype("string")
    date = (
        pd.to_datetime(tab.date, errors="coerce")
        .dt.strftime("%Y-%m-%d")
        .astype("string")
    )
    site = tab.takeoff.astype("string").str.strip().str.casefold()
    missing = (
        site.isna()
        | site.isin(
            ["", "unknown", "inconnu", "non renseigne", "non renseigné", "autre"]
        )
        | date.isna()
    )
    key = site + " | " + tab.dept.astype("string").fillna("")
    tab["cluster_site"] = key.mask(missing)
    tab["cluster_date"] = date.mask(missing)
    tab["cluster_missing"] = missing
    tab["cluster"] = cluster_labels(
        pd.DataFrame({"takeoff": tab.cluster_site, "date": tab.cluster_date}),
        "day_site",
    )
    for limit in COHORT_LIMITS:
        manifest = cohort_manifest(frames.rows, limit)
        write_json(out / f"cohort-{limit}.json", manifest)
        members = {r["flight_id"] for r in manifest["members"]}
        tab[f"cohort_{limit}"] = tab.flight_id.isin(members)
    tab.to_parquet(out / "flights.parquet", index=False)
    draws = cluster_draws(tab.cluster.to_numpy(), n_resamples)
    np.save(out / "cluster-draws.npy", draws)
    print(f"{g.slug}: {len(tab)} eligible flights, {draws.shape[1]} groups", flush=True)
    return tab, draws


def msd_stage(frames, tab, draws, out):
    """FFT segment curves pooled by available origin counts inside each flight."""
    lags = GENERAL_LAGS[GENERAL_LAGS >= 10].astype(int)
    values = np.full((len(frames), 4, len(lags)), np.nan)
    for f, (row, pos) in enumerate(frames):
        sums = np.zeros((4, len(lags)))
        counts = np.zeros_like(sums)
        for a, b in row["segments"]:
            duration = (b - a - 1) * 10
            curve = time_averaged_msd(pos[a:b, 0], pos[a:b, 1], 10)
            k = lags // 10
            support = lags <= 0.8 * duration + 1e-9
            for c, limit in enumerate((None, *COHORT_LIMITS)):
                use = support.copy()
                if limit is not None:
                    use &= (duration * 0.8 >= limit - 1e-9) & (lags <= limit)
                kk = k[use]
                n = b - a - kk
                sums[c, use] += curve[kk] * n
                counts[c, use] += n
        values[f] = np.divide(
            sums, counts, out=np.full_like(sums, np.nan), where=counts > 0
        )
        if (f + 1) % 10000 == 0:
            print(f"MSD {f + 1}/{len(frames)}", flush=True)
    np.save(out / "flight-msd.npy", values)
    curves = bootstrap_means(values, tab.cluster.to_numpy(), draws)
    fields = {
        "lags": lags,
        "curves": curves,
        "support": np.isfinite(values).sum(axis=0),
    }
    # Preserve exact same bootstrap multiplicities for every circuit/altitude cell.
    for task in ("open", "closed"):
        for i, band in enumerate(BANDS):
            keep = (
                (tab.task.eq(task) & tab.altitude_band.eq(band))
                .fillna(False)
                .to_numpy(dtype=bool)
            )
            fields[f"{task}_{i}"] = bootstrap_means(
                values[keep, 3], tab.cluster.to_numpy()[keep], draws
            )
            fields[f"{task}_{i}_n"] = np.isfinite(values[keep, 3]).sum(axis=0)
    np.savez_compressed(out / "msd.npz", **fields)


def scaling_lag(frames, tab, draws, cohort, lag, out, bins):
    """Moments and signed kurtosis share every origin with weighted quantiles."""
    members = cohort["members"]
    indices = np.array([r["frame_index"] for r in members])
    spans = [[(s["start"], s["stop"]) for s in r["segments"]] for r in members]
    k = int(lag // 10)
    sizes = np.array([sum(b - a - k for a, b in ranges) for ranges in spans])
    offsets = np.r_[0, np.cumsum(sizes)]
    labels = tab.cluster.to_numpy()[indices]
    scratch = out / f".increments-{lag}.npy"
    values = np.lib.format.open_memmap(
        scratch, mode="w+", dtype="float64", shape=(3, int(sizes.sum()))
    )
    means = np.empty((len(indices), 3, len(ORDERS)))
    signed = np.empty((len(indices), 2, 4))
    started = time.monotonic()
    for first in range(0, len(indices), 512):
        last = min(first + 512, len(indices))
        xy = np.concatenate(
            [
                increments(frames[int(indices[f])][1], spans[f], k)
                for f in range(first, last)
            ]
        )
        starts = offsets[first:last] - offsets[first]
        number = sizes[first:last]
        amplitudes = (np.abs(xy[:, 0]), np.abs(xy[:, 1]), np.hypot(xy[:, 0], xy[:, 1]))
        for coordinate, x in enumerate(amplitudes):
            values[coordinate, offsets[first] : offsets[last]] = x
            half = np.sqrt(x)
            quarter = np.sqrt(half)
            square = x * x
            cube = square * x
            powers = (
                quarter,
                half,
                quarter * half,
                x,
                x * half,
                square,
                square * half,
                cube,
                cube * half,
                square * square,
            )
            for j, power in enumerate(powers):
                means[first:last, coordinate, j] = (
                    np.add.reduceat(power, starts) / number
                )
        for c in range(2):
            signed[first:last, c, 0] = np.add.reduceat(xy[:, c], starts) / number
            signed[first:last, c, 1] = means[first:last, c, 5]
            signed[first:last, c, 2] = (
                np.add.reduceat(xy[:, c] ** 2 * xy[:, c], starts) / number
            )
            signed[first:last, c, 3] = means[first:last, c, 9]
    values.flush()
    moment_draws = bootstrap_means(means, labels, draws)
    signed_draws = bootstrap_means(signed, labels, draws)
    kurtosis = centred_excess(signed_draws)
    quantiles = np.empty((len(draws), 3, len(PROBABILITIES)))
    for c in range(3):
        quantiles[:, c] = mixture_quantiles(
            values[c], sizes, labels, draws, PROBABILITIES, bins=bins
        )
        print(
            f"lag {lag}: quantiles {c + 1}/3, {time.monotonic() - started:.1f}s",
            flush=True,
        )
    q2 = int(np.flatnonzero(ORDERS == 2)[0])
    np.testing.assert_allclose(
        moment_draws[:, 2, q2],
        moment_draws[:, 0, q2] + moment_draws[:, 1, q2],
        rtol=1e-12,
    )
    target = out / f"lag-{lag}.npz"
    np.savez_compressed(
        target.with_suffix(".partial.npz"),
        moments=moment_draws,
        quantiles=quantiles,
        kurtosis=kurtosis,
        signed_moments=signed_draws,
        origins=sizes,
        flight_indices=indices,
        cohort_sha256=cohort["sha256"],
        lag=lag,
    )
    target.with_suffix(".partial.npz").replace(target)
    del values
    scratch.unlink()
    print(
        f"lag {lag}: complete; {sizes.sum()} increments; "
        f"{time.monotonic() - started:.1f}s",
        flush=True,
    )


def main():
    """Run or resume one discipline with explicit stage and output directory."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument(
        "--coordinates",
        type=Path,
        default=Path(
            "/Volumes/SSD_DISANTE/derived-audit/runs/20260911T213634Z-7b7367f1/arrays"
        ),
    )
    parser.add_argument("--discipline", choices=["para", "hang"], required=True)
    parser.add_argument(
        "--stage", choices=["prepare", "msd", "scaling", "all"], default="all"
    )
    parser.add_argument("--resamples", type=int, default=1000)
    parser.add_argument("--bins", type=int, default=1024)
    parser.add_argument("--lags", type=int, nargs="+")
    args = parser.parse_args()
    g = next(g for g in DISCIPLINES.values() if g.slug == args.discipline)
    frames = DiskFrames(args.coordinates / f"ch3-full-{g.slug}")
    out = args.out / g.slug
    out.mkdir(parents=True, exist_ok=True)
    audit_path = out / "input-audit.json"
    if audit_path.exists():
        audit = json.loads(audit_path.read_text())
        if audit["status"] != "passed":
            raise ValueError("Coordinate audit has not passed")
        for record in audit["inputs"].values():
            stat = Path(record["path"]).stat()
            if (stat.st_size, stat.st_mtime_ns) != (record["size"], record["mtime_ns"]):
                raise ValueError(
                    f"Changed input; use a fresh output run: {record['path']}"
                )
    if not (out / "flights.parquet").exists():
        tab, draws = prepare(g, frames, out, args.resamples)
    else:
        tab = pd.read_parquet(out / "flights.parquet")
        draws = np.load(out / "cluster-draws.npy", mmap_mode="r")
        assert draws.shape[0] == args.resamples + 1
        assert tab.flight_id.tolist() == [r["flight_id"] for r in frames.rows]
        for limit in COHORT_LIMITS:
            saved = json.loads((out / f"cohort-{limit}.json").read_text())
            if saved["sha256"] != cohort_manifest(frames.rows, limit)["sha256"]:
                raise ValueError("Saved cohort disagrees with current segment contract")
    if args.stage == "prepare":
        return
    if args.stage in ("msd", "all") and not (out / "msd.npz").exists():
        msd_stage(frames, tab, draws, out)
    if args.stage in ("scaling", "all"):
        cohort = json.loads((out / "cohort-10000.json").read_text())
        for lag in args.lags or LAGS:
            if lag not in LAGS:
                raise ValueError("Lag is not on the common grid")
            if (out / f"lag-{lag}.npz").exists():
                with np.load(out / f"lag-{lag}.npz") as cached:
                    if str(cached["cohort_sha256"]) != cohort["sha256"]:
                        raise ValueError("Cached lag has a different cohort")
                    if cached["moments"].shape != (len(draws), 3, len(ORDERS)):
                        raise ValueError("Cached lag has a different bootstrap design")
                continue
            scaling_lag(frames, tab, draws, cohort, int(lag), out, args.bins)
    sources = [
        Path(__file__),
        Path(__file__).with_name("prepare_ch3_native.py"),
        Path(__file__).with_name("audit_ch3_inputs.py"),
        ROOT / "src/soaring/analysis/observables/fixed_transport.py",
        ROOT / "src/soaring/analysis/observables/fixed_bootstrap.py",
    ]
    write_json(
        out / "measurement-provenance.json",
        {
            "coordinates": frames.directory,
            "resamples": args.resamples,
            "seed": 20260917,
            "lags": LAGS,
            "q": ORDERS,
            "probabilities": PROBABILITIES,
            "code_sha256": {
                str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
                for p in sources
            },
        },
    )


if __name__ == "__main__":
    main()
