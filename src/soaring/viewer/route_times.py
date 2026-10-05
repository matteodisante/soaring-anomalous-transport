"""Recover the dates of retained route endpoints from the original IGC clock."""

from __future__ import annotations

import numpy as np
import pandas as pd

from ..analysis.igc import first_fix
from .catalog_index import resolve_igc_path
from .thermal_index import _check_cancel


def with_flight_times(selected, disciplines, *, progress=lambda _: None, cancel=None):
    """Attach UTC endpoints without mistaking relative archive times for dates.

    Cleaning stores seconds relative to the start of the trimmed airborne window.
    Restore that offset and the UTC origin of the first parsed IGC fix. Missing
    headers, files or trim offsets leave dates unavailable; catalogue dates are
    used only to locate the raw file, never to invent a clock origin.
    """
    result = selected.assign(departure_utc=np.nan, arrival_utc=np.nan)
    for disc in disciplines:
        _check_cancel(cancel)
        rows = result.loc[result.discipline == disc.name]
        if rows.empty:
            continue
        cfg = disc.config()
        catalog_path = getattr(cfg, "catalog_path", None)
        if catalog_path is None:
            continue
        try:
            meta = pd.read_parquet(
                cfg.derived_dir / "flights_meta.parquet",
                columns=["flight_id", "ground_phase_start_s"],
            )
            meta["flight_id"] = meta.flight_id.astype(str)
            offsets = (
                meta.drop_duplicates("flight_id", keep="last")
                .set_index("flight_id")
                .ground_phase_start_s
            )
            catalog = (
                pd.read_csv(
                    catalog_path,
                    usecols=["flight_id", "season_year", "date"],
                    dtype={"flight_id": str},
                )
                .drop_duplicates("flight_id", keep="last")
                .set_index("flight_id", drop=False)
            )
        except (OSError, KeyError, ValueError):
            continue
        for number, (index, row) in enumerate(rows.iterrows()):
            _check_cancel(cancel)
            if number % 25 == 0:
                progress(f"{disc.name}: reading flight dates {number + 1}/{len(rows)}")
            offset = offsets.get(row.flight_id, np.nan)
            if pd.isna(offset) or not np.isfinite(offset):
                continue
            if row.flight_id not in catalog.index:
                continue
            try:
                path = resolve_igc_path(disc, catalog.loc[row.flight_id])
                first = first_fix(path, include_utc=True) if path else None
            except (OSError, ValueError, TypeError, OverflowError):
                continue
            if first is None or not np.isfinite(first["start_utc"]):
                continue
            origin = first["start_utc"] + offset
            result.loc[index, ["departure_utc", "arrival_utc"]] = (
                origin + row.t0,
                origin + row.t1,
            )
    return result
