# Scaricare i dati

Tutto passa dalla CLI `soaring-ffvl`. La destinazione dei dati è
`data_root` in [`configs/ffvl_download.yaml`](https://github.com/matteodisante/soaring-anomalous-transport)
— **deve puntare all'HDD esterno** (i dati sono ~65 GB).

```yaml
data_root: /Volumes/HDD_DISANTE/ffvl_cfd_igc
```

In alternativa, senza toccare il file: `export SOARING_FFVL_DATA_ROOT=/percorso/su/hdd`.

## I quattro comandi

Lancia i comandi con `uv run` (oppure attiva prima la venv: `source .venv/bin/activate`,
poi usa `soaring-ffvl ...` senza prefisso).

```bash
uv run soaring-ffvl fetch-xml --seasons all   # 1) archivia gli XML di stagione (veloce)
uv run soaring-ffvl download  --seasons all   # 2) scarica i .igc (lungo, resumibile)
uv run soaring-ffvl build-catalog             # 3) genera catalog.csv + seasons_index.csv
uv run soaring-ffvl status                    # 4) riepilogo per stagione
```

L'argomento `--seasons` accetta: `all`, un anno (`2014`), un intervallo (`2010-2015`) o un
elenco (`2010,2012,2015`).

### Opzioni utili di `download`

| Opzione | Effetto |
|---------|---------|
| `--workers N` | numero di download paralleli (default da config) |
| `--limit N`   | al massimo N file per stagione (per test) |
| `--dry-run`   | non scarica: conta soltanto cosa farebbe |

## Robustezza

!!! tip "È sicuro interrompere e riprendere"
    Il download è **resumibile**: i file già presenti vengono saltati. Puoi fermarlo
    (`Ctrl-C`) e rilanciarlo: riparte da dove era. Le scritture sono **atomiche**
    (file temporaneo `.part` poi rinominato), quindi un file con il nome definitivo è sempre
    completo e valido — importante su exfat, senza journaling.

- Ogni file scaricato è **validato** come IGC (record `A` iniziale + record `B`); risposte
  HTML/troncate vengono scartate e ritentate.
- I tentativi falliti finiscono in `logs/failures.csv` (per un retry mirato); il log
  completo è in `logs/download.log`.

## File `._*` su exfat (macOS)

Su HDD exfat, macOS crea un sidecar `._nome` accanto a ogni file scritto. Per evitarne
l'accumulo, `download` e `fetch-xml` lanciano automaticamente una pulizia (`dot_clean`) al
termine. Puoi anche pulire a mano in qualsiasi momento:

```bash
uv run soaring-ffvl clean
```

(Su sistemi non-macOS o senza `dot_clean` la pulizia viene semplicemente saltata.)

## Stima dei tempi e dello spazio

~186.000 file, ~342 KB medi → **~65 GB**. Con pochi worker, alcune ore (riprendibile, quindi
anche overnight). Lo spazio richiesto è ben sotto la capacità di un HDD da ~1 TB.

I dettagli implementativi sono in `soaring.acquisition.ffvl.download`
(vedi [Reference API](../reference.md)).
