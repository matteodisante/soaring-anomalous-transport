#!/usr/bin/env python3
"""Separate observed flight duration and equipment composition in archive TAMSDs.

Reuses identified segment curves from measure_msd.py. Within each flight, segment
curves are weighted by their available time origins; population curves then give
each contributing flight equal weight. Durations sum all retained segment spans.
Beginners (EN A/B) and experts (EN C/D/CCC) are equipment-based experience proxies;
the catalogue does not independently measure each pilot's skill.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "src"))
from soaring.analysis.observables.global_diagnostics import log_slope  # noqa: E402
from soaring.reporting import (  # noqa: E402
    DISCIPLINES,
    canonical_wing_class,
    write_macros,
)
from soaring.reporting.glider_class import (  # noqa: E402
    EQUIPMENT_CLASSES,
    EQUIPMENT_LABELS,
    EQUIPMENT_TAGS,
    equipment_group,
)
from soaring.reporting.style import (  # noqa: E402
    DURATION_COLORS,
    EQUIPMENT_COLORS,
    PDF_METADATA,
    paper_style,
)

GENERATED_OUTPUTS = (
    "ch3_duration.pdf",
    "ch3_duration_equipment.pdf",
    "ch3_duration_composition.pdf",
    "duration_equipment.tex",
    "duration_equipment_table.tex",
    "duration_bands_table.tex",
    "duration_equipment.json",
)
OUT = ROOT / "thesis/generated"
THRESHOLDS = (0, 3600, 7200, 14400)
COHORT_NAMES = ("All durations", "T ≥ 1 h", "T ≥ 2 h", "T ≥ 4 h")
# Disjoint duration bands for the duration figure. Nested thresholds answer whether a
# pooled exponent survives restriction; they cannot show how transport depends on
# duration, because consecutive cohorts share most of their flights -- all durations and
# T >= 1 h overlap by 96% -- and each is a subset of the previous, so only a monotone
# progression can appear. Bands are near-independent samples and admit a non-monotone
# dependence. The equipment comparison below keeps the nested thresholds.
BANDS = ((0, 3600), (3600, 7200), (7200, 14400), (14400, np.inf))
BAND_NAMES = ("T < 1 h", "1 ≤ T < 2 h", "2 ≤ T < 4 h", "T ≥ 4 h")
BAND_TEX = (r"$T<1$ h", r"$1\le T<2$ h", r"$2\le T<4$ h", r"$T\ge4$ h")
BAND_TAGS = ("BandUnderOneH", "BandOneToTwoH", "BandTwoToFourH", "BandOverFourH")
REFERENCE_LAG_S = 1000.0
LINESTYLES = ("-", "--", "-.", ":")
MIN_FLIGHTS = 30


def flight_curves(samples, segments, lags):
    """Combine segment sums and admissible-origin counts, never equal segment means."""
    samples = np.asarray(samples, dtype=float)
    if len(segments) != len(samples):
        raise ValueError("Segment metadata and TAMSD rows differ")
    eligible = (segments.dt_s.to_numpy() <= 10) & (segments.dt_s.to_numpy() > 0)
    segments = segments.loc[eligible].reset_index(drop=True)
    samples = samples[eligible]
    if segments.empty:
        raise ValueError("No segment has a native interval at most 10 s")
    ids = segments.flight_id.astype(str).to_numpy()
    starts = np.r_[0, np.flatnonzero(ids[1:] != ids[:-1]) + 1]
    if len(np.unique(ids)) != len(starts):
        raise ValueError("Segment rows for each flight must be contiguous")
    rounded_lags = np.rint(
        np.asarray(lags)[None, :] / segments.dt_s.to_numpy()[:, None]
    )
    weights = np.maximum(segments.n_fixes.to_numpy()[:, None] - rounded_lags, 0)
    weights = np.where(np.isfinite(samples), weights, 0)
    numerator = np.add.reduceat(np.nan_to_num(samples) * weights, starts, axis=0)
    denominator = np.add.reduceat(weights, starts, axis=0)
    values = np.divide(
        numerator,
        denominator,
        out=np.full_like(numerator, np.nan),
        where=denominator > 0,
    )
    frame = segments.iloc[starts][
        ["flight_id", "total_retained_duration_s"]
    ].reset_index(drop=True)
    return frame, values


def mean_curve(values, mask):
    selected = values[np.asarray(mask, dtype=bool)]
    count = np.isfinite(selected).sum(axis=0)
    mean = np.divide(
        np.nansum(selected, axis=0),
        count,
        out=np.full(values.shape[1], np.nan),
        where=count > 0,
    )
    return mean, count


def composition_control(values, frame):
    """Compare actual class mixtures with a fixed reference over known EN groups."""
    classes = list(EQUIPMENT_CLASSES)
    labels = frame.equipment.to_numpy()
    duration = frame.total_retained_duration_s.to_numpy()
    reference = np.array([(labels == c).sum() for c in classes], dtype=float)
    if reference.sum() == 0:
        raise ValueError("No flights belong to the defined EN groups")
    reference /= reference.sum()
    result = []
    for threshold in THRESHOLDS:
        selected = duration >= threshold
        rows = []
        for c in classes:
            mask = selected & (labels == c)
            curve, count = mean_curve(values, mask)
            rows.append(
                {
                    "class": c,
                    "flights": int(mask.sum()),
                    "curve": curve,
                    "support": count,
                }
            )
        curves = np.asarray([row["curve"] for row in rows])
        supports = np.asarray([row["support"] for row in rows])
        supported = np.all(supports >= MIN_FLIGHTS, axis=0)
        standardized = np.sum(reference[:, None] * curves, axis=0)
        standardized[~supported] = np.nan
        raw, raw_count = mean_curve(values, selected & np.isin(labels, classes))
        result.append(
            {
                "threshold_s": threshold,
                "total_flights": int(selected.sum()),
                "other_flights": int(np.sum(selected & ~np.isin(labels, classes))),
                "classes": rows,
                "standardized": standardized,
                "known_class_raw": raw,
                "known_class_support": raw_count,
            }
        )
    return reference, result


def load(glider, audit_dir):
    with np.load(audit_dir / f"msd_{glider.slug}.npz") as archive:
        lags = archive["lags"]
        keep = (lags >= 10) & (lags <= 10000)
        samples = archive["time_averaged_samples"][:, keep]
        lags = lags[keep]
    segments = pd.read_parquet(audit_dir / f"msd_segments_{glider.slug}.parquet")
    frame, values = flight_curves(samples, segments, lags)
    catalog = pd.read_csv(
        glider.catalog_path(),
        usecols=["flight_id", "wing_class"],
        dtype={"flight_id": str},
    )
    catalog["canonical_class"] = canonical_wing_class(glider.name, catalog.wing_class)
    frame["flight_id"] = frame.flight_id.astype(str)
    frame = frame.merge(
        catalog[["flight_id", "canonical_class"]],
        on="flight_id",
        how="left",
        sort=False,
        validate="one_to_one",
    )
    frame["equipment"] = equipment_group(frame.canonical_class)
    return lags, frame, values


def _axis(ax, title, *, ratio=False):
    ax.set(
        xscale="log",
        yscale="linear" if ratio else "log",
        xlim=(10, 10000),
        xlabel=r"Lag $\tau$ (s)",
        ylabel="Ratio to all durations"
        if ratio
        else r"$M_2^{\rm flight}(\tau)$ (m$^2$)",
        title=title,
    )
    ax.grid(False)


def _line(ax, lags, curve, count, color, style, name, threshold=0):
    valid = (count >= MIN_FLIGHTS) & np.isfinite(curve) & (curve > 0)
    if threshold:
        valid &= lags <= threshold / 2
    if not valid.any():
        return
    low, high = int(count[valid].min()), int(count[valid].max())
    text = f"N={high:,}" if low == high else f"N={low:,}–{high:,}"
    ax.plot(
        lags,
        np.where(valid, curve, np.nan),
        style,
        color=color,
        label=f"{name}; {text}",
    )


def portable(value):
    if isinstance(value, dict):
        return {k: portable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, np.ndarray)):
        return [portable(v) for v in value]
    if isinstance(value, np.generic):
        return portable(value.item())
    if isinstance(value, float) and not np.isfinite(value):
        return None
    return value


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--audit-dir", type=Path, required=True)
    args = parser.parse_args()
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    paper_style()
    loaded = {name: load(g, args.audit_dir) for name, g in DISCIPLINES.items()}
    macros, records = {}, {}
    fig, axes = plt.subplots(2, 2, figsize=(6.1, 5.2), layout="constrained")
    for column, (name, (lags, frame, values)) in enumerate(loaded.items()):
        glider = DISCIPLINES[name]
        duration = frame.total_retained_duration_s.to_numpy()
        pooled, _ = mean_curve(values, np.ones(len(duration), dtype=bool))
        reference = int(np.argmin(abs(lags - REFERENCE_LAG_S)))
        bands = []
        for (low, high), label, tag, color, linestyle in zip(
            BANDS, BAND_NAMES, BAND_TAGS, DURATION_COLORS, LINESTYLES, strict=True
        ):
            selected = (duration >= low) & (duration < high)
            curve, count = mean_curve(values, selected)
            _line(axes[0, column], lags, curve, count, color, linestyle, label, low)
            # A band holds its membership only out to half its lower edge, which is
            # why the curves end at different lags. The lowest band has no such range.
            valid = (count >= MIN_FLIGHTS) & np.isfinite(curve) & (curve > 0)
            if low:
                valid &= lags <= low / 2
            axes[1, column].plot(
                lags,
                np.where(valid, curve / pooled, np.nan),
                linestyle,
                color=color,
            )
            bands.append(
                {
                    "low_s": low,
                    "high_s": high if np.isfinite(high) else None,
                    "flights": int(selected.sum()),
                    "curve": curve,
                    "support": count,
                    "valid": valid,
                }
            )
            macros[f"StatDuration{glider.tag}{tag}Flights"] = str(int(selected.sum()))
            macros[f"StatDuration{glider.tag}{tag}RmsKm"] = (
                f"{np.sqrt(curve[reference]) / 1000:.2f}"
            )
            macros[f"StatDuration{glider.tag}{tag}Ratio"] = (
                f"{curve[reference] / pooled[reference]:.2f}"
            )
        _axis(axes[0, column], name.capitalize())
        axes[0, column].legend(
            loc="best", fontsize=7, frameon=True, framealpha=0.85, edgecolor="none"
        )
        axes[1, column].axhline(1.0, color=".75", lw=0.6)
        _axis(axes[1, column], f"Ratio, {name}", ratio=True)
        macros[f"StatDuration{glider.tag}Flights"] = str(len(frame))
        records[name] = {"lags_s": lags, "bands": bands, "pooled": pooled}
    shared_lags = loaded["paragliders"][0]
    if not all(np.array_equal(shared_lags, lags) for lags, _, _ in loaded.values()):
        raise ValueError("Disciplines must share one lag grid to be tabulated together")
    macros["StatDurationReferenceLagS"] = (
        f"{shared_lags[int(np.argmin(abs(shared_lags - REFERENCE_LAG_S)))]:.0f}"
    )
    fig.savefig(OUT / "ch3_duration.pdf", metadata=PDF_METADATA)
    plt.close(fig)

    # Every band is read over one lag range, the intersection of their supports across
    # both disciplines. Each band ends at its own T_0/2, so fitting each on its own span
    # would compare different parts of a bending curve and report the difference as an
    # effect of duration. The all-duration curve is refitted here for the same reason.
    common = np.ones(shared_lags.size, dtype=bool)
    for entry in records.values():
        for band in entry["bands"]:
            common &= band["valid"]
    if common.sum() < 4:
        raise ValueError("No common lag range supports every duration band")
    band_table = [
        "% Generated by scripts/esperimenti/ch04_global_transport/"
        "generate_duration_equipment.py",
        r"\begin{tabular}{@{}llrrrr@{}}",
        r"\toprule",
        r"Discipline & Duration & Flights & $b$ & $H=b/2$ & RMS residual (dex) \\",
        r"\midrule",
    ]
    for name, entry in records.items():
        glider = DISCIPLINES[name]
        rows = [("All durations", entry["pooled"], len(loaded[name][1]))]
        rows += [
            (label, band["curve"], band["flights"])
            for label, band in zip(BAND_TEX, entry["bands"], strict=True)
        ]
        slopes = {}
        for (label, curve, flights), tag in zip(
            rows, ("Pooled", *BAND_TAGS), strict=True
        ):
            slope, residual = log_slope(shared_lags[common], curve[common])
            slopes[tag] = slope
            macros[f"StatDuration{glider.tag}{tag}Exponent"] = f"{slope:.3f}"
            macros[f"StatDuration{glider.tag}{tag}Hurst"] = f"{slope / 2:.3f}"
            macros[f"StatDuration{glider.tag}{tag}ResidualDex"] = f"{residual:.3f}"
            band_table.append(
                f"{name.capitalize()} & {label} & {flights:,} "
                f"& {slope:.3f} & {slope / 2:.3f} & {residual:.3f}" + r" \\"
            )
        # Evaluated here rather than typeset as a subtraction of two macros.
        band_only = [slopes[tag] for tag in BAND_TAGS]
        macros[f"StatDuration{glider.tag}BandHurstSpread"] = (
            f"{(max(band_only) - min(band_only)) / 2:.3f}"
        )
        band_table.append(r"\addlinespace")
    band_table += [r"\bottomrule", r"\end{tabular}"]
    (OUT / "duration_bands_table.tex").write_text("\n".join(band_table) + "\n")
    macros["StatDurationBandFitMinS"] = f"{shared_lags[common][0]:.0f}"
    macros["StatDurationBandFitMaxS"] = f"{shared_lags[common][-1]:.0f}"

    lags, frame, values = loaded["paragliders"]
    reference, cohorts = composition_control(values, frame)
    # One common lag set across every equipment/duration cell makes fitted slopes
    # directly comparable. Unsupported ends are reported rather than extrapolated.
    common = lags <= min(t for t in THRESHOLDS if t > 0) / 2
    for cohort in cohorts:
        for row in cohort["classes"]:
            common &= (row["support"] >= MIN_FLIGHTS) & (row["curve"] > 0)
    if common.sum() < 4:
        raise ValueError(
            "Too little common support for the duration/equipment comparison"
        )
    for cohort in cohorts:
        for row in cohort["classes"]:
            row["exponent"], row["residual_dex"] = log_slope(
                lags[common], row["curve"][common]
            )
    full = np.all(
        [row["support"] >= MIN_FLIGHTS for row in cohorts[0]["classes"]], axis=0
    )
    full &= np.all([row["curve"] > 0 for row in cohorts[0]["classes"]], axis=0)
    if full.sum() < 4:
        raise ValueError("Too little support for unconditional equipment slopes")
    for row in cohorts[0]["classes"]:
        tag = EQUIPMENT_TAGS[row["class"]]
        exponent, residual = log_slope(lags[full], row["curve"][full])
        row.update(full_range_exponent=exponent, full_range_residual_dex=residual)
        macros[f"StatDuration{tag}FullExponent"] = f"{exponent:.3f}"
    macros["StatDurationFullFitMinS"] = f"{lags[full][0]:.0f}"
    macros["StatDurationFullFitMaxS"] = f"{lags[full][-1]:.0f}"
    macros.update(
        {
            "StatDurationFitMinS": f"{lags[common][0]:.0f}",
            "StatDurationFitMaxS": f"{lags[common][-1]:.0f}",
            "StatDurationMinFlights": str(MIN_FLIGHTS),
            "StatDurationUnknownFlights": str(cohorts[0]["other_flights"]),
        }
    )
    fig, axes = plt.subplots(1, 2, figsize=(6.1, 3.3), layout="constrained")
    for j, (ax, c) in enumerate(zip(axes, EQUIPMENT_CLASSES, strict=True)):
        for cohort, label, linestyle in zip(
            cohorts, COHORT_NAMES, LINESTYLES, strict=True
        ):
            row = cohort["classes"][j]
            _line(
                ax,
                lags,
                row["curve"],
                row["support"],
                EQUIPMENT_COLORS[c],
                linestyle,
                label,
                cohort["threshold_s"],
            )
        _axis(ax, f"{EQUIPMENT_LABELS[c]} ({c})")
        ax.legend(
            loc="best", fontsize=7, frameon=True, framealpha=0.85, edgecolor="none"
        )
    fig.savefig(OUT / "ch3_duration_equipment.pdf", metadata=PDF_METADATA)
    plt.close(fig)

    fig, axes = plt.subplots(1, 2, figsize=(6.1, 3.3), layout="constrained")
    bottom = np.zeros(4)
    for j, c in enumerate([*EQUIPMENT_CLASSES, "Other / unknown"]):
        count = np.array(
            [
                cohort["classes"][j]["flights"]
                if j < len(EQUIPMENT_CLASSES)
                else cohort["other_flights"]
                for cohort in cohorts
            ]
        )
        fraction = count / np.array([cohort["total_flights"] for cohort in cohorts])
        axes[0].bar(
            range(4),
            fraction,
            bottom=bottom,
            color=EQUIPMENT_COLORS.get(c, ".72"),
            label=EQUIPMENT_LABELS.get(c, c),
            width=0.66,
        )
        bottom += fraction
    axes[0].set(
        xticks=range(4),
        xticklabels=["All", "≥1 h", "≥2 h", "≥4 h"],
        ylim=(0, 1),
        ylabel="Fraction of flights",
        xlabel="Retained flight duration T",
        title="(a) Equipment composition",
    )
    axes[0].legend(
        loc="upper center", bbox_to_anchor=(0.5, -0.28), ncol=2, fontsize=7.2
    )
    raw = cohorts[-1]["known_class_raw"] / cohorts[0]["known_class_raw"]
    adjusted = cohorts[-1]["standardized"] / cohorts[0]["standardized"]
    ratio_support = (
        (lags <= THRESHOLDS[-1] / 2) & np.isfinite(adjusted) & np.isfinite(raw)
    )
    axes[1].semilogx(
        lags[ratio_support],
        raw[ratio_support],
        color=".25",
        label="Observed class mixture",
    )
    axes[1].semilogx(
        lags[ratio_support],
        adjusted[ratio_support],
        "--",
        color="#3A3A3A",
        label="Fixed class proportions",
    )
    _axis(axes[1], "(b) T ≥ 4 h / all durations", ratio=True)
    axes[1].axhline(1, color=".5", ls=":", lw=0.7)
    axes[1].legend(loc="upper center", bbox_to_anchor=(0.5, -0.28), fontsize=7.2)
    fig.savefig(OUT / "ch3_duration_composition.pdf", metadata=PDF_METADATA)
    plt.close(fig)

    table = [
        "% Generated by scripts/esperimenti/ch04_global_transport/generate_duration_equipment.py",
        r"\begin{tabular}{@{}llrrr@{}}",
        r"\toprule",
        r"Experience proxy & Duration & Flights & $b$ & RMS residual (dex) \\",
        r"\midrule",
    ]
    for j, c in enumerate(EQUIPMENT_CLASSES):
        for cohort, label in zip(
            cohorts, ("All", r"$T\ge1$ h", r"$T\ge2$ h", r"$T\ge4$ h"), strict=True
        ):
            row = cohort["classes"][j]
            table.append(
                f"{EQUIPMENT_LABELS[c]} & {label} & {row['flights']:,} & {row['exponent']:.3f} & {row['residual_dex']:.3f}"
                + r" \\"
            )
        table.append(r"\addlinespace")
    table += [r"\bottomrule", r"\end{tabular}"]
    (OUT / "duration_equipment_table.tex").write_text("\n".join(table) + "\n")
    records["equipment_control"] = {
        "experience_proxy_labels": EQUIPMENT_LABELS,
        "equipment_classes": EQUIPMENT_CLASSES,
        "reference_proportions": dict(zip(EQUIPMENT_CLASSES, reference, strict=True)),
        "common_lags_s": lags[common],
        "unconditional_fit_lags_s": lags[full],
        "ratio_display_lags_s": lags[ratio_support],
        "cohorts": cohorts,
        "raw_four_hour_ratio": raw,
        "fixed_mix_four_hour_ratio": adjusted,
    }
    (OUT / "duration_equipment.json").write_text(
        json.dumps(portable(records), indent=2) + "\n"
    )
    write_macros(
        OUT / "duration_equipment.tex",
        macros,
        generator="scripts/esperimenti/ch04_global_transport/generate_duration_equipment.py",
    )
    print(
        f"Duration/equipment control: {len(frame)} flights; common lag range {lags[common][0]:g}–{lags[common][-1]:g} s"
    )


if __name__ == "__main__":
    main()
