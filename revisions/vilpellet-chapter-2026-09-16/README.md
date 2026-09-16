# Vilpellet implementation reference chapter — 2026-09-16

Chapter 5, printed pages 125–130 (PDF pages 130–135), documents the implemented
Vilpellet segmentation without selecting it over the Chapter 4 Gaussian HMM.
It reuses the existing HMM theory, derives the three binary indicators, prints
the applied parameter blocks, describes eligibility, boundary handling and
majority voting, and provides a worked flight and a code reading guide.

The focused report was regenerated on the existing example flight. Its numerical
results and applied configuration are identical to the saved report before this
revision. Only report metadata and three parameter macros changed. All other
inherited generated files retain their original SHA256. No SSD archive products,
segmentation algorithms or configurations were changed.

`before/` preserves the inherited entry point, report and generator;
`before-generated-sha256.json` fingerprints the inherited products.
`manuscript-review.json` records checks, source hashes, PDF hash and review scope.
`build.log` records the successful full LaTeX build (trailing whitespace removed). All six chapter pages were
rendered and visually inspected. The focused build/provenance tests passed (16).
Two missing provenance headers in Chapter 3 are inherited and recorded separately;
this revision does not claim that the global provenance check is clean.
