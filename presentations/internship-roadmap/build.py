"""Build the standalone Beamer slides and the companion speaker-notes PDF."""
from pathlib import Path
import shutil
import subprocess
import tempfile

root = Path(__file__).resolve().parent
with tempfile.TemporaryDirectory(prefix="internship-roadmap-") as temporary:
    for name, source in [
        ("internship-roadmap", "internship-roadmap.tex"),
        ("internship-roadmap-notes", r"\def\Speakernotes{1}\input{internship-roadmap.tex}"),
    ]:
        for _ in range(2):
            subprocess.run(["pdflatex", "-interaction=nonstopmode", "-halt-on-error", f"-output-directory={temporary}", f"-jobname={name}", source], cwd=root, check=True, stdout=subprocess.DEVNULL)
        log = (Path(temporary) / f"{name}.log").read_text()
        warnings = [line for line in log.splitlines() if "Overfull" in line or "undefined" in line or "Missing character" in line]
        if warnings:
            raise RuntimeError("\n".join(warnings))
        shutil.copy2(Path(temporary) / f"{name}.pdf", root / f"{name}.pdf")
        print(root / f"{name}.pdf")
