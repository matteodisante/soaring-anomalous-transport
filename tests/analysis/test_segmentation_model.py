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
    model.n_features = 4
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


@pytest.mark.parametrize("allow_skip", [False, True])
def test_sequence_policy_is_invariant_to_raw_component_permutation(config, allow_skip):
    from soaring.analysis.segmentation.config import SequencePrior
    from soaring.analysis.segmentation.model import effective_transition_matrix

    artifact = _policy_artifact(
        replace(
            config,
            sequence_prior=SequencePrior(
                weight=0.75,
                allow_search_skip=allow_skip,
                search_mean_dwell_s=20.0 if allow_skip else None,
            ),
        )
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


def test_optional_search_has_no_long_persistence_floor(config):
    from soaring.analysis.segmentation.config import SequencePrior
    from soaring.analysis.segmentation.model import effective_transition_matrix

    artifact = _policy_artifact(config)
    artifact.model.transmat_[1] = [0.025, 0.95, 0.025]
    old = replace(
        artifact, config=replace(config, sequence_prior=SequencePrior(weight=0.75))
    )
    new = replace(
        artifact,
        config=replace(
            config,
            sequence_prior=SequencePrior(
                weight=0.75,
                forward_probability=0.95,
                allow_search_skip=True,
                search_mean_dwell_s=20.0,
            ),
        ),
    )
    before = effective_transition_matrix(old)
    after = effective_transition_matrix(new)
    assert after[0, 2] > before[0, 2]  # direct transit -> climb easier
    assert after[1, 1] < before[1, 1]  # search need not last like a climb
    assert after[2, 0] > after[2, 1]  # climb preferentially exits to transit
    assert (after > 0).all()
    np.testing.assert_allclose(after.sum(axis=1), 1.0)


def test_coherence_marginal_is_unconditional_and_does_not_mutate_fitted_model(config):
    from scipy.special import softmax
    from scipy.stats import multivariate_normal

    artifact = _policy_artifact(replace(config, marginalize_turn_coherence=True))
    covariance = artifact.model.covars_.copy()
    covariance[:, 0, 3] = covariance[:, 3, 0] = 0.7
    artifact.model.covars_ = covariance
    values = np.array([[2.0, 0.1, 0.2, -0.9]])
    states, posterior = decode(artifact, values)
    changed = values.copy()
    changed[:, 3] = 10000.0
    other_states, other_posterior = decode(artifact, changed)
    np.testing.assert_array_equal(states, other_states)
    np.testing.assert_allclose(posterior, other_posterior)
    # The marginal uses the principal covariance, not the Schur complement for
    # conditioning on coherence, despite correlation with a retained feature.
    expected = softmax(
        [
            multivariate_normal.logpdf(values[0, :3], mean=mean[:3], cov=cov[:3, :3])
            for mean, cov in zip(artifact.model.means_, covariance, strict=True)
        ]
    )
    np.testing.assert_allclose(posterior[0], expected)
    assert artifact.model.means_.shape == (3, 4)
    np.testing.assert_array_equal(artifact.model.covars_, covariance)


def test_reported_flight_climb_is_not_rejected_for_imperfect_turn_coherence(config):
    import json
    from pathlib import Path

    from soaring.analysis.segmentation.config import SequencePrior
    from soaring.analysis.segmentation.model import semantic_states

    fixture = json.loads(
        (Path(__file__).parents[1] / "fixtures/segmentation_20311250.json").read_text()
    )
    artifact = _policy_artifact(config)
    artifact.scaler = Standardizer(
        np.array(fixture["scaler_mean"]), np.array(fixture["scaler_scale"])
    )
    artifact.model.means_ = np.array(fixture["means"])
    artifact.model.covars_ = np.array(fixture["covariances"])
    artifact.model.startprob_ = np.array(fixture["startprob"])
    artifact.model.transmat_ = np.array(fixture["transmat"])
    artifact.state_mapping = {int(k): v for k, v in fixture["mapping"].items()}
    observations = np.array(fixture["observations"])
    times = np.array(fixture["t"])
    policy = SequencePrior(
        weight=0.75,
        forward_probability=0.95,
        allow_search_skip=True,
        search_mean_dwell_s=20.0,
    )
    artifact.config = replace(config, sequence_prior=policy)
    unchanged_emissions, _ = decode(artifact, observations)
    before = semantic_states(artifact, unchanged_emissions)
    assert (before[(times >= 1640) & (times <= 1770)] == "search").all()
    artifact.config = replace(artifact.config, marginalize_turn_coherence=True)
    states, probabilities = decode(artifact, observations)
    after = semantic_states(artifact, states)
    assert (after[(times >= 1640) & (times <= 1810)] == "climb").all()
    assert (after[times >= 1820] == "transition").all()
    np.testing.assert_allclose(probabilities.sum(axis=1), 1.0)


def test_current_decoder_policy_survives_artifact_round_trip(tmp_path, config):
    from soaring.analysis.segmentation.config import SequencePrior

    config = replace(
        config,
        marginalize_turn_coherence=True,
        sequence_prior=SequencePrior(
            weight=0.75,
            allow_search_skip=True,
            search_mean_dwell_s=20.0,
            forward_probability=0.95,
        ),
    )
    artifact = _policy_artifact(config)
    artifact.save(tmp_path)
    restored = HMMArtifact.load(tmp_path)
    assert restored.config == config
    observations = np.zeros((20, 4))
    observations[10:, 0] = 6.0
    expected, probabilities = decode(artifact, observations)
    actual, restored_probabilities = decode(restored, observations)
    np.testing.assert_array_equal(actual, expected)
    np.testing.assert_allclose(restored_probabilities, probabilities)
    assert restored.model.means_.shape == (3, 4)


@pytest.mark.parametrize(
    ("history", "score", "expected_success", "expected_converged"),
    [
        ([1.0, 2.0], 2.0, True, False),
        ([2.0, 1.0], 1.0, True, False),
        ([1.0, 1.00001], 1.00001, True, True),
        ([1.0, 2.0], float("nan"), False, False),
    ],
)
def test_restart_distinguishes_stopping_from_convergence(
    monkeypatch, config, history, score, expected_success, expected_converged
):
    from types import SimpleNamespace

    import hmmlearn.hmm

    from soaring.analysis.segmentation.model import _fit_restart

    class Model:
        def __init__(self, **kwargs):
            self.monitor_ = SimpleNamespace(history=history, converged=True)

        def fit(self, *args, **kwargs):
            return self

        def score(self, *args, **kwargs):
            return score

    monkeypatch.setattr(hmmlearn.hmm, "GaussianHMM", Model)
    _, fitted, _, converged = _fit_restart(0, np.ones((5, 4)), [5], config)
    assert (fitted is not None) is expected_success
    assert converged is expected_converged
