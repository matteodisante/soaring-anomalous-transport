"""Preserve complete full-archive JSON bytes in deterministic gzip files.

Execute only after the run and its expanded review-input manifest are complete.
The canonical generated JSON files remain untouched. This avoids committing huge
duplicate archive indexes while retaining every value and flight identity.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
HERE=Path(__file__).resolve().parent
REPORTS=('ch3_revision.json','ch3_self_similarity.json')


def digest(data): return hashlib.sha256(data).hexdigest()


def archive(run,out):
    manifest_path=run/'review-inputs/manifest.json'
    manifest=json.loads(manifest_path.read_text())
    if manifest['status']!='complete' or not manifest.get('review_input_extension'):
        raise ValueError('Complete numerical run and expanded review inputs are required')
    records={}
    for name in REPORTS:
        raw=(ROOT/'thesis/generated'/name).read_bytes()
        expected=manifest['outputs'][name]
        expected=expected['sha256'] if isinstance(expected,dict) else expected
        if digest(raw)!=expected:
            raise ValueError(f'{name}: bytes no longer match the reviewed numerical inputs')
        data=json.loads(raw)
        contract=data.get('measurement_contract',data.get('identity',{}).get('source_contract'))
        if contract['scope']!='full eligible archive':
            raise ValueError('Only full-archive reports belong in this archive')
        compressed=gzip.compress(raw,compresslevel=9,mtime=0)
        if gzip.decompress(compressed)!=raw:
            raise ValueError('Compression round-trip changed report bytes')
        records[name]={'raw_sha256':digest(raw),'raw_size_bytes':len(raw),
                       'gzip_sha256':digest(compressed),'gzip_size_bytes':len(compressed),
                       'archive_name':name+'.gz'}
        out.mkdir(parents=True,exist_ok=True)
        target=out/(name+'.gz')
        if target.exists() and target.read_bytes()!=compressed:
            raise ValueError(f'Refusing to replace a different identified report: {target}')
        if not target.exists():
            target.write_bytes(compressed)
    record={'operation':__doc__,'numerical_run':str(run),'numerical_source_sha256':manifest['numerical_source_sha256'],
            'review_input_manifest':str(manifest_path),'review_input_manifest_sha256':digest(manifest_path.read_bytes()),
            'script_sha256':digest(Path(__file__).read_bytes()),'reports':records}
    (out/'manifest.json').write_text(json.dumps(record,indent=2)+'\n')
    print(json.dumps(records,indent=2))


def restore(directory):
    manifest=json.loads((directory/'manifest.json').read_text())
    for name,row in manifest['reports'].items():
        compressed=(directory/row['archive_name']).read_bytes()
        if digest(compressed)!=row['gzip_sha256']:
            raise ValueError(f'{name}: compressed archive changed')
        raw=gzip.decompress(compressed)
        if digest(raw)!=row['raw_sha256'] or len(raw)!=row['raw_size_bytes']:
            raise ValueError(f'{name}: restored bytes do not match the original')
        target=ROOT/'thesis/generated'/name
        if target.exists() and target.read_bytes()!=raw:
            raise ValueError(f'Refusing to overwrite a different current report: {target}')
        if not target.exists():
            target.write_bytes(raw)
    print('Original complete JSON reports restored with matching byte hashes.')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    mode=parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--run',type=Path)
    mode.add_argument('--restore',type=Path)
    parser.add_argument('--out',type=Path,default=HERE/'full-report-archive')
    args=parser.parse_args()
    if args.restore: restore(args.restore)
    else: archive(args.run,args.out)
