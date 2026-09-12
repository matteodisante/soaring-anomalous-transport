# Full-chapter supervisor decks: coverage and discussion

Preparation only. Build final decks after numerical completion, quantitative review
and the Chapter 3 restructuring. These replace the old timed 18-slide presentations.
Do not impose a talk duration or demote new evidence to optional backup slides.
Preserve the existing Pisa/Palatino visual style, discipline/equipment colours and
slide-plus-notes deliverables. Titles should state a question or supported result.

The complete drafts are now assembled as chapter2-supervisor-draft.tex (59 frames)
and chapter3-supervisor-draft.tex (73 frames), using assemble_supervisor_drafts.py.
They replace obsolete gap/subset statements and move duration controls before model
conclusions. They are not delivered decks: Chapter 3 plot placeholders and old
macros remain in the explicitly labelled layout preview until the run completes.
The existing presentations/ PDFs have not been overwritten.

preview_supervisor_crops.py prepares exact vector crops, including both position
and velocity for each equipment region. The PSD crop has been visually checked:
its own axes, legend and Nyquist label remain intact and the neighbouring ylabel
fragment is excluded. render_chapter3_panels.py prepares 24 readable redraws from
completed full-report arrays, including paired contrasts and fit-range sensitivity.
It has passed syntax/help checks but has not yet run on completed new reports.
Its marginal panels show raw density, power-rescaled density and median-normalized
quantile ranks, one coordinate at a time, with any zero mass reported explicitly.

Three synthetic reach-gate pairs now use render_supervisor_gate.py: it calls the
original example function with an in-memory save callback, then changes layout and
font sizes, checking plotted arrays and limits remain identical. Attempted vector
column crops clipped neighbouring labels, so they were replaced by this re-layout.
The full vector crop helper now contains 18 valid panel previews, without gate crops.

Three launch maps use render_supervisor_maps.py and their metadata from the completed
preliminary stage recorded in the recovery manifest. A direct read of the general
derived-audit directory was refused because it contained historical metadata; the
helper now derives the exact run-specific directory from the completed producer.
The successful redraw covers 156406 para/6094 hang flights, preserves bins, colours,
positions and geographic extents, and identifies its inputs and plot data by hashes.
Regional annotations are reflowed for readability. These are still draft assets.

## Chapter 2

