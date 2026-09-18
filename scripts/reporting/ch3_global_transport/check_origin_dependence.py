"""Test whether the fixed-cohort increment law depends on the origin's position.

Within each selected segment the admissible origins are split into three equal
contiguous blocks. The early and late blocks always hold the same number of
origins, so every cohort flight contributes to both and the late/early ratio is
paired inside the saved site-day bootstrap draws. Under stationary increments
that ratio is one at every lag.

The published run is read only. Pooling all three blocks must reproduce the
archived equal-flight moments exactly; that identity is checked before any
contrast is reported.
"""

from __future__ import annotations

# ruff: noqa: E402 -- support direct execution from the checkout
import argparse
import hashlib
import json
import shutil
import sys
import time
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "src"))
from soaring.analysis.observables.archive_diagnostics import DiskFrames
from soaring.analysis.observables.fixed_bootstrap import bootstrap_means
from soaring.analysis.observables.fixed_transport import (
    FIT_RANGES,
    GRID_S,
    LAGS,
    ORDERS,
    log_fit,
)
from soaring.analysis.observables.origin_dependence import (
    BLOCKS,
    STATISTICS,
    flight_statistics,
    interval,
    ratio_statistics,
)

PREFIX = "ch3_transport_origin_dependence"
NAMES = {"para": "Paragliders", "hang": "Hang gliders"}
COLORS = {"para": "#0072B2", "hang": "#D55E00"}
# Radial coordinate and the q = 1, 2 columns of the archived moment spectrum.
RADIAL = 2
PUBLISHED_ORDERS = tuple(int(np.flatnonzero(q == ORDERS)[0]) for q in (1, 2))
# H from a fitted log slope: the first moment carries H, the second 2H.
EXPONENT_DIVISOR = {"m1": 1.0, "m2": 2.0}


def signature(path):
    """Fingerprint a source file without modifying the published run."""
    with Path(path).open("rb") as stream:
        digest = hashlib.file_digest(stream, "sha256").hexdigest()
    return {
        "path": str(Path(path).resolve()),
        "bytes": Path(path).stat().st_size,
        "sha256": digest,
    }


def load_cohort(data, slug):
    """Validate the cohort manifest and return its flights, segments and draws."""
    directory = data / slug
    frame = pd.read_parquet(directory / "flights.parquet")
    if frame.flight_id.duplicated().any():
        raise ValueError("Flight identities must be unique")
    manifest = json.loads((directory / "cohort-10000.json").read_text())
    digest = manifest.pop("sha256")
    if (
        hashlib.sha256(json.dumps(manifest, sort_keys=True).encode()).hexdigest()
        != digest
    ):
        raise ValueError("Invalid cohort manifest hash")
    if manifest["grid_s"] != GRID_S:
        raise ValueError("Cohort manifest uses a different time grid")
    members = manifest["members"]
    indices = np.array([m["frame_index"] for m in members], dtype=int)
    cohort = frame.cohort_10000.to_numpy(dtype=bool)
    np.testing.assert_array_equal(np.flatnonzero(cohort), indices)
    np.testing.assert_array_equal(
        frame.flight_id.iloc[indices].astype(str), [m["flight_id"] for m in members]
    )
    spans = [[(s["start"], s["stop"]) for s in m["segments"]] for m in members]
    labels = frame.cluster.to_numpy(dtype=int)[indices]
    draws = np.load(directory / "cluster-draws.npy", mmap_mode="r")
    if draws.shape[1] != frame.cluster.max() + 1:
        raise ValueError("Archived draws and cluster identities differ")
    provenance = {
        name: signature(directory / name)
        for name in ("flights.parquet", "cluster-draws.npy", "cohort-10000.json")
    }
    provenance["cohort_sha256"] = digest
    return members, indices, spans, labels, draws, provenance


def block_values(frames, indices, spans, lags):
    """Measure every cohort flight once, looping lags inside its own positions."""
    steps = np.asarray(lags, dtype=int) // GRID_S
    means = np.full((len(indices), len(BLOCKS), len(STATISTICS), len(lags)), np.nan)
    counts = np.zeros((len(indices), len(BLOCKS), len(lags)))
    times = np.full((len(indices), len(BLOCKS), len(lags)), np.nan)
    started = time.monotonic()
    for f, index in enumerate(indices):
        _, mapped = frames[int(index)]
        positions = np.asarray(mapped)
        for j, step in enumerate(steps):
            piece = flight_statistics(positions, spans[f], int(step))
            if piece is None:
                continue
            means[f, :, :, j], counts[f, :, j], times[f, :, j] = piece
        if (f + 1) % 5000 == 0:
            print(
                f"  flights {f + 1}/{len(indices)}, {time.monotonic() - started:.1f}s",
                flush=True,
            )
    return means, counts, times * GRID_S


