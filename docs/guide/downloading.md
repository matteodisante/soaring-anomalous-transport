# Downloading the data

Two CLI tools share the same interface: `soaring-para` (paragliders) and `soaring-delta`
(hang gliders). Everything below applies to both; replace the command name as needed.

## First: set `data_root` (required)

`data_root` is where the raw data is written. This project keeps the full archives on
the external SSD. Both configuration files contain the author's actual disk paths;
on another machine, override them to point to the intended mounted archive.

The recommended way is the environment variable — it always overrides the config file:

```bash
# Paragliders
export SOARING_PARA_DATA_ROOT=/Volumes/SSD_DISANTE/paragliders/ffvl_cfd_igc

# Hang gliders
export SOARING_DELTA_DATA_ROOT=/Volumes/SSD_DISANTE/hang_gliders/delta_cfd_igc
```

Alternatively, edit `data_root` in the corresponding config file:
[`configs/para_download.yaml`](https://github.com/matteodisante/soaring-anomalous-transport)
or [`configs/delta_download.yaml`](https://github.com/matteodisante/soaring-anomalous-transport).
Either way, make sure the **external disk is mounted** first.

!!! note "The destination check tests the parent directory"
    Configuration loading requires `data_root`. At startup, the CLI then checks that
    its parent directory exists, before initializing the download. The archive root
    itself can be created later. With the configured SSD layout, a disconnected disk
    normally leaves that parent absent and the command stops with an explanation.

    Parent existence does not establish writability or that an existing location is
    the intended archive. Confirm the configured location before starting a download.

## The commands

Run commands with `uv run` (or activate the venv first with `source .venv/bin/activate`).

```bash
# Replace soaring-para with soaring-delta for hang-glider data.
uv run soaring-para fetch-xml --seasons all   # 1) archive the season XMLs (fast)
uv run soaring-para download  --seasons all   # 2) download .igc files (long, resumable)
uv run soaring-para build-catalog             # 3) generate catalog.csv + seasons_index.csv
uv run soaring-para status                    # 4) per-season summary
uv run soaring-para verify                    # 5) integrity check of .igc files on disk
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

On exfat volumes, macOS creates a `._name` sidecar next to every file it writes. To prevent
their accumulation, `download` and `fetch-xml` automatically run a cleanup (`dot_clean`) on
completion. You can also clean manually at any time:

```bash
uv run soaring-para clean    # or soaring-delta clean
```

## Time and space estimates

| Source | Files | Avg size | Total |
|--------|-------|----------|-------|
| Paragliders (`soaring-para`) | ~186,000 | ~342 KB | ~65 GB |
| Hang gliders (`soaring-delta`) | ~6,750 | ~200 KB | ~1–2 GB |

Download code: `soaring.acquisition.ffvl.download` (see [API Reference](../reference.md)).
