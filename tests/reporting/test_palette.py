"""The colour contract of src/soaring/reporting/style.py.

Colour carries meaning in these figures, so two comparisons sharing a value would
read as a shared meaning. The discipline pair and the equipment pair sit side by
side in Chapter 3 and are reserved for the whole document; every other set has to
be internally distinct and stay off those reserved values.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from soaring.reporting.style import (
    PALETTE_FAMILIES,
    RESERVED_FAMILIES,
)

ROOT = Path(__file__).resolve().parents[2]
_HEX = re.compile(r"#[0-9A-Fa-f]{6}")
# Diagrams label coordinate frames and document accents rather than populations,
# and they always name what a colour means in the same breath, so the reserved
# values stay available to them.
_DIAGRAM_ACCENTS = {"figblue", "figred", "figgreen"}


def _reserved() -> dict[str, tuple[str, str]]:
    """Reserved value -> (family, member) it belongs to."""
    out: dict[str, tuple[str, str]] = {}
    for family in RESERVED_FAMILIES:
        for member, value in PALETTE_FAMILIES[family].items():
            out[value.upper()] = (family, member)
    return out


@pytest.mark.parametrize("family", sorted(PALETTE_FAMILIES))
def test_members_of_a_set_are_distinct(family: str) -> None:
    members = PALETTE_FAMILIES[family]
    seen: dict[str, object] = {}
    for member, value in members.items():
        key = value.upper()
        assert key not in seen, (
            f"{family}: {member} and {seen[key]} share {value}; two members of one "
            "comparison cannot be the same colour"
        )
        seen[key] = member


def test_reserved_values_are_used_by_nothing_else() -> None:
    reserved = _reserved()
    for family, members in PALETTE_FAMILIES.items():
        if family in RESERVED_FAMILIES:
            continue
        for member, value in members.items():
            owner = reserved.get(value.upper())
            assert owner is None, (
                f"{family}.{member} uses {value}, reserved for "
                f"{owner[0]}.{owner[1]}"
            )


def test_reserved_sets_do_not_overlap_each_other() -> None:
    first, second = (set(PALETTE_FAMILIES[f].values()) for f in RESERVED_FAMILIES)
    assert not first & second


def test_no_figure_code_writes_a_reserved_colour_by_hand() -> None:
    """A reserved colour must come from the module, so its meaning stays one thing."""
    reserved = _reserved()
    style = ROOT / "src" / "soaring" / "reporting" / "style.py"
    offenders: list[str] = []
    for path in [
        *(ROOT / "src" / "soaring").rglob("*.py"),
        *(ROOT / "scripts").rglob("*.py"),
    ]:
        if path == style:
            continue
        for number, line in enumerate(
            path.read_text().splitlines(), start=1
        ):
            for value in _HEX.findall(line):
                if value.upper() in reserved:
                    offenders.append(f"{path.relative_to(ROOT)}:{number}: {value}")
    assert not offenders, "hard-coded reserved colours:\n" + "\n".join(offenders)
