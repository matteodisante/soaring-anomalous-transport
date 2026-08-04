"""Trajectories whose transport is known, for validating the estimators against.

Every estimator in this package returns a number on any input, and most of them return a
plausible number on an input that violates their assumptions. The only way to know what an
estimator measures is to run it on a process whose answer is known in advance, so these
generators come before the observables rather than after them.

Four processes, chosen for what each one tests:

``brownian``
    the null. An estimator that does not return :math:`\\alpha = 1` here is wrong, and
    everything else it says is uninterpretable.
``fractional_brownian``
    correlated Gaussian motion at a set exponent. The competing hypothesis to a Lévy walk,
    and the process against which the detrending bias is measured, since it has no jumps
    to confuse the question.
``levy_walk``
    ballistic flights of heavy-tailed duration. The hypothesis: it is the process whose
    moment spectrum bends and whose front is ballistic.
``persistent_walk``
    a correlated random walk with a set persistence time, per flight. Superposed over a
    spread of persistence times it manufactures a power law out of ordinary diffusion,
    which is the confound the chapter has to rule out.

All of them return positions on a uniform grid, in metres, shaped ``(n, 2)``, so that a
synthetic flight is fed to an estimator through exactly the code path a real one takes.
"""

from __future__ import annotations

import numpy as np

__all__ = [
    "brownian",
    "fractional_brownian",
    "levy_walk",
    "persistent_walk",
    "with_drift",
]


def brownian(n: int, dt: float = 1.0, *, speed: float = 10.0, seed: int | None = None):
    """An uncorrelated 2-D random walk, ``MSD = (speed^2) t``.

    Args:
        n: Number of samples.
        dt: Grid step, in seconds.
        speed: Root-mean-square step speed, in m/s.
        seed: Seed for the generator.

    Returns:
        ``(n, 2)`` positions in metres, starting at the origin.
    """
    rng = np.random.default_rng(seed)
    steps = rng.normal(0.0, speed * np.sqrt(dt) / np.sqrt(2.0), size=(n - 1, 2))
    return np.vstack([np.zeros((1, 2)), np.cumsum(steps, axis=0)])


def fractional_brownian(
    n: int, hurst: float, dt: float = 1.0, *, scale: float = 10.0, seed: int | None = None
):
    """Two independent fractional Brownian motions, ``MSD ~ t^(2H)``.

    Built by the Davies--Harte circulant embedding, which is exact rather than
    approximate: an estimator validated against an approximate fBm is validated against
    the approximation. When the embedding is not non-negative definite -- possible for
    ``H`` near 1 at short series -- it falls back to the Hosking recursion.

    Args:
        n: Number of samples.
        hurst: The Hurst exponent, ``0 < H < 1``; the MSD exponent is ``2H``.
        dt: Grid step, in seconds.
        scale: Displacement scale at unit lag, in metres.
        seed: Seed for the generator.

    Returns:
        ``(n, 2)`` positions in metres, starting at the origin.
    """
    rng = np.random.default_rng(seed)
    increments = np.column_stack([_fgn(n - 1, hurst, rng) for _ in range(2)])
    increments *= scale * dt**hurst / np.sqrt(2.0)
    return np.vstack([np.zeros((1, 2)), np.cumsum(increments, axis=0)])


def _fgn(n: int, hurst: float, rng: np.random.Generator) -> np.ndarray:
    """One realisation of unit-variance fractional Gaussian noise, length ``n``."""
    k = np.arange(n + 1, dtype=float)
    gamma = 0.5 * (
        np.abs(k - 1) ** (2 * hurst) - 2 * k ** (2 * hurst) + (k + 1) ** (2 * hurst)
    )
    # Circulant embedding: the eigenvalues must be non-negative for the square root to
    # exist. They are, for every H in (0,1) with this autocovariance, but a short series
    # at H close to 1 can produce a small negative from rounding.
    circulant = np.concatenate([gamma, gamma[-2:0:-1]])
    eigenvalues = np.fft.fft(circulant).real
    if eigenvalues.min() < -1e-10:
        return _fgn_hosking(n, hurst, rng)
    eigenvalues = np.clip(eigenvalues, 0.0, None)
    size = eigenvalues.size
    noise = rng.normal(size=size) + 1j * rng.normal(size=size)
    # The real part of the complex Gaussian carries half the variance, so the
    # normalisation is 1/size and not 1/(2 size): with the latter the sequence comes
    # out at unit variance halved, which leaves the correlation structure exact and
    # every displacement scale wrong by sqrt(2).
    return np.fft.fft(np.sqrt(eigenvalues / size) * noise).real[:n]


