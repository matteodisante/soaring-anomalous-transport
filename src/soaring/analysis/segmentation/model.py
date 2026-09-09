"""Fitting, decoding, and persistence for the adopted Gaussian HMM."""

from __future__ import annotations

import json
import pickle
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import numpy as np

from .config import SegmentationConfig
from .features import FEATURE_COLUMNS


@dataclass(frozen=True)
class Standardizer:
    """Training-only affine feature scaling stored beside the fitted model."""

    mean: np.ndarray
    scale: np.ndarray

    @classmethod
    def fit(cls, values: np.ndarray) -> Standardizer:
        """Estimate means and standard deviations from training observations only."""
        array = _check_observations(values)
        scale = np.std(array, axis=0)
        if np.any(scale <= np.finfo(float).eps):
            raise ValueError("a segmentation feature has zero training variance")
        return cls(mean=np.mean(array, axis=0), scale=scale)

    def transform(self, values: np.ndarray) -> np.ndarray:
        """Apply the fitted, leakage-free standardization."""
        array = _check_observations(values)
        if array.shape[1] != self.mean.size:
            raise ValueError("feature count differs from the fitted standardizer")
        return (array - self.mean) / self.scale


@dataclass
class HMMArtifact:
    """One reproducible discipline-specific phase model and its semantic mapping."""

    model: Any
    scaler: Standardizer
    state_mapping: dict[int, str]
    config: SegmentationConfig
    fit_log_likelihood: float
    selected_restart: int
    restart_log_likelihoods: list[float | None] = field(default_factory=list)
    restart_converged: list[bool] = field(default_factory=list)
    n_fit_observations: int = 0
    n_fit_sequences: int = 0

    def save(self, directory: str | Path) -> None:
        """Persist model, scaler, mapping, configuration, and fit provenance."""
        target = Path(directory)
        target.mkdir(parents=True, exist_ok=True)
        with (target / "gaussian_hmm.pkl").open("wb") as stream:
            pickle.dump(self.model, stream, protocol=pickle.HIGHEST_PROTOCOL)
        metadata = {
            "feature_columns": FEATURE_COLUMNS,
            "state_mapping": {
                str(key): value for key, value in self.state_mapping.items()
            },
            "scaler_mean": self.scaler.mean.tolist(),
            "scaler_scale": self.scaler.scale.tolist(),
            "fit_log_likelihood": self.fit_log_likelihood,
            "selected_restart": self.selected_restart,
            "restart_log_likelihoods": self.restart_log_likelihoods,
            "restart_converged": self.restart_converged,
            "n_fit_observations": self.n_fit_observations,
            "n_fit_sequences": self.n_fit_sequences,
            "config": asdict(self.config),
        }
        (target / "metadata.json").write_text(
            json.dumps(metadata, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )

    @classmethod
    def load(cls, directory: str | Path) -> HMMArtifact:
        """Restore a model written by :meth:`save`."""
        target = Path(directory)
        with (target / "gaussian_hmm.pkl").open("rb") as stream:
            model = pickle.load(stream)
        metadata = json.loads((target / "metadata.json").read_text(encoding="utf-8"))
        config_data = metadata["config"].copy()
        split_data = config_data.pop("split")
        config_data["states"] = tuple(config_data["states"])
        from .config import SplitFractions

        config = SegmentationConfig(split=SplitFractions(**split_data), **config_data)
        if metadata["feature_columns"] != FEATURE_COLUMNS:
            raise ValueError("model artifact uses a different feature schema")
        return cls(
            model=model,
            scaler=Standardizer(
                mean=np.asarray(metadata["scaler_mean"], dtype=float),
                scale=np.asarray(metadata["scaler_scale"], dtype=float),
            ),
            state_mapping={
                int(key): value for key, value in metadata["state_mapping"].items()
            },
            config=config,
            fit_log_likelihood=float(metadata["fit_log_likelihood"]),
            selected_restart=int(metadata["selected_restart"]),
            restart_log_likelihoods=list(metadata.get("restart_log_likelihoods", [])),
            restart_converged=list(metadata.get("restart_converged", [])),
            n_fit_observations=int(metadata.get("n_fit_observations", 0)),
            n_fit_sequences=int(metadata.get("n_fit_sequences", 0)),
        )


def _check_observations(values: np.ndarray) -> np.ndarray:
    """Validate a finite two-dimensional observation matrix."""
    array = np.asarray(values, dtype=float)
    if array.ndim != 2 or array.shape[0] == 0:
        raise ValueError("HMM observations must be a non-empty two-dimensional array")
    if array.shape[1] != len(FEATURE_COLUMNS):
        raise ValueError("HMM observations do not match the phase feature schema")
    if not np.isfinite(array).all():
        raise ValueError("HMM observations must be finite")
    return array


def concatenate_sequences(
    sequences: list[np.ndarray], config: SegmentationConfig
) -> tuple[np.ndarray, list[int]]:
    """Bound fitting memory while preserving every retained sequence boundary.

    Long segments are split into contiguous sub-sequences, which is legitimate because
    their joins are declared sequence boundaries through ``lengths``.  No observations
    from two flight segments are ever made adjacent for HMM transition estimation.
    """
    selected: list[np.ndarray] = []
    lengths: list[int] = []
    used = 0
    for sequence in sequences:
        checked = _check_observations(sequence)
        for start in range(0, len(checked), config.max_sequence_observations):
            chunk = checked[start : start + config.max_sequence_observations]
            remaining = config.max_fit_observations - used
            if remaining <= 0:
                break
            if len(chunk) > remaining:
                break
            selected.append(chunk)
            lengths.append(len(chunk))
            used += len(chunk)
        if used >= config.max_fit_observations:
            break
    if not selected:
        raise ValueError("no finite sequences were available for HMM fitting")
    return np.concatenate(selected, axis=0), lengths


def fit_gaussian_hmm(
    sequences: list[np.ndarray], config: SegmentationConfig
) -> HMMArtifact:
    """Fit the best of deterministic Gaussian-HMM initializations.

    The state mapping is intentionally empty here: semantic labels are fitted only from
    the separately annotated training intervals after this unsupervised step.
    """
    from hmmlearn.hmm import GaussianHMM

    raw, lengths = concatenate_sequences(sequences, config)
    if len(raw) < len(config.states):
        raise ValueError("HMM fitting needs at least one observation per state")
    scaler = Standardizer.fit(raw)
    values = scaler.transform(raw)
    best_model: Any | None = None
    best_score = -np.inf
    selected_restart = -1
    restart_scores: list[float | None] = []
    restart_converged: list[bool] = []
    for restart in range(config.n_restarts):
        try:
            model = GaussianHMM(
                n_components=len(config.states),
                covariance_type=config.covariance_type,
                min_covar=config.min_covar,
                random_state=config.random_seed + restart,
                n_iter=config.n_iter,
                tol=config.tol,
                implementation="log",
            )
            model.fit(values, lengths=lengths)
            score = float(model.score(values, lengths=lengths))
        except (FloatingPointError, ValueError, np.linalg.LinAlgError):
            restart_scores.append(None)
            restart_converged.append(False)
            continue
        restart_scores.append(score)
        restart_converged.append(bool(model.monitor_.converged))
        if score > best_score:
            best_model, best_score, selected_restart = model, score, restart
    if best_model is None:
        raise RuntimeError("all Gaussian-HMM initializations failed")
    return HMMArtifact(
        model=best_model,
        scaler=scaler,
        state_mapping={},
        config=config,
        fit_log_likelihood=best_score,
        selected_restart=selected_restart,
        restart_log_likelihoods=restart_scores,
        restart_converged=restart_converged,
        n_fit_observations=len(raw),
        n_fit_sequences=len(lengths),
    )


def decode(
    artifact: HMMArtifact, observations: np.ndarray
) -> tuple[np.ndarray, np.ndarray]:
    """Return Viterbi components and smoothed posterior state probabilities."""
    values = artifact.scaler.transform(observations)
    states = artifact.model.predict(values)
    probabilities = artifact.model.predict_proba(values)
    return np.asarray(states, dtype=int), np.asarray(probabilities, dtype=float)


def semantic_states(artifact: HMMArtifact, raw_states: np.ndarray) -> np.ndarray:
    """Map numerical HMM components to the three calibrated flight-phase names."""
    if set(artifact.state_mapping) != set(range(len(artifact.config.states))):
        raise ValueError("HMM artifact has no complete semantic state mapping")
    return np.asarray(
        [artifact.state_mapping[int(state)] for state in raw_states], dtype=object
    )
