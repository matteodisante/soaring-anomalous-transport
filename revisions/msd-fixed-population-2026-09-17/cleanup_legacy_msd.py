"""Retire the four remaining MSD-only arrays in the earlier completed run."""
import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
BASE = Path('/Volumes/SSD_DISANTE/derived-audit/runs/20260910T221820Z-05d36ab4/arrays')
MANIFEST = HERE / 'SSD-PULIZIA-SUPPLEMENTO.json'
NAMES = ('msd_para.npz', 'msd_hang.npz', 'msd_segments_para.parquet', 'msd_segments_hang.parquet')
PATHS = [BASE / name for name in NAMES] + [BASE / ('._' + name) for name in NAMES]


def fingerprint(path):
    s = path.lstat()
    return {'bytes': s.st_size, 'mtime_ns': s.st_mtime_ns, 'inode': s.st_ino,
            'allocated_bytes': s.st_blocks * 512}


if sys.argv[1:] == ['--apply']:
    report = json.loads(MANIFEST.read_text())
    assert report['status'] == 'prepared'
    assert [r['path'] for r in report['files']] == list(map(str, PATHS))
    check = subprocess.run(['/usr/sbin/lsof', '-nP', '+D', str(BASE)], capture_output=True, text=True)
    assert check.returncode == 1 and not check.stdout and not check.stderr
    for row, path in zip(report['files'], PATHS, strict=True):
        assert path.resolve() == path and not path.is_symlink()
        assert fingerprint(path) == {k: row[k] for k in fingerprint(path)}
    report['free_before'] = shutil.disk_usage(BASE).free
    for path in PATHS:
        if path.name.startswith('._') and not path.exists():
            continue
        path.unlink()
    report['free_after'] = shutil.disk_usage(BASE).free
    report['status'] = 'deleted'
    MANIFEST.write_text(json.dumps(report, indent=2) + '\n')
    print('Removed 4 legacy MSD caches and 4 sidecars:', sum(r['allocated_bytes'] for r in report['files']) / 2**30, 'GiB')
else:
    assert not sys.argv[1:] and not MANIFEST.exists()
    records = []
    for path in PATHS:
        with path.open('rb') as stream:
            sha = hashlib.file_digest(stream, 'sha256').hexdigest()
        records.append({'path': str(path), **fingerprint(path), 'sha256': sha})
    report = {'status': 'prepared', 'reason': 'Remaining old transport-only arrays; chapter 2 reads audit_positions/audit_flights, PCA reads coordinates. Preserve those shared inputs and historical PCA sample.', 'files': records}
    MANIFEST.write_text(json.dumps(report, indent=2) + '\n')
    print(len(records), 'files,', sum(r['allocated_bytes'] for r in records) / 2**30, 'GiB')
