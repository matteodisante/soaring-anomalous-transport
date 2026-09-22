"""Flight-level strata for the fixed-cohort conditional transport analysis.

The equipment split belongs to the current thesis. Historical experiments retain
their earlier A/B versus C/D/CCC convention in reporting.glider_class.
"""

import numpy as np

from soaring.analysis.observables.global_diagnostics import closed_route_geometry
from soaring.analysis.regions import region_box_masks
from soaring.reporting.glider_class import canonical_wing_class

BANDS = ("Plains", "Hills", "Low mountains", "High mountains")
EQUIPMENT = {"Beginners": ("EN A", "EN B", "EN C"), "Experts": ("EN D", "CCC")}
REGIONAL_TERRAIN = {
    "Alps": "mountains",
    "Pyrenees": "mountains",
    "Channel Coast": "lowlands",
    "Champagne-Lorraine": "lowlands",
}


def strata(frame):
    """Return aligned Boolean masks; missing labels never enter named groups."""
    wing = canonical_wing_class("paragliders", frame.wing_class)
    groups = {"all": np.ones(len(frame), dtype=bool)}
    for task in ("open", "closed"):
        groups[task] = frame.task.eq(task).fillna(False).to_numpy(dtype=bool)
    geometry = (
        frame.flight_type.map(closed_route_geometry)
        if "flight_type" in frame
        else None
    )
    for shape in ("triangle", "out_and_return"):
        groups[shape] = (
            geometry.eq(shape).to_numpy(dtype=bool)
            if geometry is not None
            else np.zeros(len(frame), dtype=bool)
        )
    for i, band in enumerate(BANDS):
        groups[f"alt{i}"] = (
            frame.altitude_band.eq(band).fillna(False).to_numpy(dtype=bool)
        )
        for task in ("open", "closed"):
            groups[f"{task}_{i}"] = groups[task] & groups[f"alt{i}"]
    groups["mountains"] = groups["alt2"] | groups["alt3"]
    groups["lowlands"] = groups["alt0"] | groups["alt1"]
    for name, classes in EQUIPMENT.items():
        key = name.lower()
        groups[key] = np.isin(wing, classes)
        for terrain in ("mountains", "lowlands", "alt0", "alt1", "alt2", "alt3"):
            groups[f"{key}_{terrain}"] = groups[key] & groups[terrain]
    for name, region in region_box_masks(frame).items():
        key = name.lower().replace(" ", "_").replace("-", "_")
        groups[key] = region & groups[REGIONAL_TERRAIN[name]]
    return groups
