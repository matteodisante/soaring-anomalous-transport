# Installation

The project uses [uv](https://docs.astral.sh/uv/) for environment and dependency management
(reproducible via `uv.lock`). Without uv, `venv` + `pip` can be used instead.

## With uv (recommended)

```bash
cd soaring-anomalous-transport
uv sync        # creates .venv; installs core + dev + analysis (see below) by default
```

`uv sync`/`uv run` always include the `dev` and `analysis` dependency groups (see
`[tool.uv] default-groups` in `pyproject.toml`) — no flags to remember, and no risk of a
plain `uv run <tool>` silently uninstalling them because a previous invocation happened
to pass different flags. Add `--extra docs` (or `--all-extras`) only when working on this
documentation site:

```bash
uv sync --extra docs
```

Commands are run with `uv run …` (or by activating `.venv`):

```bash
uv run soaring-para --help    # paraglider downloader
uv run soaring-delta --help   # hang-glider downloader
```

## With venv + pip

`dev` and `analysis` are [dependency groups](https://peps.python.org/pep-0735/), not pip
extras, so `pip install -e ".[dev]"` will not find them (only `docs` is a real extra).
With a recent enough pip (≥25.1, PEP 735 support):

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[docs]"
pip install --group dev --group analysis
```

Otherwise, install the two groups' packages directly (see `[dependency-groups]` in
`pyproject.toml` for the current list).

## Dependency groups

| Group      | Kind             | Purpose |
|-----------|------------------|---------|
| _core_    | always installed | `curl_cffi`, `pyyaml`, `pandas`, `tqdm` — data acquisition |
| `dev`     | uv default group | `pytest`, `ruff`, `mypy`, `interrogate` — development and quality |
| `analysis`| uv default group | `matplotlib`, `scipy`, `pyarrow` — diagnostics figures, PSD, scan cache |
| `docs`    | pip extra, on-demand | `mkdocs-material`, `mkdocstrings`, … — this documentation |

## Quick check

```bash
uv run ruff check .
uv run pytest
uv run mkdocs serve     # documentation at http://127.0.0.1:8000
```