def _fgn_hosking(n: int, hurst: float, rng: np.random.Generator) -> np.ndarray:
    """Exact but ``O(n^2)`` fallback, used only when the embedding is not usable."""
    def autocov(k):
        return 0.5 * (
            abs(k - 1) ** (2 * hurst) - 2 * abs(k) ** (2 * hurst) + (k + 1) ** (2 * hurst)
        )

    series = np.zeros(n)
    series[0] = rng.normal()
    phi = np.zeros(n)
    variance = 1.0
    for i in range(1, n):
        phi[i - 1] = autocov(i)
        for j in range(i - 1):
            phi[i - 1] -= phi[j] * autocov(i - j - 1)
        phi[i - 1] /= variance
        for j in range(i - 1):
            phi[j] -= phi[i - 1] * phi[i - j - 2]
        variance *= 1 - phi[i - 1] ** 2
        series[i] = np.sqrt(variance) * rng.normal() + phi[: i].dot(series[i - 1 :: -1][: i])
    return series


def levy_walk(
    n: int,
    alpha: float,
    dt: float = 1.0,
    *,
    speed: float = 12.0,
    min_duration: float = 5.0,
    seed: int | None = None,
):
    """Ballistic flights of Pareto-distributed duration, at constant speed.

    The walk moves at a fixed speed and reorients at renewal times drawn from
    ``P(T > t) ~ t^-alpha``; the coupling between how long a flight lasts and how far it
    goes is what makes it a *walk* rather than a *flight*, and what gives it a ballistic
    front. For ``1 < alpha < 2`` the MSD exponent is ``3 - alpha``.

    Args:
        n: Number of samples.
        alpha: Tail index of the flight-duration distribution.
        dt: Grid step, in seconds.
        speed: Constant speed, in m/s.
        min_duration: Lower cut-off of the Pareto, in seconds.
        seed: Seed for the generator.

    Returns:
        ``(n, 2)`` positions in metres, starting at the origin.
    """
    rng = np.random.default_rng(seed)
    total = n * dt
    durations, elapsed = [], 0.0
    while elapsed < total + min_duration:
        step = min_duration * rng.pareto(alpha) + min_duration
        durations.append(step)
        elapsed += step
    angles = rng.uniform(0.0, 2 * np.pi, size=len(durations))

    time = np.arange(n, dtype=float) * dt
    edges = np.concatenate([[0.0], np.cumsum(durations)])
    # Position at the start of each flight, then the ballistic remainder within it.
    legs = speed * np.column_stack([np.cos(angles), np.sin(angles)]) * np.diff(edges)[:, None]
    corners = np.vstack([np.zeros((1, 2)), np.cumsum(legs, axis=0)])
    index = np.clip(np.searchsorted(edges, time, side="right") - 1, 0, len(durations) - 1)
    remainder = (time - edges[index])[:, None]
    heading = np.column_stack([np.cos(angles), np.sin(angles)])[index]
    return corners[index] + speed * remainder * heading


def persistent_walk(
    n: int,
    tau: float,
    dt: float = 1.0,
    *,
    speed: float = 12.0,
    seed: int | None = None,
):
    """A correlated random walk: constant speed, heading decorrelating over ``tau``.

    Ballistic below ``tau`` and diffusive above it. One of these is not anomalous; a
    population of them with a broad spread of ``tau`` produces an ensemble MSD that is a
    power law over the whole range of ``tau``, which is the confound of
    ``03_diagnostica.md`` §3.1 and the reason this generator exists.

    Args:
        n: Number of samples.
        tau: Heading correlation time, in seconds.
        dt: Grid step, in seconds.
        speed: Constant speed, in m/s.
        seed: Seed for the generator.

    Returns:
        ``(n, 2)`` positions in metres, starting at the origin.
    """
    rng = np.random.default_rng(seed)
    # Ornstein-Uhlenbeck on the heading angle: <cos(theta(t)-theta(0))> = exp(-t/tau).
    diffusion = np.sqrt(2.0 * dt / tau)
    turns = rng.normal(0.0, diffusion, size=n - 1)
    heading = np.concatenate([[rng.uniform(0, 2 * np.pi)], np.cumsum(turns)])
    velocity = speed * np.column_stack([np.cos(heading), np.sin(heading)])
    return np.vstack([np.zeros((1, 2)), np.cumsum(velocity[:-1] * dt, axis=0)])


def with_drift(positions: np.ndarray, velocity, dt: float = 1.0) -> np.ndarray:
    """Add a constant drift to a trajectory.

    The operation the whole frame discussion is about: a drift adds ``|v|^2 t^2`` to the
    mean square displacement, so a process of any exponent becomes ballistic at long lags
    once it is superposed.

    Args:
        positions: ``(n, 2)`` positions.
        velocity: ``(vx, vy)`` in m/s.
        dt: Grid step, in seconds.

    Returns:
        ``(n, 2)`` positions with the drift added.
    """
    time = np.arange(len(positions), dtype=float)[:, None] * dt
    return positions + np.asarray(velocity, dtype=float)[None, :] * time
