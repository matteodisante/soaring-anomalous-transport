"""Source links and map uses shared by the information pages."""

from ..thermal_imagery import LAYERS
from ..thermal_relief import SOURCE_URL as HILLSHADE_URL

FFVL_PARAGLIDING = "https://parapente.ffvl.fr/cfd/liste"
FFVL_HANG_GLIDING = "https://delta.ffvl.fr/cfd/liste"
NATURAL_EARTH = (
    "https://www.naturalearthdata.com/downloads/10m-cultural-vectors/"
    "10m-admin-0-countries/"
)
NATURAL_EARTH_WORLD = (
    "https://www.naturalearthdata.com/downloads/50m-cultural-vectors/"
    "50m-admin-0-countries-2/"
)
PLAN_IGN = "https://www.data.gouv.fr/datasets/plan-ign"
BD_ORTHO = "https://cartes.gouv.fr/rechercher-une-donnee/dataset/IGNF_BD-ORTHO"
CONTOURS = "https://www.data.gouv.fr/datasets/courbes-de-niveau-4"
ORTHO_DATES = (
    "https://data.geopf.fr/wfs/ows?SERVICE=WFS&amp;VERSION=2.0.0"
    "&amp;REQUEST=DescribeFeatureType"
    "&amp;TYPENAMES=ORTHOIMAGERY.ORTHOPHOTOS.GRAPHE-MOSAIQUAGE:graphe_bdortho"
)
LICENCE_OUVERTE = "https://www.etalab.gouv.fr/licence-ouverte-open-licence/"

FLIGHT_SOURCE_HTML = (
    f'<a href="{FFVL_PARAGLIDING}">FFVL CFD paragliders</a> / '
    f'<a href="{FFVL_HANG_GLIDING}">hang gliders</a>'
)


def background_sources_html() -> str:
    """Name each background's data, viewer control and purpose."""
    return f"""
<p>Backgrounds in <b>Thermal planes</b> and <b>Thermal density</b>:</p>
<ul>
<li><a href="{PLAN_IGN}" title="{LAYERS["colour"]}">IGN Plan IGN v2</a>:
<b>Colour map</b>. A drawn map: roads, place names and symbols for land features.
Use it to locate flights and identify places.</li>
<li><a href="{BD_ORTHO}" title="{LAYERS["aerial"]}">IGN BD ORTHO</a>:
<b>Aerial photo</b>. Actual aerial photographs, corrected to align with map
coordinates. Use them to see fields, forests and buildings beneath the flights.</li>
<li><a href="{CONTOURS}" title="{LAYERS["topography"]}">IGN elevation contours</a>:
<b>Topography + contours</b>. The same Colour map, with elevation lines added.
Each line joins locations at the same ground altitude; closer lines indicate
steeper slopes. Use them to read terrain height and slope.</li>
<li><a href="{HILLSHADE_URL}">Esri World Hillshade</a>:
<b>Shaded relief</b>. Shaded terrain to locate ridges and valleys.</li>
</ul>
<p>These images provide visual context. Flight counts, climb labels and plane
altitudes are calculated independently of the selected background.</p>
"""


def aerial_dates_html() -> str:
    """Explain the separate source used to date the aerial photographs."""
    return f"""
<p><a href="{ORTHO_DATES}">IGN BD ORTHO mosaic graph</a>: acquisition dates
shown below the <b>Thermal planes</b> controls. They date the photographs;
flight dates come from IGC recordings. A cell can contain several photo dates.</p>
"""
