"""Force the auxiliary raw trimming census and record its exact source identity.

The main rebuild's trimming stage can read an unversioned cache. This supplementary
run removes that provenance ambiguity without changing canonical cleaned tables or
the numerical sources while the main driver is active.
"""
from __future__ import annotations

import hashlib
import json
import os
import runpy
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT/'src'))
driver = runpy.run_path(str(ROOT/'scripts/rebuild_thesis.py'))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None


def main():
    # Spare-core work: preserve priority for the main numerical pipeline.
    os.nice(10)
    source = driver['source_hash'](ROOT)
    cleaning = driver['current_cleaning'](ROOT)
    snapshots = {
        name: driver['validate_snapshot'](g.config().derived_dir, cleaning)
        for name, g in driver['DISCIPLINES'].items()
    }
    files = [ROOT/'thesis/generated'/name for name in (
        'trim_split_seconds.pdf', 'trim_interior_excisions.pdf', 'trim.tex')]
    caches = [g.config().derived_dir/'trim_scan.parquet'
              for g in driver['DISCIPLINES'].values()]
    record = {
        'status': 'running', 'started_utc': datetime.now(UTC).isoformat(),
        'parent_run_id': '20260911T213634Z-7b7367f1',
        'source_sha256': source, 'cleaning': cleaning, 'datasets': snapshots,
        'reason': 'Force a full raw trimming census instead of trusting an unversioned cache',
        'workers': 4, 'nice': 10,
        'outputs_before': {p.name: sha(p) for p in files},
        'caches_before': {str(p): sha(p) for p in caches},
    }
    path = HERE/'trimming-refresh.json'
    driver['write_json'](path, record)
    environment = dict(os.environ, SOARING_MAX_WORKERS='4', PYTHONPATH=str(ROOT/'src'),
                       PYTHONUNBUFFERED='1')
    for key in ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS',
                'VECLIB_MAXIMUM_THREADS', 'NUMEXPR_NUM_THREADS', 'BLIS_NUM_THREADS'):
        environment[key] = '1'
    command = [sys.executable, 'scripts/reporting/ch2_dataset/generate_trimming_figure.py', '--rescan']
    record['command'] = command
    started = time.monotonic()
    try:
        with (HERE/'trimming-refresh.log').open('w') as log:
            child = subprocess.Popen(command, cwd=ROOT, env=environment,
                                     stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
            for line in child.stdout:
                print(line, end='', flush=True)
                log.write(line)
                log.flush()
            if child.wait():
                raise RuntimeError(f'Trimming census exited {child.returncode}')
        if driver['source_hash'](ROOT) != source:
            raise ValueError('Source changed during supplementary census')
        for name, g in driver['DISCIPLINES'].items():
            if driver['validate_snapshot'](g.config().derived_dir, cleaning) != snapshots[name]:
                raise ValueError(f'{name}: canonical archive changed')
        record['outputs_after'] = {p.name: sha(p) for p in files}
        record['caches_after'] = {str(p): sha(p) for p in caches}
        record['same_outputs_as_cached_stage'] = record['outputs_before'] == record['outputs_after']
        record.update(status='complete', completed_utc=datetime.now(UTC).isoformat(),
                      elapsed_seconds=time.monotonic()-started)
    except BaseException as exc:
        record.update(status='failed', error=f'{type(exc).__name__}: {exc}')
        driver['write_json'](path, record)
        raise
    driver['write_json'](path, record)
    print(f'Supplementary census complete; same outputs as cached stage: {record["same_outputs_as_cached_stage"]}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
