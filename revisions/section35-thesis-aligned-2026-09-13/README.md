# Slides for thesis Sections 3.5.1--3.5.3

The dedicated source `presentations/chapter3-section35.tex` follows the manuscript:

- 3.5.1: archive east/north balance, Fig. 3.20, and the site--day bootstrap.
- 3.5.2: centred regional PCA, scalar normalisation, terrain orientation and
  coastal wind at flight altitude, Figs. 3.21--3.23.
- 3.5.3: regional position/velocity/acceleration ratios, equipment comparisons,
  their interpretation and limitations, Figs. 3.24--3.26.

All seven original figures appear in full. Enlarged panels supplement them;
visible comments explain the findings, while speaker notes retain discussion
questions and methodological detail. Both PDFs have 40 pages: 37 numbered slides
including the title, and three subsection dividers. The visual style is shared
with the chapter decks.

This replaces the previous automatic extract, which incorrectly included the
regional second/third-difference material from thesis Sections 3.5.4--3.5.5 and
omitted Fig. 3.20 and the acceleration panel. The new validation explicitly checks
the three subsection numbers, their order, all seven complete figures and their
hashes against the reviewed manuscript. No thesis or numerical input changed.

Build: `python3 presentations/build.py 3.5 --notes`.
Validation: `python3 presentations/validate.py`.
