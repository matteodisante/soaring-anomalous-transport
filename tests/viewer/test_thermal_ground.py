"""The plane datum is the complete cell's unsmoothed area mean."""

import hashlib
import json

import numpy as np
import pytest
from PIL import Image

from soaring.viewer.thermal_geometry import ThermalCell
from soaring.viewer.thermal_ground import mean_terrain, terrain_reference


def test_mean_uses_whole_cell_without_the_crest_buffer():
    z = np.full((240, 240), 8000.0)
    z[20:220, 20:220] = np.arange(200)[None, :] + 100
    actual = mean_terrain(z, (-500, -500, 5500, 5500), (0, 0, 5000, 5000))
    assert actual["mean_m"] == pytest.approx(199.5)
    assert actual["samples"] == 40000
    assert actual["grid_m"] == [25, 25]
    assert actual["coverage_fraction"] == 1


def test_partial_pixels_are_area_weighted_and_rows_run_north_to_south():
    # The selected rectangle includes 25 m of the left pixel, 5 m of the right,
    # and only the northern row: (100*25 + 400*5) / 30 = 150.
    actual = mean_terrain([[100, 400], [800, 900]], (0, 0, 50, 50), (0, 25, 30, 50))
    assert actual["mean_m"] == 150


@pytest.mark.parametrize("bad", [np.nan, np.inf, -99999])
def test_missing_inside_cell_is_an_error_but_buffer_is_excluded(bad):
    z = np.full((240, 240), bad)
    z[20:220, 20:220] = 200
    assert (
        mean_terrain(z, (-500, -500, 5500, 5500), (0, 0, 5000, 5000))["mean_m"] == 200
    )
    z[100, 100] = bad
    with pytest.raises(ValueError, match="Missing or invalid"):
        mean_terrain(z, (-500, -500, 5500, 5500), (0, 0, 5000, 5000))


def test_incomplete_or_coarse_terrain_is_rejected():
    with pytest.raises(ValueError, match="complete cell"):
        mean_terrain(np.ones((200, 200)), (0, 0, 5000, 5000), (0, 0, 5001, 5000))
    with pytest.raises(ValueError, match="25 m or finer"):
        mean_terrain(np.ones((100, 100)), (0, 0, 5000, 5000), (0, 0, 5000, 5000))


def test_local_reference_preserves_api_query_and_checks_hash(tmp_path):
    cell = ThermalCell(0, 0, "Plains", 1, 1, 900, 2000)
    raster = tmp_path / "ign-terrain-0-0.tif"
    Image.fromarray(np.full((200, 200), 123.5, dtype=np.float32)).save(raster)
    provenance = {
        "bounds_epsg2154": cell.bounds,
        "raster_bounds_epsg2154": cell.bounds,
        "terrain_file": raster.name,
        "response_sha256": hashlib.sha256(raster.read_bytes()).hexdigest(),
        "source_url": "https://data.geopf.fr/wms-r/wms?REQUEST=GetMap",
        "dataset_url": "https://www.data.gouv.fr/datasets/rge-alti-r",
        "retrieved_utc": "2026-09-22",
    }
    (tmp_path / "ign-ridges-0-0.geojson").write_text(
        json.dumps({"provenance": provenance})
    )
    reference = terrain_reference(cell, tmp_path)
    assert reference["mean_m"] == 123.5
    assert reference["source_url"] == provenance["source_url"]
    raster.write_bytes(raster.read_bytes() + b"tampered")
    with pytest.raises(ValueError, match="hash"):
        terrain_reference(cell, tmp_path)
