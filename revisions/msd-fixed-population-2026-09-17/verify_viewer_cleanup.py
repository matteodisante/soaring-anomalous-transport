"""Read-only real-SSD verification, runnable before and after cache retirement."""
from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import sys
from pathlib import Path

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'src'))
HERE = Path(__file__).resolve().parent
candidates = {
    p['path'] for p in json.loads((HERE / 'SSD-PULIZIA-PREVENTIVO.json').read_text())['candidate_files']
}
opened = set()


def guard(event, args):
    """Prove viewer operations do not open any cache scheduled for deletion."""
    if event != 'open' or not isinstance(args[0], (str, bytes, os.PathLike)):
        return
    name = os.fsdecode(args[0])
    if '/Volumes/SSD_DISANTE/' not in name and '/recovery-runs/' not in name:
        return
    resolved = str(Path(name).resolve())
    if resolved in candidates:
        raise RuntimeError('Viewer tried to read a retired cache: ' + resolved)
    opened.add(resolved)


sys.addaudithook(guard)
import numpy as np
import pandas as pd
from soaring.reporting.disciplines import DISCIPLINES
from soaring.viewer import catalog_index, data, geography
from soaring.viewer.thermal_daily import local_bounds
from soaring.viewer.thermal_store import load_store


def frame_digest(frame):
    return hashlib.sha256(pd.util.hash_pandas_object(frame, index=True).values.tobytes()).hexdigest()


