"""Recheck eight identified altitude-step examples under cleaning 2.3.0.

Read-only with respect to the archive: raw flights and features are recomputed in
memory. Temporal proximity to a usable feature is not an independent defect label.
"""
from __future__ import annotations

import hashlib
import json
import runpy
import sys
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / 'scripts'))
from preprocess import _process_one
from soaring.analysis.preproc import cleaning
from soaring.analysis.segmentation.config import load_segmentation_config
from soaring.analysis.segmentation.features import build_feature_frame, valid_feature_mask
from soaring.reporting import DISCIPLINES
from soaring.reporting.snapshot import current_cleaning


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    historical_path = ROOT / 'revisions/manuscript-review-2026-09-11/level-shift-candidate-audit.json'
    historical = json.loads(historical_path.read_text())
    driver = runpy.run_path(str(ROOT / 'scripts/rebuild_thesis.py'))
    identity = driver['source_hash'](ROOT)
    contract = current_cleaning(ROOT)
    config = load_segmentation_config(ROOT / 'configs/segmentation.yaml')
    original = cleaning._clean_altitude
    captured = {}

    def capture(t, altitude, fix_level):
        result = original(t, altitude, fix_level)
        excess = np.abs(cleaning.step_vz(t, altitude)) > fix_level.max_vertical_speed_mps
        isolated = excess.copy()
        isolated[:-1] &= ~excess[1:]
        isolated[1:] &= ~excess[:-1]
        events = []
        for i in np.flatnonzero(isolated):
            jump = abs(altitude[i+1] - altitude[i])
            future = altitude[i+1:min(i+6, len(altitude))]
            future = future[np.isfinite(future)]
            if not len(future) or np.min(abs(future-altitude[i])) > .3*jump:
                events.append({
                    't': float(t[i+1]), 'jump_m': float(altitude[i+1]-altitude[i]),
                    'dt_s': float(t[i+1]-t[i]),
                    'endpoint_flagged': bool(result[0][i+1] or result[1][i+1] or result[2][i+1]),
                })
        if len(events) != result[-1]:
            raise ValueError('Independent candidate recount differs from the cleaner')
        captured['events'] = events
        return result

    rows, inputs = [], {}
    cleaning._clean_altitude = capture
    try:
        for discipline, glider in DISCIPLINES.items():
            meta_path = glider.derived_dir() / 'flights_meta.parquet'
            before = digest(meta_path)
            meta = pd.read_parquet(meta_path)
            meta.flight_id = meta.flight_id.astype(str)
            meta = meta.set_index('flight_id')
            for previous in historical['rows']:
                if previous['discipline'] != discipline:
                    continue
                fid, path = previous['flight_id'], Path(previous['raw_path'])
                raw_hash = digest(path)
                if raw_hash != previous['raw_sha256']:
                    raise ValueError(f'Historical raw example changed: {fid}')
                if pd.notna(meta.loc[fid, 'drop_reason']):
                    raise ValueError(f'Example is no longer retained: {fid}')
                m, fixes, _, _ = _process_one((str(path), glider.source, discipline))
                if fixes is None:
                    raise ValueError(f'Example does not reproduce as retained: {fid}')
                events = captured['events']
                if len(events) != int(meta.loc[fid, 'n_alt_level_shift']):
                    raise ValueError(f'Recomputed metadata counter differs: {fid}')
                observations = pd.concat(
                    [build_feature_frame(segment, config)
                     for _, segment in fixes.groupby('segment_id')], ignore_index=True,
                )
                valid = valid_feature_mask(observations)
                centres = observations.t.to_numpy()
                covered = sum(bool(np.any(
                    (abs(centres-(event['t']-m['ground_phase_start_s'])) <= config.feature_window_s/2) & valid
                )) for event in events)
                row = {
                    'discipline': discipline, 'flight_id': fid,
                    'selection': 'Same identified historical example: ' + previous['selection'],
                    'raw_path': str(path), 'raw_sha256': raw_hash,
                    'candidate_count': len(events),
                    'candidate_endpoint_already_altitude_flagged': sum(e['endpoint_flagged'] for e in events),
                    'candidate_times_near_usable_feature_centres': covered,
                    'usable_feature_count': int(valid.sum()),
                    'retained_segments': int(fixes.segment_id.nunique()),
                    'retained_fixes': len(fixes),
                    'fraction_z_reconstructed': float(fixes.z_reconstructed.mean()),
                }
                rows.append(row)
                print(f'{discipline} {fid}: {len(events)} candidates; {covered} near usable feature centres', flush=True)
            if digest(meta_path) != before:
                raise ValueError(f'Metadata changed during audit: {discipline}')
            inputs[str(meta_path)] = before
    finally:
        cleaning._clean_altitude = original
    if driver['source_hash'](ROOT) != identity:
        raise ValueError('Sources changed during the audit')
    report = {
        'observed_utc': datetime.now(UTC).isoformat(),
        'source_sha256': identity, 'cleaning': contract,
        'historical_comparison_sha256': digest(historical_path),
        'script_sha256': digest(Path(__file__)),
        'inputs': inputs, 'rows': rows,
        'scope': 'Eight previously identified examples recomputed in memory with current cleaning and feature definitions. No archive, model, or generated thesis output modified. Counter reproduction and temporal association do not establish surviving defects, causality or population prevalence.',
    }
    (HERE / 'current-level-shift-examples.json').write_text(json.dumps(report, indent=2, allow_nan=False)+'\n')


if __name__ == '__main__':
    main()
