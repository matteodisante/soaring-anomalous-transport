"""Semantic palettes for Section 3.2, separate from discipline blue/orange."""

CIRCUIT_COLORS = {"Open": "#7B3294", "Closed": "#008577"}
GEOMETRY_COLORS = {"Triangle": "#D1495B", "Out-and-return": "#3D5A80"}
ALTITUDE_COLORS = {
    "Plains": "#547A3B",
    "Hills": "#9B7A35",
    "Low mountains": "#9A4C68",
    "High mountains": "#60528C",
}
REGION_COLORS = {
    "Alps": "#8E3B5C",
    "Pyrenees": "#8A6240",
    "Channel Coast": "#2E7D8A",
    "Champagne-Lorraine": "#817268",
}
EQUIPMENT_COLORS = {"Beginners": "#686868", "Experts": "#B83B83"}
CONDITIONAL_COLORS = {
    **CIRCUIT_COLORS,
    **GEOMETRY_COLORS,
    **ALTITUDE_COLORS,
    **REGION_COLORS,
    **EQUIPMENT_COLORS,
}
