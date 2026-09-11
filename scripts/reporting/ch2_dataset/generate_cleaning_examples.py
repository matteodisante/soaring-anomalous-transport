#!/usr/bin/env python3
"""Extract reproducible, short raw-data examples of each cleaning defect class.

Select the first qualifying archived paraglider flight per class and rerun cleaning.
and store only the plotted window with its source identity. Examples show detector
behaviour, not independently labelled sensor errors or classification accuracy.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import matplotlib
import numpy as np
import pandas as pd

matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[3]
# Static output contract for the provenance checker; paths may be built dynamically.
GENERATED_OUTPUTS = (
    "cleaning_real_examples.pdf",
    "cleaning_real_examples.json",
)

sys.path.insert(0, str(ROOT / "src"))
from soaring.analysis.config import load_preproc_config  # noqa: E402
from soaring.analysis.igc import parse_igc  # noqa: E402
from soaring.analysis.preproc.altchannel import adopt_alt_channel  # noqa: E402
from soaring.analysis.preproc.cleaning import clean_flight  # noqa: E402
from soaring.reporting import DISCIPLINES  # noqa: E402
from soaring.reporting.style import paper_style


def main():
    """Select archive examples and write their plotted values beside the PDF."""
    paper_style()
    g = DISCIPLINES["paragliders"]
    derived = g.derived_dir("flights_meta.parquet")
    meta = pd.read_parquet(derived / "flights_meta.parquet")
    cat = pd.read_csv(g.catalog_path(), usecols=["flight_id", "local_path"], dtype=str)
    paths = cat.set_index("flight_id").local_path.to_dict()
    cfg = load_preproc_config()
    classes = [
        ("n_removed_spike", "position_spike", "east [m]"),
        ("n_removed_frozen", "frozen_lock_run", "east [m]"),
        ("n_alt_vz_spike", None, "GNSS altitude [m]"),
    ]
    examples = []
    fig, axes = plt.subplots(3, 1, figsize=(6.1, 7.0), constrained_layout=True)
    for ax, (column, reason, ylabel) in zip(axes, classes, strict=True):
        eligible = meta.drop_reason.isna() & (meta[column] > 0)
        if reason == "frozen_lock_run":
            eligible &= meta.dt_native_s.le(5)
        candidates = meta.loc[eligible].head(400)
        found = False
        for r in candidates.itertuples():
            original = paths.get(str(r.flight_id), "")
            if "/igc/" not in original:
                continue
            path = g.config().igc_dir / original.split("/igc/", 1)[1]
            if not path.is_file():
                continue
            raw = parse_igc(path)
            work, ch = adopt_alt_channel(raw, cfg.alt_channel)
            result = clean_flight(
                work, cfg.fix, discipline="paragliders", baro_witness=ch.baro_witness
            )
            if reason:
                affected = result.removed.loc[
                    result.removed.reason == reason, "t"
                ].to_numpy()
            else:
                affected = result.fixes.loc[
                    result.fixes.alt_invalidated, "t"
                ].to_numpy()
            # Inspect airborne interiors; parked recorders are not flight defects.
            affected = affected[
                (affected > r.ground_phase_start_s + 90)
                & (affected < r.ground_phase_end_s - 90)
            ]
            if not len(affected):
                continue
            centre = float(affected[0])
            end = centre
            if reason == "frozen_lock_run":
                cadence = float(np.median(np.diff(work.t)))
                if cadence > 5:
                    continue
                groups = np.split(
                    affected, np.flatnonzero(np.diff(affected) > 2 * cadence) + 1
                )
                groups = [
                    v
                    for v in groups
                    if len(v) >= 15 and cfg.fix.frozen_tau_s <= v[-1] - v[0] <= 180
                ]
                if not groups:
                    continue
                centre, end = float(groups[0][0]), float(groups[0][-1])
            window = work[(work.t >= centre - 45) & (work.t <= end + 45)].copy()
            if len(window) < 8:
                continue
            if reason:
                lat0 = window.lat.iloc[0]
                y = (
                    (window.lon - window.lon.iloc[0])
                    * 111320
                    * np.cos(np.deg2rad(lat0))
                )
                if reason == "position_spike":
                    north = (window.lat - window.lat.iloc[0]) * 111320
                    location = int(np.flatnonzero(window.t.to_numpy() == centre)[0])
                    xy = np.column_stack([y, north])
                    residual = xy[location] - 0.5 * (
                        xy[location - 1] + xy[location + 1]
                    )
                    magnitude = np.linalg.norm(residual)
                    if not 100 <= magnitude <= 2000:
                        continue
                    direction = residual / magnitude
                    y = pd.Series(xy @ direction, index=window.index)
                    ylabel = "along excursion direction [m]"
                marked = window.t.isin(affected)
            else:
                y = window.alt
                marked = window.t.isin(affected)
                # Keep a readable isolated excursion, not a thousands-of-metres failure.
                if y.max() - y.min() > 1200:
                    continue
            xx = window.t - centre
            ax.plot(xx, y, ".-", color="0.65", lw=1, ms=3, label="Raw")
            ax.plot(
                xx[~marked],
                y[~marked],
                ".",
                color="#3477A8",
                ms=4,
                label="Retained",
            )
            ax.plot(
                xx[marked],
                y[marked],
                "x",
                color="#B5482A",
                ms=5,
                label="Removed / invalidated",
            )
            ax.set(xlabel="time relative to first marked fix [s]", ylabel=ylabel)
            title = {
                "position_spike": "Position removed by the speed/rejoin test",
                "frozen_lock_run": "Repeated position interval cut and split",
                None: "Altitude invalidated; horizontal fixes retained",
            }[reason]
            ax.set_title(f"{title}\nFlight {r.flight_id}", loc="left", fontsize=10)
            ax.grid(alpha=0.2)
            ax.legend(loc="best", fontsize=8, frameon=False, ncol=3)
            examples.append(
                {
                    "flight_id": str(r.flight_id),
                    "igc_relative_path": str(path.relative_to(derived.parent)),
                    "rule": reason or "altitude_invalidation",
                    "reference_time_s": centre,
                    "time_s": window.t.tolist(),
                    "displayed_value": y.tolist(),
                    "marked": marked.tolist(),
                }
            )
            found = True
            print(title, r.flight_id, flush=True)
            break
        if not found:
            raise RuntimeError(
                f"No readable airborne example for {column}; no output written"
            )
    out = ROOT / "thesis" / "generated"
    fig.savefig(
        out / "cleaning_real_examples.pdf",
        bbox_inches="tight",
        metadata={
            "Creator": "soaring.analysis",
            "Producer": "soaring.analysis",
            "CreationDate": None,
        },
    )
    fig.savefig("/tmp/cleaning_real_examples.png", dpi=130, bbox_inches="tight")
    (out / "cleaning_real_examples.json").write_text(
        json.dumps(examples, indent=2) + "\n"
    )
    plt.close(fig)


if __name__ == "__main__":
    main()
