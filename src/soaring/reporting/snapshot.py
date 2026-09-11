"""Record the code, configuration and table identities of a cleaning run.

Table identities use size, modification time and a hash of the Parquet footer.
They detect replacement and schema changes without rereading a multi-gigabyte
table. They are not a cryptographic checksum of every trajectory value.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict
from pathlib import Path

TABLES = (
    "fixes.parquet",
    "segments.parquet",
    "flights_meta.parquet",
    "suspect_intervals.parquet",
)


def source_hash(root: Path, *, preprocessing_only: bool = False) -> str:
    """Hash sorted source paths and contents, including uncommitted changes."""
    if preprocessing_only:
        paths = [
            *root.glob("src/soaring/analysis/preproc/*.py"),
            root / "src/soaring/analysis/igc.py",
            root / "src/soaring/analysis/census.py",
            root / "src/soaring/analysis/config.py",
            root / "src/soaring/acquisition/ffvl/naming.py",
            root / "scripts/preprocess.py",
            root / "src/soaring/reporting/snapshot.py",
        ]
    else:
        paths = [
            *root.glob("src/**/*.py"),
            *root.glob("scripts/**/*.py"),
            *root.glob("configs/*.yaml"),
            *root.glob("thesis/sections/*.tex"),
            *root.glob("thesis/appendices/**/*.tex"),
            root / "thesis/main.tex",
            root / "thesis/references.bib",
            root / "uv.lock",
        ]
    digest = hashlib.sha256()
    for path in sorted(set(paths)):
        digest.update(path.relative_to(root).as_posix().encode() + b"\0")
        digest.update(path.read_bytes())
    return digest.hexdigest()


def current_cleaning(root: Path) -> dict:
    """Return the executable cleaning definition, independent of YAML comments."""
    from importlib.metadata import version

    from soaring.analysis.config import load_preproc_config
    from soaring.analysis.preproc.pipeline import PIPELINE_VERSION

    return {
        "pipeline_version": PIPELINE_VERSION,
        "configuration": asdict(load_preproc_config()),
        "source_sha256": source_hash(root, preprocessing_only=True),
        "packages": {
            name: version(name) for name in ("numpy", "pandas", "scipy", "pyarrow")
        },
    }


def table_identity(path: Path) -> dict:
    """Identify a completed Parquet table from its stat and validated footer."""
    import pyarrow.parquet as pq

    stat = path.stat()
    with path.open("rb") as stream:
        stream.seek(-8, 2)
        tail = stream.read(8)
        if tail[4:] != b"PAR1":
            raise ValueError(f"Not a complete Parquet file: {path}")
        footer_length = int.from_bytes(tail[:4], "little")
        if footer_length > stat.st_size - 12:
            raise ValueError(f"Invalid Parquet footer: {path}")
        stream.seek(-8 - footer_length, 2)
        footer = stream.read(footer_length)
    metadata = pq.read_metadata(path)
    return {
        "bytes": stat.st_size,
        "mtime_ns": stat.st_mtime_ns,
        "footer_sha256": hashlib.sha256(footer).hexdigest(),
        "rows": metadata.num_rows,
    }


def dataset_identity(directory: Path) -> dict:
    """Identify all four tables; a missing table is an error."""
    return {name: table_identity(directory / name) for name in TABLES}


def write_json(path: Path, value: dict) -> None:
    """Replace a small JSON manifest only after its contents have been written."""
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")
    temporary.replace(path)


def validate_snapshot(directory: Path, expected_cleaning: dict) -> dict:
    """Reject incomplete, sampled, altered or outdated cleaned archives."""
    if (directory / ".run_incomplete").exists():
        raise ValueError(f"Unfinished cleaning in {directory}; rerun with --clean.")
    path = directory / "run_manifest.json"
    if not path.is_file():
        raise ValueError(f"No cleaning manifest in {directory}; rerun with --clean.")
    manifest = json.loads(path.read_text())
    if manifest.get("status") != "complete" or manifest.get("limit") != 0:
        raise ValueError(f"Cleaning is incomplete or sampled in {directory}.")
    if manifest.get("cleaning") != expected_cleaning:
        raise ValueError(
            f"Cleaning code/configuration changed for {directory}; use --clean."
        )
    if manifest.get("tables") != dataset_identity(directory):
        raise ValueError(f"Tables changed since the recorded cleaning in {directory}.")
    if manifest["tables"]["fixes.parquet"]["rows"] == 0:
        raise ValueError(f"No retained fixes in {directory}.")
    return manifest
