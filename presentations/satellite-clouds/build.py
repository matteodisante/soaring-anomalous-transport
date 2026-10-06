"""Compile the slide and slide+notes PDFs on disk, without opening a viewer."""

import shutil
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
STEM = "satellite-clouds"


def publish_pdf(source: Path, target: Path) -> None:
    """Replace ``target`` atomically, and only when the PDF changed."""
    if target.exists() and source.read_bytes() == target.read_bytes():
        return
    with tempfile.NamedTemporaryFile(
        dir=target.parent, prefix=f".{target.stem}-", suffix=".pdf", delete=False
    ) as pending:
        temporary = Path(pending.name)
    try:
        shutil.copy2(source, temporary)
        temporary.replace(target)
    finally:
        temporary.unlink(missing_ok=True)


for notes in (False, True):
    stem = STEM + ("-notes" if notes else "")
    build = ROOT / "build" / stem
    build.mkdir(parents=True, exist_ok=True)
    source = ROOT / (stem + ".tex")
    if notes:
        source.write_text(f"\\def\\Speakernotes{{1}}\n\\input{{{STEM}.tex}}\n")
    try:
        subprocess.run(
            ["latexmk", "-pdf", "-pv-", "-pvc-", "-view=none",
             "-interaction=nonstopmode", "-halt-on-error", "-file-line-error",
             f"-outdir={build}", source.name],
            cwd=ROOT, check=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        )
    except subprocess.CalledProcessError as error:
        print(error.stdout.decode(errors="replace")[-4000:])
        raise
    finally:
        if notes:
            source.unlink(missing_ok=True)
    publish_pdf(build / (stem + ".pdf"), ROOT / (stem + ".pdf"))
    print(f"Built {stem}.pdf")
