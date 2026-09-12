"""Continue an identified unchanged numerical prefix in isolated source files.

The failed parent manifest is preserved. Reuse requires identical numerical sources,
identical canonical data tables, a complete ordered stage prefix, and fresh copied
outputs. All remaining stages retain the original driver's source, data, locking and
output checks. This orchestration is recorded by hash in the new manifest.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import importlib.util
import json
import os
import shutil
import sys
import time
import uuid
from contextlib import ExitStack
from datetime import UTC, datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    record = json.loads((HERE/'frozen-source.json').read_text())
    root = Path(record['source_root'])
    parent = Path(record['parent_run'])
    parent_bytes = (parent/'manifest.json').read_bytes()
    if hashlib.sha256(parent_bytes).hexdigest() != record['parent_manifest_sha256']:
        raise ValueError('Parent manifest changed after snapshot preparation')
    previous = json.loads(parent_bytes)
    sys.path.insert(0, str(root/'src'))
    spec = importlib.util.spec_from_file_location('frozen_rebuild', root/'scripts/rebuild_thesis.py')
    driver = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(driver)
    if driver.source_hash(root) != record['source_sha256']:
        raise ValueError('Frozen source changed')
    if driver.numerical_source_hash(root) != previous['numerical_source_sha256']:
        raise ValueError('Numerical source changes forbid prefix reuse')
    cleaning = driver.current_cleaning(root)
    if cleaning != previous['cleaning']:
        raise ValueError('Cleaning definition changed')
    archives = {name: g.config() for name, g in driver.DISCIPLINES.items()}
    snapshots = {name: driver.validate_snapshot(g.derived_dir, cleaning) for name, g in archives.items()}
    if snapshots != previous['datasets']:
        raise ValueError('Source tables differ from the completed prefix')
    prefix = []
    for stage in previous['stages']:
        if stage['status'] != 'complete':
            break
        prefix.append(copy.deepcopy(stage))
    if not prefix:
        raise ValueError('No completed prefix to reuse')
    plan = driver.load_plan(root/'configs/rebuild.yaml')
    run_id = datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')+'-'+uuid.uuid4().hex[:8]
    base = parent.parent.parent
    run = base/'runs'/run_id
    annotations = root/'annotations/phase_labeling'/run_id
    commands = driver.commands(plan, run/'arrays', annotations, clean=False, jobs=8, build=True)
    if [s['id'] for s in prefix] != [name for name, _ in commands[:len(prefix)]]:
        raise ValueError('Completed prefix differs from current stage plan')
    if any('{audit_dir}' in str(s.get('args', [])) for s in plan['stages'][:len(prefix)]):
        raise ValueError('This continuation does not reuse earlier analysis-array stages')
    completed = {s['command'][1]:s['started_unix'] for s in prefix if s['command'][1].endswith('.py')}
    required = driver.required_outputs()
    historical = set(plan.get('historical_outputs', []))
    reused_outputs = driver.check_fresh_outputs(
        {name:producer for name,producer in required.items() if producer in completed},
        completed, historical, root/'thesis/generated',
    )
    # The copied results must still equal the working-tree results whose stages
    # actually completed. Their copied mtimes preserve the original freshness check.
    for name, entry in reused_outputs.items():
        path = Path(record['working_root'])/'thesis/generated'/name
        if hashlib.sha256(path.read_bytes()).hexdigest() != entry['sha256']:
            raise ValueError(f'Reused output changed since copying: {name}')
    if args.check:
        print(json.dumps({'reusable_stages':[s['id'] for s in prefix],
                          'reused_outputs':sorted(reused_outputs),
                          'remaining_stages':[name for name,_ in commands[len(prefix):]],
                          'frozen_root':str(root)},indent=2))
        return 0
    os.environ['SOARING_MAX_WORKERS'] = '8'
    run.mkdir(parents=True)
    (run/'arrays').mkdir()
    for i, stage in enumerate(prefix, 1):
        stage['reused_from'] = str(parent)
        stage['source_sha256_at_execution'] = previous['source_sha256']
        source = parent/f'{i:02d}-{stage["id"]}.log'
        if source.is_file():
            shutil.copy2(source, run/source.name)
    manifest = {
        'run_id':run_id, 'status':'running', 'source_root':str(root),
        'source_sha256':record['source_sha256'],
        'numerical_source_sha256':previous['numerical_source_sha256'],
        'cleaning':cleaning, 'datasets':snapshots, 'annotation_dir':str(annotations),
        'stages':prefix, 'resources':previous['resources'],
        'started_utc':datetime.now(UTC).isoformat(),
        'continuation':{'parent_run':str(parent),
                        'parent_manifest_sha256':record['parent_manifest_sha256'],
                        'reason':record['reason'], 'reused_outputs':reused_outputs,
                        'orchestrator':str(Path(__file__).resolve()),
                        'orchestrator_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()},
    }
    path = run/'manifest.json'
    driver.write_json(path, manifest)
    (HERE/'frozen-downstream-run.json').write_text(json.dumps({'run_dir':str(run), 'manifest':str(path), 'source_root':str(root)},indent=2)+'\n')
    print(f'Continuation manifest: {path}', flush=True)
    print(f'Reusing {len(prefix)} completed stages with identical numerical sources and data.', flush=True)
    def guard():
        if driver.source_hash(root) != manifest['source_sha256']:
            raise ValueError('Frozen source changed during continuation')
        if driver.current_cleaning(root) != cleaning:
            raise ValueError('Cleaning definition or numerical environment changed')
        for name, archive in archives.items():
            if (archive.derived_dir/'.run_incomplete').exists() or driver.dataset_identity(archive.derived_dir) != snapshots[name]['tables']:
                raise ValueError(f'{name}: canonical tables changed')
    try:
        with ExitStack() as stack:
            driver._lock(stack, base/'.rebuild.lock')
            for archive in archives.values():
                driver._lock(stack, archive.derived_dir/'.preprocess.lock')
            for index,(name,command) in enumerate(commands[len(prefix):], len(prefix)+1):
                guard()
                if name == 'latex':
                    manifest['outputs'] = driver.check_fresh_outputs(driver.required_outputs(), completed, historical, root/'thesis/generated')
                print(f'\n[{index}/{len(commands)}] {name}', flush=True)
                started = time.time()
                stage = {'id':name, 'command':command, 'started_unix':started, 'status':'running'}
                manifest['stages'].append(stage)
                driver.write_json(path, manifest)
                driver._run(command, run/f'{index:02d}-{name}.log')
                stage.update(status='complete', elapsed_seconds=time.time()-started)
                if len(command)>1 and command[1].endswith('.py'):
                    completed[command[1]] = started
                driver.write_json(path, manifest)
            guard()
            manifest['outputs'] = driver.check_fresh_outputs(driver.required_outputs(), completed, historical, root/'thesis/generated')
            manifest['pdf_sha256'] = hashlib.sha256((root/'thesis/main.pdf').read_bytes()).hexdigest()
            manifest.update(status='complete', completed_utc=datetime.now(UTC).isoformat())
            driver.write_json(path, manifest)
    except BaseException as exc:
        if manifest['stages'][-1]['status']=='running':
            manifest['stages'][-1]['status']='failed'
        manifest.update(status='failed', error=f'{type(exc).__name__}: {exc}')
        driver.write_json(path, manifest)
        raise
    print(f'Frozen numerical rebuild complete: {path}', flush=True)
    print('Generated products and the unique annotation pack must now be copied back and the working manuscript reviewed.', flush=True)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
