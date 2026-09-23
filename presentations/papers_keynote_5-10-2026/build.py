"""Compile both paper-review decks, their speaker-notes PDFs and the two reading guides."""
from pathlib import Path
import shutil
import subprocess

ROOT = Path(__file__).resolve().parent
DECKS = {"neggers2003": 5, "arakawa-schubert1974": 6}

for deck, expected in DECKS.items():
    for notes in (False, True):
        stem = deck + ("-notes" if notes else "")
        build = ROOT / "build" / stem
        build.mkdir(parents=True, exist_ok=True)
        source = ROOT / (stem + ".tex")
        if notes:
            source.write_text(f"\\def\\Speakernotes{{1}}\n\\input{{{deck}.tex}}\n")
        try:
            subprocess.run(["latexmk", "-pdf", "-interaction=nonstopmode", "-halt-on-error",
                            "-file-line-error", f"-outdir={build}", source.name],
                           cwd=ROOT, check=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        except subprocess.CalledProcessError as error:
            print(error.stdout.decode(errors="replace")[-4000:])
            raise
        finally:
            if notes:
                source.unlink(missing_ok=True)
        shutil.copy2(build / (stem + ".pdf"), ROOT / (stem + ".pdf"))
        info = subprocess.check_output(["pdfinfo", str(ROOT / (stem + ".pdf"))], text=True)
        pages = int(next(line.split(":")[1] for line in info.splitlines() if line.startswith("Pages:")))
        assert pages == expected, (stem, pages)
        print(f"Built {stem}.pdf ({pages} pages)")

GUIDES = {"neggers2003-vademecum": 2, "arakawa-schubert1974-vademecum": 4}
for stem, expected in GUIDES.items():
    build = ROOT / "build" / stem
    build.mkdir(parents=True, exist_ok=True)
    try:
        subprocess.run(["latexmk", "-pdf", "-interaction=nonstopmode", "-halt-on-error",
                        "-file-line-error", f"-outdir={build}", stem + ".tex"],
                       cwd=ROOT, check=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    except subprocess.CalledProcessError as error:
        print(error.stdout.decode(errors="replace")[-4000:])
        raise
    shutil.copy2(build / (stem + ".pdf"), ROOT / (stem + ".pdf"))
    info = subprocess.check_output(["pdfinfo", str(ROOT / (stem + ".pdf"))], text=True)
    pages = int(next(line.split(":")[1] for line in info.splitlines() if line.startswith("Pages:")))
    assert pages == expected, (stem, pages)
    print(f"Built {stem}.pdf ({pages} pages)")
