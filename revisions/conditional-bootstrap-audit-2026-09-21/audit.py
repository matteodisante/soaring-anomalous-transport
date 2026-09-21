"""Independent numerical audit of Section 3.2; source data remain untouched."""
from pathlib import Path
import hashlib
import json
import sys
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent
DATA = Path('/Volumes/SSD_DISANTE/derived-audit/chapter3-fixed-20260917')
RUN = ROOT / 'revisions/conditional-transport-2026-09-19/run-altitude'
sys.path.insert(0, str(ROOT / 'src'))
from soaring.analysis.observables.conditional_transport import strata

report = json.loads((ROOT / 'thesis/generated/ch3_conditional.json').read_text())
assert report == json.loads((RUN / 'report.json').read_text())
checks = {}
for name, entry in report['source_files'].items():
    if not isinstance(entry, dict):
        continue
    with Path(entry['path']).open('rb') as stream:
        actual = hashlib.file_digest(stream, 'sha256').hexdigest()
    assert actual == entry['sha256'], name
    checks[name] = actual
print('All 5 source-file hashes match.', flush=True)
frame = pd.read_parquet(DATA / 'para/flights.parquet')
cohort = frame.cohort_10000.to_numpy(bool)
members = frame.loc[cohort]
manifest = json.loads((DATA / 'para/cohort-10000.json').read_text())
np.testing.assert_array_equal(np.flatnonzero(cohort), [r['frame_index'] for r in manifest['members']])
np.testing.assert_array_equal(members.flight_id.astype(str), [r['flight_id'] for r in manifest['members']])
with np.load(DATA / 'para/msd.npz') as msd:
    source_lags = msd['lags']
    take = np.flatnonzero(np.isin(source_lags, report['lags_s']))
    baseline = msd['curves'][:, 3, take]
lags = np.asarray(report['lags_s'])
np.testing.assert_array_equal(source_lags[take], lags)
values = np.load(DATA / 'para/flight-msd.npy', mmap_mode='r')[cohort, 3][:, take]
assert np.isfinite(values).all() and (values > 0).all()
labels = members.cluster.to_numpy(int)
draws = np.load(DATA / 'para/cluster-draws.npy', mmap_mode='r')
B, G = draws.shape[0] - 1, draws.shape[1]
assert B == 1000 and np.all(draws[0] == 1)
assert np.all(draws[1:].sum(axis=1) == G)
# Verify actual site-day keys agree exactly with cluster identities.
known = ~frame.cluster_missing.to_numpy(bool)
keys = frame.loc[known, ['cluster_site', 'cluster_date', 'cluster']]
assert keys.groupby('cluster').ngroups == keys.drop_duplicates(['cluster_site', 'cluster_date']).shape[0]
assert keys.groupby('cluster')[['cluster_site', 'cluster_date']].nunique().to_numpy().max() == 1
assert keys.groupby(['cluster_site', 'cluster_date']).cluster.nunique().max() == 1
missing_labels = frame.loc[~known, 'cluster']
assert not missing_labels.duplicated().any()
assert not np.isin(missing_labels, frame.loc[known, 'cluster']).any()
# Independently recreate the original seeded sampling, including all empty-for-cohort groups.
rng = np.random.default_rng(20260917)
for b in range(1, B + 1):
    picked = rng.choice(G, size=G, replace=True)
    np.testing.assert_array_equal(np.bincount(picked, minlength=G), draws[b])
print(f'All {B} draws exactly reproduced; {G} site-day groups.', flush=True)
mask_map = strata(members)
membership = pd.read_parquet(RUN / 'membership.parquet')
np.testing.assert_array_equal(membership.flight_id, members.flight_id)
for name, mask in mask_map.items():
    np.testing.assert_array_equal(mask, membership[name])
assert set(mask_map) == set(report['groups'])
archived = np.load(RUN / 'replicates.npz')
np.testing.assert_array_equal(archived['lags'], lags)
x = np.log10(lags)
design = np.column_stack([np.ones(len(x)), x])

def h_fit(curves):
    return np.linalg.lstsq(design, np.log10(curves).T, rcond=None)[0][1] / 2

def bounds(a):
    return np.percentile(a[1:], [5, 95], axis=0, method='linear')

