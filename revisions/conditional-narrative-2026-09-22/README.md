# Section 3.2 and seminar narrative: marginal comparisons, interactions, future factorial analysis

The main manuscript and current offsite presentation now use the same argument:

1. Describe marginal open/closed transport before the altitude comparison.
2. Explain how the circuit mix within each altitude class enters its MSD.
3. Display circuit-by-altitude interactions and retain the existing paired tests.
4. Continue with regional and equipment comparisons, retaining their findings.
5. Explain unequal composition separately from interactions in H, and motivate
   the joint analysis needed for the future group/solo comparison.

The archive analysis is described as marginal and stratified, rather than a
controlled one-factor-at-a-time (OFAT) experiment. The OFAT and full factorial
definitions cite the NIST/SEMATECH handbook. Main effects and interactions also
refer to the existing Mohr, Wilson and Freund reference. Factorial implementation
and results remain in Experimentals, explicitly provisional and outside the
main chapter's conclusions.

## Interpretation of the supplied contribution plot

The script supplied by the user computes `w_c|a = p_c|a M_c,a / M_a`, where the
denominator is the full altitude-class MSD. These are circuit contributions
**inside each altitude class**, not altitude contributions inside all open or
closed flights. Unclassified flights remain in the denominator. Their unplotted
contribution is at most 0.21% across the published curves.

At 10000 s, open circuits supply 99.4%, 97.6%, 60.6% and 48.0% of the MSD in
Plains, Hills, Low mountains and High mountains. Low mountains supplies the
minority example: 33.5% of flights are open but contribute 60.6% of the MSD.
Open flights are already a numerical majority in Plains and Hills.
The manuscript distinguishes fixed flight fractions from lag-varying MSD shares
and does not use these shares to average the fitted H values.

`scripts/tesi/ch03_fixed_transport/circuit_msd_weights.py` generates the vector
figure, numeric macros and JSON provenance from the portable conditional report.
The conditional renderer now invokes it, and the offsite renderer uses the same
calculation with the deck's palette and larger labels.

## Documents

- Thesis: Section 3.2.1 circuit, 3.2.2 altitude and circuit interaction,
  3.2.3 regions, 3.2.4 equipment, 3.2.5 synthesis and future joint analysis.
- New Figure 3.8: circuit MSD contributions. The former altitude Figure 3.6
  becomes Figure 3.7, and the circuit-by-altitude figure remains Figure 3.9.
- Offsite deck: 18 slides, including the original evidence and three new slides
  on the comparison method, contribution shares, and factorial/group-solo work.
  Both the projection and English speaker-note PDFs are updated.
- The older extended chapter decks remain historical September 14 presentations,
  as documented in `presentations/README.md`; they do not present the current
  Section 3.2 results and were not rewritten.

## Checks

- All 264 open/closed contribution values reproduce the supplied script's
  calculation from `ch3_conditional_curves.csv` to floating-point precision.
- Circuit shares plus the unclassified remainder sum to one within each class.
- A complete conditional redraw in a temporary directory produces the new
  figure, macros and JSON and reproduces the contribution arrays.
- Thesis, experiments, 18-slide projection deck and 18-page notes deck compile.
- Modified thesis pages and slides are visually reviewed for labels, wrapping,
  equations and figure placement. The contribution legend was moved to avoid
  covering the curves.

`before/` preserves the pre-edit manuscript and seminar sources/PDFs, including
the uncommitted edits that were already present. The separate reweighting check
in `revisions/circuit-composition-2026-09-22/` remains a diagnostic: no new
composition-standardized H estimates or provisional factorial results are
promoted to the main chapter.
