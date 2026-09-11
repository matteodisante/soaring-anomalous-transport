"""Bind blinded annotation inputs to the cleaned and segmented source snapshot."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

PACK_INPUTS = ("annotation_windows.csv", "annotation_candidates.parquet")
SOURCE_INPUTS = (
    "fixes.parquet",
    "segmentation/phase_points.parquet",
    "segmentation/model/metadata.json",
    "segmentation/model/split_manifest.parquet",
)
SOURCE_VALIDATION_INPUTS = (
    "fixes.parquet",
    "segmentation/model/split_manifest.parquet",
)


def file_signature(path: Path) -> dict:
    """Read a checksum or large Parquet footer identity without a full rescan."""
    stat = path.stat()
    result = {"size": stat.st_size, "mtime_ns": stat.st_mtime_ns}
    if path.suffix == ".parquet" and stat.st_size > 16_000_000:
        with path.open("rb") as stream:
            stream.seek(-8, 2)
            trailer = stream.read(8)
            if trailer[4:] != b"PAR1":
                raise ValueError(f"{path}: incomplete Parquet file")
            size = int.from_bytes(trailer[:4], "little")
            stream.seek(-8 - size, 2)
            result["footer_sha256"] = hashlib.sha256(stream.read(size)).hexdigest()
    else:
        result["sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
    return result


def write_pack_provenance(pack_dir: Path, derived_dirs: dict[str, Path]) -> None:
    """Record pack and source identities, excluding the editable label CSV."""
    record = {
        "schema_version": 1,
        "inputs": {name: file_signature(pack_dir / name) for name in PACK_INPUTS},
        "sources": {
            name: {
                "derived_dir": str(derived.resolve()),
                "files": {
                    file: file_signature(derived / file) for file in SOURCE_INPUTS
                },
            }
            for name, derived in derived_dirs.items()
        },
        "large_file_identity": (
            "file size, modification time and SHA256 of Parquet footer"
        ),
    }
    (pack_dir / "pack_provenance.json").write_text(
        json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def validate_pack_provenance(pack_dir: Path) -> list[str]:
    """Reject changed inputs or mounted sources; allow an intact offline pack.

    Returns names of archives unavailable for comparison. The editable annotations
    are deliberately outside this check. Copying the pack preserves content checksums
    even when the copied files' modification times differ.
    """
    provenance = pack_dir / "pack_provenance.json"
    if not provenance.is_file():
        raise ValueError(
            "Pack provenance is missing. Prepare a versioned annotation pack first."
        )
    record = json.loads(provenance.read_text(encoding="utf-8"))
    for name, expected in record["inputs"].items():
        actual = file_signature(pack_dir / name)
        if actual["size"] != expected["size"] or actual.get("sha256") != expected.get(
            "sha256"
        ):
            raise ValueError(f"Annotation input {name} changed after pack preparation.")
    unavailable = []
    for name, source in record["sources"].items():
        derived = Path(source["derived_dir"])
        if not derived.exists():
            unavailable.append(name)
            continue
        # Calibration changes predictions and model metadata, but not the blinded
        # kinematics or split. It must not invalidate validation/test annotations.
        for file in SOURCE_VALIDATION_INPUTS:
            expected = source["files"][file]
            path = derived / file
            actual = file_signature(path) if path.is_file() else None
            changed = actual is None or any(
                actual.get(key) != value
                for key, value in expected.items()
                if key != "mtime_ns" or "footer_sha256" in expected
            )
            if changed:
                raise ValueError(
                    f"{name}: {file} changed since this annotation pack was prepared. "
                    "Keep existing labels; use a new pack for the rebuilt archive."
                )
    return unavailable
