#!/usr/bin/env python3
"""Compile the supervisor decks; never rerun cleaning or analysis."""

from __future__ import annotations

import argparse
import shutil
import subprocess
from pathlib import Path


def main() -> None:
    """Build Chapter 3 first, optionally followed by Chapter 2 and speaker notes."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "chapter", choices=("all", "3", "2", "3.5"), nargs="?", default="all"
    )
    parser.add_argument(
        "--notes", action="store_true", help="Also build slide + notes PDFs"
    )
    args = parser.parse_args()
    root = Path(__file__).resolve().parent
    if shutil.which("latexmk") is None:
        raise SystemExit("latexmk and a TeX installation are required.")
    decks = {
        "2": ("chapter2", None),
        "3": ("chapter3", None),
        "3.5": ("chapter3-section35", None),
    }
    selected = ("3", "2", "3.5") if args.chapter == "all" else (args.chapter,)
    for deck in selected:
        stem, selector = decks[deck]
        for notes in [False, True] if args.notes else [False]:
            job = stem + ("-notes" if notes else "")
            out = root / "build" / job
            out.mkdir(parents=True, exist_ok=True)
            target = root / (job + ".tex")
            if notes or selector:
                definitions = []
                if notes:
                    definitions.append("\\def\\Speakernotes{1}")
                if selector:
                    definitions.append(f"\\def\\{selector}{{1}}")
                source = "chapter3" if selector else stem
                target.write_text(
                    "\n".join(definitions) + f"\n\\input{{{source}.tex}}\n",
                    encoding="utf-8",
                )
            try:
                subprocess.run(
                    [
                        "latexmk",
                        "-pdf",
                        "-interaction=nonstopmode",
                        "-halt-on-error",
                        "-file-line-error",
                        f"-outdir={out}",
                        target.name,
                    ],
                    cwd=root,
                    check=True,
                )
            finally:
                if notes or selector:
                    target.unlink(missing_ok=True)
            shutil.copy2(out / (job + ".pdf"), root / (job + ".pdf"))
            print(f"Built {root / (job + '.pdf')}")


if __name__ == "__main__":
    main()
