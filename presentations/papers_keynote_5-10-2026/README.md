# Paper reviews: Neggers et al. (2003), Arakawa & Schubert (1974)

| File | Content |
|---|---|
| `neggers2003.pdf`, `-notes.pdf` | 5-slide deck, and the same deck with speaker notes |
| `arakawa-schubert1974.pdf`, `-notes.pdf` | 7-slide deck, and the same deck with speaker notes |
| `neggers2003-vademecum.pdf` | 2-page reading guide |
| `arakawa-schubert1974-vademecum.pdf` | 4-page reading guide |

Sources are the Zotero copies of the two papers (`~/Zotero/storage/WIZ6AR53`, `~/Zotero/storage/NRBB6NCN`).
The decks reuse `../theme.tex` and the slide macros of `offsite2026`; `paper-review.tex` holds the shared layout.
The Arakawa & Schubert deck follows seven slides: goal and roadmap, environmental budgets, one cloud type, ensemble profiles, cloud work function, quasi-equilibrium closure, and the observational test. Single-plume structure and ensemble weighting occupy separate slides, as do the work function and its balance. The observational test concludes the deck. The original final slide on the horizontal distribution of thermals has been removed.
The Neggers deck has four slides on the paper and a final thermal comparison. Its Fig. 7b comparison uses paraglider and hang-glider sink rates (land cases only) and compares climbable cloud sizes with expected thermal diameters.
Each slide opens with a plain-language summary and ends with a takeaway bar. Symbol legends define the main notation, with longer derivations and technical qualifications in the speaker notes. The decks preserve the paper's definitions, including $s=c_pT+gz$ and water-vapour mixing ratio $q$.
Original figures accompany the equations. Editable diagrams explain physical feedbacks and measurement steps. The Arakawa & Schubert deck shows the paper's Fig. 6 beside the single-cloud model, with the cloud tops and the pull of entrainment drawn over it, writes the work function (Eq. 133) with its buoyancy spelled out in temperature, vapour and liquid water next to a schematic buoyancy profile, and shows Fig. 13 at a larger size for the closing test.
The reading guides remain separate, longer companion material from the earlier review.

Rebuild:

```
python3 crop_figures.py   # figures cropped from the PDFs into assets/
python3 build.py          # decks, notes and guides; checks page counts 5, 7, 2, 4
```
