#!/usr/bin/env python3
"""10--10000 s diagnostics over all eligible cleaned flights and segments.

Stream complete flights across Parquet row groups, using a common 10 s grid for
segments with native cadence at most 10 s. All supported segments contribute;
no increment crosses a recording boundary. Disk-backed pools and bounded process
queues permit a complete scan on a laptop. --sample is for development only.
"""

from __future__ import annotations

import argparse
import hashlib
import inspect
import json
import pickle
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
# Static output contract for the provenance checker; paths may be built dynamically.
GENERATED_OUTPUTS = (
    "ch3_scaling.pdf",
    "ch3_quantiles.pdf",
    "ch3_quantile_control.pdf",
    "ch3_models.pdf",
    "ch3_velocity_memory.pdf",
    "ch3_pca.pdf",
    "ch3_revision.tex",
    "ch3_revision.json",
    "ch3_self_similarity.json",
    "ch3_self_similarity_table.tex",
    "ch3_self_similarity_collapse.tex",
    "ch3_self_similarity_ranges.tex",
    "ch3_self_similarity_values.tex",
    "ch3_joint_para.pdf",
    "ch3_joint_hang.pdf",
    "ch3_fixed_quantiles.pdf",
    "ch3_fixed_exponents.pdf",
    "ch3_absolute_laws_para.pdf",
    "ch3_absolute_laws_hang.pdf",
    "ch3_squared_laws_para.pdf",
    "ch3_squared_laws_hang.pdf",
)

sys.path.insert(0, str(ROOT / "src"))

from soaring.analysis.observables.archive_diagnostics import (  # noqa: E402
    archive_quantile_control,
    collect_archive,
    load_measurement,
    measure_archive,
    region_geometry,
    save_measurement,
)
from soaring.analysis.observables.global_diagnostics import (  # noqa: E402
    covariance_geometry,
    declared_task_class,
    empirical_quantiles,
    levy_walk_spectrum,
    log_slope,
    mardia_excess,
)
from soaring.analysis.observables.persistence import (  # noqa: E402
    velocity_autocorrelation,
)
from soaring.reporting import DISCIPLINES, write_macros  # noqa: E402

OUT = ROOT / "thesis" / "generated"
LAGS = np.unique(np.round(np.geomspace(1, 1000, 35)).astype(int)) * 10
Q = np.array([0.25, 0.5, 0.75, 1, 1.5, 2, 2.5, 3, 3.5, 4])
PROBABILITIES = (0.25, 0.5, 0.75, 0.9)
SCALES = (10, 60, 300)
REGIONS = {
    "Alps": (5.4, 10.0, 43.8, 46.6),
    "Pyrenees": (-1.9, 3.3, 42.0, 43.5),
    "Channel Coast": (-1.8, 2.0, 48.3, 51.2),
}
PDF_META = {"CreationDate": None, "Creator": "soaring.analysis"}
from soaring.reporting.style import (  # noqa: E402
    COMPONENT_COLORS,
    CONTROL_COLORS,
    DISCIPLINE_COLORS,
    QUANTILE_COLORS,
    paper_style,
)

PLOT_COLORS = DISCIPLINE_COLORS
CACHE_VERSION = 4
FIXED_QUANTILE_DURATION_S = 20000
QUANTILE_CONTROL_NAMES = (
    "All available / pooled",
    "Fixed flights / pooled",
    "Fixed flights / equal weight",
    "Fixed flights and origins",
)


def file_signature(path):
    """Identify the exact local source by path, size and modification timestamp."""
    path = Path(path)
    stat = path.stat()
    return {"path": str(path), "bytes": stat.st_size, "mtime_ns": stat.st_mtime_ns}


def measurement_contract(para_groups, hang_groups, per_group, *, sample=False):
    """Hash estimator dependencies separately from rendering and summary code."""
    functions = (
        sample_flights,
        region,
        measure,
        quantile_population_control,
        empirical_quantiles,
        nanmean,
        velocity_autocorrelation,
        covariance_geometry,
        mardia_excess,
        declared_task_class,
    )
    return {
        "version": CACHE_VERSION,
        "scope": "development sample" if sample else "full eligible archive",
        "archive_modules_sha256": {
            name: hashlib.sha256(
                (ROOT / "src/soaring/analysis/observables" / name).read_bytes()
            ).hexdigest()
            for name in (
                "archive_diagnostics.py",
                "segment_support.py",
                "joint_distribution.py",
            )
        },
        "estimator_sha256": hashlib.sha256(
            "\n".join(inspect.getsource(f) for f in functions).encode()
        ).hexdigest(),
        "para_groups": para_groups,
        "hang_groups": hang_groups,
        "per_group": per_group,
        "seed": 20260910,
        "lags_s": LAGS.tolist(),
        "q": Q.tolist(),
        "probabilities": PROBABILITIES,
        "velocity_scales_s": SCALES,
        "regions": REGIONS,
        "fixed_quantile_min_duration_s": FIXED_QUANTILE_DURATION_S,
        "quantile_convention": "inverse weighted empirical CDF, no interpolation",
    }


def validate_cache(cached, contract):
    """Reject changed inputs or estimators instead of stamping old results as new."""
    if not isinstance(cached, dict) or cached.get("contract") != contract:
        raise RuntimeError("Measurement cache is obsolete; rerun without --reuse.")
    for source in cached["provenance"].values():
        for signature in source["inputs"].values():
            if file_signature(signature["path"]) != signature:
                raise RuntimeError("A sample input changed; rerun without --reuse.")
    return cached["measured"], cached["provenance"]


