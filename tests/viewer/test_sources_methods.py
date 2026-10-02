"""The Sources & methods page must state the sources and the numbers the code uses."""

import pytest

pytest.importorskip("PyQt6")
pytest.importorskip("pyproj")

from soaring.analysis.segmentation.config import load_segmentation_config
from soaring.viewer.thermal_imagery import LAYERS
from soaring.viewer.thermal_ridges import LAYER
from soaring.viewer.widgets.sources_methods import SourcesMethods, sources_html


def test_page_names_every_data_and_map_source():
    html = sources_html()
    for name in ("FFVL", "Natural Earth", "RGE ALTI", LAYER, "Esri World Hillshade"):
        assert name in html
    for layer in ",".join(LAYERS.values()).split(","):
        assert layer in html


def test_numbers_follow_the_configuration():
    text = " ".join(sources_html().split())
    assert f"one every {load_segmentation_config().decision_step_s:g} s" in text


def test_every_contents_link_has_an_anchor():
    html = sources_html()
    for key in ("sources", "maps", "tab-planes", "thermal-points", "caveats"):
        assert f'href="#{key}"' in html
        assert f'name="{key}"' in html


def test_page_is_built_on_first_display(qapp):
    page = SourcesMethods()
    assert page._browser.toPlainText() == ""
    page.ensure_loaded()
    assert "Intersection points" in page._browser.toPlainText()
