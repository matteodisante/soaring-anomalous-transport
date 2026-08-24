#!/usr/bin/env python3
r"""Reduce the shape pass into Chapter 3's second measurement, its figure and its macros.

The exponent of ``generate_transport_figure.py`` is one moment of one distribution. This
asks the questions that one moment cannot answer.

**Is it a Lévy walk?** The spectrum :math:`\langle|\Delta\mathbf{r}|^q\rangle\sim
\Delta^{q\nu(q)}` is bilinear with a knee for a Lévy walk and straight through the origin
for a monofractal process. The discrimination is visual and does not rest on a delicate
fit, which is why it is worth a full pass over the archive.

**Is the propagator Gaussian?** The second and fourth moments already carry the answer:
:math:`\alpha_2=\langle|\Delta\mathbf{r}|^4\rangle/2\langle|\Delta\mathbf{r}|^2\rangle^2-1`
vanishes for a Gaussian and is positive for heavier tails. It costs nothing beyond the
spectrum and it separates two things the spectrum alone conflates --- one exponent for
every moment is a statement about *scaling*, not about *shape*.

**Does the memory account for the displacement?** The velocity autocorrelation and the
displacement are two readings of one thing, joined by Green--Kubo. The two channels are
built by different routes --- positions smoothed, velocities differentiated from them --- so
comparing them catches a class of error in either. The comparison is made through the
scaling form and is one-sided; the reason is in
``soaring.analysis.observables.persistence``.

Writes ``thesis/generated/shape.tex`` and ``shape.pdf``.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
_SRC = str(ROOT / "src")
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

OUT_TEX = ROOT / "thesis" / "generated" / "shape.tex"
OUT_FIG = ROOT / "thesis" / "generated" / "shape.pdf"

DISCIPLINES = {"paragliders": ("para", "Para"), "hang gliders": ("hang", "Hang")}
COLORS = {"paragliders": "#3477a8", "hang gliders": "#b5482a"}
MIN_SAMPLES = 500

# The window every exponent in Chapter 3 is fitted on. Quantities that are sensitive to the
# far tail are quoted over it and drawn beyond it.
TRANSPORT_RANGE_S = (60.0, 2000.0)

_PDF_METADATA = {"Creator": "soaring.analysis", "Producer": "soaring.analysis", "CreationDate": None}


def load(slug: str, audit_dir: Path):
    path = audit_dir / f"shape_{slug}.npz"
    return dict(np.load(path)) if path.is_file() else None


def matched_gaussian_null(slug: str, audit_dir: Path, data: dict, macros: dict) -> None:
    """What a pooled non-Gaussian parameter reads when every flight is exactly Gaussian.

    The pooled parameter is not a statement about the shape of an increment distribution
    until it is compared with this. Writing ``S_f`` for a flight's own second moment and
    ``a_f`` for its own non-Gaussian parameter, the pooled value obeys

        1 + alpha_pooled = E_n[(1 + a_f) S_f^2] / E_n[S_f]^2,

    an identity rather than an approximation, with the expectations weighted by the number of
    windows each flight supplies. Setting every ``a_f`` to zero leaves ``CV^2(S_f)``: the
    excess a population of Gaussian flights of differing amplitude produces on its own. So a
    measured value *below* this null is a population of flights whose individual propagators
    are flatter than Gaussian, and one above it is a heavy tail.

    ``S_f`` comes from the order-1 filtered variation, which is the same second moment on the
    same increments, so the two are comparable lag by lag -- but only where the two passes put
    a lag in the same place, and only where the reconstruction returns the pooled second
    moment the shape pass measured. Both are checked here rather than assumed, and a lag that
    fails either is dropped: the alternative is a comparison between two different quantities
    that looks like a result.

    The null is built isotropic. The archive is mildly anisotropic, and anisotropy raises the
    Gaussian value (19/18 at a two-to-one ratio of component variances), so an isotropic null
    is the conservative one when the finding is that the null already exceeds the measurement.
    """
    import pandas as pd

    curves_path = audit_dir / f"variations_{slug}.npz"
    flights_path = audit_dir / f"variation_flights_{slug}.parquet"
    if not (curves_path.is_file() and flights_path.is_file()):
        return
    curves = np.load(curves_path)
    frame = pd.read_parquet(flights_path, columns=["duration_s"])
    duration = frame["duration_s"].to_numpy(dtype=float)
    var_lags, first_order = curves["lags_s"], curves["order1"]
    if first_order.shape[0] != duration.size:
        return

    lags = np.asarray(data["lags_s"], dtype=float)
    moment = np.asarray(data["moment"], dtype=float)
    q_grid = np.asarray(data["q_grid"], dtype=float)
    two = int(np.argmin(np.abs(q_grid - 2.0)))
    four = int(np.argmin(np.abs(q_grid - 4.0)))
    measured = moment[:, four] / (2.0 * moment[:, two] ** 2) - 1.0

    rows = []
    for j, lag in enumerate(lags):
        if not (TRANSPORT_RANGE_S[0] <= lag <= TRANSPORT_RANGE_S[1]):
            continue
        i = int(np.argmin(np.abs(var_lags - lag)))
        if abs(var_lags[i] - lag) > 0.02 * lag:
            continue
        second = first_order[:, i]
        windows = np.floor(duration / var_lags[i])
        good = np.isfinite(second) & (second > 0) & (windows > 0)
        if good.sum() < 100:
            continue
        weight, value = windows[good], second[good]
        pooled = float(np.sum(weight * value) / np.sum(weight))
        if not np.isfinite(moment[j, two]) or abs(pooled / moment[j, two] - 1.0) > 0.03:
            continue
        null = float(np.sum(weight * value**2) / np.sum(weight) / pooled**2 - 1.0)
        rows.append((lag, measured[j], null))

    if len(rows) < 2:
        return
    lag_at, measured_at, null_at = (np.array(c) for c in zip(*rows))
    tag = DISCIPLINES[discipline_of(slug)][1]
    macros[f"StatShape{tag}NullLags"] = f"{len(rows)}"
    macros[f"StatShape{tag}NullAbove"] = f"{int((null_at > measured_at).sum())}"
    macros[f"StatShape{tag}NullAtFloor"] = f"{null_at[0]:+.3f}"
    macros[f"StatShape{tag}NullFloorS"] = f"{lag_at[0]:.0f}"
    macros[f"StatShape{tag}WithinFlight"] = f"{np.median(measured_at - null_at):+.3f}"
    macros[f"StatShape{tag}AmplitudeCv"] = f"{np.sqrt(max(null_at[0], 0.0)):.2f}"


def discipline_of(slug: str) -> str:
    for name, (candidate, _) in DISCIPLINES.items():
        if candidate == slug:
            return name
    raise KeyError(slug)


def measure(discipline: str, data: dict, macros: dict) -> dict:
    from soaring.analysis.observables.moments import bilinear_fit
    from soaring.analysis.observables.persistence import vacf_tail_exponent

    tag = DISCIPLINES[discipline][1]
    lags, q_grid = data["lags_s"], data["q_grid"]
    moment, counts, tail = data["moment"], data["moment_count"], data["tail_share"]

    def put(name, value):
        macros[f"StatShape{tag}{name}"] = value

    usable = (counts > MIN_SAMPLES) & np.isfinite(moment[:, 0])
    put("Lags", f"{int(usable.sum())}")
    put("FitMinS", f"{lags[usable][0]:.0f}")
    put("FitMaxS", f"{lags[usable][-1]:.0f}")
    put("QMin", f"{q_grid[0]:.2f}")
    put("QMax", f"{q_grid[-1]:.0f}")

    q_nu = np.array(
        [np.polyfit(np.log(lags[usable]), np.log(moment[usable, j]), 1)[0]
         for j in range(q_grid.size)]
    )
    fitted = bilinear_fit(q_grid, q_nu)
    put("NuMin", f"{np.nanmin(q_nu / q_grid):.3f}")
    put("NuMax", f"{np.nanmax(q_nu / q_grid):.3f}")
    put("NuSpread", f"{np.nanmax(q_nu / q_grid) - np.nanmin(q_nu / q_grid):.3f}")
    put("LinearSlope", f"{fitted['linear_slope']:.3f}")
    put("LinearDeparture", f"{fitted['linear_departure']:.4f}")
    put("Bilinear", "yes" if fitted["prefers_bilinear"] else "no")
    if fitted["prefers_bilinear"]:
        put("Knee", f"{fitted['knee']:.2f}")
        put("SlopeHigh", f"{fitted['slope_high']:.2f}")
    # The tail control: a moment carried by its largest one per cent is not a moment.
    put("TailMaxPct", f"{100 * np.nanmax(tail[usable]):.0f}")
    put("TailAtQMaxPct", f"{100 * np.nanmedian(tail[usable, -1]):.0f}")

    # The non-Gaussian parameter, which the second and fourth moments already carry:
    # alpha_2 = <|dr|^4> / (2 <|dr|^2>^2) - 1, zero for a two-dimensional Gaussian. Read on
    # the increment rather than on the position, which is the frame the rest of the chapter
    # trusts; on the position it would measure the launch geometry again.
    #
    # It is quoted over TRANSPORT_RANGE_S and not over the whole grid. Above it the curve
    # climbs steeply, but that is where the declared task takes the trajectory over and
    # where a fourth moment is carried by the fewest flights, so a maximum read there would
    # be a statement about the scoring rule. The range is the one every exponent in the
    # chapter is fitted on, and the full curve is drawn so the climb is visible.
    non_gaussian = None
    two = int(np.argmin(np.abs(q_grid - 2.0)))
    four = int(np.argmin(np.abs(q_grid - 4.0)))
    if abs(q_grid[two] - 2.0) < 1e-9 and abs(q_grid[four] - 4.0) < 1e-9:
        non_gaussian = moment[:, four] / (2.0 * moment[:, two] ** 2) - 1.0
        quoted = (
            usable
            & np.isfinite(non_gaussian)
            & (lags >= TRANSPORT_RANGE_S[0])
            & (lags <= TRANSPORT_RANGE_S[1])
        )
        if quoted.any():
            values, at = non_gaussian[quoted], lags[quoted]
            peak = int(np.nanargmax(values))
            put("NonGaussMinS", f"{at[0]:.0f}")
            put("NonGaussMaxS", f"{at[-1]:.0f}")
            put("NonGaussMin", f"{np.nanmin(values):+.3f}")
            put("NonGaussMax", f"{np.nanmax(values):+.3f}")
            put("NonGaussMedian", f"{np.nanmedian(values):+.3f}")
            # The curve has an interior maximum, so where it is and how far it stands above
            # the ends is the measurement. The end-to-end difference this used to report is
            # the CHORD OF AN ARCH -- the error this project diagnoses in the ensemble MSD
            # and then committed here: it read +0.02 on a curve that rises sevenfold and
            # falls back.
            put("NonGaussPeak", f"{values[peak]:+.3f}")
            put("NonGaussPeakS", f"{at[peak]:.0f}")
            put("NonGaussAtFloor", f"{values[0]:+.3f}")
            put("NonGaussAtCeiling", f"{values[-1]:+.3f}")
            put("NonGaussPeakRatio", f"{values[peak] / max(values[0], 1e-9):.1f}")
            put("NonGaussInterior", "yes" if 0 < peak < len(values) - 1 else "no")
        beyond = usable & np.isfinite(non_gaussian) & (lags > TRANSPORT_RANGE_S[1])
        if beyond.any():
            put("NonGaussBeyond", f"{np.nanmax(non_gaussian[beyond]):+.2f}")


    # The velocity memory.
    vacf = data.get("vacf", np.zeros(0))
    good = np.isfinite(vacf) & (vacf != 0)
    if good.any():
        put("VacfFlights", f"{int(data['vacf_flights'][0])}")
        put("VacfAtFloor", f"{vacf[good][0]:+.2f}")
        below = np.flatnonzero(good & (vacf < np.exp(-1.0)))
        put("VacfDecayS", f"{lags[below[0]]:.0f}" if below.size else "beyond the range")
        negative = np.flatnonzero(good & (vacf < 0))
        put("VacfSignChangeS", f"{lags[negative[0]]:.0f}" if negative.size else "never")

        # The tail of the memory against the exponent of the motion: two readings of one
        # thing, joined by Green-Kubo in its scaling form. One-sided, so it is reported as
        # the bound it is rather than as an agreement.
        positive = good & (vacf > 0)
        gamma, implied, n_lags = vacf_tail_exponent(lags[positive], vacf[positive])
        if n_lags:
            put("VacfTailGamma", f"{gamma:.2f}")
            put("VacfTailLags", f"{n_lags}")
            put("VacfTailMinS", f"{lags[positive][0]:.0f}")
            put("VacfTailMaxS", f"{lags[positive][-1]:.0f}")
            put("VacfImpliedAlphaFloor", f"{implied:.2f}")
            # Whether one exponent is the right description of those lags is a separate
            # question from what its value is, and a straight line through a bend is the
            # error this chapter diagnoses elsewhere. The local slope answers it on the
            # same lags the fit used. What Green-Kubo needs is not the fitted value but
            # that every local slope is below one, which is the stronger statement.
            from soaring.analysis.observables.regimes import local_slope

            gamma_local = -local_slope(lags[positive], vacf[positive], 0.25)
            finite = np.isfinite(gamma_local)
            if finite.sum() > 3:
                values = gamma_local[finite]
                put("VacfGammaLocalMin", f"{np.nanmin(values):.2f}")
                put("VacfGammaLocalMax", f"{np.nanmax(values):.2f}")
                put("VacfGammaLocalRatio", f"{np.nanmax(values) / max(np.nanmin(values), 1e-9):.1f}")
                put("VacfGammaBelowOne", "yes" if np.nanmax(values) < 1.0 else "no")
                coefficients = np.polyfit(
                    np.log(lags[positive]), np.log(vacf[positive]), 1
                )
                residual = np.log10(vacf[positive]) - np.polyval(
                    coefficients, np.log(lags[positive])
                ) / np.log(10)
                put("VacfGammaResidualDex", f"{np.ptp(residual):.3f}")
            put("VacfIntegrable", "yes" if gamma > 1.0 else "no")

    return {"lags": lags, "q_grid": q_grid, "q_nu": q_nu, "usable": usable,
            "moment": moment, "tail": tail, "vacf": vacf, "fit": fitted, "data": data,
            "gamma": float(macros.get(f"StatShape{tag}VacfTailGamma", "nan")),
            "non_gaussian": non_gaussian}


def draw(measured: dict):
    import matplotlib.pyplot as plt

    fig, axes = plt.subplots(2, 2, figsize=(9.5, 7.4))
    (spec_ax, tail_ax), (gauss_ax, vacf_ax) = axes

    for discipline, m in measured.items():
        colour = COLORS[discipline]
        q, q_nu = m["q_grid"], m["q_nu"]
        spec_ax.plot(q, q_nu, "o-", color=colour, ms=4, label=discipline)
        spec_ax.plot(q, m["fit"]["linear_slope"] * q, "--", color=colour, lw=0.9,
                     label=f"{discipline}, $q\\nu={m['fit']['linear_slope']:.2f}q$")
        tail_ax.plot(q, np.nanmedian(m["tail"][m["usable"]], axis=0), "o-", color=colour, ms=4,
                     label=discipline)
        # Log-log, not semilog: the statement about C is that its tail is a power law, and
        # a semilog axis hides exactly that.
        good = np.isfinite(m["vacf"]) & (m["vacf"] > 0)
        if good.any():
            vacf_ax.loglog(m["lags"][good], m["vacf"][good], color=colour, label=discipline)
            if np.isfinite(m["gamma"]):
                tau = m["lags"][good]
                reference = m["vacf"][good][0] * (tau / tau[0]) ** -m["gamma"]
                vacf_ax.loglog(tau, reference, "--", color=colour, lw=0.9,
                               label=f"{discipline}, $\\tau^{{-{m['gamma']:.2f}}}$")
        if m["non_gaussian"] is not None:
            keep = m["usable"] & np.isfinite(m["non_gaussian"])
            gauss_ax.semilogx(m["lags"][keep], m["non_gaussian"][keep], "o-", color=colour,
                              ms=3, label=discipline)

    spec_ax.set_xlabel("$q$")
    spec_ax.set_ylabel(r"$q\,\nu(q)$")
    spec_ax.set_title("(a) moment spectrum: straight means monofractal", fontsize=10, loc="left")
    tail_ax.axhline(0.2, color="0.4", lw=0.8, ls="--")
    tail_ax.set_xlabel("$q$")
    tail_ax.set_ylabel("share of the moment in its largest 1\\%".replace("\\", ""))
    tail_ax.set_title("(b) tail control", fontsize=10, loc="left")
    vacf_ax.set_xlabel(r"$\tau$ (s)")
    vacf_ax.set_ylabel(r"$C(\tau)$")
    vacf_ax.set_title("(d) velocity autocorrelation, and its tail", fontsize=10, loc="left")
    # The Gaussian value is zero, and the two calibrations bracket what the archive shows.
    gauss_ax.axhline(0.0, color="0.4", lw=0.8, ls="--")
    gauss_ax.axhline(0.56, color="0.6", lw=0.8, ls=":")
    gauss_ax.axvspan(*TRANSPORT_RANGE_S, color="0.85", alpha=0.5, zorder=0)
    gauss_ax.text(0.02, 0.96, "Gaussian $=0$, Levy walk $\\simeq 0.56$;\nshaded: the quoted range",
                  fontsize=7, transform=gauss_ax.transAxes, va="top")
    gauss_ax.set_xlabel(r"$\Delta$ (s)")
    # Superscripted to keep it apart from the filtered-variation exponent, which the
    # chapter also calls alpha_2 and which is a different quantity.
    gauss_ax.set_ylabel(r"$\alpha_2^{\mathrm{NG}}(\Delta)$")
    gauss_ax.set_title("(c) non-Gaussian parameter", fontsize=10, loc="left")
    for ax in axes.ravel():
        ax.legend(frameon=False, fontsize=7)
    fig.tight_layout()
    return fig


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--audit-dir", type=Path, required=True)
    # Writing a file for one discipline when the thesis quotes both is the worst available
    # failure: the build dies hundreds of lines later on an undefined control sequence, and
    # the error names the sentence rather than the missing pass. So a missing discipline is
    # fatal by default, and the escape hatch has to be asked for.
    parser.add_argument(
        "--allow-partial",
        action="store_true",
        help="write the macros for whichever disciplines are reachable, instead of failing",
    )
    args = parser.parse_args()

    import matplotlib

    matplotlib.use("Agg")

    macros: dict[str, str] = {}
    missing: list[str] = []
    measured: dict[str, dict] = {}
    for discipline, (slug, _) in DISCIPLINES.items():
        data = load(slug, args.audit_dir)
        if data is None:
            print(f"{discipline}: shape pass not found")
            missing.append(discipline)
            continue
        measured[discipline] = measure(discipline, data, macros)
        matched_gaussian_null(slug, args.audit_dir, data, macros)
    if missing and not args.allow_partial:
        print(
            f"{', '.join(missing)}: pass not reachable. shape.tex would be written for the "
            "other discipline alone and the thesis would fail to build on the macros this "
            "one owns. Re-run the pass, or pass --allow-partial if that is what you want."
        )
        return 1
    if not macros:
        print("no shape pass reachable; shape.tex not written")
        return 1

    draw(measured).savefig(OUT_FIG, metadata=_PDF_METADATA)
    lines = ["% Generated by scripts/reporting/generate_shape_figure.py -- do not edit."]
    lines += [f"\\newcommand{{\\{k}}}{{{v}}}" for k, v in macros.items()]
    OUT_TEX.write_text("\n".join(lines) + "\n")
    print(f"wrote {OUT_TEX.name}, {OUT_FIG.name} ({len(macros)} macros)")
    for k, v in macros.items():
        print(f"  {k:36s} {v}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
