# Versioned data

This directory contains small inputs that can be distributed with the repository:

```text
data/
├── paragliders/seasons_index.csv
├── hang_gliders/seasons_index.csv
└── basemap.json
```

The season indexes contain one row per season, with source links and catalogue,
IGC-availability and download counts. `generate_stats.py` reads them to produce
acquisition statistics and season tables. These particular tables can be regenerated
without the SSD. Recomputing cleaned-data statistics and empirical figures requires
their external source tables or compatible analysis arrays.

The canonical indexes are written next to each SSD catalogue by the acquisition
commands. `scripts/reporting/tools/refresh_seasons_index.py` copies reachable indexes
here; the pre-commit hook runs it. If a discipline's SSD root is unavailable, its
versioned index is preserved. A refresh does not rebuild the cleaned archive.

`basemap.json` contains simplified Natural Earth country polygons for metropolitan
France, La Réunion and the world panel. The source is public domain. The builder is
`scripts/reporting/tools/build_basemap.py`; it needs network access. Drawing the stored
geometry requires no download, but displaying flight density still needs measured
positions.

Raw tracks, archived source XML, full catalogues, derived trajectories, diagnostic
caches and large analysis arrays remain on the SSD. See
[the disk guide](../docs/guide/data-on-disk.md) for their current organization.
