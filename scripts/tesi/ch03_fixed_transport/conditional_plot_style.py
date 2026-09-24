"""Semantic palettes for Section 3.2, separate from discipline blue/orange."""

CIRCUIT_COLORS = {"Open": "#7B3294", "Closed": "#008577"}
GEOMETRY_COLORS = {"Triangle": "#D1495B", "Out-and-return": "#3D5A80"}
# Four declared closed routes, drawn side by side; checked for colour-vision
# separation. They stay out of CONDITIONAL_COLORS, which already has "Out-and-return".
ROUTE_COLORS = {
    "Flat triangle": "#2A78D6",
    "FAI triangle": "#EB6834",
    "Quadrilateral": "#1BAF7A",
    "Out-and-return": "#4A3AA7",
}
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
