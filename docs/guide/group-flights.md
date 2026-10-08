# Group flights in the viewer

The **Group flights** tab compares cleaned flights departing from the same cell
within a chosen time window. Arrival cells and journey lengths are unrestricted.
It reuses the Routes 3D renderer, IGN elevation model, aerial imagery and thermal
density layer. Every member of the selected group is loaded, without the
300-flight sampling limit used by Routes.

## Selecting a group

Choose a **5 × 5 km** or **10 × 10 km** departure cell grid, a launch window in
minutes, and a minimum group size. The defaults are 5 km, 30 minutes and two flights.
The 10 km grid merges aligned 2 × 2 blocks of the existing 5 km Lambert-93 grid.
Departure cells use the existing metropolitan-France viewing bounds; arrival
locations can lie outside those bounds.

Optional discipline and year filters apply before grouping. Cells are ranked by
the total number of flights in qualifying groups, each counted once. The ranking
selector also offers the largest single group and the number of groups. Each cell
entry reports all three counts. Within a cell, groups are listed by decreasing size,
then increasing departure time. Changing the window recalculates the ranking.

The initial result opens the largest group in the highest-ranked cell. To explore
another result, choose its cell and launch group, then **Load selected group**.
**Prepare / refresh groups** builds missing indexes or refreshes the saved catalog.
Ordinary tab opening reuses current indexes; it never silently scans raw IGC headers.

## Exact time-window rule

For each departure cell and Europe/Paris calendar day:

1. Sort all departures chronologically.
2. The first unassigned departure opens a window of W elapsed minutes.
3. Include every remaining departure up to and including that window's end.
4. Repeat from the next unassigned departure.
5. Keep windows containing at least the selected minimum number of flights.

For W = 30 minutes and departures at 10:00, 10:20 and 10:40, the first two form one
group. The 10:40 flight starts the next window and appears as a group only if enough
other flights join it. Singletons still consume their window before the size filter
is applied. No flight belongs to two groups; a chain of nearby consecutive departures
cannot extend a group beyond W minutes.

This partition depends on the first departure. Changing W can redistribute later
groups, so the grouped-flight count need not increase monotonically. This is an
operational cohort definition, not evidence that the pilots flew together after
launch. Nearby launch sites can merge or split when the grid size changes.

Window comparisons use UTC elapsed seconds, so daylight-saving changes do not alter
their duration. Tables and group dates use Europe/Paris. Flights with unrecoverable
clocks are excluded from temporal grouping and their count is reported. The excluded
count is measured after the discipline filter, before the year filter.

## Geometry, clocks and the flight table

Geometry comes from `fixes.parquet`, with origins from `flights_meta.parquet`.
The viewer inverts each flight's local coordinates and projects them into the shared
Lambert-93 map frame, preserving all retained segments and their gaps. Raw IGC geometry
is never substituted for cleaned geometry.

Departure and arrival refer to the first and last **retained cleaned fixes**, not a
separate physical takeoff or landing detector. Absolute clocks combine the IGC clock
origin, trimming offset and cleaned relative time, reusing the verified thermal index
or the shared clock-recovery code.

The table remains in departure order and reports:

- Flight identity and discipline, departure and arrival in Paris time.
- Delay relative to the group's earliest departure and total elapsed duration.
- Horizontal distance along supported cleaned edges in Lambert-93 (**Path**).
- Horizontal separation of the first and last fixes (**Net**).
- Unsupported elapsed time (**Gaps**) and the number of continuous cleaned segments.

Path distance excludes jumps across gaps. Elapsed duration includes those gaps.
**Export group CSV** saves the displayed membership and metrics, with explicit UTC
timestamp fields.

## Reading the map

Colours progress from blue through cyan to lime in departure order. Selecting table
rows highlights their trajectories in white; **Selected rows only** isolates them.
Use the checkboxes in **Show / order** to show or hide individual paths and their
endpoint markers. Unticked flights stay in the table for easy reactivation, and
choices persist through style changes. **Hide all flights** clears every checkbox;
**Show all flights** checks them all and returns to the All view. The counter reports
the actual visible count. New groups start fully checked; visibility changes do not
alter membership, ranking, CSV exports or the all-flight thermal background.
Track width remains adjustable down to 0.1 screen pixels. First and last cleaned fixes
have distinct circle and square markers, and the departure cell has an outlined border.

The background offers elevation colours, grayscale relief and aerial imagery on the
IGN terrain. The France/world locator shows where the group is located.
**Map full screen** enlarges the main 3D map and hides the locator and flight table;
the same button restores them. Dragging the divider above the table changes its height.

Thermal density is the same Vilpellet climb-hours-per-km² layer used by
[Routes](route-comparison.md) and [Thermal density](thermal-density.md), draped on the
DEM. It uses **all available indexed flights crossing the area, all dates, heights
and disciplines**, not only the displayed group or selected year. It therefore shows
historical recorded thermal activity rather than the weather on the group's date.
Thermal pixel size is independent of departure cell size.

The renderer preserves flight altitudes. Recorder GNSS and IGN height datums have
not been harmonised; missing terrain coverage remains explicit.

## Computation and disk usage

Ranking reads a small metadata catalog, not every trajectory. Full cleaned tracks are
read only for the selected group, from the relevant Parquet row groups. DEM, aerial
imagery and the all-flight density atlas share the existing Routes caches.

On the archive checked during implementation, the catalog contains 153,975 cleaned
departures and occupies approximately 4.7 MiB. Eight clocks are unavailable. Building
the catalog from existing endpoint and clock indexes took about 11 seconds; ranking
took about 2–3 seconds. These are measurements on the current machine and archive,
not fixed performance guarantees. Geometry is not duplicated into the catalog.

For subsequent analysis, synchronized playback in absolute time, horizontal/vertical
separation curves and highlights of the members' own thermal segments would help
distinguish shared launch timing from sustained group flight. These are possible
extensions; the current tab displays complete trajectories and historical density.
