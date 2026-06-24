# Fonte dati: la CFD della FFVL

I dati provengono dalla **Coupe Fédérale de Distance (CFD)** della Fédération Française de
Vol Libre. Per ogni stagione esiste una pagina-lista dei voli; **il punto chiave** è che
ogni lista ha un **export XML completo** che restituisce *tutti* i voli in un'unica risposta.

## I link, per stagione

Per la stagione che inizia nell'anno `Y` (es. `Y = 1999` → stagione 1999-2000):

| Risorsa | URL |
|---------|-----|
| Pagina-lista (umana) | `https://parapente.ffvl.fr/cfd/liste/{Y}` |
| **Export XML** (usato dal downloader) | `https://parapente.ffvl.fr/cfd/liste/{Y}?xml=1` |

L'elenco completo dei link e dei conteggi, stagione per stagione, è in
[`data/seasons_index.csv`](https://github.com/matteodisante/soaring-anomalous-transport)
(rigenerato da `build-catalog`). I costruttori di URL sono in `soaring.acquisition.ffvl.seasons`
(vedi [Reference API](../reference.md)).

## Cosa contiene l'XML

Ogni volo è un elemento `<flight>` con tutti i metadati come attributi, **incluso il link
diretto al file `.igc`**. Estratto reale (stagione 1999-2000):

```xml
<flight id="20150770"
        flight_link="https://parapente.ffvl.fr/cfd/liste/vol/20150770"
        date="2000-00-00" pilot="ETIENNE GRASSART" flight_type="triangle"
        distance="35.59" takeOff="Les Ilettes" landing="Orbassy"
        igc_tracklog="53180"
        igc_tracklog_link="https://parapente.ffvl.fr/sites/.../…-53180.igc" .../>
```

Grazie a questo non serve mai visitare le pagine dei singoli voli: tutto è nell'XML.
Il parsing è in `soaring.acquisition.ffvl.catalog_xml`.

## Cloudflare

Il sito è protetto da Cloudflare: una richiesta HTTP normale riceve `403` con una pagina di
challenge. Usiamo [`curl_cffi`](https://github.com/lexiforest/curl_cffi) che imita il
fingerprint TLS di un browser reale e supera il filtro. La logica (con retry, backoff e
rigenerazione della sessione) è in `soaring.acquisition.ffvl.http`.

!!! note "Cortesia"
    Scarichiamo con un numero limitato di richieste parallele e una pausa con jitter tra le
    richieste, per non sovraccaricare i server FFVL. I dati sono pubblici e usati per ricerca
    accademica.
