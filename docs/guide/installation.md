# Installation

The project uses [uv](https://docs.astral.sh/uv/) for environment and dependency management
(reproducible via `uv.lock`). Without uv, `venv` + `pip` can be used instead.

## With uv (recommended)

```bash
cd soaring-anomalous-transport
uv sync --all-extras        # creates .venv, installs the package + [dev] and [docs] extras
```

Commands are run with `uv run …` (or by activating `.venv`):

```bash
uv run soaring-para --help    # paraglider downloader
uv run soaring-delta --help   # hang-glider downloader
```

## With venv + pip

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev,docs]"
```

## Dependency groups

| Group      | Purpose |
|-----------|---------|
| _core_    | `curl_cffi`, `pyyaml`, `pandas`, `tqdm` — data acquisition |
| `dev`     | `pytest`, `ruff`, `mypy`, `interrogate` — development and quality |
| `docs`    | `mkdocs-material`, `mkdocstrings`, … — this documentation |
| `analysis`| `matplotlib` — preprocessing diagnostics figures |

## Quick check

```bash
uv run ruff check .
uv run pytest
uv run mkdocs serve     # documentation at http://127.0.0.1:8000
```
