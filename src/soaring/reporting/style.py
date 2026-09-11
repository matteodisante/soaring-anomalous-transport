"""Semantic colours and typography for figures printed at thesis text width.

Importing this module does not change Matplotlib settings. Reporting entry points
call ``paper_style`` before drawing; numerical analysis never needs Matplotlib.
"""

DISCIPLINE_COLORS = {"paragliders": "#3477A8", "hang gliders": "#B5482A"}
PHASE_COLORS = {"transition": "#3477A8", "search": "#C98A1E", "climb": "#4E8A5B"}
REGION_COLORS = {
    "Alps": "#B5482A",
    "Pyrenees": "#6A3D9A",
    "Channel Coast": "#2A6DB5",
    "Massif Central": "#B5482A",
    "Poitou-Charente": "#4E8A5B",
    "Champagne-Lorraine": "#6A3D9A",
    "outside massifs": "#777777",
    "abroad": "#CCBB44",
}
EQUIPMENT_COLORS = {"EN A/B": "#3477A8", "EN C/D/CCC": "#B5482A"}
QUANTILE_COLORS = {0.25: "#482878", 0.50: "#31688E", 0.75: "#26828E", 0.90: "#35A779"}
TEXT_WIDTH_IN = 6.1
PDF_METADATA = {
    "Creator": "soaring.analysis",
    "Producer": "soaring.analysis",
    "CreationDate": None,
}


def paper_style() -> None:
    """Readable vector figures at their final 6.1-inch text width."""
    import matplotlib as mpl

    mpl.rcParams.update(
        {
            "font.family": "DejaVu Sans",
            "axes.prop_cycle": mpl.cycler(
                color=["#3477A8", "#B5482A", "#4E8A5B", "#6A3D9A"]
            ),
            "font.size": 9,
            "axes.labelsize": 9,
            "axes.titlesize": 9,
            "axes.titlelocation": "left",
            "xtick.labelsize": 8,
            "ytick.labelsize": 8,
            "legend.fontsize": 8.5,
            "legend.frameon": False,
            "lines.linewidth": 1.1,
            "lines.markersize": 3.0,
            "axes.linewidth": 0.6,
            "axes.spines.top": True,
            "axes.spines.right": True,
            "axes.axisbelow": True,
            "grid.color": ".93",
            "grid.linewidth": 0.4,
            "savefig.dpi": 300,
            "pdf.fonttype": 42,
            "ps.fonttype": 42,
        }
    )
