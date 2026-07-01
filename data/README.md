# data/

Only a small versionable artifact lives here:

- `seasons_index.csv` — one row per season with links (list + XML export) and counts
  (total flights, with track, downloaded). Generated/updated by `soaring-para build-catalog`
  and copied here as a quick reference for the paraglider dataset.

The **raw data** (`.igc` files, archived XMLs, full catalog) is **not** stored in the repo:
it lives in `data_root` on the external SSD (see `configs/para_download.yaml` for paragliders
and `configs/delta_download.yaml` for hang gliders). It is excluded via `.gitignore`.
