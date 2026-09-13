# Thesis subsection mapping in the chapter decks

Each slide block now starts with an unnumbered divider that displays the exact
thesis section or subsection number and its title. This makes the mapping visible
inside the PDF rather than requiring a separate lookup table.

- Chapter 2: 58 numbered slides and 16 subsection dividers, 74 PDF pages.
- Chapter 3: 119 numbered slides and 27 subsection dividers, 146 PDF pages.

The visible slide numbers continue to identify content slides; divider pages do
not consume those numbers. `presentations/outline.md` uses the same convention.
The presentation README distinguishes numbered slides from physical PDF pages.

The canonical thesis PDF was also rebuilt from the current sources after its
working-tree copy disappeared. Its SHA-256 identity matches the completed
temporal-scaling manuscript review, so no thesis content changed during recovery.

Both normal decks and notes decks were rebuilt. The presentation validator checks
the physical page count, numbered slide count and divider count separately, as
well as the reviewed thesis identity, figure provenance and LaTeX logs.
