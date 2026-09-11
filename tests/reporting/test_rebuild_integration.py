"""Exercise the workflow on isolated snapshots and real child processes."""

import hashlib
import json
import os
import runpy
import subprocess
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Event, Lock
from types import SimpleNamespace

import pandas as pd
import pytest

from soaring.reporting.snapshot import TABLES, dataset_identity, write_json

ROOT = Path(__file__).resolve().parents[2]

# Every planned producer has its own script path, as in the real workflow. The
# shared fixture body reads both miniarchives, logs its invocation, and can fail
# before replacing an existing output. No cleaning or LaTeX process is launched.
STAGE_SCRIPT = """
import hashlib
import json
import sys
from pathlib import Path

stage, action, output, audit, annotation, para, hang = sys.argv[1:]
inputs = {}
for name, directory in (("para", para), ("hang", hang)):
    data = (Path(directory) / "fixes.parquet").read_bytes()
    assert data[:4] == data[-4:] == b"PAR1"
    inputs[name] = hashlib.sha256(data).hexdigest()
record = dict(stage=stage, audit=audit, annotation=annotation, inputs=inputs)
with Path("trace.jsonl").open("a") as trace:
    trace.write(json.dumps(record) + "\\n")
print("fixture stage: " + stage, flush=True)
if action == "fail":
    print("intentional fixture failure", flush=True)
    raise SystemExit(7)
if action == "mutate-table":
    with (Path(hang) / "fixes.parquet").open("ab") as table:
        table.write(b"unexpected final-stage mutation")
if action == "mark-incomplete":
    (Path(hang) / ".run_incomplete").write_text("unexpected cleaning writer")
if action != "leave-old":
    Path(output).write_text(json.dumps(record))
"""


@pytest.fixture
def rebuild_workspace(tmp_path, monkeypatch):
    driver = runpy.run_path(str(ROOT / "scripts/rebuild_thesis.py"))
    main = driver["main"]
    root = tmp_path / "workspace"
    generated = root / "thesis/generated"
    generated.mkdir(parents=True)
    (root / "scripts").mkdir()
    cleaning = {"pipeline_version": "integration", "configuration": {"bound": 10}}
    archives = {}
    original_tables = {}
    for index, name in enumerate(("para", "hang"), start=1):
        archive = root / "data" / name
        raw = archive / "igc"
        raw.mkdir(parents=True)
        catalog = archive / "catalog.csv"
        catalog.write_text("flight_id\nfixture\n")
        derived = archive / "derived"
        derived.mkdir()
        for filename in TABLES:
            pd.DataFrame({"flight_id": [name], "value": [float(index)]}).to_parquet(
                derived / filename
            )
        identity = dataset_identity(derived)
        original_tables[name] = identity
        write_json(
            derived / "run_manifest.json",
            {
                "status": "complete",
                "limit": 0,
                "cleaning": cleaning,
                "tables": identity,
            },
        )
        archives[name] = SimpleNamespace(
            igc_dir=raw, catalog_path=catalog, derived_dir=derived
        )

    plan = {"stages": [], "historical_outputs": ["dated-control.json"]}
    required = {"dated-control.json": None}
    old_content = b"previous-run output\n"
    for name in ("first", "final", "later"):
        script = f"scripts/{name}.py"
        (root / script).write_text(STAGE_SCRIPT)
        (generated / f"{name}.json").write_bytes(old_content)
    control = generated / "dated-control.json"
    control.write_text('{"dated": true}\n')
    for path in generated.iterdir():
        os.utime(path, ns=(946684800_000_000_000, 946684800_000_000_000))

    (root / "uv.lock").write_text("test fixture lock\n")
    monkeypatch.setitem(main.__globals__, "ROOT", root)
    monkeypatch.setitem(main.__globals__, "load_plan", lambda: plan)
    monkeypatch.setitem(main.__globals__, "source_hash", lambda _: "fixture-source")
    monkeypatch.setitem(main.__globals__, "current_cleaning", lambda _: cleaning)
    monkeypatch.setitem(main.__globals__, "required_outputs", lambda: dict(required))
    monkeypatch.setitem(
        main.__globals__,
        "DISCIPLINES",
        {
            name: SimpleNamespace(config=lambda archive=archive: archive)
            for name, archive in archives.items()
        },
    )

    def add_stage(name, action="write"):
        script = f"scripts/{name}.py"
        output = f"{name}.json"
        plan["stages"].append(
            {
                "id": name,
                "script": script,
                "args": [
                    name,
                    action,
                    f"thesis/generated/{output}",
                    "{audit_dir}",
                    "{annotation_dir}",
                    str(archives["para"].derived_dir),
                    str(archives["hang"].derived_dir),
                ],
            }
        )
        required[output] = script

    audit = root / "audit"

    def manifest():
        paths = list((audit / "runs").glob("*/manifest.json"))
        assert len(paths) == 1
        return paths[0], json.loads(paths[0].read_text())

    def trace():
        return [
            json.loads(line) for line in (root / "trace.jsonl").read_text().splitlines()
        ]

    return SimpleNamespace(
        main=main,
        root=root,
        generated=generated,
        archives=archives,
        original_tables=original_tables,
        cleaning=cleaning,
        add_stage=add_stage,
        manifest=manifest,
        trace=trace,
        old_content=old_content,
        argv=["--no-build", "--audit-dir", str(audit)],
    )


