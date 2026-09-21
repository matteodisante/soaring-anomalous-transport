"""Balanced factorial summaries of estimated cell exponents, not flight-level ANOVA.

The last three axes are altitude (4), circuit (open, closed), and equipment
(beginners, experts). Leading axes, including paired bootstrap draws, are retained.
"""

from itertools import combinations

import numpy as np

from soaring.analysis.observables.conditional_transport import BANDS, strata

TASKS = ("open", "closed")
EQUIPMENT_KEYS = ("beginners", "experts")
COMPONENTS = {
    "altitude": (0,),
    "circuit": (1,),
    "equipment": (2,),
    "altitude_circuit": (0, 1),
    "altitude_equipment": (0, 2),
    "circuit_equipment": (1, 2),
    "three_way": (0, 1, 2),
}


def cell_masks(frame):
    """Return the disjoint 4 x 2 x 2 intersections in tensor flattening order."""
    groups = strata(frame)
    return {
        f"alt{i}_{task}_{equipment}": groups[f"alt{i}"]
        & groups[task]
        & groups[equipment]
        for i in range(len(BANDS))
        for task in TASKS
        for equipment in EQUIPMENT_KEYS
    }


def decompose(h):
    """Project onto mutually orthogonal factorial subspaces with equal cell weights.

    Orthogonality is algebraic; estimated components need not be statistically
    independent. The saturated reconstruction has no separate error estimate.
    """
    h = np.asarray(h, dtype=float)
    if h.shape[-3:] != (4, 2, 2) or not np.isfinite(h).all():
        raise ValueError("Expected finite exponents with final shape (4, 2, 2)")
    offset = h.ndim - 3
    mean = h.mean(axis=(-3, -2, -1), keepdims=True)
    pieces = {(): mean}
    result = {"mean": np.broadcast_to(mean, h.shape)}
    for name, factors in COMPONENTS.items():
        axes = tuple(offset + i for i in range(3) if i not in factors)
        term = h.mean(axis=axes, keepdims=True) if axes else h.copy()
        for size in range(len(factors)):
            for subset in combinations(factors, size):
                term = term - pieces[subset]
        pieces[factors] = term
        result[name] = np.broadcast_to(term, h.shape)
    result["additive"] = sum(
        result[k] for k in ("mean", "altitude", "circuit", "equipment")
    )
    result["residual"] = h - result["additive"]
    return result


def diagnostics(h):
    """Describe observed cell variation; return undefined shares for a constant grid."""
    parts = decompose(h)
    total = np.sum((h - parts["mean"]) ** 2, axis=(-3, -2, -1))
    residual = np.sum(parts["residual"] ** 2, axis=(-3, -2, -1))

    def fraction(numerator):
        return np.divide(
            numerator, total, out=np.full_like(total, np.nan), where=total > 0
        )

    return {
        "r2_add": 1 - fraction(residual),
        "residual_rms": np.sqrt(residual / 16),
        "components": {
            key: {
                "share": fraction(np.sum(parts[key] ** 2, axis=(-3, -2, -1))),
                "rms": np.sqrt(np.mean(parts[key] ** 2, axis=(-3, -2, -1))),
            }
            for key in COMPONENTS
        },
    }


def contrasts(h):
    """Return simple contrasts and a declared Plains-minus-High-mountains family."""
    circuit = h[..., :, 0, :] - h[..., :, 1, :]
    equipment = h[..., :, :, 1] - h[..., :, :, 0]
    attenuation = circuit[..., 0, :] - circuit[..., 3, :]
    return {
        "circuit": circuit,
        "equipment": equipment,
        "endpoints": np.concatenate(
            [attenuation, (attenuation[..., 1] - attenuation[..., 0])[..., None]],
            axis=-1,
        ),
    }


def bootstrap_summary(samples, coverage=0.9):
    """Summarize paired draws; row zero is observed and never a resample.

    Simultaneous intervals use the bootstrap quantile of the largest absolute
    centred deviation divided by each statistic's fixed bootstrap SE. The family
    is every entry after the leading draw axis. These are approximate, conditional
    on the resampling design; no nested studentization or coverage claim is made.
    """
    samples = np.asarray(samples, dtype=float)
    if samples.ndim < 1 or len(samples) < 3 or not np.isfinite(samples).all():
        raise ValueError("Expected an observed row and at least two finite draws")
    if not 0 < coverage < 1:
        raise ValueError("Coverage must lie strictly between zero and one")
    point, draws = samples[0], samples[1:]
    se = draws.std(axis=0, ddof=1)
    delta = draws - point
    if np.any((se == 0) & np.any(delta != 0, axis=0)):
        raise ValueError("Constant bootstrap samples differ from the observed value")
    standardized = np.divide(delta, se, out=np.zeros_like(delta), where=se > 0)
    maximum = np.max(np.abs(standardized).reshape(len(draws), -1), axis=1)
    critical = np.quantile(maximum, coverage)
    low, high = np.quantile(draws, [(1 - coverage) / 2, (1 + coverage) / 2], axis=0)
    return {
        "point": point,
        "low": low,
        "high": high,
        "se": se,
        "sim_low": point - critical * se,
        "sim_high": point + critical * se,
        "critical": critical,
        "family_size": int(point.size),
    }
