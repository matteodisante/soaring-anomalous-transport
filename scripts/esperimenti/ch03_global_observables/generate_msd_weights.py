#!/usr/bin/env python3
r"""Compare the three population weightings of the archive segment TAMSDs.

Reuses the identified segment curves ``measure_msd.py`` stored, so the weights are the
only thing separating the three curves: the segments, their lag support and the
population behind them are shared. Writes ``ch3_msd_weights.pdf``, the curves behind it
and the macros the chapter quotes.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
OUT_FIG = ROOT / "thesis" / "generated" / "ch3_msd_weights.pdf"
OUT_CSV = ROOT / "thesis" / "generated" / "ch3_msd_weights.csv"
OUT_TEX = ROOT / "thesis" / "generated" / "ch3_msd_weights.tex"

_SRC = str(ROOT / "src")
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

# The sys.path line above is what makes this resolvable when the script is run
# directly, so the import cannot move to the top of the file.
from soaring.reporting import DISCIPLINES, write_macros  # noqa: E402
from soaring.reporting.style import CONTROL_COLORS  # noqa: E402

# The chapter's comparison interval, and generate_msd_figure.py's own TA fit range.
# Duplicated rather than imported, the way COHORTS_S is: one script's fit range is not
# the other's contract, and a shared import would hide a later divergence.
FIT_MIN_S, FIT_MAX_S = 10.0, 10_000.0

# Sampling conventions, which is what CONTROL_COLORS is for. The segment convention
# takes the neutral first value: it is the reference here and the one Fig. 3.1b draws.
ESTIMATORS = (
    ("segment", "Equal segment", CONTROL_COLORS[0], "-"),
    ("flight", "Equal flight", CONTROL_COLORS[1], "--"),
    ("window", "Equal window", CONTROL_COLORS[2], "-."),
)

_PDF_METADATA = {
    "Creator": "soaring.analysis",
    "Producer": "soaring.analysis",
    "CreationDate": None,
}


def load(slug: str, audit_dir: Path):
    """The stored segment curves and the identity table that explains their support."""
    from soaring.analysis.observables.transport import admissible_windows

    arrays = audit_dir / f"msd_{slug}.npz"
    identities = audit_dir / f"msd_segments_{slug}.parquet"
    if not (arrays.is_file() and identities.is_file()):
        return None
    with np.load(arrays) as archive:
        lags = archive["lags"]
        samples = archive["time_averaged_samples"]
    segments = pd.read_parquet(identities)
    if len(segments) != len(samples):
        raise ValueError(f"{slug}: segment identities and curve rows differ")
    # The weights are derived from the identity table, the curves were written by the
    # accumulator: a stale pairing would reweight one run's curves by another's
    # segments and still produce a plausible figure.
    stored = np.isfinite(samples)
    if not np.array_equal(
        stored, admissible_windows(lags, segments.n_fixes, segments.dt_s) > 0
    ):
        raise ValueError(f"{slug}: stored support differs from the recorded lag rule")
    return lags, samples, segments


def measure(discipline: str, loaded, macros: dict) -> pd.DataFrame:
    """Average one discipline's segment curves three ways and emit its macros."""
    from soaring.analysis.observables.transport import (
        fit_msd_exponent,
        population_tamsd,
    )

    lags, samples, segments = loaded
    curves = population_tamsd(
        samples, lags, segments.n_fixes, segments.dt_s, segments.flight_id.astype(str)
    )
    shown = (lags >= FIT_MIN_S) & (lags <= FIT_MAX_S)
    tag = DISCIPLINES[discipline].tag
    reference = curves["segment"].msd

    frames, exponents = [], {}
    for name, _, _, _ in ESTIMATORS:
        curve = curves[name]
        # min_flights is the equal-flight population's floor; the window count runs to
        # 10^9 and the segment count to 10^5, so the cut has to be the same statement
        # about the population rather than the same number on three different units.
        fit = fit_msd_exponent(
            curve, t_min_s=FIT_MIN_S, t_max_s=FIT_MAX_S, min_flights=0
        )
        macros[f"StatMsdWeight{tag}Alpha{name.capitalize()}"] = f"{fit.alpha:.3f}"
        exponents[name] = fit.alpha
        if name != "segment":
            departure = np.nanmax(np.abs(curve.msd[shown] / reference[shown] - 1.0))
            macros[f"StatMsdWeight{tag}Gap{name.capitalize()}Pct"] = (
                f"{100 * departure:.1f}"
            )
        frame = curve.to_frame()
        frame.insert(0, "estimator", name)
        frame.insert(0, "discipline", discipline)
        frames.append(frame)
        print(
            f"    {name:8s} alpha = {fit.alpha:.3f} on "
            f"[{fit.t_min:.0f}, {fit.t_max:.0f}] s ({fit.n_points} lags)"
        )

    # Evaluated here rather than typeset as a subtraction of two macros, which would
    # print the arithmetic where the sentence promises a number.
    spread = max(exponents.values()) - min(exponents.values())
    macros[f"StatMsdWeight{tag}AlphaSpread"] = f"{spread:.3f}"

    # The population the three conventions average over, not its lag-varying support:
    # every stored segment curve, and the flights they belong to.
    segment_count = len(segments)
    flight_count = segments.flight_id.astype(str).nunique()
    macros[f"StatMsdWeight{tag}Segments"] = f"{segment_count}"
    macros[f"StatMsdWeight{tag}Flights"] = f"{flight_count}"
    # The split that makes the segment and flight conventions differ at all.
    macros[f"StatMsdWeight{tag}SegmentsPerFlight"] = (
        f"{segment_count / flight_count:.2f}"
    )
    print(f"[{discipline}] {flight_count} flights, {segment_count} segments")
    return pd.concat(frames, ignore_index=True)


