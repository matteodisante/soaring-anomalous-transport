"""Optimising the recursion must preserve paths, including zero mass and ties."""

import numpy as np
import pytest

from soaring.analysis.segmentation.vilpellet.config import HMMParameters
from soaring.analysis.segmentation.vilpellet.model import (
    _viterbi_general,
    emission_probabilities,
    viterbi,
)


@pytest.mark.parametrize("seed", range(10))
def test_optimized_recursion_matches_general_on_random_fitted_models(seed):
    rng = np.random.default_rng(seed)
    parameters = HMMParameters(
        emission=rng.dirichlet(np.ones(8), size=3),
        transition=rng.dirichlet(np.full(3, 0.2), size=3),
        initial=rng.dirichlet(np.ones(3)),
    )
    observations = rng.integers(0, 2, size=(4000, 3))
    expected = _viterbi_general(
        emission_probabilities(observations, parameters), parameters
    )
    np.testing.assert_array_equal(viterbi(observations, parameters), expected)


@pytest.mark.parametrize("zero_mass", [False, True])
def test_optimized_recursion_preserves_lowest_state_tie_break(zero_mass):
    emission = np.ones((3, 8)) / 8
    if zero_mass:
        emission[:, 0] = 0
        emission[:, 1:] = 1 / 7
    parameters = HMMParameters(
        emission=emission,
        transition=np.ones((3, 3)) / 3,
        initial=np.ones(3) / 3,
    )
    observations = np.zeros((100, 3), dtype=int)
    expected = _viterbi_general(
        emission_probabilities(observations, parameters), parameters
    )
    np.testing.assert_array_equal(viterbi(observations, parameters), expected)
    np.testing.assert_array_equal(expected, np.zeros(100, dtype=int))
