"""Figures and reproducible tables for the fixed-population scaling diagnostic."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np

from soaring.analysis.observables import self_similarity as analysis
from soaring.reporting.macros import write_macros
from soaring.reporting.style import (
    COMPONENT_COLORS,
    LAG_COLORS,
    PDF_METADATA,
    QUANTILE_COLORS,
    paper_style,
)

GENERATOR = "scripts/reporting/ch3_global_transport/generate_revision_diagnostics.py"
LABELS = (r"$|X_E|$", r"$|X_N|$", r"$R$")
NAMES = {"paragliders": "Paragliders", "hang gliders": "Hang gliders"}


def jsonable(value):
    """Convert NumPy arrays and scalar types to portable JSON values."""
    if isinstance(value, dict):
        return {key: jsonable(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [jsonable(item) for item in value]
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, np.generic):
        return value.item()
    return value


def save(fig, out, name):
    """Save a vector figure with all labels inside its bounding box."""
    import matplotlib.pyplot as plt

    fig.savefig(out / name, metadata=PDF_METADATA, bbox_inches="tight", pad_inches=0.05)
    plt.close(fig)


def draw(results, out):
    """Draw rank curves, paired comparisons, and full-support displacement laws."""
    import matplotlib.pyplot as plt
    from matplotlib.colors import LogNorm
    from matplotlib.lines import Line2D

    paper_style()
    for discipline, result in results.items():
        joint = result["joint"]
        fig, axes = plt.subplots(2, 3, figsize=(6.1, 4.5), layout="constrained")
        maximum = max(np.max(law["mass"]) for law in joint["laws"])
        norm = LogNorm(vmin=max(1e-6, maximum * 1e-4), vmax=maximum)
        for ax, law in zip(axes.flat, joint["laws"], strict=True):
            mass = np.asarray(law["mass"])
            im = ax.pcolormesh(
                joint["interior_edges"],
                joint["interior_edges"],
                mass[1:-1, 1:-1].T,
                norm=norm,
                cmap="viridis",
                rasterized=True,
            )
            ax.set(
                xlabel=r"Rescaled $X_E$",
                ylabel=r"Rescaled $X_N$",
                title=f"{law['lag_s']} s; tail {100 * law['tail_mass']:.1f}%",
                aspect="equal",
            )
        fig.colorbar(im, ax=axes, label="Joint probability per cell", shrink=0.75)
        tag = "para" if discipline == "paragliders" else "hang"
        save(fig, out, f"ch3_joint_{tag}.pdf")

    fig, axes = plt.subplots(3, 2, figsize=(6.1, 7.6), layout="constrained")
    for col, (discipline, result) in enumerate(results.items()):
        tau = np.asarray(result["lags_s"])
        fit = result["fits"]["full"]
        for k in range(3):
            ax = axes[k, col]
            for p, probability in enumerate(analysis.PROBABILITIES):
                color = QUANTILE_COLORS[probability]
                ax.loglog(tau, result["quantiles_m"][:, k, p], color=color, lw=1.5)
                fitted = (
                    np.exp(fit["intercept_at_1000s"][k, p])
                    * (tau / 1000) ** fit["h"][k, p]
                )
                ax.loglog(tau, fitted, "--", color=color, lw=0.8)
            ax.set(
                xlabel=r"Lag $\tau$ [s]",
                ylabel=LABELS[k] + " quantile [m]",
                title=NAMES[discipline] if k == 0 else "",
            )
    fig.legend(
        handles=[
            Line2D([], [], color=c, label=f"{100 * p:g}%")
            for p, c in QUANTILE_COLORS.items()
        ],
        loc="outside lower center",
        ncol=4,
        title="Solid: empirical quantiles; dashed: separate power fits",
    )
    save(fig, out, "ch3_fixed_quantiles.pdf")

    fig, axes = plt.subplots(2, 2, figsize=(6.1, 5.5), layout="constrained")
    for col, (discipline, result) in enumerate(results.items()):
        fit = result["fits"]["full"]
        for k, color in enumerate(COMPONENT_COLORS.values()):
            h = fit["h"][k]
            interval = fit["h_ci95"][:, k]
            x = np.arange(4) + (k - 1) * 0.12
            axes[0, col].errorbar(
                x,
                h,
                yerr=np.maximum(0, np.array([h - interval[0], interval[1] - h])),
                color=color,
                fmt="o-",
                capsize=2,
                label=LABELS[k],
            )
            curves = result["quantiles_m"][:, k]
            axes[1, col].semilogx(
                result["lags_s"], curves[:, 3] / curves[:, 0], color=color
            )
        axes[0, col].set(
            title=NAMES[discipline],
            xlabel="Percentile",
            ylabel=r"Effective $H_p$",
            xticks=np.arange(4),
            xticklabels=(25, 50, 75, 90),
        )
        axes[0, col].legend(ncol=3)
        axes[1, col].set(xlabel=r"Lag $\tau$ [s]", ylabel=r"$Q_{0.90}/Q_{0.25}$")
    save(fig, out, "ch3_fixed_exponents.pdf")

    for discipline, result in results.items():
        slug = "para" if discipline == "paragliders" else "hang"
        tau = np.asarray(result["lags_s"])
        chosen = result["display_lag_indexes"]
        for power in (1, 2):
            fig, axes = plt.subplots(
                3 if power == 1 else 2,
                3,
                figsize=(6.1, 7.1 if power == 1 else 5.2),
                layout="constrained",
            )
            for k, law in enumerate(result["laws"]):
                h = result["fits"]["full"]["common_h"][k]
                edges = law["edges_m"] ** power
                centers = np.sqrt(edges[:-1] * edges[1:])
                for i, j in enumerate(chosen):
                    color = LAG_COLORS[i]
                    mass = law["mass"][i]
                    density = mass / np.diff(edges)
                    scale = (tau[j] / 1000.0) ** (power * h)
                    density = np.where(density > 0, density, np.nan)
                    axes[0, k].loglog(centers, density, color=color)
                    axes[1, k].loglog(centers / scale, scale * density, color=color)
                    if power == 1:
                        median = result["quantiles_m"][j, k, 1]
                        axes[2, k].semilogx(
                            result["dense_quantiles_m"][j, k] / median,
                            result["dense_probabilities"],
                            color=color,
                        )
                variable = (
                    LABELS[k] if power == 1 else (r"$X_E^2$", r"$X_N^2$", r"$R^2$")[k]
                )
                unit = "m" if power == 1 else r"m$^2$"
                exponent_label = "H_*" if power == 1 else "2H_*"
                axes[0, k].set(
                    title=variable, xlabel=f"Displacement [{unit}]", ylabel="Density"
                )
                axes[1, k].set(
                    title=rf"$H_*={h:.3f}$" if power == 1 else rf"$2H_*={2 * h:.3f}$",
                    xlabel=rf"$y/(\tau/\tau_0)^{{{exponent_label}}}$ [{unit}]",
                    ylabel="Rescaled density",
                )
                if power == 1:
                    axes[2, k].set(
                        xlabel=r"$y/Q_{0.50}(\tau)$",
                        ylabel="Cumulative probability",
                        ylim=(0, 1),
                        xlim=(0.01, 10),
                    )
            fig.suptitle(
                NAMES[discipline]
                + (
                    ": absolute displacement"
                    if power == 1
                    else ": squared displacement"
                )
            )
            fig.legend(
                handles=[
                    Line2D([], [], color=LAG_COLORS[i], label=f"{tau[j]:g} s")
                    for i, j in enumerate(chosen)
                ],
                loc="outside lower center",
                ncol=3,
            )
            save(
                fig,
                out,
                f"ch3_{'absolute' if power == 1 else 'squared'}_laws_{slug}.pdf",
            )


def write_tables(results, out):
    """Write manuscript tables directly from the numerical report."""
    lines = [
        f"% Generated by {GENERATOR} -- do not edit.",
        r"\begin{tabular}{@{}llrrrr@{}}",
        r"\toprule",
        r"Discipline & Quantity & $H_{.25}$ & $H_{.50}$ & $H_{.75}$ & $H_{.90}$ \\",
        r"\midrule",
    ]
    for discipline, result in results.items():
        for k in range(3):
            fit = result["fits"]["full"]
            cells = [f"{fit['h'][k, p]:.3f}" for p in range(4)]
            lines.append(
                f"{NAMES[discipline] if k == 0 else ''} & {LABELS[k]} & "
                + " & ".join(cells)
                + r" \\"
            )
        lines.append(r"\addlinespace")
    lines += [r"\bottomrule", r"\end{tabular}"]
    (out / "ch3_self_similarity_table.tex").write_text("\n".join(lines) + "\n")
    lines = [
        f"% Generated by {GENERATOR} -- do not edit.",
        r"\begin{tabular}{@{}llrrr@{}}",
        r"\toprule",
        r"Discipline & Quantity & $H_*$ & $D_{\rm power}$ & $D_{\rm median}$ \\",
        r"\midrule",
    ]
    for discipline, result in results.items():
        for k, law in enumerate(result["laws"]):
            power = max(pair["power"] for pair in law["cdf_distances"])
            median = max(pair["median"] for pair in law["cdf_distances"])
            lines.append(
                f"{NAMES[discipline] if k == 0 else ''} & {LABELS[k]} & "
                f"{result['fits']['full']['common_h'][k]:.3f} & "
                f"{power:.3f} & {median:.3f}" + r" \\"
            )
        lines.append(r"\addlinespace")
    lines += [r"\bottomrule", r"\end{tabular}"]
    (out / "ch3_self_similarity_collapse.tex").write_text("\n".join(lines) + "\n")
    lines = [
        f"% Generated by {GENERATOR} -- do not edit.",
        r"\begin{tabular}{@{}llrrr@{}}",
        r"\toprule",
        r"Discipline & Quantity & 10--10000 s & 60--1970 s & 210--1970 s \\",
        r"\midrule",
    ]
    for discipline, result in results.items():
        for k in range(3):
            cells = [
                f"{result['fits'][name]['common_h'][k]:.3f}"
                for name in ("full", "intermediate", "late_intermediate")
            ]
            lines.append(
                f"{NAMES[discipline] if k == 0 else ''} & {LABELS[k]} & "
                + " & ".join(cells)
                + r" \\"
            )
        lines.append(r"\addlinespace")
    lines += [r"\bottomrule", r"\end{tabular}"]
    (out / "ch3_self_similarity_ranges.tex").write_text("\n".join(lines) + "\n")
    macros = {}
    for discipline, result in results.items():
        tag = "Para" if discipline == "paragliders" else "Hang"
        fit = result["fits"]["full"]
        for k, quantity in enumerate(("East", "North", "Radial")):
            contrast = fit["contrasts"]["p90_minus_p25"]
            prefix = f"StatSS{tag}{quantity}RankDifference"
            macros[prefix] = f"{contrast['estimate'][k]:.3f}"
            macros[prefix + "Low"] = f"{contrast['ci95'][0][k]:.3f}"
            macros[prefix + "High"] = f"{contrast['ci95'][1][k]:.3f}"
        contrast = fit["contrasts"]["north_minus_east"]
        for p, rank in enumerate(("Lower", "Median", "Upper", "Ninetieth")):
            prefix = f"StatSS{tag}NorthEast{rank}"
            macros[prefix] = f"{contrast['estimate'][p]:.3f}"
            macros[prefix + "Low"] = f"{contrast['ci95'][0][p]:.3f}"
            macros[prefix + "High"] = f"{contrast['ci95'][1][p]:.3f}"
    write_macros(out / "ch3_self_similarity_values.tex", macros, generator=GENERATOR)


def write_report(
    measured, provenance, contract, out, *, snapshot=None, n_resamples=400
):
    """Compute or reuse an identified scaling measurement and render its products."""
    out = Path(out)
    source_files = [Path(analysis.__file__), Path(__file__)]
    identity = {
        "source_contract": contract,
        "source_provenance": provenance,
        "resamples": n_resamples,
        "seed": 20260911,
        "analysis_sha256": hashlib.sha256(source_files[0].read_bytes()).hexdigest(),
        "support_sha256": {
            name: hashlib.sha256(
                (source_files[0].parent / name).read_bytes()
            ).hexdigest()
            for name in ("segment_support.py", "joint_distribution.py")
        },
    }
    signature = hashlib.sha256(
        json.dumps(jsonable(identity), sort_keys=True).encode()
    ).hexdigest()
    report_path = out / "ch3_self_similarity.json"
    previous = json.loads(report_path.read_text()) if report_path.exists() else {}
    if previous.get("measurement_sha256") == signature:
        results = previous["results"]
        # Numerical arrays are kept in a private recursive conversion only where
        # plotting and fitting need them; dictionaries/lists of laws retain shape.
        for result in results.values():
            for key in (
                "lags_s",
                "quantiles_m",
                "dense_probabilities",
                "dense_quantiles_m",
            ):
                result[key] = np.asarray(result[key])
            for fit in result["fits"].values():
                for key in ("h", "h_ci95", "intercept_at_1000s", "common_h"):
                    fit[key] = np.asarray(fit[key])
            for law in result["laws"]:
                for key in ("edges_m", "mass"):
                    law[key] = np.asarray(law[key])
    else:
        results = {}
        for discipline, m in measured.items():
            print(f"Fixed-population scaling: {discipline}", flush=True)
            frames = analysis.recover_positions(m, contract["lags_s"])
            results[discipline] = analysis.measure_scaling(
                frames,
                contract["lags_s"],
                n_resamples=n_resamples,
                progress=lambda message: print(message, flush=True),
            )
            if "quantile_control" in m and not np.allclose(
                results[discipline]["quantiles_m"],
                m["quantile_control"]["quantiles"][3],
                rtol=1e-9,
                atol=1e-6,
            ):
                raise ValueError("Recovered paths disagree with saved fixed quantiles")
    report = {
        "measurement_sha256": signature,
        "identity": identity,
        "snapshot": snapshot,
        "method": (
            "Fixed segments >=20000 s; all common 10-s origins; equal flight "
            "weights; inverse weighted ECDF; whole-flight paired bootstrap"
        ),
        "squares": (
            "Monotone transform: quantiles squared, slopes doubled, identical "
            "bin masses on squared edges; ECDF distances invariant"
        ),
        "limitations": (
            "Fixed long-flight population within the identified input scope. "
            "Bootstrap assumes independent "
            "flights, does not model shared site/day weather, and intervals are "
            "pointwise. One-lag scale families do not establish "
            "process self-similarity."
        ),
        "code_sha256": {
            str(path): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in source_files
        },
        "results": results,
    }
    out.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        json.dumps(jsonable(report), indent=2, allow_nan=False) + "\n"
    )
    draw(results, out)
    write_tables(results, out)
    return report
