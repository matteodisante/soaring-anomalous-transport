# Completed numerical and manuscript release

`manifest.json` is an exact copy of the completed run's expanded review-input
manifest. `manuscript-review.json` identifies the final reviewed thesis and source.
It records the SHA-256 of that exact numerical manifest. The original local
recovery directories are retained separately; their machine paths are provenance,
not portable data distribution paths.

All 39 stages completed. Original numerical source and the final manuscript source
have separate hashes. `../reviewed-checkout.json` records the publication back to
the working checkout without replacing unrelated viewer edits.

`../full-report-archive/` stores complete JSON bytes in lossless gzip. Final source,
generated input and thesis PDF identities are also checked directly against Git
by `../audit_committed_release.py`; see `../committed-release-audit.json` after
the delivery commits. Presentation-specific provenance lives in `presentations/`.

Trajectory files remain on the user's SSD. Their recorded identities use the
pipeline's metadata/footer/stat contract; they are not full-content hashes of
all trajectory bytes. Numerical agreement and structural checks do not constitute
independent physical validation of sensor measurements or phase labels.
