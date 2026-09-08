#!/usr/bin/env python3
r"""The time-averaged MSD split by flight duration -- the direct aging check App. A poses.

Reads ``thesis/generated/msd_curve.csv`` (already written by ``generate_msd_figure.py``,
which keeps the pooled time-averaged MSD and its three fixed-duration cohorts --
segments of at least 1, 2 and 4 hours -- from the same streaming pass), and produces:

* ``thesis/generated/msd_duration.pdf`` -- the pooled TA-MSD against its own cohorts,
  one panel per discipline;
* ``thesis/generated/msd_duration.tex`` -- the ``\\StatMsdTa*CohortAmp*`` macros (each
  cohort's TA-MSD relative to the pooled curve, read at one fixed reference lag common
  to all of them) and, when ``--audit-dir`` is given, the ``\\StatErgo*`` macros: the
  ergodicity-breaking parameter at one fixed lag, swept over the duration threshold T --
  not swept over the lag, since the question App.~app:ctrw poses is about the T
  dependence at a lag held fixed (see :func:`ergodicity_breaking`).

No new pass over the archive: everything here is a reduction of a CSV and of the
``variations_<slug>.npz`` pass already on disk, so it costs a fraction of a second and
needs neither a new traversal nor the SSD beyond reading those two files.

Why this figure: App. app:ctrw derives that a CTRW with power-law waiting times has a
time-averaged MSD whose *prefactor* depends on the total duration T of the record it is
read from -- the aging signature, present for a non-ergodic process and absent for an
ergodic one, regardless of whether the process is that particular CTRW. Sec. sec:obs-global
promises this check when it declines to read the EA/TA gap as evidence of aging on its
own; this is that check, on the same segments the pooled curve already uses.

Run it after ``generate_msd_figure.py``::

    uv run python scripts/reporting/ch3_global_transport/generate_msd_duration_figure.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
CURVE_CSV = ROOT / "thesis" / "generated" / "msd_curve.csv"
OUT_FIG = ROOT / "thesis" / "generated" / "msd_duration.pdf"
OUT_TEX = ROOT / "thesis" / "generated" / "msd_duration.tex"

_SRC = str(ROOT / "src")
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

# The sys.path line above is what makes this resolvable when the script is run
# directly, so the import cannot move to the top of the file.
from soaring.reporting import write_macros  # noqa: E402

# Matches generate_msd_figure.py's own COHORTS_S -- duplicated rather than imported for
# the same reason FIT_MIN_S is there: the two scripts do not import from each other.
THRESHOLDS_S = (3600.0, 7200.0, 14_400.0)
_HOURS = {1: "One", 2: "Two", 4: "Four"}

# Where the amplitude comparison is read: well inside even the shortest cohort's own
# reach (half of 3600 s = 1800 s), and inside the pooled fit range
# (StatMsdTaParaFitMinS-FitMaxS), so every curve compared has a well-populated estimate
# there.
REFERENCE_LAG_S = 1000.0

# A flight answers a duration threshold for the ergodicity-breaking parameter only with
# at least this many of its own windows behind the fixed lag's per-flight V1 -- the same
# duration/lag reach rule generate_shape_figure.py's matched_gaussian_null already
# applies, for the same reason: fewer windows means the per-flight value is dominated by
# that one record's own sampling noise rather than by where its true time average sits,
# which would inflate EB for a reason that has nothing to do with ergodicity.
EB_MIN_WINDOWS = 4
EB_MIN_FLIGHTS = 200

# App. app:ctrw's EB(t, T) is a function of the lag t *and* the record duration T, and the
# question it answers -- does the scatter across flights shrink as the record gets longer,
# or sit at a positive constant -- is a question about the T dependence at one lag held
# fixed, not about how EB varies with the lag. Varying the lag while implicitly letting T
# track "however long that flight happens to be" answers neither question cleanly, so the
# lag is fixed here and T is the swept variable instead.
#
# The lag is fixed well below the smallest duration threshold below (at least a factor
# EB_MIN_WINDOWS x 3 under 1 h), so the EB_MIN_WINDOWS reach rule is satisfied at every
# threshold by construction and never itself shapes the T dependence being read.
EB_LAG_TARGET_S = 300.0

# Duration thresholds T: flights with duration_s >= T answer this T, each contributing its
# own full-duration time average at the fixed lag above -- the same "at least T" cohort
# construction generate_msd_figure.py's fixed-duration cohorts already use, applied to the
# ergodicity-breaking parameter instead of to the TA-MSD amplitude.
EB_DURATION_THRESHOLDS_S = (3600.0, 7200.0, 10_800.0, 14_400.0)
_EB_HOURS = {1: "One", 2: "Two", 3: "Three", 4: "Four"}

_PDF_METADATA = {
    "Creator": "soaring.analysis",
    "Producer": "soaring.analysis",
    "CreationDate": None,
}


def _load_curve(table, discipline: str, estimator: str):
    from soaring.analysis.observables.transport import MSDResult

    rows = table[
        (table["discipline"] == discipline) & (table["estimator"] == estimator)
    ].sort_values("t_s")
    if rows.empty:
        return None
    return MSDResult(
        t=rows["t_s"].to_numpy(),
        msd=rows["msd_m2"].to_numpy(),
        n_flights=rows["n_flights"].to_numpy(),
        sem=None,
        p10=None,
        p50=None,
        p90=None,
    )


def _at(curve, target_s: float) -> tuple[float, float]:
    """The curve's own lag and MSD nearest ``target_s``."""
    idx = int(np.nanargmin(np.abs(curve.t - target_s)))
    return float(curve.t[idx]), float(curve.msd[idx])


