#!/usr/bin/env python3
"""Record whether the manuscript's numerical inputs have passed this rebuild.

The completed-run manifest remains the release record. This small TeX fragment
prevents a methods revision from silently presenting an older numerical archive.
"""

from __future__ import annotations

import argparse
import json
import runpy
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "src"))
from soaring.reporting import write_macros  # noqa: E402

OUT_TEX = ROOT / "thesis" / "generated" / "snapshot_status.tex"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--audit-dir", type=Path)
    parser.add_argument("--pending", action="store_true")
    args = parser.parse_args()
    if args.pending:
        values = {"StatSnapshotCurrent": "0", "StatSnapshotVersion": "pending"}
    else:
        if args.audit_dir is None:
            parser.error("--audit-dir is required unless --pending is selected")
        manifest = json.loads((args.audit_dir.parent / "manifest.json").read_text())
        completed = {
            stage["command"][1]: stage["started_unix"]
            for stage in manifest["stages"]
            if stage["status"] == "complete"
        }
        rebuild = runpy.run_path(str(ROOT / "scripts/rebuild_thesis.py"))
        required = rebuild["required_outputs"]()
        required.pop(OUT_TEX.name, None)
        plan = rebuild["load_plan"]()
        rebuild["check_fresh_outputs"](
            required, completed, set(plan.get("historical_outputs", [])), OUT_TEX.parent
        )
        snapshots = manifest.get("datasets", {})
        if len(snapshots) != 2:
            raise ValueError("Both cleaned archives must be verified")
        versions = {row["cleaning"]["pipeline_version"] for row in snapshots.values()}
        if len(versions) != 1:
            raise ValueError("Cleaning versions differ between disciplines")
        values = {"StatSnapshotCurrent": "1", "StatSnapshotVersion": versions.pop()}
    write_macros(
        OUT_TEX,
        values,
        generator="scripts/reporting/checks/generate_snapshot_status.py",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
