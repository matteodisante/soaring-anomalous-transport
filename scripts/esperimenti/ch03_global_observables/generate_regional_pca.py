"""Regenerate regional PCA directly from saved coordinates, without increment caches.

The output directory is explicit so validating an archived PCA cannot overwrite
current thesis results. The reference report supplies regions and flight identities;
the PCA estimator and physical lags are shared with the original full report.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "src"))

from soaring.analysis.observables.archive_diagnostics import DiskFrames  # noqa: E402
from soaring.analysis.observables.regional_pca import (  # noqa: E402
    PCA_LAGS_S,
    regional_pca,
)
from soaring.reporting import DISCIPLINES, write_macros  # noqa: E402


def main():
    """Validate coordinate provenance, then write only PCA products."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--audit-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument(
        "--reference-report",
        type=Path,
        default=ROOT / "thesis/generated/ch3_revision.json",
    )
    args = parser.parse_args()
    reference = json.loads(args.reference_report.read_text())
    contract = reference["measurement_contract"]
    if contract["scope"] != "full eligible archive":
        raise ValueError("The reference report must describe the full eligible archive")
    regions = contract["regions"]
    summaries, inputs = {}, {}
    for name, discipline in DISCIPLINES.items():
        directory = args.audit_dir / f"ch3-full-{discipline.slug}"
        frames = DiskFrames(directory)
        if frames.rows != reference["provenance"][name]["flights"]:
            raise ValueError(f"Coordinate index differs from the reference: {name}")
        records = {}
        for filename in ("positions.bin", "flights.json"):
            path = directory / filename
            with path.open("rb") as stream:
                digest = hashlib.file_digest(stream, "sha256").hexdigest()
            records[filename] = {
                "path": str(path.resolve()),
                "bytes": path.stat().st_size,
                "sha256": digest,
            }
        inputs[name] = records
        summaries[name] = {"pca": regional_pca(frames, regions)}
        print(f"{name}: {len(frames)} flights, PCA complete", flush=True)

    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    from soaring.reporting.regional_pca import pca_figure, pca_macros

    args.output_dir.mkdir(parents=True, exist_ok=True)
    figure = pca_figure(summaries["paragliders"]["pca"], regions)
    figure.savefig(
        args.output_dir / "ch3_pca.pdf",
        metadata={"CreationDate": None, "Creator": "soaring.analysis"},
    )
    plt.close(figure)
    write_macros(
        args.output_dir / "ch3_pca.tex",
        pca_macros(summaries, DISCIPLINES),
        generator=str(Path(__file__).relative_to(ROOT)),
    )
    code = (
        Path(__file__),
        ROOT / "src/soaring/analysis/observables/regional_pca.py",
        ROOT / "src/soaring/analysis/observables/segment_support.py",
    )
    report = {
        "regional_pca_lags_s": PCA_LAGS_S,
        "regions": regions,
        "coordinate_inputs": inputs,
        "results": summaries,
        "reference_report": str(args.reference_report.resolve()),
        "reference_report_sha256": hashlib.sha256(
            args.reference_report.read_bytes()
        ).hexdigest(),
        "code_sha256": {
            str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in code
        },
    }
    (args.output_dir / "ch3_pca.json").write_text(json.dumps(report, indent=2) + "\n")


if __name__ == "__main__":
    main()
