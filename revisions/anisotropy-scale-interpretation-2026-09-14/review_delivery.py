"""Check the scale interpretation and record a manuscript-only revision.

Run after compiling and visually reviewing the thesis and both Chapter 3 decks.
All numerical products and environmental inputs must match the parent review.
Only editorial provenance is refreshed in the presentation source manifest.
"""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
from datetime import UTC, datetime
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
PARENT = ROOT / "revisions/era5-source-clarification-2026-09-13/manuscript-review.json"
TITLES = (
    "Directional constraints become more visible at longer lags",
    "Terrain constraints appear as a route explores their scale",
    "A weak persistent wind contribution can emerge with lag",
    "Whitening each lag makes each increment covariance isotropic",
)
CHANGED = {"thesis/sections/04-global-transport.tex", "thesis/references.bib"}


def digest(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def write_new(path, record):
    with path.open("x") as stream:
        stream.write(json.dumps(record, indent=2) + "\n")


def frame(text, title):
    start = text.index("\\begin{frame}{" + title + "}")
    end = text.index("\\end{frame}", start) + len("\\end{frame}")
    return text[start:end]


def main():
    parent = json.loads(PARENT.read_text())
    manifest_path = ROOT / "presentations/source-manifest.json"
    manifest = json.loads(manifest_path.read_text())
    assert parent["status"] == "complete"
    assert manifest["reviewed_thesis"] == parent
    assert manifest["review_record_sha256"] == digest(PARENT)
    sources = {name: digest(ROOT / name) for name in parent["source_files"]}
    changed = {name for name, value in sources.items() if value != parent["source_files"][name]}
    assert changed == CHANGED, changed
    for name, expected in parent["generated_outputs"].items():
        assert digest(ROOT / "thesis/generated" / name) == expected, name
    for name, expected in parent["external_input_files"].items():
        assert digest(ROOT / name) == expected, name

    paths = [ROOT / f"presentations/{name}.tex" for name in ("chapter3", "chapter3-section35")]
    decks = [path.read_text() for path in paths]
    assert all("Equal one-time covariances can conceal directional memory" not in deck for deck in decks)
    for title in TITLES:
        assert frame(decks[0], title) == frame(decks[1], title), title

    pca_path = ROOT / "revisions/regional-pca-lags-2026-09-12/regional-pca.json"
    rows = json.loads(pca_path.read_text())["paragliders"]
    numerical_rows = {}
    whitening_error = 0.0
    for region in ("Alps", "Pyrenees", "Channel Coast"):
        records = sorted((row for row in rows if row["region"] == region), key=lambda row: row["lag_s"])
        assert [row["lag_s"] for row in records] == [10, 100, 1000, 10000]
        assert np.all(np.diff([row["ratio"] for row in records]) > 0)
        table_row = region + " & " + " & ".join(f"{row['ratio']:.2f}" for row in records)
        assert all(table_row in deck for deck in decks), table_row
        numerical_rows[region] = [{key: row[key] for key in ("lag_s", "ratio", "n_flights")} for row in records]
        for row in records:
            covariance = np.array(row["covariance"])
            values, vectors = np.linalg.eigh(covariance)
            assert np.all(values > 0)
            whitening = (vectors * (values ** -0.5)) @ vectors.T
            error = float(np.max(np.abs(whitening @ covariance @ whitening.T - np.eye(2))))
            whitening_error = max(whitening_error, error)
    assert whitening_error < 1e-12

    direction = np.array([0.6, 0.8])
    diffusivity, wind_variance = 2.0, 0.3
    toy_errors = []
    for tau in (1.0, 10.0, 100.0):
        covariance = 2 * diffusivity * tau * np.eye(2) + wind_variance * tau**2 * np.outer(direction, direction)
        values = np.linalg.eigvalsh(covariance)
        toy_errors.append(float(abs(values[-1] / values[0] - (1 + wind_variance * tau / (2 * diffusivity)))))
    assert max(toy_errors) < 1e-12
    quarter_turn = np.array([[0.0, -1.0], [1.0, 0.0]])
    two_time = np.diag(np.exp(-1 / np.array([1.0, 2.0])))
    rotation_error = float(np.max(np.abs(quarter_turn @ two_time @ quarter_turn.T - two_time)))
    assert rotation_error > 0.1

    logs = [ROOT / "thesis/main.log"] + [
        ROOT / "presentations/build" / stem / (stem + ".log")
        for stem in ("chapter3", "chapter3-notes", "chapter3-section35", "chapter3-section35-notes")
    ]
    for path in logs:
        assert not re.search(r"Overfull|LaTeX Warning:|Undefined control sequence|Fatal error", path.read_text()), path
    pdfinfo = subprocess.check_output(["pdfinfo", str(ROOT / "thesis/main.pdf")], text=True)
    pages = int(re.search(r"^Pages:\s+(\d+)", pdfinfo, re.M)[1])
    now = datetime.now(UTC).isoformat()
    checks = {
        "status": "complete", "verified_utc": now,
        "scope": "Editorial interpretation and algebraic examples; no new flight measurement or causal test.",
        "pca_report_sha256": digest(pca_path), "observed_pca": numerical_rows,
        "same_four_frames_in_both_decks": list(TITLES),
        "whitened_covariance_max_absolute_error": whitening_error,
        "illustrative_wind_ratio_max_absolute_error": max(toy_errors),
        "two_time_covariance_quarter_turn_difference": rotation_error,
        "assumptions": [
            "Lag is increment duration, not time since launch; monotonicity is observed at four lags.",
            "Terrain exploration times are dimensional examples, not fitted thresholds or hard mountain walls.",
            "Common deterministic wind cancels from centred covariance.",
            "The wind example assumes an independent diffusive isotropic background and ensemble-variable wind coherent within each increment.",
            "Lag-wise whitening is exact for the fitted positive-definite weighted covariance, not necessarily new data.",
            "Second-order process isotropy also constrains two-time covariances; lag-wise matrices need not preserve increment additivity.",
        ],
        "sources": {
            "Taylor (1922), pp. 207--208": "https://mhd.ens.fr/IHP09/Young/Biblio/Taylor1921.pdf",
            "Kessy, Lewin and Strimmer (2018), whitening identity": "https://arxiv.org/abs/1512.00809",
        },
    }
    check_path = HERE / "interpretation-check.json"
    review_path = HERE / "manuscript-review.json"
    write_new(check_path, checks)
    review = dict(parent)
    review.update(
        reviewed_utc=now, parent_manuscript_review_sha256=digest(PARENT),
        source_files=sources, changed_manuscript_sources=sorted(changed),
        pdf_sha256=digest(ROOT / "thesis/main.pdf"), pages=pages,
        review_script_sha256=digest(__file__),
        interpretation_check_path=str(check_path.relative_to(ROOT)),
        interpretation_check_sha256=digest(check_path),
        scope="Develop the proposed terrain-exploration and coherent-wind interpretation of increasing PCA anisotropy; distinguish lag-wise whitening from second-order process isotropy. Numerical results unchanged.",
    )
    write_new(review_path, review)
    parent_manifest_hash = digest(manifest_path)
    manifest["reviewed_thesis"] = review
    manifest["review_record_sha256"] = digest(review_path)
    for name in changed & manifest["inputs"].keys():
        manifest["inputs"][name] = sources[name]
    manifest["editorial_update"] = {
        "review_path": str(review_path.relative_to(ROOT)),
        "parent_source_manifest_sha256": parent_manifest_hash,
        "operation": "Refresh reviewed manuscript provenance; retain existing figure, panel and numerical input records.",
    }
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
    print(f"Reviewed {pages} thesis pages, four matching frames per deck and unchanged numerical products.")


if __name__ == "__main__":
    main()
