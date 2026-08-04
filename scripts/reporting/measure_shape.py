#!/usr/bin/env python3
r"""One streaming pass for the observables that need the increments themselves.

The variation pass keeps a second moment per flight per lag, which is enough for an
exponent and not enough for anything about *shape*. Three observables need more, and all
three need the same traversal, so they share one:

* the **moment spectrum** :math:`\langle|\Delta\mathbf{r}|^q\rangle`, which discriminates a
  Lévy walk from a correlated Gaussian process in one figure;
* the **velocity autocorrelation**, whose integral must reproduce the displacement if the
  position and velocity channels are consistent;
* the **persistence runs**, which say how far the wing goes before it turns, with the
  non-overlapping decomposition that avoids the inspection bias.

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
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
_SRC = str(ROOT / "src")
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

DISCIPLINES = {
    "paragliders": ("para", "SOARING_PARA_DATA_ROOT", "PARA_CONFIG_PATH"),
    "hang gliders": ("hang", "SOARING_DELTA_DATA_ROOT", "DELTA_CONFIG_PATH"),
}

LAG_MIN_S, LAG_MAX_S, N_LAGS = 60.0, 8000.0, 24
VACF_MAX_S = 1200.0
SINUOSITIES = (1.05, 1.15, 1.30)

# Flights whose increments are kept whole, for the pooled tail control. One in this many.
TAIL_SUBSAMPLE = 40


def _derived_and_catalog(discipline: str):
    from soaring.acquisition.ffvl import config as cfgmod

    _, env, attr = DISCIPLINES[discipline]
    try:
        cfg = cfgmod.load_config(str(getattr(cfgmod, attr)), data_root_env=env)
    except (FileNotFoundError, KeyError):
        return None, None
    if not (cfg.derived_dir / "fixes.parquet").is_file():
        return None, None
    return cfg.derived_dir, cfg.catalog_path


def run(discipline: str, out_dir: Path) -> int:
    from soaring.analysis.derived import stream_flights
    from soaring.analysis.observables.moments import Q_GRID, _increments
    from soaring.analysis.observables.persistence import (
        persistence_runs,
        velocity_autocorrelation,
    )

    derived, catalog_path = _derived_and_catalog(discipline)
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
    runs = {s: [] for s in SINUOSITIES}
    tail_pool = {i: [] for i in range(n_lag)}
    rows: list[dict] = []

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
                magnitude = _increments(positions, lag, order=1)
                if magnitude.size == 0:
                    continue
                moment_count[i] += magnitude.size
                for j, q in enumerate(q_grid):
                    moment_sum[i, j] += float((magnitude**q).sum())
                if keep_tail and magnitude.size:
                    tail_pool[i].append(magnitude.astype(np.float32))

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

            for sinuosity in SINUOSITIES:
                lengths = persistence_runs(positions, sinuosity)
                if lengths.size:
                    runs[sinuosity].append(lengths * step)

        if vacf_flight:
            vacf_count += 1
        rows.append({"flight_id": flight_id})
        if count % 20_000 == 0:
            print(f"  {discipline}: {count} flights", flush=True)

    slug = DISCIPLINES[discipline][0]
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

    np.savez_compressed(
        out_dir / f"shape_{slug}.npz",
        lags_s=lags_s,
        q_grid=q_grid,
        moment=np.where(moment_count[:, None] > 0, moment_sum / np.maximum(moment_count[:, None], 1), np.nan),
        moment_count=moment_count,
        tail_share=tail_share,
        vacf=np.where(vacf_n > 0, vacf_sum / np.maximum(vacf_n, 1), np.nan) if vacf_sum is not None else np.zeros(0),
        vacf_flights=np.array([vacf_count]),
        **{f"runs_{str(s).replace('.', 'p')}": np.concatenate(runs[s]) if runs[s] else np.zeros(0)
           for s in SINUOSITIES},
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
