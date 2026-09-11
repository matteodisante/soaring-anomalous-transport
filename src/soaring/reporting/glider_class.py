r"""Canonical class labels for ``aile_class``, the raw FFVL wing-class field.

The FFVL catalogue records the class in its own French-language codes (e.g.
``"C ou 2"``), not the EN/FAI labels of Table~\ref{tab:aileclass} (Sec.~\ref{sec:glider}).
This is the map between the two, so that a stratum is the same set of flights whichever
code named it, rather than the raw FFVL string passed straight through.

Recovering the placeholder (the literal ``"0"``, or a blank entry) from the wing-model
name would need a wing-model-to-class lookup this repository does not have, so those
flights stay unclassified -- excluded from a class stratum -- rather than guessed.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

#: Raw ``aile_class`` (paragliders) -> the label it is drawn under in
#: Table~\ref{tab:aileclass}. ``Biplace`` (tandem) and the two codes Table~\ref{tab:aileclass}
#: does not itemise (``Open Class certification``, an uncertified competition wing;
#: ``test en charge seulement``, load-tested only) join ``non homologuée`` in the
#: table's pooled "tandem / non-certified" row. None supplies a single-seat EN/LTF
#: grade in this catalogue field; a tandem designation alone does not rule out certification.
PARA_CLASS_MAP: dict[str, str] = {
    "A ou 1": "EN A",
    "B ou 1-2": "EN B",
    "C ou 2": "EN C",
    "D ou 2-3": "EN D",
    "CIVL Competition Class": "CCC",
    "Biplace": "tandem / non-certified",
    "Biplace non homologué": "tandem / non-certified",
    "non homologuée": "tandem / non-certified",
    "Open Class certification": "tandem / non-certified",
    "test en charge seulement": "tandem / non-certified",
}

#: Raw ``aile_class`` (hang gliders) -> the same string: the FAI codes already match
#: Table~\ref{tab:aileclass}. Listed explicitly so an unrecognised code raises rather
#: than silently entering a stratum under its own spelling.
HANG_CLASS_MAP: dict[str, str] = {
    "Delta Class 1": "Delta Class 1",
    "Delta Class Sport": "Delta Class Sport",
    "Rigide Class 2": "Rigide Class 2",
    "Rigide Class 5": "Rigide Class 5",
}

#: The literal placeholder ``aile_class`` carries when the FFVL record has no class.
PLACEHOLDER = "0"


def canonical_wing_class(discipline: str, raw: pd.Series) -> np.ndarray:
    r"""``raw`` (the FFVL ``aile_class`` field) mapped onto Table~\ref{tab:aileclass}'s
    labels.

    The placeholder and a blank or missing entry come back as ``NaN``.

    Raises:
        ValueError: ``discipline`` is neither ``"paragliders"`` nor ``"hang gliders"``,
            or ``raw`` holds a value that is neither the placeholder, blank, nor a key
            of the map -- most likely a new FFVL code the map has not been taught yet.
    """
    if discipline == "paragliders":
        class_map = PARA_CLASS_MAP
    elif discipline == "hang gliders":
        class_map = HANG_CLASS_MAP
    else:
        raise ValueError(f"unknown discipline {discipline!r}")

    stripped = raw.map(lambda value: value.strip() if isinstance(value, str) else value)

    blank = {"", PLACEHOLDER}
    seen = {value for value in stripped.dropna().unique() if value not in blank}
    unknown = sorted(seen - class_map.keys())
    if unknown:
        raise ValueError(
            f"{discipline}: unmapped aile_class value(s) {unknown!r} -- extend "
            "PARA_CLASS_MAP / HANG_CLASS_MAP in soaring.reporting.glider_class"
        )
    return stripped.map(class_map).to_numpy()


EQUIPMENT_CLASSES = {
    "EN A/B": ("EN A", "EN B"),
    "EN C/D/CCC": ("EN C", "EN D", "CCC"),
}
EQUIPMENT_LABELS = {"EN A/B": "Beginners", "EN C/D/CCC": "Experts"}
EQUIPMENT_TAGS = {"EN A/B": "AB", "EN C/D/CCC": "CDCCC"}


def equipment_group(wing_class):
    """Two equipment-based experience proxies, not individual skill measurements.

    A/B forms the beginners group; C/D/CCC forms the experts group. Experienced
    pilots can use A/B wings, and observed differences also include equipment effects.
    Tandem, unknown and non-certified catalogue entries receive neither label.
    """
    wing_class = np.asarray(wing_class, dtype=object)
    labels = np.full(wing_class.shape, "", dtype=object)
    for name, classes in EQUIPMENT_CLASSES.items():
        labels[np.isin(wing_class, classes)] = name
    return labels
