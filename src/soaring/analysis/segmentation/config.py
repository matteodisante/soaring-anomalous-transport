"""Typed configuration for the continuous flight-phase HMM."""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from pathlib import Path

from .labels import STATES

DEFAULT_SEGMENTATION_CONFIG_PATH = (
    Path(__file__).resolve().parents[4] / "configs" / "segmentation.yaml"
)


@dataclass(frozen=True)
class SplitFractions:
    """Fractions assigned at flight, rather than point, level."""

    train: float
    validation: float
    test: float

    def __post_init__(self) -> None:
        """Check that the three independent flight-level splits form a partition."""
        if not all(
            isfinite(value) for value in (self.train, self.validation, self.test)
        ):
            raise ValueError("segmentation split fractions must be finite")
        if any(value <= 0.0 for value in (self.train, self.validation, self.test)):
            raise ValueError("every segmentation split fraction must be positive")
        if abs(self.train + self.validation + self.test - 1.0) > 1e-9:
            raise ValueError("segmentation split fractions must sum to one")


@dataclass(frozen=True)
class SegmentationConfig:
    """All fixed choices of the Gaussian-HMM segmentation protocol."""

    decision_step_s: float
    feature_window_s: float
    max_native_dt_s: float
    min_horizontal_speed_mps: float
    states: tuple[str, ...]
    covariance_type: str
    random_seed: int
    n_restarts: int
    n_iter: int
    tol: float
    min_covar: float
    split: SplitFractions
    max_fit_flights: int
    max_fit_observations: int
    max_sequence_observations: int
    bootstrap_replicates: int

    def __post_init__(self) -> None:
        """Check the invariants that make the HMM configuration interpretable."""
        continuous_values = (
            self.decision_step_s,
            self.feature_window_s,
            self.max_native_dt_s,
            self.min_horizontal_speed_mps,
            self.tol,
            self.min_covar,
        )
        if not all(isfinite(value) for value in continuous_values):
            raise ValueError("segmentation numeric parameters must be finite")
        if self.decision_step_s <= 0.0 or self.feature_window_s <= 0.0:
            raise ValueError("segmentation time scales must be positive")
        if self.feature_window_s < 2.0 * self.decision_step_s:
            raise ValueError("feature window must contain at least two decision steps")
        if self.max_native_dt_s <= 0.0 or self.min_horizontal_speed_mps <= 0.0:
            raise ValueError("segmentation cadence and speed limits must be positive")
        if self.tol <= 0.0 or self.min_covar <= 0.0:
            raise ValueError("HMM tolerance and covariance floor must be positive")
        if self.covariance_type != "full":
            raise ValueError("the adopted segmentation model uses full covariance")
        if self.states != STATES:
            raise ValueError(
                "segmentation states must be transition, search, climb in that order"
            )
        integer_limits = (
            self.n_restarts,
            self.n_iter,
            self.max_fit_flights,
            self.max_fit_observations,
            self.max_sequence_observations,
            self.bootstrap_replicates,
        )
        if min(integer_limits) < 1:
            raise ValueError("HMM iteration and fitting caps must be positive")
        if self.random_seed < 0:
            raise ValueError("segmentation random seed must be non-negative")


def load_segmentation_config(path: str | Path | None = None) -> SegmentationConfig:
    """Load the repository's segmentation protocol from YAML.

    Args:
        path: Optional replacement configuration file.

    Returns:
        A validated immutable configuration.
    """
    import yaml

    source = Path(path) if path is not None else DEFAULT_SEGMENTATION_CONFIG_PATH
    raw = yaml.safe_load(source.read_text(encoding="utf-8"))
    return SegmentationConfig(
        decision_step_s=float(raw["decision_step_s"]),
        feature_window_s=float(raw["feature_window_s"]),
        max_native_dt_s=float(raw["max_native_dt_s"]),
        min_horizontal_speed_mps=float(raw["min_horizontal_speed_mps"]),
        states=tuple(raw["states"]),
        covariance_type=str(raw["covariance_type"]),
        random_seed=int(raw["random_seed"]),
        n_restarts=int(raw["n_restarts"]),
        n_iter=int(raw["n_iter"]),
        tol=float(raw["tol"]),
        min_covar=float(raw["min_covar"]),
        split=SplitFractions(**raw["split"]),
        max_fit_flights=int(raw["max_fit_flights"]),
        max_fit_observations=int(raw["max_fit_observations"]),
        max_sequence_observations=int(raw["max_sequence_observations"]),
        bootstrap_replicates=int(raw["bootstrap_replicates"]),
    )
