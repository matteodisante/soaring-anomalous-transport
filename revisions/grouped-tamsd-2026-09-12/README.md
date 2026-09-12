# Grouped native-grid flight TAMSD

The regional and initial-altitude measurement is complete. All 155,085 eligible
paragliders and 6,060 hang gliders enter where supported. The independent audit
reconstructs 2,242 group/control/lag cells per discipline and checks 104 native
displacement stencils against the cleaned coordinates. Relative differences
are below 6e-8, consistent with the stored float32 segment curves.

The main average pools native-grid origins within flights, then weights flights
equally. It uses the full available segment population. The fixed control retains
the exact same long segments and flights through the requested 10,000-s maximum;
origins and within-flight segment weights still vary with lag. Five hundred
site-day bootstrap replicates are paired across lag and control within each group.
Bands are pointwise 95%, require 20 clusters, and do not supply simultaneous
between-group tests. Region-by-altitude cells are descriptive.

Regions are the existing Alps, Pyrenees and Channel Coast boxes. The four familiar
altitude labels use the **cleaned GNSS origin altitude**: below 300 m, 300–800 m,
800–1500 m and at least 1500 m. They describe neither local relief nor instantaneous
flight altitude. This differs from the chapter-two raw-first-altitude map with its
pressure fallback. All eligible regions enter the altitude grouping; the crossed
table exposes how strongly geography and the altitude labels are associated.

At the requested 1049-s reference lag, paraglider RMS displacements are 5.54, 4.69
and 7.42 km in the three regions. Fixed long-segment values are 6.97, 6.58 and
9.65 km. The coast remains larger. Its descriptive long-lag slope changes from
2.20 to 1.98 when segments are fixed. Plains and Hills similarly change from
2.19/2.21 to 1.97/1.93. Population selection contributes to the apparent
superquadratic growth. No Hurst estimate or causal wind/terrain effect is claimed.

The four paraglider altitude-band RMS values are 7.23, 6.25, 5.40 and 5.66 km;
their ordering is not monotonic. Regional composition and long-flight selection
matter. Hang-glider regional conclusions are limited by two-flight fixed
Pyrenean/coastal controls. The full report preserves these small cells; curves
below eight contributing flights are omitted.

The source stores are identified by the existing September 12 duplicate-byte
verification and are independently SHA-256 checked before reading. Full flight
membership, sources and input identities are preserved in `report.json.gz`.
The native requested lag grid has 59 values; it must not be presented as the
exact PCA grid. The final measurement took about ten seconds using the saved
segment curves, without another cleaning or full trajectory pass.

Reproduce from the verified source stores into a new record directory:

```bash
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1 \
.venv/bin/python scripts/reporting/ch3_global_transport/generate_grouped_tamsd.py \
  --audit-dir revisions/vertical-gap-split-2026-09-11/recovery-runs/20260912T104500Z-5cfc4e8c/arrays \
  --record-dir /path/to/a/new/grouped-tamsd-run \
  --input-proof revisions/vertical-gap-split-2026-09-11/ssd-duplicate-verification.json
```

The full rebuild contains the `grouped_tamsd` stage after native TAMSD measurement.
Saved results can be redrawn using `--render-only` and the same record directory.
Complete reports remain immutable; an initial local rendering iteration is kept
under ignored `initial-render/`. Its numerical result arrays agree exactly with
the final report.

## Combined manuscript delivery

The V2/V3 extension was completed in commits `119755d`, `3d2395a` and `a041fc3`.
This follow-up owns `generate_grouped_tamsd.py`, `grouped_tamsd.py`, the
`04-grouped-tamsd.tex` section, its figures, eight new TAMSD frames, and the
`--tamsd-update` presentation overlay. It preserves the concurrently developing
terrain-axis and coastal-wind work. The audited `numerical-update.json` preserves
all inherited numerical inputs. Its measurement review used `--numerical-only`;
the grouped-TAMSD report does not certify the terrain/wind outputs.

The completed [combined manuscript review](../environment-axis-integration-2026-09-12/manuscript-review.json)
uses this numerical update as its parent and verifies the union of 97 generated
outputs, including both extensions, against the 131-page thesis. The TAMSD
figures, eight slide layouts and their notes have been visually checked.
Presentation preparation uses all four overlays, ending with
`--environment-update revisions/environment-axis-integration-2026-09-12`;
the full command is in [the presentation instructions](../../presentations/README.md).
This preserves the separate numerical records while identifying one shared,
reviewed manuscript and slide delivery.
