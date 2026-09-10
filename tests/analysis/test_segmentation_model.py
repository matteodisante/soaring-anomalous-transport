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