def _macro_name(discipline: str) -> str:
    return "Para" if discipline.startswith("para") else "Hang"


def ergodicity_breaking(discipline: str, audit_dir, macros: dict) -> dict | None:
    r"""The ergodicity-breaking parameter, swept over duration T at one fixed lag.

    App.~app:ctrw defines :math:`\mathrm{EB}(t,T)` as the variance, across trajectories,
    of each one's own time-averaged MSD read at lag :math:`t` from a record of duration
    :math:`T`, normalised by the square of its mean -- a quantity that tends to a positive
    constant as :math:`T\to\infty` for a non-ergodic process and to zero for an ergodic
    one. The question is squarely about the :math:`T` dependence at a lag held fixed, so
    that is what is computed here: the lag is fixed at :data:`EB_LAG_TARGET_S` and the
    swept variable is the duration threshold, each threshold answered by the flights whose
    own duration reaches it -- the same "at least T" cohort construction the amplitude
    panel above uses, applied to the scatter across flights rather than to the pooled
    curve's amplitude.

    The input is ``order1`` from ``variations_<slug>.npz`` (Sec.~sec:variations), one row
    per flight and one column per lag: :math:`\alpha_1` **is** :math:`\overline{\delta^2
    (\Delta)}` under another name (Sec.~sec:variations), so the per-flight time average
    App.~app:ctrw's derivation needs is already sitting in a pass this chapter has already
    paid for, and no new traversal of the fix table is spent on it.

    A flight answers a duration threshold only with :data:`EB_MIN_WINDOWS` of its own
    windows behind the fixed lag's estimate -- see the module docstring for why.
    """
    import pandas as pd

    from soaring.reporting import DISCIPLINES

    slug = DISCIPLINES[discipline].slug
    npz_path = audit_dir / f"variations_{slug}.npz"
    flights_path = audit_dir / f"variation_flights_{slug}.parquet"
    if not (npz_path.is_file() and flights_path.is_file()):
        return None

    data = np.load(npz_path)
    if "order1" not in data:
        return None
    lags, order1 = data["lags_s"], data["order1"]
    duration = pd.read_parquet(flights_path, columns=["duration_s"])["duration_s"].to_numpy(
        dtype=float
    )
    if order1.shape[0] != duration.size:
        return None

    lag_idx = int(np.nanargmin(np.abs(lags - EB_LAG_TARGET_S)))
    lag = float(lags[lag_idx])
    value = order1[:, lag_idx]
    windows = np.floor(duration / lag)
    finite = np.isfinite(value) & (value > 0) & (windows >= EB_MIN_WINDOWS)

    tag = DISCIPLINES[discipline].tag
    thresholds_s: list[float] = []
    eb_values: list[float] = []
    n_flights: list[int] = []
    for threshold in EB_DURATION_THRESHOLDS_S:
        good = finite & (duration >= threshold)
        if good.sum() < EB_MIN_FLIGHTS:
            continue
        sample = value[good]
        mean = float(np.mean(sample))
        if mean <= 0:
            continue
        thresholds_s.append(threshold)
        eb_values.append(float(np.var(sample, ddof=1) / mean**2))
        n_flights.append(int(good.sum()))

    if not thresholds_s:
        return None

    thresholds_arr = np.asarray(thresholds_s)
    eb_arr = np.asarray(eb_values)
    n_arr = np.asarray(n_flights)

    macros[f"StatErgo{tag}LagS"] = f"{lag:.0f}"
    macros[f"StatErgo{tag}MinWindows"] = f"{EB_MIN_WINDOWS}"
    macros[f"StatErgo{tag}RangeMinH"] = f"{thresholds_arr.min() / 3600.0:.0f}"
    macros[f"StatErgo{tag}RangeMaxH"] = f"{thresholds_arr.max() / 3600.0:.0f}"
    macros[f"StatErgo{tag}Min"] = f"{eb_arr.min():.2f}"
    macros[f"StatErgo{tag}Max"] = f"{eb_arr.max():.2f}"
    for threshold, eb_value, n in zip(thresholds_arr, eb_arr, n_arr):
        hours = _EB_HOURS.get(int(round(threshold / 3600.0)))
        if hours is None:
            continue
        macros[f"StatErgo{tag}At{hours}H"] = f"{eb_value:.2f}"
        macros[f"StatErgo{tag}At{hours}HFlights"] = f"{n}"

    return {"thresholds_s": thresholds_arr, "eb": eb_arr, "n_flights": n_arr, "lag_s": lag}



