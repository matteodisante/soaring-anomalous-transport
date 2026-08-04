#!/usr/bin/env python3
r"""Check that every generated macro the thesis quotes is one a generator writes.

The thesis quotes its numbers through macros (``\StatPipe*``, ``\StatScan*``,
``\StatMsd*``, ``\Preproc*``) so that no figure is ever typed by hand: each is written
into ``thesis/generated/`` by a reporting script, from the data itself. The contract
has one failure mode, and it is worse than it sounds. A macro *quoted* and never
*written* is an undefined control sequence, and where it sits inside a ``\\SI{}`` --
which is where most of them sit, since most are physical quantities -- siunitx does
not degrade to a warning: the argument fails to parse, the braces unbalance, and the
build dies with dozens of *Extra }* errors pointing at lines that are perfectly
correct. One missing macro is therefore not a blemish on a page, it is a thesis that
does not compile, diagnosed from a symptom that names the wrong place. It has happened
here three times, each time because a number was argued for in the text before its
generator knew about it.

This script reads both sides and reports the difference, in a second and with no build:

* **quoted but not defined** is an error. Either the generator is missing the number, or
  the thesis quotes a macro that no longer exists.
* **defined but not quoted** is only reported. A generator may legitimately write more
  than the current draft uses -- a macro dropped from the text in a revision, or one
  written for a section not yet drafted -- so it is a note, not a failure.

The numbers themselves are not checked here; that is the job of the generators, which
recompute them from the data. What is checked is that the two lists agree.

Usage::

    python scripts/reporting/check_generated_macros.py [--quiet]
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

THESIS = Path(__file__).resolve().parents[2] / "thesis"
GENERATED = THESIS / "generated"

# Macro families written by a generator. A macro outside these prefixes is hand-written
# LaTeX (a command defined in the preamble) and none of this script's business.
PREFIXES = ("Stat", "Preproc")

_DEFINITION = re.compile(r"\\newcommand\{\\([A-Za-z]+)\}")
_USE = re.compile(r"\\((?:" + "|".join(PREFIXES) + r")[A-Za-z]+)")


def defined_macros() -> set[str]:
    """Every macro name ``thesis/generated/*.tex`` defines."""
    return {
        name
        for path in sorted(GENERATED.glob("*.tex"))
        for name in _DEFINITION.findall(path.read_text(encoding="utf-8"))
    }


def quoted_macros() -> dict[str, set[str]]:
    """Every generated-family macro the thesis quotes, and the files quoting it."""
    out: dict[str, set[str]] = {}
    for path in sorted(THESIS.rglob("*.tex")):
        if path.is_relative_to(GENERATED):
            continue
        for match in _USE.finditer(path.read_text(encoding="utf-8")):
            out.setdefault(match.group(1), set()).add(
                str(path.relative_to(THESIS.parent))
            )
    return out


def invalid_names() -> list[str]:
    r"""Generated macro names LaTeX cannot accept, whether or not anything quotes them.

    A control sequence is letters only. ``\newcommand{\StatMsdParaCohortAlpha1H}{...}``
    therefore parses as ``\StatMsdParaCohortAlpha`` followed by the characters ``1H``,
    and ``\newcommand`` reads that 1 as an argument count -- twelve errors and a build
    that stops, from a *definition* nothing was even quoting. The contract check above
    cannot see it, since the macro is written; only a build can, and only if something
    quotes it. So the names are checked here directly.
    """
    bad = []
    for path in sorted(GENERATED.glob("*.tex")):
        for line in path.read_text(encoding="utf-8").splitlines():
            match = re.match(r"\\newcommand\{\\([^}]+)\}", line)
            if match and not match.group(1).isalpha():
                bad.append(f"{path.name}: \\{match.group(1)}")
    return bad


def main(argv: list[str] | None = None) -> int:
    """Report the difference; non-zero exit if the thesis quotes an undefined macro."""
    quiet = "--quiet" in (argv if argv is not None else sys.argv[1:])
    defined, quoted = defined_macros(), quoted_macros()

    unusable = invalid_names()
    for name in unusable:
        print(f"  UNUSABLE  {name}  (a control sequence takes letters only)")

    missing = sorted(name for name in quoted if name not in defined)
    unused = sorted(defined - set(quoted))

    if not quiet:
        print(f"{len(defined)} macros written, {len(quoted)} quoted by the thesis")
    for name in missing:
        print(f"  MISSING  \\{name}  <- {', '.join(sorted(quoted[name]))}")
    if unused and not quiet:
        print(f"  {len(unused)} written but not quoted (not an error): ", end="")
        print(", ".join(unused[:8]) + (" ..." if len(unused) > 8 else ""))

    if unusable:
        print(
            f"\n{len(unusable)} generated macro name(s) LaTeX cannot accept. The build "
            "will fail on the definition, whether or not anything quotes it."
        )
        return 1
    if missing:
        print(
            f"\n{len(missing)} macro(s) quoted and never written. Re-run the generator "
            "that owns them, or correct the thesis."
        )
        return 1
    if not quiet:
        print("every quoted macro is written by a generator.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
