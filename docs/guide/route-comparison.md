# Cleaned flights between two cells

Open **Routes · 50-300 km** in `uv run --group viewer soaring-viewer`. The tab loads
the saved endpoint index and the busiest directed pair in the selected interval.
If no current index exists, **Prepare / refresh index** builds it once on the SSD.
Endpoint preparation is cancellable and resumes from completed Parquet row groups.
The same button also prepares the all-flight thermal background. Its separate
archive scan is cancellable and publishes only a complete density product.

**Info** explains this screen's endpoint selection, duration ranks, dates, terrain,
imagery and independent all-flight thermal overlay. The expanded locator also
has **Info**. **Sources & methods** is the viewer-wide summary; each view keeps
its own detailed explanation next to its controls.

Every displayed flight starts in the same 10 x 10 km cell A and ends in the same
10 x 10 km cell B. These are the first and last **retained cleaned fixes**, not
catalogue takeoff/landing labels or an inferred physical touchdown. Flights that
merely pass through the cells do not qualify. A to B and B to A are separate pairs.
Both disciplines can be included, or either can be selected separately.
**Pairs shared by both** further requires that both paragliding and hang-gliding
flights exist for the exact same directed pair; this does not require equal counts.

Distance presets are **50, 100, 200 and 300 km**, each with a +/-10 km interval;
the initial preset is 100 km. Changing the preset loads its busiest pair. Distances
are **between cell centres**, measured in Lambert-93 (EPSG:2154), not flown path
length. The interval is adjustable; available pairs are ordered by population,
then closeness to the interval centre. Coordinate
origins belong to individual flights: cleaned E/N/z is inverted using each flight's
saved lat0/lon0/alt0, then projected into the same Lambert-93 grid as IGN. Absolute
recorded z is retained; ENU up is never substituted for altitude.

The input is **`derived/fixes.parquet`**, columns `flight_id, segment_id, t, E, N, z`,
with `lat0, lon0, alt0` from **`flights_meta.parquet`**. Raw lat/lon tracks are not
used. Local coordinates from different flights are not directly overlaid: their
different origins are accounted for first. A round-trip test at 300 km, across
all bearings and several French latitudes and altitudes, recovers geographic
positions within 2 m including float32 storage (observed maximum about 1.5 m).
This validates display conversion, not GPS accuracy, geodesic distances measured
directly in ENU, or the recorder's vertical datum.

Pair labels say **A [col …, row …] → B [col …, row …]**. These are grid addresses,
not fractions or counts. The old stored 5 km census is merged exactly into aligned
2 x 2 blocks on read, without rescanning the archive. The pair selector's tooltip
reports the number of occupied endpoint cells. On the connected archive there are
4,346 such 10 km cells (10,563 on the previous 5 km grid); empty cells are omitted.

The **France / World** locator marks the current scene footprint and cells A/B.
**Expand map** opens a larger map with zoom/pan; its geometry is available offline.

## Durations and selection

Duration is elapsed time from the first to the last retained fix, including any
intervening gaps. Each cleaned segment is drawn separately, without connecting
unsupported edges or thinning its fixes. The source archive is read without
rerunning cleaning or segmentation.

At most **300 flights total per selected pair** are displayed. If more match, the sample always keeps
the five shortest and five longest durations from the entire matching population,
plus 290 evenly spaced ranks from the interior duration ordering. This reproducible
comparison sample is not a random population estimate. Ties break by discipline
and flight ID. The table shows the original rank, identity, departure and arrival
dates/times, and elapsed duration. **Departure (Paris)** and **Arrival (Paris)**
refer to the first and last retained fixes of the displayed trajectory. Both show
`DD/MM/YYYY HH:MM:SS` in **Europe/Paris**, with CET/CEST stated explicitly.
They restore the original IGC date/time plus `ground_phase_start_s` and the saved
endpoint time (`t0` or `t1`); archive times alone are relative, not UTC timestamps.
Only the selected flights' IGC headers/first fixes are read, in the background;
the endpoint index does not need rebuilding. Missing clock information is shown
as **Unavailable**, never replaced with a guessed catalogue date. Columns keep
dates legible; narrow windows provide horizontal scrolling.
If fewer than 300 exist, all are displayed and both counts are stated explicitly.

