"""Group verified native-grid flight TAMSDs by region and initial GNSS altitude."""

from __future__ import annotations

# ruff: noqa: E402 -- support direct execution from the checkout
import argparse
import hashlib
import json
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "src"))
from generate_duration_equipment import flight_curves, portable

from soaring.analysis.observables.grouped_tamsd import (
    clustered_summary,
    decade_slopes,
    mean_and_support,
)
from soaring.analysis.stats.bootstrap import cluster_labels
from soaring.reporting import DISCIPLINES
from soaring.reporting.style import PDF_METADATA, paper_style
from soaring.viewer.geography import (
    REGIONS,
    TERRAIN_BANDS,
    classify_region,
    classify_terrain,
)

GENERATED_OUTPUTS = (
    "ch3_tamsd_regions.pdf",
    "ch3_tamsd_altitude.pdf",
    "ch3_tamsd_region_altitude.pdf",
    "ch3_grouped_tamsd_values.tex",
    "ch3_grouped_tamsd.json",
)
COLORS = {
    "Alps": "#207f86",
    "Pyrenees": "#a04c42",
    "Channel Coast": "#a07a22",
    "Plains": "#3a7d34",
    "Hills": "#819b28",
    "Low mountains": "#d99a3d",
    "High mountains": "#8c2f2f",
}
MIN_FLIGHTS = 8


def digest(path):
    """Hash all bytes without loading an archive into memory."""
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def write(path, value):
    """Save complete finite JSON, with null for unsupported cells."""
    Path(path).write_text(json.dumps(portable(value), indent=2, allow_nan=False) + "\n")


