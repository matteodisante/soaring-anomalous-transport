# What is on the SSD

Every byte of data lives on the external disk, never in the repository. This page is the
map: what each directory holds, what each file is, and — for every table — its shape, its
dtypes and its first rows, as you would see them if you opened it yourself.

Those views are not typed out here. They are the output of
`scripts/reporting/show_dataset.py`, which reads the real files and prints them, so the
page can be refreshed after any run and cannot drift from the disk:

```bash
SOARING_DELTA_DATA_ROOT=... uv run python scripts/reporting/show_dataset.py \
    --discipline "hang gliders"
```

The pilot name and pilot URL of the catalog are the one thing the script does not print:
a public listing is still not something to reproduce in a repository page, so those two
fields show what kind of value they hold instead of the value.

The repo keeps only the small versioned `data/<discipline>/seasons_index.csv`, a copy of
the season summary used to regenerate the thesis tables without the disk mounted.

### `suspect_intervals.parquet`

Slow-and-flat stints too short to excise, one row per stint: `source`, `flight_id`,
`t_start`, `t_end` in the re-zeroed clock. Stage (iii) produces them so the ψ(τ) fits can
be re-run with and without them as a sensitivity check. Written even when empty.

> **The views below are from pipeline 1.3.0.** The nine blocks that `show_dataset.py`
> produces reproduce byte for byte against the archive as it stands, checked rather than
> assumed; the others — the directory tree, the `.igc` and XML excerpts, a log extract —
> are quoted from their own sources. Re-run `show_dataset.py` after the next full pass and
> paste its output over the generated ones. The page is only worth what its freshness is.

## The two roots

One root per discipline, each self-contained and identically laid out. They are found
through environment variables, so no path is ever hard-coded:

| discipline | environment variable | root |
|---|---|---|
| paragliders | `SOARING_PARA_DATA_ROOT` | `/Volumes/SSD_DISANTE/paragliders/ffvl_cfd_igc` |
| hang gliders | `SOARING_DELTA_DATA_ROOT` | `/Volumes/SSD_DISANTE/hang_gliders/delta_cfd_igc` |

The directory names on disk (`paragliders/`, `hang_gliders/`) are *not* the values of the
`source` column in the tables (`paraglider`, `hangglider`). That is deliberate — a
directory is a place, a source is a label — and the mapping lives in
`scripts/preprocess.py`.

## Layout

```
<data_root>/
├── raw/                     immutable: what the acquisition downloaded
│   ├── igc/<season>/        the track files, one directory per season
│   └── raw_xml/<year>.xml   the season listings, as served
├── catalog/                 tables derived from the listings (metadata only)
│   ├── catalog.csv          one row per flight the CFD lists
│   └── seasons_index.csv    one row per season
├── logs/                    what the acquisition did, and what it failed to do
│   ├── download.log
│   └── failures.csv
└── derived/                 everything the analysis produces
    ├── track_scan.parquet   the census scan cache (pre-cleaning diagnostics)
    ├── fixes.parquet        the processed trajectories
    ├── segments.parquet     one row per segment
    └── flights_meta.parquet one row per flight attempted
```

Three maturity levels, and the boundary between them is a rule: **`raw/` is never
modified**, `catalog/` is regenerable from `raw/`, and `derived/` is regenerable from
both. Deleting `derived/` costs computation, never data.

## `raw/igc/` — the tracks

186,052 paraglider files over 27 seasons, 6,716 hang-glider files over 24. One directory
per season, named `<start>-<end>`:

```
raw/igc/1999-2000/   raw/igc/2000-2001/   ...   raw/igc/2023-2024/   raw/igc/2025-2026/
```

File names are `<date>_<flight_id>.igc`, the date as the CFD declares it and the
`flight_id` as its primary key (`soaring.acquisition.ffvl.naming`). The date can be a
placeholder — `2000-00-00_20150770.igc` is a real file — which is why nothing downstream
parses the date out of the name.

A file is plain IGC text: an `H` header block, then one `B` record per fix.

