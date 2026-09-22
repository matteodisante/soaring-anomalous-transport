"""Compile the twenty-eight-slide offsite deck and the companion speaker-notes PDF."""
from pathlib import Path
import shutil
import subprocess

ROOT = Path(__file__).resolve().parent
for notes in (False, True):
    stem = "offsite-2026" + ("-notes" if notes else "")
    build = ROOT / "build" / stem
    build.mkdir(parents=True, exist_ok=True)
    source = ROOT / (stem + ".tex")
    if notes:
        source.write_text("\\def\\Speakernotes{1}\n\\input{offsite-2026.tex}\n")
    try:
        subprocess.run(["latexmk", "-pdf", "-interaction=nonstopmode", "-halt-on-error", "-file-line-error", f"-outdir={build}", source.name], cwd=ROOT, check=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    except subprocess.CalledProcessError as error:
        print(error.stdout.decode(errors="replace"))
        raise
    finally:
        if notes: source.unlink(missing_ok=True)
    shutil.copy2(build / (stem + ".pdf"), ROOT / (stem + ".pdf"))
    info = subprocess.check_output(["pdfinfo", str(ROOT / (stem + ".pdf"))], text=True)
    pages = int(next(line.split(":")[1] for line in info.splitlines() if line.startswith("Pages:")))
    assert pages == 28, (stem, pages)
    print(f"Built {stem}.pdf ({pages} pages)")
