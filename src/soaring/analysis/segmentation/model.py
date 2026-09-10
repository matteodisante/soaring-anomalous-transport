"""Fitting, decoding, and persistence for the adopted Gaussian HMM."""

from __future__ import annotations

import copy
import json
import pickle
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import numpy as np

from .config import SegmentationConfig, SequencePrior
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
    mapping_method: str = "unmapped"
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
            "mapping_method": self.mapping_method,
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
        config_data["sequence_prior"] = SequencePrior(
            **config_data.get("sequence_prior", {})
        )
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
            mapping_method=str(metadata.get("mapping_method", "legacy-unspecified")),
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

    The pipeline supplies whole valid blocks, never arbitrary prefixes. A block that
    exceeds either configured cap is refused rather than split, because a synthetic
    sequence boundary would remove a real HMM transition. No observations from two
    flight segments are ever made adjacent for HMM transition estimation.
    """
    selected: list[np.ndarray] = []
    lengths: list[int] = []
    used = 0
    for sequence in sequences:
        checked = _check_observations(sequence)
        if len(checked) > config.max_sequence_observations:
            raise ValueError("a fitting sequence exceeds max_sequence_observations")
        if used + len(checked) > config.max_fit_observations:
            break
        selected.append(checked)
        lengths.append(len(checked))
        used += len(checked)
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
    raw, lengths = concatenate_sequences(sequences, config)
    if len(raw) < len(config.states):
        raise ValueError("HMM fitting needs at least one observation per state")
    scaler = Standardizer.fit(raw)
    values = scaler.transform(raw)
    if config.n_jobs == 1 or config.n_restarts == 1:
        results = [
            _fit_restart(restart, values, lengths, config)
            for restart in range(config.n_restarts)
        ]
    else:
        from joblib import Parallel, delayed, parallel_config

        worker_count = min(config.n_jobs, config.n_restarts)
        with parallel_config(backend="loky", inner_max_num_threads=1):
            results = Parallel(
                n_jobs=worker_count,
                max_nbytes="16M",
                mmap_mode="r",
            )(
                delayed(_fit_restart)(restart, values, lengths, config)
                for restart in range(config.n_restarts)
            )

    restart_scores = [result[2] for result in results]
    restart_converged = [result[3] for result in results]
    successful = [result for result in results if result[1] is not None]
    if successful:
        selected_restart, best_model, score, _ = max(
            successful,
            key=lambda result: -np.inf if result[2] is None else result[2],
        )
        assert score is not None
        best_score = score
    else:
        best_model = None
        best_score = -np.inf
        selected_restart = -1
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


def _fit_restart(
    restart: int,
    values: np.ndarray,
    lengths: list[int],
    config: SegmentationConfig,
) -> tuple[int, Any | None, float | None, bool]:
    """Fit one deterministic initialization, suitable for a worker process."""
    from hmmlearn.hmm import GaussianHMM

    try:
        model = GaussianHMM(
            n_components=len(config.states),
            covariance_type=config.covariance_type,
            min_covar=config.min_covar,
            random_state=config.random_seed + restart,
            n_iter=config.n_iter,
            tol=config.tol,
            implementation=config.implementation,
        )
        model.fit(values, lengths=lengths)
        score = float(model.score(values, lengths=lengths))
    except (FloatingPointError, ValueError, np.linalg.LinAlgError):
        return restart, None, None, False
    return restart, model, score, bool(model.monitor_.converged)


def heuristic_state_mapping(artifact: HMMArtifact) -> dict[int, str]:
    """Return an interpretable but explicitly provisional component permutation.

    Gaussian-HMM component numbers carry no semantics.  Before manual annotations are
    available, this assignment makes diagnostic plots readable by matching three
    simple flight-mechanics signatures to the standardized emission means: fast and
    straight for ``transition``, turning without strong lift for ``search``, and
    positive vertical speed with turning for ``climb``.  It is not ground truth and is
    replaced by the annotation-based Hungarian assignment for final reporting.
    """
    means = np.asarray(artifact.model.means_, dtype=float)
    if means.shape != (len(artifact.config.states), len(FEATURE_COLUMNS)):
        raise ValueError("HMM emission means do not match the phase feature schema")
    vertical, horizontal, turning, coherence = means.T
    climb_component = int(np.argmax(vertical))
    remaining = np.asarray(
        [component for component in range(len(means)) if component != climb_component]
    )
    straight_score = horizontal - turning - 0.5 * coherence
    transition_component = int(remaining[np.argmax(straight_score[remaining])])
    search_component = int(
        next(
            component
            for component in range(len(means))
            if component not in {climb_component, transition_component}
        )
    )
    return {
        transition_component: "transition",
        search_component: "search",
        climb_component: "climb",
    }


def effective_transition_matrix(artifact: HMMArtifact) -> np.ndarray:
    """Return the soft, semantic sequence policy without mutating the fitted model.

    Persistence is increased toward exp(-decision_step / mean_dwell_s) only when
    that exceeds learned persistence. Conditional exit probabilities are blended
    with a cyclic preference; all exceptions remain possible when weight > 0.
    Applied after state naming, so raw component permutations cannot reverse it.
    """
    learned = np.asarray(artifact.model.transmat_, dtype=float)
    prior = artifact.config.sequence_prior
    if prior.weight == 0 or not artifact.state_mapping:
        return learned.copy()
    inverse = {name: component for component, name in artifact.state_mapping.items()}
    states = artifact.config.states
    if set(inverse) != set(states) or set(inverse.values()) != set(range(len(states))):
        raise ValueError(
            "sequence prior requires a complete one-to-one semantic mapping"
        )
    result = np.zeros_like(learned)
    persistence = np.exp(-artifact.config.decision_step_s / prior.mean_dwell_s)
    for index, name in enumerate(states):
        component = inverse[name]
        forward = inverse[states[(index + 1) % len(states)]]
        exits = [j for j in range(len(states)) if j != component]
        weights = learned[component, exits].copy()
        weights = weights / weights.sum() if weights.sum() else np.full(len(exits), 0.5)
        target = np.array(
            [
                prior.forward_probability
                if j == forward
                else 1 - prior.forward_probability
                for j in exits
            ]
        )
        weights = (1 - prior.weight) * weights + prior.weight * target
        stay = learned[component, component]
        stay += prior.weight * max(0.0, persistence - stay)
        # An absorbing fitted component must not make the soft policy deterministic.
        stay = min(stay, 1 - np.finfo(float).eps)
        result[component, component] = stay
        result[component, exits] = (1 - stay) * weights
    return result


def decode(
    artifact: HMMArtifact, observations: np.ndarray
) -> tuple[np.ndarray, np.ndarray]:
    """Return Viterbi components and smoothed posterior state probabilities."""
    values = artifact.scaler.transform(observations)
    # A shallow model copy keeps shared archive workers and the cached viewer
    # artifact immutable; both Viterbi and posterior use the same transition matrix.
    model = copy.copy(artifact.model)
    model.implementation = "log"
    model.transmat_ = effective_transition_matrix(artifact)
    states = model.predict(values)
    probabilities = model.predict_proba(values)
    return np.asarray(states, dtype=int), np.asarray(probabilities, dtype=float)


def semantic_states(artifact: HMMArtifact, raw_states: np.ndarray) -> np.ndarray:
    """Map numerical HMM components to the three calibrated flight-phase names."""
    if set(artifact.state_mapping) != set(range(len(artifact.config.states))):
        raise ValueError("HMM artifact has no complete semantic state mapping")
    return np.asarray(
        [artifact.state_mapping[int(state)] for state in raw_states], dtype=object
    )
