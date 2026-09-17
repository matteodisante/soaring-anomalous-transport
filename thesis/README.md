# Thesis and experiments

- `main.tex` / `main.pdf`: Chapters 1–3 and the appendices supporting Chapter 2,
  2.A (spectral estimation) and 2.B (geodetic coordinates).
- `esperimenti.tex` / `esperimenti.pdf`: Chapters 3–7, retaining their original
  numbering, and Appendix 4.A (squared-displacement distributions).
- `preamble.tex`: shared typography and generated measurement macros.

Both documents use the existing section sources and `references.bib`; each has
its own table of contents and bibliography. The thesis compiles independently
of the experiments. It contains no references to the experiments volume.
Experiments uses `xr-hyper` to link back to the thesis through `main.aux`.

Build from this directory:

```bash
latexmk -pdf -interaction=nonstopmode -halt-on-error main.tex
latexmk -pdf -interaction=nonstopmode -halt-on-error esperimenti.tex
```

Keep the PDFs together for links from experiments to the thesis to work. Rebuild
experiments after changes to the thesis labels or numbering. The usual command
`scripts/build_docs.sh thesis` from the repository root still compiles the thesis.
These commands reuse existing figures and measurements; they do not rerun the
analysis pipeline.

The experiments PDF preserves the older scaling extension and can compile while
its historical fixed-population spectrum outputs are unavailable. In that case it explicitly marks the affected passages
in Chapters 4 and 7 as pending and omits the missing spectrum figure and two
tables. The complete numerical prose is preserved in conditional source blocks;
it is included automatically once all required macros and files exist.

Four pooled-spectrum macros are recovered from the existing `ch3_revision.json`
using `revisions/thesis-experiments-split-2026-09-17/recover_pooled_values.py`.
The supplemental file records its source hash and does not override newer macros
from the standard reporting pipeline. This recovery does not regenerate the
fixed-population estimates or claim fresh analysis results.

The current Chapter 3 is `sections/04-fixed-transport.tex`. It uses the new
`ch3_transport_*` numerical report, figures and tables. Transferred original passages
are red in experiments; their definitions and estimates remain historical. The
new chapter uses normal typography. PCA and anisotropy remain in experiments, with
a placeholder in the thesis.

For immediate redraw from saved SSD data, from the repository root:

```bash
uv run python scripts/reporting/ch3_global_transport/run_ch3_fixed.py \
  --data /Volumes/SSD_DISANTE/derived-audit/chapter3-fixed-20260917 --redraw
```

See [the Chapter 3 reproduction guide](../docs/guide/chapter3-fixed-transport.md)
for full measurements, file provenance and the distinction between bootstrap
intervals and across-flight scatter. Rebuilding the PDF alone never recalculates data.
