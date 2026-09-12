"""Local fault injection for recovery gates; no SSD or canonical outputs touched."""
from __future__ import annotations

import importlib.util
import json
import pickle
from pathlib import Path

import numpy as np
import pytest

HERE = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location(
    'recovery_under_test', HERE / 'resume_after_ssd_disconnect.py'
)
RECOVERY = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(RECOVERY)


@pytest.fixture
def store(tmp_path):
    # Two segments with a large gap, followed by a separate complete flight.
    positions = np.array([
        [0, 0], [1, 2], [3, 3], [6, 4],
        [100, 80], [102, 81], [105, 82], [109, 83],
        [0, 0], [-1, 3], [-3, 5], [-6, 8], [-10, 12],
    ], dtype=np.float64)
    positions.tofile(tmp_path / 'positions.bin')
    rows = [
        dict(flight_id='a', offset=0, length=8, segments=[[0, 4], [4, 8]], duration_s=30),
        dict(flight_id='b', offset=8, length=5, segments=[[0, 5]], duration_s=40),
    ]
    (tmp_path / 'flights.json').write_text(json.dumps(rows))
    with (tmp_path / 'measurement.pkl').open('wb') as stream:
        pickle.dump({}, stream)
    # Explicit legal starts: the 3->4 transition must never enter a pool.
    specifications = [
        (1, [0, 1, 2, 4, 5, 6, 8, 9, 10, 11], [0]*6 + [1]*4),
        (2, [0, 4, 8, 10], [0, 0, 1, 1]),
        (10, [], []),
    ]
    counts = []
    for j, (lag, starts, owners) in enumerate(specifications):
        starts = np.array(starts, dtype=int)
        (positions[starts+lag] - positions[starts]).tofile(tmp_path / f'vectors-{j}.bin')
        np.array(owners, dtype=np.int32).tofile(tmp_path / f'owners-{j}.bin')
        counts.append(len(starts))
    (tmp_path / 'counts.json').write_text(json.dumps(counts))
    return tmp_path


def test_complete_segment_aware_store_passes(store):
    result = RECOVERY.validate_store(store, [10, 20, 100])
    assert result['flights'] == 2
    assert result['positions'] == 13


def test_incomplete_store_rejected(store):
    (store / '.incomplete').touch()
    with pytest.raises(ValueError, match='incomplete'):
        RECOVERY.validate_store(store, [10, 20, 100])


@pytest.mark.parametrize('mutation', ['truncate', 'append'])
def test_wrong_pool_size_rejected(store, mutation):
    path = store / 'vectors-0.bin'
    original = path.read_bytes()
    path.write_bytes(original[:-8] if mutation == 'truncate' else original + b'12345678')
    with pytest.raises(ValueError, match='pool byte size'):
        RECOVERY.validate_store(store, [10, 20, 100])


def test_finite_cross_gap_increment_rejected(store):
    path = store / 'vectors-0.bin'
    vectors = np.fromfile(path, dtype=np.float64).reshape(-1, 2)
    vectors[2] = [94, 76]  # 3->4 is finite, but crosses the recording gap.
    vectors.tofile(path)
    with pytest.raises(AssertionError):
        RECOVERY.validate_store(store, [10, 20, 100])


def test_nonfinite_coordinate_rejected(store):
    path = store / 'positions.bin'
    positions = np.fromfile(path, dtype=np.float64)
    positions[0] = np.nan
    positions.tofile(path)
    with pytest.raises(ValueError, match='Non-finite coordinates'):
        RECOVERY.validate_store(store, [10, 20, 100])


def test_owner_corruption_rejected(store):
    path = store / 'owners-0.bin'
    owners = np.fromfile(path, dtype=np.int32)
    owners[1] = 1
    owners.tofile(path)
    with pytest.raises(ValueError, match='Unordered increment owners'):
        RECOVERY.validate_store(store, [10, 20, 100])


def test_segment_metadata_corruption_rejected(store):
    path = store / 'flights.json'
    rows = json.loads(path.read_text())
    rows[0]['segments'][1][0] = 3
    path.write_text(json.dumps(rows))
    with pytest.raises(ValueError, match='retained-segment ranges'):
        RECOVERY.validate_store(store, [10, 20, 100])


def test_staged_file_change_rejected(tmp_path):
    source = tmp_path / 'source'
    source.write_bytes(b'original')
    target = tmp_path / 'staged'
    proof = RECOVERY.copy_checked(source, target)
    RECOVERY.verify_staged_inputs([proof])
    target.write_bytes(b'changed!')  # Same byte count still must fail.
    with pytest.raises(ValueError, match='Staged input changed'):
        RECOVERY.verify_staged_inputs([proof])


def test_changed_link_target_rejected(tmp_path):
    source = tmp_path / 'source'
    source.write_bytes(b'original')
    alternate = tmp_path / 'alternate'
    alternate.write_bytes(source.read_bytes())
    target = tmp_path / 'linked'
    target.symlink_to(source)
    proof = dict(source=str(source), target=str(target), bytes=8,
                 sha256=RECOVERY.digest(source), operation='read-only input link')
    RECOVERY.verify_staged_inputs([proof])
    target.unlink()
    target.symlink_to(alternate)
    with pytest.raises(ValueError, match='Staged input link changed'):
        RECOVERY.verify_staged_inputs([proof])
