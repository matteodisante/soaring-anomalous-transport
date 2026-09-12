"""Independently aggregate all segment curves and spot-check native displacements."""

from __future__ import annotations

import gzip
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow.parquet as pq

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent


def digest(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def main():
    raw = gzip.decompress((HERE / "report.json.gz").read_bytes())
    report = json.loads(raw)
    assert report["status"] == "complete"
    for path, expected in report["inputs"].items():
        assert digest(path) == expected["sha256"], path
    for path, expected in report["sources"].items():
        assert digest(ROOT / path) == expected, path
    checked = {}
    for discipline, entry in report["results"].items():
        slug = "para" if discipline == "paragliders" else "hang"
        paths = {Path(p).name: Path(p) for p in report["inputs"] if
                 f"msd_{slug}.npz" in p or f"msd_segments_{slug}.parquet" in p
                 or (f"/{discipline.replace(' ', '_')}/" in p and p.endswith("flights_meta.parquet"))}
        # Locate metadata by the archive directory rather than presentation labels.
        metadata_path = next(Path(p) for p in report["inputs"] if p.endswith("flights_meta.parquet")
                             and ("/paragliders/" in p if slug == "para" else "/hang_gliders/" in p))
        segments = pd.read_parquet(paths[f"msd_segments_{slug}.parquet"])
        lags = np.asarray(entry["lags_s"])
        with np.load(paths[f"msd_{slug}.npz"]) as archive:
            mask = np.isin(archive["lags"], lags)
            samples = archive["time_averaged_samples"][:, mask].astype(float)
        eligible = (segments.dt_s.to_numpy() > 0) & (segments.dt_s.to_numpy() <= 10)
        seg = segments.loc[eligible].reset_index(drop=True)
        curves = samples[eligible]
        ids, codes = np.unique(seg.flight_id.astype(str), return_inverse=True)
        records = pd.DataFrame(entry["flights"]).set_index("flight_id").loc[ids]
        assert len(ids) == entry["n_flights"] == len(entry["flights"])
        meta = pd.read_parquet(metadata_path).assign(flight_id=lambda f: f.flight_id.astype(str)).set_index("flight_id").loc[ids]
        assert meta.drop_reason.isna().all()
        np.testing.assert_allclose(records.alt0, meta.alt0, rtol=0, atol=0)
        altitude = np.select([meta.alt0 < 300, meta.alt0 < 800, meta.alt0 < 1500, meta.alt0 >= 1500],
                             ["Plains", "Hills", "Low mountains", "High mountains"], default="")
        np.testing.assert_array_equal(records.altitude_band, altitude)
        for name, (xmin, ymin, xmax, ymax) in report["contract"]["regions"].items():
            hit = meta.lon0.between(xmin, xmax) & meta.lat0.between(ymin, ymax)
            np.testing.assert_array_equal(records.region.eq(name), hit)
        reconstructed = np.full((len(ids), 2, len(lags)), np.nan)
        fixed = np.isfinite(curves[:, -1])
        for control in (0, 1):
            selected = np.ones(len(seg), dtype=bool) if control == 0 else fixed
            for j, lag in enumerate(lags):
                steps = np.rint(lag / seg.dt_s.to_numpy())
                good = selected & np.isfinite(curves[:, j])
                w = seg.n_fixes.to_numpy()[good] - steps[good]
                numerator = np.bincount(codes[good], weights=w * curves[good, j], minlength=len(ids))
                denominator = np.bincount(codes[good], weights=w, minlength=len(ids))
                reconstructed[:, control, j] = np.divide(numerator, denominator,
                    out=np.full(len(ids), np.nan), where=denominator > 0)
        cells = 0
        for category in ("region", "altitude_band"):
            for name, row in entry[category].items():
                subset = reconstructed[records[category].eq(name)]
                count = np.isfinite(subset).sum(axis=0)
                mean = np.divide(np.nansum(subset, axis=0), count,
                                 out=np.full(count.shape, np.nan), where=count > 0)
                np.testing.assert_array_equal(count, row["n_flights"])
                np.testing.assert_allclose(mean, np.asarray(row["mean_m2"], dtype=float), rtol=1e-12, equal_nan=True)
                assert (count[1] == count[1, 0]).all()
                expected_fixed = set(records.index[records[category].eq(name) & np.isfinite(reconstructed[:, 1, -1])])
                assert expected_fixed == set(row["fixed_flight_ids"])
                cells += count.size
        for row in entry["region_altitude"]:
            subset = reconstructed[records.region.eq(row["region"]) & records.altitude_band.eq(row["altitude_band"])]
            count = np.isfinite(subset).sum(axis=0)
            mean = np.divide(np.nansum(subset, axis=0), count,
                             out=np.full(count.shape, np.nan), where=count > 0)
            np.testing.assert_array_equal(count, row["n_flights"])
            np.testing.assert_allclose(mean, np.asarray(row["mean_m2"], dtype=float), rtol=1e-12, equal_nan=True)
            cells += count.size
        # Complete segments wholly inside three widely separated Parquet groups.
        fix_path = metadata_path.with_name("fixes.parquet")
        parquet = pq.ParquetFile(fix_path)
        lookup = {(str(r.flight_id), int(r.segment_id)): i for i, r in seg.iterrows()}
        direct, maximum_relative = 0, 0.
        for group in sorted({0, parquet.metadata.num_row_groups // 2, parquet.metadata.num_row_groups - 1}):
            data = parquet.read_row_group(group, columns=["flight_id", "segment_id", "t", "E", "N"]).to_pandas()
            candidates = list(data.groupby(["flight_id", "segment_id"], sort=False))
            good = [(key, frame) for key, frame in candidates if (str(key[0]), int(key[1])) in lookup
                    and len(frame) == seg.iloc[lookup[(str(key[0]), int(key[1]))]].n_fixes]
            for key, frame in [good[i] for i in np.linspace(0, len(good)-1, min(6, len(good)), dtype=int)]:
                index = lookup[(str(key[0]), int(key[1]))]
                frame = frame.sort_values("t")
                xy = frame[["E", "N"]].to_numpy(dtype=float)
                step = float(seg.iloc[index].dt_s)
                for target in (10, 100, 1000, 10000):
                    j = int(np.argmin(abs(lags-target)))
                    if not np.isfinite(curves[index, j]):
                        continue
                    k = int(np.rint(lags[j]/step))
                    result = np.mean(np.sum((xy[k:]-xy[:-k])**2, axis=1))
                    np.testing.assert_allclose(curves[index, j], result, rtol=2e-6, atol=1e-3)
                    maximum_relative = max(maximum_relative, abs(curves[index,j]-result)/max(result, 1e-20))
                    direct += 1
        checked[discipline] = {"flight_identities": len(ids), "group_control_lag_cells": cells,
                               "direct_native_stencil_checks": direct, "maximum_relative_stencil_difference": maximum_relative,
                               "fixes_file": str(fix_path), "fixes_bytes": fix_path.stat().st_size,
                               "fixes_row_groups": parquet.metadata.num_row_groups}
        print(discipline, checked[discipline], flush=True)
    (HERE / "numerical-audit.json").write_text(json.dumps({"status": "complete",
        "report_sha256": hashlib.sha256(raw).hexdigest(), "checks": checked}, indent=2) + "\n")


if __name__ == "__main__":
    main()
