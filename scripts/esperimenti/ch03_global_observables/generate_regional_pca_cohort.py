"""Regional PCA at the four display lags on one fixed population, the C_10000 cohort.

A change of covariance shape across lags is only readable if the same flights and
segments contribute at every lag. The cohort fixes both. Take-off boxes are those of
the regional comparison. Increments are nonoverlapping within the cohort's own
segments and equally weighted, as in soaring.analysis.observables.regional_pca.
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "src"))
from soaring.analysis.observables.archive_diagnostics import DiskFrames  # noqa: E402
from soaring.analysis.observables.regional_pca import (  # noqa: E402
    PCA_LAGS_S,
    PCA_REFERENCE_LAG_S,
    regional_pca,
)
from soaring.analysis.observables.takeoff_frames import takeoff_frames  # noqa: E402
from soaring.analysis.regions import REGIONAL_BOXES  # noqa: E402
from soaring.reporting import write_macros  # noqa: E402
from soaring.reporting.regional_pca import pca_figure  # noqa: E402

DATA = Path("/Volumes/SSD_DISANTE/derived-audit/chapter3-fixed-20260917")
OUT = ROOT / "thesis/generated"
REGIONS = {k: REGIONAL_BOXES[k] for k in ("Alps", "Pyrenees", "Channel Coast")}


def digest(path):
    """Identify a large input without loading it."""
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def main():
    """Measure the three regions on the cohort and write figure, macros and report."""
    audit = json.loads((DATA / "para/input-audit.json").read_text())
    store = Path(audit["inputs"]["coordinates"]["path"])
    if digest(store) != audit["inputs"]["coordinates"]["sha256"]:
        raise ValueError("The coordinate store differs from the audited one")
    coordinates = DiskFrames(store.parent)
    takeoffs = pd.read_parquet(
        DATA / "para/flights.parquet", columns=["flight_id", "lon0", "lat0"]
    )
    manifest = json.loads((DATA / "para/cohort-10000.json").read_text())
    records = regional_pca(
        takeoff_frames(coordinates, takeoffs, REGIONS, manifest["members"]),
        REGIONS,
        lags_s=PCA_LAGS_S,
    )
    macros = {"StatPcaCohortReferenceLagS": str(PCA_REFERENCE_LAG_S)}
    for row in records:
        if row["lag_s"] == PCA_REFERENCE_LAG_S:
            prefix = "StatPcaCohort" + row["region"].replace(" ", "")
            macros[prefix + "Flights"] = str(row["n_flights"])
            macros[prefix + "Ratio"] = f"{row['ratio']:.2f}"
            macros[prefix + "Angle"] = f"{row['angle_deg']:.1f}"
    write_macros(
        OUT / "ch3_pca_cohort_values.tex",
        macros,
        generator=str(Path(__file__).relative_to(ROOT)),
    )
    figure = pca_figure(records, REGIONS)
    figure.savefig(
        OUT / "ch3_pca_cohort.pdf",
        metadata={"CreationDate": None, "Creator": "soaring.analysis"},
    )
    plt.close(figure)
    report = {
        "cohort": "C_10000; fixed flights and segments",
        "cohort_sha256": manifest["sha256"],
        "regions": REGIONS,
        "lags_s": PCA_LAGS_S,
        "coordinate_sha256": audit["inputs"]["coordinates"]["sha256"],
        "producer_sha256": digest(__file__),
        "pca": records,
    }
    (OUT / "ch3_pca_cohort.json").write_text(json.dumps(report, indent=2) + "\n")
    for r in records:
        print(
            r["region"],
            r["lag_s"],
            r["n_flights"],
            r["n_increments"],
            f"{r['angle_deg']:.1f}",
            f"{r['ratio']:.2f}",
        )


if __name__ == "__main__":
    main()
