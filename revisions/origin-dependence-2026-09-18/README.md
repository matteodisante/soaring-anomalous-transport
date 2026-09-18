# Origin dependence of the increment law, 18 September 2026

Chapter 3 reads its lag distributions through stationary increments: every
estimator pools all admissible origins inside a selected segment, which
estimates one population law only if the law of `X(t+tau) - X(t)` is free of
`t`. This diagnostic tests that assumption on the published fixed cohort. It
reads the coordinate store and the published run without modifying either.

## Method

Within each selected segment the admissible origins at a lag are split into
three contiguous blocks of equal size. The early and late blocks receive
`floor(n/3)` origins each and the remainder stays in the middle, so the two ends
carry identical counts in every segment and at every lag. Each cohort flight
therefore contributes to both ends, and the late/early ratio is formed inside
each of the 1000 saved site-day bootstrap draws, which keeps the contrast
paired. Under stationary increments the ratio is one at every lag.

Pooling the three blocks must return the archived equal-flight radial M1 and M2
of `lag-*.npz` to `rtol=1e-9`. That check runs at all 33 lags before any
contrast is reported, and it passed for both disciplines. It fixes the
diagnostic to the published estimator rather than to a reimplementation.

## Result

Increments are not stationary in these segments. The late/early second-moment
ratio is resolved away from one at 33 of 33 lags for paragliders and 32 of 33
for hang gliders. Late origins give larger displacements over most of the range,
peaking at a ratio of 1.388 (1.378–1.398) for paragliders and 1.337
(1.310–1.364) for hang gliders near tau = 390 s. The excess closes at the
longest lags and falls below one for hang gliders at tau = 8160 s.

The fitted exponent is far less sensitive than the amplitude. Over 10–10000 s,
H late minus H early is -0.0104 (-0.0110, -0.0098) for paragliders and -0.0168
(-0.0186, -0.0150) for hang gliders: resolved, and small beside ratios reaching
1.39 at the same lags.

The lever arm of the contrast shrinks with lag, because the admissible origins
shrink as the lag consumes the segment. The two blocks are about 12000 s apart
at small lags and roughly half that at tau = 10000 s, with a per-flight minimum
of 1680 s there. The large-lag end of the curve is therefore a weaker test, not
a measurement of a vanishing effect.

## Reading

The direction is opposite to waiting-time ageing, which suppresses late
displacements in a subordinated walk. Launch and initial circling confine the
early part of a flight while route-following occupies its later part, and that
ordering alone reproduces the observed sign. The diagnostic separates origin
position from lag; it does not separate flight phase from wind evolution or
pilot behaviour, and it does not identify a mechanism.

For the chapter this means the pooled one-lag laws describe a mixture over
flight phases. H survives as a lag exponent of that mixture and does not survive
as the self-similarity exponent of a stationary-increment position process.

## Reproduce

See `docs/guide/chapter3-fixed-transport.md`, section "Test increment
stationarity by origin position". Run directories and replicate arrays stay
local; the portable report, CSV, figure and numerical prose are versioned in
`thesis/generated/ch3_transport_origin_dependence*`. The chapter text is the
"Does the increment law depend on the origin?" passage of
`thesis/tesi/04-fixed-transport.tex`, and the numbers it cites come from
`ch3_transport_origin_dependence_values.tex`.

No published interval is replaced. The site-day bootstrap, the cohort and the
equal-flight estimator are unchanged.
