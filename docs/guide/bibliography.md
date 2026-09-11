# Bibliography: evidence and local inventory

Initial audit: **10 September 2026**; additional original-source checks: **11 September 2026**. The machine-readable record is
`revisions/bibliography-audit-2026-09-10.json`; it preserves the registry responses,
primary URLs, the fields actually checked and local-file hashes. A metadata match
establishes the identity of a work. Whether that work supports a statement is a
separate check, recorded in the chapter audit reports under `revisions/`.

## Corrections from this review

- The DOI record for Dempster, Laird and Rubin (1977) identifies the article on
  **pages 1–22**. The former 1–38 range included discussion without saying so.
- Both 2026 arXiv papers have arXiv-issued DOIs. Their entries now identify the
  inspected versions: Vilpellet v1, Hernández-Aguayo v2.
- García Crespillo et al. (2024) has DOI **10.33012/2024.19499**, pages 301–306,
  confirmed by the [Institute of Navigation](https://www.ion.org/publications/abstract.cfm?articleID=19499).
- The Navipedia coordinate-conversion page credits three named authors and the
  year 2011. The bibliography now records them. Welch's name is expanded to Peter D.
- The IGC-approved recorder specification and the CIVL document use different
  altitude conventions. Their scope is stated; neither proves a common datum
  across every historical logger. The CIVL file retains draft annotations.
- The 2012 EN document is a final draft with editing marks. Its Table 1 was checked;
  the published 2013 text and subsequent amendments were not compared.
- The local MS5611 document puts the quoted specification table on **page 1**;
  its ±2.5 mbar condition requires an autozero. A specification for one sensor is
  not an accuracy estimate for the recorder population.

The previous inventory incorrectly marked several existing PDFs as absent and
made unsupported claims that no lawful accessible copy existed. Those statements
have been removed. Existing copies are inventoried below without inventing their
acquisition history. A local file is not proof that its original download URL or
licence was recorded.

## Scope of source checking

The chapter reports document the checks of stochastic scaling, moment spectra,
Gaussian/non-Gaussian diagnostics, HMM assumptions, filtering and coordinate
transforms. Formulae were also derived or checked against implementation where
appropriate. Software-dependent statements identify **hmmlearn 0.3.3** and
**SciPy 1.18.0**. The hmmlearn stopping flag and covariance update were checked
against installed source, not inferred from their parameter names.

The 2021 [corrigendum to McClintock et al.](https://doi.org/10.1111/ele.13709)
concerns example observation matrices for capture–recapture/coexistence models;
those examples are not used in this Gaussian flight HMM. The audit does not
reinterpret a publisher's later website-migration date as the original publication
year of classic papers.

The original Baum et al. (1970) publisher endpoint remained inaccessible. A reproduction
of the original article was inspected: its header confirms the identity, and pp. 164–168
support the historical HMM likelihood and iterative estimation attribution. The modern
multivariate recursions were also checked against the local Rabiner tutorial (Sections
II–IV). This is recorded separately from a successful publisher retrieval. The original
Kapos et al. chapter was subsequently recovered as author-uploaded manuscript text:
its title page and Methods/Results were inspected, including the slope and relief
criteria absent from an altitude-only classification. The downloadable PDF remained
unavailable. Mardia's publisher metadata and first original pages were checked; the
full original kurtosis section was not retrieved, and that limitation is retained in
the record rather than described as a full-text verification.

The Hampel identifier is attributed specifically to Davies and Gather (1993), Example
2.2, rather than treating Hampel's influence-function paper as the source of the entire
GPS-cleaning procedure. The physical gate and its numerical thresholds are choices of
this analysis.


The final manuscript also cites three methods whose originals were inspected:

- Efron (1979), pp. 1–3, introduces resampling from the empirical distribution.
  Whole-flight or site/day resampling still requires a defensible sampling-unit
  assumption; the citation does not calibrate the present bands.
- Fritsch and Butland (1984), p. 301, Eq. (5), gives the local monotone cubic
  slope construction used by PCHIP. The weighted harmonic slope was checked
  against the installed SciPy source; its endpoint scheme is documented separately.
- Taylor, p. 207, Eqs. (15)–(18), relates stationary velocity correlation to
  displacement variance. The thesis sums the coordinate relations and exchanges
  the integration order. The publisher and registry identify **1922**; the often-used
  1921 filename and the 1920 reading date in the scan do not replace that issue date.

## Inventory

“Registry” means publisher-deposited Crossref metadata were retrieved. “Primary”
means a publisher, author or issuing-body record/document was inspected; exact
field limitations are in the JSON record. “Local” denotes an inspected local
manufacturer document. Files below are under `thesis/references/`, an ignored
local directory. A dash means no matching copy was present at the audit date.

| Key | Source | Check | Used in current manuscript | Local file |
|---|---|---|---|---|
| `metzler2000` | [record](https://doi.org/10.1016/S0370-1573(00)00070-3) | Registry | yes | `metzler2000.pdf` |
| `tejedor2010` | [record](https://arxiv.org/abs/0910.1194) | Primary | yes | `tejedor2010_arxiv.pdf` |
| `schulz2013` | [record](https://doi.org/10.1088/1751-8113/46/47/475001) | Registry | yes | `schulz2013_arxiv.pdf` |
| `zaburdaev2015` | [record](https://arxiv.org/abs/1410.5100) | Primary | yes | `zaburdaev2015_arxiv.pdf` |
| `viswanathan1999` | [record](https://doi.org/10.1038/44831) | Registry | no | `—` |
| `bouchaud1990` | [record](https://www.sciencedirect.com/science/article/pii/037015739090099N) | Primary | no | `—` |
| `solomon1993` | [record](https://doi.org/10.1103/PhysRevLett.71.3975) | Registry | no | `—` |
| `vilpellet2026` | [record](https://arxiv.org/abs/2601.01293) | Primary | yes | `vilpellet2026.pdf` |
| `reddy2016` | [record](https://doi.org/10.1073/pnas.1606075113) | Registry | yes | `reddy2016.pdf` |
| `fai_igc_spec` | [record](https://www.fai.org/sites/default/files/igc_fr_specification_with_al8_2023-2-1_0.pdf) | Primary | yes | `fai_igc_spec.pdf` |
| `esa_navipedia_ellipsoidal_cartesian` | [record](https://gssc.esa.int/navipedia/index.php/Ellipsoidal_and_Cartesian_Coordinates_Conversion) | Primary | yes | `esa_navipedia_ellipsoidal_cartesian.html` |
| `nga_wgs84` | [record](https://earth-info.nga.mil/php/download.php?file=coord-wgs84) | Primary | yes | `wgs84_nga_std.pdf` |
| `gps_sps_ps_2020` | [record](https://archive.gps.gov/technical/ps/2020-SPS-performance-standard.pdf) | Primary document | no | `—` |
| `garciacrespillo2024` | [record](https://www.ion.org/publications/abstract.cfm?articleID=19499) | Primary | yes | `—` |
| `fpren926_2_2012` | [record](https://xcmag.com/wp-content/uploads/2012/08/DraftEN926-2.pdf) | Primary document | yes | `—` |
| `sklearn_haversine` | [record](https://scikit-learn.org/stable/modules/generated/sklearn.metrics.pairwise.haversine_distances.html) | Primary document | yes | `—` |
| `savitzky1964` | [record](https://doi.org/10.1021/ac60214a047) | Registry | yes | `savitzky1964.pdf` |
| `welch1967` | [record](https://research.ibm.com/publications/the-use-of-fast-fourier-transform-for-the-estimation-of-power-spectra-a-method-based-on-time-averaging-over-short-modified-periodograms) | Primary | yes | `welch1967.pdf` |
| `hampel1974` | [record](https://www.tandfonline.com/doi/abs/10.1080/01621459.1974.10482962) | Primary | no | `hampel1974.pdf` |
| `rousseeuw1993` | [record](https://doi.org/10.1080/01621459.1993.10476408) | Registry | yes | `rousseeuw1993.pdf` |
| `clauset2009` | [record](https://doi.org/10.1137/070710111) | Registry | no | `clauset2009.pdf` |
| `mardia1970` | [record](https://doi.org/10.1093/biomet/57.3.519) | Registry | yes | `—` |
| `he2008` | [record](https://doi.org/10.1103/PhysRevLett.101.058101) | Registry | no | `he2008.pdf` |
| `rabiner1989` | [record](https://web.ece.ucsb.edu/Faculty/Rabiner/ece259/publications.html) | Primary | yes | `A_tutorial_on_hidden_Markov_models_and_selected_applications_in_speech_recognition.pdf` |
| `baum1970` | [record](https://doi.org/10.1214/aoms/1177697196) | Original reproduction | yes | `—` |
| `dempster1977` | [record](https://academic.oup.com/jrsssb/article/39/1/1/7027539) | Primary | yes | `—` |
| `viterbi1967` | [record](https://cris.technion.ac.il/en/publications/error-bounds-for-convolutional-codes-and-an-asymptotically-optimu/) | Primary | yes | `—` |
| `langrock2012` | [record](https://esajournals.onlinelibrary.wiley.com/doi/10.1890/11-2241.1) | Primary | yes | `—` |
| `mcclintock2020` | [record](https://onlinelibrary.wiley.com/doi/abs/10.1111/ele.13610) | Primary | yes | `—` |
| `redner2001` | [record](https://www.cambridge.org/core/books/guide-to-firstpassage-processes/errata/80029DC0ABF4B98C29A79D996167D6EC) | Primary | no | `—` |
| `mantegna1995` | [record](https://www.nature.com/articles/376046a0) | Primary | no | `mantegna1995.pdf` |
| `daviesgather1993` | [record](https://www.tandfonline.com/doi/abs/10.1080/01621459.1993.10476339) | Primary | yes | `—` |
| `fai_sc7_2024` | [record](https://fai.org/sites/default/files/civl/documents/sporting_code_s7_-_common_2024_v3.pdf) | Primary | yes | `—` |
| `hernandezaguayo2026` | [record](https://arxiv.org/abs/2608.00241) | Primary | yes | `—` |
| `kapos2000` | [author manuscript](https://www.researchgate.net/publication/306151877_Developing_a_map_of_the_world%27s_mountain_forests_Forests_in_sustainable_mountain_development_a_state_of_knowledge_report_for_2000) | Author manuscript | yes | `—` |
| `ms5611_datasheet` | local / unresolved | Local document | no | `ms5611_datasheet.pdf` |
| `mandelbrot1968` | [record](https://epubs.siam.org/doi/abs/10.1137/1010093) | Primary | yes | `—` |
| `rebenshtok2014` | [record](https://arxiv.org/abs/1408.4479) | Primary | yes | `—` |
| `fai_civl_s7h_2024` | [record](https://fai.org/sites/default/files/civl/documents/sporting_code_s7_h_-_civl_flight_recorder_specification_2024.pdf) | Primary | yes | `—` |
| `hmmlearn033` | [record](https://hmmlearn.readthedocs.io/en/0.3.3/api.html) | Primary | yes | `—` |
| `scipy_savgol_filter` | [record](https://docs.scipy.org/doc/scipy-1.18.0/reference/generated/scipy.signal.savgol_filter.html) | Primary | no | `—` |
| `efron1979` | [record](https://doi.org/10.1214/aos/1176344552) | Registry + original | yes | `efron1979.pdf` |
| `fritsch1984` | [record](https://doi.org/10.1137/0905021) | Registry + original | yes | `fritsch1984.pdf` |
| `taylor1922` | [record](https://doi.org/10.1112/plms/s2-20.1.196) | Registry + original | yes | `taylor1922.pdf` |

The old two-page `fai_igc_spec_AL7_amendment_only.pdf` is retained separately as an
amendment-only historical file. It is not the full specification cited in the thesis.

For later changes, verify the specific version, record what was actually opened,
and distinguish a formula's assumptions from its applicability to these data.
Unreachable originals remain identified as such; metadata or a secondary citation
must not be described as a full-text check.
