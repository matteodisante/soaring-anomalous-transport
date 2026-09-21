# Experimental factorial analysis in Section 3.2.4

The user requested implementation in Chapter 3, within Section 3.2, explicitly
marked experimental. The subsection follows the equipment comparisons. Existing
uncommitted chapter and bibliography edits were retained; their pre-edit sources
are in `before/`. The reader's `thesis/main.pdf` stays unchanged until final PDF
validation and publication.

## Statistical contract

- 44,030 admitted flights from C_10000; 2,243 other cohort flights excluded.
- Four launch-altitude classes x open/closed x EN A/B/C versus EN D/CCC.
- Equal-flight cell MSD, H = half its OLS log-log slope, identical lag grid.
- Equal-cell factorial decomposition with sum-to-zero constraints; saturated
  reconstruction and ordinary least-squares additive projection.
- All main and interaction components retained; no F test, model selection,
  random-effects interpretation, or causal attribution.
- Original 1000 paired site-day draws; six additional resampling runs (three
  schemes, two seeds), four fit windows, unchanged flights/segments.
- One explicitly declared family of 19 contrasts per window/grouping. Single-step
  bootstrap simultaneous intervals use the maximum absolute centred deviation
  standardized by fixed marginal bootstrap SEs. This is a first-order plug-in
  implementation, not nested bootstrap-t or Romano-Wolf stepdown testing.
- Residual maps have no significance stars. Component shares and R2 describe
  variation in estimated H, including sampling noise; they do not estimate a
  population causal variance fraction.

Reproduction commands and source paths are in the Chapter 3 guide. The portable
report allows offline redraw; `replicates.npz` preserves the baseline cell MSDs
and exponent tensors for every window/configuration. `membership.parquet` records
the exact cell or exclusion for each fixed-cohort flight. Source hashes and
resampling definitions are included in the report.

## Check against the user's textbook

Inspected the supplied PDF of Donna L. Mohr, William J. Wilson and Rudolf J.
Freund, *Statistical Methods*, fourth edition, Academic Press, 2022. Title page,
copyright year and ISBN 978-0-12-823043-5 match the provided book identity.
DOI supplied by the user: https://doi.org/10.1016/C2019-0-02521-6 .
The DOI landing page was unavailable through the web reader; full-text checks
below refer to the supplied PDF, not an inferred publisher-page inspection.

Chapter 9 passages checked against the code and manuscript:

| Passage (printed pages) | Application here |
|---|---|
| 9.2, pp. 447-450 | Main effects versus interactions; observational factorial structure is distinct from randomized treatment assignment. |
| 9.3.1, pp. 450-451 | Fixed-effects model, sum-to-zero restrictions and interpretation of marginal effects in the presence of interactions. |
| 9.3.3-9.3.5, pp. 452-455 | Deviation-based partition of sums of squares; applied here to the equally weighted cell-exponent table. |
| 9.3.7, pp. 459-460 | Unbalanced flight counts do not justify the balanced-design ANOVA formulas on raw observations. The equal-cell projection is an explicitly different descriptive estimand. |
| 9.4, pp. 460-468 | Contrasts with zero-sum coefficients, within-factor comparisons in the presence of interactions, and multiplicity. The selected endpoint comparisons are explicitly exploratory, not retrospectively called preplanned. |
| 9.6, p. 472 | No within-cell replication at the exponent-table level gives no classical pure-error estimate. Bootstrap draws are not experimental replicates; the interaction residual is not pooled into error. |
| 9.7, pp. 472-475 | Three main effects, three two-factor interactions, and a three-factor interaction describing change of a two-factor interaction across the third factor. |

The textbook supports the factorial algebra and contrast terminology. It does
not supply the cluster-bootstrap simultaneous interval algorithm used here.
That distinction is explicit in the manuscript.

## Additional inference sources

- Romano and Wolf (2005), *Econometrica* 73(4), 1237-1282,
  DOI 10.1111/j.1468-0262.2005.00615.x. Inspected the
  [author-hosted original](https://www.econ.uzh.ch/dam/jcr:ffffffff-935a-b0d6-ffff-ffffa286d4d1/etca.pdf),
  Sections 3-5. Section 5, p. 1256, gives the two-sided maximum-absolute-error
  joint region. The manuscript identifies its fixed marginal scale adaptation;
  it does not claim the full replicate-studentized/stepdown algorithm or finite
  sample coverage. First-order validity still requires consistent bootstrap
  approximation and marginal scale estimates.
- Cameron and Miller (2015), already in the thesis bibliography: justification
  and limitations of cluster-based inference, including dependence across groups.
  Alternative groupings here are sensitivity scenarios, not verified independent
  sampling units or mathematical bounds on the true uncertainty.

## Observed findings

The additive projection accounts for 75.8% of cell-exponent variation; altitude
x circuit accounts for 23.6%, and residual RMS is 0.024 H units. The circuit
gap decreases between Plains and High mountains by 0.104 for beginners and
0.109 for experts. These contrasts stay positive under the simultaneous
intervals in every resampling configuration. Their difference is unresolved.
The simple equipment contrasts for closed circuits in Plains and Hills include
zero; the other six equipment contrasts and all eight circuit contrasts remain
positive across the evaluated configurations. The long-lag decade has much
larger endpoint circuit interactions, so the fitted H values are scale-dependent.

## Validation

Numerical unit tests check exact reconstruction, zero-sum margins, orthogonal
sum-of-squares partition, agreement with an independent least-squares design,
isolation of a pure three-factor interaction, and cancellation of shared
bootstrap noise in paired contrasts. The simultaneous calibration check concerns
the empirical bootstrap distribution only, not population coverage.

- 40 targeted analysis tests passed; Ruff passed for all new Python sources.
- `audit.py` independently reconstructed all 16 x 1000 x 33 baseline cell
  replicates using direct flight-level weights. Maximum relative MSD discrepancy
  was 7.8e-15; independent least-squares H fits agreed within 1.7e-15. The
  additive projection and all 19 simultaneous contrast intervals also agreed.
- The final manuscript was compiled in an isolated temporary source directory,
  keeping the reader's PDF unchanged during calculations and layout checks.
  The new subsection is 3.2.4, printed pages 65-69 (PDF pages 69-73).
  The section pages, both figures, all three tables and bibliography entries
  were rendered and visually inspected. No undefined citations/references or
  overfull boxes occurred in the final build.