| Topic | Evidence to show | Discussion prompted by the evidence |
|---|---|---|
| Scope and acquisition | FFVL CFD source, seasons, raw counts, acquisition checks | Which selection into recorded/declared flights can this archive assess? |
| IGC records | One decoded fix, timestamp/validity flag, altitude fields | What does a logger declaration establish, and what remains a sensor inference? |
| Metadata and equipment | Catalog fields, scoring categories, EN groups and unknowns | What independent pilot information would validate the equipment proxy? |
| Coverage | Geography, seasons and group composition | Which regions and periods have enough comparable observations? |
| Pipeline contract | Fix decisions, flight gates, segment gates, outputs and census | Which exclusions define a study population rather than identify impossible physics? |
| Altitude channels | Paired raw PSDs, availability/variation and witness role | Can overlap of spectral bands distinguish sensor noise, quantization and common flight motion? |
| PSD selection sensitivity | Same-flight old-rule/current-rule comparison, 2008 flights | How much sensitivity remains to chosen valid-block length? The observed change is not Savitzky–Golay filtering. |
| Structural defects | Duplicate/reversed timestamps, frozen runs, explicit boundaries | What evidence is sufficient to call a frozen-position candidate? |
| Horizontal geometry | Hampel identifier, reach/rejoin gate, real examples | Which operational thresholds merit blinded manual review? A flag alone never deletes. |
| Frozen-lock witness | Complete local pressure support, fallback conditions | How should abstention and uncertain witnesses enter a manual reference set? |
| Vertical decisions | Window medians, 10 m/s threshold, invalidation | Does the decision protect against spikes and sustained offsets equally? |
| Unresolved altitude steps | Real level-shift candidates and current lack of automatic correction | Which phase observables are most sensitive, and what independent evidence can resolve offsets? |
| Ground trimming | Leading/trailing ground phases and interior excisions | Could slow soaring resemble a ground phase? Compare support and censoring. |
| Flight gates | Duration/path/altitude range and sequential first-failure census | Which conclusions are conditional on excluding short/low-relief flights? |
| Geographic coordinates | Geodetic to ECEF to local ENU, origin and units | On what spatial extent is a fixed local frame adequate? |
| Uniform sampling | Native cadence, common grid, interpolation flags | How does cadence constrain derivatives and later common-grid eligibility? |
| Unified gap rule | Exact g_max rule; threshold equality, long horizontal/vertical holes | Which threshold sensitivity preserves a common comparison population? |
| Vertical-gap witness | Flight 20171597; removed 6806–7449 s interval | What information is intentionally lost when missing altitude splits the whole trajectory? |
| Segment accounting | Preserved clock/origin, unsupported intervals, censoring | Are long-lag and phase results sensitive to where observation support ends? |
| Smoothing | Local polynomial, position and derivative kernels, edge masks | Which scales are measurement-limited or attenuated? |
| Spectral response | Raw spectra, Savitzky–Golay response, cadence-specific window | How can a residual diagnostic distinguish noise suppression from removal of manoeuvres? |
| Numerical and empirical checks | Full structural verifier, reproducibility sample, provenance | Which checks establish implementation consistency and which require external labels? |
| Retained archive | Current counts, segment multiplicity, seasons and geography | How does the cleaned population differ from attempted flights? |
| Preliminary characterization | Ensemble paths and transport-ready coordinates | Which patterns motivate the next chapter without already identifying a process? |
| Supervisor priorities | Threshold sensitivity, reference labels, altitude offsets, selection | Agree concrete next comparisons and the evidence needed for each. |

Use more than one slide for dense topics: in particular horizontal cleaning, vertical
rules, trimming, ENU, the gap rule and smoothing. Preserve complete method coverage
without putting a whole thesis page on a single slide. Explain the exact cadence-
dependent gap cap; never retain the old unlimited altitude reconstruction statement.

## Chapter 3

