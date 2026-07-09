# From the `.igc` file to the flight

Central requirement: given a `.igc` file, trace back to *which flight* it belongs to and its
URLs. No fragile lookup dictionary is needed — the information is already in the **filename**
and in the **archived XMLs**.

## 1. The filename is self-describing

Scheme: **`{date}_{flightID}.igc`**, e.g. `2000-00-00_20150770.igc`.

The `flightID` is the unique flight key and always opens its page:

```text
# Paraglider file:
2000-00-00_20150770.igc   →   flight_id = 20150770
                          →   https://parapente.ffvl.fr/cfd/liste/vol/20150770

# Hang-glider file (same scheme, different base URL):
2014-07-15_99876.igc      →   flight_id = 99876
                          →   https://delta.ffvl.fr/cfd/liste/vol/99876
```

In code:

```python
from soaring.acquisition.ffvl.naming import parse_igc_filename
from soaring.acquisition.ffvl.seasons import flight_page_url

date, flight_id = parse_igc_filename("2000-00-00_20150770.igc")
# Paraglider base URL:
print(flight_page_url(flight_id, base_url="https://parapente.ffvl.fr"))
# Hang-glider base URL:
print(flight_page_url(flight_id, base_url="https://delta.ffvl.fr"))
```

## 2. Full metadata: the catalog

For metadata (pilot, distance, takeoff/landing, duration, …) there is `catalog.csv`, one
row per flight, **regenerable** at any time from the XMLs via `build-catalog`. It includes
the `local_path` column that links the flight to the physical file on disk.

```python
import pandas as pd
from soaring.acquisition.ffvl.config import PARA_CONFIG_PATH, DELTA_CONFIG_PATH, load_config

# Paragliders:
cfg = load_config(PARA_CONFIG_PATH, data_root_env="SOARING_PARA_DATA_ROOT")
# Hang gliders:
# cfg = load_config(DELTA_CONFIG_PATH, data_root_env="SOARING_DELTA_DATA_ROOT")

cat = pd.read_csv(cfg.catalog_path)
row = cat.loc[cat.flight_id == 20150770].iloc[0]
print(row.pilot, row.distance_km, row.takeoff, row.flight_link)

flights = cat[(cat.downloaded) & (cat.distance_km > 50)]
for p in flights.local_path:
    ...  # open the .igc and analyse it
```

!!! info "Source of truth vs derivative"
    The **source of truth** is the pair *[filenames] + [XMLs archived in `raw_xml/`]*.
    `catalog.csv` is a **convenient derivative**: if you delete it, recreate it with `build-catalog`.

Catalog columns and build logic: `soaring.acquisition.ffvl.catalog`
(see [API Reference](../reference.md)).
