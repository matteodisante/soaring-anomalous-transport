"""Configuration of the satellite crop, read from ``configs/satellite.yaml``."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml

CONFIG_PATH = Path(__file__).resolve().parents[4] / "configs" / "satellite.yaml"


@dataclass(frozen=True)
class Cell:
    """One Thermal-planes cell: the Lambert-93 square ``[ix, ix+1) x [iy, iy+1)``.

    Attributes:
        ix: Column index on the cell lattice.
        iy: Row index on the cell lattice.
        terrain: Terrain band the viewer assigned to the cell.
    """

    ix: int
    iy: int
    terrain: str

    @property
    def name(self) -> str:
        """Stable key used in output files, e.g. ``c089_1375``."""
        return f"c{self.ix:03d}_{self.iy:04d}"


@dataclass(frozen=True)
class WindowConfig:
    """Extent of the crop around each cell centre, in Lambert-93 metres.

    Attributes:
        half_size_m: Half side of the square window (5000 gives 10 x 10 km).
        north_margin_m: Extra extent to the north, for cloud parallax.
        side_margin_m: Extra extent to the east and west.
    """

    half_size_m: float
    north_margin_m: float
    side_margin_m: float


@dataclass(frozen=True)
class Config:
    """Complete crop configuration.

    Attributes:
        output_root: Directory receiving the cropped files.
        min_free_gib: Free space below which writing stops.
        local_timezone: IANA zone of ``local_hours``.
        local_hours: Kept local hours, start inclusive and end exclusive.
        window: Window extent (see :class:`WindowConfig`).
        cell_size_m: Side of a lattice cell in metres.
        cells: The cells to crop.
    """

    output_root: Path
    min_free_gib: float
    local_timezone: str
    local_hours: tuple[int, int]
    window: WindowConfig
    cell_size_m: float
    cells: tuple[Cell, ...]

    def centre(self, cell: Cell) -> tuple[float, float]:
        """Lambert-93 centre of ``cell``."""
        return (
            (cell.ix + 0.5) * self.cell_size_m,
            (cell.iy + 0.5) * self.cell_size_m,
        )


def load_config(path: Path = CONFIG_PATH) -> Config:
    """Read and validate the YAML configuration at ``path``."""
    raw = yaml.safe_load(Path(path).read_text())
    start, end = raw["local_hours"]
    if not 0 <= start < end <= 24:
        raise ValueError(f"local_hours must satisfy 0 <= start < end <= 24: {raw}")
    cells = tuple(
        Cell(int(c["ix"]), int(c["iy"]), str(c["terrain"])) for c in raw["cells"]
    )
    if len({c.name for c in cells}) != len(cells):
        raise ValueError("Duplicate cells in the satellite configuration")
    return Config(
        output_root=Path(raw["output_root"]),
        min_free_gib=float(raw["min_free_gib"]),
        local_timezone=str(raw["local_timezone"]),
        local_hours=(int(start), int(end)),
        window=WindowConfig(**{k: float(v) for k, v in raw["window"].items()}),
        cell_size_m=float(raw["cell_size_m"]),
        cells=cells,
    )
