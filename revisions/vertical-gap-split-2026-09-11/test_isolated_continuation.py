"""Fault injection for the bounded non-analysis source reconciliation."""
from pathlib import Path
import runpy

import pytest


@pytest.fixture
def checker(tmp_path):
    path = Path(__file__).with_name('continue_isolated_rebuild.py')
    module = runpy.run_path(str(path))
    check = module['viewer_difference_proof']
    original = tmp_path/'frozen'
    working = tmp_path/'working'
    sources = {
        'src/soaring/viewer/geography.py':
            'FRANCE_EXTENT = (1, 2, 3, 4)\nLAND = "tan"\n'
            'def draw_land():\n    return LAND\n'
            'def load_basemap():\n    return FRANCE_EXTENT\n',
        'src/soaring/viewer/catalog_index.py': 'VALUE = 1\n',
        'src/soaring/analysis/observable.py': 'VALUE = 1\n',
        'scripts/reporting/ch2_dataset/generate_terrain_figure.py':
            'from soaring.viewer.geography import FRANCE_EXTENT, draw_land, load_basemap\n',
        'thesis/main.tex': '', 'thesis/references.bib': '', 'uv.lock': '',
    }
    for root in (original, working):
        for name, value in sources.items():
            path = root/name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(value)
    check.__globals__['WORK'] = working
    check.__globals__['FROZEN'] = original
    return check, working


def test_identical_sources_pass(checker):
    check, _ = checker
    assert check()['differences'] == {}


def test_unused_viewer_additions_pass(checker):
    check, work = checker
    path = work/'src/soaring/viewer/geography.py'
    path.write_text(path.read_text()+'REGIONS = {}\ndef classify_region(lat, lon):\n    return lat\n')
    (work/'src/soaring/viewer/catalog_index.py').write_text('VALUE = 2\n')
    assert len(check()['differences']) == 2


def test_changed_analysis_refused(checker):
    check, work = checker
    (work/'src/soaring/analysis/observable.py').write_text('VALUE = 2\n')
    with pytest.raises(ValueError, match='Non-viewer source changed'):
        check()


def test_changed_shared_geography_refused(checker):
    check, work = checker
    path = work/'src/soaring/viewer/geography.py'
    path.write_text(path.read_text().replace('return LAND', 'return "blue"'))
    with pytest.raises(ValueError, match='Existing geography definitions changed'):
        check()


def test_shadowing_existing_global_refused(checker):
    check, work = checker
    path = work/'src/soaring/viewer/geography.py'
    path.write_text(path.read_text()+'LAND = "blue"\n')
    with pytest.raises(ValueError, match='Unexpected new geography binding'):
        check()


def test_new_guarded_file_refused(checker):
    check, work = checker
    (work/'src/soaring/analysis/added.py').write_text('VALUE = 2\n')
    with pytest.raises(ValueError, match='Guarded source file sets differ'):
        check()