**5 fastest**, **5 slowest**, and **Fastest + slowest** isolate the groups without
moving the camera. They are cyan and lime green respectively, with a dark outline
to separate them from the thermal palette and imagery. Other flights are white.
Selecting table rows highlights individual flights in blue. For fewer than ten flights the two groups
overlap; shared members are marked `both` and the controls state the available count.

**Track width** ranges from **0.1 to 12 screen pixels**, in 0.1-pixel steps.
The outline shrinks along with thin strokes. Fast/slow strokes are 1.25 times this
base width and selected rows 1.75 times. The GPU expands the original cleaned
edges into strokes, so the control works on macOS core OpenGL too, including
antialiased widths below one pixel. Geometry and the camera remain unchanged.
White circles mark the first retained fixes, dark squares with white outlines
mark the last. **A · DEPARTURE** and **B · ARRIVAL** label the two endpoint cells.

**Map full screen**, at the top right, enlarges the main map, hiding
controls, the flight table and the France/world locator. The tab strip and the
same button remain visible: click **Exit map full screen** to restore the prior
window and panels. Only this button toggles the map layout. The macOS green
window button puts the complete viewer in native full screen, keeping the sidebar,
tabs and controls visible. If the viewer is already in native full screen, exiting
map full screen returns to that complete fullscreen viewer.
This also works for Trajectory, Map, Thermal planes and Thermal
density. Thermal planes hides its France overview while enlarging the horizontal
plane. The separate 3-D terrain window has its own top-right **Map full screen**
toggle with the same distinction between native fullscreen and map focus.

## Terrain and resources