```
AXSR
HFDTE010923
HFFXA035
HFPLTPILOTINCHARGE:Margaux
HFGTYGLIDERTYPE:NKN
HFDTM100GPSDATUM:WGS-84
...
B0545152107904S05518180EA006400078612-016010
B0545162107906S05518177EA006390078512-014010
```

Only the `B` records are read (`soaring.analysis.igc.parse_igc`), at the fixed character
positions the FAI standard defines: time `[1:7]`, latitude `[7:15]`, longitude `[15:24]`,
the `A`/`V` validity flag `[24]`, barometric altitude `[25:30]`, GNSS altitude `[30:35]`.
The trailing digits are logger-specific `I`-record extensions and are ignored.

Parsing one file gives this — the table every later stage starts from:

```
fixes (in memory, one track)   shape = 3,261 rows x 6 columns

dtypes:
  t                     float64
  lat                   float64
  lon                   float64
  valid                 bool
  baro_alt              float64
  gnss_alt              float64

head(4):
   t     lat      lon  valid  baro_alt  gnss_alt
 0.0 44.2977 5.763400   True    1260.0    1353.0
30.0 44.2977 5.763400   True    1260.0    1353.0
60.0 44.2977 5.763400   True    1259.0    1352.0
90.0 44.2977 5.763417   True    1260.0    1352.0
```

`t` is seconds elapsed from the first fix, with the UTC midnight roll-over unwrapped and
any backward step *left in place*: that is a defect for the cleaning to remove, not for
the parser to hide. `baro_alt` and `gnss_alt` are `0` where the logger writes no such
channel, which is how a GNSS-only flight announces itself. The four rows above are a
hang glider still on the ground: 30 s cadence, the position unchanged to the fourth
decimal.

## `raw/raw_xml/` — the season listings as served

One file per season year, `1999.xml` … `2025.xml`, kept exactly as the site returned it.
They are the provenance of `catalog.csv`: if a catalog field is ever in doubt, the answer
is in the XML.

```xml
<?xml version="1.0" encoding="UTF-8"?>
<ffvldata url="https://parapente.ffvl.fr/cfd/liste/2019" comment="generated from www.ffvl.fr" ...>
<cfdflightlist nb_flights="10966">
<flight ...
```

## `catalog/catalog.csv` — one row per listed flight

87 MB for paragliders, 3.6 MB for hang gliders. 23 columns
(`soaring.acquisition.ffvl.catalog.CATALOG_COLUMNS`), regenerable with `build-catalog`:

```
catalog/catalog.csv   shape = 9,259 rows x 23 columns

dtypes:
  flight_id             int64
  season                str
  season_year           int64
  date                  str
  pilot                 str
  flight_type           str
  distance_km           float64
  points                float64
  duration_s            float64
  speed                 float64
  takeoff               str
  landing               str
  dept                  str
  club                  str
  wing                  str
  wing_class            str
  flight_link           str
  igc_link              str
  tracklog_id           float64
  pilot_link            str
  local_path            str
  downloaded            bool
  file_size             int64

head(4), columns 1-12:
 flight_id    season  season_year       date                  pilot  flight_type  distance_km  points  duration_s  speed                takeoff                 landing
       573 2001-2002         2001 2002-03-10           <pilot name> Aller-Retour         36.0    46.8         NaN    NaN SANT HILAIRE DU TOUVET                  Lumbin
       574 2001-2002         2001 2002-03-23 <anonymised at source>   Dist libre        220.0   220.0         NaN    NaN          SAINT SULPICE            Casteljaloux
       575 2001-2002         2001 2002-03-17           <pilot name>   Dist libre         30.0    30.0         NaN    NaN          COL DE BLEINE Attérissage Saint André
       576 2001-2002         2001 2002-03-17           <pilot name>   Dist libre         31.0    31.0         NaN    NaN         LES MONEDIERES          Lac le Chammet

head(4), columns 13-23:
dept                                 club    wing        wing_class                             flight_link igc_link  tracklog_id  pilot_link local_path  downloaded  file_size
 NaN GRENOBLE CHARTREUSE VOL LIBRE (GCVL)    Atos    Rigide Class 5 https://delta.ffvl.fr/cfd/liste/vol/573      NaN          NaN <pilot URL>        NaN       False          0
 NaN                                  NaN  Atos V    Rigide Class 5 https://delta.ffvl.fr/cfd/liste/vol/574      NaN          NaN <pilot URL>        NaN       False          0
 NaN           DELTA CLUB DU BAR SUR LOUP Topless     Delta Class 1 https://delta.ffvl.fr/cfd/liste/vol/575      NaN          NaN <pilot URL>        NaN       False          0
 NaN                                  NaN   Astir Delta Class Sport https://delta.ffvl.fr/cfd/liste/vol/576      NaN          NaN <pilot URL>        NaN       False          0
```

