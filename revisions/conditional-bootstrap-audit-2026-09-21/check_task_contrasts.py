"""Verify circuit-by-altitude fits and contrasts from the separate main report."""
from pathlib import Path
import json
import numpy as np
OUT=Path(__file__).resolve().parent
ROOT=OUT.parents[1]
r=json.loads((ROOT/'thesis/generated/ch3_transport_report.json').read_text())['results']['para']
f=np.load(OUT/'verified_replicates.npz')
x=np.log10(f['lags']); design=np.column_stack([np.ones(len(x)),x])
h={k:np.linalg.lstsq(design,np.log10(f[k]).T,rcond=None)[0][1]/2 for k in r['groups']}
for key, group in r['groups'].items():
    target=group['fit']['hurst']
    np.testing.assert_allclose([h[key][0],*np.percentile(h[key][1:],[5,95])],
        [target['point'],target['low'],target['high']],atol=2e-14,rtol=0)
for key,target in r['hurst_contrasts'].items():
    if key.startswith('open_minus_closed_'):
        i=key.rsplit('_',1)[1]; a,b=f'open_{i}',f'closed_{i}'
    else:
        a,j=key.split('_minus_'); b=a.split('_')[0]+'_'+j
    delta=h[a]-h[b]
    np.testing.assert_allclose([delta[0],*np.percentile(delta[1:],[5,95])],
        [target['point'],target['low'],target['high']],atol=2e-14,rtol=0)
json.dump({'all_8_fits_match':True,'all_12_contrasts_match':True},(OUT/'task_contrasts.json').open('w'),indent=2)
print('PASS: 8 circuit-altitude fits and 12 paired contrasts.')