One bounded elevation window is fetched from the official [IGN RGE ALTI
service](https://www.data.gouv.fr/datasets/rge-alti-r), covering all selected tracks
and both cells. The display overview has at most 600 x 600 DEM pixels, sampled at
100 m or coarser according to the extent; the actual sampling is displayed. This
does not claim native 1 m DEM detail. Unknown terrain remains a hole, and a network
or coverage failure is reported while the tracks remain available. Loading the
pair again retries an unavailable terrain window.

**Elevation colours · DEM** shows the relief with elevation colours and hillshade.
**Aerial imagery · IGN** drapes the official [IGN BD ORTHO
orthophoto](https://www.data.gouv.fr/datasets/bd-ortho-r) over the **same DEM mesh**.
Switching appearance preserves the camera, trajectories, elevations and missing
terrain triangles. The orthophoto has exactly the same Lambert-93 bounds, with
image row zero at the north. It is an overview up to 3072 pixels on its longest
side (actual metres/pixel are displayed), not a download of native-resolution
imagery across the entire corridor. Its acquisition dates differ from flight
dates. Both appearances work offline after the initial download.

**Grayscale relief · DEM** uses the same 3-D elevation mesh with a neutral gray
hillshade. It requires no additional terrain or image downloads.

The default vertical scale is 1:1. **Vertical exaggeration** exaggerates
both ground and trajectories together. The terrain can be hidden to inspect
occluded tracks; **Top view** gives the overhead projection. Recorder GNSS heights
are **not harmonised with IGN normal heights**. No datum correction, clamping to
ground or precise height-above-ground measurement is implied by the overlay.

## Thermal hours on the terrain

**Thermal hours · all flights** uses every available HMM-classified flight crossing
the area, including departures/arrivals elsewhere, both disciplines and all dates
and heights. Selecting a route, a discipline or the five fastest/slowest flights
does **not** filter this background population. It is the same quantity and uses
the same `phase_edges` and `TimeGrid` calculation as the regional Thermal density tab:

1. Read saved `derived/segmentation/phase_points.parquet` HMM decisions (currently
   every 10 seconds), recovering locations with each flight's stored origin.
2. Keep edges between consecutive `climb` decisions in the same flight and cleaned
   segment, with positive duration and no gap above 1.5 decision steps (15 s).
3. Split each edge's duration across the 50 x 50 m ground pixels it traverses,
   assuming linear motion. A stationary edge contributes all its time to one pixel.
4. Sum seconds across all flights and divide by 3600 and the pixel's area in km².

Thus 36 seconds in a 50 m square gives 0.01 h / 0.0025 km² = **4 h/km²**. It still
represents 36 recorded seconds, not four hours inside that pixel. This is cumulative
recorded climb residence time per area, not thermal counts, probability or yearly
frequency. Two pilots sharing a thermal both contribute; zero can mean unvisited.
The **What is h/km²?** button explains this with examples.

The density is a texture blended with the background **in the same shader on the
same DEM mesh**, not a 2-D plane or a second surface. Its colours cannot be hidden
by the underlying ground or flicker from competing coplanar triangles. Terrain
coverage holes remain holes. Hiding **IGN terrain** hides the background material;
the thermal colours still follow the 3-D relief. Opacity is independently adjustable.

The **Thermal pixels** control offers 250, 500, 1000 and 2000 m overviews, starting
at 250 m. Coarser pixels sum the 50 m seconds and divide by their larger area; no
spatial smoothing or invented observations are used. A side is bounded at 1600
pixels; finer options are omitted for unusually extensive scenes. Grid origins
remain fixed as routes change. The total refers to the aligned density rectangle,
which can extend less than one chosen pixel beyond the terrain. One logarithmic
colour range (0.01 to the largest archive 50 m value, at least 1 h/km²) is retained
across routes and resolutions.

The thermal cache covers France and its surroundings in Lambert-93, bounded by
(-500000, 5500000, 2000000, 8000000) m. An extent outside this prepared area reports
unavailable coverage instead of showing unknown territory as zero. Prepare it with
the viewer button or `python scripts/pipeline/prepare_thermal_density.py --only routes`.

The cache lives alongside the existing viewer cache on the archive disk:

- `route-cells.sqlite3`: endpoint cells, durations, local origins and source
  row-group lookup, with atomic publication and archive path/size/mtime checks.
- `route-terrain/ign-route-*.npz`: compressed DEM responses and provenance,
  including request URL, retrieval date and SHA-256, checked on reuse.
- `route-terrain/ign-aerial-*.npz`: aerial overview responses and the same integrity
  and georeferencing checks, plus imagery attribution.
- `route-thermal-duration.npz`: sparse all-flight 50 m thermal seconds, with source
  signatures and complete-build checks. Each scene retains only bounded overviews.

The existing `SOARING_VIEWER_CACHE_DIR` override is respected. No full trajectory
archive is copied: only necessary row groups are read, once each per scene, and
only selected tracks are retained in memory. Terrain windows are reused offline;
each new geographic extent adds small overview rasters, not a full regional DEM.

On the connected archive tested on 2026-10-05, the census covered 153,973 retained
flights with valid endpoints inside the viewer's metropolitan-France envelope. It
took about 84 seconds and wrote 36 MB. After grouping into 10 km endpoint cells,
the largest directed-pair populations at each distance were:

| Preset | Interval | Most populated pair | Centre distance | Available flights |
|---|---|---|---|---|
| 50 km | 40–60 km | (92, 645) → (95, 649) | 50.00 km | 133 |
| 100 km | 90–110 km | (95, 640) → (95, 649) | 90.00 km | 49 |
| 200 km | 190–210 km | (100, 630) → (93, 648) | 193.13 km | 6 |
| 300 km | 290–310 km | (101, 629) → (90, 657) | 300.83 km | 3 |

None contained 300 flights. The all-flight thermal preparation took about 134 s
in the initial measurement and wrote **135.5 MB**, representing 137,893 recorded
climb hours in 14,964,894 occupied 50 m pixels. All 5,017,647 occupied Alps pixels
agree with the existing Thermal density product to floating-point summation error
(maximum difference below 5e-10 seconds). These are machine/archive-specific
measurements. No raw tracks or full-resolution regional orthophotos are copied.
