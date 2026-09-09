"""Continuous Gaussian-HMM segmentation of soaring flight phases.

The package consumes the final, smoothed ``fixes.parquet`` table but does not alter it.
It constructs observations on a common 10-second decision grid, fits one model per
discipline, and writes phase labels to separate derived tables.  Scripts should use
:mod:`soaring.analysis.segmentation.pipeline` rather than individual helpers.
"""

from .config import SegmentationConfig, load_segmentation_config
from .features import FEATURE_COLUMNS, build_feature_frame
from .labels import STATES

__all__ = [
    "FEATURE_COLUMNS",
    "STATES",
    "SegmentationConfig",
    "build_feature_frame",
    "load_segmentation_config",
]
