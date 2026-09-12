"""Isolate the historical PSD selection correction on the current raw sample.

Uses the current decoder and identical Welch estimator for both variants. It does
not recreate every historical environment change or overwrite canonical products.
"""
from __future__ import annotations
import os
for key in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','VECLIB_MAXIMUM_THREADS','NUMEXPR_NUM_THREADS'):
    os.environ[key]='1'
import hashlib
import json
import runpy
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from datetime import UTC, datetime
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'src'))
from soaring.analysis.altitude_noise import (
    BARO_PRESENT_MIN, DT_TOLERANCE_S, NPERSEG, _uniform_resample, _welch,
    longest_regular_block,
)
from soaring.analysis.igc import baro_present_fraction, median_sampling_period, parse_igc
from soaring.reporting import DISCIPLINES


def one(path):
    raw_hash=hashlib.sha256(path.read_bytes()).hexdigest()
    fixes=parse_igc(path)
    base={'path':str(path),'sha256':raw_hash,'old':None,'new':None}
    if len(fixes)<3:return base
    dt=median_sampling_period(fixes)
    base['rounded_cadence']=round(dt) if np.isfinite(dt) and dt>0 else None
    if not (baro_present_fraction(fixes)>=BARO_PRESENT_MIN and np.isfinite(dt)
            and abs(dt-1)<=DT_TOLERANCE_S and len(fixes)>=NPERSEG):return base
    t=fixes['t'].to_numpy()
    old=[_uniform_resample(t,fixes[c].to_numpy(),1) for c in ('baro_alt','gnss_alt')]
    if len(old[0])>=NPERSEG:
        base['old']=np.array([_welch(z,1)[1] for z in old])
    values=fixes[['baro_alt','gnss_alt']].to_numpy(dtype=float,copy=True)
    values[values==0]=np.nan
    values[~fixes['valid'].to_numpy(dtype=bool),1]=np.nan
    t,values=longest_regular_block(t,values,1)
    if len(t)>=NPERSEG:
        new=[_uniform_resample(t,values[:,i],1) for i in range(2)]
        if len(new[0])>=NPERSEG:
            base['new']=np.array([_welch(z,1)[1] for z in new])
    return base


def stats(spectra):
    a=np.asarray(spectra)
    freq=np.fft.rfftfreq(NPERSEG,d=1)
    band=(freq>=.35)&(freq<=.5)
    output={}
    for k,name in enumerate(('baro','gnss')):
        x=a[:,k]
        valid=np.isfinite(x).all(axis=1)
        floors=np.median(x[valid][:,band],axis=1)
        output[name]={'spectra':len(x),'nonfinite_spectra':int((~valid).sum()),
                      'finite_floor_percentiles_10_50_90_99':np.percentile(floors,[10,50,90,99]).tolist(),
                      'per_frequency_10_50_90':np.percentile(x[valid], [10,50,90],axis=0)[:,band].tolist()}
    return output


def main():
    os.nice(10)
    driver=runpy.run_path(str(ROOT/'scripts/rebuild_thesis.py'))
    reporter=runpy.run_path(str(ROOT/'scripts/reporting/ch2_dataset/generate_altitude_noise_figure.py'))
    # The reporter imports this helper inside main; use its defining module.
    from soaring.analysis.altitude_noise import sample_igc_paths
    source=driver['source_hash'](ROOT)
    started=time.monotonic()
    record={'status':'running','started_utc':datetime.now(UTC).isoformat(),
            'parent_run_id':'20260911T213634Z-7b7367f1','source_sha256':source,
            'script_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            'comparison':'Current decoder/1Hz Welch; legacy whole-trace selection versus current paired uninterrupted valid block. Correction introduced in8744a52.',
            'workers':4,'results':{},'input_files':{}}
    path=Path(__file__).with_name('psd-selection-comparison.json')
    path.write_text(json.dumps(record,indent=2)+'\n')
    all_old=[];all_matched=[];all_new=[]
    try:
        for name,g in DISCIPLINES.items():
            paths=sample_igc_paths(g.config().igc_dir,reporter['PSD_SAMPLE_PER_DISCIPLINE'])
            print(f'{name}: comparing both selection rules on {len(paths)} raw files',flush=True)
            with ProcessPoolExecutor(max_workers=4) as pool:
                rows=list(pool.map(one,paths,chunksize=8))
            old=[r['old'] for r in rows if r['old'] is not None]
            chosen=[r for r in rows if r['new'] is not None]
            new=[r['new'] for r in chosen]
            matched=[r['old'] for r in chosen]
            assert all(v is not None for v in matched)
            cache=g.config().derived_dir/'psd_sample.npz'
            with np.load(cache) as d:
                assert float(d['target_dt'])==1
                np.testing.assert_allclose(np.asarray(new)[:,0],d['baro'],rtol=1e-12,atol=0)
                np.testing.assert_allclose(np.asarray(new)[:,1],d['gnss'],rtol=1e-12,atol=0)
            record['input_files'][name]=[{k:v for k,v in r.items() if k not in ('old','new')} for r in rows]
            record['results'][name]={'legacy_all':stats(old),'legacy_same_flights_as_current':stats(matched),
                                     'current':stats(new),'current_cache_sha256':hashlib.sha256(cache.read_bytes()).hexdigest(),
                                     'current_spectra_reproduced':True}
            all_old.extend(old);all_matched.extend(matched);all_new.extend(new)
            print(f'{name}: legacy {len(old)}, current {len(new)}; current cache reproduced',flush=True)
        record['results']['pooled']={'legacy_all':stats(all_old),'legacy_same_flights_as_current':stats(all_matched),'current':stats(all_new)}
        assert driver['source_hash'](ROOT)==source,'Sources changed during diagnostic'
        record.update(status='complete',elapsed_seconds=time.monotonic()-started,completed_utc=datetime.now(UTC).isoformat())
    except BaseException as exc:
        record.update(status='failed',error=f'{type(exc).__name__}: {exc}')
        path.write_text(json.dumps(record,indent=2)+'\n')
        raise
    path.write_text(json.dumps(record,indent=2,allow_nan=False)+'\n')
    print('PSD selection comparison complete: '+str(path),flush=True)


if __name__=='__main__':
    main()
