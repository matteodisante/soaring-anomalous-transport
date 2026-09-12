# Channel Coast wind at mean flight altitude

This focused extension compares the current 10,000-s coastal paraglider PCA
with an independent ERA5 wind climatology evaluated at the mean altitude of
**the same PCA windows**. It preserves the completed cleaning 2.3.0, the full
flight transport report, the terrain comparison and the previous surface-wind
estimates. The parent review is `environment-axis-integration-2026-09-12`;
its completed records remain immutable.

## Flight population and vertical reference

`flight-altitude.json` retains all 1680 contributing flight IDs and the 2013
window-mean altitudes. The producer reads current cleaned GNSS `z`, interpolates
within each retained segment on the existing 10-s PCA grid, and integrates
altitude by the trapezoidal rule on each exact nonoverlapping 10,000-s window.
The mean is **1006.262 m**, with equal weight per window, matching the PCA.
Equal weight per flight gives 980.260 m. The window-mean interquartile range
is 853.932–1159.549 m; it is population spread, not uncertainty in the mean.
Shorter flights cannot support this lag and therefore do not define this
particular altitude target. No flight increment or altitude integral crosses
a cleaning boundary.

The GNSS datum is not harmonised across recorders. Absolute logged `z` is used
as an **approximate mean-sea-level altitude**, with no receiver-specific geoid
correction. It is neither ENU up, take-off altitude nor height above ground.
This limits the precision of the physical height match. Sensitivities evaluate
the wind at both quartiles and at the equal-flight mean as well.

## Preserved independent atmospheric observations

