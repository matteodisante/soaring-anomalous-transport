"""Compile a manuscript-only revision while preserving its numerical parent."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def digest(path):
    """Identify complete file bytes."""
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def main():
    """Validate unchanged inputs, build the PDF and write a new child review."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("parent", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--scope", required=True)
    args = parser.parse_args()
    parent_path = args.parent.resolve()
    output = args.output.resolve()
    if output.exists():
        raise ValueError("Use a new output review; completed reviews are immutable")
    parent = json.loads(parent_path.read_text())
    assert parent["status"] == "complete"
    sources = {n: digest(ROOT / n) for n in parent["source_files"]}
    changed = [n for n, h in sources.items() if h != parent["source_files"][n]]
    assert changed and all(
        n.startswith("thesis/") and Path(n).suffix in (".tex", ".bib") for n in changed
    ), changed
    for name, expected in parent["generated_outputs"].items():
        assert digest(ROOT / "thesis/generated" / name) == expected, name
    for name, expected in parent.get("external_input_files", {}).items():
        assert digest(ROOT / name) == expected, name
    if "interpretation_check_path" in parent:
        assert (
            digest(ROOT / parent["interpretation_check_path"])
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
        scope=args.scope,
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("x") as stream:
        stream.write(json.dumps(review, indent=2) + "\n")
    print(f"Reviewed {review['pages']} pages; all numerical products unchanged")


if __name__ == "__main__":
    main()
