# Paper reviews: Neggers et al. (2003), Arakawa & Schubert (1974)

| File | Content |
|---|---|
| `neggers2003.pdf`, `-notes.pdf` | 5-slide deck, and the same deck with speaker notes |
| `arakawa-schubert1974.pdf`, `-notes.pdf` | 5-slide deck, and the same deck with speaker notes |
| `neggers2003-vademecum.pdf` | 2-page reading guide |
| `arakawa-schubert1974-vademecum.pdf` | 4-page reading guide |

Sources are the Zotero copies of the two papers (`~/Zotero/storage/WIZ6AR53`, `~/Zotero/storage/NRBB6NCN`).
The decks reuse `../theme.tex` and the slide macros of `offsite2026`; `paper-review.tex` holds the shared layout.
Each deck has four slides on the paper's definitions, principal equations and results, followed by one slide on what is missing for a 2D thermal field: size, positions and inter-thermal spacing.
Each slide opens with a one- or two-sentence summary in plain words and ends with a takeaway bar; a "Symbols" box defines every symbol on the slide, with the paper's definitions (e.g. $s=c_pT+gz$, $q$ the water-vapour mixing ratio).
Original figures accompany the equations. Editable diagrams explain the measurement sequence, physical feedbacks and spatial quantities sought; schematic thermal circles are explicitly labelled as non-data.
The slides and speaker notes contain no proposals for further use. The reading guides remain the separate, longer companion material from the earlier review.

Rebuild:

```
python3 crop_figures.py   # figures cropped from the PDFs into assets/
python3 build.py          # decks, notes and guides; checks page counts 5, 5, 2, 4
```
