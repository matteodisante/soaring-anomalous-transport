#!/usr/bin/env python3
"""Rebuild analyses, segmentation, figures and thesis from one verified snapshot.

Run ``uv run python scripts/rebuild_thesis.py --clean --jobs 1`` after changing
cleaning. ``--dry-run`` prints the commands without writing or processing data.
Without ``--clean``, an archive made by the current cleaning code is required.
"""

from __future__ import annotations

import argparse
import fcntl
import hashlib
import os
import runpy
import shlex
import shutil
import signal
import subprocess
import sys
import time
import uuid
from contextlib import ExitStack, suppress
from datetime import UTC, datetime
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from soaring.reporting import DISCIPLINES  # noqa: E402
from soaring.reporting.snapshot import (  # noqa: E402
    current_cleaning,
    dataset_identity,
    source_hash,
    validate_snapshot,
    write_json,
)


def load_plan(path: Path = ROOT / "configs/rebuild.yaml") -> dict:
    """Read the ordered workflow and reject duplicate stage identifiers."""
    plan = yaml.safe_load(path.read_text())
    ids = [stage["id"] for stage in plan["stages"]]
    if len(ids) != len(set(ids)):
        raise ValueError("Rebuild stage identifiers must be unique")
    return plan


def numerical_source_hash(root: Path) -> str:
    """Identify code and parameters separately from subsequent manuscript editing."""
    paths = [
        *root.glob("src/**/*.py"),
        *root.glob("scripts/**/*.py"),
        *root.glob("configs/*.yaml"),
        root / "uv.lock",
    ]
    digest = hashlib.sha256()
    for path in sorted(set(paths)):
        digest.update(path.relative_to(root).as_posix().encode() + b"\0")
        digest.update(path.read_bytes())
    return digest.hexdigest()


def commands(
    plan: dict,
    audit_dir: Path,
    annotation_dir: Path,
    *,
    clean: bool,
    jobs: int,
    build: bool,
) -> list[tuple[str, list[str]]]:
    """Expand argument placeholders into executable argument vectors."""
    result = []
    if clean:
        result.append(
            ("clean", [sys.executable, "scripts/preprocess.py", "--jobs", str(jobs)])
        )
    values = {"audit_dir": str(audit_dir), "annotation_dir": str(annotation_dir)}
    for stage in plan["stages"]:
        args = [str(arg).format_map(values) for arg in stage.get("args", [])]
        result.append((stage["id"], [sys.executable, stage["script"], *args]))
    if build:
        result.append(
            (
                "latex",
                [
                    "latexmk",
                    "-pdf",
                    "-halt-on-error",
                    "-interaction=nonstopmode",
                    "-cd",
                    "thesis/main.tex",
                ],
            )
        )
    return result


def required_outputs() -> dict[str, str | None]:
    """Find figure/table inputs and files defining macros used by thesis sources."""
    provenance = runpy.run_path(
        str(ROOT / "scripts/reporting/checks/generate_provenance.py")
    )
    defines = provenance["defined_macros"]()
    macros, figures = provenance["used_in"](set(defines))
    names = set(figures) | {defines[name] for name in macros}
    writers = provenance["writers"]()
    return {name: writers.get(name) for name in names}


def check_fresh_outputs(
    required: dict[str, str | None],
    completed: dict[str, float],
    historical: set[str],
    generated: Path,
) -> dict[str, dict]:
    """Reject absent outputs, omitted generators, and silently reused old figures."""
    result = {}
    for name, producer in sorted(required.items()):
        path = generated / name
        if not path.is_file():
            raise ValueError(f"Required thesis output is missing: {path}")
        if name not in historical:
            if producer not in completed:
                raise ValueError(
                    f"No completed rebuild stage produces {name}: {producer}"
                )
            if path.stat().st_mtime_ns < int(completed[producer] * 1e9):
                raise ValueError(f"{producer} left an old output unchanged: {name}")
        result[name] = {
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "producer": producer,
            "historical_control": name in historical,
        }
    return result


