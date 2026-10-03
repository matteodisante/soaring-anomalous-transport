"""Readable typography shared by the viewer's information pages."""

from PyQt6.QtWidgets import QTextBrowser, QWidget


def info_browser(parent: QWidget | None = None) -> QTextBrowser:
    """Create a text browser with larger type, spacing and clickable sources."""
    browser = QTextBrowser(parent)
    font = browser.font()
    font.setPointSizeF(max(15.0, font.pointSizeF() + 2))
    browser.setFont(font)
    browser.document().setDocumentMargin(20)
    browser.document().setDefaultStyleSheet(
        "h2 { margin-top: 0px; margin-bottom: 16px; }"
        "h3 { margin-top: 24px; margin-bottom: 10px; }"
        "p, ul, ol { margin-top: 0px; margin-bottom: 12px; }"
        "li { margin-bottom: 6px; }"
        "td, th { padding: 8px; text-align: left; }"
    )
    browser.setOpenExternalLinks(True)
    return browser
