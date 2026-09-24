"""Compile both PDFs on disk without opening a viewer or a save dialog."""
from pathlib import Path
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parent


def publish_pdf(source: Path, target: Path) -> None:
    # A no-op build must not send another file-change event to an open reader.
    if target.exists() and source.read_bytes() == target.read_bytes():
        return
    # Never truncate a PDF while Preview/PDFgear may be reading it. Copy beside
    # the target, then replace it atomically on the same filesystem.
    with tempfile.NamedTemporaryFile(dir=target.parent, prefix=f".{target.stem}-",
                                     suffix=".pdf", delete=False) as pending:
        temporary = Path(pending.name)
    try:
        shutil.copy2(source, temporary)
        temporary.replace(target)
    finally:
        temporary.unlink(missing_ok=True)


# This deck has one PDF page per explicit frame, including in the notes version.
expected_pages = sum(
    line.lstrip().startswith(r"\begin{frame}")
    for line in (ROOT / "offsite-2026.tex").read_text().splitlines()
)
for notes in (False, True):
    stem = "offsite-2026" + ("-notes" if notes else "")
    build = ROOT / "build" / stem
    build.mkdir(parents=True, exist_ok=True)
    source = ROOT / (stem + ".tex")
    if notes:
        source.write_text("\\def\\Speakernotes{1}\n\\input{offsite-2026.tex}\n")
    try:
        subprocess.run(["latexmk", "-pdf", "-pv-", "-pvc-", "-view=none", "-interaction=nonstopmode", "-halt-on-error", "-file-line-error", f"-outdir={build}", source.name], cwd=ROOT, check=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    except subprocess.CalledProcessError as error:
        print(error.stdout.decode(errors="replace"))
        raise
    finally:
        if notes: source.unlink(missing_ok=True)
    compiled = build / (stem + ".pdf")
    info = subprocess.check_output(["pdfinfo", str(compiled)], text=True)
    pages = int(next(line.split(":")[1] for line in info.splitlines() if line.startswith("Pages:")))
    assert pages == expected_pages, (stem, pages, expected_pages)
    publish_pdf(compiled, ROOT / (stem + ".pdf"))
    print(f"Built {stem}.pdf ({pages} pages)")
