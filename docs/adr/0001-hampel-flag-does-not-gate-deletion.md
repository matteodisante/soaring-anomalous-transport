# The Hampel flag never gates fix deletion

Fix-level cleaning flags off-the-trend horizontal fixes with a Hampel identifier (a
local-median outlier test) and separately deletes them with an impossibility gate
(unreachable from the last accepted fix at the absolute speed bound, with the block's
removal restoring reachability). We decided the impossibility gate alone does the
deleting; the Hampel flag is recorded for the per-flight anomaly count but is never
required to corroborate a deletion.

The two-conditions design (flag *and* gate) looks more conservative and was the first
specification, but it breaks past the identifier's own 50% breakdown point: a run of
null-island `(0, 0)` fixes longer than the window moves the local median onto the
corruption itself, so the corrupt fixes score a residual near zero and go *unflagged*
while the genuine fixes around them get flagged instead. Requiring the flag there does
not make the rule conservative, it makes it blind — one archive flight kept a corrupt
block under that reading and left a 5000 km step in the record. The impossibility gate
has no local scale in it, so contamination cannot break it the same way.

## Consequences

A future change that reintroduces "require the Hampel flag to delete" as a safety net
will silently defeat the deletion on exactly the contaminated runs it was meant to catch.
Any tightening of the deletion rule must be checked against a synthetic run of repeated
identical (or near-identical) fixes longer than the Hampel window.
