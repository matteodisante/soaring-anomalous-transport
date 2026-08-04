#!/usr/bin/env python3
"""Extract Skim annotations (colour + note + marked text + source location).

Skim keeps its notes in extended attributes, not in the PDF object tree, and its
own text export drops both the colour and the text that was marked up. This
script recovers all four fields:

1. ``skimpdf embed``   writes the notes out as real PDF annotations;
2. ``pypdf``           reads /Subtype, /C (colour), /Contents (the typed note)
                       and /QuadPoints (where the mark sits on the page);
3. ``pdftotext -bbox`` gives word boxes, intersected with the quads to recover
                       the marked-up text;
4. ``synctex edit``    maps each mark back to ``file:line`` in the LaTeX sources.

Step 4 needs a build of the *same* PDF carrying a .synctex.gz; the script builds
one in a temp directory and refuses to use it unless it is byte-identical to the
annotated PDF (otherwise the line numbers would silently drift).

Usage:
    extract_annotations.py ANNOTATED.pdf OUT.json [OUT.md] [--tex-root main.tex]
"""
from __future__ import annotations

import hashlib
import html
import json
import re
import subprocess
import sys
import tempfile
from collections import Counter
from pathlib import Path
from xml.etree import ElementTree as ET

import pypdf

SKIMPDF = "/Applications/Skim.app/Contents/SharedSupport/skimpdf"
MARKUP = {"/Highlight", "/StrikeOut", "/Underline", "/Squiggly", "/FreeText", "/Text"}

