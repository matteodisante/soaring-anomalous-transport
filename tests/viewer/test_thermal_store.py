"""The delivered file works alone and the actual Qt worker loads it end to end."""

import io
import json
import sqlite3
import time
from dataclasses import asdict

import numpy as np
import pytest

from soaring.viewer.thermal_geometry import ThermalCell
from soaring.viewer.thermal_store import ThermalStore, load_store


@pytest.fixture
def store(tmp_path):
    cell = ThermalCell(193, 1304, "Plains", 2, 1, 260, 2000)
    west, south, _, _ = cell.bounds
    blob = io.BytesIO()
    np.savez_compressed(
        blob,
        edges=np.array(
            [[west + 100, south + 100, 400, 100, west + 200, south + 200, 800, 200.0]]
        ),
    )
    path = tmp_path / "thermal-planes.sqlite3"
    with sqlite3.connect(path) as db:
        db.executescript("""
        CREATE TABLE metadata(key TEXT,value TEXT);
        CREATE TABLE cells(position INTEGER,ix INTEGER,iy INTEGER,
                payload TEXT,day REAL,height REAL);
        CREATE TABLE visitors(ix INTEGER,iy INTEGER,discipline TEXT,flight_id TEXT,
                start REAL,end REAL);
        CREATE TABLE climbs(source TEXT,discipline TEXT,flight_id TEXT,
                ix INTEGER,iy INTEGER,
                status TEXT,edges BLOB);
        """)
        db.executemany(
            "INSERT INTO metadata VALUES (?,?)",
            [("ready", "1"), ("version", "1"), ("disciplines", '["paragliders"]')],
        )
        db.execute(
            "INSERT INTO cells VALUES (0,?,?,?,?,?)",
            (cell.ix, cell.iy, json.dumps(asdict(cell)), 0, 340),
        )
        db.execute(
            "INSERT INTO visitors VALUES (?,?,?,?,?,?)",
            (cell.ix, cell.iy, "paragliders", "a", 100, 200),
        )
        db.execute(
            "INSERT INTO visitors VALUES (?,?,?,?,NULL,NULL)",
            (cell.ix, cell.iy, "paragliders", "unknown"),
        )
        for source in ("own", "vilpellet"):
            db.execute(
                "INSERT INTO climbs VALUES (?,?,?,?,?,?,?)",
                (
                    source,
                    "paragliders",
                    "a",
                    cell.ix,
                    cell.iy,
                    "decoded",
                    blob.getvalue(),
                ),
            )
    path.chmod(0o444)
    return ThermalStore(path)


def test_standalone_read_only_file_needs_no_archive_or_model(store, monkeypatch):
    monkeypatch.setenv("SOARING_VIEWER_CACHE_DIR", str(store.path.parent))
    before = store.path.stat().st_mtime_ns
    loaded = load_store()
    cell = loaded.cells()[0]
    for source in ("own", "vilpellet"):
        result = loaded.read_plane(cell, 125, 175, source)
        assert result.cached == result.decoded == result.selected == 1
        assert result.unknown_clock == 1
        assert len(result.edges) == 1
        assert loaded.read_plane(cell, 300, 400, source).edges.empty
    assert store.path.stat().st_mtime_ns == before
    assert {p.name for p in store.path.parent.iterdir()} == {"thermal-planes.sqlite3"}


def test_real_worker_auto_load_and_reload_button(qapp, store, monkeypatch):
    from soaring.viewer.widgets.thermal_plane import ThermalPlane

    monkeypatch.setenv("SOARING_VIEWER_CACHE_DIR", str(store.path.parent))
    view = ThermalPlane()

    def drain():
        deadline = time.monotonic() + 10
        while view._worker is not None and time.monotonic() < deadline:
            qapp.processEvents()
            time.sleep(0.01)
        qapp.processEvents()
        assert view._worker is None, view._status.text()
        assert view._plane is not None, view._status.text()
        assert view._load.isEnabled()
        assert len(view._plane_ax.collections) == 1

    try:
        view.ensure_loaded()
        drain()
        assert view._build.text() == "Reload SSD data"
        view._build.click()
        drain()
        view._source.setCurrentIndex(1)
        view._load.click()
        drain()
    finally:
        view.shutdown()
        view.close()