rows, h_replicates, fresh_curves = [], {}, {}
max_curve_error, max_h_error = 0., 0.
for name, mask in mask_map.items():
    selected, owners = values[mask], labels[mask]
    # Direct flight-level weighted mean: does not call bootstrap_means or group-sum reducer.
    calculated = np.empty((B + 1, len(lags)))
    sizes = np.empty(B + 1)
    for start in range(0, B + 1, 64):
        weights = np.asarray(draws[start:start + 64, owners], dtype=float)
        sizes[start:start + 64] = weights.sum(axis=1)
        calculated[start:start + 64] = (weights @ selected) / sizes[start:start + 64, None]
    saved = archived[name]
    np.testing.assert_allclose(calculated, saved, rtol=2e-12, atol=0)
    max_curve_error = max(max_curve_error, float(np.max(np.abs(calculated / saved - 1))))
    if name == 'all':
        np.testing.assert_allclose(calculated, baseline, rtol=2e-12, atol=0)
    row = report['groups'][name]
    q = bounds(calculated)
    np.testing.assert_allclose(calculated[0], row['msd']['point'], rtol=2e-12)
    np.testing.assert_allclose(q, [row['msd']['low'], row['msd']['high']], rtol=2e-12)
    h = h_fit(calculated)
    h_replicates[name] = h
    fresh_curves[name] = calculated
    hq = bounds(h)
    hp = row['fit']['hurst']
    np.testing.assert_allclose([h[0], *hq], [hp['point'], hp['low'], hp['high']], atol=2e-14, rtol=0)
    max_h_error = max(max_h_error, float(np.max(np.abs(np.r_[h[0], hq] - [hp['point'], hp['low'], hp['high']]))))
    assert row['valid_replicates'] == B and row['flights'] == int(mask.sum())
    unique, inverse, counts = np.unique(owners, return_inverse=True, return_counts=True)
    assert len(unique) == row['clusters']
    # Independent first-order cluster variance for a ratio mean (diagnostic only).
    residual_sums = np.zeros((len(unique), len(lags)))
    np.add.at(residual_sums, inverse, selected - selected.mean(axis=0))
    analytic_se = np.sqrt(np.sum(residual_sums ** 2, axis=0)) / len(selected)
    se_ratio = np.std(calculated[1:], axis=0, ddof=1) / analytic_se
    result = dict(group=name, flights=len(selected), clusters=len(unique),
        min_resampled_flights=int(sizes[1:].min()), max_resampled_flights=int(sizes[1:].max()),
        largest_cluster_fraction=float(counts.max()/len(selected)),
        H=float(h[0]), H_low=float(hq[0]), H_high=float(hq[1]),
        bootstrap_vs_linearized_se_min=float(se_ratio.min()),
        bootstrap_vs_linearized_se_max=float(se_ratio.max()))
    for lag in [10, 100, 1000, 10000]:
        j = int(np.flatnonzero(lags == lag)[0])
        result[f'full_band_width_pct_at_{lag}'] = float(100 * (q[1,j] - q[0,j]) / calculated[0,j])
        result[f'band_log10_width_at_{lag}'] = float(np.log10(q[1,j] / q[0,j]))
    rows.append(result)
print(f'All {len(rows)} groups x 1000 replicates x {len(lags)} lags independently reconstructed.', flush=True)
for name, contrast in report['contrasts'].items():
    diff = sum(w * h_replicates[k] for k,w in contrast['terms'])
    q = bounds(diff)
    target = contrast['hurst']
    np.testing.assert_allclose([diff[0], *q], [target['point'],target['low'],target['high']], atol=3e-14, rtol=0)
print(f'All {len(report["contrasts"])} paired contrasts match.', flush=True)
# The circuit-by-altitude figure uses the main report: verify all three plotted arrays too.
main = json.loads((ROOT / 'thesis/generated/ch3_transport_report.json').read_text())
for name in [f'{task}_{i}' for task in ('open', 'closed') for i in range(4)]:
    for field in ('point', 'low', 'high'):
        np.testing.assert_allclose(main['results']['para']['groups'][name]['curve'][field], report['groups'][name]['msd'][field], rtol=2e-12)
# Check exported CSVs, not just the JSON used by plotting.
csv = pd.read_csv(ROOT / 'thesis/generated/ch3_conditional_curves.csv')
fitcsv = pd.read_csv(ROOT / 'thesis/generated/ch3_conditional_fits.csv').set_index('group')
for name in mask_map:
    part = csv[csv.group == name]
    np.testing.assert_array_equal(part.lag_s, lags)
    for field in ('point','low','high'):
        np.testing.assert_allclose(part[field], report['groups'][name]['msd'][field], rtol=2e-12)
    hp = report['groups'][name]['fit']['hurst']
    np.testing.assert_allclose(fitcsv.loc[name, ['H','H_low','H_high']].astype(float), [hp['point'],hp['low'],hp['high']], atol=1e-14)
pd.DataFrame(rows).to_csv(OUT / 'band_widths.csv', index=False)
json.dump(dict(source_hashes=checks, groups=len(rows), replicates=B, lags=len(lags),
    contrasts=len(report['contrasts']), max_relative_curve_error=max_curve_error,
    max_absolute_H_error=max_h_error, archived_draws_exact=True,
    all_report_percentiles_match=True, all_exported_csv_values_match=True),
    (OUT / 'audit.json').open('w'), indent=2)
# Preserve compact independent reconstructions for sensitivity and visualization.
np.savez_compressed(OUT / 'verified_replicates.npz', lags=lags, **fresh_curves)
print('Numerical audit PASS.', flush=True)
