"""Audit fresh full-archive Chapter 3 outputs and extract manuscript review values."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', required=True, type=Path)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[2]
    manifest = json.loads((args.run/'manifest.json').read_text())
    stage = next(s for s in manifest['stages'] if s['id'] == 'transport_full')
    assert stage['status'] == 'complete', 'Full Chapter 3 stage has not completed'
    generated = Path(manifest.get('source_root', root))/'thesis/generated'
    paths = [generated/name for name in ('ch3_revision.json', 'ch3_self_similarity.json')]
    assert all(p.stat().st_mtime >= stage['started_unix'] for p in paths), 'Stale report'
    overview, scaling = [json.loads(p.read_text()) for p in paths]
    assert overview['measurement_contract']['scope'] == 'full eligible archive'
    assert scaling['identity']['source_contract'] == overview['measurement_contract']
    report = {'run_id': manifest['run_id'], 'reports_sha256': {
        p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}, 'results': {}}
    for name, r in scaling['results'].items():
        source = overview['provenance'][name]
        general = overview['results'][name]
        assert source['sampling'] is False
        assert source['eligible_flights'] == general['n_flights'] == len(source['flights'])
        assert source['eligible_segments'] == sum(len(f['segments']) for f in source['flights'])
        assert len(set(f['flight_id'] for f in source['flights'])) == general['n_flights']
        fixed_ids = {f['flight_id'] for f in source['flights'] if f['duration_s'] >= 20000}
        assert set(r['flight_ids']) == fixed_ids
        assert len(r['flight_ids']) == r['n_flights'] == len(fixed_ids)
        assert sum(r['origin_counts']) == r['n_origins']
        assert min(r['origin_counts']) > 0
        flight_by_id = {f['flight_id']: f for f in source['flights']}
        maximum_lag_steps = int(max(r['lags_s'])/10)
        expected_origins = [sum(max(stop-start-maximum_lag_steps, 0)
                                for start, stop in flight_by_id[fid]['segments'])
                            for fid in r['flight_ids']]
        np.testing.assert_array_equal(r['origin_counts'], expected_origins)
        q = np.asarray(r['quantiles_m'])
        tau = np.asarray(r['lags_s'])
        assert np.isfinite(q).all() and (q > 0).all()
        assert (np.diff(q, axis=-1) >= 0).all()
        np.testing.assert_allclose(np.asarray(r['quantiles_m2']), q*q, rtol=1e-14)
        np.testing.assert_allclose(general['quantile_control']['quantiles'][3], q, rtol=1e-12)
        for fit in r['fits'].values():
            chosen = np.isin(tau, fit['lags_s'])
            # Independent ordinary least-squares regression on the saved quantiles.
            design = np.column_stack([np.ones(chosen.sum()), np.log(tau[chosen])])
            slopes = np.linalg.lstsq(design, np.log(q[chosen]).reshape(chosen.sum(), -1), rcond=None)[0][1].reshape(3, 4)
            np.testing.assert_allclose(slopes, fit['h'], rtol=1e-12, atol=1e-12)
            np.testing.assert_allclose(np.mean(slopes), fit['joint_common_h'], atol=1e-12)
            np.testing.assert_allclose(slopes.mean(axis=-1), fit['common_h'], atol=1e-12)
            contrasts = fit['contrasts']
            for label, expected in (
                ('north_minus_east', slopes[1]-slopes[0]),
                ('radial_minus_east', slopes[2]-slopes[0]),
                ('radial_minus_north', slopes[2]-slopes[1]),
                ('p90_minus_p25', slopes[:, 3]-slopes[:, 0]),
            ):
                np.testing.assert_allclose(contrasts[label]['estimate'], expected, atol=1e-12)
                bounds = np.asarray(contrasts[label]['ci95'])
                assert np.isfinite(bounds).all() and (bounds[0] <= bounds[1]).all()
            for key in ('h_ci95', 'common_h_ci95'):
                bounds = np.asarray(fit[key])
                assert np.isfinite(bounds).all() and (bounds[0] <= bounds[1]).all()
        collapse = []
        for law in r['laws']:
            np.testing.assert_allclose(np.asarray(law['mass']).sum(axis=-1)+law['zero_mass'], 1, atol=1e-10)
            np.testing.assert_allclose(law['squared_edges_m2'], np.asarray(law['edges_m'])**2, rtol=1e-14)
            assert len(law['cdf_distances']) == 15
            distances = np.array([[p['power'], p['median']] for p in law['cdf_distances']])
            assert np.isfinite(distances).all() and (distances >= 0).all() and (distances <= 1+1e-12).all()
            collapse.append(dict(zip(('power_max', 'median_max'), distances.max(axis=0).tolist(), strict=True)))
        joint = r['joint']
        reference_index = np.argmin(abs(tau-1000))
        np.testing.assert_allclose(joint['reference_scale_m'],
            q[reference_index, 2, 1]/(tau[reference_index]/1000)**joint['exponent'], rtol=1e-12)
        masses = np.asarray([law['mass'] for law in joint['laws']])
        assert masses.shape == (6, 66, 66)
        assert (masses >= 0).all()
        np.testing.assert_allclose(masses.sum(axis=(1, 2)), 1, atol=1e-12)
        actual_distance = np.abs(masses[:, None]-masses[None, :]).sum(axis=(2, 3))/2
        np.testing.assert_allclose(actual_distance, joint['total_variation'], atol=1e-12)
        assert (actual_distance >= 0).all() and (actual_distance <= 1+1e-12).all()
        for law, mass in zip(joint['laws'], masses, strict=True):
            np.testing.assert_allclose(law['tail_mass'], 1-mass[1:-1, 1:-1].sum(), atol=1e-12)
            covariance = np.asarray(law['covariance'])
            np.testing.assert_allclose(covariance, covariance.T, atol=1e-12)
            assert np.linalg.eigvalsh(covariance).min() >= -1e-12
        ratio = q[:, 2, 3]/q[:, 2, 0]
        positive_distances = actual_distance[np.triu_indices(6, 1)]
        observed_closure = {}
        for label, closed in [('open', False), ('closed', True)]:
            task_flights = [f for f in source['flights'] if f['task_known'] and f['closed'] == closed]
            continuous = [f['closure_ratio'] for f in task_flights if len(f['segments']) == 1]
            observed_closure[label] = {
                'all_count': len(task_flights),
                'all_median': float(np.median([f['closure_ratio'] for f in task_flights])),
                'single_segment_count': len(continuous),
                'single_segment_median': float(np.median(continuous)),
                'above_one_count': sum(f['closure_ratio'] > 1 for f in task_flights),
            }
            np.testing.assert_allclose(observed_closure[label]['all_median'], general['tasks'][label]['median_closure'])
        report['results'][name] = {
            'archive_flights': source['archive_flights'],
            'eligible_flights': source['eligible_flights'],
            'eligible_segments': source['eligible_segments'],
            'excluded_segments': source['excluded_segments'],
            'fixed_flights': r['n_flights'], 'fixed_origins': r['n_origins'],
            'radial_p90_p25': dict(zip(map(str, tau.tolist()), ratio.tolist(), strict=True)),
            'radial_ratio_max': {'lag_s': int(tau[ratio.argmax()]), 'ratio': float(ratio.max())},
            'radial_ratio_min': {'lag_s': int(tau[ratio.argmin()]), 'ratio': float(ratio.min())},
            'full_fit': r['fits']['full'],
            'all_fit_ranges': r['fits'],
            'marginal_collapse': dict(zip(('east', 'north', 'radial'), collapse, strict=True)),
            'joint_common_h': joint['exponent'],
            'joint_lags_s': [law['lag_s'] for law in joint['laws']],
            'joint_tail_masses': [law['tail_mass'] for law in joint['laws']],
            'joint_distance_min': float(positive_distances.min()),
            'joint_distance_max': float(positive_distances.max()),
            'joint_distance_first_last': float(actual_distance[0, -1]),
            'joint_total_variation': joint['total_variation'],
            'joint_means': [law['mean'] for law in joint['laws']],
            'joint_covariance_eigenvalues': [np.linalg.eigvalsh(law['covariance']).tolist() for law in joint['laws']],
            'observed_path_closure': observed_closure,
            'tasks': general['tasks'], 'alpha': general['alpha'],
            'fixed_alpha': general['fixed_alpha'],
            'mardia_range': [min(general['mardia']), max(general['mardia'])],
            'vacf_at_600s': {k: v for k, v in general.items() if k.startswith('vacf_')},
        }
    target = Path(__file__).with_name('chapter3-results-audit.json')
    target.write_text(json.dumps(report, indent=2, allow_nan=False)+'\n')
    print(f'Full Chapter 3 identities, support, quantiles and joint-law checks passed: {target}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