def load_population(glider, directory, inputs, proof):
    """Reuse all identified segment curves and join one metadata row per flight."""
    paths = [
        directory / f"msd_{glider.slug}.npz",
        directory / f"msd_segments_{glider.slug}.parquet",
        glider.derived_dir("flights_meta.parquet") / "flights_meta.parquet",
        glider.catalog_path(),
    ]
    for path in paths:
        actual = digest(path)
        if (
            proof is not None
            and path in paths[:2]
            and proof.get(str(path.resolve())) != actual
        ):
            raise ValueError(
                f"TAMSD bytes differ from the verified completed run: {path}"
            )
        inputs[str(path.resolve())] = {"sha256": actual, "bytes": path.stat().st_size}
    with np.load(paths[0]) as archive:
        lags = archive["lags"]
        keep = (lags >= 10) & (lags <= 10000)
        samples = archive["time_averaged_samples"][:, keep]
        lags = lags[keep]
    segments = pd.read_parquet(paths[1])
    if len(segments) != len(samples):
        raise ValueError("Segment identities and curve rows differ")
    dt = segments.dt_s.to_numpy()
    k = np.rint(lags[None, :] / dt[:, None])
    expected = (
        (lags[None, :] >= dt[:, None])
        & (k >= 1)
        & (k <= segments.n_fixes.to_numpy()[:, None] // 2)
    )
    if not np.array_equal(np.isfinite(samples), expected):
        raise ValueError("Segment support differs from the recorded native-grid rule")
    frame, available = flight_curves(samples, segments, lags)
    # Fix the contributing segments as well as flights over the full lag range.
    long_segment = np.isfinite(samples[:, -1]) & (dt <= 10) & (dt > 0)
    fixed_frame, fixed_values = flight_curves(
        samples[long_segment], segments.loc[long_segment], lags
    )
    fixed = np.full_like(available, np.nan)
    indices = pd.Index(frame.flight_id).get_indexer(fixed_frame.flight_id)
    assert (indices >= 0).all() and np.isfinite(fixed_values).all()
    fixed[indices] = fixed_values
    metadata = pd.read_parquet(paths[2])
    metadata = metadata.loc[
        metadata.drop_reason.isna(), ["flight_id", "lat0", "lon0", "alt0"]
    ].copy()
    metadata["flight_id"] = metadata.flight_id.astype(str)
    frame = frame.merge(
        metadata, on="flight_id", how="left", validate="one_to_one", indicator=True
    )
    assert frame._merge.eq("both").all()
    frame = frame.drop(columns="_merge")
    catalog = pd.read_csv(
        paths[3], usecols=["flight_id", "date", "takeoff"], dtype={"flight_id": str}
    )
    frame = frame.merge(
        catalog, on="flight_id", how="left", sort=False, validate="one_to_one"
    )
    frame["date"] = pd.to_datetime(
        frame.date, format="%Y-%m-%d", errors="coerce"
    ).dt.strftime("%Y-%m-%d")
    frame["region"] = classify_region(frame.lat0.to_numpy(), frame.lon0.to_numpy())
    frame["altitude_band"] = classify_terrain(frame.alt0.to_numpy())
    keys = (
        frame[["date", "takeoff"]].astype("string").apply(lambda col: col.str.strip())
    )
    frame["missing_cluster_key"] = (keys.isna() | keys.eq("").fillna(False)).any(axis=1)
    frame["cluster"] = cluster_labels(frame, "day_site")
    return lags, frame, np.stack([available, fixed], axis=1)


def measure(args):
    """Summarise both disciplines, retaining full membership and input identities."""
    start = time.monotonic()
    proof = None
    inputs = {}
    if args.input_proof:
        evidence = json.loads(args.input_proof.read_text())
        proof = {
            r["local_copy"]: r["local_identity"]["sha256"]
            for r in evidence["files"]
            if r["identical_bytes"]
        }
        inputs[str(args.input_proof.resolve())] = {
            "sha256": digest(args.input_proof),
            "bytes": args.input_proof.stat().st_size,
        }
    results = {}
    for discipline, glider in DISCIPLINES.items():
        lags, frame, values = load_population(glider, args.audit_dir, inputs, proof)
        reference = int(np.argmin(abs(lags - 1000)))
        entry = {
            "lags_s": lags,
            "reference_lag_s": float(lags[reference]),
            "n_flights": len(frame),
            "missing_altitude": int(frame.altitude_band.eq("").sum()),
            "outside_regions": int(frame.region.eq("").sum()),
            "missing_cluster_keys": int(frame.missing_cluster_key.sum()),
            "flights": frame[
                [
                    "flight_id",
                    "region",
                    "altitude_band",
                    "alt0",
                    "total_retained_duration_s",
                    "cluster",
                ]
            ].to_dict("records"),
        }
        for category, names in (
            ("region", list(REGIONS)),
            ("altitude_band", [b[0] for b in TERRAIN_BANDS]),
        ):
            groups = {}
            for number, name in enumerate(names):
                mask = frame[category].eq(name).to_numpy()
                row = clustered_summary(
                    values[mask],
                    frame.cluster.to_numpy()[mask],
                    resamples=args.resamples,
                    seed=20260913 + number,
                )
                row["n_flights_total"] = int(mask.sum())
                row["fixed_flight_ids"] = frame.loc[
                    mask & np.isfinite(values[:, 1, -1]), "flight_id"
                ].tolist()
                row["missing_cluster_keys"] = int(
                    frame.loc[mask, "missing_cluster_key"].sum()
                )
                row["decade_slopes"] = [
                    decade_slopes(np.where(count >= MIN_FLIGHTS, curve, np.nan), lags)
                    for curve, count in zip(
                        row["mean_m2"], row["n_flights"], strict=True
                    )
                ]
                groups[name] = row
                print(f"{discipline}: {name}: {mask.sum():,} flights", flush=True)
            entry[category] = groups
        cross = []
        for region in REGIONS:
            for band, _, _ in TERRAIN_BANDS:
                mask = (
                    frame.region.eq(region).to_numpy()
                    & frame.altitude_band.eq(band).to_numpy()
                )
                mean, count = mean_and_support(values[mask])
                cross.append(
                    {
                        "region": region,
                        "altitude_band": band,
                        "n_flights_total": int(mask.sum()),
                        "n_flights": count,
                        "mean_m2": mean,
                    }
                )
        entry["region_altitude"] = cross
        results[discipline] = entry
    sources = [
        Path(__file__),
        Path(__file__).with_name("generate_duration_equipment.py"),
        ROOT / "src/soaring/analysis/observables/grouped_tamsd.py",
        ROOT / "src/soaring/analysis/observables/transport.py",
        ROOT / "src/soaring/viewer/geography.py",
        ROOT / "src/soaring/analysis/stats/bootstrap.py",
    ]
    return {
        "status": "complete",
        "run_id": args.record_dir.name,
        "measured_utc": datetime.now(UTC).isoformat(),
        "runtime_s": time.monotonic() - start,
        "inputs": inputs,
        "sources": {str(p.relative_to(ROOT)): digest(p) for p in sources},
        "contract": {
            "observable": "horizontal native-grid equal-flight TAMSD",
            "scope": (
                "all eligible flights, every retained segment with native "
                "cadence at most 10 s"
            ),
            "within_flight": (
                "pool segment sums with their actual admissible-origin "
                "counts"
            ),
            "between_flights": "equal weight per contributing flight",
            "lag_support": (
                "nearest native step k=round(tau/dt), 1<=k<=floor(n/2), "
                "tau>=dt"
            ),
            "controls": [
                "available segments",
                "fixed segments supporting the maximum 10000-s requested lag",
            ],
            "fixed_control_limitation": (
                "flight and segment identities fixed; time origins and "
                "within-flight segment weights still change with lag"
            ),
            "altitude_source": (
                "cleaned GNSS origin alt0; no pressure fallback or "
                "instantaneous altitude grouping"
            ),
            "altitude_bands": [
                {"name": n, "low_m": low, "high_m": high}
                for n, low, high in TERRAIN_BANDS
            ],
            "regions": REGIONS,
            "uncertainty": (
                "pointwise 95% percentile site-day cluster bootstrap within "
                "each group"
            ),
            "resamples": args.resamples,
            "minimum_clusters_for_interval": 20,
            "minimum_flights_for_display": MIN_FLIGHTS,
            "cross_classification": (
                "descriptive only; no calibrated intervals or independent "
                "terrain/wind attribution"
            ),
        },
        "results": results,
    }


def render(report, out):
    """Draw grouped curves with support and a regional-altitude composition check."""
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    paper_style()
    out.mkdir(parents=True, exist_ok=True)
    for category, stem in (("region", "regions"), ("altitude_band", "altitude")):
        fig, axes = plt.subplots(3, 2, figsize=(7.0, 7.8), layout="constrained")
        for column, (discipline, entry) in enumerate(report["results"].items()):
            lags = np.asarray(entry["lags_s"], dtype=float)
            for name, row in entry[category].items():
                means = np.asarray(row["mean_m2"], dtype=float)
                counts = np.asarray(row["n_flights"])
                for control, style in enumerate(("-", "--")):
                    curve = np.where(
                        counts[control] >= MIN_FLIGHTS, means[control], np.nan
                    )
                    axes[0, column].loglog(
                        lags,
                        curve,
                        style,
                        color=COLORS[name],
                        label=name if control == 0 else None,
                    )
                    axes[1, column].semilogx(
                        lags, np.sqrt(curve) / lags, style, color=COLORS[name]
                    )
                    axes[2, column].loglog(
                        lags,
                        np.where(counts[control] > 0, counts[control], np.nan),
                        style,
                        color=COLORS[name],
                    )
                bounds = np.asarray(row["pointwise_95_m2"], dtype=float)[:, 0]
                axes[0, column].fill_between(
                    lags, *bounds, color=COLORS[name], alpha=0.15
                )
                axes[1, column].fill_between(
                    lags, *(np.sqrt(bounds) / lags), color=COLORS[name], alpha=0.15
                )
            axes[0, column].set(
                title=discipline.capitalize(), ylabel=r"Flight TAMSD [m$^2$]"
            )
            axes[0, column].legend(fontsize=7, loc="upper left")
            axes[1, column].set(ylabel=r"$\sqrt{\mathrm{TAMSD}}/\tau$ [m/s]")
            axes[2, column].set(ylabel="Contributing flights")
            for ax in axes[:, column]:
                ax.set(xlim=(10, 10000), xlabel=r"Requested lag $\tau$ [s]")
        fig.savefig(out / f"ch3_tamsd_{stem}.pdf", metadata=PDF_METADATA)
        plt.close(fig)
    fig, axes = plt.subplots(1, 2, figsize=(7.0, 3.6), layout="constrained")
    bands = [r[0] for r in TERRAIN_BANDS]
    for ax, (discipline, entry) in zip(axes, report["results"].items(), strict=True):
        j = int(np.argmin(abs(np.asarray(entry["lags_s"]) - 1000)))
        matrix = np.full((3, 4), np.nan)
        counts = np.zeros((3, 4), dtype=int)
        for row in entry["region_altitude"]:
            i, k = list(REGIONS).index(row["region"]), bands.index(row["altitude_band"])
            counts[i, k] = row["n_flights"][0][j]
            if counts[i, k] >= MIN_FLIGHTS:
                matrix[i, k] = np.sqrt(row["mean_m2"][0][j]) / 1000
        artist = ax.imshow(matrix, cmap="viridis", vmin=0, vmax=12, aspect="auto")
        for i in range(3):
            for k in range(4):
                value = f"{matrix[i, k]:.2f} km" if np.isfinite(matrix[i, k]) else "—"
                ax.text(
                    k,
                    i,
                    f"{value}\nN={counts[i, k]:,}",
                    ha="center",
                    va="center",
                    fontsize=7,
                    color="white"
                    if np.isfinite(matrix[i, k]) and matrix[i, k] < 6
                    else "black",
                )
        ax.set(
            xticks=range(4),
            xticklabels=["Plains", "Hills", "Low\nmtns", "High\nmtns"],
            yticks=range(3),
            yticklabels=list(REGIONS),
            title=discipline.capitalize(),
        )
        ax.tick_params(axis="x", labelsize=7)
    fig.colorbar(artist, ax=axes, label="RMS displacement [km]", shrink=0.8)
    fig.savefig(out / "ch3_tamsd_region_altitude.pdf", metadata=PDF_METADATA)
    plt.close(fig)
    macros = {}
    for discipline, entry in report["results"].items():
        tag = DISCIPLINES[discipline].tag
        j = int(np.argmin(abs(np.asarray(entry["lags_s"]) - 1000)))
        macros[f"StatGrouped{tag}Flights"] = str(entry["n_flights"])
        macros["StatGroupedReferenceLagS"] = f"{entry['reference_lag_s']:.0f}"
        for category in ("region", "altitude_band"):
            for name, row in entry[category].items():
                key = "".join(name.title().split())
                prefix = f"StatGrouped{tag}{key}"
                for control, suffix in enumerate(("", "Fixed")):
                    value = row["mean_m2"][control][j]
                    macros[prefix + "RmsKm" + suffix] = (
                        f"{np.sqrt(value) / 1000:.2f}" if value is not None else "--"
                    )
                    macros[prefix + "Flights" + suffix] = str(
                        row["n_flights"][control][j]
                    )
                    for interval, word in enumerate(("Short", "Middle", "Long")):
                        slope = row["decade_slopes"][control][interval]["slope"]
                        macros[prefix + "Slope" + word + suffix] = (
                            f"{slope:.2f}" if slope is not None else "--"
                        )
    (out / "ch3_grouped_tamsd_values.tex").write_text(
        "% Generated by scripts/reporting/ch3_global_transport/"
        "generate_grouped_tamsd.py\n"
        + "".join("\\newcommand{\\" + k + "}{" + v + "}\n" for k, v in macros.items())
    )


def main():
    """Measure once or redraw the saved report, recording every output identity."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--audit-dir", type=Path, required=True)
    parser.add_argument("--record-dir", type=Path)
    parser.add_argument("--out", type=Path, default=ROOT / "thesis/generated")
    parser.add_argument("--input-proof", type=Path)
    parser.add_argument("--resamples", type=int, default=500)
    parser.add_argument("--render-only", action="store_true")
    args = parser.parse_args()
    args.audit_dir = args.audit_dir.resolve()
    args.record_dir = (args.record_dir or args.audit_dir / "grouped-tamsd").resolve()
    args.record_dir.mkdir(parents=True, exist_ok=True)
    target = args.record_dir / "report.json"
    if args.render_only:
        report = json.loads(target.read_text())
        if report["status"] != "complete":
            raise ValueError("A complete report is required")
    else:
        if target.exists():
            raise ValueError(
                "Preserve the existing measurement; use a new record directory"
            )
        report = portable(measure(args))
        write(target, report)
    render(report, args.out)
    write(args.out / "ch3_grouped_tamsd.json", report)
    write(
        args.record_dir / "figure-manifest.json",
        {
            "report_sha256": digest(target),
            "renderer_sha256": digest(Path(__file__)),
            "outputs": {name: digest(args.out / name) for name in GENERATED_OUTPUTS},
        },
    )
    print(
        f"Completed grouped TAMSD; measurement runtime {report['runtime_s']:.1f} s",
        flush=True,
    )


if __name__ == "__main__":
    main()
