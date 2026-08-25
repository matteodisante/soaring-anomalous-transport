"""The two disciplines, and how to reach the tables written for each.

Every reporting script works on both archives and has to answer the same two questions:
what this discipline is called in a macro name and in a filename, and where its
processed tables are. Before this module each script answered them for itself, and the
answers had drifted: four different tuple shapes for the same mapping, and eight copies
of the same resolver differing only in which file they required.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..acquisition.ffvl.config import Config


@dataclass(frozen=True)
class Discipline:
    r"""One glider discipline: its names, its data root, and the colour it is drawn in.

    Attributes:
        name: The key the scripts index by, and what a message prints
            (``"paragliders"``, ``"hang gliders"``).
        slug: Filename component of the intermediate arrays (``"para"``, ``"hang"``).
        source: The value of the ``source`` column in the ``fixes`` schema
            (``"paraglider"``, ``"hangglider"``). Deliberately unlike ``name`` and
            unlike the on-disk directory: a new archive is a new value of this column,
            never a new column, so it is the one field the pipeline itself reads.
        tag: Macro-name component (``"Para"``, ``"Hang"``), as in
            ``\\StatMsdParaAlpha``.
        env: Environment variable overriding ``data_root`` for this discipline.
        config_attr: Name of the acquisition-config path constant
            (:data:`soaring.acquisition.ffvl.config.PARA_CONFIG_PATH` or ``DELTA_``).
        color: The colour every figure uses for this discipline, so that a panel added
            later cannot disagree with the ones already printed.
    """

    name: str
    slug: str
    source: str
    tag: str
    env: str
    config_attr: str
    color: str

    def config(self) -> Config:
        """The acquisition config for this discipline.

        Returns:
            The populated :class:`~soaring.acquisition.ffvl.config.Config`.

        Raises:
            FileNotFoundError: If the YAML config file is absent.
            KeyError: If it defines no ``data_root`` and the environment does not
                either.
        """
        from ..acquisition.ffvl import config as cfgmod

        return cfgmod.load_config(
            str(getattr(cfgmod, self.config_attr)), data_root_env=self.env
        )

    def derived_dir(self, require: str = "fixes.parquet") -> Path | None:
        """This discipline's ``derived/`` directory, or ``None`` if it is not reachable.

        Unreachable covers both the config being absent and the SSD not being mounted,
        and the callers treat them the same way: skip this discipline, report what was
        written for the other. A missing archive is the normal state of a fresh
        checkout, not an error.

        Args:
            require: The table that must exist for the directory to count as usable.
                ``fixes.parquet`` for a pass that streams the fix table,
                ``flights_meta.parquet`` for a reduction that needs the flight rows.

        Returns:
            The directory, or ``None``.
        """
        try:
            cfg = self.config()
        except (FileNotFoundError, KeyError):
            return None
        return cfg.derived_dir if (cfg.derived_dir / require).is_file() else None

    def catalog_path(self) -> Path | None:
        """The acquisition catalogue for this discipline, or ``None`` if unreachable.

        Returns:
            The path to ``catalog.csv``, which is metadata and can be wrong -- a coarse
            pre-filter and a provenance source, never the basis of a cut.
        """
        try:
            return self.config().catalog_path
        except (FileNotFoundError, KeyError):
            return None


PARAGLIDERS = Discipline(
    name="paragliders",
    slug="para",
    source="paraglider",
    tag="Para",
    env="SOARING_PARA_DATA_ROOT",
    config_attr="PARA_CONFIG_PATH",
    color="#3477a8",
)

HANG_GLIDERS = Discipline(
    name="hang gliders",
    slug="hang",
    source="hangglider",
    tag="Hang",
    env="SOARING_DELTA_DATA_ROOT",
    config_attr="DELTA_CONFIG_PATH",
    color="#b5482a",
)

#: Both disciplines, keyed by name. The iteration order is the order every table, figure
#: legend and console report presents them in, so it is fixed here, not per script.
DISCIPLINES: dict[str, Discipline] = {d.name: d for d in (PARAGLIDERS, HANG_GLIDERS)}
