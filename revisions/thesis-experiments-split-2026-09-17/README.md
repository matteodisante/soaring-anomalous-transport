# Thesis without forward references; experiments PDF

The `before/` files preserve the working sources before this follow-up, including
uncommitted work already present in the workspace.

Eight explicit occurrences of the name `Esperimenti` were removed from thesis prose:

| Source | Original location | Subject |
| --- | --- | --- |
| main.tex | Abstract | Chapters 3–7 and Appendix 4.A |
| 01-introduction.tex | 1.2.1 | Global observables and transport |
| 01-introduction.tex | 1.4 | Document structure |
| 03-dataset.tex | 2.4 | Operational equipment proxies |
| 03-dataset.tex | 2.7.6 | Reconstruction flags for phase analysis |
| 03-dataset.tex | 2.9, opening | Directional anisotropy |
| 03-dataset.tex | Map caption | Regional principal-axis analysis |
| 03-dataset.tex | 2.10 | Observable definitions and population weights |

Also removed the eight separate forward chapter references in the introduction
(two to Chapter 7, one to Chapter 5 in 1.2.2, one chapter group in the priorities,
two chapter labels in the diagram, and two chapter references after the diagram),
and three generic companion mentions (diagram brace, caption and chapter summary).
The research programme remains; the diagram now distinguishes the dataset in this
volume from subsequent analysis without pointing to the experiments document.

## Experiments compilation

The initial build lacked 32 numerical macros, two tables and the fixed-population
spectrum figure. Four pooled-spectrum macros were reconstructed from the saved
`thesis/generated/ch3_revision.json`, with exactly the generator's formula
`nu = zeta / q`. Reproduce this recovery from the repository root with:

```bash
python3 revisions/thesis-experiments-split-2026-09-17/recover_pooled_values.py
```

The generated supplemental TeX records the JSON SHA256 and uses `providecommand`
so the standard reporter's newer values take precedence. No flight analysis was
rerun. The other 28 macros and three assets require regenerated fixed-population
measurements. `esperimenti.tex` checks that all exist before including the affected
quantitative passages. Until then it renders explicit pending-result explanations
in the scope page and Chapters 4 and 7. Dependent numerical conclusions, including
the model-comparison summary row, are deferred. Original quantitative source text
is retained in conditional blocks; no dummy numbers or fabricated plots are used.

The long moment/quantile identity was split across two lines to remove a margin
overflow, without changing its mathematical content.

## Validation

- `latexmk -pdf -quiet -interaction=nonstopmode -halt-on-error -cd thesis/main.tex`
  succeeds: 57 pages; chapters 1, 2, 2.A, 2.B.
- The corresponding command for `thesis/esperimenti.tex` succeeds: 97 pages;
  chapters 3, 4, 5, 6, 7, 4.A.
- No undefined references/citations, fatal errors or overfull boxes in either log.
- Extracted thesis text contains no `Esperimenti`, `companion` or
  `thesis and experiments`; neither PDF contains unresolved `??` markers.
- Visual inspection: thesis abstract and structure diagram; experiments scope,
  moment identity, pending spectrum discussion and model-comparison opening.
