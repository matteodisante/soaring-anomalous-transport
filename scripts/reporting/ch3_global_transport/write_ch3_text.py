"""Numerical prose and macros generated from the validated Chapter 3 report."""

from __future__ import annotations

# ruff: noqa: E501 -- keep numerical prose literals readable for manuscript review
import numpy as np


def interval(stats, index=None, digits=3):
    """Render a point estimate and central percentile interval."""
    values = [np.asarray(stats[k]) for k in ("point", "low", "high")]
    if index is not None:
        values = [v[index] for v in values]
    return f"{values[0]:.{digits}f} [{values[1]:.{digits}f}, {values[2]:.{digits}f}]"


def write_text(report, out):
    """Keep reported counts and numerical comparisons synchronised with plots."""
    results = report["results"]
    names = {"para": "paragliders", "hang": "hang gliders"}
    values = []
    for slug, d in results.items():
        prefix = "Para" if slug == "para" else "Hang"
        n = d["interpolation"]["10000"]["grid_exact_previously_interpolated"]
        values.append(
            r"\newcommand{\ChThree" + prefix + r"PriorInterp}{" + f"{n:,}" + "}"
        )
    (out / "ch3_transport_values.tex").write_text("\n".join(values) + "\n")

    def save(name, paragraphs):
        (out / f"ch3_transport_{name}.tex").write_text("\n\n".join(paragraphs) + "\n")

    paragraphs = []
    for slug, d in results.items():
        s = d["cluster_diagnostics"]
        spatial = s["same_day_nearest_km"]
        temporal = s["previous_observed_day_gap"]
        p10, med, p90 = spatial["p10_median_p90"]
        t10, tmed, t90 = temporal["p10_median_p90"]
        sizes = s["size_min_median_p95_max"]
        paragraphs.append(
            f"For {names[slug]}, the main cohort spans {s['sites']:,} catalogue sites and "
            f"{s['dates']:,} dates; group size has median {sizes[1]:.0f}, "
            f"the 95th percentile {sizes[2]:.0f}, and the largest group {sizes[3]:.0f} "
            f"({100 * s['largest_group_flight_fraction']:.2f}\\% of flights). "
            f"Where another site is represented on the same day ({spatial['n']:,} of "
            f"{s['groups']:,} groups), its nearest distance has median {med:.1f} km "
            f"and 10--90\\% range {p10:.2f}--{p90:.0f} km. "
            f"The gap from the previous observed date at the same site is "
            f"{tmed:.0f} days (10--90\\%: {t10:.0f}--{t90:.0f}; "
            f"{temporal['n']:,} comparisons). "
            f"Missing group keys affect {s['missing_key_flights']:,} main-cohort flights."
        )
    save("cluster_context", paragraphs)

    paragraphs = []
    for slug, d in results.items():
        start = d["cohorts"]["100"]
        main = d["cohorts"]["10000"]
        a = 100 * start["task_counts"].get("closed", 0) / start["flights"]
        b = 100 * main["task_counts"].get("closed", 0) / main["flights"]
        paragraphs.append(
            f"The closed-route fraction changes from {a:.1f}\\% in $\\mathcal C_{{100}}$ "
            f"to {b:.1f}\\% in $\\mathcal C_{{10000}}$ for {names[slug]}. "
            "Thus duration selection measurably changes circuit composition."
        )
    save("cohort_composition", paragraphs)
    paragraphs = []
    for slug, d in results.items():
        x = np.asarray(d["msd_lags"])
        i = int(np.flatnonzero(x == 100)[0])
        j = int(np.flatnonzero(x == 1000)[0])
        short = interval(d["cohort_ratios"]["1"], i)
        medium = interval(d["cohort_ratios"]["2"], j)
        paragraphs.append(
            f"For {names[slug]}, the dedicated-to-main MSD ratio is {short} at 100 s "
            f"and {medium} at 1000 s. The long-flight requirement therefore selects "
            "larger mean displacements at shared lags, with differences exceeding "
            "the paired bootstrap variability."
        )
    save("cohort_effect", paragraphs)

    d = results["para"]
    paragraphs = []
    for label, counts, n in (
        (
            "The eligible common-grid population",
            d["eligible_task_counts"],
            d["eligible_flights"],
        ),
        (
            "The main cohort",
            d["cohorts"]["10000"]["task_counts"],
            d["cohorts"]["10000"]["flights"],
        ),
    ):
        paragraphs.append(
            f"{label} contains {counts['open']:,} open flights "
            f"({100 * counts['open'] / n:.1f}\\%), {counts['closed']:,} closed flights "
            f"({100 * counts['closed'] / n:.1f}\\%), and {counts.get('unknown', 0):,} "
            "without a recognised circuit class."
        )
    save("task_composition", paragraphs)
    contrasts = d["hurst_contrasts"]
    direct = [interval(contrasts[f"open_minus_closed_{i}"]) for i in range(4)]
    save(
        "task_contrasts",
        [
            "The paired contrasts $H_{\\rm open}-H_{\\rm closed}$ are "
            + ", ".join(direct)
            + ", in ascending altitude-band order. "
            "Each interval lies above zero under the adopted cluster resampling."
        ],
    )

    paragraphs = []
    for slug, d in results.items():
        g = d["general"]
        x = np.asarray(g["lags"])
        h = np.asarray(g["ensemble_local_h"], dtype=float)
        keep = np.flatnonzero((x >= 20) & (x <= 2000) & np.isfinite(h))
        j = keep[np.argmin(h[keep])]
        paragraphs.append(
            f"For {names[slug]}, the origin-distance mean has an early local-slope "
            f"minimum at the evaluated lag {x[j]:.0f} s, with $H_{{\\rm loc}}={h[j]:.2f}$ "
            "(search interval 20--2000 s)."
        )
    paragraphs.append(
        "Both curves are approximately ballistic at the earliest resolved lags and "
        "recover towards $H_{\\rm loc}\\simeq1$ around 600--700 s "
        "(Fig.~\\ref{fig:fixed-general-slopes})."
    )
    save("launch_interpretation", paragraphs)

    paragraphs = []
    for slug, d in results.items():
        ratio = np.asarray(d["quantile_ratio"]["point"])[:, 2]
        x = np.asarray(d["lags"])
        early = np.flatnonzero(x <= 200)
        j = early[np.argmin(ratio[early])]
        # The early minimum is followed by a broad maximum before long-lag decline.
        late = np.flatnonzero((x >= 200) & (x <= 5000))
        k = late[np.argmax(ratio[late])]
        contrast = interval(d["scaling_fits"]["10-10000"]["H25_minus_H90"], 2)
        rms = np.asarray(d["scaling_fits"]["10-10000"]["quantile_rms_dex"]["point"])
        paragraphs.append(
            f"For {names[slug]}, the radial ratio is {ratio[0]:.3f} at 10 s, "
            f"has an early minimum of {ratio[j]:.3f} at {x[j]:.0f} s, "
            f"and takes the value {ratio[k]:.3f} at {x[k]:.0f} s before "
            f"ending at {ratio[-1]:.3f} at 10000 s. "
            f"The global radial contrast $H_{{25}}-H_{{90}}$ is {contrast}. "
            f"Quantile-fit RMS residuals span {rms.min():.3f}--{rms.max():.3f} dex."
        )
    paragraphs.append(
        "The nonmonotonic ratios show changes of distributional shape across scales. "
        "A global positive ratio slope summarises all fitted lags and need not imply "
        "a net increase between the two endpoints. The effective quantile exponents "
        "must therefore be read together with the curves."
    )
    save("quantile_findings", paragraphs)

    paragraphs = []
    for slug, d in results.items():
        s = d["scaling_fits"]["10-10000"]
        h = interval(d["fits"]["10-10000"]["hurst"])
        contrast = interval(s["H4_minus_H025"], 2, digits=4)
        rms = np.asarray(s["moment_rms_dex"]["point"])
        paragraphs.append(
            f"The single global MSD exponent is $H={h}$ for {names[slug]}. "
            f"The radial contrast $\\zeta(4)/4-\\zeta(0.25)/0.25$ is {contrast}; "
            f"across all three amplitudes and orders, moment-fit RMS residuals range "
            f"from {rms.min():.3f} to {rms.max():.3f} dex."
        )
    paragraphs.append(
        "The decade fits and local slopes expose crossovers within the full interval. "
        "Accordingly, a small departure of the fitted spectrum from $qH$ is evidence "
        "against a common effective exponent on these scales, rather than a measurement "
        "of an asymptotic multifractal law."
    )
    save("moment_findings", paragraphs)

    paragraphs = []
    for slug, d in results.items():
        a = np.asarray(d["kurtosis"]["point"])
        paragraphs.append(
            f"For {names[slug]}, $(K_E,K_N)$ changes from "
            f"$({a[0, 0]:.2f},{a[0, 1]:.2f})$ at 10 s to "
            f"$({a[-1, 0]:.2f},{a[-1, 1]:.2f})$ at 10000 s. "
            "The short-lag negative excess and long-lag positive excess show a change "
            "in standardised fourth-moment shape."
        )
    save("kurtosis_findings", paragraphs)
    save(
        "scaling_conclusion",
        [
            "The finite-range evidence does not support one common displacement scale "
            "exponent over 10--10000 s: quantile ratios vary, fitted quantile slopes differ, "
            "and standardised fourth moments change with lag. The global MSD exponent remains "
            "a useful summary of net growth. Approximate linearity of a moment spectrum "
            "alone does not establish monofractal scaling across an interval containing "
            "these crossovers."
        ],
    )
