# Direct viewer-data maps for the thesis and slide 18

These are scientific exports from the viewer code, not screenshots.
`render_thermal_panels.py` uses `ThermalStore.read_plane`, `height_levels` and
the saved IGN colour maps. The prepared SQLite store is opened read-only.
No raw-flight decoding, segmentation, network access or GUI capture is needed.

| Map | Viewer cell | Height above cell reference | Crossings | Flights |
| --- | --- | --- | --- | --- |
| `mountain-low` | H2 (185,1295), High mountains #2 | 100 m | 1,856 | 1,261 |
| `mountain-high` | Same cell | 600 m | 1,868 | 1,452 |
| `plains-low` | P1 (89,1374), Plains #1 | 100 m | 1,441 | 734 |
| `plains-high` | Same cell | 600 m | 901 | 574 |

**All available dates and years are pooled, with no seasonal filter.** The
reader selects the entire prepared archive's inclusive time extent (2000–2026,
ending in June 2026). Each panel retains every saved Vilpellet climb crossing
at its exact plane, without subsampling. Reported per-year and per-month counts
show the actual temporal support; not every year or month has crossings.

Selection follows the requested saved viewer ranks: **High mountains #2**
and **Plains #1**, ranked by all-time distinct crossing-flight count within
each altitude band. The selected cells are:

- **H2**, 15,840 flights, Aulp du Seuil, Chartreuse, **Alps**.
  Cell centre: 45.359209 N, 5.906365 E. Reference: 1,756 m ASL, from five
  screened starts. Planes: 1,856 and 2,356 m ASL.
- **P1**, 2,246 flights, Suisse Normande, in the thesis's **Channel Coast**
  box. This cell is inland and has local slopes. Centre: 48.902915 N,
  0.445440 W. Reference: 185 m ASL, from 1,165 screened starts.
  Planes: 285 and 785 m ASL.

All 15,840 and 2,246 visitors have known timestamps and are read. The stored
Vilpellet classification is unavailable for 5,586 and 744 of those flights
(`unclassified` status); those cannot supply classified climb crossings.
The panel counts are the distinct flights actually contributing at each height,
not the full cell populations. The renderer does not impose the MSD cohort's
duration restriction. Both disciplines contribute: blue is paragliders,
orange is hang gliders.

Slide 16 also reports distinct flights by discipline: 1,249 PG / 12 HG at
H2 100 m, 1,434 / 18 at H2 600 m, 733 / 1 at P1 100 m, and 574 / 0 at P1
600 m. `render_figures.py` verifies the saved crossing CSV hashes and exports
these counts into `thermal-flight-counts.tex`; it needs no SSD access.

Each map covers the same 5 × 5 km Lambert-93 square within its pair, north up.
**The viewer's AGL is relative to a fixed cell reference, not local terrain.**
A low horizontal plane can intersect hillsides, restricting possible airborne
locations. The starting-altitude bands are not geomorphological classes.
The maps show observed climb crossings, not uniquely identified thermal centres,
and do not separate thermal lift from slope lift. Pooling dates mixes weather,
pilots and sampling; different flights support different heights. These images
cannot establish temporal persistence or measure displacement of the same thermal.

The France locator (`cell-locator.pdf/.png`) marks both cell centres using the
viewer basemap in `data/basemap.json`. Markers are enlarged for visibility.

Red lines trace approximate crests from IGN RGE ALTI (25 m grid, 50 m smoothing),
including secondary ridges. They remain fixed across heights and are derived
without flight coordinates. The shared `thermal_ridges` viewer module draws
the local extracts; export makes no network requests. Source, Licence Ouverte
2.0, parameters and limitations are recorded in `data/thermal_orography/README.md`.
H2's two main low-plane crossing bands chiefly follow the outer slopes of
separate ridges enclosing the Vallon de Marcieu, not one central crest.

The slide embeds PDFs; PNGs are also exported. Source-point CSVs preserve plotted
coordinates, UTC and flight identities. Counts and heights are generated into
`thermal-panel-values.tex`. The renderer also copies the four panel PDFs, locator, values and
provenance report into `thesis/generated/ch3_thermal_*`, keeping the thesis
independently compilable from the same maps.

`thermal-panels-report.json` records store metadata, reader/renderer hashes,
full-date visitor coverage, yearly/monthly counts, exact bounds, point hashes and
background provenance. Markers use saturated blue (`#005CFF`) for paragliders
and orange (`#E75A00`) for hang gliders, size 8 pt² and opacity 0.9, for
visibility in both the thesis and projected deck. They are not a calibrated density
scale. Background: **© IGN / Géoplateforme, Plan IGN**, layer
`GEOGRAPHICALGRIDSYSTEMS.PLANIGNV2`, from the viewer's existing offline cache.
The map retains its exact EPSG:2154 bounds and is not contemporaneous with the
flight dates. Region names come from `soaring.viewer.geography.classify_region`.

Reproduce from the repository root, with the prepared SSD connected:

```bash
MPLCONFIGDIR=/tmp/soaring-offsite-mpl .venv/bin/python presentations/offsite2026/render_thermal_panels.py
MPLCONFIGDIR=/tmp/soaring-offsite-mpl .venv/bin/python presentations/offsite2026/render_figures.py
python3 presentations/offsite2026/build.py
```

Then compile `thesis/main.tex` using its usual `latexmk` workflow.
