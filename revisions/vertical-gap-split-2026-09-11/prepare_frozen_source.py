"""Copy a stable source snapshot without changing the working manuscript."""
import hashlib
import importlib.util
import json
import shutil
from pathlib import Path

root = Path(__file__).resolve().parents[2]
parent = Path('/Volumes/SSD_DISANTE/derived-audit/runs/20260911T204919Z-a9801d6d')
manifest = json.loads((parent/'manifest.json').read_text())
spec = importlib.util.spec_from_file_location('original_rebuild', root/'scripts/rebuild_thesis.py')
driver = importlib.util.module_from_spec(spec)
spec.loader.exec_module(driver)
if driver.numerical_source_hash(root) != manifest['numerical_source_sha256']:
    raise ValueError('Numerical changes forbid reuse of completed stages')
before = driver.source_hash(root)
target = Path(__file__).with_name('frozen-source')
target.mkdir(exist_ok=True)
for name in ('src', 'scripts', 'configs', 'thesis', 'docs', 'annotations', '.agents'):
    source = root/name
    if source.exists():
        shutil.copytree(source, target/name, dirs_exist_ok=True, symlinks=True,
                        ignore=shutil.ignore_patterns('__pycache__', '.DS_Store', '._*'))
for name in ('uv.lock', 'pyproject.toml', 'README.md', 'CONTEXT.md', 'AGENTS.md', '.env'):
    source = root/name
    if source.exists():
        shutil.copy2(source, target/name)
if not (target/'.venv').exists():
    (target/'.venv').symlink_to(root/'.venv', target_is_directory=True)
after = driver.source_hash(root)
if before != after or driver.source_hash(target) != before:
    raise ValueError('Source changed during copying; recopy the snapshot before running')
if driver.numerical_source_hash(target) != manifest['numerical_source_sha256']:
    raise ValueError('Frozen numerical source differs from the completed prefix')
record = {
    'source_root':str(target), 'working_root':str(root), 'parent_run':str(parent),
    'parent_manifest_sha256':hashlib.sha256((parent/'manifest.json').read_bytes()).hexdigest(),
    'source_sha256':before, 'numerical_source_sha256':manifest['numerical_source_sha256'],
    'reason':'working manuscript changed; numerical sources and completed stages unchanged',
}
Path(__file__).with_name('frozen-source.json').write_text(json.dumps(record,indent=2)+'\n')
print(json.dumps(record,indent=2))
