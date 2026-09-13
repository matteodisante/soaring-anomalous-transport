"""Review component scaling against the unchanged numerical manuscript inputs."""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
PARENT = ROOT / "revisions/joint-laws-and-hurst-interpretation-2026-09-13"


def digest(path):
    """Identify complete file bytes."""
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def main():
    """Build the manuscript and preserve the completed numerical lineage."""
    parent_path = PARENT / "manuscript-review.json"
    parent = json.loads(parent_path.read_text())
    assert parent["status"] == "complete"
    sources = {n: digest(ROOT / n) for n in parent["source_files"]}
    changed = [n for n, h in sources.items() if h != parent["source_files"][n]]
    assert changed == ["thesis/sections/04-global-transport.tex"], changed
    for name, expected in parent["generated_outputs"].items():
        assert digest(ROOT / "thesis/generated" / name) == expected, name
    for name, expected in parent["external_input_files"].items():
        assert digest(ROOT / name) == expected, name
    assert (
        digest(PARENT / "interpretation-check.json")
        == parent["interpretation_check_sha256"]
    )
    subprocess.run(
        [
            "latexmk",
            "-pdf",
            "-halt-on-error",
            "-interaction=nonstopmode",
            "-cd",
            "thesis/main.tex",
        ],
        cwd=ROOT,
        check=True,
        stdout=subprocess.DEVNULL,
    )
    log = (ROOT / "thesis/main.log").read_text()
    assert not re.search(
        r"Overfull|LaTeX Warning:|Undefined control sequence|Fatal error", log
    )
    assert sources == {n: digest(ROOT / n) for n in sources}
    review = dict(parent)
    review.update(
        reviewed_utc=datetime.now(UTC).isoformat(),
        parent_manuscript_review_sha256=digest(parent_path),
        changed_manuscript_sources=changed,
        source_files=sources,
        pdf_sha256=digest(ROOT / "thesis/main.pdf"),
        pages=int(re.search(r"Output written on main.pdf \((\d+) pages", log)[1]),
        review_script_sha256=digest(__file__),
        interpretation_check_path=str(
            (PARENT / "interpretation-check.json").relative_to(ROOT)
        ),
        scope=(
            "Add explicit signed east/north, marginal-density and absolute-component "
            "quantile scaling laws. Retain the reviewed Hurst interpretation and "
            "spatial-versus-temporal distinction. All 98 generated numerical products "
            "and numerical sources remain unchanged."
        ),
    )
    (HERE / "manuscript-review.json").write_text(json.dumps(review, indent=2) + "\n")
    print(f"Reviewed {review['pages']} pages; all 98 numerical products unchanged")


if __name__ == "__main__":
    main()
