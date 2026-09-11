"""A failed or stale scientific rebuild must never be reported as complete."""

import json
import runpy
import time
from pathlib import Path

import pandas as pd
import pytest

from soaring.reporting.snapshot import (
    TABLES,
    dataset_identity,
    validate_snapshot,
    write_json,
)

ROOT = Path(__file__).resolve().parents[2]
DRIVER = runpy.run_path(str(ROOT / "scripts/rebuild_thesis.py"))


@pytest.fixture
def snapshot(tmp_path):
    for name in TABLES:
        pd.DataFrame({"value": [1.0]}).to_parquet(tmp_path / name)
    definition = {"pipeline_version": "test", "configuration": {"bound": 10}}
    manifest = {
        "status": "complete",
        "limit": 0,
        "cleaning": definition,
        "tables": dataset_identity(tmp_path),
    }
    write_json(tmp_path / "run_manifest.json", manifest)
    return tmp_path, definition


def test_current_snapshot_is_accepted_but_replaced_table_is_rejected(snapshot):
    directory, definition = snapshot
    validate_snapshot(directory, definition)
    pd.DataFrame({"value": [2.0, 3.0]}).to_parquet(directory / "fixes.parquet")
    with pytest.raises(ValueError, match="Tables changed"):
        validate_snapshot(directory, definition)


def test_changed_cleaning_or_partial_run_cannot_enter_reporting(snapshot):
    directory, definition = snapshot
    with pytest.raises(ValueError, match="code/configuration changed"):
        validate_snapshot(directory, {**definition, "configuration": {"bound": 30}})
    (directory / ".run_incomplete").write_text("interrupted")
    with pytest.raises(ValueError, match="Unfinished cleaning"):
        validate_snapshot(directory, definition)


def test_sampled_cleaning_is_not_mistaken_for_a_full_archive(snapshot):
    directory, definition = snapshot
    path = directory / "run_manifest.json"
    value = json.loads(path.read_text())
    value["limit"] = 100
    write_json(path, value)
    with pytest.raises(ValueError, match="sampled"):
        validate_snapshot(directory, definition)


def test_success_exit_with_an_old_figure_is_a_failed_rebuild(tmp_path):
    (tmp_path / "figure.pdf").write_bytes(b"old figure")
    started = time.time() + 1
    with pytest.raises(ValueError, match="old output unchanged"):
        DRIVER["check_fresh_outputs"](
            {"figure.pdf": "report.py"}, {"report.py": started}, set(), tmp_path
        )


def test_dated_control_is_preserved_without_exempting_current_figures(tmp_path):
    (tmp_path / "control.json").write_text("{}")
    result = DRIVER["check_fresh_outputs"](
        {"control.json": "historical.py"}, {}, {"control.json"}, tmp_path
    )
    assert result["control.json"]["historical_control"]
    with pytest.raises(ValueError, match="No completed rebuild stage"):
        DRIVER["check_fresh_outputs"](
            {"control.json": "historical.py"}, {}, set(), tmp_path
        )


def test_dry_run_does_not_touch_dataset_or_create_output(tmp_path, monkeypatch):
    main = DRIVER["main"]
    monkeypatch.setitem(main.__globals__, "DISCIPLINES", {"missing": object()})
    assert main(["--clean", "--dry-run", "--audit-dir", str(tmp_path / "absent")]) == 0
    assert not (tmp_path / "absent").exists()


def test_child_failure_is_propagated_and_captured_in_log(tmp_path):
    import subprocess
    import sys

    log = tmp_path / "stage.log"
    with pytest.raises(subprocess.CalledProcessError):
        DRIVER["_run"](
            [sys.executable, "-c", "print('failed diagnostic'); raise SystemExit(7)"],
            log,
        )
    assert "failed diagnostic" in log.read_text()
