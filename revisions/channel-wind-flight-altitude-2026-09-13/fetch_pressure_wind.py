"""Archive just the ERA5 pressure-level series needed for coastal flight heights.

Use an isolated environment with icechunk, xarray, zarr and numcodecs[pcodec].
The public
repository snapshot is pinned; exact extracted float32 values are saved losslessly.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import UTC, datetime
from importlib.metadata import version
from pathlib import Path

HERE = Path(__file__).resolve().parent
SNAPSHOT = "TGSHKBHQ8D687WS6STMG"
LEVELS = [1000, 925, 850, 700]


def digest(path):
    """Identify exact saved input bytes."""
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    """Download the compact selection once, or verify the frozen selection."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=HERE)
    args = parser.parse_args()
    out = args.output.resolve()
    out.mkdir(parents=True, exist_ok=True)
    manifest_path = out / "pressure-input-manifest.json"
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text())
        for name, expected in manifest["files_sha256"].items():
            assert digest(out / name) == expected, name
        print("Verified frozen ERA5 pressure-level archive; no network request")
        return
    import icechunk
    import numpy as np
    import xarray as xr

    latitudes = np.repeat([48.75, 49.75, 50.75], 3)
    longitudes = np.tile([-1.25, 0, 1.25], 3)
    storage = icechunk.s3_storage(
        bucket="earthmover-icechunk-era5",
        prefix="icechunkV2",
        region="us-east-1",
        anonymous=True,
    )
    config = icechunk.RepositoryConfig(
        max_concurrent_requests=8,
        caching=icechunk.CachingConfig(num_bytes_chunks=128 * 1024**2),
        storage=icechunk.StorageSettings(
            timeouts=icechunk.StorageTimeoutSettings(
                connect_timeout_ms=20000,
                read_timeout_ms=60000,
                operation_timeout_ms=120000,
            ),
            retries=icechunk.StorageRetriesSettings(max_tries=3),
        ),
        manifest=icechunk.ManifestConfig(
            preload=icechunk.ManifestPreloadConfig(max_total_refs=0)
        ),
    )
    repo = icechunk.Repository.open(storage, config=config)
    session = repo.readonly_session(snapshot_id=SNAPSHOT)
    ds = xr.open_zarr(
        session.store, group="pressure/temporal", consolidated=False, chunks=None
    )
    print("Opened pinned pressure-level store", SNAPSHOT, flush=True)
    coords = {
        "latitude": xr.DataArray(latitudes, dims="cell"),
        "longitude": xr.DataArray(longitudes % 360, dims="cell"),
    }
    selected = ds[["u", "v", "z"]].sel(
        **coords,
        pressure_level=LEVELS,
        valid_time=slice("2016-01-01", "2025-12-31T23:00:00"),
    )
    time = selected.valid_time.values.astype("datetime64[h]")
    assert len(time) == 87672
    payload = {
        "time_hours_since_epoch": time.astype("int64"),
        "pressure_hpa": np.array(LEVELS, dtype="int32"),
        "latitude": latitudes,
        "longitude": longitudes,
    }
    attrs = {}
    for name in ("u", "v", "z"):
        payload[name] = (
            selected[name].transpose("cell", "valid_time", "pressure_level").values
        )
        assert payload[name].shape == (9, 87672, 4)
        assert np.isfinite(payload[name]).all()
        attrs[name] = dict(ds[name].attrs)
        print("Retrieved", name, payload[name].shape, flush=True)
    surface = ds["z_sfc"].sel(**coords).values
    payload["surface_geopotential"] = surface
    attrs["z_sfc"] = dict(ds["z_sfc"].attrs)
    np.savez_compressed(out / "pressure-wind.npz", **payload)
    manifest = {
        "source": (
            "Copernicus/ECMWF ERA5 pressure-level data via public "
            "Earthmover Icechunk archive"
        ),
        "source_url": "https://registry.opendata.aws/earthmover-era5/",
        "era5_doi": "10.24381/cds.bd0915c6",
        "licence": "CC-BY-4.0",
        "bucket": "earthmover-icechunk-era5",
        "prefix": "icechunkV2",
        "group": "pressure/temporal",
        "snapshot_id": SNAPSHOT,
        "period": ["2016-01-01T00:00", "2025-12-31T23:00"],
        "pressure_levels_hpa": LEVELS,
        "latitude": latitudes.tolist(),
        "longitude": longitudes.tolist(),
        "variables": attrs,
        "retrieved_utc": datetime.now(UTC).isoformat(),
        "operation": (
            "Exact coordinate selection; lossless NumPy archive of float32 values; "
            "no spatial or temporal averaging"
        ),
        "packages": {
            name: version(name)
            for name in ("icechunk", "xarray", "zarr", "numcodecs", "numpy")
        },
        "files_sha256": {"pressure-wind.npz": digest(out / "pressure-wind.npz")},
    }
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
    print("Archived bytes", (out / "pressure-wind.npz").stat().st_size, flush=True)


if __name__ == "__main__":
    main()
