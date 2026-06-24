# Installazione

Il progetto usa [uv](https://docs.astral.sh/uv/) per ambiente e dipendenze (riproducibili
tramite `uv.lock`). In assenza di uv si può usare `venv` + `pip`.

## Con uv (consigliato)

```bash
cd soaring-anomalous-transport
uv sync --all-extras        # crea .venv, installa il pacchetto + extra [dev] e [docs]
```

I comandi si lanciano con `uv run …` (oppure attivando `.venv`):

```bash
uv run soaring-ffvl --help
```

## Con venv + pip

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev,docs]"
```

## Gruppi di dipendenze

| Gruppo | A cosa serve |
|--------|--------------|
| _core_ | `curl_cffi`, `pyyaml`, `pandas`, `tqdm` — l'acquisizione dati |
| `dev`  | `pytest`, `ruff`, `mypy`, `interrogate` — sviluppo e qualità |
| `docs` | `mkdocs-material`, `mkdocstrings`, … — questa documentazione |

## Verifica rapida

```bash
uv run ruff check .
uv run pytest
uv run mkdocs serve     # documentazione su http://127.0.0.1:8000
```
