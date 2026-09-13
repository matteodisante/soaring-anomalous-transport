# Approximate marginal collapse and radial density shape

The manuscript now explicitly acknowledges the visual approximate collapse of
the absolute east/north densities. It reports the saved residual ECDF distances
and distinguishes this one-lag observation from signed or multi-time process
self-similarity. The radial laws also show partial alignment, with larger
remaining differences.

A separate derivation explains the radial Jacobian: a regular two-dimensional
joint density gives a radial density proportional to radius near zero, while
a regular absolute-component density can have a nonzero plateau. Both can
obey the same one-dimensional scaling prefactor with different scaling
functions. An exact Gaussian/half-normal/Rayleigh example illustrates this;
it is not a distribution fitted to the flights. The MIT probability course's
[derived-distributions lecture, Section 2.4](https://ocw.mit.edu/courses/6-436j-fundamentals-of-probability-fall-2018/fffea6a21fa73ed546d9edfcb4384bef_MIT6_436JF18_lec12.pdf)
provides the standard Gaussian-to-Rayleigh change of variables.

Slides 42 and 49 add the strip/disk geometry and the measured collapse
assessment. Numerical figures and all 98 thesis numerical products are unchanged.

The manuscript review was generated from the repository root with:

```bash
.venv/bin/python presentations/review_editorial.py revisions/component-scaling-and-quantile-slides-2026-09-13/manuscript-review.json revisions/marginal-collapse-and-radial-shape-2026-09-13/manuscript-review.json --scope 'Describe the observed approximate marginal collapse and its measured limitations; derive the different component and radial shapes near zero and their compatible scaling factors. All numerical products are unchanged.'
```

The helper refuses to replace a completed review. To review later edits,
choose a fresh output path and use the current completed review as its parent.
`presentations/README.md` gives the current asset preparation and PDF commands.