def _lock(stack: ExitStack, path: Path) -> None:
    """Hold a nonblocking advisory lock for the lifetime of the workflow."""
    stream = stack.enter_context(path.open("a"))
    try:
        fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError as exc:
        raise RuntimeError(f"Another process holds {path}") from exc


def _run(command: list[str], log: Path) -> None:
    """Stream a child process to the terminal and its log; propagate failure."""
    env = dict(os.environ, PYTHONUNBUFFERED="1", PYTHONPATH=str(ROOT / "src"))
    for name in (
        "OMP_NUM_THREADS",
        "OPENBLAS_NUM_THREADS",
        "MKL_NUM_THREADS",
        "VECLIB_MAXIMUM_THREADS",
        "NUMEXPR_NUM_THREADS",
        "BLIS_NUM_THREADS",
    ):
        env[name] = "1"
    with log.open("w") as output:
        process = subprocess.Popen(
            command,
            cwd=ROOT,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            start_new_session=True,
        )
        try:
            assert process.stdout is not None
            for line in process.stdout:
                print(line, end="", flush=True)
                output.write(line)
            code = process.wait()
        except BaseException:
            # Workers and joblib children belong to this process group too.
            with suppress(ProcessLookupError):
                os.killpg(process.pid, signal.SIGTERM)
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL)
                process.wait()
            raise
        if code:
            raise subprocess.CalledProcessError(code, command)


