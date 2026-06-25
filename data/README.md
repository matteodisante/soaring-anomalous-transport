# data/

Only a small versionable artifact lives here:

- `seasons_index.csv` — one row per season with links (list + XML export) and counts
  (total flights, with track, downloaded). Generated/updated by `soaring-ffvl build-catalog`
  and copied here as a quick reference.

The **raw data** (`.igc` files, archived XMLs, full catalog) is **not** stored in the repo:
it lives in `data_root` on the external HDD (see `configs/ffvl_download.yaml`). It is ~65 GB
and is excluded via `.gitignore`.
