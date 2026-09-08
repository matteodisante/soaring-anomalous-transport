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

ROOT = Path(__file__).resolve().parents[3]
_SRC = str(ROOT / "src")
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

# The sys.path line above is what makes this resolvable when the script is run
# directly, so the import cannot move to the top of the file.
from soaring.reporting import DISCIPLINES, write_macros  # noqa: E402

OUT_TEX = ROOT / "thesis" / "generated" / "shape.tex"
OUT_FIG = ROOT / "thesis" / "generated" / "shape.pdf"

MIN_SAMPLES = 500

# The window every exponent in Chapter 3 is fitted on. Quantities that are sensitive to the
# far tail are quoted over it and drawn beyond it.
TRANSPORT_RANGE_S = (60.0, 2000.0)

_PDF_METADATA = {"Creator": "soaring.analysis", "Producer": "soaring.analysis", "CreationDate": None}


def load(slug: str, audit_dir: Path):
    path = audit_dir / f"shape_{slug}.npz"
    return dict(np.load(path)) if path.is_file() else None


def matched_gaussian_null(slug: str, audit_dir: Path, data: dict, macros: dict) -> None:
    r"""What pooling reads when every flight is exactly Gaussian, for Mardia's kurtosis.

    The pooled statistic is not a statement about the shape of an increment distribution
    until it is compared with this. Writing :math:`S_f` for a flight's own second moment
    (its trace, :math:`\langle|\Delta\mathbf r|^2\rangle`) and :math:`\lambda_f\equiv
    S_f/\mathbb E_n[S_f]` for its amplitude relative to the pooled population, a population
    of flights that are each exactly bivariate Gaussian -- same shape, differing only in
    overall amplitude -- pools to a Mardia excess of

    .. math::

        8\,\mathrm{CV}^2(\lambda_f) = 8\,\mathrm{CV}^2(S_f),

    a scale-mixture identity (App.~app:ctrw's own Mittag-Leffler route is the same kind of
    argument for a different mixture) verified on synthetic anisotropic, correlated
    Gaussian data before being trusted here: measured against a predicted
    :math:`8\,\mathrm{CV}^2` this way, agreement was within Monte Carlo noise at
    :math:`n=3\times10^6` \impldetails{impl:global}. Setting :math:`\mathrm{CV}(S_f)=0`
    recovers 0, the population value for *any* single bivariate Gaussian regardless of its
    covariance -- which is what makes Mardia's kurtosis the right statistic for an
    anisotropic, correlated archive: it needs no isotropic assumption the null could be
    wrong about. So a measured value *below* this null is a population of flights whose
    individual propagators are flatter than Gaussian, and one above it is a heavy tail.

    :math:`S_f` comes from the order-1 filtered variation, the same second moment on the
    same increments, so the two are comparable lag by lag -- but only where the two passes
    put a lag in the same place, and only where the reconstruction returns the pooled second
    moment the shape pass measured. Both are checked here rather than assumed, and a lag
    that fails either is dropped.
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
    measured = mardia_kurtosis(data)
    if measured is None:
        return
    trace = np.asarray(data["east_m2"], dtype=float) + np.asarray(data["north_m2"], dtype=float)

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
        if not np.isfinite(trace[j]) or abs(pooled / trace[j] - 1.0) > 0.03:
            continue
        cv2 = float(np.sum(weight * value**2) / np.sum(weight) / pooled**2 - 1.0)
        null = 8.0 * cv2
        rows.append((lag, measured[j], null))

    if len(rows) < 2:
        return
    lag_at, measured_at, null_at = (np.array(c) for c in zip(*rows, strict=True))
    tag = DISCIPLINES[discipline_of(slug)].tag
    macros[f"StatShape{tag}NullLags"] = f"{len(rows)}"
    macros[f"StatShape{tag}NullAbove"] = f"{int((null_at > measured_at).sum())}"
    macros[f"StatShape{tag}NullAtFloor"] = f"{null_at[0]:+.2f}"
    macros[f"StatShape{tag}NullFloorS"] = f"{lag_at[0]:.0f}"
    macros[f"StatShape{tag}WithinFlight"] = f"{np.median(measured_at - null_at):+.2f}"
    macros[f"StatShape{tag}AmplitudeCv"] = f"{np.sqrt(max(null_at[0], 0.0) / 8.0):.2f}"


def discipline_of(slug: str) -> str:
    for name, glider in DISCIPLINES.items():
        if glider.slug == slug:
            return name
    raise KeyError(slug)


def mardia_kurtosis(data: dict) -> np.ndarray | None:
    r"""Mardia's multivariate kurtosis excess of the joint (east, north) increment,
    per lag: :math:`b_{2,2}=\mathbb E[Q^2]-8`, :math:`Q=\mathbf d^\top\hat\Sigma^{-1}
    \mathbf d` the squared Mahalanobis distance under the pooled sample covariance
    :math:`\hat\Sigma` \cite{mardia1970}.

    Zero for *any* bivariate Gaussian, whatever its covariance -- anisotropic, correlated,
    it does not matter -- which is the property the ratio this replaced did not have: that
    one assumed an isotropic propagator to fix its normalisation, on an archive
    Sec.~sec:prelim already measures as anisotropic. :math:`Q^2` is a quartic form in
    :math:`\mathbf d`, so its expectation is a fixed contraction of the raw fourth-moment
    tensor with :math:`\hat\Sigma^{-1}\otimes\hat\Sigma^{-1}` and needs no second pass over
    the increments: only the five raw moments ``measure_shape.py`` already keeps
    (``east_m2/m4``, ``north_m2/m4``, ``cross_x2y2``) plus the two odd cross moments
    (``cross_xy``, ``cross_x3y``, ``cross_xy3``). Not centred on a per-flight mean -- see
    ``measure_shape.py`` for why that is a good approximation pooled across the whole
    archive. Verified against a closed-form scale-mixture null in
    :func:`matched_gaussian_null` and against synthetic anisotropic, correlated Gaussian
    data \impldetails{impl:global}.
    """
    needed = ("east_m2", "east_m4", "north_m2", "north_m4", "cross_xy", "cross_x3y",
              "cross_x2y2", "cross_xy3")
    if not all(key in data for key in needed):
        return None
    a = np.asarray(data["east_m2"], dtype=float)
    b = np.asarray(data["north_m2"], dtype=float)
    c = np.asarray(data["cross_xy"], dtype=float)
    m40 = np.asarray(data["east_m4"], dtype=float)
    m04 = np.asarray(data["north_m4"], dtype=float)
    m31 = np.asarray(data["cross_x3y"], dtype=float)
    m22 = np.asarray(data["cross_x2y2"], dtype=float)
    m13 = np.asarray(data["cross_xy3"], dtype=float)
    det = a * b - c**2
    with np.errstate(invalid="ignore", divide="ignore"):
        e_q2 = (
            b**2 * m40 - 4 * b * c * m31 + (2 * a * b + 4 * c**2) * m22
            - 4 * a * c * m13 + a**2 * m04
        ) / det**2
    return e_q2 - 8.0


def component_kurtosis(data: dict) -> tuple[np.ndarray, np.ndarray] | tuple[None, None]:
    """Classical (univariate) excess kurtosis of the east-only and north-only increment,
    per lag: :math:`\\langle\\delta x^4\\rangle/\\langle\\delta x^2\\rangle^2-3`, zero for
    a Gaussian, on the same raw, uncentred moments :func:`mardia_kurtosis` uses.
    """
    if not all(key in data for key in ("east_m2", "east_m4", "north_m2", "north_m4")):
        return None, None
    a = np.asarray(data["east_m2"], dtype=float)
    b = np.asarray(data["north_m2"], dtype=float)
    m40 = np.asarray(data["east_m4"], dtype=float)
    m04 = np.asarray(data["north_m4"], dtype=float)
    with np.errstate(invalid="ignore", divide="ignore"):
        kurt_east = m40 / a**2 - 3.0
        kurt_north = m04 / b**2 - 3.0
    return kurt_east, kurt_north


def measure(discipline: str, data: dict, macros: dict) -> dict:
    from soaring.analysis.observables.moments import bilinear_fit
    from soaring.analysis.observables.persistence import vacf_tail_exponent

    tag = DISCIPLINES[discipline].tag
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

    # The non-Gaussian parameter: Mardia's multivariate kurtosis excess of the joint
    # (east, north) increment (mardia_kurtosis, eq:nongauss), zero for any bivariate
    # Gaussian regardless of its covariance -- the property that matters on an archive
    # Sec. prelim already measures as anisotropic. Read on the increment rather than on
    # the position, which is the frame the rest of the chapter trusts; on the position it
    # would measure the launch geometry again.
    #
    # It is quoted over TRANSPORT_RANGE_S and not over the whole grid. Above it the curve
    # climbs steeply, but that is where the declared task takes the trajectory over and
    # where a fourth moment is carried by the fewest flights, so a maximum read there would
    # be a statement about the scoring rule. The range is the one every exponent in the
    # chapter is fitted on, and the full curve is drawn so the climb is visible.
    non_gaussian = mardia_kurtosis(data)
    if non_gaussian is not None:
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
            put("NonGaussMin", f"{np.nanmin(values):+.2f}")
            put("NonGaussMax", f"{np.nanmax(values):+.2f}")
            put("NonGaussMedian", f"{np.nanmedian(values):+.2f}")
            # The curve has an interior maximum, so where it is and how far it stands above
            # the ends is the measurement. The end-to-end difference this used to report is
            # the CHORD OF AN ARCH -- the error this project diagnoses in the ensemble MSD
            # and then committed here: it read +0.02 on a curve that rises sevenfold and
            # falls back.
            put("NonGaussPeak", f"{values[peak]:+.2f}")
            put("NonGaussPeakS", f"{at[peak]:.0f}")
            put("NonGaussAtFloor", f"{values[0]:+.2f}")
            put("NonGaussAtCeiling", f"{values[-1]:+.2f}")
            put("NonGaussPeakRatio", f"{values[peak] / max(values[0], 1e-9):.1f}")
            put("NonGaussInterior", "yes" if 0 < peak < len(values) - 1 else "no")
        beyond = usable & np.isfinite(non_gaussian) & (lags > TRANSPORT_RANGE_S[1])
        if beyond.any():
            put("NonGaussBeyond", f"{np.nanmax(non_gaussian[beyond]):+.2f}")

    # The per-component (1D) excess kurtosis, the classical statistic rather than Mardia's
    # multivariate one -- appropriate here precisely because a single component is a
    # scalar, and reported the same way sec:transport-axisroutes reports every other
    # estimator per component, since pooling presupposes an isotropy this archive lacks.
    kurt_east, kurt_north = component_kurtosis(data)
    if kurt_east is not None:
        quoted = usable & (lags >= TRANSPORT_RANGE_S[0]) & (lags <= TRANSPORT_RANGE_S[1])
        for name, values in (("KurtEast", kurt_east), ("KurtNorth", kurt_north)):
            v = values[quoted & np.isfinite(values)]
            if v.size:
                put(f"{name}Median", f"{np.median(v):+.2f}")
                put(f"{name}Max", f"{np.max(v):+.2f}")


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


def gaussian_tail_reference(q_grid: np.ndarray, n: int = 4_000_000, seed: int = 0) -> np.ndarray:
    """What panel (b)'s tail-share statistic reads on an isotropic 2D Gaussian.

    The archive's own share is computed the same way in ``measure_shape.py``: the largest
    one per cent of a lag's increments, by count, and what fraction of :math:`\\sum r^q`
    they carry. Simulated here directly rather than assumed, on i.i.d. bivariate Gaussian
    noise -- the modulus is then Rayleigh, and the statistic is scale-free, so one large
    sample stands for every lag rather than one per lag.
    """
    rng = np.random.default_rng(seed)
    r = np.hypot(rng.standard_normal(n), rng.standard_normal(n))
    keep = max(1, int(round(0.01 * n)))
    out = np.empty(len(q_grid))
    for j, q in enumerate(q_grid):
        w = r.astype(float) ** q
        out[j] = np.sort(w)[-keep:].sum() / w.sum()
    return out


def draw(measured: dict):
    import matplotlib.pyplot as plt

    fig, axes = plt.subplots(2, 2, figsize=(9.5, 7.4))
    (spec_ax, tail_ax), (gauss_ax, vacf_ax) = axes

    for discipline, m in measured.items():
        colour = DISCIPLINES[discipline].color
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

    reference = gaussian_tail_reference(next(iter(measured.values()))["q_grid"]) if measured else None
    if reference is not None:
        tail_ax.plot(next(iter(measured.values()))["q_grid"], reference, "--", color="0.4",
                     lw=1.1, label="isotropic Gaussian")

    spec_ax.set_xlabel("$q$")
    spec_ax.set_ylabel(r"$q\,\nu(q)$")
    spec_ax.set_title("(a) moment spectrum: straight means monofractal", fontsize=10, loc="left")
    tail_ax.axhline(0.2, color="0.4", lw=0.8, ls="--")
    tail_ax.set_xlabel("$q$")
    tail_ax.set_ylabel("share of the moment in its largest 1\\%".replace("\\", ""))
    tail_ax.set_title("(b) tail control, against an isotropic Gaussian", fontsize=10, loc="left")
    vacf_ax.set_xlabel(r"$\tau$ (s)")
    vacf_ax.set_ylabel(r"$C(\tau)$")
    vacf_ax.set_title("(d) velocity autocorrelation, and its tail", fontsize=10, loc="left")
    # Zero is the Gaussian value for Mardia's kurtosis, whatever the covariance -- unlike
    # the ratio this replaced, it needs no isotropic assumption. No Levy-walk reference
    # line: on a synthetic Levy walk at this archive's own protocol the statistic is
    # negative at short lag and swings by an order of magnitude between seeds at long lag
    # (heavy-tailed, so a finite sample does not settle it), so it has no single value to
    # mark -- the moment spectrum in (a) is where that question is actually decided.
    gauss_ax.axhline(0.0, color="0.4", lw=0.8, ls="--")
    gauss_ax.axvspan(*TRANSPORT_RANGE_S, color="0.85", alpha=0.5, zorder=0)
    gauss_ax.text(0.02, 0.96, "Gaussian $=0$;\nshaded: the window every exponent\nin this chapter is fitted on",
                  fontsize=7, transform=gauss_ax.transAxes, va="top")
    gauss_ax.set_xlabel(r"$\Delta$ (s)")
    # Superscripted to keep it apart from the filtered-variation exponent, which the
    # chapter also calls alpha_2 and which is a different quantity.
    gauss_ax.set_ylabel(r"$\alpha_2^{\mathrm{NG}}(\Delta)$")
    gauss_ax.set_title("(c) non-Gaussian parameter (Mardia's kurtosis excess)", fontsize=10,
                       loc="left")
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
    for discipline, glider in DISCIPLINES.items():
        slug = glider.slug
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
    write_macros(
        OUT_TEX, macros, generator="scripts/reporting/ch3_global_transport/generate_shape_figure.py"
    )
    print(f"wrote {OUT_TEX.name}, {OUT_FIG.name} ({len(macros)} macros)")
    for k, v in macros.items():
        print(f"  {k:36s} {v}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
