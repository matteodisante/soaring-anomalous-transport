r"""Writing the generated-macro files the thesis quotes.

The contract the whole repository rests on: no measured number is typed into the thesis,
every one of them is a ``\newcommand`` written by a script into ``thesis/generated/``.
This module is the one place that emission happens, which matters for one reason beyond
removing seven copies of the same loop.

A LaTeX control sequence is letters only, so
``\newcommand{\StatMsdParaCohortAlpha1H}{...}``
parses as ``\StatMsdParaCohortAlpha`` followed by the characters ``1H``, and
``\newcommand`` reads that ``1`` as an argument count -- twelve errors and a build that
stops, from a *definition* that nothing was even quoting. That was caught after the
fact, by ``scripts/reporting/check_generated_macros.py``, once a generator had written
the unusable file. :func:`write_macros` refuses to write it in the first place, so the
error names the generator and the macro instead of a LaTeX line number.
"""

from __future__ import annotations

from collections.abc import ItemsView
from pathlib import Path
from typing import Any


class MacroNameError(ValueError):
    """A macro name LaTeX cannot accept as a control sequence."""


def check_name(name: str) -> None:
    r"""Validates one macro name against what LaTeX will accept.

    Args:
        name: The name without its leading backslash, e.g. ``"StatMsdParaAlpha"``.

    Raises:
        MacroNameError: If the name is empty or holds anything but ASCII letters.
            Spell the digit out (``CohortAlphaOneH``) rather than dropping it.
    """
    if not name.isalpha() or not name.isascii():
        raise MacroNameError(
            rf"\{name}: a LaTeX control sequence is ASCII letters only, so this name "
            "would be read as a shorter macro followed by text -- and a leading digit "
            r"in that text is read by \newcommand as an argument count. Spell the "
            "non-letters out in the name."
        )


class MacroWriter:
    """Accumulates macros under a fixed prefix.

    Replaces the ``def put(name, value)`` closure that each generator defined over its
    own dict. Values are coerced to ``str`` on the way in, so a caller can pass the
    number it just computed and the file still holds what LaTeX will typeset.

    Example:
        >>> w = MacroWriter("StatMsdPara")
        >>> w.put("Alpha", 1.42)
        >>> w.macros
        {'StatMsdParaAlpha': '1.42'}
    """

    def __init__(self, prefix: str = "") -> None:
        """Creates a writer whose names all begin with ``prefix``.

        Args:
            prefix: Prepended to every name passed to :meth:`put`, typically the family
                and the discipline tag (``"StatMsd" + discipline.tag``).
        """
        self.prefix = prefix
        self.macros: dict[str, str] = {}

    def put(self, name: str, value: Any) -> None:
        """Records one macro.

        Args:
            name: The name after the prefix.
            value: Anything with a ``str()``; format it first if the number of decimals
                matters, which it usually does.

        Raises:
            MacroNameError: If the prefixed name is not a valid control sequence.
        """
        full = f"{self.prefix}{name}"
        check_name(full)
        self.macros[full] = str(value)

    def update(self, other: dict[str, str]) -> None:
        """Merges in macros written elsewhere, validating each name.

        Args:
            other: Fully-qualified names to values; the prefix is *not* applied.

        Raises:
            MacroNameError: If any name is not a valid control sequence.
        """
        for name, value in other.items():
            check_name(name)
            self.macros[name] = str(value)

    def items(self) -> ItemsView[str, str]:
        """The recorded macros, in insertion order.

        Returns:
            The ``(name, value)`` pairs.
        """
        return self.macros.items()

    def __len__(self) -> int:
        """The number of macros recorded."""
        return len(self.macros)


def write_macros(
    path: str | Path,
    macros: dict[str, str] | MacroWriter,
    *,
    generator: str,
    sort: bool = False,
    extra_header: list[str] | None = None,
) -> int:
    r"""Writes a generated-macro file, refusing any name LaTeX cannot accept.

    Args:
        path: Destination, normally under ``thesis/generated/``.
        macros: The macros, as a dict or a :class:`MacroWriter`.
        generator: Path of the script writing the file, for the header comment telling
            a reader of the ``.tex`` where to go to change it.
        sort: Sort by name. Off by default so a generator that emits in a meaningful
            order keeps it -- and so this function reorders no existing file.
        extra_header: Further comment lines, written after the generator line. The ``%``
            is added here.

    Returns:
        The number of macros written.

    Raises:
        MacroNameError: If any name is not a valid control sequence; nothing is written.
    """
    pairs = list(macros.items())
    for name, _ in pairs:
        check_name(name)
    if sort:
        pairs.sort()

    lines = [f"% Generated by {generator} -- do not edit."]
    lines += [f"% {line}" for line in extra_header or []]
    lines += [f"\\newcommand{{\\{name}}}{{{value}}}" for name, value in pairs]
    Path(path).write_text("\n".join(lines) + "\n", encoding="utf-8")
    return len(pairs)


def tex_int(value: int | float) -> str:
    """Formats a thousands-separated integer that siunitx will not re-parse.

    Args:
        value: The number; truncated to ``int``.

    Returns:
        e.g. ``"1{,}363{,}998{,}292"``. The braces are what stop siunitx from reading
        the comma as a decimal separator.
    """
    return f"{int(value):,}".replace(",", "{,}")


def pct_of(part: int | float, whole: int | float) -> float:
    """Percentage of a total, ``0.0`` rather than an error when the total is zero.

    Args:
        part: The numerator.
        whole: The denominator.

    Returns:
        ``100 * part / whole``, rounded to one decimal, or ``0.0``.
    """
    return round(100.0 * part / whole, 1) if whole else 0.0


def pct_true(mask: Any) -> float:
    """Percentage of a boolean array that is true, ``0.0`` (not ``NaN``) when empty.

    An empty slice is a real case here -- a discipline with no flight in some category
    -- and ``mean()`` on it returns ``NaN`` with a warning, which then reaches the
    thesis as the string ``nan``.

    Args:
        mask: Anything ``numpy.asarray`` accepts as a boolean array.

    Returns:
        ``100 * mean(mask)``, or ``0.0``.
    """
    import numpy as np

    m = np.asarray(mask)
    return 100.0 * float(m.mean()) if m.size else 0.0