def test_saved_relief_preserves_extent_and_never_uses_network(store, monkeypatch):
    from PIL import Image

    store.path.chmod(0o644)
    pixels = np.array(
        [[[30, 40, 50], [60, 70, 80]], [[90, 100, 110], [120, 130, 140]]],
        dtype=np.uint8,
    )
    output = io.BytesIO()
    Image.fromarray(pixels).save(output, format="PNG")
    cell = store.cells()[0]
    info = {"extent": cell.bounds, "epsg": 2154}
    with sqlite3.connect(store.path) as db:
        db.execute("CREATE TABLE relief(key TEXT,metadata TEXT,png BLOB)")
        db.execute(
            "INSERT INTO relief VALUES (?,?,?)",
            (f"{cell.ix}/{cell.iy}", json.dumps(info), output.getvalue()),
        )
    store.path.chmod(0o444)
    monkeypatch.setattr(
        "urllib.request.urlopen", lambda *a, **k: pytest.fail("network")
    )
    actual, metadata = store.relief(cell)
    np.testing.assert_array_equal(actual, pixels)
    assert metadata["extent"] == list(cell.bounds)
    assert metadata["epsg"] == 2154
    assert store.relief() is None


def test_prepared_points_read_without_geometry_and_resume(store, monkeypatch):
    from soaring.viewer.thermal_daily import prepare_daily

    store.path.chmod(0o644)
    prepare_daily(store.path, progress=lambda _: None)
    prepared = ThermalStore(store.path)
    assert prepared.has_points
    cell = prepared.cells()[0]
    before = store.path.stat().st_size
    prepare_daily(store.path, progress=lambda _: None)
    assert store.path.stat().st_size == before
    store.path.chmod(0o444)
    monkeypatch.setattr(
        "soaring.viewer.thermal_geometry.plane_intersections",
        lambda *a, **k: pytest.fail("runtime intersection calculation"),
    )
    for source in ("own", "vilpellet"):
        data = prepared.read_plane(cell, 125, 175, source)
        assert data.edges.empty
        assert data.points is not None
        assert data.points.utc.between(125, 175).all()
        # z=340 AGL means 600 ASL, halfway along the original native edge.
        point = data.points.loc[data.points.level == 34].iloc[0]
        assert point.x == cell.bounds[0] + 150
        assert point.y == cell.bounds[1] + 150
        assert point.utc == 150
        assert data.selected == 1


def test_saved_aerial_dates_and_pixels(store, monkeypatch):
    from PIL import Image

    store.path.chmod(0o644)
    cell = store.cells()[0]
    image = io.BytesIO()
    Image.new("RGB", (4, 4), (20, 40, 60)).save(image, format="PNG")
    dates = ["2022-06-12", "2023-08-01"]
    with sqlite3.connect(store.path) as db:
        db.execute(
            "CREATE TABLE backgrounds(kind TEXT,key TEXT,metadata TEXT,image BLOB)"
        )
        db.execute(
            "INSERT INTO backgrounds VALUES (?,?,?,?)",
            (
                "aerial",
                f"{cell.ix}/{cell.iy}",
                json.dumps({"extent": cell.bounds, "acquisition_dates": dates}),
                image.getvalue(),
            ),
        )
    monkeypatch.setattr(
        "urllib.request.urlopen", lambda *a, **k: pytest.fail("network")
    )
    pixels, metadata = store.background(cell, "aerial")
    assert pixels[0, 0].tolist() == [20, 40, 60]
    assert metadata["acquisition_dates"] == dates
