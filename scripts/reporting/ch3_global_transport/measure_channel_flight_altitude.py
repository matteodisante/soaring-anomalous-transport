"""Measure coastal altitude on the exact windows supporting the long-lag PCA."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.parquet as pq

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "src"))
from soaring.analysis.observables.segment_support import increment_starts  # noqa: E402
from soaring.analysis.observables.wind_reference import (  # noqa: E402
    window_altitude_means,
)
from soaring.reporting.snapshot import current_cleaning, validate_snapshot  # noqa: E402

GENERATED_OUTPUTS = ("ch3_channel_flight_altitude.json",)
DEFAULT_AUDIT = (
    ROOT
    / "revisions/vertical-gap-split-2026-09-11/recovery-runs"
    / "20260912T104500Z-5cfc4e8c/arrays"
)


def digest(path):
    """Identify the exact source or small input bytes."""
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def main():
    """Read only selected altitude columns, retaining complete flight identities."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--audit-dir", type=Path, default=DEFAULT_AUDIT)
    parser.add_argument(
        "--derived",
        type=Path,
        default=Path("/Volumes/SSD_DISANTE/paragliders/ffvl_cfd_igc/derived"),
    )
    args = parser.parse_args()
    started = time.monotonic()
    snapshot = validate_snapshot(args.derived, current_cleaning(ROOT))
    metadata_path = args.audit_dir / "ch3-full-para/flights.json"
    report_path = ROOT / "thesis/generated/ch3_revision.json"
    report = json.loads(report_path.read_text())
    reference = next(
        r
        for r in report["results"]["paragliders"]["pca"]
        if r["region"] == "Channel Coast" and r["lag_s"] == 10000
    )
    rows = json.loads(metadata_path.read_text())
    coast = {r["flight_id"]: r for r in rows if r["region"] == "Channel Coast"}
    selected = {
        key: r
        for key, r in coast.items()
        if len(increment_starts(r, r["length"], 1000))
    }
    assert len(selected) == reference["n_flights"]
    # Cross-check membership and segment grids against the frozen report itself.
    recorded = {
        r["flight_id"]: r for r in report["provenance"]["paragliders"]["flights"]
    }
    for key, row in selected.items():
        for field in ("region", "segments", "segment_ids", "segment_start_s", "length"):
            assert row[field] == recorded[key][field], (key, field)
    parquet = pq.ParquetFile(args.derived / "fixes.parquet")
    wanted = pa.array(list(selected))
    hits = []
    for i in range(parquet.metadata.num_row_groups):
        ids = parquet.read_row_group(i, columns=["flight_id"])
        mask = pc.is_in(ids["flight_id"], value_set=wanted)
        if pc.any(mask).as_py():
            table = parquet.read_row_group(
                i, columns=["flight_id", "segment_id", "t", "z"]
            )
            hits.append(table.filter(mask))
        if (i + 1) % 400 == 0:
            print("Checked row groups", i + 1, flush=True)
    frame = pa.concat_tables(hits).to_pandas()
    del hits
    means, by_flight = [], []
    for fid, fixes in frame.groupby("flight_id", sort=False):
        values = window_altitude_means(selected[str(fid)], fixes)
        means.extend(values)
        by_flight.append(
            {
                "flight_id": str(fid),
                "window_mean_altitudes_m": values.tolist(),
                "flight_mean_altitude_m": float(values.mean()),
                "n_windows": len(values),
            }
        )
    assert len(by_flight) == len(selected)
    assert len(means) == reference["n_increments"]
    assert validate_snapshot(args.derived, current_cleaning(ROOT)) == snapshot
    sources = [
        Path(__file__),
        ROOT / "src/soaring/analysis/observables/wind_reference.py",
        ROOT / "src/soaring/analysis/observables/segment_support.py",
    ]
    result = {
        "status": "complete",
        "measured_utc": datetime.now(UTC).isoformat(),
        "region": "Channel Coast",
        "discipline": "paragliders",
        "lag_s": 10000,
        "grid_s": 10,
        "n_flights": len(by_flight),
        "n_windows": len(means),
        "mean_altitude_m": float(np.mean(means)),
        "equal_flight_mean_altitude_m": float(
            np.mean([r["flight_mean_altitude_m"] for r in by_flight])
        ),
        "window_mean_quantiles_m": dict(
            zip(
                ["q10", "q25", "q50", "q75", "q90"],
                np.quantile(means, [0.1, 0.25, 0.5, 0.75, 0.9]).tolist(),
                strict=True,
            )
        ),
        "method": (
            "Trapezoidal mean cleaned GNSS altitude z on each exact "
            "10,000-s PCA window, interpolated on the same 10-s segment "
            "grids; equal window weights"
        ),
        "height_datum": (
            "Logged absolute GNSS altitude proxy; interpreted "
            "approximately as height above sea level, without a "
            "harmonised receiver-datum correction; not ENU up or "
            "height above terrain"
        ),
        "flight_report_sha256": digest(report_path),
        "flight_metadata_sha256": digest(metadata_path),
        "cleaning_manifest": snapshot,
        "sources": {str(p.relative_to(ROOT)): digest(p) for p in sources},
        "flights": by_flight,
        "runtime_s": time.monotonic() - started,
    }
    path = ROOT / "thesis/generated/ch3_channel_flight_altitude.json"
    path.write_text(json.dumps(result, indent=2) + "\n")
    print(
        f"Mean altitude {result['mean_altitude_m']:.3f} m; {len(means)} PCA windows",
        flush=True,
    )


if __name__ == "__main__":
    main()
