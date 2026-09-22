"""Crop the figures shown in the two paper-review decks from the Zotero PDFs.

Neggers et al. (2003) is rendered at 300 dpi with pdftoppm; Arakawa and
Schubert (1974) is a 300-dpi scan whose page images are extracted with
pdfimages. Boxes are (left, top, right, bottom) in 300-dpi pixels; a box may come with
page-coordinate rectangles to blank, used to drop panel letters.
"""
from pathlib import Path
import subprocess
import tempfile

from PIL import Image

ROOT = Path(__file__).resolve().parent
ZOTERO = Path.home() / "Zotero/storage"
NEGGERS = ZOTERO / "WIZ6AR53/Neggers et al. - 2003 - Size Statistics of Cumulus Cloud Populations in Large-Eddy Simulations.pdf"
ARAKAWA = ZOTERO / "NRBB6NCN/atsc-1520-0469_1974_031_0674_ioacce_2_0_co_2.pdf"

# PDF page number (1-based) -> {asset name: box}
NEGGERS_BOXES = {
    5: {"fig3": (310, 295, 1235, 1035)},
    6: {"fig4a": (1390, 285, 2180, 1005)},
    7: {"fig6": (1390, 2050, 2165, 2780)},
    8: {
        "fig7a": ((390, 290, 1140, 1015), [(390, 290, 440, 362)]),
        "fig7b": ((390, 1065, 1150, 1800), [(390, 1065, 433, 1140)]),
        "fig7c": ((390, 1850, 1150, 2560), [(390, 1850, 440, 1932)]),
    },
}
ARAKAWA_BOXES = {
    2: {"fig1": (600, 290, 1890, 905)},
    10: {"fig5": (200, 2040, 1185, 2850), "fig6": (1225, 300, 2200, 1030)},
    11: {"fig8": (1280, 1640, 2140, 2790)},
    12: {"fig9": (510, 285, 1830, 735), "fig10": (1230, 2100, 2215, 2800)},
    16: {"fig11": (1200, 270, 2205, 1045), "fig12": (1240, 2255, 2330, 2630)},
    20: {"fig13a": (560, 320, 1810, 1385), "fig13b": (560, 1400, 1810, 2465)},
    21: {"fig14": (560, 305, 1840, 1190)},
}


def neggers_page(tmp, page):
    """Render one page of the vector PDF at 300 dpi."""
    stem = Path(tmp) / f"n{page}"
    subprocess.run(["pdftoppm", "-r", "300", "-png", "-singlefile", "-f", str(page),
                    "-l", str(page), str(NEGGERS), str(stem)], check=True)
    return Image.open(f"{stem}.png").convert("L")


def arakawa_page(tmp, page):
    """Extract the scanned page image (one 300-dpi bilevel image per page)."""
    stem = Path(tmp) / f"a{page}"
    subprocess.run(["pdfimages", "-tiff", "-f", str(page), "-l", str(page),
                    str(ARAKAWA), str(stem)], check=True)
    return Image.open(f"{stem}-000.tif").convert("L")


def main():
    with tempfile.TemporaryDirectory() as tmp:
        for boxes, loader, folder in ((NEGGERS_BOXES, neggers_page, "neggers2003"),
                                      (ARAKAWA_BOXES, arakawa_page, "arakawa1974")):
            out = ROOT / "assets" / folder
            out.mkdir(parents=True, exist_ok=True)
            for page, crops in boxes.items():
                image = loader(tmp, page)
                for name, box in crops.items():
                    box, blanks = box if isinstance(box[0], tuple) else (box, [])
                    page_image = image.copy()
                    for rect in blanks:
                        page_image.paste(255, rect)
                    page_image.crop(box).save(out / f"{name}.png", optimize=True)
                    print(f"{folder}/{name}.png  page {page}  box {box}")


if __name__ == "__main__":
    main()
