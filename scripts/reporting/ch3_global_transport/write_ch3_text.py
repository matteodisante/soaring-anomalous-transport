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

    general = [
        results[slug]["general"]["tamsd_global_fit"] for slug in ("para", "hang")
    ]
    save(
        "general_fit",
        [
            "The available-population fits give $H="
            + interval(general[0]["hurst"])
            + "$ for paragliders and $H="
            + interval(general[1]["hurst"])
            + "$ for hang gliders. These summarise growth with changing flight support. "
            f"The hang-glider fit reaches a tail supported by only {general[1]['minimum_group_support']} "
            f"groups; its interval uses {general[1]['valid_bootstrap_replicates']} replicates with complete lag support."
        ],
    )

    diagnostics = [results[slug]["cluster_diagnostics"] for slug in ("para", "hang")]

    def median_range(item, key, spatial=False):
        low, median, high = item[key]["p10_median_p90"]
        if spatial:
            return f"{median:.1f} [{low:.2f}, {high:.0f}]"
        return f"{median:.0f} [{low:.0f}, {high:.0f}]"

    rows = [
        ("Catalogue sites", [f"{s['sites']:,}" for s in diagnostics]),
        ("Calendar dates", [f"{s['dates']:,}" for s in diagnostics]),
        (
            "Flights per group: median / P95 / max",
            [
                " / ".join(f"{v:.0f}" for v in s["size_min_median_p95_max"][1:])
                for s in diagnostics
            ],
        ),
        (
            r"Largest group (\% of flights)",
            [f"{100 * s['largest_group_flight_fraction']:.2f}" for s in diagnostics],
        ),
        (
            "Nearest same-day site (km)",
            [median_range(s, "same_day_nearest_km", True) for s in diagnostics],
        ),
        (
            "Spatial comparisons",
            [f"{s['same_day_nearest_km']['n']:,}" for s in diagnostics],
        ),
        (
            "Prior observed date at same site: gap (days)",
            [median_range(s, "previous_observed_day_gap") for s in diagnostics],
        ),
        (
            "Temporal comparisons",
            [f"{s['previous_observed_day_gap']['n']:,}" for s in diagnostics],
        ),
        (
            "Flights with missing site/date keys",
            [f"{s['missing_key_flights']:,}" for s in diagnostics],
        ),
    ]
    lines = [
        r"\begin{tabular}{lrr}",
        r"\toprule",
        r"Quantity & Paragliders & Hang gliders \\",
        r"\midrule",
    ]
    lines.extend(
        label + " & " + " & ".join(entries) + r" \\" for label, entries in rows
    )
    lines.extend([r"\bottomrule", r"\end{tabular}"])
    save("cluster_context", ["\n".join(lines)])

    fractions = []
    for slug, d in results.items():
        start = d["cohorts"]["100"]
        main = d["cohorts"]["10000"]
        a = 100 * start["task_counts"].get("closed", 0) / start["flights"]
        b = 100 * main["task_counts"].get("closed", 0) / main["flights"]
        fractions.append(f"{a:.1f}\\% to {b:.1f}\\% for {names[slug]}")
    save(
        "cohort_composition",
        [
            "From $\\mathcal C_{100}$ to $\\mathcal C_{10000}$, the closed-route fraction "
            "rises from " + " and from ".join(fractions) + "."
        ],
    )
    paragraphs = []
    main_contrasts = []
    for d in results.values():
        comparisons = d["cohort_h_comparisons"]
        broad = comparisons["10-100"]["contrasts"]["100_minus_1000"]
        assert abs(broad["point"]) < 1e-4, (
            "Update the cohort effect-size interpretation"
        )
        main_contrasts.extend(
            contrast
            for comparison in comparisons.values()
            for key, contrast in comparison["contrasts"].items()
            if key.endswith("minus_10000")
        )
    paragraphs.append(
        "On 10--100 s, $\\mathcal C_{100}$ and $\\mathcal C_{1000}$ differ in $H$ by "
        "less than $10^{-4}$ in both disciplines. The paired interval resolves this tiny "
        "difference for paragliders; for hang gliders it includes zero. "
        "The extensive overlap of these cohorts makes the paired comparison particularly precise."
    )
    if all(contrast["high"] < 0 for contrast in main_contrasts):
        paragraphs.append(
            "The main cohort has a larger effective exponent in both matched fit intervals "
            "and both disciplines; every paired comparison with a broader cohort excludes zero."
        )
    save("cohort_effect", paragraphs)

    d = results["para"]
    paragraphs = []
    for label, counts, n in (
        (
            "Eligible flights",
            d["eligible_task_counts"],
            d["eligible_flights"],
        ),
        (
            "Main-cohort flights",
            d["cohorts"]["10000"]["task_counts"],
            d["cohorts"]["10000"]["flights"],
        ),
    ):
        paragraphs.append(
            f"{label}: {counts['open']:,} open "
            f"({100 * counts['open'] / n:.1f}\\%), {counts['closed']:,} closed "
            f"({100 * counts['closed'] / n:.1f}\\%), and {counts.get('unknown', 0):,} "
            "unclassified."
        )
    save("task_composition", paragraphs)
    contrasts = d["hurst_contrasts"]
    direct = [contrasts[f"open_minus_closed_{i}"]["point"] for i in range(4)]
    save(
        "task_contrasts",
        [
            f"The paired contrasts $H_{{\\rm open}}-H_{{\\rm closed}}$ range from "
            f"{min(direct):.3f} to {max(direct):.3f}; all four 90\\% intervals exclude zero."
        ],
    )

    minima = []
    for slug, d in results.items():
        g = d["general"]
        x = np.asarray(g["lags"])
        h = np.asarray(g["ensemble_local_h"], dtype=float)
        keep = np.flatnonzero((x >= 20) & (x <= 2000) & np.isfinite(h))
        j = keep[np.argmin(h[keep])]
        minima.append(f"{x[j]:.0f} s ($H_{{\\rm loc}}={h[j]:.2f}$) for {names[slug]}")
    save(
        "launch_interpretation",
        [
            "The origin-distance means are approximately ballistic at the earliest resolved lags. "
            "Their local slopes reach minima at "
            + " and ".join(minima)
            + " within 20--2000 s, then recover towards $H_{\\rm loc}\\simeq1$ around 600--700 s."
        ],
    )

    paragraphs = []
    for slug, d in results.items():
        ratio = np.asarray(d["quantile_ratio"]["point"])[:, 2]
        x = np.asarray(d["lags"])
        early = np.flatnonzero(x <= 200)
        j = early[np.argmin(ratio[early])]
        # The early minimum is followed by a broad maximum before long-lag decline.
        late = np.flatnonzero((x >= 200) & (x <= 5000))
        k = late[np.argmax(ratio[late])]
        rms = np.asarray(d["scaling_fits"]["10-10000"]["quantile_rms_dex"]["point"])
        paragraphs.append(
            f"For {names[slug]}, the radial ratio falls from {ratio[0]:.3f} at 10 s "
            f"to {ratio[j]:.3f} at {x[j]:.0f} s, rises to {ratio[k]:.3f} at {x[k]:.0f} s, "
            f"then falls to {ratio[-1]:.3f} at 10000 s. "
            f"Quantile-fit RMS residuals span {rms.min():.3f}--{rms.max():.3f} dex."
        )
    paragraphs.append(
        "A positive global slope of these nonmonotonic ratios can coexist with a net endpoint decrease."
    )
    save("quantile_findings", paragraphs)

    paragraphs = []
    for slug, d in results.items():
        s = d["scaling_fits"]["10-10000"]
        contrast = interval(s["H4_minus_H025"], 2, digits=4)
        rms = np.asarray(s["moment_rms_dex"]["point"])
        paragraphs.append(
            f"For {names[slug]}, the radial contrast "
            f"$\\zeta(4)/4-\\zeta(0.25)/0.25$ is {contrast}. "
            f"Moment-fit RMS residuals span {rms.min():.3f}--{rms.max():.3f} dex across all amplitudes and orders."
        )
    save("moment_findings", paragraphs)

    paragraphs = []
    for slug, d in results.items():
        a = np.asarray(d["kurtosis"]["point"])
        paragraphs.append(
            f"For {names[slug]}, $(K_E,K_N)$ changes from "
            f"$({a[0, 0]:.2f},{a[0, 1]:.2f})$ at 10 s to "
            f"$({a[-1, 0]:.2f},{a[-1, 1]:.2f})$ at 10000 s."
        )
    save("kurtosis_findings", paragraphs)
    save(
        "scaling_conclusion",
        [
            "Over 10--10000 s, a single self-similar model with stationary increments "
            "does not adequately describe the pooled displacement law."
        ],
    )
