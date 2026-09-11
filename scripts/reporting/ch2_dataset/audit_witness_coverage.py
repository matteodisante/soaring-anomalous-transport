#!/usr/bin/env python3
"""Compare legacy endpoint-only and complete paired-pressure witness rules.

Reads the stored 2.0.0 flight metadata to select possible affected flights and
reruns both rules on each raw file without replacing the cleaned archive.
Keeps the historical 30 m/s vertical cutoff to isolate the witness change from
the later 2.1.0 change of operating point to 10 m/s.
Writes machine-readable changes to thesis/generated/cleaning_witness_audit.json.
"""

from __future__ import annotations

import json
import sys
from concurrent.futures import ProcessPoolExecutor
from dataclasses import replace
from pathlib import Path

import numpy as np
import pandas as pd

GENERATED_OUTPUTS = ("cleaning_witness_audit.tex", "cleaning_witness_audit.json")

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "src"))
from soaring.analysis.config import load_preproc_config  # noqa: E402
from soaring.analysis.igc import parse_igc  # noqa: E402
from soaring.analysis.preproc import cleaning, trimming  # noqa: E402
from soaring.analysis.preproc.pipeline import run_flight  # noqa: E402
from soaring.reporting import DISCIPLINES  # noqa: E402

NEW_W = cleaning._is_witnessed
NEW_F = trimming._is_flat
NEW_M = cleaning._merge_duplicate_seconds


