"""Observe the existing recovery; never launch or mutate numerical work."""
from __future__ import annotations

import json
import os
import re
import time
from datetime import UTC, datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
record = json.loads((HERE / 'recovery-run.json').read_text())
run = Path(record['run_dir'])
previous = None
while True:
    manifest = json.loads((run / 'manifest.json').read_text())
    stage = manifest['stages'][-1]
    lines = (HERE / 'recovery-console.log').read_text().splitlines()
    detail = next((line for line in reversed(lines) if line.strip()), '')
    phase = None
    lag = None
    completed_lags = []
    if stage['id'] == 'transport_full':
        for line in lines:
            if line.startswith('Fixed-population scaling: '):
                phase = line.split(': ', 1)[1]
                completed_lags = []
            elif phase and re.fullmatch(r'lag [\d.]+ s: \d+ flights, \d+ fixed origins', line):
                completed_lags.append(float(line.split()[1]))
        if completed_lags:
            lag = completed_lags[-1]
    state = {
        'observed_utc': datetime.now(UTC).isoformat(),
        'run_id': record['run_id'], 'status': manifest['status'],
        'stage': stage['id'], 'completed_stages': sum(s['status'] == 'complete' for s in manifest['stages']),
        'stage_elapsed_seconds': time.time() - stage['started_unix'],
        'phase': phase, 'last_observed_complete_lag_s': lag,
        'observed_complete_lags': len(completed_lags), 'last_console_line': detail,
        'timing_scope': 'Observation times at roughly 50-second intervals, not exact completion timestamps',
    }
    target = HERE / 'recovery-live.json'
    temporary = target.with_suffix('.tmp')
    temporary.write_text(json.dumps(state, indent=2) + '\n')
    temporary.replace(target)
    key = (state['status'], state['stage'], phase, lag, detail)
    if key != previous:
        with (HERE / 'recovery-progress.jsonl').open('a') as stream:
            stream.write(json.dumps(state) + '\n')
        print(f"{state['observed_utc']} | {state['completed_stages']}/39 complete | {state['stage']} | {detail}", flush=True)
        previous = key
    if manifest['status'] != 'running':
        break
    time.sleep(50)
