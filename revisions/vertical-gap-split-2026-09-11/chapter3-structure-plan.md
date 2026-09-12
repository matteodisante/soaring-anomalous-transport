# Chapter 3: separate scaling tests from environmental interpretation

Prepared from the current manuscript after the request to split section 3.3.
The plan below has now been applied to the working manuscript after the completed
Chapter 3 numerical audit. The running continuation retains its separate frozen
source tree. Final reviewed compilation against all completed stages is pending.

## Proposed sequence

- **3.1 Displacement and time scales:** retain the estimators, drift-removing
  variations and route-closure discussion; correct the closure caveat already
  recorded in manuscript-review-pending.md.
- **3.2 Quantiles and self-similarity:** retain the scalar prediction, changing
  versus fixed population, and relative spread. Define weighting and common
  origins once here. The duration/equipment section supplies a separate
  sensitivity analysis, which should be explicitly signposted here rather than
  introduced later as an unexpected qualification.
- **3.3 Vector scaling and dependence:** move the existing subsections
  “Testing east, north and radial scaling”, “Distribution collapse” and
  “Signed joint distributions” into this section. The question is whether one
  scalar rescaling describes the displacement vector across lags. Present
  component/radial quantiles, the failure of marginals to identify dependence,
  and the signed joint-law diagnostic as consecutive parts of that question.
  Refer back to 3.2 for quantile definitions and population controls instead of
  repeating them. Distinguish single-lag distributions from multi-time process
  self-similarity. Finish with the measured conclusion after the full-run audit.
- **3.4 Directional structure, terrain and equipment:** move “East--north
  balance in the retained archive” here, followed by “Regional principal axes”
  and the regional equipment comparisons. Separate mountain/coastal/low-relief
  observations from the final subsection on possible mechanisms and limitations.
  Define raw second-moment balance and centred covariance together, specifying
  the different populations and weighting used by the actual plots. State when
  the abscissa changes from increment lag tau to elapsed time since launch t.
- **3.5 Flight duration and equipment composition:** retain the sensitivity
  analysis of growth exponents. Its opening distinguishes this question from
  regional directional contrasts in 3.4. Place these population controls before
  the model comparison, so the argument does not return to a prerequisite after
  presenting its verdict. This order is implemented in the prepared structural draft.
- **3.6 Comparison with stochastic models:** retain moment spectra, centred
  kurtosis, velocity memory, and the model comparison. Joint-law dependence
  belongs in 3.3; temporal memory belongs here. Explain that distinction once.
- **3.7 Constraints for the phase analysis:** retain the conclusions that
  motivate the next chapter, with no new results introduced here.

## Environmental interpretation to preserve and qualify

The user's hypothesis belongs in 3.4 and in the corresponding supervisor slides:
equipment groups that remain closer to equal east/north moments may differ in
how their routes respond to wind and terrain. Present this as a hypothesis to
discuss, alongside the fresh observations and competing explanations.

Use regional-interpretation-review.md and regional-contrasts-audit.json for the
actual new evidence: the Alpine/coastal contrast is recognisable, whereas the
Pyrenean ordering reverses. Equal diagonal moments do not establish isotropy;
equipment classes do not directly measure pilot skill; coastal terrain is not
absent; and these observational groups do not isolate wind from route choice,
terrain or selection. Do not title the section “Effects of orography”, which
would imply causal identification that these plots do not provide.

## Editing and verification

Move complete text/figure/equation blocks and retain their unique labels. Add a
new section label for the environmental block and inspect every reference to
sec:transport-axisroutes and sec:transport-anisotropy for its intended meaning.
Use figure references rather than retaining the old literal number 3.17.
Rewrite the chapter roadmap and transitions after moving the blocks. Keep PCA
rotation/whitening caveats concise here and cross-reference the fixed-axis
collapse protocol in 3.3. Include an explicit weighting/support comparison so
that regional PCA, launch-time moments and fixed-origin joint laws cannot be
mistaken for identical estimators.

After the numerical run completes, reconcile every quantitative claim, compile
through the manuscript-review workflow, inspect figure placement and references,
then build the full supervisor decks in the same argumentative order. The working
manuscript moves and numerical interpretation are applied; final slide work remains
suspended until the thesis document is complete.
