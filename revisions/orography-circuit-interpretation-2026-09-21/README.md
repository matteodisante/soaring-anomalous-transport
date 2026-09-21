# Orography and circuit interpretation - 2026-09-21

Revised Section 3.2 after checking how circuit composition affects the
altitude-only comparison. Figure 3.6 now explicitly describes pooled
populations. It directs the reader to the crossed circuit/altitude Figure 3.9,
which shows open H above closed H in each class, and opposite lowland-minus-
mountain contrasts within the two circuits. Pooled contrast magnitudes are
not used to rank the importance of orography and circuit type.

Moved "How relief could shape transport" to the circuit-stratified discussion.
The mountain-detour hypothesis is qualified for open routes; a different
return/leg-timescale hypothesis for closed routes is explicitly unverified.
The physical mechanism behind the reversal remains unresolved. Retained the
regional analysis and stated explicitly that it also pools circuit types.

No estimator, population, saved result or figure was changed. `check_evidence.py`
reconstructs all eight circuit/altitude exponents and 12 paired contrasts from
the saved independent bootstrap audit. It checks group counts and circuit
fractions against membership, long-lag closed slopes, and the Plains MSD mixture
identity. `evidence.json` records the checks and values.

The existing FAA handbook citation supports the general lift mechanisms only:
Chapter 9, https://www.faa.gov/regulations_policies/handbooks_manuals/aviation/glider_handbook/gfh_chapter_9.pdf
It is not cited as evidence for an H ordering or the closed-route hypothesis.

Build the manuscript in an isolated source tree, visually review the revised
pages, then replace the reader-facing PDF once at the end.

Validation: all 8 fits and 12 contrasts match the saved paired bootstrap;
all signs asserted in the revised prose are confirmed. The isolated build has
93 pages and no undefined references, overfull boxes or duplicate destinations.
PDF pages 62–69 were visually inspected. Current source/generated-file hashes
matched the build snapshot at publication. This task replaced `main.pdf` once.
An external update of the reader PDF occurred during the task; the final build
includes the current source files and preserves the other manuscript changes.
