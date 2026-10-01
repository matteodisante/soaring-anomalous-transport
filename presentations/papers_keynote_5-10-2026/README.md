# Paper reviews: Neggers et al. (2003), Arakawa & Schubert (1974)

| File | Content |
|---|---|
| `neggers2003.pdf`, `-notes.pdf` | 4-slide deck, and the same deck with speaker notes |
| `arakawa-schubert1974.pdf`, `-notes.pdf` | 4-slide deck, and the same deck with speaker notes |
| `neggers2003-vademecum.pdf` | 2-page reading guide |
| `arakawa-schubert1974-vademecum.pdf` | 4-page reading guide |

Sources are the Zotero copies of the two papers (`~/Zotero/storage/WIZ6AR53`, `~/Zotero/storage/NRBB6NCN`).
The decks reuse `../theme.tex` and the slide macros of `offsite2026`; `paper-review.tex` holds the shared layout.
Each deck has three slides on the paper's methods and results, followed by one slide on what is missing for a 2D thermal field: size, positions and inter-thermal spacing.
The last slide also offers a conditional use of the results, explicitly labelled as our inference in gold. No cloud-size or mass-flux spectrum is presented as a measured thermal distribution.
The speaker notes explain the assumptions behind these possible links. The reading guides remain the longer companion material and carry gold boxes and `[ours]` for our proposals and readings.

Rebuild:

```
python3 crop_figures.py   # figures cropped from the PDFs into assets/
python3 build.py          # decks, notes and guides; checks page counts 4, 4, 2, 4
```