**This is metadata, and it can be wrong.** It is a coarse pre-filter and a provenance
source, never the basis of a scientific cut — every number the thesis quotes about
trajectories comes from the tracks themselves. Its known quirks: placeholder dates
(`0000-00-00`, `2000-00-00`), `duration_s = 0.0` where the hang-glider file leaves the
field blank, `dept` carrying non-French sentinels (`0`, `999`), `wing_class` not
comparable across the two disciplines, and `local_path` still naming an older disk
(`HDD_DISANTE`) for the rows downloaded before the move — which is why the pipeline
locates files by walking `raw/igc/` rather than by trusting that column.

## `catalog/seasons_index.csv` — one row per season

The download ledger. Also committed to the repo, so the thesis season tables build
without the disk:

```
catalog/seasons_index.csv   shape = 25 rows x 7 columns

dtypes:
  season_year           int64
  season                str
  list_url              str
  xml_url               str
  n_flights             int64
  n_with_igc            int64
  n_downloaded          int64

head(4):
 season_year    season                             list_url                                    xml_url  n_flights  n_with_igc  n_downloaded
        2001 2001-2002 https://delta.ffvl.fr/cfd/liste/2001 https://delta.ffvl.fr/cfd/liste/2001?xml=1        248           0             0
        2002 2002-2003 https://delta.ffvl.fr/cfd/liste/2002 https://delta.ffvl.fr/cfd/liste/2002?xml=1        281           6             6
        2003 2003-2004 https://delta.ffvl.fr/cfd/liste/2003 https://delta.ffvl.fr/cfd/liste/2003?xml=1        256          28            25
        2004 2004-2005 https://delta.ffvl.fr/cfd/liste/2004 https://delta.ffvl.fr/cfd/liste/2004?xml=1        244          35            25
```

`n_flights` is what the season listed, `n_with_igc` how many carried a track link,
`n_downloaded` how many were fetched. The three differ, and the gaps are the subject of
the coverage discussion in the thesis.

## `logs/`

`download.log` is the acquisition's own record, appended across runs — including the day
the data root moved:

```
2026-06-26 17:51:22,827 INFO data_root = /Volumes/SSD_DISANTE/ffvl_cfd_igc
2026-07-05 19:02:30,135 INFO data_root = /Volumes/SSD_DISANTE/paragliders/ffvl_cfd_igc
```

`failures.csv` is the retry registry: one row per flight whose track could not be
fetched, with the reason — a Cloudflare challenge, or a response that was not an IGC at
all.

```
logs/failures.csv   shape = 30 rows x 4 columns

dtypes:
  flight_id             int64
  season                str
  igc_link              str
  error                 str

head(2):
 flight_id    season                                                                                         igc_link                                       error
      1152 2003-2004           https://delta.ffvl.fr/sites/parapente.ffvl.fr/files/igcfiles/-igcfile-51598-196818.igc invalid content (does not look like an IGC)
      1140 2003-2004 https://delta.ffvl.fr/sites/parapente.ffvl.fr/files/igcfiles/2004-04-25-igcfile-89740-196631.igc invalid content (does not look like an IGC)
```

## `derived/track_scan.parquet` — the census cache

One row per *readable* parsed flight, twelve scalar columns, produced by
`track_stats`/`load_or_scan_tracks`. It exists to decouple the cost of reading the
archive (hours, once) from the cost of asking it a question (instant), and every
`\StatScan*` macro in the thesis is a query against it.

