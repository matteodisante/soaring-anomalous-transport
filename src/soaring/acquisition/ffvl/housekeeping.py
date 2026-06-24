"""Pulizia dei file AppleDouble (`._*`) creati da macOS su volumi exfat.

Su volumi exfat (senza xattr nativi) macOS scrive, accanto a ogni file, un sidecar
``._nome`` di ~4 KB per conservare l'attributo ``com.apple.provenance``.
Su centinaia di migliaia di tracciati questi file sporcano i ``glob('*.igc')`` e
sprecano spazio. ``dot_clean`` li rimuove. La pulizia e' best-effort: se non siamo su
macOS o ``dot_clean`` non c'e', viene semplicemente saltata.
"""

from __future__ import annotations

import logging
import shutil
import subprocess
import sys
from pathlib import Path

logger = logging.getLogger(__name__)


def clean_appledouble(root: Path) -> bool:
    """Rimuove i file sidecar ``._*`` sotto ``root`` tramite ``dot_clean``.

    Args:
        root: Cartella da ripulire (ricorsivamente).

    Returns:
        ``True`` se la pulizia e' stata eseguita; ``False`` se saltata (non su macOS,
        ``dot_clean`` assente, o cartella inesistente).
    """
    if sys.platform != "darwin" or shutil.which("dot_clean") is None:
        logger.debug("dot_clean non disponibile: salto la pulizia dei file '._'")
        return False
    if not root.exists():
        return False
    try:
        subprocess.run(["dot_clean", "-m", str(root)], check=True, capture_output=True)
    except (subprocess.CalledProcessError, OSError) as err:
        logger.warning("Pulizia dei file '._' fallita: %s", err)
        return False
    logger.info("Pulizia dei file '._' completata in %s", root)
    return True
