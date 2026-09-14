# Scale-dependent anisotropy and whitening

The thesis and both Chapter 3 decks now develop Matteo's interpretation that
longer displacement intervals can reveal terrain constraints and persistent wind
contributions that are less visible over short parts of a flight.

The terrain discussion gives the time needed to explore a corridor as a concrete
interpretation of feeling a boundary. It distinguishes this example from actual
pilots anticipating terrain or following usable lift. The wind discussion treats
coherence, cancellation and a weak directional contribution emerging above
background dispersion. A derived example assumes isotropic diffusive background
motion and independent wind that varies across observations but stays constant
within an increment. It is illustrative and has not been fitted to flights.
Common deterministic wind cancels from the centred covariance. The observed
ordering across four lags does not identify a cause, and changing population
support remains relevant.

Whitening separately at every lag enforces an identity covariance on the fitted
weighted sample when that covariance is positive definite. Different directional
correlation times supply a counterexample to second-order isotropy of the whole
process, even when every one-time distribution is isotropic. A different matrix
at every lag can also break increment additivity. The PCA figures still use the
existing scalar trace normalisation.

The four added slides are 83--86 in `chapter3.pdf`, and 12--14 and 16 in
`chapter3-section35.pdf`. Both notes PDFs include the assumptions and discussion
questions. The two France maps remain slides 5--6 in the focused deck. The
directional-memory counterexample remains in the thesis; its separate slide
was removed from both decks at Matteo's request. Slide 13 of the focused deck
explicitly defines the illustrative terrain exploration time and its parameters.

Sources checked: Taylor (1922), pp. 207--208, for integrated velocity covariance
and coherence limits; Kessy, Lewin and Strimmer (2018), DOI
10.1080/00031305.2016.1277159, for the whitening identity. Terrain times, the
independent-wind example and the temporal counterexample are explicit mathematical
illustrations, not source-attributed empirical flight results.

The `no-ai-slop` editing skill guided the prose: preserve the proposed mechanisms,
state the conditions in which they work, and keep the thesis and slides concrete.
The detailed edited text is in the environmental-interpretation and whitening
paragraphs of thesis Section 3.5.2. The presentation source files contain the
complete shorter versions. Numerical figures and measurements are unchanged.

After compilation and visual inspection, `review_delivery.py` verifies the
parent's numerical and environmental inputs, checks the four frames agree,
checks the reported ratios and illustrative algebra, and records a new immutable
manuscript review. It refreshes only manuscript provenance in the presentation
manifest. `presentations/validate.py` then checks all six PDFs and asset hashes.
