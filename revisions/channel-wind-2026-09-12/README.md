# Channel Coast: archived ERA5 wind reference

The current coastal comparison is extended to measured flight altitude in
`revisions/channel-wind-flight-altitude-2026-09-13/`. This directory preserves
the completed surface-reference inputs and earlier review; use the new
revision for current wind results and manuscript reproduction.

This directory preserves **all nine hourly API responses used in the thesis**,
losslessly compressed as `cell-0.json.gz` to `cell-8.json.gz`. They contain
87,672 consecutive UTC hours per cell, from 2016-01-01 00:00 through
2025-12-31 23:00, with speed (m/s) and meteorological direction (degrees from
north, clockwise, **where wind comes from**) at 10 and 100 m above ground.
The nine files total **6,325,394 bytes** (6.33 MB, 6.03 MiB). These are the
provider's JSON values, including its numerical rounding; they are not native
ERA5 GRIB files or an archive of every ERA5 grid cell in the box.

## Source and spatial selection

Data: Copernicus Climate Change Service, *ERA5 hourly data on single levels*,
[DOI 10.24381/cds.adbb2d47](https://doi.org/10.24381/cds.adbb2d47), accessed
through the [Open-Meteo Historical Weather API](https://open-meteo.com/en/docs/historical-weather-api)
on 12 September 2026. Credit both Copernicus/ECMWF and Open-Meteo on reuse;
the source datasets and API data carry attribution requirements.
These calculations are the author's interpretation, not an endorsement by the providers.

The exact Channel Coast take-off box is longitude −1.8 to 2.0°, latitude
48.3 to 51.2°. We request the centres of a regular 3 × 3 partition, explicitly
select ERA5, and use `cell_selection=nearest` and `elevation=nan` to avoid a
land preference and elevation downscaling. ERA5's 0.25° grid returns nine
distinct cells: latitudes 48.75, 49.75, 50.75° crossed with longitudes
−1.25, 0, 1.25°. This is a sparse regional reference, not a local coastal-flow
model. The manifest retains requested coordinates, returned coordinates,
full URLs, retrieval times, units via the responses, and SHA-256 identities
of both compressed and decompressed bytes.

## Calculation and interpretation

Convert speed `s` and meteorological direction `phi` to air-motion components:
`u = -s sin(phi)` east and `v = -s cos(phi)` north. Average components over
hours and approximately by cell area with `cos(latitude)` weights, then take
`atan2(mean(v), mean(u))`. Angles below are counterclockwise from east,
modulo 180° for comparison with the **undirected** PCA axis. No arithmetic
mean of degree angles is taken.

| Wind selection | Wind axis | Flight PCA at 10,000 s | Axis separation |
|---|---:|---:|---:|
| 10 m, all hours | 25.8° | 30.2° | 4.3° |
| 100 m, all hours | 26.8° | 30.2° | 3.3° |
| 10 m, April–September, 09–17 UTC inclusive | 2.1° | 30.2° | 28.1° |

The main mean flow goes towards the northeast, from meteorological 244.2°.
The ratio of mean-vector speed to mean scalar speed is 0.28: considerable
cancellation occurs across the distribution of winds. It is neither a confidence
level nor the fraction of winds in the mean direction. The wind rose shows
frequencies in 15° **towards** sectors, excludes speeds below 0.5 m/s and
normalises the retained observations; the vector mean includes all hours.

Annual alignment is close and similar at 100 m, but **does not persist in the
warm daytime selection**. The latter is only an operational sensitivity
window, not a match to recorded flight conditions. Ten years reduce reliance
on one unusual year; they do not reproduce the full 1999–2026 flight archive.
There is no matching to actual dates, locations or flying altitude. The PCA
uses 1,680 supported coastal flights; cell-hours are not independent flight
replicates. A fixed additive wind shifts mean displacement and disappears
from centred covariance at fixed lag. Variable winds and route responses can
still affect covariance, but alignment with a climatological mean cannot
establish this mechanism or pilot skill.

## Why preserve hourly values?

`sampling-check.json` tests every UTC phase of 3-, 6-, 12- and 24-hour
subsampling of the annual 10 m series. The largest changes from the hourly
axis are 0.16°, 0.52°, 5.70° and 14.47°, respectively. Six-hourly data would
suffice for this indicative annual mean. Hourly values cost only about 6 MB
and preserve the distribution and flexible seasonal/daytime checks; retaining
them avoids irreversible information loss. Finer spatial coverage and a
longer period are not required for the stated indicative comparison.

## Reuse and reproduction

From any directory, verify the frozen archive without network access:

```bash
python3 /path/to/repo/revisions/channel-wind-2026-09-12/fetch_wind.py
```

From the repository root, reproduce the calculation, plot and sampling check:

```bash
.venv/bin/python scripts/reporting/ch3_global_transport/generate_channel_wind_comparison.py
.venv/bin/python revisions/channel-wind-2026-09-12/check_temporal_sampling.py
```

The comparison reads the current `thesis/generated/ch3_revision.json` for the
flight axis; a complete frozen copy is in the reviewed PCA revision as gzip.
The weather observations are readable independently with Python's standard library:

```python
import gzip, json
with gzip.open('cell-0.json.gz', 'rt', encoding='utf-8') as stream:
    cell = json.load(stream)
print(cell['latitude'], cell['longitude'])
print(cell['hourly_units'])
print(cell['hourly']['time'][:3])
```

To fetch the same requests again, use `fetch_wind.py --download-to NEW_DIRECTORY`.
This never overwrites the original inputs; provider revisions can change a
new response. No token or account is embedded. Anyone receiving this directory
can reuse the exact saved inputs offline.

A verified mirror is stored on the SSD at
`/Volumes/SSD_DISANTE/derived-audit/external-data/channel-wind-2026-09-12/`.
The repository archive is the shareable primary copy; the SSD mirror is a backup.
