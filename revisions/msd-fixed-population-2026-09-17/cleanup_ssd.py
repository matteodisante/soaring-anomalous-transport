"""Delete only the audited experiment caches; never remove directories or glob matches."""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import stat
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SSD = Path('/Volumes/SSD_DISANTE')
AUDIT = SSD / 'derived-audit'
MANIFEST = HERE / 'SSD-PULIZIA-ESECUZIONE.json'


def fingerprint(path):
    s = path.lstat()
    return {'bytes': s.st_size, 'mtime_ns': s.st_mtime_ns,
            'inode': s.st_ino, 'device': s.st_dev, 'allocated_bytes': s.st_blocks * 512}


def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def dump(payload):
    MANIFEST.write_text(json.dumps(payload, indent=2) + '\n')


def allowed(path):
    """Separate broad archive protection from the exact manifest allowlist."""
    assert path.is_absolute() and path.resolve() == path and path.is_relative_to(AUDIT)
    assert not path.is_symlink() and stat.S_ISREG(path.lstat().st_mode)
    assert not any(part in ('viewer', 'raw', 'segmentation', 'cleaning', 'external-data') for part in path.parts)
    base = path.name.removeprefix('._')
    assert base not in ('positions.bin', 'flights.json', 'counts.json', 'measurement.pkl')
    assert not base.startswith('audit_')
    if path.parent == AUDIT:
        assert base.startswith(('msd_', 'variations_', 'variation_flights_', 'propagator_', 'shape_')) or base == 'ch3_revision_sample.pkl'
    else:
        run = AUDIT / 'runs/20260911T213634Z-7b7367f1/arrays'
        assert path.parent in (run, run / 'ch3-full-para', run / 'ch3-full-hang')
        assert base.startswith(('vectors-', 'owners-', 'scaling-values-', 'msd_'))


def prepare():
    assert not MANIFEST.exists(), 'Do not overwrite a prepared/executed manifest'
    estimate = json.loads((HERE / 'SSD-PULIZIA-PREVENTIVO.json').read_text())
    paths = []
    for row in estimate['candidate_files']:
        path = Path(row['path'])
        allowed(path)
        assert path.stat().st_size == row['logical_bytes']
        paths.append(path)
        sidecar = path.with_name('._' + path.name)
        if sidecar.is_file():
            allowed(sidecar)
            paths.append(sidecar)
    assert len(paths) == len(set(paths))
    def record(path):
        before = fingerprint(path)
        h = digest(path)
        assert fingerprint(path) == before
        return {'path': str(path), **before, 'sha256': h}
    with ThreadPoolExecutor(max_workers=2) as pool:
        candidates = list(pool.map(record, paths))
    print(f'{len(paths)} exact candidates fingerprinted', flush=True)
    excluded = set(paths)
    protected = {}
    for parent in (AUDIT, SSD / 'paragliders/ffvl_cfd_igc/derived', SSD / 'hang_gliders/delta_cfd_igc/derived'):
        for path in parent.rglob('*'):
            if path.is_file() and path not in excluded:
                assert path.resolve() not in excluded, f'Protected reference: {path}'
                protected[str(path)] = fingerprint(path)
    for archive in (SSD / 'paragliders/ffvl_cfd_igc', SSD / 'hang_gliders/delta_cfd_igc'):
        for path in archive.glob('*.csv'):
            protected[str(path)] = fingerprint(path)
    links = []
    for path in (ROOT / 'revisions').rglob('*'):
        if path.is_symlink() and path.resolve() in excluded:
            links.append({'path': str(path), 'target': str(path.resolve()), 'link_text': os.readlink(path)})
    payload = {
        'status': 'prepared', 'prepared_utc': datetime.now(timezone.utc).isoformat(),
        'scope': 'experiment caches only; viewer, raw, cleaning, segmentation, chapter 2, PCA and anisotropy protected',
        'free_bytes_before': shutil.disk_usage(SSD).free,
        'candidate_allocated_bytes': sum(r['allocated_bytes'] for r in candidates),
        'candidates': candidates, 'protected_files': protected, 'local_links_to_retire': links,
        'deleted': [], 'retired_links': [],
    }
    dump(payload)
    print(f'{len(protected)} protected files; {len(links)} local links; {payload["candidate_allocated_bytes"] / 2**30:.6f} GiB', flush=True)


def apply():
    payload = json.loads(MANIFEST.read_text())
    assert payload['status'] == 'prepared'
    assert (HERE / 'viewer-before.json').is_file(), 'Real-data viewer checks required'
    assert (HERE / 'pca-preserved/ch3_pca.json').is_file(), 'PCA regeneration required'
    preflight = subprocess.run(['/usr/sbin/lsof', '-nP', '+D', str(AUDIT)], capture_output=True, text=True)
    assert preflight.returncode == 1 and not preflight.stdout and not preflight.stderr, preflight.stdout + preflight.stderr
    for path, expected in payload['protected_files'].items():
        assert fingerprint(Path(path)) == expected, f'Protected input changed: {path}'
    for row in payload['candidates']:
        path = Path(row['path'])
        allowed(path)
        assert fingerprint(path) == {k: row[k] for k in fingerprint(path)}, f'Candidate changed: {path}'
    for row in payload['local_links_to_retire']:
        path = Path(row['path'])
        assert path.is_symlink() and os.readlink(path) == row['link_text']
    payload['status'] = 'deleting'
    payload['free_bytes_at_deletion'] = shutil.disk_usage(SSD).free
    dump(payload)
    for row in payload['candidates']:
        path = Path(row['path'])
        if path.name.startswith('._') and not path.exists():
            payload.setdefault('sidecars_removed_by_filesystem', []).append(str(path))
        else:
            path.unlink()
        payload['deleted'].append(str(path))
        dump(payload)
    for row in payload['local_links_to_retire']:
        path = Path(row['path'])
        path.unlink()
        payload['retired_links'].append(str(path))
    for path, expected in payload['protected_files'].items():
        assert fingerprint(Path(path)) == expected, f'Protected input changed: {path}'
    payload['status'] = 'deleted; awaiting post-cleanup viewer validation'
    payload['deleted_utc'] = datetime.now(timezone.utc).isoformat()
    payload['free_bytes_after'] = shutil.disk_usage(SSD).free
    dump(payload)
    print(json.dumps({k: payload[k] for k in ('status', 'candidate_allocated_bytes', 'free_bytes_at_deletion', 'free_bytes_after')}, indent=2))
    print(f'Deleted {len(payload["deleted"])} files; retired {len(payload["retired_links"])} local links; protected files unchanged')


if __name__ == '__main__':
    if sys.argv[1:] == ['--apply']:
        apply()
    elif not sys.argv[1:]:
        prepare()
    else:
        raise SystemExit('Usage: cleanup_ssd.py [--apply]')
