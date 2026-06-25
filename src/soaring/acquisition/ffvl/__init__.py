"""Download of `.igc` tracks from the Coupe Fédérale de Distance (CFD) of the FFVL.

Four-step pipeline, exposed by the ``soaring-ffvl`` CLI:

1. :mod:`~.catalog_xml` -- downloads and parses the XML export for each season;
2. :mod:`~.download` -- downloads `.igc` files in a resumable manner;
3. :mod:`~.catalog` -- builds the CSV catalog (metadata + local paths);
4. :mod:`~.cli` -- command-line interface.

The *source of truth* is always the pair [filenames] + [archived XMLs]: the CSV catalog
is a convenient derivative, regenerable at any time.
"""
