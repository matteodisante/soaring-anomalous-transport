# Final manuscript review — 11 September 2026

`completion.json` records the final checks and the 101-page PDF identity.
`final-run-manifest.json` and `ssd-manuscript-review.json` are copies of the closed
SSD records for run `20260910T221820Z-05d36ab4`.

The final manuscript includes the interpretation of the new cleaning, revised
mathematical explanations and cautions, corrected bibliography, and checked figure
layouts. The parameter table distinguishes altitude admission from fix cleaning,
defines the adjacent-window vertical rule and its finite-step fallback, uses the
50 m reach allowance at every fix, and reports the Savitzky–Golay temporal span as
`(w−1)Δt`. Its dataset paragraph distinguishes retained trajectories from subsets
admitted by later estimators.

The original numerical-execution PDF and initial authored sources are preserved
here. `manifest.json` retains their initial hashes and identifies the final
versions separately. The earlier PDF review remains available in
`ssd-manuscript-review-before-table-proofread.json`; the later record supersedes it.

The three `fresh-result-audit-*-final.json` files repeat the independent algebraic
and support checks against the closed run manifest. Files without `-final` preserve
the earlier checkpoints. `ssd-readme-final.md` is the inspected disk inventory.
The test and build logs are evidence of the reported checks, not substitutes for
independent statistical or behavioural validation.

`resume-ssd-review.py.txt` preserves the one-off reconciliation procedure prepared
while the disk was disconnected. It has already been executed and is not a general
rerun command. For a new analysis use `scripts/rebuild_thesis.py`; for a subsequent
authored revision use `scripts/review_thesis.py` as described in the rebuild guide.
