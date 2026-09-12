"""Verify this frozen archive, or download the same requests into a new directory.

The default invocation is offline and never overwrites the frozen input manifest.
A new download may differ if the provider revises its data or response metadata.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import time
import urllib.error
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent


def sha(data: bytes) -> str:
    """Identify the exact input bytes."""
    return hashlib.sha256(data).hexdigest()


def verify(folder: Path) -> None:
    """Check both archive representations and the recorded time coverage."""
    manifest = json.loads((folder / "input-manifest.json").read_text())
    total = 0
    for record in manifest["files"]:
        compressed = (folder / record["file"]).read_bytes()
        raw = gzip.decompress(compressed)
        if sha(compressed) != record["sha256"] or sha(raw) != record["raw_sha256"]:
            raise ValueError(f"Archived bytes changed: {record['file']}")
        data = json.loads(raw)
        times = data["hourly"]["time"]
        if (
            len(times) != record["hours"]
            or times[0] != "2016-01-01T00:00"
            or times[-1] != "2025-12-31T23:00"
        ):
            raise ValueError(f"Unexpected time coverage: {record['file']}")
        total += len(compressed)
    print(f"Verified {len(manifest['files'])} cells; {total:,} compressed bytes")


def main() -> None:
    """Verify locally by default; fetch only into a new directory on request."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--download-to",
        type=Path,
        help="new empty directory for a fresh provider download",
    )
    args = parser.parse_args()
    if args.download_to is None:
        verify(HERE)
        return
    destination = args.download_to.resolve()
    if destination.exists() and any(destination.iterdir()):
        raise ValueError(
            "Choose a new empty directory; frozen inputs are never overwritten"
        )
    destination.mkdir(parents=True, exist_ok=True)
    manifest = json.loads((HERE / "input-manifest.json").read_text())
    for record in manifest["files"]:
        for attempt in range(4):
            try:
                with urllib.request.urlopen(record["url"], timeout=60) as response:
                    raw = response.read()
                break
            except urllib.error.HTTPError as error:
                if error.code != 429 or attempt == 3:
                    raise
                time.sleep(60)
        data = json.loads(raw)
        compressed = gzip.compress(raw, mtime=0)
        (destination / record["file"]).write_bytes(compressed)
        record.update(
            sha256=sha(compressed),
            raw_sha256=sha(raw),
            latitude=data["latitude"],
            longitude=data["longitude"],
            retrieved_utc=datetime.now(UTC).isoformat(),
        )
    (destination / "input-manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n"
    )
    verify(destination)


if __name__ == "__main__":
    main()