```
6,716 rows in 1 row groups, 0.4 MB on disk, SNAPPY

derived/track_scan.parquet   shape = 6,716 rows x 12 columns

dtypes:
  duration_s            float64
  n_fix                 int64
  path_km               float64
  extent_km             float64
  dt_s                  float64
  max_gap_ratio         float64
  missing_fraction      float64
  baro_present_frac     float64
  max_vxy_mps           float64
  max_vz_mps            float64
  baro_alt_min_m        float64
  baro_alt_max_m        float64

head(4), columns 1-7:
 duration_s  n_fix    path_km  extent_km  dt_s  max_gap_ratio  missing_fraction
     1740.0    349   9.963398   2.288345   5.0       1.000000          0.000000
    20996.0   2099 283.732285  62.048893  10.0       1.300000          0.000762
    15066.0    730 145.955185  36.239109  21.0       5.142857          0.000000
    18102.0   1802 237.710438  74.587096  10.0       5.000000          0.005080

head(4), columns 8-12:
 baro_present_frac  max_vxy_mps  max_vz_mps  baro_alt_min_m  baro_alt_max_m
               0.0    56.496301         0.0             0.0             0.0
               1.0    28.861290         5.9          1059.0          3036.0
               0.0    22.413217         0.0             0.0             0.0
               1.0    28.669268         5.0          1458.0          3782.0
```

Row 1 of that head is a GNSS-only flight (`baro_present_frac = 0`, so the three
barometric columns are all zero and mean nothing); row 3 is a 21 s logger whose largest
gap is five times its own cadence. Both are exactly the populations the pre-processing
cuts have to be audited against.

Two things to know before using it. It carries **no `flight_id`**: rows are in
`sorted(rglob("*.igc"))` order and are identified positionally, which is enough for
distributions and not enough for a join — a limitation, not a design. And it is
**pre-cleaning**: it describes parsed tracks, not processed ones, which is exactly what a
diagnostic that justifies a cut has to do (a cut is audited on the population it acts on).
For post-pipeline numbers, use `flights_meta.parquet` below.

## `derived/fixes.parquet` — the trajectories

The output of the pipeline, and the largest artefact by three orders of magnitude:
**43 GB and 1.36 × 10⁹ rows** for paragliders, 1.2 GB and 3.4 × 10⁷ for hang gliders.
One row per **grid point** of every retained segment, keyed `(source, flight_id,
segment_id)`:

```
34,525,108 rows in 43 row groups, 1,161.6 MB on disk, ZSTD

derived/fixes.parquet   shape = 34,525,108 rows x 18 columns

dtypes:
  source                str
  flight_id             str
  segment_id            int16
  t                     float32
  E                     float32
  N                     float32
  z                     float32
  v_E                   float32
  v_N                   float32
  v_z                   float32
  a_E                   float32
  a_N                   float32
  a_z                   float32
  interpolated          bool
  z_reconstructed       bool
  edge                  bool
  hampel_flagged        bool
  alt_invalidated       bool

head(4), columns 1-9:
    source flight_id  segment_id    t          E           N           z       v_E       v_N
hangglider       975           0  0.0  -2.644085   -4.948205 1458.585693 13.275144  1.215108
hangglider       975           0 10.0 111.172691  -33.921207 1460.657104  9.778760 -5.975531
hangglider       975           0 20.0 198.742096 -103.775276 1468.514282  8.025670 -6.961107
hangglider       975           0 30.0 279.220947 -138.911942 1463.914307  7.008325 -2.623670

head(4), columns 10-18:
      v_z       a_E       a_N       a_z  interpolated  z_reconstructed  edge  hampel_flagged  alt_invalidated
-0.532143 -0.436803 -1.029317  0.192857         False            False  True           False            False
 0.721429 -0.262474 -0.408811  0.057857         False            False  True           False            False
 0.625000 -0.088144  0.211696 -0.077143         False            False False           False            False
-1.466667  0.072790  0.463077 -0.047143         False            False False            True            False
```

