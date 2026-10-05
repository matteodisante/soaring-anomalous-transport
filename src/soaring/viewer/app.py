"""Entry point for the ``soaring-viewer`` console script."""

from __future__ import annotations

import sys


def configure_graphics() -> None:
    """Choose a shared core profile before Qt creates any internal contexts.

    macOS cannot share the terrain widget's core-profile textures with Qt's
    default legacy context. Configure all windows before QApplication exists,
    including the backing-store compositor used by modeless 3D dialogs.
    """
    from PyQt6.QtCore import QCoreApplication, Qt
    from PyQt6.QtGui import QSurfaceFormat

    fmt = QSurfaceFormat()
    fmt.setRenderableType(QSurfaceFormat.RenderableType.OpenGL)
    fmt.setVersion(3, 3)
    fmt.setProfile(QSurfaceFormat.OpenGLContextProfile.CoreProfile)
    fmt.setDepthBufferSize(24)
    fmt.setStencilBufferSize(8)
    fmt.setSamples(4)
    QSurfaceFormat.setDefaultFormat(fmt)
    QCoreApplication.setAttribute(Qt.ApplicationAttribute.AA_ShareOpenGLContexts)


def main() -> int:
    """Launch the trajectory viewer. Returns the process exit code."""
    configure_graphics()

    from PyQt6.QtWidgets import QApplication

    from .main_window import MainWindow

    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
