"""Check the saved evidence used to revise Section 3.2 interpretation."""
from pathlib import Path
import json
import numpy as np
import pandas as pd

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[1]
report = json.loads((ROOT / 'thesis/generated/ch3_conditional.json').read_text())
main = json.loads((ROOT / 'thesis/generated/ch3_transport_report.json').read_text())['results']['para']
membership = pd.read_parquet(ROOT / 'revisions/conditional-transport-2026-09-19/run-altitude/membership.parquet')
replicates = np.load(ROOT / 'revisions/conditional-bootstrap-audit-2026-09-21/verified_replicates.npz')
lags = replicates['lags']
x = np.log10(lags)
design = np.column_stack([np.ones(len(x)), x])
h = {key: np.linalg.lstsq(design, np.log10(replicates[key]).T, rcond=None)[0][1] / 2 for key in main['groups']}
for key, group in main['groups'].items():
    expected = group['fit']['hurst']
    np.testing.assert_allclose([h[key][0], *np.percentile(h[key][1:], [5, 95])], [expected['point'], expected['low'], expected['high']], atol=2e-14, rtol=0)
    assert int(membership[key].sum()) == group['flights']
contrasts = {}
for key, expected in main['hurst_contrasts'].items():
    if key.startswith('open_minus_closed_'):
        i = key.rsplit('_', 1)[1]
        left, right = f'open_{i}', f'closed_{i}'
    else:
        left, j = key.split('_minus_')
        right = left.split('_')[0] + '_' + j
    delta = h[left] - h[right]
    observed = [float(delta[0]), *np.percentile(delta[1:], [5, 95]).tolist()]
    np.testing.assert_allclose(observed, [expected['point'], expected['low'], expected['high']], atol=2e-14, rtol=0)
    assert observed[2] < 0 if left.startswith('closed') else observed[1] > 0
    contrasts[key] = observed
composition = {}
for key in ['alt0', 'alt1', 'alt2', 'alt3', 'alps', 'pyrenees', 'channel_coast', 'champagne_lorraine']:
    group = membership[membership[key]]
    assert len(group) == report['groups'][key]['flights']
    counts = {str(k): int(v) for k, v in group['task'].value_counts().items()}
    composition[key] = {'flights': len(group), 'circuit_counts': counts, 'open_percent': 100 * counts['open'] / len(group)}
long_lag_h = {}
for key in main['groups']:
    if key.startswith('closed'):
        mask = lags >= 1000
        long_h = float(np.polyfit(x[mask], np.log10(replicates[key][0, mask]), 1)[0] / 2)
        assert long_h < h[key][0]
        long_lag_h[key] = long_h
# Where there are no unclassified flights, independently check the mixture identity.
n = report['groups']['alt0']['flights']
mixed = sum(report['groups'][key]['flights'] * np.array(report['groups'][key]['msd']['point']) / n for key in ['open_0', 'closed_0'])
np.testing.assert_allclose(mixed, report['groups']['alt0']['msd']['point'], rtol=1e-13)
audit = {'fits_verified': len(h), 'paired_contrasts_verified': len(contrasts), 'contrasts_point_lower_upper': contrasts, 'composition': composition, 'closed_h_1000_10000_s': long_lag_h, 'plains_msd_mixture_identity_verified': True}
(OUT / 'evidence.json').write_text(json.dumps(audit, indent=2) + '\n')
print(json.dumps(audit, indent=2))
