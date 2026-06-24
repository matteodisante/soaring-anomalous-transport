"""Download dei tracciati `.igc` dalla Coupe Federale de Distance (CFD) della FFVL.

Pipeline in quattro passi, esposti dalla CLI ``soaring-ffvl``:

1. :mod:`~.catalog_xml` -- scarica e analizza l'export XML di ogni stagione;
2. :mod:`~.download` -- scarica i file `.igc` in modo resumibile;
3. :mod:`~.catalog` -- costruisce il catalogo CSV (metadati + path locali);
4. :mod:`~.cli` -- interfaccia a riga di comando.

La *fonte di verita'* resta sempre la coppia [nomi file] + [XML archiviati]: il
catalogo CSV e' un comodo derivato, rigenerabile in qualsiasi momento.
"""