def region(lat, lon):
    """Assign the same named takeoff boxes as the full-archive terrain diagnostic."""
    for name, (west, east, south, north) in REGIONS.items():
        if west <= lon <= east and south <= lat <= north:
            return name
    return "other"


def sample_flights(glider, audit_dir, groups, per_group, seed):
    """Read bounded complete flights and yield their longest continuous segment."""
    import pyarrow.parquet as pq

    derived = glider.derived_dir()
    path = derived / "fixes.parquet"
    source = pq.ParquetFile(path)
    rng = np.random.default_rng(seed)
    selected = np.sort(
        rng.choice(
            source.metadata.num_row_groups,
            min(groups, source.metadata.num_row_groups),
            replace=False,
        )
    )
    info = pd.read_parquet(
        derived / "flights_meta.parquet", columns=["flight_id", "lat0", "lon0"]
    )
    info["flight_id"] = info.flight_id.astype(str)
    if info.flight_id.duplicated().any():
        raise ValueError("Flight metadata has duplicate flight identifiers")
    info = info.set_index("flight_id")
    catalog_path = Path(glider.catalog_path())
    tasks = pd.read_csv(
        catalog_path,
        usecols=["flight_id", "flight_type"],
        dtype={"flight_id": str},
        low_memory=False,
    )
    if tasks.flight_id.duplicated().any():
        raise ValueError("The flight catalog has duplicate flight identifiers")
    tasks = tasks.set_index("flight_id")
    provenance = {
        "path": str(path),
        "bytes": path.stat().st_size,
        "mtime_ns": path.stat().st_mtime_ns,
        "seed": seed,
        "row_groups": selected.tolist(),
        "per_group_cap": per_group,
        "native_max_s": 10,
        "grid_s": 10,
        "inputs": {
            "fixes": file_signature(path),
            "metadata": file_signature(derived / "flights_meta.parquet"),
            "tasks": file_signature(catalog_path),
        },
        "flights": [],
    }
    frames = []
    for group in selected:
        frame = source.read_row_group(
            int(group), columns=["flight_id", "segment_id", "t", "E", "N"]
        ).to_pandas()
        ids = frame.flight_id.astype(str)
        complete = ids.loc[~ids.isin([ids.iloc[0], ids.iloc[-1]])].unique()
        chosen = rng.choice(complete, min(per_group, len(complete)), replace=False)
        frame = frame.loc[ids.isin(chosen)]
        for flight_id, flight in frame.groupby("flight_id", sort=False):
            flight_id = str(flight_id)
            sizes = flight.groupby("segment_id").t.agg(["min", "max"])
            longest = (sizes["max"] - sizes["min"]).idxmax()
            segment = flight.loc[flight.segment_id == longest].sort_values("t")
            t = segment.t.to_numpy(dtype=float)
            if len(t) < 32 or np.any(np.diff(t) <= 0):
                continue
            dt = float(np.median(np.diff(t)))
            if not 0 < dt <= 10 or t[-1] - t[0] < 300:
                continue
            grid = np.arange(t[0], t[-1] + 1e-7, 10)
            position = np.column_stack(
                [np.interp(grid, t, segment[c]) for c in ("E", "N")]
            )
            if not np.isfinite(position).all():
                continue
            position -= position[0]
            lat, lon = (
                info.loc[flight_id, ["lat0", "lon0"]].to_numpy()
                if flight_id in info.index
                else [np.nan, np.nan]
            )
            task = (
                str(tasks.loc[flight_id, "flight_type"])
                if flight_id in tasks.index
                else "unknown"
            )
            closed = declared_task_class(task) == "closed"
            known = declared_task_class(task) != "unknown"
            length = np.linalg.norm(np.diff(position, axis=0), axis=1).sum()
            row = {
                "flight_id": flight_id,
                "segment_id": int(longest),
                "native_dt_s": dt,
                "duration_s": float(grid[-1] - grid[0]),
                "region": region(lat, lon),
                "task": task,
                "closed": closed,
                "task_known": known,
                "closure_ratio": float(np.linalg.norm(position[-1]) / length)
                if length
                else 0,
            }
            provenance["flights"].append(row)
            frames.append((row, position))
        print(
            f"{glider.slug}: row group {group}, retained {len(frames)} flights",
            flush=True,
        )
    return frames, provenance


def nanmean(a, axis=0):
    """Average finite entries without warning for unsupported lags."""
    count = np.isfinite(a).sum(axis=axis)
    return np.divide(
        np.nansum(a, axis=axis),
        count,
        out=np.full(np.shape(count), np.nan),
        where=count > 0,
    )


