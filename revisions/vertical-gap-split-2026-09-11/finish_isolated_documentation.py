"""Retry only provenance and LaTeX after missing static documentation inputs.

Preserve the failed attempt. All 37 completed stages, numerical source, cleaning
and archive identities must still agree. The hook and MkDocs configuration are
read as text; their bytes must equal Git HEAD. No numerical producer is rerun.
"""
from __future__ import annotations
import hashlib
import importlib.util
import json
import shutil
import subprocess
import time
from contextlib import ExitStack
from datetime import UTC, datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
WORK = HERE.parents[1]


def require(condition, message):
    if not condition:
        raise ValueError(message)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    spec = importlib.util.spec_from_file_location('isolated', HERE/'continue_isolated_rebuild.py')
    helper = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(helper)
    record_path = HERE/'isolated-continuation.json'
    record = json.loads(record_path.read_text())
    run = Path(record['run_dir'])
    path = run/'manifest.json'
    manifest = json.loads(path.read_text())
    require(record['status'] == manifest['status'] == 'failed', 'Expected the failed finalization')
    require(len(manifest['stages']) == 38, 'Unexpected stage chain')
    require(all(s['status'] == 'complete' for s in manifest['stages'][:37]), 'Numerical work incomplete')
    require(manifest['stages'][-1]['id'] == 'provenance' and manifest['stages'][-1]['status'] == 'failed', 'Unexpected failure')
    failed_log = run/'38-provenance.log'
    require('FileNotFoundError' in failed_log.read_text() and any(n in failed_log.read_text() for n in ('.githooks/pre-commit', 'mkdocs.yml')), 'Different failure requires review')
    driver = helper.load_driver()
    helper.guard(driver, record)
    require(digest(helper.PARENT/'manifest.json') == record['parent_manifest_sha256'], 'Parent changed')
    plan = driver.load_plan(helper.FROZEN/'configs/rebuild.yaml')
    commands = driver.commands(plan, run/'arrays', Path(manifest['annotation_dir']), clean=False, jobs=8, build=True)
    require(len(commands) == 39 and [x[0] for x in commands[37:]] == ['provenance', 'latex'], 'Unexpected tail')
    require(all(s['id'] == name and s['command'] == command for s, (name, command) in zip(manifest['stages'][24:37], commands[24:37])), 'Completed commands changed')
    completed = {s['command'][1]: s['started_unix'] for s in manifest['stages'][:37] if s['command'][1].endswith('.py')}
    historical = set(plan.get('historical_outputs', []))
    outputs = driver.check_fresh_outputs(driver.required_outputs(), completed, historical, helper.FROZEN/'thesis/generated')
    support_inputs = ('.githooks/pre-commit', 'mkdocs.yml')
    for name in support_inputs:
        require((WORK/name).read_bytes() == subprocess.check_output(['git', 'show', f'HEAD:{name}'], cwd=WORK), f'Support input differs from Git: {name}')
        if (helper.FROZEN/name).exists():
            require((helper.FROZEN/name).read_bytes() == (WORK/name).read_bytes(), f'Isolated support input differs: {name}')
    with ExitStack() as stack:
        driver._lock(stack, HERE/'.isolated-continuation.lock')
        driver._lock(stack, Path('/Volumes/SSD_DISANTE/derived-audit/.rebuild.lock'))
        for glider in driver.DISCIPLINES.values():
            driver._lock(stack, glider.config().derived_dir/'.preprocess.lock')
        helper.guard(driver, record)
        backup = run/'finalization-retry-2'
        backup.mkdir(exist_ok=False)
        for source in (path, record_path, failed_log):
            shutil.copy2(source, backup/source.name)
        for name in support_inputs:
            support = helper.FROZEN/name
            support.parent.mkdir(exist_ok=True)
            if not support.exists():
                shutil.copy2(WORK/name, support)
        shutil.copy2(Path(__file__), backup/Path(__file__).name)
        retry = {'reason': 'Missing static documentation inputs read by the provenance index; no numerical failure',
                 'failed_manifest_sha256': digest(backup/'manifest.json'),
                 'failed_record_sha256': digest(backup/record_path.name),
                 'failed_log_sha256': digest(backup/failed_log.name),
                 'support_inputs_sha256': {n: digest(helper.FROZEN/n) for n in support_inputs},
                 'previous_finalization_retry': manifest.get('finalization_retry'),
                 'script_sha256': digest(Path(__file__)), 'preserved_complete_stages': 37}
        manifest['finalization_retry'] = retry
        manifest['stages'] = manifest['stages'][:37]
        manifest['status'] = record['status'] = 'running'
        manifest.pop('error', None)
        record.pop('error', None)
        record['finalization_retry'] = retry
        driver.write_json(record_path, record)
        try:
            for index, (name, command) in enumerate(commands[37:], 38):
                helper.guard(driver, record)
                stage = {'id': name, 'command': command, 'started_unix': time.time(), 'status': 'running'}
                if name == 'provenance':
                    stage['previous_failed_attempt'] = str(backup/failed_log.name)
                manifest['stages'].append(stage)
                driver.write_json(path, manifest)
                print(f'[{index}/39] {name}: finalization retry', flush=True)
                driver._run(command, run/f'{index:02d}-{name}.log')
                stage.update(status='complete', elapsed_seconds=time.time()-stage['started_unix'])
                if command[1].endswith('.py'):
                    completed[command[1]] = stage['started_unix']
                driver.write_json(path, manifest)
            helper.guard(driver, record)
            fresh = driver.check_fresh_outputs(driver.required_outputs(), completed, historical, helper.FROZEN/'thesis/generated')
            require(fresh == outputs, 'Numerical outputs changed during finalization')
            manifest.update(status='complete', outputs=fresh, completed_utc=datetime.now(UTC).isoformat(), pdf_sha256=digest(helper.FROZEN/'thesis/main.pdf'))
            record['status'] = 'complete'
            driver.write_json(path, manifest)
            driver.write_json(record_path, record)
            driver.write_json(backup/'completion.json', retry | {'pdf_sha256': manifest['pdf_sha256'], 'manifest_sha256': digest(path)})
        except BaseException as exc:
            if manifest['stages'][-1]['status'] == 'running':
                manifest['stages'][-1]['status'] = 'failed'
            manifest.update(status='failed', error=f'{type(exc).__name__}: {exc}')
            record.update(status='failed', error=manifest['error'])
            driver.write_json(path, manifest)
            driver.write_json(record_path, record)
            raise
    print(f'All 39 stages complete: {run}', flush=True)


if __name__ == '__main__':
    main()