def file_digest(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


result = {'catalogs': {}, 'flights': {}, 'thermal': {}, 'gui': {}}
paths = {}
for name, discipline in DISCIPLINES.items():
    catalog = catalog_index.filter_flights(discipline)
    kept = catalog_index.filter_flights(discipline, kept_only=True)
    points = catalog_index.takeoff_points(discipline)
    dropdowns = {
        column: hashlib.sha256(json.dumps(catalog_index.distinct_values(discipline, column)).encode()).hexdigest()
        for column in ('dept', 'flight_type', 'wing_class', 'takeoff', 'landing', 'club', 'wing', 'pilot')
    }
    result['catalogs'][name] = {
        'all': len(catalog), 'kept': len(kept), 'map_points': len(points),
        'catalog_hash': frame_digest(catalog), 'map_hash': frame_digest(points),
        'dropdowns': dropdowns,
        'terrain_counts': kept.terrain.value_counts().to_dict(),
        'region_counts': kept.region.value_counts().to_dict(),
    }
    ids = ['20040462', '20290038', '20399347', '20010413'] if discipline.slug == 'para' else ['1748', '20329142', '3336', '1037']
    for fid in ids:
        row = catalog.loc[catalog.flight_id.eq(fid)].iloc[0]
        path = catalog_index.resolve_igc_path(discipline, row)
        assert path and path.is_file(), (name, fid)
        raw = data.load_raw(path)
        cleaned = data.load_cleaned(path, source=discipline.source, flight_id=fid, discipline=name)
        assert cleaned.kept, (name, fid, cleaned.meta)
        own = data.load_flight_phases(cleaned.fixes, discipline)
        vilpellet = data.load_vilpellet_phases(cleaned.fixes, discipline)
        assert own is not None and vilpellet is not None
        result['flights'][name + '/' + fid] = {
            'raw_fixes': len(raw.fixes), 'cleaned_fixes': len(cleaned.fixes),
            'raw': frame_digest(raw.fixes), 'cleaned': frame_digest(cleaned.fixes),
            'hmm': frame_digest(own.fixes), 'vilpellet': frame_digest(vilpellet.fixes),
            'hmm_counts': own.fixes.phase.value_counts().to_dict(),
            'vilpellet_counts': vilpellet.fixes.phase.value_counts().to_dict(),
        }
        paths[name] = paths.get(name, (path, fid))
    print(name + ': catalog, map, filters and 4 flights OK', flush=True)
assert geography.load_basemap()

store = load_store()
assert store is not None and store.has_points
cells = store.cells()
assert len(cells) == 12
result['thermal']['store'] = str(store.path)
result['thermal']['sha256'] = file_digest(store.path)
with sqlite3.connect(store.path.resolve().as_uri() + '?mode=ro', uri=True) as db:
    assert db.execute('PRAGMA quick_check').fetchall() == [('ok',)]
    result['thermal']['coverage'] = db.execute('SELECT source,status,COUNT(*) FROM climbs GROUP BY source,status').fetchall()
    missing = db.execute('SELECT COUNT(*) FROM climbs c LEFT JOIN plane_points p USING(source,ix,iy,discipline,flight_id) WHERE p.points IS NULL').fetchone()[0]
    assert missing == 0
    result['thermal']['missing_products'] = missing
result['thermal']['extent'] = store.time_extent()
result['thermal']['images'] = {}
for cell in [None, *cells]:
    key = 'france' if cell is None else f'{cell.ix}/{cell.iy}'
    for kind in ('relief', 'colour', 'aerial'):
        image, meta = store.background(cell, kind=kind)
        result['thermal']['images'][key + '/' + kind] = {
            'shape': image.shape, 'sha256': hashlib.sha256(image.tobytes()).hexdigest(), 'metadata': meta,
        }
result['thermal']['cells'] = []
for cell in cells:
    days = store.summer_days(cell)
    assert days
    start, end = local_bounds(days[0][0])
    row = {'cell': [cell.ix, cell.iy], 'flights': cell.flights, 'days': days,
           'defaults': store.defaults(cell), 'reference_audit': store.reference_audit(cell), 'methods': {}}
    for source in ('own', 'vilpellet'):
        plane = store.read_plane(cell, start, end - 1, source)
        assert plane.selected and plane.points is not None
        assert plane.unavailable == 0
        row['methods'][source] = {
            'selected': plane.selected, 'unclassified': plane.unclassified,
            'points': len(plane.points), 'digest': frame_digest(plane.points),
            'periods': [int(((plane.points.utc >= a) & (plane.points.utc < b)).sum())
                        for a, b in (local_bounds(days[0][0], h) for h in ((8,11),(11,15),(15,18)))],
        }
    result['thermal']['cells'].append(row)
print('12 cells, 24 method/day selections, 39 backgrounds and database integrity OK', flush=True)

from PyQt6.QtWidgets import QApplication
from soaring.viewer.main_window import MainWindow
from soaring.viewer.plotting import save_pdf
app = QApplication.instance() or QApplication([])
window = MainWindow()
window.show()
app.processEvents()
for name, (path, fid) in paths.items():
    window._on_flight_chosen(path, DISCIPLINES[name], fid)
    assert window._raw is not None and window._cleaned.kept
    assert window._phases is not None and window._vilpellet_phases is not None
    controls = window._controls
    panels = []
    for frame_index in (0, 1):
        controls._frame_combo.setCurrentIndex(frame_index)
        for mode in (0, 1, 2):
            controls._segmentation_combo.setCurrentIndex(mode)
            for three_d in (False, True):
                controls._chk_3d.setChecked(three_d)
                app.processEvents()
                panels.append(len(window._figure.axes))
    controls._chk_climb_only.setChecked(True)
    controls._chk_dms.setChecked(True)
    controls._slider_zoom.setValue(130)
    controls._btn_reset_view.click()
    target = Path('/tmp') / ('ssd-viewer-' + DISCIPLINES[name].slug + '.pdf')
    save_pdf(window._figure, target)
    assert target.stat().st_size > 1000
    result['gui'][name] = {'panel_counts': panels, 'pdf_export': True}
window.close()
app.processEvents()
result['opened_ssd_files'] = sorted(opened)
result['viewer_code'] = {str(p.relative_to(ROOT)): file_digest(p) for p in sorted((ROOT / 'src/soaring/viewer').rglob('*.py'))}
output = Path(sys.argv[1])
output.write_text(json.dumps(result, indent=2, default=lambda x: x.item()) + '\n')
print('Real-data GUI 2D/3D, frames, segmentations, comparison, climb filter and PDF export OK', flush=True)