def check_against_published(data, slug, means, counts, labels, draws, lags):
    """Pooling the three blocks must rebuild the archived equal-flight moments."""
    total = counts.sum(axis=1)
    pooled = np.einsum("fbsl,fbl->fsl", means, counts) / total[:, None, :]
    replicates = bootstrap_means(pooled, labels, draws)
    checked = []
    for j, lag in enumerate(lags):
        path = data / slug / f"lag-{lag}.npz"
        if not path.exists():
            continue
        with np.load(path) as cached:
            published = cached["moments"][:, RADIAL][:, list(PUBLISHED_ORDERS)]
        np.testing.assert_allclose(
            replicates[..., j], published, rtol=1e-9, atol=0, equal_nan=False
        )
        checked.append(int(lag))
    if not checked:
        raise ValueError("No archived lag file was available for verification")
    return {"verified_lags_s": checked, "statistic": "equal-flight radial M1 and M2"}


def exponents(replicates, lags):
    """Fit H separately in each block, over every published fit interval."""
    out = {}
    for low, high in FIT_RANGES:
        fits = log_fit(lags, replicates, (low, high))
        for s, name in enumerate(STATISTICS):
            hurst = fits["slope"][:, :, s] / EXPONENT_DIVISOR[name]
            summary = {
                block: {
                    k: v
                    for k, v in interval(hurst[:, b]).items()
                    if k != "excludes_one"
                }
                for b, block in enumerate(BLOCKS)
            }
            difference = (
                hurst[:, BLOCKS.index("late")] - hurst[:, BLOCKS.index("early")]
            )
            bounds = np.nanquantile(difference[1:], [0.025, 0.975])
            summary["late_minus_early"] = {
                "point": difference[0],
                "lower": bounds[0],
                "upper": bounds[1],
                "excludes_zero": bool(bounds[0] > 0 or bounds[1] < 0),
            }
            out[f"{name}_{low}_{high}"] = summary
    return out


def measure(data, coords, out, lags, disciplines):
    """Run both disciplines from immutable caches and save replicate curves."""
    report = {
        "status": "complete",
        "scope": "Diagnostic only; published intervals are not replaced",
        "cohort": "10000 s; fixed flights and retained segments",
        "split": "three contiguous equal blocks of a segment's admissible origins",
        "pairing": "early and late blocks hold identical origin counts per segment",
        "null_hypothesis": "stationary increments give a late/early ratio of one",
        "interpretation": (
            "A resolved departure refutes increment stationarity for these "
            "segments without identifying a mechanism"
        ),
        "lags_s": [int(x) for x in lags],
        "statistics": list(STATISTICS),
        "blocks": list(BLOCKS),
        "units": {"m1": "m", "m2": "m^2", "lever_arm": "s"},
        "results": {},
    }
    for slug in disciplines:
        members, indices, spans, labels, draws, provenance = load_cohort(data, slug)
        directory = Path(coords) / f"ch3-full-{slug}"
        frames = DiskFrames(directory)
        if len(frames.rows) <= int(indices.max()):
            raise ValueError("Coordinate store is smaller than the cohort indices")
        np.testing.assert_array_equal(
            [str(frames.rows[int(i)]["flight_id"]) for i in indices],
            [m["flight_id"] for m in members],
        )
        print(f"{slug}: {len(indices)} cohort flights", flush=True)
        means, counts, times = block_values(frames, indices, spans, lags)
        if not np.isfinite(means).all():
            raise ValueError("Every cohort flight must support all three blocks")
        verification = check_against_published(
            data, slug, means, counts, labels, draws, lags
        )
        replicates = bootstrap_means(means, labels, draws)
        ratios = ratio_statistics(replicates)
        lever = times[:, BLOCKS.index("late")] - times[:, BLOCKS.index("early")]
        report["results"][slug] = {
            "provenance": provenance,
            "coordinates": signature(directory / "positions.bin"),
            "flights": len(indices),
            "resamples": len(draws) - 1,
            "verification": verification,
            "lever_arm_s": {
                "mean": lever.mean(axis=0).tolist(),
                "minimum": lever.min(axis=0).tolist(),
            },
            "origins_per_block": counts[:, BLOCKS.index("early")].sum(axis=0).tolist(),
            "ratio": {
                name: {
                    key: value.tolist() if hasattr(value, "tolist") else value
                    for key, value in interval(ratios[:, s]).items()
                }
                for s, name in enumerate(STATISTICS)
            },
            "exponents": exponents(replicates, lags),
        }
        np.savez_compressed(
            out / f"{slug}-replicates.npz",
            lags=np.asarray(lags),
            block_means=replicates,
            ratios=ratios,
            lever_arm_s=lever,
        )
    return report


