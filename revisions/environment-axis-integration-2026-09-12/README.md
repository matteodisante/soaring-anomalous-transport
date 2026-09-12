# Independent terrain and wind references in the current thesis and slides

This revision integrates the ETOPO mountain-footprint comparison and the new
ERA5 coastal wind reference into the current Chapter 3. It also reviews the
combined manuscript containing the audited grouped TAMSD extension. The
preceding numerical records are preserved, and all 89 inherited generated
outputs retain their exact bytes. Eight new outputs publish the two
independent environmental comparisons; no flight trajectory or cleaning is rerun.

The thesis presents the methods, maps/wind rose, sensitivities and conclusions
before the equipment discussion. Six Chapter 3 slides use the same figures
and macros after manuscript review, with supervisor questions and speaker notes.

- **Pyrenees:** footprint and flight axes both approximately 170.5°, supporting
  a geographical association, without identifying a causal terrain effect.
- **Alps:** footprint 47.6°, flight 65.2°, separation 17.6°. Curvature, box
  truncation, routes and wind remain relevant.
- **Channel Coast:** annual 10 m wind axis 25.8°, flight 30.2°, separation 4.3°;
  the 100 m annual reference is similar. The warm daytime reference is 2.1°,
  giving a 28.1° separation. Annual alignment is not robust to this time selection.

Wind means use E/N velocity components, not degree averages. PCA axes are
undirected and centred. A common constant additive wind disappears under
centring at fixed lag; a climatological mean direction cannot establish the
cause of covariance anisotropy. The wind distribution is broad, with a
mean-vector/mean-speed ratio of 0.28. Weather is not matched to flight dates,
locations or heights. Neither terrain nor wind comparison tests pilot skill.

## Reusable independent inputs

- `revisions/terrain-axis-2026-09-12/`: original two ETOPO elevation subsets,
  geometric estimator, exact requests and hashes.
- `revisions/channel-wind-2026-09-12/`: **all nine** hourly ERA5 API responses
  for 2016–2025, at 10 and 100 m, compressed without loss (6,325,394 bytes),
  URLs, returned and requested coordinates, hashes, offline verifier, protected
  re-download script and reading examples. The SSD mirror is documented there.

Six-hour temporal subsampling would suffice for the indicative annual mean
(maximum change 0.52° across UTC phases). Hourly values are preserved because
storage is small and future distribution/daytime checks need the observations.
This is a sparse regional grid of provider-rounded values, not native ERA5 GRIB.

## Reproduction and audit

```bash
.venv/bin/python scripts/reporting/ch3_global_transport/generate_terrain_axis_comparison.py
.venv/bin/python scripts/reporting/ch3_global_transport/generate_channel_wind_comparison.py
.venv/bin/python revisions/environment-axis-integration-2026-09-12/review_delivery.py
```

The review refuses changed inherited calculations, inputs or numerical records.
It verifies the completed cleaning 2.3.0 definition and manifests, including
current table sizes, timestamps, row counts and footer identities. This is not
a fresh full-byte hash of all trajectory values. It verifies the new producers
and all external input hashes, checks required thesis outputs and compiles the
combined manuscript with no unresolved LaTeX warnings or overfull boxes.

`numerical-update.json` identifies the parent and eight new outputs;
`manuscript-review.json` identifies all 97 generated outputs, current sources,
external data, and the compiled thesis. `presentations/source-manifest.json`
and `presentations/validation.json` identify the slide inputs and delivered PDFs.
The slide preparation command with all four parent/extension flags is in
`presentations/README.md`.
