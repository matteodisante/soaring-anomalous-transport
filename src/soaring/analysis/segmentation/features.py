"""Continuous, time-windowed observations for flight-phase segmentation.

The preprocessing pipeline preserves each logger's native cadence.  A discrete HMM,
however, attaches its transition matrix to one observation interval.  This module
therefore evaluates every eligible preprocessed segment on a common decision grid while
computing the 30-second summaries directly in physical time.  No feature window or
interpolation crosses a preprocessing segment boundary.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from .config import SegmentationConfig

FEATURE_COLUMNS = ["mean_v_z", "mean_v_h", "mean_abs_turn_rate", "turn_coherence"]
POINT_COLUMNS = [
    "source",
    "flight_id",
    "segment_id",
    "t",
    "E",
    "N",
    "z",
    "feature_edge",
    "quality_masked",
    *FEATURE_COLUMNS,
]
_REQUIRED_COLUMNS = {
    "t",
    "E",
    "N",
    "z",
    "v_E",
    "v_N",
    "v_z",
    "a_E",
    "a_N",
    "z_reconstructed",
    "edge",
}


def native_cadence_s(segment: pd.DataFrame) -> float:
    """Return a segment's uniform cadence, refusing malformed clocks.

    Args:
        segment: One preprocessed segment, ordered or unordered in time.

    Returns:
        The native time step in seconds.

    Raises:
        ValueError: If fewer than two points exist or the time base is not uniform.
    """
    t = np.sort(segment["t"].to_numpy(dtype=float))
    if t.size < 2:
        raise ValueError("a phase segment needs at least two fixes")
    dt = np.diff(t)
    if np.any(dt <= 0.0):
        raise ValueError("phase-segmentation time stamps must increase strictly")
    cadence = float(np.median(dt))
    if not np.allclose(dt, cadence, rtol=1e-7, atol=1e-8):
        raise ValueError("phase segmentation requires a uniform preprocessed segment")
    return cadence


def _cumulative_trapezoid(t: np.ndarray, values: np.ndarray) -> np.ndarray:
    """Integrate a piecewise-linear signal once for all subsequent windows."""
    cumulative = np.zeros(len(t), dtype=float)
    cumulative[1:] = np.cumsum(
        0.5 * (values[:-1] + values[1:]) * np.diff(t), dtype=float
    )
    return cumulative


def _integral_at(
    t: np.ndarray,
    values: np.ndarray,
    cumulative: np.ndarray,
    query: np.ndarray,
) -> np.ndarray:
    """Evaluate the exact piecewise-linear trapezoidal integral at many times."""
    indexes = np.searchsorted(t, query, side="right") - 1
    indexes = np.clip(indexes, 0, len(t) - 2)
    elapsed = query - t[indexes]
    slopes = (values[indexes + 1] - values[indexes]) / (t[indexes + 1] - t[indexes])
    at_query = values[indexes] + slopes * elapsed
    return cumulative[indexes] + 0.5 * (values[indexes] + at_query) * elapsed


def _window_integrals(
    t: np.ndarray, values: np.ndarray, left: np.ndarray, right: np.ndarray
) -> np.ndarray:
    """Return exact piecewise-linear integrals for equally indexed windows."""
    cumulative = _cumulative_trapezoid(t, values)
    return _integral_at(t, values, cumulative, right) - _integral_at(
        t, values, cumulative, left
    )


def _identity(segment: pd.DataFrame, column: str) -> object:
    """Read one segment-wide identity field and reject accidental mixed inputs."""
    if column not in segment:
        raise ValueError(f"phase input is missing identity column {column!r}")
    values = segment[column].drop_duplicates()
    if len(values) != 1:
        raise ValueError(f"feature construction received more than one {column}")
    return values.iloc[0]


def empty_feature_frame() -> pd.DataFrame:
    """Return the output schema for an ineligible or empty source segment."""
    dtypes: dict[str, str] = {
        "source": "string",
        "flight_id": "string",
        "segment_id": "int64",
        "t": "float64",
        "E": "float64",
        "N": "float64",
        "z": "float64",
        "feature_edge": "bool",
        "quality_masked": "bool",
    }
    dtypes.update(dict.fromkeys(FEATURE_COLUMNS, "float64"))
    return pd.DataFrame(
        {name: pd.Series(dtype=dtype) for name, dtype in dtypes.items()}
    )


def build_feature_frame(
    segment: pd.DataFrame, config: SegmentationConfig
) -> pd.DataFrame:
    """Build 10-second observations from one independently preprocessed segment.

    A segment logged more slowly than the decision grid is returned as an empty frame:
    interpolating it would manufacture observations.  At valid cadences, position is
    interpolated only for visualisation and the kinematic summaries are integrated over
    the original smoothed series.  The first and last half-window are retained as rows
    but marked ``feature_edge`` and have no emission features. A window touching either
    a reconstructed-altitude sample or a Savitzky--Golay derivative-edge sample is also
    retained but marked ``quality_masked``. Such rows intentionally separate HMM
    sequences, rather than allowing a vertical reconstruction or an unsafe derivative
    to contribute an emission or a transition.

    Args:
        segment: Rows belonging to one ``(source, flight_id, segment_id)``.
        config: Adopted common-grid and feature-window settings.

    Returns:
        One row per decision time, with NaN features at unclassifiable feature edges.

    Raises:
        ValueError: If required kinematics or identity fields are absent.
    """
    missing = _REQUIRED_COLUMNS.difference(segment.columns)
    if missing:
        raise ValueError(f"phase input is missing columns: {sorted(missing)}")
    if segment.empty:
        return empty_feature_frame()

    ordered = segment.sort_values("t", kind="stable").reset_index(drop=True)
    cadence = native_cadence_s(ordered)
    if cadence > config.max_native_dt_s:
        return empty_feature_frame()

    source = _identity(ordered, "source")
    flight_id = _identity(ordered, "flight_id")
    segment_id = _identity(ordered, "segment_id")
    t = ordered["t"].to_numpy(dtype=float)
    span = t[-1] - t[0]
    n_decisions = int(np.floor(span / config.decision_step_s + 1e-9)) + 1
    decision_t = t[0] + config.decision_step_s * np.arange(n_decisions)
    half_window = config.feature_window_s / 2.0
    feature_edge = (decision_t - half_window < t[0]) | (
        decision_t + half_window > t[-1]
    )
    quality_masked = np.zeros(decision_t.size, dtype=bool)

    v_e = ordered["v_E"].to_numpy(dtype=float)
    v_n = ordered["v_N"].to_numpy(dtype=float)
    v_z = ordered["v_z"].to_numpy(dtype=float)
    a_e = ordered["a_E"].to_numpy(dtype=float)
    a_n = ordered["a_N"].to_numpy(dtype=float)
    if ordered[["z_reconstructed", "edge"]].isna().any().any():
        raise ValueError("phase quality flags must not contain missing values")
    unsafe_input = ordered["z_reconstructed"].to_numpy(dtype=bool) | ordered[
        "edge"
    ].to_numpy(dtype=bool)
    v_h_squared = v_e**2 + v_n**2
    v_h = np.sqrt(v_h_squared)
    turn_rate = np.zeros_like(v_h)
    moving = v_h >= config.min_horizontal_speed_mps
    turn_rate[moving] = (
        v_e[moving] * a_n[moving] - v_n[moving] * a_e[moving]
    ) / v_h_squared[moving]

    features = np.full((decision_t.size, len(FEATURE_COLUMNS)), np.nan)
    interior = np.flatnonzero(~feature_edge)
    left = decision_t[interior] - half_window
    right = decision_t[interior] + half_window
    # Endpoint values are linearly interpolated, so both bracketing raw fixes are part
    # of the support even when one lies just outside the integration interval.
    first_support = np.maximum(0, np.searchsorted(t, left, side="right") - 1)
    last_support = np.minimum(len(t) - 1, np.searchsorted(t, right, side="left"))
    unsafe_prefix = np.concatenate(([0], np.cumsum(unsafe_input, dtype=np.int64)))
    unsafe_windows = (
        unsafe_prefix[last_support + 1] - unsafe_prefix[first_support]
    ) > 0
    quality_masked[interior[unsafe_windows]] = True
    safe = ~unsafe_windows
    safe_indexes = interior[safe]
    safe_left, safe_right = left[safe], right[safe]
    duration = config.feature_window_s
    if safe_indexes.size:
        signed_turn = _window_integrals(t, turn_rate, safe_left, safe_right)
        absolute_turn = _window_integrals(t, np.abs(turn_rate), safe_left, safe_right)
        coherence = np.divide(
            np.abs(signed_turn),
            absolute_turn,
            out=np.zeros_like(absolute_turn),
            where=absolute_turn > np.finfo(float).eps,
        )
        features[safe_indexes] = np.column_stack(
            [
                _window_integrals(t, v_z, safe_left, safe_right) / duration,
                _window_integrals(t, v_h, safe_left, safe_right) / duration,
                absolute_turn / duration,
                coherence,
            ]
        )

    frame = pd.DataFrame(
        {
            "source": source,
            "flight_id": flight_id,
            "segment_id": segment_id,
            "t": decision_t,
            "E": np.interp(decision_t, t, ordered["E"].to_numpy(dtype=float)),
            "N": np.interp(decision_t, t, ordered["N"].to_numpy(dtype=float)),
            "z": np.interp(decision_t, t, ordered["z"].to_numpy(dtype=float)),
            "feature_edge": feature_edge,
            "quality_masked": quality_masked,
        }
    )
    for feature_index, name in enumerate(FEATURE_COLUMNS):
        frame[name] = features[:, feature_index]
    return frame[POINT_COLUMNS]


def valid_feature_matrix(frame: pd.DataFrame) -> np.ndarray:
    """Return finite classifiable observations in the canonical feature-column order."""
    valid = valid_feature_mask(frame)
    values = frame.loc[valid, FEATURE_COLUMNS].to_numpy(dtype=float)
    if not np.isfinite(values).all():
        raise ValueError("classifiable feature rows must contain finite observations")
    return values


def valid_feature_mask(frame: pd.DataFrame) -> np.ndarray:
    """Return rows whose centred window is both available and quality-safe."""
    required = {"feature_edge", "quality_masked"}
    missing = required.difference(frame.columns)
    if missing:
        raise ValueError(f"feature frame is missing validity flags: {sorted(missing)}")
    return ~(
        frame["feature_edge"].to_numpy(dtype=bool)
        | frame["quality_masked"].to_numpy(dtype=bool)
    )


def valid_feature_block_indexes(frame: pd.DataFrame) -> list[np.ndarray]:
    """Return contiguous classifiable decision-row positions as separate sequences."""
    positions = np.flatnonzero(valid_feature_mask(frame))
    if positions.size == 0:
        return []
    boundaries = np.flatnonzero(np.diff(positions) > 1) + 1
    return [block for block in np.split(positions, boundaries) if block.size]


def valid_feature_blocks(frame: pd.DataFrame) -> list[np.ndarray]:
    """Return finite blocks without transitions across unavailable decision rows."""
    blocks = [
        frame.iloc[indexes][FEATURE_COLUMNS].to_numpy(dtype=float)
        for indexes in valid_feature_block_indexes(frame)
    ]
    for values in blocks:
        if not np.isfinite(values).all():
            raise ValueError(
                "classifiable feature rows must contain finite observations"
            )
    return blocks
