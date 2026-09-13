# Joint laws and the interpretation of second differences

This manuscript revision clarifies two distinct issues in Chapter 3:

- The signed east–north law at one lag is two-dimensional. Comparing those
  laws across lags does not determine temporal joint laws or establish
  finite-dimensional process self-similarity.
- Constant velocity is cancelled exactly, but this does not make the residual
  scale-free. The identity `V2 = tau^2 D2^2` relates the measured exponent to
  differences between consecutive interval-mean velocity vectors. Saved curves
  have a nonmonotone D2 of roughly 4.9–7.3 m/s for paragliders and 7.6–11.5 m/s
  for hang gliders over 10–10,000 s. Finite persistence, turning and route phases,
  together with changing observation support, are plausible explanations for
  the curvature; no single physical cause is identified.

A stationary exponential velocity-covariance example gives V2 growth from
cubic to linear across its persistence time. This is an analytical
counterexample to interpreting every second-difference slope as 2H, not a
model fitted to the flights. The thesis also specifies the limits of fixed
flight cohorts and the further checks needed to discriminate mechanisms.

Run from the repository root:

```bash
.venv/bin/python revisions/joint-laws-and-hurst-interpretation-2026-09-13/review_clarification.py
```

The script reproduces the published slopes and support counts from the saved
full-archive measurement arrays, records their hashes and D2 curves, checks
the analytical formula against independent covariance integration, and builds
the thesis. It verifies that all 98 generated numerical products and all
external inputs still match the completed wind-at-altitude parent review.
No cleaning or transport measurement is rerun. The parent manifest is unchanged.
The new manuscript review records the PDF and changed source identities.

See `presentations/README.md` for asset preparation against this new review.
The existing slides already distinguish spatial and temporal laws and explain
the interval-mean velocity identity; this revision changes their manuscript
provenance without requiring new numerical figures.
