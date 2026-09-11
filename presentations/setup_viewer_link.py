#!/usr/bin/env python3
"""Register the local macOS soaring-viewer://open handler used by Chapter 2."""

from __future__ import annotations

import plistlib
import subprocess
import sys
from pathlib import Path


def main() -> None:
    """Build a relocatable AppleScript app beside the launcher and register it."""
    if sys.platform != "darwin":
        raise SystemExit(
            "This URL handler is for macOS; "
            "use launch_viewer.command on other Unix systems."
        )
    root = Path(__file__).resolve().parent
    app = root / "Soaring Viewer.app"
    subprocess.run(
        ["/usr/bin/osacompile", "-o", str(app), str(root / "viewer-link.applescript")],
        check=True,
    )
    plist_path = app / "Contents/Info.plist"
    with plist_path.open("rb") as stream:
        info = plistlib.load(stream)
    info.update(
        {
            "CFBundleIdentifier": "org.matteodisante.soaring.viewerlink",
            "CFBundleName": "Soaring Viewer",
            "LSUIElement": True,
            "CFBundleURLTypes": [
                {
                    "CFBundleURLName": "Soaring Python trajectory viewer",
                    "CFBundleURLSchemes": ["soaring-viewer"],
                    "CFBundleTypeRole": "Viewer",
                }
            ],
        }
    )
    with plist_path.open("wb") as stream:
        plistlib.dump(info, stream)
    # osacompile may sign its output. Re-sign after adding the URL declaration.
    subprocess.run(
        ["/usr/bin/codesign", "--force", "--sign", "-", str(app)], check=True
    )
    register = (
        "/System/Library/Frameworks/CoreServices.framework/Frameworks/"
        "LaunchServices.framework/Support/lsregister"
    )
    subprocess.run([register, "-f", str(app)], check=True)
    print("Registered soaring-viewer://open")
    print(
        "Fallback: double-click launch_viewer.command. "
        "The app reads the current repository viewer."
    )


if __name__ == "__main__":
    main()
