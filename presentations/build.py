#!/usr/bin/env python3
"""Compile the two complete supervisor chapter decks; never rerun cleaning or analysis."""

from __future__ import annotations

import argparse
import shutil
import subprocess
from pathlib import Path


def main() -> None:
    """Build Chapter 3 first, optionally followed by Chapter 2 and speaker notes."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("chapter", choices=("all", "3", "2"), nargs="?", default="all")
    parser.add_argument(
        "--notes", action="store_true", help="Also build slide + notes PDFs"
    )
    args = parser.parse_args()
    root = Path(__file__).resolve().parent
    if shutil.which("latexmk") is None:
        raise SystemExit("latexmk and a TeX installation are required.")
    for chapter in (3, 2) if args.chapter == "all" else (int(args.chapter),):
        stem = f"chapter{chapter}"
        for notes in [False, True] if args.notes else [False]:
            job = stem + ("-notes" if notes else "")
            out = root / "build" / job
            out.mkdir(parents=True, exist_ok=True)
            target = root / (job + ".tex")
            if notes:
                target.write_text(
                    f"\\def\\Speakernotes{{1}}\n\\input{{{stem}.tex}}\n",
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
                if notes:
                    target.unlink(missing_ok=True)
            shutil.copy2(out / (job + ".pdf"), root / (job + ".pdf"))
            print(f"Built {root / (job + '.pdf')}")


if __name__ == "__main__":
    main()