def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--audit-dir", type=Path, default=None,
        help="where variations_<slug>.npz lives, for the ergodicity-breaking parameter "
             "panel; omit to draw the cohort panel alone.",
    )
    args = parser.parse_args()

    try:
        import matplotlib

        import pandas as pd
    except ImportError:
        print("matplotlib/pandas missing ('analysis' group); keeping the committed figure.")
        return 0
    matplotlib.use("Agg")

    from soaring.analysis.figures.msd_duration import make_msd_duration_figure

    if not CURVE_CSV.is_file():
        print(f"{CURVE_CSV} not found: run generate_msd_figure.py first.")
        return 1
    table = pd.read_csv(CURVE_CSV)

    pooled: dict[str, object] = {}
    cohorts: dict[str, dict[float, object]] = {}
    ergo: dict[str, dict] = {}
    macros: dict[str, str] = {}

    for discipline in table["discipline"].unique():
        ta = _load_curve(table, discipline, "time_averaged")
        if ta is None:
            continue
        pooled[discipline] = ta
        cohorts[discipline] = {}
        ref_t, ref_msd = _at(ta, REFERENCE_LAG_S)
        tag = _macro_name(discipline)
        macros[f"StatMsdTa{tag}CohortAmpRefS"] = f"{ref_t:.0f}"
        print(f"[{discipline}] pooled TA-MSD at {ref_t:.0f} s: {ref_msd:.3e} m^2")
        for threshold in THRESHOLDS_S:
            curve = _load_curve(table, discipline, f"ta_cohort_{int(threshold)}s")
            if curve is None:
                continue
            cohorts[discipline][threshold] = curve
            c_t, c_msd = _at(curve, REFERENCE_LAG_S)
            ratio = c_msd / ref_msd
            hours = _HOURS[int(threshold / 3600)]
            macros[f"StatMsdTa{tag}CohortAmp{hours}H"] = f"{ratio:.2f}"
            print(
                f"    >= {threshold / 3600:.0f} h at {c_t:.0f} s: {c_msd:.3e} m^2 "
                f"-> {ratio:.2f}x pooled"
            )

        if args.audit_dir is not None:
            result = ergodicity_breaking(discipline, args.audit_dir, macros)
            if result is not None:
                ergo[discipline] = result
                summary = ", ".join(
                    f"{t / 3600:.0f} h: {eb:.2f}"
                    for t, eb in zip(result["thresholds_s"], result["eb"])
                )
                print(f"    EB(t={result['lag_s']:.0f} s, T) = {summary}")
            else:
                print(f"    {discipline}: variations pass not found, no EB panel")

    if not macros:
        print("no time-averaged curves in the CSV; msd_duration.tex not written")
        return 0

    write_macros(
        OUT_TEX,
        macros,
        generator="scripts/reporting/ch3_global_transport/generate_msd_duration_figure.py",
    )
    print(f"Wrote {OUT_TEX.name}.")

    OUT_FIG.parent.mkdir(parents=True, exist_ok=True)
    make_msd_duration_figure(pooled, cohorts, THRESHOLDS_S, ergo).savefig(
        OUT_FIG, metadata=_PDF_METADATA, bbox_inches="tight"
    )
    print(f"Wrote {OUT_FIG.name}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
