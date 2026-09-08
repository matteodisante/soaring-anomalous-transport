#!/usr/bin/env python3
r"""One streaming pass for the observables that need the increments themselves.

The variation pass keeps a second moment per flight per lag, which is enough for an
exponent and not enough for anything about *shape*. Two observables need more, and both
need the same traversal, so they share one:

* the **moment spectrum** :math:`\langle|\Delta\mathbf{r}|^q\rangle`, which discriminates a
  Lévy walk from a correlated Gaussian process in one figure;
* the **velocity autocorrelation**, whose integral must reproduce the displacement if the
  position and velocity channels are consistent.

The moments are accumulated as pooled sums, since a moment of the ensemble is a sum over
every increment of every flight and not an average of per-flight moments; the per-flight
counts travel with them so the pooling is exact. The tail control needs the largest
increments of the *pooled* sample, which a single pass cannot hold, so it is computed on a
seeded subsample of flights and reported as such.
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
from soaring.reporting import DISCIPLINES  # noqa: E402

LAG_MIN_S, LAG_MAX_S, N_LAGS = 60.0, 8000.0, 24
VACF_MAX_S = 1200.0

# Flights whose increments are kept whole, for the pooled tail control. One in this many.
TAIL_SUBSAMPLE = 40


def run(discipline: str, out_dir: Path) -> int:
    from soaring.analysis.derived import stream_flights
    from soaring.analysis.observables.moments import Q_GRID, _increment_vectors
    from soaring.analysis.observables.persistence import velocity_autocorrelation

    derived = DISCIPLINES[discipline].derived_dir()
    if derived is None:
        print(f"{discipline}: fixes.parquet not reachable, skipping")
        return 1

    lags_s = np.unique(np.round(np.geomspace(LAG_MIN_S, LAG_MAX_S, N_LAGS)))
    q_grid = np.asarray(Q_GRID)
    n_lag, n_q = lags_s.size, q_grid.size

    moment_sum = np.zeros((n_lag, n_q))
    moment_count = np.zeros(n_lag)
    vacf_sum = None
    vacf_count = 0
    tail_pool = {i: [] for i in range(n_lag)}
    rows: list[dict] = []

    # Raw (uncentred) power sums of the two signed components, pooled the same way as the
    # modulus moments above and over the same windows -- moment_count already counts them.
    # Together they are exactly what sec:transport-gaussian needs and nothing more: the
    # per-component excess kurtosis (east_m2/m4, north_m2/m4 alone) and Mardia's kurtosis of
    # the joint (east, north) distribution, which also needs the cross moments
    # <dx dy>, <dx^3 dy>, <dx^2 dy^2>, <dx dy^3>. Not centred on a per-flight mean: the same
    # convention the modulus non-Gaussian parameter already uses, and defensible at the
    # archive level since courses point every which way and average out pooled, unlike
    # within one flight (Sec. transport-gaussian; matched_gaussian_null below).
    east_m2_sum = np.zeros(n_lag)
    east_m4_sum = np.zeros(n_lag)
    north_m2_sum = np.zeros(n_lag)
    north_m4_sum = np.zeros(n_lag)
    cross_xy_sum = np.zeros(n_lag)
    cross_x3y_sum = np.zeros(n_lag)
    cross_x2y2_sum = np.zeros(n_lag)
    cross_xy3_sum = np.zeros(n_lag)

    for count, flight in enumerate(
        stream_flights(derived / "fixes.parquet", ["segment_id", "t", "E", "N", "v_E", "v_N"]), 1
    ):
        ordered = flight.sort_values(["segment_id", "t"], kind="stable")
        vacf_flight = False
        flight_id = str(ordered["flight_id"].iloc[0])
        keep_tail = (count % TAIL_SUBSAMPLE) == 0

        for _, segment in ordered.groupby("segment_id", sort=False):
            times = segment["t"].to_numpy(dtype=float)
            if times.size < 16:
                continue
            step = float(np.median(np.diff(times)))
            if not np.isfinite(step) or step <= 0:
                continue
            positions = np.column_stack(
                [segment["E"].to_numpy(dtype=float), segment["N"].to_numpy(dtype=float)]
            )

            for i, lag_s in enumerate(lags_s):
                lag = int(round(lag_s / step))
                vectors = _increment_vectors(positions, lag, order=1)
                if vectors.shape[0] == 0:
                    continue
                dx, dy = vectors[:, 0], vectors[:, 1]
                magnitude = np.hypot(dx, dy)
                moment_count[i] += magnitude.size
                for j, q in enumerate(q_grid):
                    moment_sum[i, j] += float((magnitude**q).sum())
                if keep_tail and magnitude.size:
                    tail_pool[i].append(magnitude.astype(np.float32))
                dx2, dy2 = dx * dx, dy * dy
                east_m2_sum[i] += float(dx2.sum())
                east_m4_sum[i] += float((dx2 * dx2).sum())
                north_m2_sum[i] += float(dy2.sum())
                north_m4_sum[i] += float((dy2 * dy2).sum())
                cross_xy_sum[i] += float((dx * dy).sum())
                cross_x3y_sum[i] += float((dx2 * dx * dy).sum())
                cross_x2y2_sum[i] += float((dx2 * dy2).sum())
                cross_xy3_sum[i] += float((dx * dy2 * dy).sum())

            velocity = np.column_stack(
                [segment["v_E"].to_numpy(dtype=float), segment["v_N"].to_numpy(dtype=float)]
            )
            max_lag = int(min(VACF_MAX_S / step, velocity.shape[0] // 4))
            if max_lag >= 4:
                _, correlation = velocity_autocorrelation(velocity, max_lag=max_lag)
                if correlation.size:
                    grid = np.round(lags_s[lags_s <= VACF_MAX_S] / step).astype(int)
                    grid = grid[(grid >= 0) & (grid < correlation.size)]
                    sampled = np.full(lags_s.size, np.nan)
                    sampled[: grid.size] = correlation[grid]
                    if vacf_sum is None:
                        vacf_sum = np.zeros(lags_s.size)
                        vacf_n = np.zeros(lags_s.size)
                    good = np.isfinite(sampled)
                    vacf_sum[good] += sampled[good]
                    vacf_n[good] += 1
                    vacf_flight = True

        if vacf_flight:
            vacf_count += 1
        rows.append({"flight_id": flight_id})
        if count % 20_000 == 0:
            print(f"  {discipline}: {count} flights", flush=True)

    slug = DISCIPLINES[discipline].slug
    out_dir.mkdir(parents=True, exist_ok=True)
    tails = {}
    for i in range(n_lag):
        if tail_pool[i]:
            pooled = np.concatenate(tail_pool[i])
            keep = max(1, int(round(0.01 * pooled.size)))
            weights = {}
            for j, q in enumerate(q_grid):
                w = pooled.astype(float) ** q
                weights[j] = float(np.sort(w)[-keep:].sum() / w.sum()) if w.sum() > 0 else np.nan
            tails[i] = [weights[j] for j in range(n_q)]
    tail_share = np.full((n_lag, n_q), np.nan)
    for i, row in tails.items():
        tail_share[i] = row

    def _mean(total):
        return np.where(moment_count > 0, total / np.maximum(moment_count, 1), np.nan)

    np.savez_compressed(
        out_dir / f"shape_{slug}.npz",
        lags_s=lags_s,
        q_grid=q_grid,
        moment=np.where(moment_count[:, None] > 0, moment_sum / np.maximum(moment_count[:, None], 1), np.nan),
        moment_count=moment_count,
        tail_share=tail_share,
        vacf=np.where(vacf_n > 0, vacf_sum / np.maximum(vacf_n, 1), np.nan) if vacf_sum is not None else np.zeros(0),
        vacf_flights=np.array([vacf_count]),
        # <dx^2>, <dx^4>, <dy^2>, <dy^4>, and the three cross moments Mardia's kurtosis of
        # the joint (dx, dy) distribution needs beyond the per-component ones.
        east_m2=_mean(east_m2_sum),
        east_m4=_mean(east_m4_sum),
        north_m2=_mean(north_m2_sum),
        north_m4=_mean(north_m4_sum),
        cross_xy=_mean(cross_xy_sum),
        cross_x3y=_mean(cross_x3y_sum),
        cross_x2y2=_mean(cross_x2y2_sum),
        cross_xy3=_mean(cross_xy3_sum),
    )
    print(f"{discipline}: {len(rows)} flights, {n_lag} lags -> {out_dir}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--discipline", choices=[*DISCIPLINES, "all"], default="all")
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    status = 0
    for discipline in (list(DISCIPLINES) if args.discipline == "all" else [args.discipline]):
        status |= run(discipline, args.out)
    return status


if __name__ == "__main__":
    raise SystemExit(main())