| Argument block | Required content | Discussion target |
|---|---|---|
| Scope and observables | Full eligible archive, segments, increments and support | What motion should a stochastic model describe? |
| Growth estimators | Ensemble MSD, TAMSD, equal-flight versus pooled origins | Do weighting and changing support explain apparent estimator differences? |
| Effective exponents | Full curves, fit windows, local slopes | Which scale interval supports a finite-range description? |
| Constant velocity | V1/V2, cancellation identity and conditional H interpretation | What remains after removing a constant velocity: route geometry, turns, changing wind? |
| Open/closed routes | Declared tasks and measured observed-path closure | Is a task contrast still present at matched duration and environment? |
| Quantile prediction | Inverse weighted ECDF and common-H implication | Which shape changes can moments conceal? |
| Population control | All eligible baseline plus the four nested controls | Separate membership, flight weighting and origin selection; never present the fixed cohort as the entire archive. |
| Relative spread | Radial p90/p25 across lag, not only fitted slope | What explains early widening and later narrowing, if confirmed by the fresh run? |
| Vector scaling | E/N/radial quantiles and paired bootstrap contrasts | Can one scalar H describe components and radius on the same observations? |
| Marginal limitations | Exact same-E/N/R, different-joint example | Which additional information is recovered by retaining signs and joint structure? |
| Distribution collapse | Absolute laws, fitted rescaling and median rescaling | Is failure primarily scale mismatch or changing shape? |
| Joint distributions | Both disciplines, all six lags, fixed geographic axes and scalar scale | Which joint changes survive after normalization? Keep the finite bin resolution explicit. |
| Scope of inference | Overflow mass, descriptive TV, paired origins, flight bootstrap assumptions | What calibrated process comparison would require multi-time information? |
| Raw directional balance | Launch-time E²/N², mean-plus-covariance identity | Does group balance reflect drift, within-flight variability or a mixture of route directions? |
| PCA | Centred pooled-origin covariance, eigenvalue ratio and axis | Does axis alignment persist across lags, and when is the axis poorly determined? |
| Estimator comparison | Lag versus time since launch; origin versus flight weights | Which differences are methodological before being interpreted physically? |
| Mountains/coast | Alps, Pyrenees, Channel Coast and support | Is directional structure consistent with terrain without being identified as its effect? |
| Equipment within regions | Fresh A/B and C/D/CCC curves, changing counts and bands | Preserve the user's interpretation as a hypothesis and show the Pyrenean reversal. |
| Low-relief boxes | Channel Coast, Poitou-Charente, Champagne-Lorraine | Does the coastal pattern generalize? Do not call the boxes verified flat terrain. |
| Critique and proposed tests | Ratio1 counterexample, skill proxy, wind/terrain interaction, selection | Which matched site/day/task/duration comparison is feasible first? |
| Physical wind relation | Ground = air-relative + wind; spatial wind gradients in acceleration | What outcome would actually measure resistance to wind? |
| Model comparisons | Moment spectrum, Levy-walk benchmark, finite-range caveats | Which explicit nulls should be simulated with the same observation protocol? |
| Heterogeneity | Centred kurtosis/Mardia, Gaussian-mixture counterexample | Can pooled non-Gaussianity be separated from within-flight non-Gaussianity? |
| Temporal memory | Signed VACF, several resolutions, finite persistence | Which phase-dependent correlations would distinguish competing mechanisms? |
| Duration and equipment | Cohort curves, common fit range, composition standardization | Which contrast remains after fixing equipment proportions? |
| Next chapter | Empirical constraints, limits and phase-conditioned measurements | Agree priority questions rather than treating one exponent as process identification. |

Retain all new component, collapse and joint-law evidence in the main deck. The
squared-variable appendix can be a clearly linked supplement: monotone transforms
reuse probability mass and double quantile slopes; they are not independent tests.

## Delivery checks

- Replace timed notes with speaker/discussion notes; remove 20-minute/18-slide claims.
- Refresh every data/figure snapshot only from completed, verified products and record
  the numerical run ID, source hashes and reviewed manuscript identity.
- Import macros or recorded values for counts/slopes; inspect hardcoded examples and
  dynamic plot limits, especially the old fixed quantile-slope y-range.
- Keep compact slide data derived explicitly from full reports if the full archive
  provenance would make duplicate presentation JSON unnecessarily large.
- Do not infer a new statistical result while redrawing a projection figure.
- Inspect PDF pages for clipping, axis labels, legend counts, line colour agreement,
  readable joint panels, notes, references and viewer links. Rebuild ordinary and
  notes PDFs. Update source-manifest, figure-manifest, README and validation record.
- Delivery remains pending; this coverage map is not a substitute for the decks.


## Draft material prepared during the numerical run

chapter2-additional-frames.tex contains21additional frames; chapter3-additional-frames.tex
contains20. They are material to merge/reorder with the existing decks, not final
presentations or an instruction to concatenate everything. Remove obsolete/repeated
frames and old timed notes when assembling the full decks after the manuscript review.

Draft layout builds succeeded with zero undefined-command/overfull warnings after
small height corrections. Chapter2 used current completed-stage figures; Chapter3
used explicit figure placeholders, so its build does not validate the final plots.
The first visual pass found the full four-panel altitude_noise figure too small
for projection: replace that main slide with a PSD panel/redraw and show traces/
availability separately. The three-way estimator comparison table needed ragged
columns, which are now prepared. Dense PCA, component, marginal-collapse and joint
figures will likewise need readable panels/redraws in the final deck. Retain original
PDFs as complete references and identify all derived presentation figures by hashes.
