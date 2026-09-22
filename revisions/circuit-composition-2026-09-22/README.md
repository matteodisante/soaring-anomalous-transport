# Circuit composition and the interpretation of Section 3.2.1

Review of 22 September 2026. This analysis does not edit the manuscript.

The relevant mixture is **open and closed flights within each altitude class**.
The current example about the contribution of Plains/Hills to the all-altitude
MSD addresses a different question and should be replaced.

The circuit imbalance substantially increases the pooled lowland-minus-mountain
H contrast. The stronger statement that the contrast is entirely compositional
is not supported: it persists after using the same circuit proportions in every
altitude class. Nor is the remaining contrast an identified terrain effect.

## Direct check using the saved MSD curves

For an altitude class `a`, among classified flights,

```text
M_a(p, tau) = p M_open,a(tau) + (1-p) M_closed,a(tau)
```

Hold both conditional MSD curves fixed, assign the same `p` to all four classes,
and fit each resulting curve in log-log coordinates. Never average the circuit
H values. The reference `p = 0.3888083` is the open fraction among the cohort's
46,195 classified flights. Its complement is the closed fraction. The 78
unclassified flights are excluded from these mixtures; their removal changes
the original class H estimates by at most 0.000055.

| Class | Open share among classified flights | H, observed mix | H, common 38.9% open | Nominal 90% interval, common mix |
|---|---:|---:|---:|---:|
| Plains | 91.1% | 0.9496 | 0.9125 | [0.9106, 0.9143] |
| Hills | 71.1% | 0.9285 | 0.9007 | [0.8989, 0.9024] |
| Low mountains | 33.6% | 0.8661 | 0.8687 | [0.8677, 0.8697] |
| High mountains | 35.1% | 0.8751 | 0.8760 | [0.8752, 0.8769] |

The mountain percentages differ slightly from the manuscript's 33.5% and 35.0%
because the manuscript denominator includes unclassified flights.

| Contrast | Original H gap, classified flights | Gap, common mix | Reduction |
|---|---:|---:|---:|
| Plains - Low mountains | 0.0835 | 0.0438 | 47.5% |
| Plains - High mountains | 0.0744 | 0.0365 | 50.9% |
| Hills - Low mountains | 0.0625 | 0.0320 | 48.8% |
| Hills - High mountains | 0.0534 | 0.0246 | 53.8% |

All four remaining contrasts have positive paired site-day bootstrap intervals;
the exact intervals are in `results.json`. This uses the existing 1000 paired
replicates and holds the reference fraction fixed in every replicate. Intervals
retain the original bootstrap assumptions and are not multiplicity-adjusted.

The numerical reduction depends on the chosen common composition. At 50% open,
the reductions are 37.2-40.6%. These are descriptive reweightings, not unique
causal percentages attributable to circuit choice.

The existing circuit-specific results independently exclude a purely
compositional account with common circuit laws across terrain classes:

| Circuit | Plains H | Hills H | Low mountains H | High mountains H |
|---|---:|---:|---:|---:|
| Open | 0.953 | 0.944 | 0.893 | 0.889 |
| Closed | 0.825 | 0.816 | 0.846 | 0.866 |

Within open flights, lowland H is larger; within closed flights, it is smaller.
The residual associations may involve route geometry, weather, equipment and
other differences, as well as terrain. The present data do not separate them.

## The appropriate MSD share

For the same class `a`, use

```text
w_open|a(tau) = p_open|a M_open,a(tau) / M_a(tau).
```

At 10000 s, open flights account for approximately 99.4%, 97.6%, 60.6% and
48.0% of the classified-flight MSD in Plains, Hills, Low mountains and High
mountains, respectively. This demonstrates the user's intended mechanism inside
each class. Those shares are not averages or weights for the fitted H values;
H must still be fitted to the mixed curve across the full lag interval.

## Recommended argument and section order

1. **Declared circuit and horizontal transport.** Introduce the current Figure
   3.8 first: open and closed have different MSD curves and H. Keep the simple
   return-constraint explanation; defer the detailed triangle/out-and-return
   timescale discussion until after the main comparisons or shorten it.
2. **Initial altitude and circuit composition.** Define the four altitude classes,
   show the current Figure 3.6, immediately show their open/closed proportions,
   then write the within-class mixture. The two emphasized points must concern
   open flights within each altitude class, not altitude classes within the
   whole archive.
3. **Separate composition from conditional differences.** Continue the same
   subsection with the current Figure 3.9 and the common-composition check.
   Report what shrinks and what remains before discussing physical mechanisms.
4. **Regional comparisons**, followed by **equipment comparisons**. Put the
   regional detour after the composition argument is complete. It is subject
   to the same interpretation limits unless circuit composition is also matched.

This is more effective than swapping the existing subsections as whole blocks:
the present 3.2.2 already includes altitude-specific results whose definitions
are currently in 3.2.1.

Suggested central paragraph, contingent on integrating this check:

> The larger pooled H in Plains and Hills reflects a substantial contribution
> from their greater prevalence of open routes. Assigning every altitude class
> the same 38.9% open-flight fraction reduces the lowland-minus-mountain H gaps
> by approximately half. Positive gaps remain, however, and the altitude ordering
> reverses between open and closed routes. The pooled curves therefore combine
> circuit composition with circuit-specific transport differences; they do not
> identify an effect of terrain alone.

The sentence currently asserting that circuit choice is shaped by the launch
environment solely on the evidence of different circuit percentages should
also be softened: those percentages establish an association, not its direction
or cause.

## Artifacts and reproduction

- [Diagnostic figure](composition_control.png): actual circuit proportions and
  fitted H as a function of the open fraction used to combine each class's curves.
  Dots show the observed mixes; squares show the common-mix control.
- [Results and provenance](results.json): source hashes, curves, fits, paired
  intervals, contrasts, composition sensitivity and within-class MSD shares.
- [Analysis script](analyze.py): checks every input point curve and original H
  against the published report before computing the control.

From the repository root:

```bash
MPLCONFIGDIR=/private/tmp/soaring-mpl-cache .venv/bin/python revisions/circuit-composition-2026-09-22/analyze.py
```

Uses only the portable conditional report and independently verified saved
replicates; no trajectory remeasurement or source-cache mutation is required.