def old_w(lat, lon, alt, baro, valid, fix_level, baro_witness):
    """Legacy 2.0.0 run witness, kept fixed as the audit comparator."""
    if np.all(lat == lat[0]) and np.all(lon == lon[0]):
        return True
    if baro_witness:
        end = max(1, baro.size // 4)
        if not (np.isfinite(baro[:end]).any() and np.isfinite(baro[-end:]).any()):
            return False
        return (
            abs(np.nanmedian(baro[-end:]) - np.nanmedian(baro[:end]))
            < fix_level.frozen_delta_z_m
        )
    return bool((~valid.astype(bool) | ~np.isfinite(alt)).mean() > 0.5)


def old_f(t, alt, tolerance_m, max_drift_mps):
    """Legacy ground guard, permitting missing pressure values inside a stint."""
    finite = np.isfinite(alt)
    if finite.sum() < 3:
        return False
    slope, intercept = np.polyfit(t[finite], alt[finite], 1)
    residual = alt[finite] - (slope * t[finite] + intercept)
    spread = float(np.percentile(residual, 95) - np.percentile(residual, 5))
    return bool(spread <= tolerance_m and abs(slope) <= max_drift_mps)


def old_m(fixes):
    """Legacy duplicate aggregation, before missing barometer normalisation."""
    t = fixes["t"].to_numpy(dtype=float)
    if t.size < 2 or not (np.diff(t) == 0).any():
        return fixes, 0
    grouped = fixes.groupby("t", sort=True)
    merged = grouped.mean(numeric_only=True)
    if "valid" in fixes:
        merged["valid"] = grouped["valid"].all()
    merged = merged.reset_index()
    return merged[[c for c in fixes.columns if c in merged]], t.size - len(merged)


def one(task):
    """Compare both rules on one raw flight in an isolated worker process."""
    disc, source, fid, path = task
    try:
        raw = parse_igc(path)
        cfg = load_preproc_config()
        # Historical control, not the operational cleaning threshold.
        cfg = replace(cfg, fix=replace(cfg.fix, max_vertical_speed_mps=30.0))
        cleaning._merge_duplicate_seconds = old_m
        cleaning._is_witnessed = old_w
        trimming._is_flat = old_f
        a = run_flight(raw, cfg, source=source, flight_id=fid, discipline=disc)
        cleaning._merge_duplicate_seconds = NEW_M
        cleaning._is_witnessed = NEW_W
        trimming._is_flat = NEW_F
        b = run_flight(raw, cfg, source=source, flight_id=fid, discipline=disc)
        fields = [
            "n_removed_frozen",
            "n_interior_excised",
            "drop_reason",
            "n_fix_clean",
            "duration_flight_s",
        ]
        change = {
            k: [getattr(a.meta, k), getattr(b.meta, k)]
            for k in fields
            if getattr(a.meta, k) != getattr(b.meta, k)
        }
        return {"discipline": disc, "flight_id": fid, "change": change}
    except Exception as e:
        return {"discipline": disc, "flight_id": fid, "error": str(e)}


def write_tex(summary):
    """Write the auditable comparison sentence included directly by Chapter 2."""
    changes = summary["changed"]
    nfreeze = sum("n_removed_frozen" in x["change"] for x in changes)
    nland = sum("n_interior_excised" in x["change"] for x in changes)
    fixes = sum(
        x["change"].get("n_removed_frozen", [0, 0])[0]
        - x["change"].get("n_removed_frozen", [0, 0])[1]
        for x in changes
    )
    verdicts = sum("drop_reason" in x["change"] for x in changes)
    lines = [
        "The targeted comparison reran the legacy and corrected rules on",
        f"{summary['processed']:,} candidates: {len(changes):,} flights changed.",
        f"Frozen-run counts changed in {nfreeze:,} cases; interior-ground counts",
        f"changed in {nland:,} cases (the categories can overlap).",
        f"The corrected witness retained {fixes:,} additional horizontal fixes;",
        f"{verdicts:,} flight admission decisions changed.",
        "These counts describe the targeted set, not detector error rates.",
        "They do not replace regeneration of the archive and its observables.",
    ]
    (ROOT / "thesis/generated/cleaning_witness_audit.tex").write_text(
        "% Generated by scripts/reporting/ch2_dataset/audit_witness_coverage.py\n"
        + "\n".join(lines)
        + "\n"
    )


if __name__ == "__main__":
    tasks = []
    totals = {}
    for d, g in DISCIPLINES.items():
        root = g.config().igc_dir
        meta = pd.read_parquet(
            g.derived_dir("flights_meta.parquet") / "flights_meta.parquet"
        )
        c = meta.loc[
            meta.baro_witness.eq(True)
            & meta.baro_present_frac.lt(1)
            & (
                (meta.n_removed_frozen > 0)
                | (meta.n_interior_excised > 0)
                | (meta.n_merged_duplicates > 0)
            )
        ].copy()
        c["flight_id"] = c.flight_id.astype(str)
        cat = pd.read_csv(
            g.catalog_path(),
            dtype={"flight_id": str},
            usecols=["flight_id", "local_path"],
        )
        c = c.merge(cat, on="flight_id", how="left")
        totals[d] = len(c)
        for r in c.itertuples():
            p = root / r.local_path.split("/igc/", 1)[1]
            tasks.append((d, g.source, str(r.flight_id), str(p)))
    print("Targeted candidates", totals, flush=True)
    results = []
    with ProcessPoolExecutor(max_workers=4) as ex:
        for i, r in enumerate(ex.map(one, tasks, chunksize=5)):
            results.append(r)
            if (i + 1) % 100 == 0:
                print(
                    i + 1,
                    "processed;",
                    sum(bool(x.get("change")) for x in results),
                    "changed",
                    flush=True,
                )
    summary = {
        "selection": (
            "Stored flights with eligible but incomplete barometer and any "
            "frozen-run removal, interior-ground excision, or duplicate merges; "
            "compare legacy2.0.0 and corrected2.0.1 witness rules with identical "
            "configuration and the historical 30 m/s vertical cutoff."
        ),
        "selected": totals,
        "processed": len(results),
        "changed": [r for r in results if r.get("change")],
        "errors": [r for r in results if r.get("error")],
    }
    (ROOT / "thesis/generated/cleaning_witness_audit.json").write_text(
        json.dumps(summary, indent=2) + "\n"
    )
    if summary["errors"]:
        raise RuntimeError("Audit incomplete; JSON records failures, TeX unchanged")
    write_tex(summary)
    print(
        "FINAL",
        len(results),
        "processed",
        len(summary["changed"]),
        "changed",
        len(summary["errors"]),
        "errors",
        flush=True,
    )
