# Component scaling and the quantile fitting procedure

The thesis now states the signed east/north scaling laws, their marginal
density factors, and the corresponding absolute-component quantile laws.
It distinguishes a shared vector exponent from separate marginal assumptions.
All 98 generated numerical products remain unchanged.

Chapter 3 slides now show the complete sequence:

1. Signed components, absolute components and radial displacement.
2. The weighted empirical CDF and inverse-CDF quantiles at each lag.
3. Ordinary least-squares log--log fitting with an intercept, the 31-lag
   interval and the distinction between each fitted slope and a validated Hurst.
4. All three rows of thesis Fig. 3.4, as separate vector crops.
5. The existing population controls, with empirical curves and dashed saved
   fits for the fully controlled population.
6. Whole-flight bootstrap with CDFs, quantiles and fits recomputed in each draw.
7. Separate rank exponents versus the shared exponent used for density collapse.

Rebuild the manuscript review from the repository root:

```bash
.venv/bin/python revisions/component-scaling-and-quantile-slides-2026-09-13/review_manuscript.py
```

Then use the preparation command in `presentations/README.md`, passing both
editorial reviews in chronological order, and rebuild the panels and PDFs.
The presentation renderer evaluates the stored natural-log intercepts and
slopes at their original 1000-s reference; it does not re-estimate parameters.
The scientific arrays and numerical-source identities are unchanged, and the
completed parent reviews remain immutable.