Zstd, ~33 bytes per row, written in batches of 400 flights, streamed by analyses rather
than loaded (43 GB).

**A row group is not a batch.** The writer hands pyarrow 400 flights at a time; pyarrow
then splits what it is handed into row groups of its own default size — which is why the
header above says 43 row groups for an archive written in 16 batches. So a flight *can*
straddle a boundary, and a reader that iterates row groups and groups by `flight_id` sees
it as two flights. Read this file through
[`soaring.analysis.derived.stream_flights`](../reference.md#analysisderived),
never with `read_row_group` directly: it holds back the last flight of each row group and
prepends it to the next, so it always yields whole flights.

| column | dtype | meaning |
|---|---|---|
| `source` | string | `paraglider` / `hangglider` / `sailplane`; a new source is a new value, never a new column |
| `flight_id` | string | with `source`, the primary key of a flight |
| `segment_id` | int16 | 0-based within the flight; a split at a long gap or an excised run increments it |
| `t` | float32 | s, elapsed flight time. **Zero at the first fix of free flight of the parent** — a segment keeps the parent's clock and never restarts at zero |
| `E`, `N` | float32 | m, local ENU east and north, **smoothed**; the origin is the parent's first airborne fix |
| `z` | float32 | m, the adopted altitude channel at its measured value, smoothed; never re-zeroed |
| `v_E`, `v_N`, `v_z` | float32 | m/s, the first derivative of the same Savitzky–Golay fit |
| `a_E`, `a_N`, `a_z` | float32 | m/s², its second derivative |
| `interpolated` | bool | **the time base** had no fix within half a step of this grid point, so `(E, N, z)` were all reconstructed at resampling |
| `z_reconstructed` | bool | this grid point's **altitude** did not come from a measured one — either because `interpolated` is set, or because the fix it came from carried no altitude (the logger wrote none, or the cleaning removed it). A hole in the vertical opens no time gap, so it forces no split and `interpolated` stays False: exclude on *this* flag for any vertical analysis. Its per-flight companions in `flights_meta` are `frac_z_reconstructed` and `z_gap_max_s`, the longest unbroken run in seconds |
| `edge` | bool | within a half-window of a segment boundary, where the filter is evaluated off-centre and carries more variance |
| `hampel_flagged` | bool | the fix was off its local trend; recorded, not acted on |
| `alt_invalidated` | bool | the cleaning removed this altitude (as opposed to the logger never writing one) |

Nothing that is pure algebra of these is stored: `|v|`, the heading, the curvature, the
turn radius, the glide ratio are computed at analysis time.

Two properties hold by construction and are checked by `scripts/verify_dataset.py`: no
`nan` anywhere in the kinematics, and no step *inside* a segment exceeding the fix-level
speed bound.

### From this table to the MSD

The handoff the transport analysis actually makes, stated once so that nothing downstream
has to infer it.

**Which rows.** Every row of `fixes.parquet`. The table already contains only retained
segments of retained flights — a dropped segment has no rows here, and the retention
decisions are recorded in `segments.parquet` and `flights_meta.parquet`, not re-applied at
read time. So "the analysis ensemble" is exactly "the flights that appear in
`fixes.parquet`", 155,788 paragliders and 6,132 hang gliders.

**Which columns.** `t`, `E`, `N` for both estimators, plus `segment_id` to know where a
segment ends. Nothing else: `z`, the velocities and the accelerations belong to the
phase segmentation, and the boolean flags are read only by `verify_dataset.py`.

**How they are read.** Through `soaring.analysis.derived.stream_flights`, one whole flight
at a time — *never* by iterating Parquet row groups. A row group is a unit of storage and
cuts across flights; the direct reading counted 0.7 % of flights twice and truncated the
longest segments, which are exactly the ones the long-lag end of the time-averaged curve
rests on.

**What `segment_id` means to each estimator.** They differ, and the difference is
deliberate:

- The **ensemble MSD** concatenates every retained segment of a flight in the parent clock
  and treats the result as one record. A segment keeps its parent's origin and clock, so
  `|r(t)|²` is always the squared displacement from that flight's take-off at elapsed
  time `t`, whether or not the record is continuous up to `t`. A lag falling inside a gap
  is answered by neither side, because the split bound makes every gap wider than the
  half-step coverage tolerance.
- The **time-averaged MSD** runs strictly *within* one segment and never across the gap
  that ends it, since the trajectory across that gap is unknown.

**Consequences to keep in mind.** A flight whose first segment did not survive resampling
starts its record at `t > 0` (1.4 % of paragliders, 11.7 % of hang gliders); its positions
are still measured from its own take-off, it simply does not answer the earlier lags. And
a boundary at a *re-acquisition offset* rather than at a gap puts an unknown constant into
the absolute position, which enters the ensemble MSD and cancels out of the time-averaged
one — bounded by `verify_dataset.py` at 0.029 % of paraglider flights.

## `derived/segments.parquet` — one row per segment

Every segment the splitting produced, **retained or not**, with the reason for each
drop:

```
13,222 rows in 1 row groups, 0.2 MB on disk, ZSTD

derived/segments.parquet   shape = 13,222 rows x 13 columns

dtypes:
  source                str
  flight_id             str
  segment_id            int64
  t_start               float64
  t_end                 float64
  n_fix                 int64
  n_fix_raw             int64
  frac_interpolated     float64
  frac_z_reconstructed  float64
  censored_start        bool
  censored_end          bool
  kept                  bool
  drop_reason           string

head(4):
    source flight_id  segment_id  t_start   t_end  n_fix  n_fix_raw  frac_interpolated  frac_z_reconstructed  censored_start  censored_end  kept                 drop_reason
hangglider       975           0      0.0 20640.0   2065       2064           0.001453              0.001453           False         False  True                        <NA>
hangglider      1032           0      0.0 14175.0      0        691           0.001479              1.000000           False         False False channel_not_reconstructable
hangglider      1037           0      0.0 17660.0   1767       1766           0.000000              0.000000           False         False  True                        <NA>
hangglider      1049           0      0.0 19698.0      0        960           0.000000              1.000000           False         False False channel_not_reconstructable
```

`n_fix` counts the rows the segment contributed to `fixes` (zero when dropped) against
`n_fix_raw`, its measured fixes. `censored_start`/`censored_end` are `True` only at a
boundary a *split* created: the flight's own first and last boundary truncate the phase in
progress too, but they are a different thing, and are told apart by these being `False`.
`segment_id` is assigned at split time and stays stable, so a gap in the numbering is
itself the record of a drop.

## `derived/flights_meta.parquet` — one row per flight *attempted*

Including the ones the pipeline dropped: the census of what was removed is as much a
result as what was kept. 47 columns, which read down rather than across — one retained
flight beside one the flight filter rejected:

```
6,716 rows x 47 columns (6,132 retained, 584 dropped)

                     a retained flight           a dropped one
source                      hangglider              hangglider
flight_id                          975                     830
pipeline_version                 1.3.0                   1.3.0
drop_stage                         NaN           flight_filter
drop_reason                        NaN  duration_below_minimum
error_detail                      None                    None
alt_source                        baro                    gnss
baro_present_frac                  1.0                     0.0
baro_range_m                    1977.0                     0.0
n_alt_missing_raw                    0                     349
n_fix_raw                         2099                     349
n_fix_clean                       2069                     348
n_merged_duplicates                  0                       0
n_removed_backward                   0                       0
n_removed_spike                      0                       1
n_removed_frozen                    30                       0
n_alt_out_of_band                    0                       0
n_alt_vz_spike                       0                       0
n_flagged_kept                      40                       8
n_vz_runs                            0                       0
n_alt_level_shift                    0                       0
split_jump_max_m                   0.0                     0.0
n_boundaried                         0                       0
integrity_fraction                 0.0                0.004587
ground_phase_start_s             300.0                   485.0
ground_phase_end_s             20945.0                  1570.0
trimmed_fraction              0.002464                0.376437
n_interior_excised                   0                       0
n_suspect_stints                     0                       0
duration_flight_s              20645.0                  1085.0
path_km                     283.408578                6.044969
alt_range_m                     1977.0                     NaN
extent_km                    62.132928                1.892541
lat0                         43.812717                     NaN
lon0                          6.809883                     NaN
alt0                            1459.0                     NaN
dt_native_s                       10.0                     NaN
g_max_s                           20.0                     NaN
n_segments                         1.0                     NaN
n_segments_kept                    1.0                     NaN
frac_interpolated             0.001453                     NaN
frac_z_reconstructed          0.001453                     NaN
z_gap_max_s                       10.0                     NaN
was_resampled                     True                    None
savgol_order                       3.0                     NaN
savgol_window_horiz                5.0                     NaN
savgol_window_vert                 5.0                     NaN
```

Every column is filled by the stage named in the left margin below, and a dropped flight
keeps everything the stages *before* the verdict had already measured — flight 830 above
was judged on a duration of 1085 s, and its cleaning counters are there to be audited
even though none of its fixes reached the trajectory table.

| group | columns |
|---|---|
| identity | `source`, `flight_id`, `pipeline_version` |
| verdict | `drop_stage`, `drop_reason` (both null when the flight is retained), `error_detail` (set only when `drop_reason` is `pipeline_raised`: the exception text, so the offending file can be found — the reason itself is a fixed string the census can count) |
| (i) altitude channel | `alt_source`, `baro_present_frac`, `baro_range_m`, `n_alt_missing_raw` |
| (ii) cleaning | `n_fix_raw`, `n_fix_clean`, `n_merged_duplicates`, `n_removed_backward`, `n_removed_spike`, `n_removed_frozen`, `n_alt_out_of_band`, `n_alt_vz_spike`, `n_flagged_kept`, `n_vz_runs`, `n_alt_level_shift` (unreturned vertical steps: neither spike nor run, so censored by nothing — counted so they are auditable, see `sec:fixlevel`), `n_boundaried`, `split_jump_max_m` (the largest displacement across a boundary this stage declared: excising a frozen run leaves both sides genuine, splitting at a re-acquisition offset does not, so everything after it carries an unknown constant that enters the *ensemble* MSD and not the time-averaged one — reported so the effect can be bounded and excluded on, never acted upon), `integrity_fraction` |
| (iii) trimming | `ground_phase_start_s`, `ground_phase_end_s`, `trimmed_fraction`, `n_interior_excised`, `n_suspect_stints` |
| (iv) flight filter | `duration_flight_s`, `path_km`, `alt_range_m`, `extent_km` |
| (v) local frame | `lat0`, `lon0`, `alt0` |
| (vi) resampling | `dt_native_s`, `g_max_s`, `n_segments`, `n_segments_kept`, `frac_interpolated`, `frac_z_reconstructed`, `z_gap_max_s`, `was_resampled` |
| (vii) smoothing | `savgol_order`, `savgol_window_horiz`, `savgol_window_vert` |

`ground_phase_start_s` / `ground_phase_end_s` are in the **recorded** clock, the one the
IGC file carries, because the integrity gate has to count its removals inside that window;
every other time is in the re-zeroed flight clock.

`pipeline_version` is what tells two runs apart. It is bumped whenever a stage changes
what it produces, so a table written by an older pipeline can be recognised rather than
silently mixed with a newer one.

## Regenerating any of it

| artefact | command | cost |
|---|---|---|
| `raw/`, `catalog/`, `logs/` | `soaring-para` / `soaring-delta` (acquisition CLI) | days, network-bound |
| `derived/track_scan.parquet` | delete it; `generate_preproc_figure.py` rebuilds it | tens of minutes |
| `derived/{fixes,segments,flights_meta}.parquet` | `scripts/preprocess.py` | ~80 min for both archives, 8 workers |
| the thesis figures and macros | `generate_*.py` in `scripts/reporting/` | seconds to ~20 min |

`scripts/verify_dataset.py` checks the processed tables against the invariants Chapter 2
claims for them, and exits non-zero if one fails.
