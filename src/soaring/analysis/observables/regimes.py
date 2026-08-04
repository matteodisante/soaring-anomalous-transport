"""How many scaling regimes a curve holds, and where they change.

The local slope of the ensemble MSD runs from 1.31 to 2.21 and back, so "how many regimes"
is not a rhetorical question on this archive: the answer is already known to be more than
one. What is not known is *how many more*, and that is a quantity to be fitted rather than
read off a panel.

Three things have to be right for the answer to mean anything.

**The number of breakpoints is itself estimated.** A continuous piecewise-linear fit in
log--log is run for each candidate ``K`` and the one that survives model selection is
reported, with the breakpoints located by exact dynamic programming rather than by
iterating from a guess -- the likelihood here has several optima and an iterative fit finds
whichever one it started nearest.

**The degrees of freedom are not the number of lags.** Every lag averages the same flights,
so the residuals are correlated and a curve of eighty points carries only a handful of
independent ones. :func:`effective_dof` measures that from the residual autocorrelation,
and it is what makes the difference between "two regimes" being a measurement and being an
artefact of counting.

**A curve with no breakpoint must be able to come back.** :func:`spurious_breakpoints`
runs the same selection on surrogates built from a single power law plus noise, and
returns how often it manufactures a break. Without that number, finding a knee establishes
nothing. The noise model has to come from the estimator's *sampling* error -- a clustered
bootstrap over flights -- and not from the residuals about a straight line: a genuinely
bent curve has a residual autocorrelation near one, so a surrogate built from it inherits
the curvature as noise and the test compares the curve against copies of its own
structure. On this archive that circular form returns a false-positive rate near one half
and a plausible sampling model returns one near a tenth, which is the difference between
a test and a tautology.

A crossover also has a width. :func:`smooth_crossover` fits a two-branch form with a free
sharpness, because a bend as wide as the branches it separates is not two regimes but one
curved function, and the two cases are indistinguishable to a piecewise fit.
"""

from __future__ import annotations

import numpy as np

__all__ = [
    "effective_dof",
    "local_slope",
    "piecewise_fit",
    "select_breakpoints",
    "smooth_crossover",
    "spurious_breakpoints",
]


def local_slope(t: np.ndarray, y: np.ndarray, half_decades: float = 0.15) -> np.ndarray:
    """``d log y / d log t`` by least squares over a window of ``+-half_decades``."""
    t = np.asarray(t, dtype=float)
    y = np.asarray(y, dtype=float)
    out = np.full(t.size, np.nan)
    for i in range(t.size):
        window = (
            (t >= t[i] / 10**half_decades)
            & (t <= t[i] * 10**half_decades)
            & np.isfinite(y)
            & (y > 0)
        )
        if window.sum() < 3:
            continue
        out[i] = np.polyfit(np.log10(t[window]), np.log10(y[window]), 1)[0]
    return out


def effective_dof(t: np.ndarray, y: np.ndarray) -> float:
    """Independent points a curve carries, from the lag-1 autocorrelation of its residuals.

    A curve of eighty lags is not eighty measurements: every lag is an average over the
    same flights, so the residuals about any fit are correlated and the information is a
    fraction of the point count. Using the point count instead is how a fit acquires
    confidence it has not earned, and it is the single most common way a scaling exponent
    is quoted an order of magnitude too tightly.

    The estimate is the usual first-order correction, ``n (1 - r) / (1 + r)`` with ``r``
    the lag-1 residual autocorrelation, floored at 2.
    """
    t = np.asarray(t, dtype=float)
    y = np.asarray(y, dtype=float)
    good = np.isfinite(y) & (y > 0) & (t > 0)
    if good.sum() < 4:
        return float(good.sum())
    fit = np.polyfit(np.log10(t[good]), np.log10(y[good]), 1)
    residual = np.log10(y[good]) - np.polyval(fit, np.log10(t[good]))
    if residual.std() == 0:
        return float(good.sum())
    r = float(np.corrcoef(residual[:-1], residual[1:])[0, 1])
    r = min(max(r, -0.99), 0.99)
    return float(max(2.0, good.sum() * (1.0 - r) / (1.0 + r)))


