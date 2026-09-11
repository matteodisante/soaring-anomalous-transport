"""Finite-window diagnostics without assuming a homogeneous stochastic process."""

from __future__ import annotations

import math
import unicodedata

import numpy as np


def declared_task_class(task: str) -> str:
    """Map explicit scored route types to open, closed or unknown.

    Out-and-return and quadrilateral courses are closed as well as triangles.
    Hike-and-fly labels alone do not identify route geometry.
    """
    normalized = "".join(
        char
        for char in unicodedata.normalize("NFKD", str(task).lower())
        if not unicodedata.combining(char)
    ).strip()
    if normalized.startswith("triangle") or normalized in {
        "quadrilatere",
        "aller-retour",
    }:
        return "closed"
    if normalized in {"dist libre", "dist 1 pt", "dist 2 pts", "dist 3 pts"}:
        return "open"
    return "unknown"


def log_slope(lags: np.ndarray, values: np.ndarray) -> tuple[float, float]:
    """Return a descriptive log--log slope and its RMS residual in decades."""
    good = np.isfinite(values) & (values > 0) & (lags > 0)
    if good.sum() < 4:
        return np.nan, np.nan
    x, y = np.log10(lags[good]), np.log10(values[good])
    slope, intercept = np.polyfit(x, y, 1)
    return float(slope), float(np.sqrt(np.mean((y - slope * x - intercept) ** 2)))


def covariance_geometry(vectors: np.ndarray) -> dict:
    """Centered spatial PCA; angle is counterclockwise from east, modulo 180 degrees.

    An orthogonal rotation decorrelates the two coordinates at this scale. It does
    not remove temporal dependence, imply independence, or change vector lengths.
    """
    values = np.asarray(vectors, dtype=float)
    values = values[np.isfinite(values).all(axis=1)]
    if len(values) < 8:
        return {}
    mean = values.mean(axis=0)
    centered = values - mean
    covariance = centered.T @ centered / len(values)
    eigenvalues, eigenvectors = np.linalg.eigh(covariance)
    if eigenvalues[0] <= 0:
        return {}
    principal = eigenvectors[:, -1]
    return {
        "mean": mean,
        "covariance": covariance,
        "eigenvalues": eigenvalues,
        "eigenvectors": eigenvectors,
        "ratio": float(eigenvalues[-1] / eigenvalues[0]),
        "angle_deg": float(np.degrees(np.arctan2(principal[1], principal[0])) % 180),
        "correlation": float(
            covariance[0, 1] / np.sqrt(covariance[0, 0] * covariance[1, 1])
        ),
    }


def mardia_excess(vectors: np.ndarray) -> float:
    """Centered bivariate Mardia kurtosis minus its Gaussian population value 8.

    This is a pooled-distribution diagnostic. Heterogeneity of flight means or
    covariance matrices can produce excess even if each conditional law is Gaussian.
    """
    values = np.asarray(vectors, dtype=float)
    values = values[np.isfinite(values).all(axis=1)]
    geometry = covariance_geometry(values)
    if not geometry:
        return np.nan
    centered = values - geometry["mean"]
    inverse = np.linalg.inv(geometry["covariance"])
    mahalanobis = np.einsum("ni,ij,nj->n", centered, inverse, centered)
    return float(np.mean(mahalanobis**2) - 8.0)


def levy_walk_spectrum(q: np.ndarray, gamma: float) -> np.ndarray:
    """Asymptotic moment exponent for the standard finite-speed Levy walk, 1<gamma<2.

    Flight-time density is proportional to t**(-1-gamma); this formula is a model
    benchmark, not an estimator of the empirical data's process class.
    """
    if not 1 < gamma < 2:
        raise ValueError("the superdiffusive branch requires 1 < gamma < 2")
    q = np.asarray(q, dtype=float)
    return np.where(q <= gamma, q / gamma, q + 1 - gamma)


def empirical_quantiles(values, probabilities, weights=None):
    """Generalized inverse of a finite weighted empirical CDF, without interpolation.

    The same rows and weights define every requested percentile. Positive weights
    need not sum to one. Jointly finite rows are required so coordinate contrasts
    use identical observations; invalid data are rejected rather than reweighted.
    """
    values = np.asarray(values, dtype=float)
    probabilities = np.asarray(probabilities, dtype=float)
    if values.ndim == 1:
        values = values[:, None]
    if values.ndim != 2 or not len(values) or not np.isfinite(values).all():
        raise ValueError("Quantiles require nonempty finite observation rows")
    if (
        probabilities.ndim != 1
        or not np.isfinite(probabilities).all()
        or np.any((probabilities <= 0) | (probabilities > 1))
    ):
        raise ValueError("Quantile probabilities must belong to (0, 1]")
    weights = (
        np.ones(len(values)) if weights is None else np.asarray(weights, dtype=float)
    )
    if (
        weights.shape != (len(values),)
        or not np.isfinite(weights).all()
        or np.any(weights <= 0)
    ):
        raise ValueError("One positive finite weight per observation is required")
    result = np.empty((values.shape[1], len(probabilities)))
    for coordinate in range(values.shape[1]):
        order = np.argsort(values[:, coordinate], kind="stable")
        ordered_weights = weights[order]
        # The generalized inverse jumps at an atom: ordinary cumulative round-off
        # can put p=1/2 on the wrong side of a whole flight's probability mass.
        # Locate candidates quickly, then resolve each boundary with accurate sums.
        total = math.fsum(ordered_weights)
        cumulative = np.cumsum(ordered_weights)
        targets = probabilities * total
        indexes = np.minimum(
            np.searchsorted(cumulative, targets, side="left"), len(order) - 1
        )
        for p, (index, target) in enumerate(zip(indexes, targets, strict=True)):
            while (
                index < len(order) - 1
                and math.fsum(ordered_weights[: index + 1]) < target
            ):
                index += 1
            while index > 0 and math.fsum(ordered_weights[:index]) >= target:
                index -= 1
            result[coordinate, p] = values[order[index], coordinate]

    return result
