from __future__ import annotations

from dataclasses import replace

import numpy as np
import pytest

from soaring.analysis.segmentation.config import SegmentationConfig, SplitFractions
from soaring.analysis.segmentation.model import (
    HMMArtifact,
    Standardizer,
    concatenate_sequences,
    decode,
    fit_gaussian_hmm,
    heuristic_state_mapping,
)


@pytest.fixture
def config() -> SegmentationConfig:
    return SegmentationConfig(
        decision_step_s=10.0,
        feature_window_s=30.0,
        max_native_dt_s=10.0,
        min_horizontal_speed_mps=1.0,
        states=("transition", "search", "climb"),
        covariance_type="full",
        random_seed=3,
        n_restarts=1,
        n_iter=10,
        tol=1e-3,
        min_covar=1e-3,
        split=SplitFractions(train=0.7, validation=0.15, test=0.15),
        max_fit_flights=10,
        max_fit_observations=7,
        max_sequence_observations=3,
        bootstrap_replicates=10,
    )


def test_sequence_concatenation_retains_all_boundaries(
    config: SegmentationConfig,
) -> None:
    first = np.ones((3, 4))
    second = np.full((3, 4), 2.0)
    values, lengths = concatenate_sequences([first, second], config)

    assert values.shape == (6, 4)
    assert lengths == [3, 3]


def test_standardizer_rejects_constant_training_features() -> None:
    with pytest.raises(ValueError, match="zero"):
        Standardizer.fit(np.ones((3, 4)))


def test_hmm_artifact_round_trip_and_decode(
    tmp_path, config: SegmentationConfig
) -> None:
    pytest.importorskip("hmmlearn")
    generator = np.random.default_rng(3)
    sequences = [
        np.vstack(
            [
                generator.normal(-2.0, 0.2, size=(12, 4)),
                generator.normal(0.0, 0.2, size=(12, 4)),
                generator.normal(2.0, 0.2, size=(12, 4)),
            ]
        )
        for _ in range(3)
    ]
    fit_config = replace(config, max_fit_observations=108, max_sequence_observations=36)
    artifact = fit_gaussian_hmm(sequences, fit_config)
    artifact.state_mapping = {0: "transition", 1: "search", 2: "climb"}
    artifact.save(tmp_path)
    restored = HMMArtifact.load(tmp_path)
    states, probabilities = decode(restored, sequences[0])

    assert states.shape == (36,)
    assert probabilities.shape == (36, 3)
    np.testing.assert_allclose(probabilities.sum(axis=1), 1.0)
    assert restored.n_fit_observations == 108
    assert restored.n_fit_sequences == 3
    assert len(restored.restart_log_likelihoods) == fit_config.n_restarts


def test_provisional_mapping_matches_flight_mechanics_signatures(
    config: SegmentationConfig,
) -> None:
    class EmissionModel:
        means_ = np.asarray(
            [
                [0.0, 2.0, -1.0, -1.0],  # fast and straight
                [-1.0, -0.5, 1.5, 1.5],  # turning without lift
                [2.0, -0.5, 1.0, 1.0],  # climbing turn
            ]
        )

    artifact = HMMArtifact(
        model=EmissionModel(),
        scaler=Standardizer(mean=np.zeros(4), scale=np.ones(4)),
        state_mapping={},
        config=config,
        fit_log_likelihood=0.0,
        selected_restart=0,
    )

    assert heuristic_state_mapping(artifact) == {
        0: "transition",
        1: "search",
        2: "climb",
    }


def _policy_artifact(config):
    from hmmlearn.hmm import GaussianHMM

    model = GaussianHMM(n_components=3, covariance_type="full", init_params="")
    model.startprob_ = np.full(3, 1 / 3)
    model.transmat_ = np.full((3, 3), 0.3)
    np.fill_diagonal(model.transmat_, 0.4)
    model.means_ = np.array(
        [[0.0, 0.0, 0.0, 0.0], [3.0, 0.0, 0.0, 0.0], [6.0, 0.0, 0.0, 0.0]]
    )
    model.covars_ = np.array([np.eye(4)] * 3)
    return HMMArtifact(
        model=model,
        scaler=Standardizer(np.zeros(4), np.ones(4)),
        state_mapping={0: "transition", 1: "search", 2: "climb"},
        config=config,
        fit_log_likelihood=0.0,
        selected_restart=0,
    )


def test_soft_cycle_reduces_ambiguous_fragments_but_allows_supported_exceptions(config):
    from soaring.analysis.segmentation.config import SequencePrior
    from soaring.analysis.segmentation.model import effective_transition_matrix

    artifact = _policy_artifact(config)
    observations = np.zeros((61, 4))
    observations[:, 0] = (
        [6.0] * 12 + [3.5] + [6.0] * 12 + [0.0] * 12 + [3.0] * 12 + [6.0] * 12
    )
    original = artifact.model.transmat_.copy()
    baseline, _ = decode(artifact, observations)
    policy = replace(
        artifact, config=replace(config, sequence_prior=SequencePrior(weight=0.75))
    )
    states, posterior = decode(policy, observations)
    assert baseline[12] == 1
    assert states[12] == 2
    assert np.sum(np.diff(states) != 0) < np.sum(np.diff(baseline) != 0)
    np.testing.assert_allclose(posterior.sum(axis=1), 1.0)
    np.testing.assert_array_equal(artifact.model.transmat_, original)
    matrix = effective_transition_matrix(policy)
    assert (matrix > 0).all()
    np.testing.assert_allclose(matrix.sum(axis=1), 1.0)
    for state in range(3):
        assert matrix[state, state] > original[state, state]
        assert matrix[state, (state + 1) % 3] > matrix[state, (state + 2) % 3]
    # A sustained climb -> search exception remains admissible.
    exception = np.zeros((40, 4))
    exception[:20, 0] = 6.0
    exception[20:, 0] = 3.0
    exception_states, _ = decode(policy, exception)
    assert exception_states[10] == 2 and exception_states[30] == 1


def test_sequence_policy_is_invariant_to_raw_component_permutation(config):
    from soaring.analysis.segmentation.config import SequencePrior
    from soaring.analysis.segmentation.model import effective_transition_matrix

    artifact = _policy_artifact(
        replace(config, sequence_prior=SequencePrior(weight=0.75))
    )
    matrix = effective_transition_matrix(artifact)
    permutation = np.array([2, 0, 1])
    permuted = _policy_artifact(artifact.config)
    permuted.state_mapping = {
        i: artifact.state_mapping[int(j)] for i, j in enumerate(permutation)
    }
    permuted.model.transmat_ = artifact.model.transmat_[
        np.ix_(permutation, permutation)
    ]
    np.testing.assert_allclose(
        effective_transition_matrix(permuted), matrix[np.ix_(permutation, permutation)]
    )


def test_legacy_artifact_has_no_implicit_sequence_policy(tmp_path, config):
    import json

    from soaring.analysis.segmentation.model import effective_transition_matrix

    artifact = _policy_artifact(config)
    artifact.save(tmp_path)
    path = tmp_path / "metadata.json"
    metadata = json.loads(path.read_text())
    del metadata["config"]["sequence_prior"]
    path.write_text(json.dumps(metadata))
    restored = HMMArtifact.load(tmp_path)
    assert restored.config.sequence_prior.weight == 0
    np.testing.assert_array_equal(
        effective_transition_matrix(restored), artifact.model.transmat_
    )
