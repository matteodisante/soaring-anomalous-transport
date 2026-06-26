# Downloading the data

Everything goes through the `soaring-ffvl` CLI.

## First: set `data_root` (required)

`data_root` is where the raw data is written, and it **must point to the external disk**
(the data is ~65 GB). The repository ships a **placeholder** value on purpose (so no path
tied to a specific machine is committed), so you must set it before running anything.

The recommended way is the environment variable — it always overrides the config file and
keeps your machine-specific path out of the repo:

```bash
export SOARING_FFVL_DATA_ROOT=/Volumes/<YOUR_DISK>/ffvl_cfd_igc
```

Alternatively, edit `data_root` in
[`configs/ffvl_download.yaml`](https://github.com/matteodisante/soaring-anomalous-transport).
Either way, make sure the **external disk is mounted** first.

!!! warning "If `data_root` is not set, the CLI stops immediately with a clear message"
    Every command checks `data_root` at startup. If it still points to the placeholder,
    to an **unmounted** disk, or to a disk that was **renamed**, the command aborts right
    away with an explanation and the fix — *before* any download or write:

    ```text
    ERROR: data_root is not usable: /Volumes/<YOUR_DISK>/ffvl_cfd_igc
    Its parent directory does not exist. Likely causes: the external disk is not
    mounted, was renamed, or data_root is still the placeholder.
    ...
    ```

    This is safe by design: the macOS mount point `/Volumes` is not user-writable, so a
    wrong path can never cause a silent download to the wrong place — it fails fast.

## The four commands

Run commands with `uv run` (or activate the venv first: `source .venv/bin/activate`,
then use `soaring-ffvl ...` without the prefix).

```bash
uv run soaring-ffvl fetch-xml --seasons all   # 1) archive the season XMLs (fast)
uv run soaring-ffvl download  --seasons all   # 2) download .igc files (long, resumable)
uv run soaring-ffvl build-catalog             # 3) generate catalog.csv + seasons_index.csv
uv run soaring-ffvl status                    # 4) per-season summary
```

The `--seasons` argument accepts: `all`, a single year (`2014`), a range (`2010-2015`), or a
list (`2010,2012,2015`).

### Useful `download` options

| Option | Effect |
|--------|--------|
| `--workers N` | number of parallel downloads (default from config) |
| `--limit N`   | at most N files per season (for testing) |
| `--dry-run`   | does not download: only counts what would be done |

## Robustness

!!! tip "Safe to interrupt and resume"
    The download is **resumable**: already present files are skipped. You can stop it
    (`Ctrl-C`) and relaunch it: it picks up where it left off. Writes are **atomic**
    (temporary `.part` file, then renamed), so a file with its final name is always
    complete and valid — important on exfat, which has no journaling.

- Every downloaded file is **validated** as IGC (initial `A` record + `B` record); HTML or
  truncated responses are discarded and retried.
- Failed attempts are recorded in `logs/failures.csv` (for targeted retry); the full log
  is in `logs/download.log`.

## `._*` files on exfat (macOS)

On exfat HDDs, macOS creates a `._name` sidecar next to every file it writes. To prevent
their accumulation, `download` and `fetch-xml` automatically run a cleanup (`dot_clean`) on
completion. You can also clean manually at any time:

```bash
uv run soaring-ffvl clean
```

(On non-macOS systems or without `dot_clean`, the cleanup is simply skipped.)

## Time and space estimates

~186,000 files, ~342 KB average → **~65 GB**. With few workers, a few hours (resumable, so
overnight is fine). The required space is well within the capacity of a ~1 TB HDD.

Implementation details are in `soaring.acquisition.ffvl.download`
(see [API Reference](../reference.md)).
