"""Continue the completed numerical prefix in the identified frozen source tree.

The active bootstrap is left alone. Prepare only after its reporter succeeds and
the parent stops at the broad source guard because viewer files changed. Preserve
that failure record, the executed-source identity, all checks and the user's edits.
"""
from __future__ import annotations

import argparse
import ast
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
WORK = HERE.parents[1]
FROZEN = HERE/'frozen-source'
PARENT = HERE/'recovery-runs/20260912T104500Z-5cfc4e8c'
RECORD = HERE/'isolated-continuation.json'
VIEWER_FILES = {
    'src/soaring/viewer/catalog_index.py', 'src/soaring/viewer/geography.py',
    'src/soaring/viewer/widgets/flight_picker.py',
    'src/soaring/viewer/widgets/map_view.py',
}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def guarded_paths(root):
    return set([*root.glob('src/**/*.py'), *root.glob('scripts/**/*.py'),
        *root.glob('configs/*.yaml'), *root.glob('thesis/sections/*.tex'),
        *root.glob('thesis/appendices/**/*.tex'), root/'thesis/main.tex',
        root/'thesis/references.bib', root/'uv.lock'])


def viewer_difference_proof():
    """Require all other sources identical; check the one reporting UI import."""
    relatives = {p.relative_to(WORK).as_posix() for p in guarded_paths(WORK)}
    require(relatives == {p.relative_to(FROZEN).as_posix() for p in guarded_paths(FROZEN)},
            'Guarded source file sets differ')
    differences = {}
    for name in sorted(relatives):
        old, new = digest(FROZEN/name), digest(WORK/name)
        if old != new:
            require(name in VIEWER_FILES, f'Non-viewer source changed: {name}')
            differences[name] = {'executed_sha256': old, 'working_sha256': new}
    geography = 'src/soaring/viewer/geography.py'
    before, after = [ast.parse((root/geography).read_text()) for root in (FROZEN, WORK)]
    old_nodes = [ast.dump(node, include_attributes=False) for node in before.body]
    added, index = [], 0
    for node in after.body:
        if index < len(old_nodes) and ast.dump(node, include_attributes=False) == old_nodes[index]:
            index += 1
        else:
            added.append(node)
    require(index == len(old_nodes), 'Existing geography definitions changed')
    allowed = {'REGIONS', 'TERRAIN_BANDS', 'TERRAIN_ORDER', 'classify_region', 'classify_terrain'}
    bindings = set()
    for node in added:
        if isinstance(node, ast.FunctionDef):
            bindings.add(node.name)
        elif isinstance(node, (ast.Assign, ast.AnnAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            require(all(isinstance(target, ast.Name) for target in targets), 'Unexpected geography assignment')
            bindings.update(target.id for target in targets)
        else:
            raise ValueError('Unexpected executable addition to geography')
    require(bindings <= allowed, 'Unexpected new geography binding')
    old_reads = {node.id for node in ast.walk(before) if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load)}
    require(not bindings & old_reads, 'New geography binding affects old code')
    imports = []
    for directory in ('scripts', 'src/soaring/analysis', 'src/soaring/reporting', 'src/soaring/acquisition'):
        for path in (WORK/directory).rglob('*.py'):
            for node in ast.walk(ast.parse(path.read_text())):
                if isinstance(node, ast.ImportFrom) and node.module and node.module.startswith('soaring.viewer'):
                    imports.append({'file': path.relative_to(WORK).as_posix(), 'module': node.module,
                                    'names': [item.name for item in node.names]})
                if isinstance(node, ast.Import):
                    require(not any(item.name.startswith('soaring.viewer') for item in node.names),
                            f'Unexpected viewer module import: {path}')
    require(imports == [{'file': 'scripts/reporting/ch2_dataset/generate_terrain_figure.py',
                        'module': 'soaring.viewer.geography',
                        'names': ['FRANCE_EXTENT', 'draw_land', 'load_basemap']}],
            'Reporting viewer dependencies changed')
    return {'differences': differences, 'all_other_guarded_files_identical': True,
            'geography_existing_ast_statements_unchanged': True,
            'geography_additional_bindings': sorted(bindings),
            'reporting_viewer_imports': imports,
            'scope': 'The added UI classifiers are not read by the unchanged terrain-rendering definitions. All cleaning, analysis, reporting scripts, configuration, lockfile and manuscript bytes match the executed snapshot.'}


def load_driver():
    sys.path.insert(0, str(FROZEN/'src'))
    spec = importlib.util.spec_from_file_location('isolated_rebuild', FROZEN/'scripts/rebuild_thesis.py')
    driver = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(driver)
    return driver


def guard(driver, record):
    require(driver.source_hash(FROZEN) == record['source_sha256'], 'Frozen source changed')
    require(driver.numerical_source_hash(FROZEN) == record['numerical_source_sha256'], 'Frozen numerical source changed')
    require(driver.current_cleaning(FROZEN) == record['cleaning'], 'Cleaning or package identity changed')
    for name, glider in driver.DISCIPLINES.items():
        require(driver.validate_snapshot(glider.config().derived_dir, record['cleaning']) == record['datasets'][name],
                f'Cleaned archive changed: {name}')


def prepare():
    require(not RECORD.exists(), 'An isolated continuation has already been prepared')
    original = (PARENT/'manifest.json').read_bytes()
    previous = json.loads(original)
    require(previous['status'] == 'failed' and previous.get('error') == 'ValueError: Source changed',
            'Wait for successful transport completion and the parent source-guard stop')
    require(len(previous['stages']) == 24 and all(s['status'] == 'complete' for s in previous['stages']),
            'Exactly 24 completed stages are required; do not repeat the bootstrap')
    require(previous['stages'][-1]['id'] == 'transport_full', 'Unexpected prefix')
    proof = viewer_difference_proof()
    driver = load_driver()
    guard(driver, previous)
    run_id = datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')+'-'+uuid.uuid4().hex[:8]
    run = HERE/'recovery-runs'/run_id
    run.mkdir()
    copied = {}
    generated = FROZEN/'thesis/generated'
    for source in sorted((WORK/'thesis/generated').iterdir()):
        if not source.is_file() or source.name.startswith('._'):
            continue
        target = generated/source.name
        shutil.copy2(source, target)
        require(digest(source) == digest(target), f'Generated copy differs: {source.name}')
        copied[source.name] = {'sha256': digest(target), 'source': str(source),
                              'mtime_ns': target.stat().st_mtime_ns}
    # Static map and annotation inputs stay available to scripts in the isolated tree.
    for name in ('data', 'annotations'):
        shutil.copytree(WORK/name, FROZEN/name, dirs_exist_ok=True, symlinks=True,
                        ignore=shutil.ignore_patterns('__pycache__', '.DS_Store', '._*'))
    (run/'arrays').mkdir()
    for source in (PARENT/'arrays').iterdir():
        (run/'arrays'/source.name).symlink_to(source, target_is_directory=source.is_dir())
    plan = driver.load_plan(FROZEN/'configs/rebuild.yaml')
    commands = driver.commands(plan, run/'arrays', FROZEN/'annotations/phase_labeling'/run_id,
                               clean=False, jobs=8, build=True)
    require([s['id'] for s in previous['stages']] == [name for name, _ in commands[:24]],
            'Stage prefix differs from the frozen plan')
    prefix = copy.deepcopy(previous['stages'])
    for index, stage in enumerate(prefix, 1):
        stage.update(reused_from=str(PARENT), source_sha256_at_execution=previous['source_sha256'])
        log = PARENT/f'{index:02d}-{stage["id"]}.log'
        require(log.is_file(), f'Missing completed log: {log}')
        shutil.copy2(log, run/log.name)
    completed = {s['command'][1]: s['started_unix'] for s in prefix}
    required = {name: writer for name, writer in driver.required_outputs().items()
                if writer in completed or name in plan.get('historical_outputs', [])}
    reused = driver.check_fresh_outputs(required, completed, set(plan.get('historical_outputs', [])), generated)
    guard(driver, previous)
    require(digest(PARENT/'manifest.json') == hashlib.sha256(original).hexdigest(), 'Parent record changed')
    (run/'parent-manifest-original.json').write_bytes(original)
    record = {key: copy.deepcopy(previous[key]) for key in
              ('source_sha256', 'numerical_source_sha256', 'cleaning', 'datasets', 'resources')}
    record.update(run_id=run_id, status='prepared', source_root=str(FROZEN), working_root=str(WORK),
                  run_dir=str(run), parent_run=str(PARENT), parent_manifest_sha256=hashlib.sha256(original).hexdigest(),
                  stages=prefix, copied_generated=copied, reused_required_outputs=reused,
                  viewer_difference_proof=proof, orchestrator_sha256=digest(Path(__file__)),
                  reason='Viewer edits changed the broad guard; all numerical dependencies match. Continue the 24 completed stages under the original isolated source identity.')
    driver.write_json(RECORD, record)
    driver.write_json(run/'manifest.json', record)
    print(f'Prepared isolated continuation after 24 completed stages: {run}', flush=True)


def run_prepared():
    record = json.loads(RECORD.read_text())
    require(record['status'] == 'prepared', 'Continuation already claimed')
    require(digest(Path(__file__)) == record['orchestrator_sha256'], 'Orchestrator changed')
    driver = load_driver()
    guard(driver, record)
    run = Path(record['run_dir'])
    plan = driver.load_plan(FROZEN/'configs/rebuild.yaml')
    annotations = FROZEN/'annotations/phase_labeling'/record['run_id']
    commands = driver.commands(plan, run/'arrays', annotations, clean=False, jobs=8, build=True)
    manifest = {key: copy.deepcopy(record[key]) for key in
                ('run_id', 'source_root', 'source_sha256', 'numerical_source_sha256', 'cleaning', 'datasets', 'resources', 'stages')}
    manifest.update(status='running', started_utc=datetime.now(UTC).isoformat(),
                    audit_dir=str(run/'arrays'), annotation_dir=str(annotations), continuation=record)
    completed = {s['command'][1]: s['started_unix'] for s in manifest['stages']}
    historical = set(plan.get('historical_outputs', []))
    os.environ['SOARING_MAX_WORKERS'] = '8'
    owns_run = False
    try:
        with ExitStack() as stack:
            driver._lock(stack, HERE/'.isolated-continuation.lock')
            driver._lock(stack, Path('/Volumes/SSD_DISANTE/derived-audit/.rebuild.lock'))
            for glider in driver.DISCIPLINES.values():
                driver._lock(stack, glider.config().derived_dir/'.preprocess.lock')
            require(json.loads(RECORD.read_text())['status'] == 'prepared', 'Continuation claimed concurrently')
            owns_run = True
            guard(driver, record)
            require(digest(PARENT/'manifest.json') == record['parent_manifest_sha256'], 'Parent changed')
            for name, value in record['copied_generated'].items():
                require(digest(FROZEN/'thesis/generated'/name) == value['sha256'], f'Copied result changed: {name}')
            record['status'] = 'running'
            driver.write_json(RECORD, record)
            driver.write_json(run/'manifest.json', manifest)
            for index, (name, command) in enumerate(commands[24:], 25):
                guard(driver, record)
                if name == 'latex':
                    manifest['outputs'] = driver.check_fresh_outputs(driver.required_outputs(), completed, historical, FROZEN/'thesis/generated')
                print(f'[{index}/{len(commands)}] {name}', flush=True)
                start = time.time()
                stage = {'id': name, 'command': command, 'status': 'running', 'started_unix': start}
                manifest['stages'].append(stage)
                driver.write_json(run/'manifest.json', manifest)
                driver._run(command, run/f'{index:02d}-{name}.log')
                stage.update(status='complete', elapsed_seconds=time.time()-start)
                if len(command)>1 and command[1].endswith('.py'):
                    completed[command[1]] = start
                driver.write_json(run/'manifest.json', manifest)
            guard(driver, record)
            manifest['outputs'] = driver.check_fresh_outputs(driver.required_outputs(), completed, historical, FROZEN/'thesis/generated')
            manifest.update(status='complete', completed_utc=datetime.now(UTC).isoformat(),
                            pdf_sha256=digest(FROZEN/'thesis/main.pdf'))
            driver.write_json(run/'manifest.json', manifest)
    except BaseException as exc:
        if not owns_run:
            raise
        if manifest['stages'][-1]['status'] == 'running':
            manifest['stages'][-1]['status'] = 'failed'
        manifest.update(status='failed', error=f'{type(exc).__name__}: {exc}')
        driver.write_json(run/'manifest.json', manifest)
        record.update(status='failed', error=manifest['error'])
        driver.write_json(RECORD, record)
        raise
    record['status'] = 'complete'
    driver.write_json(RECORD, record)
    print(f'Isolated numerical rebuild complete: {run}', flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--check-source', action='store_true')
    group.add_argument('--prepare', action='store_true')
    group.add_argument('--run', action='store_true')
    args = parser.parse_args()
    if args.check_source:
        proof = viewer_difference_proof()
        (HERE/'viewer-only-source-differences.json').write_text(json.dumps(proof, indent=2)+'\n')
        print(json.dumps(proof, indent=2))
    elif args.prepare:
        prepare()
    else:
        run_prepared()
