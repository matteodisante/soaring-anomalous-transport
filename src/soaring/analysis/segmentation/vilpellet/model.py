"""Inference in the fitted three-state model: emission lookup, Viterbi, majority vote.

Nothing here estimates anything.  The parameters were fitted once by the author, on a
different archive, and this module only runs the maximum-a-posteriori state path under
them.  That is a deliberate restriction: refitting would produce a different model, and
the point of this package is to reproduce the segmentation that already exists.

The recursion keeps the source implementation's per-step renormalisation of the Viterbi
scores.  It cannot change which path is selected, because the same positive factor
divides every state at one step, and it is what stops the product of 20,000 transition
probabilities from underflowing to zero.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from .config import FEATURE_VALUES, HMMParameters


def emission_indices(observations: np.ndarray) -> np.ndarray:
    """Map each binary observation triple to its row in :data:`FEATURE_VALUES`.

    Args:
        observations: An ``(n, 3)`` integer array of zeros and ones.

    Returns:
        An ``(n,)`` array of indices into the emission vectors.

    Raises:
        ValueError: If the array is misshaped, or holds a triple outside the eight
            enumerated values.  The reference implementation returns index ``0`` in
            that case; with indicators that are zero or one by construction the branch
            is unreachable, so refusing it changes no decoded label and turns a silent
            mislabelling into a visible failure.
    """
    values = np.asarray(observations)
    if values.ndim != 2 or values.shape[1] != FEATURE_VALUES.shape[1]:
        raise ValueError("Vilpellet observations must be an (n, 3) array")
    matches = (values[:, None, :] == FEATURE_VALUES[None, :, :]).all(axis=2)
    if not matches.any(axis=1).all():
        raise ValueError("Vilpellet observations must be binary triples")
    return matches.argmax(axis=1)


def emission_probabilities(
    observations: np.ndarray, parameters: HMMParameters
) -> np.ndarray:
    """The ``(n, 3)`` array of ``b_i(y_k)``, state ``i`` across the columns."""
    return parameters.emission[:, emission_indices(observations)].T


def viterbi(observations: np.ndarray, parameters: HMMParameters) -> np.ndarray:
    """Decode the most probable component sequence under the fitted parameters.

    Args:
        observations: An ``(n, 3)`` binary observation array.
        parameters: The fitted model.

    Returns:
        An ``(n,)`` integer array of component indices.

    Raises:
        ValueError: If the observation array is empty.
    """
    emissions = emission_probabilities(observations, parameters)
    n_steps, n_states = emissions.shape
    if n_steps == 0:
        raise ValueError("Vilpellet decoding needs at least one observation")
    transition = parameters.transition
    backpointer = np.zeros((n_steps, n_states), dtype=np.int64)
    score = parameters.initial * emissions[0]
    for step in range(1, n_steps):
        # `argmax` resolves a tie toward the lowest predecessor index, which is what
        # the source's strict `>` comparison does as it scans states in order.
        extended = score[:, None] * transition
        best_previous = extended.argmax(axis=0)
        backpointer[step] = best_previous
        score = extended[best_previous, np.arange(n_states)] * emissions[step]
        total = score.sum()
        if total > 0.0:
            score = score / total
    path = np.zeros(n_steps, dtype=np.int64)
    path[-1] = int(score.argmax())
    for step in range(n_steps - 2, -1, -1):
        path[step] = backpointer[step + 1, path[step + 1]]
    return path


def rolling_majority(labels: pd.Series, window_fixes: int) -> pd.Series:
    """Replace each label by the most frequent label of a centred window.

    Ties are resolved toward the label that sorts first, as in the source.  The vote
    removes the isolated one- and two-fix flips a per-fix decoder produces at a phase
    boundary; it is a smoother, and it can also erase a genuinely short phase.

    Args:
        labels: The decoded per-fix labels.
        window_fixes: Window width in fixes.

    Returns:
        The smoothed labels, indexed like ``labels``.
    """
    codes, uniques = pd.factorize(labels, sort=True)
    counts = np.column_stack(
        [
            pd.Series((codes == code).astype(np.int8), index=labels.index)
            .rolling(window=window_fixes, center=True, min_periods=1)
            .sum()
            .to_numpy()
            for code in range(len(uniques))
        ]
    )
    smoothed = pd.Series(uniques[counts.argmax(axis=1)], index=labels.index)
    return smoothed.astype(labels.dtype)