# Skim's palette as written into /C, mapped to the names used in the review.
COLOURS = {
    (0.0, 1.0, 0.0): "green",
    (1.0, 1.0, 0.0): "yellow",
    (1.0, 0.0, 0.0): "red",
    (1.0, 0.5, 0.0): "orange",
    (1.0, 0.0, 1.0): "purple",
    (0.0, 1.0, 1.0): "cyan",
    (0.0, 0.0, 1.0): "blue",
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def colour_name(c) -> str:
    if not c:
        return "none"
    key = tuple(round(float(x), 3) for x in c)
    if key in COLOURS:
        return COLOURS[key]
    # nearest neighbour, so a hand-picked shade still lands in a named bucket
    best = min(COLOURS, key=lambda k: sum((a - b) ** 2 for a, b in zip(k, key)))
    return f"{COLOURS[best]}?{key}"


def words_by_page(pdf: Path):
    """[(x0, y0, x1, y1, text)] per page, in PDF coordinates (y from bottom)."""
    with tempfile.TemporaryDirectory() as td:
        out = Path(td) / "bbox.xml"
        subprocess.run(["pdftotext", "-bbox-layout", str(pdf), str(out)],
                       check=True, capture_output=True)
        raw = out.read_text(encoding="utf-8", errors="replace")
    raw = raw.split("<body>", 1)[1].rsplit("</body>", 1)[0]  # drop poppler's DOCTYPE
    root = ET.fromstring(f"<body>{raw}</body>")
    pages = []
    for page in root.iter("page"):
        h = float(page.get("height"))
        pages.append([
            (float(w.get("xMin")), h - float(w.get("yMax")),
             float(w.get("xMax")), h - float(w.get("yMin")),
             html.unescape(w.text or ""))
            for w in page.iter("word")
        ])
    return pages


def marked_text(quads, words) -> str:
    """Words whose centre falls inside any quad of the annotation."""
    rects = []
    for i in range(0, len(quads), 8):
        q = [float(v) for v in quads[i:i + 8]]
        xs, ys = q[0::2], q[1::2]
        rects.append((min(xs), min(ys), max(xs), max(ys)))
    picked = []
    for x0, y0, x1, y1, text in words:
        cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
        if any(rx0 - 1 <= cx <= rx1 + 1 and ry0 - 2 <= cy <= ry1 + 2
               for rx0, ry0, rx1, ry1 in rects):
            picked.append((-cy, cx, text))
    picked.sort()
    return re.sub(r"\s+", " ", " ".join(t for _, _, t in picked)).strip()


def build_synctex(tex_root: Path, reference: Path, workdir: Path):
    """Build tex_root with SyncTeX; return the pdf path iff it matches reference."""
    out = workdir / "synctex-build"
    out.mkdir(exist_ok=True)
    r = subprocess.run(
        ["latexmk", "-pdf", "-synctex=1", "-interaction=nonstopmode",
         f"-outdir={out}", tex_root.name],
        cwd=tex_root.parent, capture_output=True, text=True,
    )
    pdf = out / (tex_root.stem + ".pdf")
    if r.returncode != 0 or not pdf.exists():
        print("  ! synctex build failed; source locations will be omitted", file=sys.stderr)
        return None
    if sha256(pdf) != sha256(reference):
        print("  ! synctex build differs from the annotated PDF; sources have moved "
              "on since the review — locations omitted, locate by text instead",
              file=sys.stderr)
        return None
    return pdf


def synctex_locate(pdf: Path, page: int, x: float, y_from_top: float):
    r = subprocess.run(["synctex", "edit", "-o", f"{page}:{x:.1f}:{y_from_top:.1f}:{pdf}"],
                       capture_output=True, text=True)
    src = line = None
    for row in r.stdout.splitlines():
        if row.startswith("Input:"):
            src = row.split(":", 1)[1].strip()
        elif row.startswith("Line:"):
            line = row.split(":", 1)[1].strip()
    return src, line


def main() -> int:
    argv = [a for a in sys.argv[1:] if not a.startswith("--")]
    tex_root = None
    for a in sys.argv[1:]:
        if a.startswith("--tex-root="):
            tex_root = Path(a.split("=", 1)[1]).resolve()
    src, out_json = Path(argv[0]).resolve(), Path(argv[1]).resolve()
    out_md = Path(argv[2]).resolve() if len(argv) > 2 else None

    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        embedded = td / "embedded.pdf"
        subprocess.run([SKIMPDF, "embed", str(src), str(embedded)],
                       check=True, capture_output=True)
        reader = pypdf.PdfReader(str(embedded))
        pages = words_by_page(embedded)
        heights = [float(p.mediabox.height) for p in reader.pages]
        try:
            labels = list(reader.page_labels)
        except Exception:
            labels = [str(i + 1) for i in range(len(reader.pages))]

        sync_pdf = build_synctex(tex_root, src, td) if tex_root else None

        annots = []
        for idx, page in enumerate(reader.pages):
            for ref in page.get("/Annots") or []:
                o = ref.get_object()
                sub = str(o.get("/Subtype"))
                if sub not in MARKUP:
                    continue
                quads = o.get("/QuadPoints")
                rect = [float(v) for v in (o.get("/Rect") or [0, 0, 0, 0])]
                annots.append({
                    "page_index": idx + 1,
                    "page_label": labels[idx] if idx < len(labels) else str(idx + 1),
                    "type": sub.lstrip("/"),
                    "colour": colour_name(o.get("/C")),
                    "y_top": round(rect[3], 2),
                    "x_left": round(rect[0], 2),
                    "marked_text": marked_text(quads, pages[idx]) if quads else "",
                    "note": str(o.get("/Contents") or "").strip(),
                })

        annots.sort(key=lambda a: (a["page_index"], -a["y_top"], a["x_left"]))
        for n, a in enumerate(annots, 1):
            a["id"] = n
            if sync_pdf:
                h = heights[a["page_index"] - 1]
                f, ln = synctex_locate(sync_pdf, a["page_index"],
                                       max(a["x_left"], 1.0), h - a["y_top"] + 2)
                if f:
                    try:
                        f = str(Path(f).resolve().relative_to(Path.cwd()))
                    except ValueError:
                        f = str(Path(f).name)
                a["source"] = f"{f}:{ln}" if f else None

    out_json.write_text(json.dumps(annots, ensure_ascii=False, indent=1), encoding="utf-8")

    if out_md:
        lines = [f"# Annotation digest — `{src.name}`",
                 "",
                 f"{len(annots)} annotations, reading order. `source` is a SyncTeX anchor "
                 "(±1 line: confirm by grepping the marked text).", ""]
        cur = None
        for a in annots:
            if a["page_label"] != cur:
                cur = a["page_label"]
                lines.append(f"\n## page {cur}  (pdf p. {a['page_index']})\n")
            loc = f" — `{a['source']}`" if a.get("source") else ""
            lines.append(f"### [{a['id']}] {a['colour']} {a['type']}{loc}")
            lines.append(f"- **marked**: {a['marked_text'] or '_(no text captured)_'}")
            note = a["note"].replace("\n", "\n  ")
            lines.append(f"- **note**: {note or '_(empty)_'}\n")
        out_md.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(f"{len(annots)} annotations -> {out_json}")
    for (col, typ), n in Counter((a["colour"], a["type"]) for a in annots).most_common():
        print(f"  {n:4d}  {col:8s} {typ}")
    print("  notes empty:", sum(1 for a in annots if not a["note"]))
    print("  marked text empty:", sum(1 for a in annots if not a["marked_text"]))
    print("  source unresolved:", sum(1 for a in annots if not a.get("source")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
