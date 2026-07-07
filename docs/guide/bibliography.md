# Bibliography — verification & local archive

Every work cited in the thesis is tracked here: whether its full text is archived
locally, where it was downloaded from, and — when it is not archived — why not.
The bibliographic metadata of **every** entry has been cross-checked against an
authoritative source (Crossref, arXiv, or the issuing body itself), never taken
from memory or from a secondary citation.

!!! note "The local archive is not in the repository"
    The full texts live in **`thesis/references/`**, one file per BibTeX key
    (`<bibkey>.pdf`, plus `.html` for web-only resources). That folder is
    **gitignored and never pushed**: the PDFs are copyrighted material archived
    for personal study, so the repository carries only this inventory. Anyone
    rebuilding the archive can do so from the *Downloaded from* column below.

*Last verified: 2026-07-07.*

## Status of the cited works

| BibTeX key | Reference | Metadata verified against | Local file | Downloaded from |
|---|---|---|---|---|
| `metzler2000` | Metzler & Klafter, *The random walk's guide to anomalous diffusion*, Phys. Rep. **339**(1), 1–77 (2000) | Crossref, DOI [`10.1016/S0370-1573(00)00070-3`](https://doi.org/10.1016/S0370-1573(00)00070-3) — title, authors, journal, volume, pages, year all match | **not archived** — see below | — |
| `zaburdaev2015` | Zaburdaev, Denisov & Klafter, *Lévy walks*, Rev. Mod. Phys. **87**(2), 483–530 (2015) | arXiv abstract page, whose `journal-ref` field carries the published coordinates (Rev. Mod. Phys. 87, 483, 2015) | `zaburdaev2015_arxiv.pdf` (50 pp — the **arXiv preprint**, the published APS version is paywalled) | [arxiv.org/abs/1410.5100](https://arxiv.org/abs/1410.5100) |
| `vilpellet2026` | Vilpellet, Darmon & Benzaquen, *From Random Walks to Thermal Rides: Universal Anomalous Transport in Soaring Flights*, arXiv:2601.01293 (2026) — the reference study | arXiv abstract page — title, all three authors, category (`cond-mat.stat-mech`), submission date (3 Jan 2026) all match | `vilpellet2026.pdf` (11 pp, v1) | [arxiv.org/abs/2601.01293](https://arxiv.org/abs/2601.01293) |
| `reddy2016` | Reddy, Celani, Sejnowski & Vergassola, *Learning to soar in turbulent environments*, PNAS **113**(33), E4877–E4884 (2016) | Crossref (title/authors/journal/volume/issue/year) **and** Europe PMC (`pageInfo: E4877-84`, PMC4995969) — the E-page range is absent from Crossref, so it was confirmed on PMC | `reddy2016.pdf` (8 pp — PMC free full text, PNAS papers become free 6 months after publication) | [europepmc.org/articles/PMC4995969](https://europepmc.org/articles/PMC4995969) |
| `fai_igc_spec` | FAI / International Gliding Commission, *Technical Specification for IGC-approved GNSS Flight Recorders*, Second Edition with Amendment 8, effective 1 Feb 2023 | The document's own title page (downloaded and inspected: 71 pp; contains the B-record definition and the "V ⇒ GNSS altitude `00000`" rule the thesis relies on) | `fai_igc_spec.pdf` (71 pp) | [fai.org — full spec, with AL8](https://www.fai.org/sites/default/files/igc_fr_specification_with_al8_2023-2-1_0.pdf) |
| `esa_navipedia_ellipsoidal_cartesian` | ESA Navipedia, *Ellipsoidal and Cartesian Coordinates Conversion* (web page — the geodetic-to-ECEF transform of the thesis) | The page itself (no DOI; a maintained ESA resource, cited as a web reference) | `esa_navipedia_ellipsoidal_cartesian.html` (snapshot, 2026-07-07) | [gssc.esa.int/navipedia](https://gssc.esa.int/navipedia/index.php/Ellipsoidal_and_Cartesian_Coordinates_Conversion) |

**Not archived, and why.** `metzler2000` is published by Elsevier behind a
subscription and has **no arXiv version** (checked against the arXiv API by exact
title, 2026-07-07), so there is no legal open copy to archive. Retrieve it through
university access ([ScienceDirect](https://doi.org/10.1016/S0370-1573(00)00070-3))
and drop it into `thesis/references/metzler2000.pdf`; then update this table.

## A correction this audit produced

The `fai_igc_spec` entry originally pointed at
`igc_fr_specification_2021_al7_2022-1-31.pdf` on fai.org. Downloaded and
inspected, that file turned out to be **only the two-page Amendment List 7**
(the 2022 list of edits), *not* the specification — while the thesis cites the
entry precisely for what the specification defines (the fixed character
positions of the `B` record, the `A`/`V` validity flag, the two altitude
channels). The entry now points at the **full Second Edition with Amendment 8**
(71 pages, effective 1 February 2023), which was downloaded, and whose title
page and B-record sections were checked against every claim the thesis
attributes to it. The old two-page file is kept in the local archive as
`fai_igc_spec_AL7_amendment_only.pdf`, as a record of the discrepancy.

## Verification protocol

A citation enters `thesis/references.bib` only after all of the following, and
this page records the evidence:

1. **Metadata from an authoritative registry, never from memory.** Crossref
   (`api.crossref.org/works/<DOI>`) for anything with a DOI; the arXiv abstract
   page for e-prints; the issuing body's own site for standards. Title, full
   author list, journal, volume, pages and year must all match the entry.
2. **The artifact is obtained and opened.** The PDF (or page snapshot) is
   downloaded into `thesis/references/` under the BibTeX key, and its content
   checked against what the thesis actually attributes to it — the FAI case
   above is exactly the failure mode this step catches.
3. **Only legal copies.** Where the published version is paywalled, the archive
   holds the author's own open version (arXiv, PubMed Central) and the table
   says so explicitly; a paper with no legal open copy is simply marked *not
   archived* with the reason. Never a random third-party copy.
4. **Peer-reviewed journals, established review series, recognized standards
   bodies, or major textbooks only.** Web resources are acceptable only where
   they are the natural reference for the fact cited (e.g. Navipedia for a
   coordinate transform) and are archived as dated snapshots.
5. **Provenance is recorded here** — the exact URL each file came from, and the
   date of the last verification pass.

The same protocol governs any future enrichment of the bibliography: candidate
references are located, verified per points 1–4, and only then cited in the
text — a reference that cannot be verified is not used, however plausible it
looks.
