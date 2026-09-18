"""Add signed and temporal scaling to a full rebuild's verified coordinate stores."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

from soaring.reporting import DISCIPLINES

ROOT = Path(__file__).resolve().parents[3]
GENERATED_OUTPUTS = (
    "ch3_temporal_scaling_distances.pdf",
    "ch3_temporal_scaling_para.pdf",
    "ch3_temporal_scaling_hang.pdf",
    "ch3_temporal_scaling_population.tex",
    "ch3_temporal_scaling_bounds.tex",
)


def main():
    """Identify this rebuild's stores, then measure and render the frozen protocol."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--audit-dir", type=Path, required=True)
    args = parser.parse_args()
    directory = args.audit_dir.resolve()
    output = directory / "temporal-scaling"
    output.mkdir(parents=True, exist_ok=True)
    records = {}
    upstream_path = ROOT / "thesis/generated/ch3_revision.json"
    upstream = json.loads(upstream_path.read_text())
    if upstream["measurement_contract"]["scope"] != "full eligible archive":
        raise ValueError("Temporal scaling requires the complete eligible archive")
    for name, glider in DISCIPLINES.items():
        store = directory / f"ch3-full-{glider.slug}"
        if (store / ".incomplete").exists():
            raise ValueError(f"Incomplete upstream coordinates: {store}")
        rows = json.loads((store / "flights.json").read_text())
        if rows != upstream["provenance"][name]["flights"]:
            raise ValueError("Upstream report and coordinate index differ")
        for filename in ("positions.bin", "flights.json"):
            path = store / filename
            with path.open("rb") as stream:
                sha = hashlib.file_digest(stream, "sha256").hexdigest()
            records[str(path)] = {"sha256": sha, "bytes": path.stat().st_size}
    manifest = output / "coordinate-manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "status": "complete",
                "coordinate_inputs": records,
                "upstream_report_sha256": hashlib.sha256(
                    upstream_path.read_bytes()
                ).hexdigest(),
                "cleaning": {
                    "provenance": "Verified by the containing full rebuild manifest"
                },
            },
            indent=2,
        )
        + "\n"
    )
    scripts = Path(__file__).parent
    subprocess.run(
        [
            sys.executable,
            str(scripts / "measure_temporal_scaling.py"),
            "--out",
            str(output / "measurement"),
            "--coordinate-manifest",
            str(manifest),
            "--workers",
            os.environ.get("SOARING_MAX_WORKERS", "4"),
        ],
        check=True,
    )
    subprocess.run(
        [
            sys.executable,
            str(scripts / "render_temporal_scaling.py"),
            "--measurement",
            str(output / "measurement"),
        ],
        check=True,
    )


if __name__ == "__main__":
    main()