def test_complete_workflow_records_two_snapshots_and_fresh_outputs(rebuild_workspace):
    work = rebuild_workspace
    work.add_stage("first")
    work.add_stage("final")

    assert work.main(work.argv) == 0

    path, manifest = work.manifest()
    assert manifest["status"] == "complete"
    assert manifest["source_sha256"] == "fixture-source"
    assert manifest["cleaning"] == work.cleaning
    assert "completed_utc" in manifest
    assert "pdf_sha256" not in manifest
    assert [stage["id"] for stage in manifest["stages"]] == ["first", "final"]
    assert all(stage["status"] == "complete" for stage in manifest["stages"])
    assert all(stage["elapsed_seconds"] >= 0 for stage in manifest["stages"])
    assert set(manifest["datasets"]) == {"para", "hang"}
    for name, archive in work.archives.items():
        assert manifest["datasets"][name]["tables"] == work.original_tables[name]
        assert dataset_identity(archive.derived_dir) == work.original_tables[name]

    calls = work.trace()
    assert [call["stage"] for call in calls] == ["first", "final"]
    for index, name in enumerate(("first", "final"), start=1):
        output = work.generated / f"{name}.json"
        assert output.read_bytes() != work.old_content
        assert manifest["outputs"][output.name] == {
            "sha256": hashlib.sha256(output.read_bytes()).hexdigest(),
            "producer": f"scripts/{name}.py",
            "historical_control": False,
        }
        assert (
            f"fixture stage: {name}"
            in (path.parent / f"{index:02d}-{name}.log").read_text()
        )
        assert calls[index - 1]["audit"] == str(path.parent / "arrays")
        assert calls[index - 1]["annotation"] == manifest["annotation_dir"]
        assert set(calls[index - 1]["inputs"]) == {"para", "hang"}
    assert manifest["outputs"]["dated-control.json"]["historical_control"]
    assert (work.generated / "dated-control.json").read_text() == '{"dated": true}\n'
    assert (work.generated / "later.json").read_bytes() == work.old_content


def test_child_failure_stops_later_stages_and_preserves_their_old_outputs(
    rebuild_workspace,
):
    work = rebuild_workspace
    work.add_stage("first")
    work.add_stage("final", "fail")
    work.add_stage("later")

    with pytest.raises(subprocess.CalledProcessError) as error:
        work.main(work.argv)

    assert error.value.returncode == 7
    path, manifest = work.manifest()
    assert manifest["status"] == "failed"
    assert "CalledProcessError" in manifest["error"]
    assert "completed_utc" not in manifest
    assert "outputs" not in manifest
    assert [(stage["id"], stage["status"]) for stage in manifest["stages"]] == [
        ("first", "complete"),
        ("final", "failed"),
    ]
    assert [call["stage"] for call in work.trace()] == ["first", "final"]
    assert "intentional fixture failure" in (path.parent / "02-final.log").read_text()
    assert not (path.parent / "03-later.log").exists()
    assert (work.generated / "first.json").read_bytes() != work.old_content
    for name in ("final", "later"):
        assert (work.generated / f"{name}.json").read_bytes() == work.old_content


def test_successful_child_cannot_complete_a_workflow_with_a_stale_output(
    rebuild_workspace,
):
    work = rebuild_workspace
    work.add_stage("first")
    work.add_stage("final", "leave-old")

    with pytest.raises(ValueError, match=r"old output unchanged: final\.json"):
        work.main(work.argv)

    _, manifest = work.manifest()
    assert manifest["status"] == "failed"
    assert "old output unchanged" in manifest["error"]
    assert all(stage["status"] == "complete" for stage in manifest["stages"])
    assert "completed_utc" not in manifest
    assert "outputs" not in manifest
    assert (work.generated / "final.json").read_bytes() == work.old_content


@pytest.mark.parametrize("action", ["mutate-table", "mark-incomplete"])
def test_snapshot_must_still_be_valid_after_the_final_stage(rebuild_workspace, action):
    work = rebuild_workspace
    work.add_stage("first")
    work.add_stage("final", action)

    with pytest.raises(ValueError):
        work.main(work.argv)

    _, manifest = work.manifest()
    assert manifest["status"] == "failed"
    assert "completed_utc" not in manifest
    assert all(stage["status"] == "complete" for stage in manifest["stages"])
    assert [call["stage"] for call in work.trace()] == ["first", "final"]


@pytest.mark.parametrize("max_pending", [1, 3, 20])
def test_bounded_results_keeps_source_lazy_and_yields_in_input_order(
    monkeypatch, max_pending
):
    module = runpy.run_path(str(ROOT / "scripts/preprocess.py"))
    bounded = module["_bounded_results"]
    size = 11
    state = {"pulled": 0, "delivered": 0}
    completion_order = []
    completion_lock = Lock()
    finished = [Event() for _ in range(3)]

    def jobs():
        for value in range(size):
            # Reading the source itself must be bounded, including jobs that
            # finish early but whose results cannot yet be yielded in order.
            assert state["pulled"] - state["delivered"] < max_pending
            state["pulled"] += 1
            yield value

    def worker(value):
        # Force the first three jobs to finish in reverse order without sleeps.
        if max_pending >= 3 and value < 2:
            assert finished[value + 1].wait(timeout=10), "worker was never submitted"
        with completion_lock:
            completion_order.append(value)
        if value < 3:
            finished[value].set()
        return value * value

    monkeypatch.setitem(bounded.__globals__, "_process_one", worker)
    with ThreadPoolExecutor(max_workers=3) as pool:
        results = bounded(pool, jobs(), max_pending)
        assert state == {"pulled": 0, "delivered": 0}
        observed = []
        for value in results:
            observed.append(value)
            state["delivered"] += 1
            assert state["pulled"] - state["delivered"] < max_pending
            if len(observed) == 1:
                assert state["pulled"] == min(max_pending, size)

    assert observed == [value * value for value in range(size)]
    assert state == {"pulled": size, "delivered": size}
    if max_pending >= 3:
        assert [value for value in completion_order if value < 3] == [2, 1, 0]
