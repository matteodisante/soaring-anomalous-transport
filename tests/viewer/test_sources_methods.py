"""The Sources & methods page must state the sources and the numbers the code uses."""

import pytest

pytest.importorskip("PyQt6")
pytest.importorskip("pyproj")

from soaring.viewer.thermal_imagery import LAYERS
from soaring.viewer.thermal_ridges import LAYER
from soaring.viewer.widgets.sources_methods import SourcesMethods, sources_html


def test_page_names_every_data_and_map_source():
    html = sources_html()
    for name in ("FFVL", "Natural Earth", "RGE ALTI", LAYER, "Esri World Hillshade"):
        assert name in html
    for layer in ",".join(LAYERS.values()).split(","):
        assert layer in html


def test_only_the_vilpellet_segmentation_is_described():
    text = " ".join(sources_html().split())
    assert "Vilpellet climb runs on the native fixes" in text
    assert "HMM" not in text


def test_every_contents_link_has_an_anchor():
    html = sources_html()
    for key in (
        "sources",
        "maps",
        "views",
        "tab-planes",
        "thermal-points",
        "tab-routes",
        "tab-3d",
        "caveats",
    ):
        assert f'href="#{key}"' in html
        assert f'name="{key}"' in html


def test_page_is_built_on_first_display(qapp):
    page = SourcesMethods()
    assert page._browser.toPlainText() == ""
    page.ensure_loaded()
    assert "Intersection points" in page._browser.toPlainText()


@pytest.mark.parametrize(
    "screen,expected",
    [
        ("trajectory", "How the trajectories are obtained"),
        ("map", "launch counts per degree-grid cell"),
        ("planes", "Intersection points"),
        ("density", "Cumulative climb time"),
        ("routes", "How flights and ranks are selected"),
        ("terrain", "How the points are obtained"),
        ("locator", "bounding rectangle"),
        ("summary", "viewer-wide summary"),
    ],
)
def test_each_screen_opens_and_reuses_its_own_help(qapp, screen, expected):
    from PyQt6.QtWidgets import QDialog, QTextBrowser

    from soaring.viewer.widgets.map_view import MapView
    from soaring.viewer.widgets.plot_controls import PlotControls
    from soaring.viewer.widgets.route_comparison import RouteComparison
    from soaring.viewer.widgets.route_locator import RouteLocator
    from soaring.viewer.widgets.thermal_3d import Thermal3D
    from soaring.viewer.widgets.thermal_density import ThermalDensity
    from soaring.viewer.widgets.thermal_plane import ThermalPlane

    factories = {
        "trajectory": PlotControls,
        "map": MapView,
        "planes": ThermalPlane,
        "density": ThermalDensity,
        "routes": RouteComparison,
        "terrain": Thermal3D,
        "locator": lambda: RouteLocator(expanded=True),
        "summary": SourcesMethods,
    }
    view = factories[screen]()
    try:
        view.show()
        qapp.processEvents()
        assert view._info.isVisible() and view._info.text() == "Info"
        view._info.click()
        qapp.processEvents()
        dialog = view.findChildren(QDialog)[0]
        assert dialog.isVisible() and not dialog.isModal()
        assert expected in dialog.findChild(QTextBrowser).toPlainText()
        dialog.close()
        view._info.click()
        qapp.processEvents()
        assert dialog.isVisible()
        assert view.findChildren(QDialog) == [dialog]
        dialog.close()
    finally:
        if hasattr(view, "shutdown"):
            view.shutdown()
        view.close()
