"""Extract descriptive wing-class contrasts from the fresh regional report.

This is a review aid, not a significance test or an additional transport estimator.
It never writes canonical generated products or numerical pipeline sources.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import numpy as np


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', type=Path, required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[2]
    manifest = json.loads((args.run/'manifest.json').read_text())
    stage = next(s for s in manifest['stages'] if s['id'] == 'kinematics')
    assert stage['status'] == 'complete', 'Regional figures have not completed'
    path = root/'thesis/generated/kinematic_isotropy.json'
    assert path.stat().st_mtime >= stage['started_unix'], 'Stale regional report'
    data = json.loads(path.read_text())
    rows = {(r['group'], r['quantity']): r for r in data['rows']
            if r['grouping'] == 'region_equipment'}
    output = {'run_id': manifest['run_id'],
              'report_sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
              'measure': 'Absolute log ratio of raw geographic second moments',
              'interpretation': 'Descriptive at plotted supported times; no causal or significance claim',
              'comparisons': []}
    for region in ('Alps', 'Pyrenees', 'Channel Coast'):
        for quantity in ('position', 'velocity', 'acceleration'):
            pair = [rows.get((f'{region} / {group}', quantity))
                    for group in ('EN A/B', 'EN C/D/CCC')]
            if any(r is None for r in pair):
                continue
            ab, cd = pair
            assert ab['time_s'] == cd['time_s']
            values = np.array([ab['ratio'], cd['ratio']], dtype=float)
            valid = np.isfinite(values).all(axis=0) & (values > 0).all(axis=0)
            times = np.asarray(ab['time_s'])[valid]
            if not len(times):
                continue
            imbalance = np.abs(np.log(values[:, valid]))
            output['comparisons'].append({
                'region': region, 'quantity': quantity,
                'supported_plotted_times': int(valid.sum()),
                'cdccc_closer_to_one_times': int((imbalance[1] < imbalance[0]).sum()),
                'ab_closer_to_one_times': int((imbalance[0] < imbalance[1]).sum()),
                'time_s': times.tolist(), 'ratio_ab': values[0, valid].tolist(),
                'ratio_cdccc': values[1, valid].tolist(),
                'absolute_log_ratio_ab': imbalance[0].tolist(),
                'absolute_log_ratio_cdccc': imbalance[1].tolist(),
                'n_flights_ab': np.asarray(ab['n_flights'])[valid].tolist(),
                'n_flights_cdccc': np.asarray(cd['n_flights'])[valid].tolist(),
                'n_clusters_ab': np.asarray(ab['n_clusters'])[valid].tolist(),
                'n_clusters_cdccc': np.asarray(cd['n_clusters'])[valid].tolist(),
                'n_missing_cluster_key_ab': np.asarray(ab['n_missing_cluster_key'])[valid].tolist(),
                'n_missing_cluster_key_cdccc': np.asarray(cd['n_missing_cluster_key'])[valid].tolist(),
            })
    target = Path(__file__).with_name('regional-contrasts-audit.json')
    target.write_text(json.dumps(output, indent=2, allow_nan=False)+'\n')
    print(f'Descriptive regional contrasts extracted to {target}')


if __name__ == '__main__':
    main()
