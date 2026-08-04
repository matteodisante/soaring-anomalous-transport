# data/

The repository-versioned data: one small per-season summary CSV per glider discipline,
and the basemap the take-off maps are drawn on. Everything else — raw `.igc` tracks,
archived XMLs, the full catalog, and every analysis byproduct (the pre-processing
track-scan cache, the MSD audit arrays, figure source data) — lives **only** on the
external SSD under `data_root`, organised by maturity (`raw/`,
`catalog/`, `derived/`, `logs/`); see the project README for that layout.

```
data/
├── paragliders/seasons_index.csv     # parapente.ffvl.fr  (SOARING_PARA_DATA_ROOT)
├── hang_gliders/seasons_index.csv    # delta.ffvl.fr      (SOARING_DELTA_DATA_ROOT)
└── basemap.json                      # coastlines + borders for fig:prelim-map
```

## `*/seasons_index.csv` — one row per season

Each row is one season, with its links (list + XML export) and counts (`n_flights`,
`n_with_igc`, `n_downloaded`).

### Why they are versioned

They are the **reproducibility anchor for the thesis's dataset numbers**. The thesis
quotes per-season and total flight counts (the `\Stat*` macros and the season tables),
produced by `scripts/reporting/generate_stats.py`. The thesis must build **offline** — on
a fresh checkout, a co-author's machine, or CI, with no SSD mounted — so the few-KB
summary each table depends on is committed, exactly as one commits the data behind a
plotted figure. This is *not* "keeping the dataset locally": the heavy data stays on the
SSD; only this tiny derived summary is versioned.

### Keeping the snapshot in sync (no silent drift)

The **canonical** index is on the SSD, written next to the catalog by
`soaring-<para|delta> build-catalog`. The copies here are a snapshot of it, and
`scripts/reporting/refresh_seasons_index.py` re-copies each reachable SSD index into this
folder so the snapshot cannot silently drift. It is best-effort — a discipline whose SSD
copy is not mounted is skipped — and the pre-commit hook runs it automatically: on a
machine with the SSD, every commit refreshes the snapshot; a checkout without the SSD
simply uses the committed copies.

## `basemap.json` — coastlines and borders (740 KB)

Natural Earth admin-0 country polygons (public domain), cropped to the three frames of
`fig:prelim-map` — metropolitan France, La Réunion, and a world panel — decimated, and
written by `scripts/reporting/build_basemap.py`.

It is committed for the same reason the season indexes are: the thesis figure that uses it
must regenerate offline. The alternative was Cartopy, which fetches Natural Earth at draw
time and drags in GEOS and PROJ; neither belongs in the dependency set of a figure the
thesis build reads. Drawing this file needs nothing but Matplotlib.

Country polygons rather than the land layer, so one pass gives both the coastline and the
borders — and so that the overseas departments arrive inside the France feature, which is
what puts La Réunion on the map at all. Re-run the builder (it needs the network) only to
change a panel's extent; nothing else in the pipeline reads it.