def quantile_population_control(frames):
    """Hold flight identity, mixture weights, and then time origins fixed across lags.

    Four populations expose distinct sampling changes. The last uses every 10-s
    origin eligible at the largest lag, unchanged at all shorter lags. Each flight
    has weight 1/F and its origins equal weights within that flight. Overlapping
    increments remain correlated; this control does not create independent data.
    """
    fixed = np.array(
        [
            (len(position) - 1) * 10 >= FIXED_QUANTILE_DURATION_S
            for _, position in frames
        ]
    )
    curves = np.full((4, len(LAGS), 3, len(PROBABILITIES)), np.nan)
    flights = np.zeros((4, len(LAGS)), dtype=int)
    windows = np.zeros_like(flights)
    fixed_origins = {
        i: np.arange(len(position) - int(LAGS[-1] // 10))
        for i, (_, position) in enumerate(frames)
        if fixed[i]
    }
    for j, tau in enumerate(LAGS):
        lag = int(tau // 10)
        blocks = [[] for _ in range(4)]
        weight_blocks = [[] for _ in range(4)]
        for i, (_, position) in enumerate(frames):
            ordinary = np.arange(0, len(position) - lag, lag)
            for variant in range(4):
                if variant and not fixed[i]:
                    continue
                starts = fixed_origins[i] if variant == 3 else ordinary
                if not len(starts):
                    continue
                xy = position[starts + lag] - position[starts]
                blocks[variant].append(
                    np.column_stack((np.abs(xy), np.linalg.norm(xy, axis=1)))
                )
                weight_blocks[variant].append(
                    np.full(len(starts), 1 / len(starts) if variant >= 2 else 1.0)
                )
                flights[variant, j] += 1
                windows[variant, j] += len(starts)
        for variant in range(4):
            if flights[variant, j] >= 2 and windows[variant, j] >= 30:
                curves[variant, j] = empirical_quantiles(
                    np.concatenate(blocks[variant]),
                    PROBABILITIES,
                    np.concatenate(weight_blocks[variant]),
                )
    return {
        "quantiles": curves,
        "flights_per_lag": flights,
        "windows_per_lag": windows,
        "fixed_flight_indexes": np.flatnonzero(fixed),
        "fixed_origin_counts": np.array([len(x) for x in fixed_origins.values()]),
        "fixed_min_duration_s": FIXED_QUANTILE_DURATION_S,
        "variants": QUANTILE_CONTROL_NAMES,
    }


def measure(frames):
    """Compute equal-flight variations and pooled nonoverlapping increment laws."""
    n = len(frames)
    variations = np.full((n, 2, len(LAGS)), np.nan)
    pools = [[] for _ in LAGS]
    pool_flights = [[] for _ in LAGS]
    coarse = {scale: [] for scale in SCALES}
    for f, (_, position) in enumerate(frames):
        for j, tau in enumerate(LAGS):
            lag = int(tau // 10)
            starts = np.arange(0, len(position) - lag, lag)
            if not len(starts):
                continue
            increments = position[starts + lag] - position[starts]
            pools[j].append(increments)
            pool_flights[j].append(np.full(len(increments), f, dtype=int))
            variations[f, 0, j] = np.mean(np.sum(increments**2, axis=1))
            starts2 = np.arange(0, len(position) - 2 * lag, lag)
            if len(starts2):
                second = (
                    position[starts2 + 2 * lag]
                    - 2 * position[starts2 + lag]
                    + position[starts2]
                )
                variations[f, 1, j] = np.mean(np.sum(second**2, axis=1))
        for scale in SCALES:
            stride = scale // 10
            velocity = np.diff(position[::stride], axis=0) / scale
            indices, corr = velocity_autocorrelation(
                velocity, max_lag=min(len(velocity) // 4, 10000 // scale)
            )
            out = np.full(10000 // scale + 1, np.nan)
            out[indices] = corr
            coarse[scale].append(out)
    moments = np.full((len(LAGS), len(Q)), np.nan)
    quantiles = np.full((len(LAGS), 3, 4), np.nan)
    kurtosis = np.full(len(LAGS), np.nan)
    vectors, owners = [], []
    for j, entries in enumerate(pools):
        xy = np.concatenate(entries) if entries else np.empty((0, 2))
        who = np.concatenate(pool_flights[j]) if entries else np.empty(0, dtype=int)
        vectors.append(xy)
        owners.append(who)
        if len(xy) < 30:
            continue
        r = np.linalg.norm(xy, axis=1)
        moments[j] = np.mean(r[:, None] ** Q[None, :], axis=0)
        quantiles[j] = empirical_quantiles(
            np.column_stack([np.abs(xy), r]), PROBABILITIES
        )
        kurtosis[j] = mardia_excess(xy)
    return {
        "quantile_control": quantile_population_control(frames),
        "variations": variations,
        "moments": moments,
        "quantiles": quantiles,
        "mardia": kurtosis,
        "vectors": vectors,
        "owners": owners,
        "coarse": {s: nanmean(np.array(v)) for s, v in coarse.items()},
        "coarse_support": {s: np.isfinite(v).sum(axis=0) for s, v in coarse.items()},
        "frame": pd.DataFrame([row for row, _ in frames]),
    }


def summarize(m):
    """Record effective slopes and every lag's support, without asymptotic claims."""
    f = m["frame"]
    v = m["variations"]
    mean = nanmean(v)
    fixed = f.duration_s.to_numpy() >= 20000
    out = {
        "n_flights": len(f),
        "n_fixed": int(fixed.sum()),
        "lags_s": LAGS,
        "n_per_lag": np.isfinite(v[:, 0]).sum(axis=0),
        "n_order_two": np.isfinite(v[:, 1]).sum(axis=0),
        "n_increments": np.array([len(a) for a in m["vectors"]]),
        "alpha": [log_slope(LAGS, line)[0] for line in mean],
        "fit_residual_dex": [log_slope(LAGS, line)[1] for line in mean],
        "fixed_alpha": [log_slope(LAGS, line)[0] for line in nanmean(v[fixed])],
        "quantile_h": [
            [log_slope(LAGS, m["quantiles"][:, k, j])[0] for j in range(4)]
            for k in range(3)
        ],
        "zeta": [log_slope(LAGS, m["moments"][:, j])[0] for j in range(len(Q))],
        "mardia": m["mardia"],
        "pca": [],
        "tasks": {},
    }
    control = m["quantile_control"]
    curves = control["quantiles"]
    # Compare every method, coordinate and percentile on identical positive lags.
    common = np.all(np.isfinite(curves) & (curves > 0), axis=(0, 2, 3))
    out["quantile_control"] = {
        **control,
        "fit_lags_s": LAGS[common],
        "exponents": np.array(
            [
                [
                    [
                        log_slope(LAGS[common], variant[common, k, q])[0]
                        for q in range(len(PROBABILITIES))
                    ]
                    for k in range(3)
                ]
                for variant in curves
            ]
        ),
    }
    narrow = (LAGS >= 60) & (LAGS <= 2000)
    out["quantile_h_60_2000"] = [
        [log_slope(LAGS[narrow], m["quantiles"][narrow, k, j])[0] for j in range(4)]
        for k in range(3)
    ]
    out["duration_cohorts"] = []
    reference = int(np.argmin(abs(LAGS - 1000)))
    for threshold in (3600, 7200, 14400):
        select = f.duration_s.to_numpy() >= threshold
        curve = nanmean(v[select, 0])
        out["duration_cohorts"].append(
            {
                "threshold_s": threshold,
                "n_flights": int(select.sum()),
                "reference_lag_s": int(LAGS[reference]),
                "ratio_to_all": float(curve[reference] / mean[0, reference]),
            }
        )
    for name, closed in (("open", False), ("closed", True)):
        select = (f.closed.to_numpy() == closed) & f.task_known.to_numpy()
        curves = nanmean(v[select])
        out["tasks"][name] = {
            "n": int(select.sum()),
            "alpha": [log_slope(LAGS, line)[0] for line in curves],
            "n_last": int(np.isfinite(v[select, 0, -1]).sum()),
            "median_closure": float(f.loc[select, "closure_ratio"].median()),
        }
    for name in REGIONS:
        for target in (10, 100, 1000, 10000):
            j = int(np.argmin(abs(LAGS - target)))
            who = m["owners"][j]
            if "_frames" in m:
                n_flights, geometry = region_geometry(
                    m["vectors"][j], who, f.region.to_numpy() == name
                )
            else:
                selection = f.region.to_numpy()[who] == name
                n_flights = len(np.unique(who[selection]))
                geometry = (
                    covariance_geometry(m["vectors"][j][selection])
                    if n_flights >= 8
                    else {}
                )
            if n_flights < 8:
                continue
            if geometry:
                out["pca"].append(
                    {
                        "region": name,
                        "lag_s": int(LAGS[j]),
                        "n_flights": n_flights,
                        **{
                            k: geometry[k]
                            for k in (
                                "ratio",
                                "angle_deg",
                                "correlation",
                                "covariance",
                                "mean",
                            )
                        },
                    }
                )
    for scale in SCALES:
        index = min(600 // scale, len(m["coarse"][scale]) - 1)
        out[f"vacf_{scale}s_at_600s"] = float(m["coarse"][scale][index])
    return out


def draw(measured, summaries):
    """Render at thesis text width with the shared scientific figure style."""
    import matplotlib.pyplot as plt
    from matplotlib.lines import Line2D
    from matplotlib.patches import Ellipse

    paper_style()
    plt.rcParams.update(
        {
            "font.size": 9,
            "axes.labelsize": 9,
            "axes.titlesize": 9,
            "xtick.labelsize": 9,
            "ytick.labelsize": 9,
            "legend.fontsize": 8,
            "axes.spines.top": True,
            "axes.spines.right": True,
            "lines.linewidth": 1.1,
            "pdf.fonttype": 42,
            "savefig.bbox": None,
        }
    )
    names = {"paragliders": "Paragliders", "hang gliders": "Hang gliders"}
    colors = list(COMPONENT_COLORS.values())

    def finish(fig, filename):
        for ax in fig.axes:
            ax.grid(visible=False)
            ax.set_axisbelow(True)
        # Include every label in the PDF even when backend text extents differ.
        fig.canvas.draw()
        fig.savefig(
            OUT / filename, metadata=PDF_META, bbox_inches="tight", pad_inches=0.05
        )
        plt.close(fig)

    def legend_below(ax, ncol=2):
        ax.legend(
            loc="upper center",
            bbox_to_anchor=(0.5, -0.28),
            ncol=ncol,
            frameon=False,
            columnspacing=0.9,
            handlelength=1.8,
        )

    fig, axes = plt.subplots(2, 2, figsize=(6.1, 6.45), layout="constrained")
    for discipline, m in measured.items():
        color = PLOT_COLORS[discipline]
        s, f = summaries[discipline], m["frame"]
        mean = nanmean(m["variations"])
        for order, style in enumerate(("-", "--")):
            axes[0, 0].loglog(LAGS, mean[order], style, color=color)
            axes[0, 1].semilogx(
                LAGS,
                np.gradient(np.log(mean[order]), np.log(LAGS)) / 2,
                style,
                color=color,
            )
        fixed = f.duration_s.to_numpy() >= 20000
        if fixed.any():
            axes[0, 0].loglog(
                LAGS, nanmean(m["variations"][fixed, 0]), ":", color=color
            )
        for closed, style in ((False, "--"), (True, "-")):
            mask = (f.closed.to_numpy() == closed) & f.task_known.to_numpy()
            axes[1, 0].loglog(
                LAGS, nanmean(m["variations"][mask, 0]), style, color=color
            )
        for key, style in (("n_per_lag", "-"), ("n_order_two", "--")):
            axes[1, 1].semilogx(LAGS, s[key], style, color=color)
    for ax, title, ylabel in zip(
        axes.flat,
        (
            "(a) Displacement moments",
            "(b) Half the local slope",
            "(c) Declared task geometry",
            "(d) Contributing flights",
        ),
        (
            r"$V_p(\tau)$ [m$^2$]",
            r"$\frac{1}{2}\,d\log V_p/d\log\tau$",
            r"$V_1(\tau)$ [m$^2$]",
            "Number of flights",
        ),
        strict=True,
    ):
        ax.set(title=title, xlabel=r"Lag $\tau$ [s]", ylabel=ylabel, xlim=(10, 10000))
    order_handles = [
        Line2D([], [], color=".3", ls=style, label=label)
        for style, label in (
            ("-", "$V_1$"),
            ("--", "$V_2$"),
            (":", "$V_1$, long cohort"),
        )
    ]
    axes[0, 0].legend(
        handles=order_handles,
        loc="upper center",
        bbox_to_anchor=(0.5, -0.3),
        ncol=2,
        frameon=False,
    )
    axes[1, 0].legend(
        handles=[
            Line2D([], [], color=".3", ls=style, label=label)
            for style, label in (("--", "Open"), ("-", "Closed"))
        ],
        loc="upper center",
        bbox_to_anchor=(0.5, -0.3),
        ncol=2,
        frameon=False,
    )
    axes[0, 1].axhline(1, color=".55", lw=0.7)
    fig.legend(
        handles=[
            Line2D([], [], color=PLOT_COLORS[d], label=names[d]) for d in measured
        ],
        loc="outside upper center",
        ncol=2,
        frameon=False,
    )
    finish(fig, "ch3_scaling.pdf")

    fig, axes = plt.subplots(3, 2, figsize=(6.1, 7.7), layout="constrained")
    for col, (discipline, m) in enumerate(measured.items()):
        s = summaries[discipline]
        for p, value in enumerate(PROBABILITIES):
            axes[0, col].loglog(
                LAGS,
                m["quantiles"][:, 2, p],
                color=QUANTILE_COLORS[value],
                label=f"{100 * value:g}%",
            )
        for k, label in enumerate(("|East|", "|North|", "Radius")):
            axes[1, col].plot(
                PROBABILITIES,
                s["quantile_h"][k],
                "o-",
                ms=4,
                color=colors[k],
                label=label,
            )
        axes[2, col].semilogx(
            LAGS,
            m["quantiles"][:, 2, 3] / m["quantiles"][:, 2, 0],
            color=PLOT_COLORS[discipline],
        )
        axes[0, col].set(
            title=names[discipline],
            xlabel=r"Lag $\tau$ [s]",
            ylabel=r"$Q_p(\tau)$ [m]",
            xlim=(10, 10000),
        )
        axes[1, col].set(
            xlabel="Percentile",
            ylabel=r"Fitted exponent $H_p$",
            xticks=PROBABILITIES,
            xticklabels=(25, 50, 75, 90),
        )
        axes[2, col].set(
            xlabel=r"Lag $\tau$ [s]", ylabel=r"$Q_{0.90}/Q_{0.25}$", xlim=(10, 10000)
        )
        legend_below(axes[0, col], 2)
        legend_below(axes[1, col], 3)
    finish(fig, "ch3_quantiles.pdf")

    fig, axes = plt.subplots(2, 2, figsize=(6.1, 5.5), layout="constrained")
    control_colors = CONTROL_COLORS
    control_styles = (":", "--", "-.", "-")
    for col, (discipline, _m) in enumerate(measured.items()):
        control = summaries[discipline]["quantile_control"]
        curves = control["quantiles"]
        for variant in range(4):
            axes[0, col].plot(
                PROBABILITIES,
                control["exponents"][variant, 2],
                control_styles[variant],
                color=control_colors[variant],
                marker="o",
                ms=3,
            )
            ratio = np.divide(
                curves[variant, :, 2, 3],
                curves[variant, :, 2, 0],
                out=np.full(len(LAGS), np.nan),
                where=curves[variant, :, 2, 0] > 0,
            )
            axes[1, col].semilogx(
                LAGS, ratio, control_styles[variant], color=control_colors[variant]
            )
        n = len(control["fixed_flight_indexes"])
        axes[0, col].set(
            title=f"{names[discipline]}; fixed N={n}",
            xlabel="Percentile",
            ylabel=r"Radial exponent $H_p$",
            xticks=PROBABILITIES,
            xticklabels=(25, 50, 75, 90),
        )
        axes[1, col].set(
            xlabel=r"Lag $\tau$ (s)", ylabel=r"$Q_{0.90}/Q_{0.25}$", xlim=(10, 10000)
        )
    fig.legend(
        handles=[
            Line2D([], [], color=c, ls=style, label=name)
            for c, style, name in zip(
                control_colors, control_styles, QUANTILE_CONTROL_NAMES, strict=True
            )
        ],
        loc="outside lower center",
        ncol=2,
        frameon=False,
        fontsize=8,
    )
    finish(fig, "ch3_quantile_control.pdf")

    fig, axes = plt.subplots(1, 2, figsize=(6.1, 3.8), layout="constrained")
    axes[0].plot(Q, Q / 2, ":", color=".5", label="Brownian")
    axes[0].plot(
        Q,
        levy_walk_spectrum(Q, 1.5),
        "--",
        color=".25",
        label=r"Lévy walk, $\beta=1.5$",
    )
    for discipline, m in measured.items():
        color, s = PLOT_COLORS[discipline], summaries[discipline]
        axes[0].plot(Q, s["zeta"], "o-", ms=2.5, color=color, label=names[discipline])
        axes[1].semilogx(
            LAGS, m["mardia"], "o-", ms=2.5, color=color, label=names[discipline]
        )
    axes[0].set(
        title="(a) Moment spectrum", xlabel="Moment order $q$", ylabel=r"$\zeta(q)$"
    )
    axes[1].set(
        title="(b) Multivariate kurtosis",
        xlabel=r"Lag $\tau$ (s)",
        ylabel=r"Mardia excess $K_M$",
        xlim=(10, 10000),
    )
    axes[1].axhline(0, color=".55", lw=0.7)
    legend_below(axes[0], 1)
    legend_below(axes[1], 1)
    finish(fig, "ch3_models.pdf")

    fig, axes = plt.subplots(
        2, 2, figsize=(6.1, 5.8), sharex=True, layout="constrained"
    )
    for col, (discipline, m) in enumerate(measured.items()):
        for scale, linestyle, color in zip(
            SCALES, ("-", "--", ":"), colors, strict=False
        ):
            tau = np.arange(len(m["coarse"][scale])) * scale
            curve = np.asarray(m["coarse"][scale])
            supported = (tau >= scale) & (m["coarse_support"][scale] >= 20)
            # Keep NaNs between positive stretches: never bridge a zero or negative
            # correlation, and never turn it positive by taking its absolute value.
            positive = np.where(supported & (curve > 0), curve, np.nan)
            signed = np.where(supported, curve, np.nan)
            axes[0, col].loglog(
                tau[1:], positive[1:], linestyle, color=color, label=f"h = {scale} s"
            )
            axes[1, col].semilogx(tau[1:], signed[1:], linestyle, color=color)
        axes[0, col].set(
            title=f"({chr(97 + col)}) {names[discipline]}",
            ylabel=r"Positive $C_h(\tau)$",
            xlim=(10, 10000),
        )
        axes[1, col].set(
            title=f"({chr(99 + col)}) Signed correlation",
            xlabel=r"Separation $\tau$ (s)",
            ylabel=r"$C_h(\tau)$",
            ylim=(-0.3, 1.0),
        )
        axes[1, col].axhline(0, color=".4", lw=0.7, ls="--")
        axes[0, col].legend(
            loc="best",
            frameon=True,
            facecolor="white",
            edgecolor="none",
            framealpha=0.85,
        )
    finish(fig, "ch3_velocity_memory.pdf")

    fig, axes = plt.subplots(3, 2, figsize=(6.1, 7.6), layout="constrained")
    para = summaries["paragliders"]["pca"]
    for row, name in enumerate(REGIONS):
        rows = [r for r in para if r["region"] == name]
        for r, color in zip(rows, colors, strict=False):
            values = np.linalg.eigvalsh(r["covariance"])
            scale = np.sqrt(values.sum())
            axes[row, 0].add_patch(
                Ellipse(
                    (0, 0),
                    2 * np.sqrt(values[-1]) / scale,
                    2 * np.sqrt(values[0]) / scale,
                    angle=r["angle_deg"],
                    fill=False,
                    color=color,
                    lw=1.6,
                    label=f"{r['lag_s']} s; N={r['n_flights']}",
                )
            )
        axes[row, 0].set(
            title=name,
            xlabel="East / centred RMS radius",
            ylabel="North / centred RMS radius",
            xlim=(-1.1, 1.1),
            ylim=(-1.1, 1.1),
            aspect="equal",
            xticks=(-1, 0, 1),
            yticks=(-1, 0, 1),
        )
        axes[row, 0].axhline(0, color=".8", lw=0.6)
        axes[row, 0].axvline(0, color=".8", lw=0.6)
        axes[row, 1].semilogx(
            [r["lag_s"] for r in rows], [r["ratio"] for r in rows], "-", color=".45"
        )
        for r, color in zip(rows, colors, strict=False):
            axes[row, 1].plot(r["lag_s"], r["ratio"], "o", color=color, ms=5)
            axes[row, 1].annotate(
                f"{r['angle_deg']:.0f}°",
                (r["lag_s"], r["ratio"]),
                xytext=(0, 8),
                textcoords="offset points",
                ha="center",
                fontsize=9,
            )
        axes[row, 1].set(
            xlabel=r"Lag $\tau$ [s]", ylabel=r"$\lambda_1/\lambda_2$", xlim=(6, 17000)
        )
        axes[row, 1].set_ylim(1, max([r["ratio"] for r in rows], default=1) * 1.35)
        handles, labels = axes[row, 0].get_legend_handles_labels()
        axes[row, 1].legend(
            handles,
            labels,
            loc="upper center",
            bbox_to_anchor=(0.5, -0.3),
            frameon=False,
            ncol=2,
            columnspacing=0.8,
        )
    finish(fig, "ch3_pca.pdf")


def jsonable(value):
    """Convert NumPy data to a portable JSON report."""
    if isinstance(value, dict):
        return {str(k): jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [jsonable(v) for v in value]
    if isinstance(value, np.ndarray):
        return jsonable(value.tolist())
    if isinstance(value, np.generic):
        return jsonable(value.item())
    if isinstance(value, float) and not np.isfinite(value):
        return None
    return value


def main():
    """Measure both disciplines and write the figures, results and macros."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--audit-dir", type=Path, default=Path("/Volumes/SSD_DISANTE/derived-audit")
    )
    parser.add_argument("--sample", action="store_true", help="development subset only")
    parser.add_argument("--jobs", type=int, default=None, help="bounded flight workers")
    parser.add_argument("--para-groups", type=int, default=24)
    parser.add_argument("--hang-groups", type=int, default=12)
    parser.add_argument("--per-group", type=int, default=40)
    parser.add_argument(
        "--saved-snapshot",
        type=Path,
        help="extend an immutable completed diagnostic cache with explicit provenance",
    )
    parser.add_argument(
        "--reuse",
        action="store_true",
        help="reuse this script's local measurement cache",
    )
    args = parser.parse_args()
    import matplotlib

    matplotlib.use("Agg")
    from soaring.reporting.style import paper_style

    paper_style()
    from soaring.reporting.self_similarity import write_report

    if args.saved_snapshot:
        with args.saved_snapshot.open("rb") as stream:
            saved = pickle.load(stream)
        manifest_path = args.saved_snapshot.parent.parent / "manifest.json"
        manifest = json.loads(manifest_path.read_text())
        if manifest.get("status") != "complete":
            raise RuntimeError("--saved-snapshot requires a completed run")
        snapshot = {
            "kind": "completed saved snapshot; not a claim about a running rebuild",
            "manifest": str(manifest_path),
            "run_id": manifest.get("run_id"),
            "cache": file_signature(args.saved_snapshot),
            "cache_sha256": hashlib.sha256(
                args.saved_snapshot.read_bytes()
            ).hexdigest(),
            "pipeline_versions": sorted(
                {
                    value["cleaning"]["pipeline_version"]
                    for value in manifest.get("datasets", {}).values()
                }
            ),
        }
        write_report(
            saved["measured"],
            saved["provenance"],
            saved["contract"],
            OUT,
            snapshot=snapshot,
        )
        saved_summaries = {name: summarize(m) for name, m in saved["measured"].items()}
        draw(saved["measured"], saved_summaries)
        return
    measured, summaries, provenance, macros = {}, {}, {}, {}
    args.audit_dir.mkdir(parents=True, exist_ok=True)
    cache = args.audit_dir / (
        "ch3_revision_sample.pkl" if args.sample else "ch3_revision_full.pkl"
    )
    contract = measurement_contract(
        args.para_groups, args.hang_groups, args.per_group, sample=args.sample
    )
    if args.reuse:
        with cache.open("rb") as stream:
            saved = pickle.load(stream)
        measured, provenance = validate_cache(saved, contract)
        if not args.sample:
            measured = {
                name: load_measurement(Path(directory))
                for name, directory in saved["directories"].items()
            }
    for discipline, g in DISCIPLINES.items():
        count = args.para_groups if g.slug == "para" else args.hang_groups
        if not args.reuse:
            if args.sample:
                frames, provenance[discipline] = sample_flights(
                    g, args.audit_dir, count, args.per_group, 20260910
                )
                measured[discipline] = measure(frames)
            else:
                directory = args.audit_dir / f"ch3-full-{g.slug}"
                frames, provenance[discipline] = collect_archive(
                    g, directory, REGIONS, declared_task_class, file_signature
                )
                measured[discipline] = measure_archive(
                    frames, directory, LAGS, SCALES, Q, PROBABILITIES, args.jobs
                )
                measured[discipline]["quantile_control"] = archive_quantile_control(
                    measured[discipline],
                    frames,
                    LAGS,
                    PROBABILITIES,
                    QUANTILE_CONTROL_NAMES,
                )
                save_measurement(measured[discipline], directory)
        frame = measured[discipline]["frame"]
        classes = frame.task.map(declared_task_class)
        frame["closed"] = classes == "closed"
        frame["task_known"] = classes != "unknown"
        for row in provenance[discipline]["flights"]:
            row["closed"] = declared_task_class(row["task"]) == "closed"
            row["task_known"] = declared_task_class(row["task"]) != "unknown"
        s = summaries[discipline] = summarize(measured[discipline])
        for key, value in {
            "Flights": s["n_flights"],
            "FixedFlights": s["n_fixed"],
            "LastFlights": int(s["n_per_lag"][-1]),
            "LastWindows": int(s["n_increments"][-1]),
            "LastOrderTwoFlights": int(s["n_order_two"][-1]),
            "AlphaOne": f"{s['alpha'][0]:.3f}",
            "AlphaTwo": f"{s['alpha'][1]:.3f}",
            "ResidualOne": f"{s['fit_residual_dex'][0]:.3f}",
            "ResidualTwo": f"{s['fit_residual_dex'][1]:.3f}",
            "FixedAlphaOne": f"{s['fixed_alpha'][0]:.3f}",
            "FixedAlphaTwo": f"{s['fixed_alpha'][1]:.3f}",
            "MomentZetaTwo": f"{s['zeta'][int(np.flatnonzero(Q == 2)[0])]:.3f}",
            "MomentNuMin": f"{np.min(np.array(s['zeta']) / Q):.3f}",
            "MomentNuMax": f"{np.max(np.array(s['zeta']) / Q):.3f}",
            "MardiaMin": f"{np.nanmin(s['mardia']):.2f}",
            "MardiaMedian": f"{np.nanmedian(s['mardia']):.2f}",
            "MardiaMax": f"{np.nanmax(s['mardia']):.2f}",
        }.items():
            macros[f"StatRev{g.tag}{key}"] = str(value)
        for name, task in s["tasks"].items():
            for label, value in {
                "Flights": task["n"],
                "AlphaOne": f"{task['alpha'][0]:.3f}",
                "AlphaTwo": f"{task['alpha'][1]:.3f}",
                "Closure": f"{task['median_closure']:.3f}",
            }.items():
                macros[f"StatRev{g.tag}{name.title()}{label}"] = str(value)
        for variable, values in zip(
            ("East", "North", "Radial"), s["quantile_h"], strict=True
        ):
            for label, value in zip(
                ("Lower", "Median", "Upper", "Ninetieth"), values, strict=True
            ):
                macros[f"StatRev{g.tag}{variable}{label}"] = f"{value:.3f}"
        for label, value in zip(
            ("Lower", "Median", "Upper", "Ninetieth"),
            s["quantile_h_60_2000"][2],
            strict=True,
        ):
            macros[f"StatRev{g.tag}NarrowRadial{label}"] = f"{value:.3f}"
        control = s["quantile_control"]
        macros[f"StatRev{g.tag}QuantileFixedFlights"] = str(
            len(control["fixed_flight_indexes"])
        )
        macros[f"StatRev{g.tag}QuantileFixedOrigins"] = str(
            int(control["fixed_origin_counts"].sum())
        )
        lags_control = control["fit_lags_s"]
        for suffix, value in (
            ("MinS", lags_control[0] if len(lags_control) else 0),
            ("MaxS", lags_control[-1] if len(lags_control) else 0),
        ):
            macros[f"StatRev{g.tag}QuantileControlFit{suffix}"] = f"{value:.0f}"
        for variant, prefix in ((0, "Changing"), (3, "Controlled")):
            for label, exponent in zip(
                ("Lower", "Median", "Upper", "Ninetieth"),
                control["exponents"][variant, 2],
                strict=True,
            ):
                macros[f"StatRev{g.tag}Quantile{prefix}{label}"] = (
                    f"{exponent:.3f}"
                    if np.isfinite(exponent)
                    else r"\text{unavailable}"
                )
        for label, cohort in zip(
            ("One", "Two", "Four"), s["duration_cohorts"], strict=True
        ):
            macros[f"StatRev{g.tag}Duration{label}HFlights"] = str(cohort["n_flights"])
            macros[f"StatRev{g.tag}Duration{label}HRatio"] = (
                f"{cohort['ratio_to_all']:.2f}"
            )
        for label, scale in zip(("Ten", "Sixty", "ThreeHundred"), SCALES, strict=True):
            macros[f"StatRev{g.tag}Vacf{label}AtSixHundred"] = (
                f"{s[f'vacf_{scale}s_at_600s']:.3f}"
            )
        for row in s["pca"]:
            if row["lag_s"] != 1070:
                continue
            prefix = f"StatRev{g.tag}Pca{row['region'].replace(' ', '')}"
            macros[prefix + "Flights"] = str(row["n_flights"])
            macros[prefix + "Ratio"] = f"{row['ratio']:.2f}"
            macros[prefix + "Angle"] = f"{row['angle_deg']:.1f}"
        macros[f"StatRev{g.tag}DurationReferenceLagS"] = str(
            s["duration_cohorts"][0]["reference_lag_s"]
        )
        print(
            f"{discipline}: {s['n_flights']} flights; "
            f"{s['n_fixed']} in fixed long cohort; "
            f"MSD slopes {s['alpha']}; detailed quantile controls in JSON",
            flush=True,
        )
    if not args.reuse:
        with cache.open("wb") as stream:
            pickle.dump(
                {
                    "measured": measured if args.sample else {},
                    "directories": {
                        name: str((args.audit_dir / f"ch3-full-{g.slug}").resolve())
                        for name, g in DISCIPLINES.items()
                    }
                    if not args.sample
                    else {},
                    "provenance": provenance,
                    "contract": contract,
                },
                stream,
                protocol=5,
            )
    OUT.mkdir(exist_ok=True)
    draw(measured, summaries)
    write_report(
        measured,
        provenance,
        contract,
        OUT,
        snapshot={
            "kind": "diagnostic inputs verified or measured in this run",
            "audit_dir": str(args.audit_dir),
        },
    )
    report = {
        "requested_range_s": [10, 10000],
        "q": Q,
        "method": __doc__ if not args.sample else inspect.getdoc(sample_flights),
        "provenance": provenance,
        "measurement_contract": contract,
        "results": summaries,
        "code_sha256": {
            str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in (
                Path(__file__),
                ROOT / "src/soaring/analysis/observables/global_diagnostics.py",
                ROOT / "src/soaring/analysis/observables/persistence.py",
            )
        },
    }
    (OUT / "ch3_revision.json").write_text(
        json.dumps(jsonable(report), indent=2) + "\n"
    )
    write_macros(
        OUT / "ch3_revision.tex",
        macros,
        generator=str(Path(__file__).relative_to(ROOT)),
    )
    print("Wrote Chapter 3 subset figures, macros and JSON provenance.", flush=True)


if __name__ == "__main__":
    main()
