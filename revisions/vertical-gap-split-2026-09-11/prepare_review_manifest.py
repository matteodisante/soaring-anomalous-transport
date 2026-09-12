"""Identify already generated results newly used by the manuscript review.

Run AFTER numerical completion and BEFORE manuscript editing. Preserve the original
release manifest; extend a separate review input manifest only with outputs of
completed, unchanged generators, checking freshness and hashes. This permits the
new low-relief figure to enter the thesis without rerunning its numerical producer.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import runpy
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
EXTRA_OUTPUTS = (
    'kinematic_isotropy_flat_level.pdf',
    'ch3_revision.json',
    'ch3_self_similarity.json',
)


def prepare(run):
    path = run / 'manifest.json'
    original = path.read_bytes()
    manifest = json.loads(original)
    source_root = Path(manifest.get('source_root', ROOT))
    sys.path.insert(0, str(source_root / 'src'))
    driver = runpy.run_path(str(source_root / 'scripts/rebuild_thesis.py'))
    if manifest['status'] != 'complete' or not manifest.get('pdf_sha256'):
        raise ValueError('The numerical run must finish, including its PDF')
    if driver['source_hash'](source_root) != manifest['source_sha256']:
        raise ValueError('Capture additional outputs before editing the manuscript')
    reviewer = runpy.run_path(str(source_root / 'scripts/review_thesis.py'))
    reviewer['validate_results'](source_root, manifest, set(driver['required_outputs']()))
    for name, discipline in driver['DISCIPLINES'].items():
        if driver['validate_snapshot'](discipline.config().derived_dir, manifest['cleaning']) != manifest['datasets'][name]:
            raise ValueError(f'{name}: cleaned archive changed')
    provenance = runpy.run_path(str(source_root / 'scripts/reporting/checks/generate_provenance.py'))
    writers = provenance['writers']()
    completed = {s['command'][1]: s['started_unix'] for s in manifest['stages']
                 if s['status'] == 'complete' and s['command'][1].endswith('.py')}
    additions = driver['check_fresh_outputs'](
        {name: writers[name] for name in EXTRA_OUTPUTS}, completed, set(),
        source_root / 'thesis/generated',
    )
    pdf = source_root / 'thesis/main.pdf'
    if hashlib.sha256(pdf.read_bytes()).hexdigest() != manifest['pdf_sha256']:
        raise ValueError('The original numerical-run PDF has changed')
    target = run / 'review-inputs'
    target.mkdir()
    (target / 'numerical-manifest-original.json').write_bytes(original)
    shutil.copy2(pdf, target / 'thesis-before-review.pdf')
    expanded = copy.deepcopy(manifest)
    expanded['outputs'].update(additions)
    expanded['review_input_extension'] = {
        'scope': 'Additional existing outputs from the same completed numerical run; no numerical recomputation',
        'original_manifest': str(path),
        'original_manifest_sha256': hashlib.sha256(original).hexdigest(),
        'additional_outputs': additions,
        'generator_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    }
    driver['write_json'](target / 'manifest.json', expanded)
    print(f'Review input manifest: {target / "manifest.json"}')
    print(f'Compile the edited manuscript with {source_root / "scripts/review_thesis.py"} --run {target}')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', required=True, type=Path)
    prepare(parser.parse_args().run.resolve())
