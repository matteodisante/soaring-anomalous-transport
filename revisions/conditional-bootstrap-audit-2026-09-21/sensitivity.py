"""Conditional uncertainty sensitivity; diagnostic only, no published output replaced."""
from pathlib import Path
import json
import sys
import numpy as np
import pandas as pd
ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent
DATA = Path('/Volumes/SSD_DISANTE/derived-audit/chapter3-fixed-20260917')
sys.path.insert(0, str(ROOT / 'src'))
from soaring.analysis.observables.conditional_transport import strata
from soaring.analysis.observables.bootstrap_reliability import calendar_blocks
from soaring.analysis.observables.grid_bootstrap import project_launches, cell_membership, grid_season_labels
frame = pd.read_parquet(DATA / 'para/flights.parquet')
cohort = frame.cohort_10000.to_numpy(bool)
members = frame.loc[cohort]
masks = strata(members)
r = json.loads((ROOT / 'thesis/generated/ch3_conditional.json').read_text())
main = json.loads((ROOT / 'thesis/generated/ch3_transport_report.json').read_text())['results']['para']
for key in main['hurst_contrasts']:
    if key.startswith('open_minus_closed_'):
        i = key.rsplit('_', 1)[1]
        a, b = f'open_{i}', f'closed_{i}'
    else:
        a, j = key.split('_minus_')
        b = a.split('_')[0] + '_' + j
    r['contrasts']['circuit_altitude_' + key] = {'terms': [(a, 1), (b, -1)]}
ref = np.load(OUT / 'verified_replicates.npz')
lags = ref['lags']
with np.load(DATA / 'para/msd.npz') as f:
    take = np.flatnonzero(np.isin(f['lags'], lags))
values = np.load(DATA / 'para/flight-msd.npy', mmap_mode='r')[cohort,3][:,take]
x = np.log10(lags)
c = (x - x.mean()) / np.sum((x-x.mean())**2) / 2

def hfit(curve):
    return np.log10(curve) @ c

def stats(a):
    return {'point': float(a[0]), 'low':float(np.percentile(a[1:],5)),
            'high':float(np.percentile(a[1:],95)), 'se':float(np.std(a[1:],ddof=1))}

configs = {}
for days in (1,3):
    labels, missing = calendar_blocks(frame.date, days)
    assert not missing[cohort].any()
    configs[f'calendar_{days}day_all_sites'] = labels
cells = cell_membership(project_launches(frame), 50)
labels, missing = grid_season_labels(frame,cells)
assert not missing[cohort].any()
configs['grid50km_altitude_month_all_years'] = labels
rows, contrast_rows = [], []
for name, labels in configs.items():
    G = int(labels.max())+1
    selected_labels = labels[cohort]
    for seed in (20260921,20260922):
        rng = np.random.default_rng(seed)
        weights = np.ones((1001,G))
        for b in range(1,1001):
            weights[b] = np.bincount(rng.choice(G, size=G, replace=True),minlength=G)
        hs = {}
        for key, mask in masks.items():
            owners = selected_labels[mask]
            sums = np.zeros((G,len(lags)))
            np.add.at(sums,owners,values[mask])
            counts = np.bincount(owners,minlength=G)
            denominator = weights @ counts
            assert (denominator > 0).all()
            curve = (weights @ sums) / denominator[:,None]
            np.testing.assert_allclose(curve[0],ref[key][0],rtol=2e-12)
            hs[key] = hfit(curve)
            h, orig = stats(hs[key]), stats(hfit(ref[key]))
            row = dict(configuration=name,seed=seed,group=key,
                archive_groups=G, contributing_groups=int(np.count_nonzero(counts)),
                H=h['point'],H_low=h['low'],H_high=h['high'],
                H_se_ratio=h['se']/orig['se'],
                H_interval_width_ratio=(h['high']-h['low'])/(orig['high']-orig['low']))
            for lag in (100,1000,10000):
                j = int(np.flatnonzero(lags==lag)[0])
                a, original = stats(curve[:,j]), stats(ref[key][:,j])
                row[f'MSD_se_ratio_at_{lag}']=a['se']/original['se']
                row[f'full_band_width_pct_at_{lag}']=100*(a['high']-a['low'])/a['point']
            rows.append(row)
        for key, entry in r['contrasts'].items():
            a = sum(weight*hs[group] for group,weight in entry['terms'])
            h = stats(a)
            orig = stats(sum(weight*hfit(ref[group]) for group,weight in entry['terms']))
            contrast_rows.append(dict(configuration=name,seed=seed,contrast=key,**h,
                se_ratio=h['se']/orig['se'],contains_zero=h['low']<=0<=h['high'],
                site_day_contains_zero=orig['low']<=0<=orig['high']))
        print(name,seed,'completed',flush=True)
pd.DataFrame(rows).to_csv(OUT/'sensitivity.csv',index=False)
pd.DataFrame(contrast_rows).to_csv(OUT/'sensitivity_contrasts.csv',index=False)
print('Sensitivity calculations completed.',flush=True)
