"""Verify the completed replacement archive before the downstream rebuild."""
import json
from pathlib import Path
import pandas as pd
import pyarrow.parquet as pq
from soaring.reporting import DISCIPLINES
from soaring.analysis.preproc.resample import DROP_INCOMPLETE
from soaring.reporting.snapshot import current_cleaning, validate_snapshot

root = Path(__file__).resolve().parents[2]
expected = current_cleaning(root)
results = {}
for name, glider in DISCIPLINES.items():
    directory = glider.derived_dir()
    manifest = validate_snapshot(directory, expected)
    meta = pd.read_parquet(directory / 'flights_meta.parquet')
    segments = pd.read_parquet(directory / 'segments.parquet')
    kept = meta.drop_stage.isna()
    supported = meta.loc[kept]
    violations = supported.z_gap_max_s > supported.g_max_s + 1e-7
    checked = json.loads(Path(__file__).with_name('flagged-support-audit.json').read_text())
    checked_by_id = {row['flight_id']: row for row in checked}
    for fid in supported.loc[violations, 'flight_id'].astype(str):
        if fid not in checked_by_id or checked_by_id[fid]['true_support_violations']:
            raise ValueError(f'{name}: unexplained flagged-run exceedance for {fid}')
    results[name] = {
        'attempted': len(meta), 'retained': int(kept.sum()),
        'segments_kept': int(segments.kept.sum()),
        'fixes_kept': manifest['tables']['fixes.parquet']['rows'],
        'z_gap_max_s': float(supported.z_gap_max_s.max()),
        'reconstructed_runs_above_60s': int((supported.z_gap_max_s > 60).sum()),
        'pipeline_versions': sorted(meta.pipeline_version.dropna().unique()),
        'flag_runs_above_threshold': int(violations.sum()),
        'exceedance_flights_checked_from_raw': supported.loc[violations, 'flight_id'].astype(str).tolist(),
        'true_support_violations_in_checked_flights': 0,
        'incomplete_candidates': int((segments.drop_reason == DROP_INCOMPLETE).sum()),
        'cleaning_source_sha256': expected['source_sha256'],
    }
    if glider.slug == 'para':
        case = pq.read_table(directory / 'fixes.parquet',
                             columns=['flight_id', 'segment_id', 't', 'z_reconstructed'],
                             filters=[('flight_id', '=', '20171597')]).to_pandas()
        if case.empty or case.t.between(6806, 7449).any():
            raise ValueError('Witness flight missing or former 644 s hole retained')
        results[name]['witness_20171597'] = {
            'segments': case.groupby('segment_id').t.agg(['min','max','count']).reset_index().to_dict('records'),
            'z_gap_max_s': float(meta.loc[meta.flight_id.astype(str) == '20171597', 'z_gap_max_s'].iloc[0]),
            'formerly_reconstructed_interval_absent': True,
        }
path = Path(__file__).with_name('after-cleaning.json')
path.write_text(json.dumps(results, indent=2) + '\n')
print(json.dumps(results, indent=2), flush=True)
