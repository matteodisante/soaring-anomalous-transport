# Paper reviews: Neggers et al. (2003), Arakawa & Schubert (1974)

| File | Content |
|---|---|
| `neggers2003.pdf`, `-notes.pdf` | 5-slide deck, and the same deck with speaker notes |
| `arakawa-schubert1974.pdf`, `-notes.pdf` | 10-slide deck, and the same deck with speaker notes |
| `neggers2003-vademecum.pdf` | 2-page reading guide |
| `arakawa-schubert1974-vademecum.pdf` | 4-page reading guide |

Sources are the Zotero copies of the two papers (`~/Zotero/storage/WIZ6AR53`, `~/Zotero/storage/NRBB6NCN`).
The decks reuse `../theme.tex` and the slide macros of `offsite2026`; `paper-review.tex` holds the shared layout.
Blue boxes report what the paper says; gold boxes and `[ours]` mark our proposals and readings, which are not in the papers.

Rebuild:

```
python3 crop_figures.py   # figures cropped from the PDFs into assets/
python3 build.py          # decks, notes and guides; checks page counts 5, 10, 2, 4
```
