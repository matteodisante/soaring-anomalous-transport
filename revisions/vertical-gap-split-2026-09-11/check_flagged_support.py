"""Compare flagged grid runs with actual finite-altitude interpolation support."""
import json
from pathlib import Path
import numpy as np
from soaring.analysis.config import load_preproc_config
from soaring.analysis.igc import parse_igc
from soaring.analysis.preproc import pipeline

paths = [
'/Volumes/SSD_DISANTE/paragliders/ffvl_cfd_igc/raw/igc/2005-2006/2006-07-20_20051967.igc',
'/Volumes/SSD_DISANTE/paragliders/ffvl_cfd_igc/raw/igc/2011-2012/2012-08-03_20120143.igc',
'/Volumes/SSD_DISANTE/paragliders/ffvl_cfd_igc/raw/igc/2012-2013/2013-04-16_20125152.igc',
'/Volumes/SSD_DISANTE/paragliders/ffvl_cfd_igc/raw/igc/2021-2022/2022-05-10_20320588.igc',
]
original = pipeline.resample_flight
captured = {}
def capture(local, *args, **kwargs):
    captured['local'] = local.copy()
    return original(local, *args, **kwargs)
pipeline.resample_flight = capture
records = []
for path in paths:
    fid = Path(path).stem.split('_')[-1]
    result = pipeline.run_flight(parse_igc(path), load_preproc_config(), source='ffvl_cfd', flight_id=fid, discipline='paragliders')
    local = captured['local']
    finite = local.loc[np.isfinite(local.z), 't'].to_numpy()
    grid = result.fixes.t.to_numpy()
    index = np.searchsorted(finite, grid)
    assert np.all(index < len(finite))
    right = finite[index]
    left = finite[np.maximum(index-1, 0)]
    spans = np.where(right == grid, 0, right-left)
    assert np.all(spans <= result.meta.g_max_s + 1e-7)
    record = {'flight_id': fid, 'g_max_s': result.meta.g_max_s,
              'z_flag_run_s': result.meta.z_gap_max_s,
              'max_interpolation_support_s': float(spans.max()),
              'supported_grid_points': len(grid), 'true_support_violations': 0}
    records.append(record)
print(json.dumps(records, indent=2))
Path(__file__).with_name('flagged-support-audit.json').write_text(json.dumps(records, indent=2)+'\n')
