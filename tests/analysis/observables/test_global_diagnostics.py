import numpy as np
import pytest

from soaring.analysis.observables.global_diagnostics import (
    covariance_geometry,
    declared_task_class,
    levy_walk_spectrum,
    mardia_excess,
)


@pytest.mark.parametrize(
    "name", ["triangle", "triangle FAI", "Quadrilatère", "Aller-Retour"]
)
def test_all_declared_closed_tasks(name):
    assert declared_task_class(name) == "closed"


@pytest.mark.parametrize(
    "name", ["Dist libre", "Dist 1 pt", "Dist 2 pts", "Dist 3 pts"]
)
def test_declared_open_tasks(name):
    assert declared_task_class(name) == "open"


@pytest.mark.parametrize("name", ["Marche et Vol", "unknown", "nan", ""])
def test_unidentified_geometry_is_not_assigned_open(name):
    assert declared_task_class(name) == "unknown"


def test_centering_and_rotation_invariance():
    rng = np.random.default_rng(47)
    x = rng.normal(size=(150_000, 2)) @ np.array([[3, 1], [0, 0.5]]) + [30, -70]
    geo = covariance_geometry(x)
    rotated = x @ geo["eigenvectors"]
    assert np.allclose(np.linalg.norm(x, axis=1), np.linalg.norm(rotated, axis=1))
    assert abs(covariance_geometry(rotated)["correlation"]) < 1e-12
    assert abs(mardia_excess(x)) < 0.1
    assert mardia_excess(rotated) == pytest.approx(mardia_excess(x), abs=1e-10)
    assert mardia_excess(x - [30, -70]) == pytest.approx(mardia_excess(x), abs=1e-10)


def test_levy_walk_spectrum_matches_ballistic_tail_and_msd():
    gamma = 1.6
    assert np.allclose(
        levy_walk_spectrum(np.array([0, gamma, 2, 4]), gamma), [0, 1, 1.4, 3.4]
    )
    with pytest.raises(ValueError):
        levy_walk_spectrum(np.array([2]), 2.1)


def test_weighted_quantiles_are_an_inverse_cdf_not_a_mean_of_quantiles():
    from soaring.analysis.observables.global_diagnostics import empirical_quantiles

    values = np.array([[0.0, 10.0], [4.0, 20.0], [100.0, 30.0]])
    actual = empirical_quantiles(values, [0.25, 0.5, 0.75, 0.9], [1.0, 2.0, 1.0])
    np.testing.assert_array_equal(actual, [[0, 4, 4, 100], [10, 20, 20, 30]])
    # Splitting an atom into identical observations of equal combined mass changes nothing.
    repeated = empirical_quantiles(values[[0, 1, 1, 2]], [0.25, 0.5, 0.75, 0.9])
    np.testing.assert_array_equal(actual, repeated)


def test_equal_flight_probability_mass_survives_unequal_origin_counts():
    from soaring.analysis.observables.global_diagnostics import empirical_quantiles

    # Ordinary cumsum formerly moved the exact 1/2 mass boundary past the slow flight.
    values = np.r_[np.ones(1001), np.full(3001, 3.0)]
    weights = np.r_[np.full(1001, 1 / 1001), np.full(3001, 1 / 3001)]
    np.testing.assert_array_equal(
        empirical_quantiles(values, [0.25, 0.5, 0.75], weights), [[1, 1, 3]]
    )