def piecewise_fit(x: np.ndarray, y: np.ndarray, breaks: np.ndarray):
    """Continuous piecewise-linear least squares with the breakpoints given.

    Continuity is imposed by construction rather than by a penalty: the basis is
    ``1, x, (x - b_1)_+, ...``, so every fit in the family joins at its knots.

    Returns:
        ``(coefficients, rss, predict)`` -- the fitted coefficients, the residual sum of
        squares, and a callable that evaluates the fit.
    """
    x = np.asarray(x, dtype=float)
    columns = [np.ones_like(x), x] + [np.clip(x - b, 0.0, None) for b in np.atleast_1d(breaks)]
    design = np.column_stack(columns)
    coefficients, *_ = np.linalg.lstsq(design, y, rcond=None)
    residual = y - design @ coefficients

    def predict(query):
        query = np.asarray(query, dtype=float)
        basis = [np.ones_like(query), query] + [
            np.clip(query - b, 0.0, None) for b in np.atleast_1d(breaks)
        ]
        return np.column_stack(basis) @ coefficients

    return coefficients, float(residual @ residual), predict


def select_breakpoints(
    t: np.ndarray,
    y: np.ndarray,
    *,
    max_breaks: int = 2,
    min_points: int = 4,
    dof: float | None = None,
):
    """Choose the number and position of the breakpoints by BIC on the effective d.o.f.

    The search over positions is exhaustive on the lag grid, which is affordable at this
    size and removes the local-optimum problem an iterative fit has. The penalty counts
    :func:`effective_dof` rather than the number of lags, so a curve whose residuals are
    correlated cannot buy a breakpoint with points it does not independently have.

    Args:
        t: Lags.
        y: The curve.
        max_breaks: Largest ``K`` to consider. Above two, a fit of this length is not
            identifiable and the default refuses to pretend otherwise.
        min_points: Fewest lags a segment may contain.
        dof: Effective degrees of freedom; measured from the residuals if omitted.

    Returns:
        ``{"n_breaks", "breaks_s", "slopes", "bic", "dof", "rss"}``.
    """
    t = np.asarray(t, dtype=float)
    y = np.asarray(y, dtype=float)
    good = np.isfinite(y) & (y > 0) & (t > 0)
    x, v = np.log10(t[good]), np.log10(y[good])
    n_eff = effective_dof(t, y) if dof is None else float(dof)

    def bic(rss, k_params):
        return n_eff * np.log(max(rss, 1e-300) / len(x)) + k_params * np.log(n_eff)

    best = None
    for k in range(0, max_breaks + 1):
        candidates = (
            [np.array([])]
            if k == 0
            else _combinations(np.arange(min_points, len(x) - min_points), k, min_points)
        )
        for index in candidates:
            breaks = x[np.asarray(index, dtype=int)] if len(index) else np.array([])
            coefficients, rss, _ = piecewise_fit(x, v, breaks)
            score = bic(rss, 2 + 2 * k)
            if best is None or score < best["bic"]:
                slopes = [coefficients[1]]
                for j in range(k):
                    slopes.append(slopes[-1] + coefficients[2 + j])
                best = {
                    "n_breaks": k,
                    "breaks_s": (10.0**breaks).tolist(),
                    "slopes": [float(s) for s in slopes],
                    "bic": float(score),
                    "dof": n_eff,
                    "rss": rss,
                }
    return best


def _combinations(pool, k, min_gap):
    """Index combinations of size ``k`` from ``pool``, at least ``min_gap`` apart."""
    if k == 0:
        yield []
        return
    for i, first in enumerate(pool):
        if k == 1:
            yield [first]
        else:
            rest = pool[pool >= first + min_gap]
            for tail in _combinations(rest[i * 0 :], k - 1, min_gap):
                if tail and tail[0] >= first + min_gap:
                    yield [first, *tail]


