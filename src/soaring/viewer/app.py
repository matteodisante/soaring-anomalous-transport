"""Entry point for the ``soaring-viewer`` console script."""

from __future__ import annotations

import sys


def main() -> int:
    """Launch the trajectory viewer. Returns the process exit code."""
    from PyQt6.QtWidgets import QApplication

    from .main_window import MainWindow

    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
