# Setting up

The project uses [uv](https://docs.astral.sh/uv/) for environment and dependency
management, reproducible from `uv.lock`.

```bash
cd soaring-anomalous-transport
uv sync        # creates .venv; installs core + dev + analysis by default
```

`uv sync` and `uv run` always include the `dev` and `analysis` dependency groups (see
`[tool.uv] default-groups` in `pyproject.toml`). That's on purpose: no flag to remember,
and no risk of a plain `uv run <tool>` silently dropping them because an earlier
invocation happened to pass something different. Add `--extra docs` only when working on
this documentation site:

```bash
uv sync --extra docs
```

Commands run through `uv run …`, or after activating `.venv`:

```bash
uv run soaring-para --help    # paraglider downloader
uv run soaring-delta --help   # hang-glider downloader
```

## Quick check

```bash
uv run ruff check .
uv run pytest
uv run mkdocs serve     # documentation at http://127.0.0.1:8000
```