Source: Copernicus Climate Change Service / ECMWF,
[ERA5 hourly pressure-level data](https://doi.org/10.24381/cds.bd0915c6), via
the public [Earthmover ERA5 archive](https://registry.opendata.aws/earthmover-era5/).
Attribution: contains modified Copernicus Climate Change Service information.
The public archive specifies CC-BY-4.0. The analysis is the author's; neither
ECMWF nor the European Commission endorses its interpretation.

- Anonymous S3 bucket `earthmover-icechunk-era5`, prefix `icechunkV2`,
  group `pressure/temporal`, pinned snapshot `TGSHKBHQ8D687WS6STMG`.
- Hourly timestamps, 2016-01-01 00:00 through 2025-12-31 23:00 UTC inclusive:
  **87,672 hours per cell**.
- Nine exact 0.25-degree grid cells: latitudes 48.75, 49.75, 50.75 degrees north
  crossed with longitudes −1.25, 0, 1.25 degrees east. These are the same cells
  used for the preceding surface analysis, nearest the centres of a 3 × 3
  partition of the Channel Coast take-off box.
- Pressure levels 1000, 925, 850, 700 hPa; variables `u`, `v` (m/s), `z`
  (geopotential, m²/s²), and static `surface_geopotential` (m²/s²).
- `pressure-wind.npz`: complete selected float32 values, compressed **without
  loss**, plus timestamps, levels and coordinates. No temporal subsampling,
  spatial averaging or interpolated-height replacement is applied to this input.
- `pressure-input-manifest.json`: retrieval time, package versions, variable
  metadata, source identity and exact archive SHA-256.

Only this regional selection is retained, not a global ERA5 archive. The
remote chunks transferred to extract it are larger than the final selection.
Hourly observations allow interpolation against each hour's changing pressure
heights and preserve the directional distribution and selectable daytime hours.
Their small retained size makes a coarser temporal extraction unnecessary.
The original nine 10/100-m AGL API responses remain in
`../channel-wind-2026-09-12/` as lower-level controls.

## Estimator and interpretation

For each cell and hour, convert geopotential to geopotential height
`H = z / 9.80665`, then to spherical geometric height
`h = 6371000 * H / (6371000 - H)`, following
[ECMWF's height convention](https://confluence.ecmwf.int/pages/viewpage.action?pageId=226496389).
Interpolate the **east and north components**, linearly in geometric height,
between the two levels bracketing the flight-altitude target. Require both
bounds above the model surface; reject missing or unbracketed profiles rather
than silently changing the time population. Never assign a fixed height to a
pressure level or interpolate direction angles.

Average components over hours, with cell weights `cos(latitude)`. Main cases:

1. All year, all hours (87,672 hours per cell).
2. All year, **09–17 UTC inclusive** (32,877 hours per cell).

Separate seasonal checks retain April–September, with both all hours and
09–17 UTC (43,920 and 16,470 hours per cell). UTC is used consistently; the
clock range is not adjusted for local daylight saving or inferred flight times.
The towards-angle is `atan2(mean_v, mean_u)`, counterclockwise from east;
reduce modulo 180 degrees for comparison with the undirected PCA axis.
The shortest axis separation lies between 0 and 90 degrees. The ratio of
resultant speed to mean speed measures cancellation, not confidence or the
fraction of winds near the mean. Frequency roses omit speeds below 0.5 m/s;
component means retain every selected hour.

This is a climatological reference at representative flight altitude. Weather
is not matched to flight dates, positions or instantaneous altitude. The box
classifies take-offs and need not contain whole routes. Mean wind and centred
displacement covariance are different statistics: a common constant additive
wind cancels under centring at fixed lag. Any alignment is descriptive and
does not identify the cause of anisotropy or a pilot/equipment effect.

## Results and supported-height sensitivity

At 1006.262 m, the annual all-hour wind axis is **15.8°**, the 09–17 UTC axis
**17.9°**, against **30.2°** for flight PCA: separations **14.4° and 12.3°**.
The respective April–September axes are 16.0° and 20.6°, with separations
14.2° and 9.6°. Annual mean-vector/mean-speed ratios are 0.43 and 0.44.
The annual alignment is less close than at 10/100 m AGL, while time-selection
sensitivity is smaller aloft. This supports a broad orientation resemblance,
with a remaining offset, without identifying the cause of the covariance.

All **789,048** profiles bracket the main mean-height target above ground.
At the lower quartile, 868 profiles at one cell have no above-ground lower
bound. For height sensitivity only, remove those **868 hours from every cell
and every tested height**, including a matched mean-height reference. This
retains 86,804 common hours per cell; seasonal/daytime masks then act on the
same common support. The main comparisons retain all their selected hours.
On common support, the annual quartile-height axes range from 14.3° to 17.2°
(all hours) and 16.4° to 19.3° (09–17 UTC). Equal-flight mean altitude changes
the matched mean-height axes by less than 0.3°; common-hour selection changes
the main annual axes by less than 0.1°. These are descriptive sensitivities,
not confidence intervals or receiver-datum uncertainty bounds.

The pressure archive is **32,216,992 bytes** (32.22 MB compressed), plus small
metadata and the per-flight altitude summary. Its SSD mirror is
`/Volumes/SSD_DISANTE/derived-audit/external-data/channel-wind-flight-altitude-2026-09-13/`.
`completion.json` records final mirrored-file hashes, free space and delivered
thesis/slide identities after their review. The earlier surface archive keeps
its own existing SSD mirror.

## Reuse and reproduction

Read the full input offline with standard NumPy:

```python
import numpy as np

with np.load('pressure-wind.npz') as data:
    time = data['time_hours_since_epoch'].astype('datetime64[h]')
    u = data['u']       # cell, hour, pressure level; m/s
    v = data['v']
    phi = data['z']     # geopotential, NOT metres
    levels = data['pressure_hpa']
```

From the repository root, verify the frozen atmospheric archive or explicitly
extract the same pinned snapshot to a **new** directory:

```bash
python3 revisions/channel-wind-flight-altitude-2026-09-13/fetch_pressure_wind.py
uv run --no-project --with icechunk --with xarray --with zarr --with 'numcodecs[pcodec]' python revisions/channel-wind-flight-altitude-2026-09-13/fetch_pressure_wind.py --output /path/to/new-directory
```

A matching existing manifest invokes verification without network access.
An isolated download environment keeps the cleaning environment unchanged.
For current measured outputs (altitude measurement requires the SSD):

```bash
.venv/bin/python scripts/reporting/ch3_global_transport/measure_channel_flight_altitude.py
.venv/bin/python scripts/reporting/ch3_global_transport/generate_channel_wind_comparison.py
```

The measurement report includes run timestamps, so remeasurement gives a new
byte identity even when all scientific values agree. Do not replace frozen
review inputs or relabel an old completed review after rerunning a producer.
The archived altitude summary, pressure observations, preserved surface inputs
and full PCA report support offline reproduction without reading trajectory
rows. The full PCA report is committed as
`presentations/data/ch3_revision.json.gz`; in a fresh checkout, restore its
canonical uncompressed path before running the wind producer:

```python
from pathlib import Path
import gzip
import hashlib
import json

root = Path('.')  # repository root
raw = gzip.decompress((root / 'presentations/data/ch3_revision.json.gz').read_bytes())
altitude = json.loads((root / 'thesis/generated/ch3_channel_flight_altitude.json').read_text())
assert hashlib.sha256(raw).hexdigest() == altitude['flight_report_sha256']
target = root / 'thesis/generated/ch3_revision.json'
if target.exists():
    assert target.read_bytes() == raw
else:
    target.write_bytes(raw)
```

`numerical-audit.json` records independent scalar interpolation checks and
preservation of the earlier surface estimates. `numerical-update.json` links
the parent results and four current outputs. `manuscript-review.json` identifies
the full reviewed thesis and 98 current generated outputs; it verifies cleaning
manifests and table stat/footer identities, not a fresh whole-table checksum.
The presentation preparation adds `--wind-altitude-update` to the existing four
parent flags, after the manuscript has been completed and reviewed.
