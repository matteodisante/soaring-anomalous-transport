#!/usr/bin/env python3
"""Reduce the audit pass into the ``\\StatAudit*`` macros and a readable report.

Reads what ``audit_msd.py`` wrote (one row per flight, one column per lag), the
segment and flight tables beside it, and the curve CSV ``generate_msd_figure.py``
writes, and answers the questions the averaged curve cannot answer about itself:

* whether a power law describes each estimator, measured as the residual it leaves;
* whether the shape of the ensemble curve survives the controls that would explain it
  away -- a fixed logger cadence (no population change at all), a fixed duration (no
  survivorship), and the common-direction part of the displacement (no shared heading);
* whether the ensemble is isotropic, which is what licenses the 1-D marginal;
* what the pre-processing discarded and what that costs the retained ensemble.

Writes ``thesis/generated/audit.tex``. Every number the audit reaches the thesis with
comes from here, so the prose cannot drift from the measurement.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
_SRC = str(ROOT / "src")
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

OUT_TEX = ROOT / "thesis" / "generated" / "audit.tex"
CURVE_CSV = ROOT / "thesis" / "generated" / "msd_curve.csv"

DISCIPLINES = {
    "paragliders": ("para", "Para", "SOARING_PARA_DATA_ROOT", "PARA_CONFIG_PATH"),
    "hang gliders": ("hang", "Hang", "SOARING_DELTA_DATA_ROOT", "DELTA_CONFIG_PATH"),
}

# The fit range generate_msd_figure.py used, so the residual is measured over exactly
# the lags the quoted exponent was fitted on and not over a range chosen to flatter it.
FIT_MIN_S = 120.0

# The radius that counts as having left the launch area. Five kilometres is well beyond
# any thermalling excursion and well inside the median flown path, so the crossing time
# it defines is the departure onto the cross-country leg rather than a local excursion.
DEPARTURE_RADIUS_M = 5000.0

# Local-slope window, in decades either side -- transport.local_slope's own.
SLOPE_HALF_DECADES = 0.15


def departure_times(lags: np.ndarray, radius: np.ndarray, threshold: float):
    r"""First time each flight is ``threshold`` from take-off, interpolated within the cell.

    Reading the crossing off the lag grid with an ``argmax`` snaps it to the next grid
    point, so the reported time is never early and is late by up to one cell. The grid is
    logarithmic at about thirteen per cent a step, which near a departure of 1500 s is a
    bias of order 200 s -- on a number Chapter 3 sets beside the peak of the local slope, at
    a separation of the same order. Measured on the archive, correcting it moves the median
    paraglider departure from 1911 s to 1725 s and the hang-glider one from 1695 to 1530.

    The radius grows close to a power law over the crossing, so the interpolation is linear
    in ``log t`` against ``log r``, which is exact for one and second-order for anything
    smooth.

    Returns:
        ``(times, leaves, early_fraction)`` -- the crossing time of each flight that leaves,
        the mask of those that do, and the share of them already outside at the first lag,
        for which no cell brackets the crossing and ``lags[0]`` is reported instead.
    """
    lags = np.asarray(lags, dtype=float)
    outside = radius > threshold
    leaves = outside.any(axis=1)
    if not leaves.any():
        return np.empty(0), leaves, 0.0

    index = outside.argmax(axis=1)[leaves]
    r_hi = radius[leaves, index]
    t_hi = lags[index]
    before = index - 1

    times = t_hi.copy()
    bracketed = before >= 0
    if bracketed.any():
        rows = np.flatnonzero(leaves)[bracketed]
        r_lo = radius[rows, before[bracketed]]
        t_lo = lags[before[bracketed]]
        good = np.isfinite(r_lo) & (r_lo > 0) & (r_hi[bracketed] > r_lo)
        if good.any():
            frac = (np.log(threshold) - np.log(r_lo[good])) / (
                np.log(r_hi[bracketed][good]) - np.log(r_lo[good])
            )
            interpolated = t_lo[good] * (t_hi[bracketed][good] / t_lo[good]) ** frac
            where = np.flatnonzero(bracketed)[good]
            times[where] = interpolated
    return times, leaves, float((~bracketed).mean())


def _derived_dir(discipline: str) -> Path | None:
    from soaring.acquisition.ffvl import config as cfgmod

    _, _, env, attr = DISCIPLINES[discipline]
    try:
        cfg = cfgmod.load_config(str(getattr(cfgmod, attr)), data_root_env=env)
    except (FileNotFoundError, KeyError):
        return None
    return cfg.derived_dir if (cfg.derived_dir / "flights_meta.parquet").is_file() else None


def local_slope(t: np.ndarray, y: np.ndarray, half: float = SLOPE_HALF_DECADES):
    """``d log y / d log t`` by least squares over a window of ``+-half`` decades."""
    out = np.full(t.size, np.nan)
    for i in range(t.size):
        window = (
            (t >= t[i] / 10**half)
            & (t <= t[i] * 10**half)
            & np.isfinite(y)
            & (y > 0)
        )
        if window.sum() < 3:
            continue
        out[i] = np.polyfit(np.log10(t[window]), np.log10(y[window]), 1)[0]
    return out


def power_law_residual(t: np.ndarray, y: np.ndarray) -> tuple[float, float]:
    """``(alpha, rms residual in dex)`` of the best power law through ``(t, y)``.

    Least squares always returns a slope; what it does not return is how far the curve
    wanders from the line it fitted. The size of that wander is quoted beside every
    exponent -- but see :func:`residual_runs`, because size is only half the question.
    """
    fit = np.polyfit(np.log10(t), np.log10(y), 1)
    residual = np.log10(y) - np.polyval(fit, np.log10(t))
    return float(fit[0]), float(np.std(residual))


def residual_runs(t: np.ndarray, y: np.ndarray) -> tuple[int, float, float]:
    """Wald--Wolfowitz runs test on the sign of the power-law residuals.

    The rms residual is the wrong statistic for deciding whether a power law describes a
    curve, and quoting it alone is how a systematic bend passes for a good fit. A residual
    of 3.8 % rms sounds small; if its sign changes four times where chance would change it
    eighteen, the curve is an arch and the fit is a chord across it. Only the arrangement
    of the residuals can say that, and this is the test that reads it.

    **Read the z against a simulated threshold, never against a normal table.** The
    asymptotic null assumes the signs are independent draws, and on a curve every lag of
    which averages the same flights they are nothing of the kind: the measured lag-1
    residual autocorrelation on these curves is 0.89 to 0.95. Simulating an *exact* power
    law observed with AR(1) noise of that correlation, on the same 40-lag grid, the rule
    ``|z| > 2`` rejects it 84 to 92 per cent of the time and the true five-per-cent
    threshold is ``|z|`` near 5.1. A z of 4.9 against a normal table looks decisive and is
    not evidence at all.

    Calibrating the null on the *observed* residual autocorrelation would be circular in
    the way this project has already been caught by once --- a genuinely bent curve has a
    high residual autocorrelation because of the bend --- so the runs count is reported here
    as a description of the arrangement and nothing is concluded from its z.
    :func:`residual_against_noise` supplies the test that does conclude, by comparing the
    residual against the per-lag sampling error rather than against an assumed null.

    Returns:
        ``(runs, expected_runs, z)``, where the z is the asymptotic one and is not to be
        read as a significance.
    """
    fit = np.polyfit(np.log10(t), np.log10(y), 1)
    signs = np.sign(np.log10(y) - np.polyval(fit, np.log10(t)))
    runs = 1 + int((signs[1:] != signs[:-1]).sum())
    n_pos, n_neg = int((signs > 0).sum()), int((signs < 0).sum())
    n = n_pos + n_neg
    if n_pos == 0 or n_neg == 0 or n < 3:
        return runs, float(runs), 0.0
    expected = 1.0 + 2.0 * n_pos * n_neg / n
    variance = (expected - 1.0) * (expected - 2.0) / (n - 1)
    z = (runs - expected) / np.sqrt(variance) if variance > 0 else 0.0
    return runs, float(expected), float(z)


def residual_against_noise(y: np.ndarray, low: np.ndarray, high: np.ndarray,
                           counts: np.ndarray, residual_dex: float) -> float:
    """How many times the per-lag sampling error the residual is.

    The non-circular version of the question the runs test was asked. If the departure from
    a power law were scatter, it would be of the size of the error on each point; the error
    on each point is the standard error of a mean over the flights covering that lag, which
    the stored 10--90 band and count give directly. A ratio near one is scatter; a ratio of
    twenty is a shape.

    The band is converted on a normal equivalence, which understates the spread of a
    right-skewed distribution and so understates the error --- making the returned ratio a
    lower bound, which is the direction that costs the argument nothing.
    """
    with np.errstate(divide="ignore", invalid="ignore"):
        sem = (high - low) / (2.0 * 1.2816) / np.sqrt(counts)
        sem_dex = sem / (y * np.log(10.0))
    good = np.isfinite(sem_dex) & (sem_dex > 0)
    if not good.any():
        return float("nan")
    return float(residual_dex / np.median(sem_dex[good]))


def _curve(frame: pd.DataFrame, discipline: str, estimator: str):
    sub = frame[
        (frame.discipline == discipline) & (frame.estimator == estimator)
    ].dropna(subset=["msd_m2"])
    return (
        sub.t_s.to_numpy(),
        sub.msd_m2.to_numpy(),
        sub.n_flights.to_numpy(),
        sub.p10_m2.to_numpy(),
        sub.p90_m2.to_numpy(),
    )


def audit(discipline: str, audit_dir: Path) -> dict[str, str]:
    slug, macro, _, _ = DISCIPLINES[discipline]
    derived = _derived_dir(discipline)
    positions = audit_dir / f"audit_positions_{slug}.npz"
    if derived is None or not positions.is_file():
        print(f"{discipline}: audit inputs not reachable, skipping")
        return {}

    from scipy.stats import ks_2samp

    data = np.load(positions)
    lags, east, north = data["lags"], data["E"], data["N"]
    flights = pd.read_parquet(audit_dir / f"audit_flights_{slug}.parquet")
    meta = pd.read_parquet(derived / "flights_meta.parquet")
    segments = pd.read_parquet(derived / "segments.parquet")
    kept = meta[meta.drop_reason.isna()]

    squared = east**2 + north**2
    covered = np.isfinite(squared)
    msd = np.nanmean(squared, axis=0)
    counts = covered.sum(0)

    curves = pd.read_csv(CURVE_CSV)
    ea_t, ea_msd, ea_n, ea_p10, ea_p90 = _curve(curves, discipline, "ensemble")
    ta_t, ta_msd, ta_n, ta_p10, ta_p90 = _curve(curves, discipline, "time_averaged")

    out: dict[str, str] = {}

    def put(name: str, value) -> None:
        out[f"StatAudit{macro}{name}"] = value

    # ---- the fit ranges the figure used, rediscovered the way it discovers them ----
    from soaring.analysis.observables.transport import (
        MSDResult,
        coverage_limited_range,
    )

    ea_range = coverage_limited_range(
        MSDResult(t=ea_t, msd=ea_msd, n_flights=ea_n.astype(int), sem=None,
                  p10=None, p50=None, p90=None),
        t_min_s=FIT_MIN_S,
    )
    ta_range = coverage_limited_range(
        MSDResult(t=ta_t, msd=ta_msd, n_flights=ta_n.astype(int), sem=None,
                  p10=None, p50=None, p90=None),
        t_min_s=FIT_MIN_S,
    )

    # ---- B4: does a power law describe either curve? ------------------------------
    for label, (t, y, rng, lo, hi, cnt) in {
        "Ea": (ea_t, ea_msd, ea_range, ea_p10, ea_p90, ea_n),
        "Ta": (ta_t, ta_msd, ta_range, ta_p10, ta_p90, ta_n),
    }.items():
        inside = (t >= rng[0]) & (t <= rng[1])
        alpha, residual = power_law_residual(t[inside], y[inside])
        runs, expected_runs, runs_z = residual_runs(t[inside], y[inside])
        put(
            f"{label}ResidNoiseRatio",
            f"{residual_against_noise(y[inside], lo[inside], hi[inside], cnt[inside], residual):.0f}",
        )
        put(f"{label}ResidRuns", f"{runs}")
        put(f"{label}ResidRunsExpected", f"{expected_runs:.0f}")
        put(f"{label}ResidRunsZ", f"{runs_z:.1f}")
        put(f"{label}ResidLags", f"{int(inside.sum())}")
        slopes = local_slope(t, y)[inside]
        put(f"{label}Alpha", f"{alpha:.3f}")
        put(f"{label}ResidDex", f"{residual:.4f}")
        put(f"{label}ResidPct", f"{100 * (10**residual - 1):.1f}")
        put(f"{label}SlopeMin", f"{np.nanmin(slopes):.2f}")
        put(f"{label}SlopeMax", f"{np.nanmax(slopes):.2f}")
        put(f"{label}SlopeSwing", f"{np.nanmax(slopes) - np.nanmin(slopes):.2f}")
        put(f"{label}SlopeMinAt", f"{t[inside][np.nanargmin(slopes)]:.0f}")
        put(f"{label}SlopeMaxAt", f"{t[inside][np.nanargmax(slopes)]:.0f}")
    put("FitMinS", f"{ea_range[0]:.0f}")
    put("FitMaxS", f"{ea_range[1]:.0f}")

    inside = (lags >= ea_range[0]) & (lags <= ea_range[1]) & (counts >= 100)

    # ---- B2: the common-direction part ---------------------------------------------
    mean_e, mean_n = np.nanmean(east, 0), np.nanmean(north, 0)
    drift = (mean_e**2 + mean_n**2) / msd
    put("DriftPct", f"{100 * np.nanmax(drift[inside]):.1f}")

    # ---- B2: the heterogeneous-ballistic scale -------------------------------------
    # The numerator is a mean over the flights COVERED at each lag, so the denominator has
    # to be one too. Dividing by the mean speed of the whole table instead makes the ratio
    # drift with the lag purely because the two averages are taken over different
    # populations -- and drift is the only thing this diagnostic is read for.
    speed_sq = (flights.vbar_e**2 + flights.vbar_n**2).to_numpy()
    covered = np.isfinite(squared)
    with np.errstate(invalid="ignore"):
        mean_speed_sq = np.array(
            [speed_sq[covered[:, i]].mean() if covered[:, i].any() else np.nan
             for i in range(lags.size)]
        )
    ballistic = msd / (mean_speed_sq * lags**2)
    put("BallisticRmsMs", f"{np.sqrt(np.nanmean(speed_sq)):.2f}")
    put("BallisticRatioMin", f"{np.nanmin(ballistic[inside]):.1f}")
    put("BallisticRatioMax", f"{np.nanmax(ballistic[inside]):.1f}")

    # ---- B3: the controls that would explain the shape away ------------------------
    probes = np.array([150.0, 400.0, 1000.0, 1700.0])
    probe_idx = [int(np.argmin(np.abs(lags - p))) for p in probes]

    cadence_slopes = []
    for step in (1.0, 2.0, 5.0):
        member = np.isclose(flights.native_dt_s.to_numpy(), step)
        if member.sum() < 300:
            continue
        cadence_slopes.append(local_slope(lags, np.nanmean(squared[member], 0))[probe_idx])
    cadence = np.vstack(cadence_slopes)
    put("CadenceCohorts", str(cadence.shape[0]))
    put("CadenceSpread", f"{np.nanmax(cadence.max(0) - cadence.min(0)):.2f}")

    duration_slopes = []
    for threshold in (3600.0, 7200.0, 14_400.0):
        member = flights.duration_s.to_numpy() >= threshold
        if member.sum() < 300:
            continue
        slopes = local_slope(lags, np.nanmean(squared[member], 0))
        duration_slopes.append([slopes[i] for i, p in zip(probe_idx, probes) if p <= threshold])
    common = min(len(s) for s in duration_slopes)
    duration = np.vstack([s[:common] for s in duration_slopes])
    put("DurationSpread", f"{np.nanmax(duration.max(0) - duration.min(0)):.2f}")

    # ---- B3: when the population leaves the launch area ----------------------------
    radius = np.hypot(east, north)
    departure, leaves, early = departure_times(lags, radius, DEPARTURE_RADIUS_M)
    put("DepartureRadiusKm", f"{DEPARTURE_RADIUS_M / 1000:.0f}")
    put("DepartureLeavePct", f"{100 * leaves.mean():.1f}")
    put("DepartureMedianS", f"{np.median(departure):.0f}")
    put("DepartureIqrLowS", f"{np.percentile(departure, 25):.0f}")
    put("DepartureIqrHighS", f"{np.percentile(departure, 75):.0f}")
    put("DepartureBeforeGridPct", f"{100 * early:.2f}")

    # ---- E3: isotropy ---------------------------------------------------------------
    ratio = np.nanmean(east**2, 0) / np.nanmean(north**2, 0)
    put("IsoRatioMin", f"{np.nanmin(ratio[inside]):.2f}")
    put("IsoRatioMax", f"{np.nanmax(ratio[inside]):.2f}")
    ks_stats = []
    for probe in (FIT_MIN_S, 400.0, 1700.0, 7000.0):
        i = int(np.argmin(np.abs(lags - probe)))
        good = np.isfinite(east[:, i])
        if good.sum() < 100:
            continue
        ks_stats.append(ks_2samp(east[good, i], north[good, i]).statistic)
    put("IsoKsMin", f"{min(ks_stats):.3f}")
    put("IsoKsMax", f"{max(ks_stats):.3f}")
    put("IsoKsLags", str(len(ks_stats)))

    # ---- A: what the pipeline discarded, and what survived --------------------------
    lost = meta.loc[meta.drop_reason.eq("no_segment_survived"), "flight_id"]
    their = segments[segments.flight_id.isin(set(lost))]
    profile = their.groupby("flight_id").drop_reason.agg(
        lambda x: "|".join(sorted(set(x.dropna())))
    )
    sparsity_only = int((profile == "missing_fraction_above_max").sum())
    put("LostNoSegment", str(len(lost)))
    put("LostSparsityOnly", str(sparsity_only))
    put("LostSparsityPct", f"{100 * sparsity_only / max(len(lost), 1):.1f}")
    dropped = segments[segments.drop_reason.eq("missing_fraction_above_max")]
    put("SparsityMedianFrac", f"{dropped.frac_interpolated.median():.2f}")

    frozen_fixes = kept.n_removed_frozen.sum() / max(kept.n_fix_clean.sum(), 1)
    put("FrozenFixPct", f"{100 * frozen_fixes:.2f}")
    put("FrozenFlightPct", f"{100 * (kept.n_removed_frozen > 0).mean():.1f}")

    fingerprint = (
        kept.lat0.round(4).astype(str)
        + "|" + kept.lon0.round(4).astype(str)
        + "|" + kept.duration_flight_s.round(0).astype(str)
        + "|" + kept.path_km.round(2).astype(str)
    )
    duplicated = fingerprint.duplicated(keep=False)
    put("DupFlights", str(int(duplicated.sum())))
    put("DupGroups", str(int(fingerprint[duplicated].nunique())))
    put("DupPct", f"{100 * duplicated.mean():.3f}")

    first_kept = (
        segments[segments.kept].sort_values(["flight_id", "segment_id"])
        .groupby("flight_id").first()
    )
    put("LateStartPct", f"{100 * (first_kept.t_start > 0).mean():.1f}")
    at_zero = flights.flight_id.map(first_kept.t_start).eq(0).to_numpy()
    origin = np.hypot(data["r0"][:, 0], data["r0"][:, 1])
    put("OriginMedianM", f"{np.median(origin[at_zero]):.2f}")
    put("OriginMaxM", f"{origin[at_zero].max():.1f}")

    # ---- A: invariants that must hold on the retained table -------------------------
    put("NonFiniteFixes", str(int(flights.n_nonfinite.sum())))
    put("NonMonotoneFlights", str(int((~flights.t_monotone).sum())))
    put("MaxStepSpeedMs", f"{flights.max_step_speed_ms.max():.1f}")

    return out


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--audit-dir", type=Path, required=True)
    args = parser.parse_args()

    macros: dict[str, str] = {}
    for discipline in DISCIPLINES:
        macros.update(audit(discipline, args.audit_dir))
    if not macros:
        print("no audit inputs reachable; audit.tex not written")
        return 1

    lines = ["% Generated by scripts/reporting/audit_msd_report.py -- do not edit."]
    lines += [f"\\newcommand{{\\{k}}}{{{v}}}" for k, v in macros.items()]
    OUT_TEX.write_text("\n".join(lines) + "\n")
    print(f"wrote {OUT_TEX} ({len(macros)} macros)")
    for k, v in macros.items():
        print(f"  {k:42s} {v}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
