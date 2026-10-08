"""Velocity autocorrelation of successive Vilpellet glides, paragliders, by circuit.

Each glide ("transition" run of the archived Vilpellet segmentation) gets one
horizontal velocity, its net displacement divided by its duration:

    v_k = (r(t_end) - r(t_start)) / (t_end - t_start)

Fixed cohort: flights with at least MIN_GLIDES glides in one cleaned preprocessing
segment; each flight contributes its first such segment, so every flight enters every
lag n <= MIN_GLIDES - 1 and the population does not change with the lag. Glides are
numbered in time order inside the segment. Averages are taken along each flight
first, over all its pairs n glides apart, then over flights with equal weight:

    C_v(n)     = mean_f <v_k . v_{k+n}>_f / mean_f <|v_k|^2>_f     (non-centred)
    C_theta(n) = mean_f <cos(theta_{k+n} - theta_k)>_f

Circuit class ("task": open or closed) comes from the Chapter 3 cohort table.
SSD inputs are read-only; glide velocities are cached in build/. Writes
glide-autocorrelation.csv next to this script.
"""
from pathlib import Path
import time

import numpy as np
import pandas as pd
import pyarrow.parquet as pq

HERE = Path(__file__).resolve().parent
DERIVED = Path("/Volumes/SSD_DISANTE/paragliders/ffvl_cfd_igc/derived")
COHORT = Path("/Volumes/SSD_DISANTE/derived-audit/chapter3-fixed-20260917/para/flights.parquet")
CACHE = HERE / "build/glide-velocities-paragliders.parquet"
MIN_GLIDES = 50
KEYS = ["flight_id", "segment_id", "t"]


def glide_velocities() -> pd.DataFrame:
    """One row per glide with its net horizontal velocity (vE, vN), in m/s."""
    runs = pd.read_parquet(DERIVED / "segmentation/vilpellet/phase_segments.parquet")
    glides = runs.loc[runs.phase == "transition"].copy()
    glides["flight_id"] = glides.flight_id.astype(str)
    glides["segment_id"] = glides.segment_id.astype("int64")
    glides = glides.sort_values(["flight_id", "segment_id", "t_start"]).reset_index(drop=True)
    glides["glide"] = np.arange(len(glides))
    # Run bounds are fix times, so each endpoint matches exactly one cleaned fix.
    ends = pd.concat([
        glides[["glide", "flight_id", "segment_id", "t_start"]].rename(columns={"t_start": "t"}).assign(end=0),
        glides[["glide", "flight_id", "segment_id", "t_end"]].rename(columns={"t_end": "t"}).assign(end=1),
    ], ignore_index=True)
    by_flight = ends.groupby("flight_id").indices

    found = []
    parquet = pq.ParquetFile(DERIVED / "fixes.parquet")
    start = time.time()
    for group in range(parquet.metadata.num_row_groups):
        fixes = parquet.read_row_group(group, columns=["flight_id", "segment_id", "t", "E", "N"]).to_pandas()
        fixes["flight_id"] = fixes.flight_id.astype(str)
        fixes["segment_id"] = fixes.segment_id.astype("int64")
        fixes["t"] = fixes.t.astype("float64")
        rows = [by_flight[f] for f in fixes.flight_id.unique() if f in by_flight]
        if rows:
            found.append(ends.iloc[np.concatenate(rows)].merge(fixes, on=KEYS, how="inner"))
        if group % 200 == 0:
            print(f"  row group {group}/{parquet.metadata.num_row_groups}, {time.time() - start:.0f} s", flush=True)
    points = pd.concat(found, ignore_index=True).drop_duplicates(["glide", "end"])
    if len(points) != len(ends):
        raise RuntimeError(f"matched {len(points)} of {len(ends)} glide endpoints")

    wide = points.pivot(index="glide", columns="end", values=["E", "N"])
    span = glides.t_end - glides.t_start
    glides["vE"] = (wide[("E", 1)] - wide[("E", 0)]) / span
    glides["vN"] = (wide[("N", 1)] - wide[("N", 0)]) / span
    return glides


def fixed_cohort(glides: pd.DataFrame) -> pd.DataFrame:
    """The first segment of each flight with at least MIN_GLIDES usable glides."""
    g = glides.dropna(subset=["vE", "vN"])
    g = g.loc[(g.t_end > g.t_start) & ((g.vE != 0) | (g.vN != 0))]
    size = g.groupby(["flight_id", "segment_id"]).glide.transform("size")
    g = g.loc[size >= MIN_GLIDES]
    return g.loc[g.segment_id == g.groupby("flight_id").segment_id.transform("min")]


def autocorrelation(cohort: pd.DataFrame) -> pd.DataFrame:
    """Average along each flight, then over flights with equal weight."""
    lags = np.arange(1, MIN_GLIDES)
    dots, cosines, norms = [], [], []
    for _, flight in cohort.groupby("flight_id", sort=False):
        v = flight[["vE", "vN"]].to_numpy()  # already in time order
        u = v / np.hypot(v[:, 0], v[:, 1])[:, None]
        norms.append(np.mean(np.sum(v * v, axis=1)))
        dots.append([np.mean(np.sum(v[:-n] * v[n:], axis=1)) for n in lags])
        cosines.append([np.mean(np.sum(u[:-n] * u[n:], axis=1)) for n in lags])
    return pd.DataFrame({
        "lag": np.r_[0, lags],
        "C_v": np.r_[1.0, np.mean(dots, axis=0) / np.mean(norms)],
        "C_theta": np.r_[1.0, np.mean(cosines, axis=0)],
    })


if __name__ == "__main__":
    if CACHE.exists():
        glides = pd.read_parquet(CACHE)
    else:
        CACHE.parent.mkdir(parents=True, exist_ok=True)
        glides = glide_velocities()
        glides.to_parquet(CACHE)
    tasks = pd.read_parquet(COHORT, columns=["flight_id", "task"]).astype({"flight_id": str})
    glides = glides.merge(tasks, on="flight_id", how="left")
    tables = []
    for task, subset in (("all", glides), ("open", glides[glides.task == "open"]),
                         ("closed", glides[glides.task == "closed"])):
        cohort = fixed_cohort(subset)
        tables.append(autocorrelation(cohort).assign(task=task, flights=cohort.flight_id.nunique(),
                                                     min_glides=MIN_GLIDES))
    pd.concat(tables).to_csv(HERE / "glide-autocorrelation.csv", index=False)
    print(pd.concat(tables).query("lag in [1, 5, 10, 20, 30, 40, 49]").to_string(index=False))
