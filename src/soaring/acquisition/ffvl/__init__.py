"""Download of `.igc` tracks from the Coupe Fédérale de Distance (CFD) of the FFVL.

Handles both competition sites of the federation:

* **parapente.ffvl.fr** -- paraglider CFD (CLI: ``soaring-para``,
  config: ``configs/para_download.yaml``, env: ``SOARING_PARA_DATA_ROOT``);
* **delta.ffvl.fr** -- hang-glider CFD (CLI: ``soaring-delta``,
  config: ``configs/delta_download.yaml``, env: ``SOARING_DELTA_DATA_ROOT``).

Four-step pipeline, identical for both sources:

1. :mod:`~.catalog_xml` -- downloads and parses the XML export for each season;
2. :mod:`~.download` -- downloads `.igc` files in a resumable manner;
3. :mod:`~.catalog` -- builds the CSV catalog (metadata + local paths);
4. :mod:`~.cli` -- command-line interface (``soaring-para`` / ``soaring-delta``).

The *source of truth* is always the pair [filenames] + [archived XMLs]: the CSV catalog
is a convenient derivative, regenerable at any time.
"""