def main(argv=None) -> int:
    """Run the complete workflow, recording each successful or failed stage."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--clean", action="store_true")
    parser.add_argument(
        "--jobs", type=int, default=1, help="maximum worker processes (default: 1)"
    )
    parser.add_argument(
        "--full-speed",
        action="store_true",
        help="use normal scheduling priority; --jobs still sets the worker limit",
    )
    parser.add_argument(
        "--audit-dir",
        type=Path,
        default=Path(os.environ.get("AUDIT_DIR", "/Volumes/SSD_DISANTE/derived-audit")),
    )
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--no-build", action="store_true")
    args = parser.parse_args(argv)
    if args.jobs < 1:
        parser.error("--jobs must be positive")
    plan = load_plan()
    run_id = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid.uuid4().hex[:8]
    run_dir = args.audit_dir.resolve() / "runs" / run_id
    annotation_dir = ROOT / "annotations/phase_labeling" / run_id
    todo = commands(
        plan,
        run_dir / "arrays",
        annotation_dir,
        clean=args.clean,
        jobs=args.jobs,
        build=not args.no_build,
    )
    if args.dry_run:
        for name, command in todo:
            print(f"{name}: {shlex.join(command)}")
        print(f"Manifest/logs: {run_dir}; annotations: {annotation_dir}")
        return 0

    if not args.full_speed:
        os.setpriority(os.PRIO_PROCESS, 0, 19)
        if sys.platform == "darwin" and shutil.which("taskpolicy"):
            subprocess.run(["taskpolicy", "-b", "-p", str(os.getpid())], check=True)
    os.environ["SOARING_MAX_WORKERS"] = str(args.jobs)

    # Resolve configured roots, including defaults without environment overrides.
    archives = {name: discipline.config() for name, discipline in DISCIPLINES.items()}
    for name, archive in archives.items():
        if not archive.igc_dir.is_dir() or not archive.catalog_path.is_file():
            raise ValueError(
                f"{name}: both raw IGC directory and catalog.csv are required"
            )
    if not args.no_build and shutil.which("latexmk") is None:
        raise ValueError(
            "latexmk is unavailable; install LaTeX before starting the rebuild"
        )
    cleaning = current_cleaning(ROOT)
    if not args.clean:
        for archive in archives.values():
            validate_snapshot(archive.derived_dir, cleaning)
    run_dir.mkdir(parents=True)
    (run_dir / "arrays").mkdir()
    manifest = {
        "run_id": run_id,
        "status": "running",
        "source_sha256": source_hash(ROOT),
        "numerical_source_sha256": numerical_source_hash(ROOT),
        "cleaning": cleaning,
        "annotation_dir": str(annotation_dir),
        "stages": [],
        "resources": {
            "max_workers": args.jobs,
            "native_threads": 1,
            "nice": os.getpriority(os.PRIO_PROCESS, 0),
            "full_speed": args.full_speed,
        },
    }
    manifest_path = run_dir / "manifest.json"
    write_json(manifest_path, manifest)
    completed: dict[str, float] = {}
    snapshots = None
    try:
        with ExitStack() as stack:
            _lock(stack, args.audit_dir / ".rebuild.lock")
            for index, (name, command) in enumerate(todo, 1):
                if source_hash(ROOT) != manifest["source_sha256"]:
                    raise ValueError(
                        "Source/configuration changed during rebuild; rerun"
                    )
                if name != "clean" and snapshots is None:
                    snapshots = {}
                    for key, archive in archives.items():
                        _lock(stack, archive.derived_dir / ".preprocess.lock")
                        snapshots[key] = validate_snapshot(
                            archive.derived_dir, cleaning
                        )
                    manifest["datasets"] = snapshots
                if snapshots is not None:
                    for key, archive in archives.items():
                        if (
                            archive.derived_dir / ".run_incomplete"
                        ).exists() or dataset_identity(
                            archive.derived_dir
                        ) != snapshots[key]["tables"]:
                            raise ValueError(
                                f"{key}: cleaned tables changed during rebuild"
                            )
                if name == "latex":
                    manifest["outputs"] = check_fresh_outputs(
                        required_outputs(),
                        completed,
                        set(plan.get("historical_outputs", [])),
                        ROOT / "thesis/generated",
                    )
                print(f"\n[{index}/{len(todo)}] {name}", flush=True)
                started = time.time()
                stage = {
                    "id": name,
                    "command": command,
                    "started_unix": started,
                    "status": "running",
                }
                manifest["stages"].append(stage)
                write_json(manifest_path, manifest)
                _run(command, run_dir / f"{index:02d}-{name}.log")
                stage.update(status="complete", elapsed_seconds=time.time() - started)
                if len(command) > 1 and command[1].endswith(".py"):
                    completed[command[1]] = started
                write_json(manifest_path, manifest)
            manifest["outputs"] = check_fresh_outputs(
                required_outputs(),
                completed,
                set(plan.get("historical_outputs", [])),
                ROOT / "thesis/generated",
            )
            if source_hash(ROOT) != manifest["source_sha256"]:
                raise ValueError("Source changed during the final stage")
            for key, archive in archives.items():
                if (
                    archive.derived_dir / ".run_incomplete"
                ).exists() or dataset_identity(archive.derived_dir) != snapshots[key][
                    "tables"
                ]:
                    raise ValueError(
                        f"{key}: cleaned tables changed during final stage"
                    )
            if not args.no_build:
                manifest["pdf_sha256"] = hashlib.sha256(
                    (ROOT / "thesis/main.pdf").read_bytes()
                ).hexdigest()
            manifest.update(
                status="complete", completed_utc=datetime.now(UTC).isoformat()
            )
            write_json(manifest_path, manifest)
    except BaseException as exc:
        if manifest["stages"] and manifest["stages"][-1]["status"] == "running":
            manifest["stages"][-1]["status"] = "failed"
        manifest.update(status="failed", error=f"{type(exc).__name__}: {exc}")
        write_json(manifest_path, manifest)
        print(f"Rebuild stopped. Details: {manifest_path}", file=sys.stderr)
        raise
    print(
        f"Rebuild complete. Manifest: {manifest_path}\n"
        f"Annotation pack: {annotation_dir}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
