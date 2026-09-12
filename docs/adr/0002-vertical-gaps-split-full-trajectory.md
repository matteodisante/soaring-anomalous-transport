# Long altitude gaps split the full trajectory

From pipeline 2.3.0, the existing `g_max` bound applies to elapsed time between
consecutive finite altitude readings as well as gaps between surviving fixes.
A gap exactly at the bound may be filled; a longer gap ends one supported segment
at the last finite reading and starts the next at the first finite reading after it.
Intervening horizontal fixes are excluded too. Missing altitude at segment endpoints
is removed, never extended by carrying an endpoint value. Mandatory cleaning
boundaries are preserved, including those inside a missing-altitude interval.

The previous unlimited interpolation could produce minutes of artificial altitude.
Flags protected phase-feature windows but did not make the reconstructed trajectory
valid for every downstream observable. Splitting the full trajectory matches the
pipeline contract that every retained segment has complete E, N and z coordinates.

Unsupported intervals are recorded as rejected segment candidates. Supported
candidates retain the parent's clock and origin, acquire censoring flags, and pass
the existing duration and coverage gates independently. Horizontal coverage is lost
and phases can be truncated; the gap cap remains an operational choice, not proof
that short interpolation resolves every manoeuvre. All derived tables, observables,
phase models, figures and the thesis must be rebuilt after adopting this rule.