def portable(value):
    """Convert numpy containers so the report serialises without NaN."""
    if isinstance(value, dict):
        return {k: portable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [portable(v) for v in value]
    if isinstance(value, np.ndarray):
        return portable(value.tolist())
    if isinstance(value, np.generic):
        value = value.item()
    if isinstance(value, float) and not np.isfinite(value):
        return None
    return value


def render(report, out):
    """Draw the paired contrast, write the audit CSV and the numerical prose."""
    if report.get("status") != "complete":
        raise ValueError("Refusing to render an incomplete report")
    lags = np.asarray(report["lags_s"], dtype=float)
    plt.rcParams.update(
        {
            "font.family": "serif",
            "font.size": 9,
            "axes.labelsize": 9,
            "legend.fontsize": 8,
            "pdf.fonttype": 42,
        }
    )
    fig, axs = plt.subplots(2, 2, figsize=(7.1, 5.1), layout="constrained")
    rows, macros = [], {}
    for slug in report["results"]:
        result = report["results"][slug]
        color = COLORS[slug]
        for ax, name, title in zip(
            axs.flat[:2],
            STATISTICS,
            (r"$M_1$ ratio: late / early", r"$M_2$ ratio: late / early"),
            strict=True,
        ):
            band = result["ratio"][name]
            point = np.array(band["point"], dtype=float)
            lower = np.array(band["lower"], dtype=float)
            upper = np.array(band["upper"], dtype=float)
            ax.plot(lags, point, color=color, linewidth=1.2, label=NAMES[slug])
            ax.fill_between(lags, lower, upper, color=color, alpha=0.2, linewidth=0)
            ax.set_title(title)
            ax.set_ylabel("Ratio")
        axs[1, 0].plot(
            lags,
            np.array(result["lever_arm_s"]["mean"], dtype=float),
            color=color,
            linewidth=1.2,
        )
        for name in STATISTICS:
            band = result["ratio"][name]
            for j, lag in enumerate(report["lags_s"]):
                rows.append(
                    {
                        "discipline": slug,
                        "statistic": name,
                        "lag_s": lag,
                        "ratio": band["point"][j],
                        "lower": band["lower"][j],
                        "upper": band["upper"][j],
                        "excludes_one": bool(band["excludes_one"][j]),
                        "lever_arm_s": result["lever_arm_s"]["mean"][j],
                        "origins_early": result["origins_per_block"][j],
                    }
                )
        key = f"m2_{FIT_RANGES[0][0]}_{FIT_RANGES[0][1]}"
        block_h = result["exponents"][key]
        offsets = {"para": -0.18, "hang": 0.18}
        for b, block in enumerate(BLOCKS):
            entry = block_h[block]
            axs[1, 1].errorbar(
                b + offsets[slug],
                entry["point"],
                yerr=[
                    [entry["point"] - entry["lower"]],
                    [entry["upper"] - entry["point"]],
                ],
                color=color,
                marker="o",
                markersize=3.5,
                capsize=3,
                linewidth=1,
            )
        band = result["ratio"]["m2"]
        resolved = int(np.sum(band["excludes_one"]))
        extreme = int(np.argmax(np.abs(np.array(band["point"], dtype=float) - 1)))
        delta = block_h["late_minus_early"]
        stem = f"ChThree{slug.capitalize()}Origin"
        macros.update(
            {
                f"{stem}Resolved": str(resolved),
                f"{stem}Peak": f"{band['point'][extreme]:.3f}",
                f"{stem}PeakInterval": (
                    f"{band['lower'][extreme]:.3f}--{band['upper'][extreme]:.3f}"
                ),
                f"{stem}PeakLag": str(report["lags_s"][extreme]),
                f"{stem}PeakLever": f"{result['lever_arm_s']['mean'][extreme]:.0f}",
                f"{stem}DeltaH": f"{delta['point']:.4f}",
                f"{stem}DeltaHLow": f"{delta['lower']:.4f}",
                f"{stem}DeltaHHigh": f"{delta['upper']:.4f}",
            }
        )
    for ax in axs.flat[:2]:
        ax.axhline(1, color="0.45", linewidth=0.8, linestyle="--")
        ax.set_xscale("log")
        ax.set_xlabel(r"Lag $\tau$ (s)")
    axs[1, 0].set_xscale("log")
    axs[1, 0].set_yscale("log")
    axs[1, 0].set_xlabel(r"Lag $\tau$ (s)")
    axs[1, 0].set_ylabel("Mean origin separation (s)")
    axs[1, 0].set_title("Lever arm of the contrast")
    axs[1, 1].set_xticks(range(len(BLOCKS)), [b.capitalize() for b in BLOCKS])
    axs[1, 1].set_ylabel(r"$H$: fit over 10--10000 s")
    axs[1, 1].set_title("Exponent by origin block")
    for ax in axs.flat:
        ax.grid(axis="y", color="0.9", linewidth=0.6)
        ax.spines[["top", "right"]].set_visible(False)
    axs[0, 0].legend(frameon=False)
    fig.savefig(
        out / f"{PREFIX}.pdf",
        bbox_inches="tight",
        metadata={"CreationDate": None, "ModDate": None},
    )
    plt.close(fig)
    pd.DataFrame(rows).to_csv(out / f"{PREFIX}.csv", index=False)
    # The chapter prose is hand-written; only these values are generated.
    (out / f"{PREFIX}_values.tex").write_text(
        f"% Generated by {Path(__file__).name}\n"
        + "\n".join(
            f"\\newcommand{{\\{name}}}{{{value}}}"
            for name, value in sorted(macros.items())
        )
        + "\n"
    )


def main():
    """Measure from the published run and the coordinate store, or redraw."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, help="Published Chapter 3 fixed run")
    parser.add_argument("--coords", type=Path, help="Directory of ch3-full-<slug>")
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--publish", type=Path)
    parser.add_argument("--lags", nargs="+", type=int)
    parser.add_argument(
        "--disciplines", nargs="+", choices=sorted(NAMES), default=sorted(NAMES)
    )
    parser.add_argument("--redraw", action="store_true")
    args = parser.parse_args()
    lags = np.asarray(args.lags if args.lags else LAGS, dtype=int)
    if np.any(lags % GRID_S) or len(np.unique(lags)) != len(lags):
        parser.error("--lags must be distinct multiples of the 10 s grid")
    if args.redraw:
        report = json.loads((args.out / "report.json").read_text())
    else:
        if args.data is None or args.coords is None:
            parser.error("--data and --coords are required for measurement")
        if (
            args.out.resolve() == args.data.resolve()
            or args.data.resolve() in args.out.resolve().parents
        ):
            parser.error("Use a separate output directory outside the published run")
        if (args.out / "report.json").exists():
            parser.error("Report exists; use --redraw or a fresh output directory")
        args.out.mkdir(parents=True, exist_ok=True)
        report = measure(
            args.data,
            args.coords,
            args.out,
            lags,
            list(dict.fromkeys(args.disciplines)),
        )
        report["code"] = signature(Path(__file__))
        report["analysis_code"] = signature(
            ROOT / "src/soaring/analysis/observables/origin_dependence.py"
        )
        (args.out / "report.json").write_text(
            json.dumps(portable(report), indent=2) + "\n"
        )
    render(report, args.out)
    if args.publish:
        args.publish.mkdir(parents=True, exist_ok=True)
        for suffix in (".pdf", ".csv", "_values.tex"):
            shutil.copy2(args.out / f"{PREFIX}{suffix}", args.publish)
        shutil.copy2(args.out / "report.json", args.publish / f"{PREFIX}.json")


if __name__ == "__main__":
    main()