def spurious_breakpoints(
    t: np.ndarray,
    y: np.ndarray,
    *,
    n_surrogates: int = 200,
    max_breaks: int = 2,
    seed: int = 0,
    sigma: float | None = None,
    autocorrelation: float | None = None,
) -> dict:
    """How often the selection invents a break on a curve that has none.

    A surrogate is a single power law plus noise of a stated scale and lag-to-lag
    correlation. The fraction of surrogates yielding ``K >= 1`` is the false-positive rate
    the real answer has to be read against, and a knee reported without it has established
    nothing.

    .. warning::

       **The noise model must come from the sampling error, not from the residuals.** The
       defaults here read ``sigma`` and ``autocorrelation`` off the residuals about a
       straight line, and that is circular whenever the curve is genuinely bent: a
       systematic arch produces a residual autocorrelation near one, the surrogate then
       inherits that curvature as "noise", and the test reports a false-positive rate of
       one half because it is comparing the curve against copies of its own structure. On
       the archive's MSD curves the defaults give ``r = 0.94``--``0.98`` and a rate of
       roughly ``0.5``, which measures the circularity and not the curves.

       Pass ``sigma`` and ``autocorrelation`` from the **clustered bootstrap over
       flights** -- the lag-to-lag covariance of the estimator's sampling error, which
       knows nothing about the shape of the curve. Until that is available, the default
       output is a diagnostic of this function and not a result about the data.

    Args:
        t: Lags.
        y: The curve.
        n_surrogates: How many to draw.
        max_breaks: Passed to :func:`select_breakpoints`.
        seed: Base seed.
        sigma: Standard deviation of the per-lag sampling error, in dex.
        autocorrelation: Its lag-to-lag correlation.
    """
    t = np.asarray(t, dtype=float)
    y = np.asarray(y, dtype=float)
    good = np.isfinite(y) & (y > 0) & (t > 0)
    x, v = np.log10(t[good]), np.log10(y[good])
    fit = np.polyfit(x, v, 1)
    residual = v - np.polyval(fit, x)
    circular = sigma is None or autocorrelation is None
    if autocorrelation is None:
        autocorrelation = (
            float(np.corrcoef(residual[:-1], residual[1:])[0, 1]) if len(residual) > 3 else 0.0
        )
    r = min(max(float(autocorrelation), 0.0), 0.99)
    scale = residual.std() if sigma is None else float(sigma)
    sigma_step = scale * np.sqrt(max(1e-6, 1 - r**2))

    rng = np.random.default_rng(seed)
    counts = np.zeros(max_breaks + 1, dtype=int)
    for _ in range(n_surrogates):
        noise = np.empty(len(x))
        noise[0] = rng.normal(0.0, scale)
        for i in range(1, len(x)):
            noise[i] = r * noise[i - 1] + rng.normal(0.0, sigma_step)
        surrogate = 10.0 ** (np.polyval(fit, x) + noise)
        chosen = select_breakpoints(10.0**x, surrogate, max_breaks=max_breaks)
        counts[chosen["n_breaks"]] += 1
    return {
        "counts": counts.tolist(),
        "false_positive_rate": float(counts[1:].sum() / n_surrogates),
        "residual_autocorrelation": r,
        "noise_sigma": scale,
        # True when the noise model was read off the residuals, which makes the rate a
        # property of this function rather than of the data. See the warning above.
        "circular": bool(circular),
    }


def smooth_crossover(t: np.ndarray, y: np.ndarray, *, p0=None):
    """Fit ``y = A t^a1 [1 + (t/tau)^w]^((a2-a1)/w)`` -- two branches with a free sharpness.

    A piecewise fit assumes the bend is a corner. This one measures how wide it is, and
    the width is the discriminant: a crossover as broad as the branches it separates is
    not two regimes but one curved function, and reporting it as two is the error the
    piecewise family cannot detect.

    Returns:
        ``{"alpha_low", "alpha_high", "tau_s", "sharpness", "width_decades", "rms"}``, or
        ``None`` if the fit does not converge.
    """
    from scipy.optimize import curve_fit

    t = np.asarray(t, dtype=float)
    y = np.asarray(y, dtype=float)
    good = np.isfinite(y) & (y > 0) & (t > 0)
    x, v = np.log10(t[good]), np.log10(y[good])

    def model(logt, log_a, a1, a2, log_tau, log_w):
        w = 10.0**log_w
        return log_a + a1 * logt + ((a2 - a1) / w) * np.log10(
            1.0 + 10.0 ** (w * (logt - log_tau))
        )

    guess = p0 or [v[0], 1.5, 2.0, float(np.median(x)), 0.0]
    try:
        popt, _ = curve_fit(model, x, v, p0=guess, maxfev=40000)
    except (RuntimeError, ValueError):
        return None
    residual = v - model(x, *popt)
    sharpness = 10.0 ** popt[4]
    return {
        "alpha_low": float(popt[1]),
        "alpha_high": float(popt[2]),
        "tau_s": float(10.0 ** popt[3]),
        "sharpness": float(sharpness),
        # The bend occupies roughly 2/w decades: the larger the sharpness, the tighter it.
        "width_decades": float(2.0 / sharpness),
        "rms": float(np.std(residual)),
    }
