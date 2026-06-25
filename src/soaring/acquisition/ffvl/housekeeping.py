"""Cleanup of AppleDouble files (`._*`) created by macOS on exfat volumes.

On exfat volumes (without native xattr) macOS writes, next to every file, a ``._name``
sidecar of ~4 KB to store the ``com.apple.provenance`` attribute.
With hundreds of thousands of tracks, these files pollute ``glob('*.igc')`` results and
waste space. ``dot_clean`` removes them. The cleanup is best-effort: if not on macOS or
``dot_clean`` is absent, it is simply skipped.
"""

from __future__ import annotations

import logging
import shutil
import subprocess
import sys
from pathlib import Path

logger = logging.getLogger(__name__)


def clean_appledouble(root: Path) -> bool:
    """Removes ``._*`` sidecar files under ``root`` via ``dot_clean``.

    Args:
        root: Directory to clean (recursively).

    Returns:
        ``True`` if cleanup was performed; ``False`` if skipped (not on macOS,
        ``dot_clean`` absent, or directory does not exist).
    """
    if sys.platform != "darwin" or shutil.which("dot_clean") is None:
        logger.debug("dot_clean not available: skipping '._' file cleanup")
        return False
    if not root.exists():
        return False
    try:
        subprocess.run(["dot_clean", "-m", str(root)], check=True, capture_output=True)
    except (subprocess.CalledProcessError, OSError) as err:
        logger.warning("'._' file cleanup failed: %s", err)
        return False
    logger.info("'._' file cleanup completed in %s", root)
    return True
