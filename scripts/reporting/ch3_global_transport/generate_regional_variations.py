"""Add regional finite differences to a full rebuild's freshly collected coordinates."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "src"))
from soaring.reporting import DISCIPLINES  # noqa: E402

GENERATED_OUTPUTS = (
    "ch3_regional_variations.pdf",
    "ch3_variation_axes.pdf",
    "ch3_variation_controls.pdf",
    "ch3_variation_distributions.pdf",
    "ch3_variation_orders.pdf",
    "ch3_variation_support.pdf",
    "ch3_regional_variations_values.tex",
)


def main():
    """Verify the completed upstream stores and execute measurement then rendering."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--audit-dir", type=Path, required=True)
    args = parser.parse_args()
    directory = args.audit_dir.resolve()
    output = directory / "regional-variations"
    output.mkdir(parents=True, exist_ok=True)
    records = {}
    report_path = ROOT / "thesis/generated/ch3_revision.json"
    report = json.loads(report_path.read_text())
    if report["measurement_contract"]["scope"] != "full eligible archive":
        raise ValueError("The upstream report must cover the full eligible archive")
    for name, glider in DISCIPLINES.items():
        store = directory / f"ch3-full-{glider.slug}"
        if (store / ".incomplete").exists():
            raise ValueError(f"Upstream measurement is incomplete: {store}")
        rows = json.loads((store / "flights.json").read_text())
        if rows != report["provenance"][name]["flights"]:
            raise ValueError("Upstream report and coordinate index differ")
        for filename in ("positions.bin", "flights.json"):
            path = store / filename
            with path.open("rb") as stream:
                digest = hashlib.file_digest(stream, "sha256").hexdigest()
            records[str(path)] = {"sha256": digest, "bytes": path.stat().st_size}
    manifest = output / "coordinate-manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "status": "complete",
                "coordinate_inputs": records,
                "upstream_report_sha256": hashlib.sha256(
                    report_path.read_bytes()
                ).hexdigest(),
            },
            indent=2,
        )
        + "\n"
    )
    scripts = ROOT / "scripts/reporting/ch3_global_transport"
    subprocess.run(
        [
            sys.executable,
            str(scripts / "measure_regional_variations.py"),
            "--out",
            str(output),
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
            str(scripts / "render_regional_variations.py"),
            "--report",
            str(output / "report.json.gz"),
            "--manifest",
            str(output / "figure-manifest.json"),
        ],
        check=True,
    )


if __name__ == "__main__":
    main()