def draw(table: pd.DataFrame) -> None:
    """Three weightings per discipline, over the ratio that makes them legible."""
    import matplotlib.pyplot as plt
    from matplotlib.lines import Line2D

    from soaring.reporting.style import paper_style

    paper_style()
    disciplines = list(DISCIPLINES)
    fig, axes = plt.subplots(2, 2, figsize=(6.1, 4.8), layout="constrained")
    for column, discipline in enumerate(disciplines):
        block = table[table.discipline == discipline]
        reference = block[block.estimator == "segment"].sort_values("t_s")
        shown = (reference.t_s >= FIT_MIN_S) & (reference.t_s <= FIT_MAX_S)
        for name, _, color, style in ESTIMATORS:
            rows = block[block.estimator == name].sort_values("t_s")
            lags = rows.t_s.to_numpy()[shown.to_numpy()]
            msd = rows.msd_m2.to_numpy()[shown.to_numpy()]
            axes[0, column].loglog(lags, msd, style, color=color, lw=1.3)
            axes[1, column].semilogx(
                lags,
                msd / reference.msd_m2.to_numpy()[shown.to_numpy()],
                style,
                color=color,
                lw=1.3,
            )
        axes[0, column].set(
            title=f"({'ab'[column]}) {discipline.capitalize()}",
            ylabel=r"$M_2(\tau)$ [m$^2$]",
        )
        axes[1, column].axhline(1.0, color=".75", lw=0.6)
        axes[1, column].set(
            title=f"({'cd'[column]}) Ratio, {discipline}",
            ylabel=r"$M_2/M_2^{\mathrm{segment}}$",
        )
        for ax in axes[:, column]:
            ax.set(xlim=(FIT_MIN_S, FIT_MAX_S), xlabel=r"Lag $\tau$ [s]")
            ax.grid(visible=True, which="major", color=".93", lw=0.4)
    fig.legend(
        handles=[
            Line2D([], [], color=color, ls=style, label=label)
            for _, label, color, style in ESTIMATORS
        ],
        loc="outside lower center",
        ncol=3,
        frameon=False,
    )
    OUT_FIG.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT_FIG, metadata=_PDF_METADATA)
    plt.close(fig)
    print(f"Wrote {OUT_FIG.name}.")


def main() -> int:
    """Reduce both disciplines' cached curves into the three weighted averages."""
    try:
        import matplotlib
    except ImportError:
        print("matplotlib missing ('analysis' group); keeping the committed figure.")
        return 0
    matplotlib.use("Agg")

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--audit-dir", type=Path, required=True)
    parser.add_argument(
        "--allow-partial",
        action="store_true",
        help="write whichever disciplines are reachable, instead of failing",
    )
    args = parser.parse_args()

    macros: dict[str, str] = {}
    frames, missing = [], []
    for discipline, glider in DISCIPLINES.items():
        loaded = load(glider.slug, args.audit_dir)
        if loaded is None:
            print(f"{discipline}: MSD pass not found")
            missing.append(discipline)
            continue
        frames.append(measure(discipline, loaded, macros))

    if missing and not args.allow_partial:
        print(
            f"{', '.join(missing)}: pass not reachable. The chapter quotes both "
            "disciplines, so the build would fail on the macros this one owns. "
            "Re-run measure_msd.py, or pass --allow-partial."
        )
        return 1
    if not frames:
        print("no MSD pass reachable; nothing written")
        return 0

    macros["StatMsdWeightFitMinS"] = f"{FIT_MIN_S:.0f}"
    macros["StatMsdWeightFitMaxS"] = f"{FIT_MAX_S:.0f}"
    table = pd.concat(frames, ignore_index=True)
    # Curves and macros first: a failure inside the drawing then costs a figure rather
    # than the reduction behind it.
    table.to_csv(OUT_CSV, index=False)
    write_macros(
        OUT_TEX,
        macros,
        generator="scripts/esperimenti/ch03_global_observables/generate_msd_weights.py",
    )
    print(f"Wrote {OUT_CSV.name} and {OUT_TEX.name}.")
    draw(table)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
