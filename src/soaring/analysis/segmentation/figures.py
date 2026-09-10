"""Diagnostic figures for fitted phase models and their decoded trajectories."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from .features import FEATURE_COLUMNS
from .labels import STATES
from .model import HMMArtifact


def plot_model_diagnostics(artifact: HMMArtifact, output: str | Path) -> None:
    """Draw transitions, Gaussian emissions, and restart stability."""
    import matplotlib.pyplot as plt

    inverse_mapping = {
        state: component for component, state in artifact.state_mapping.items()
    }
    if set(inverse_mapping) != set(STATES):
        raise ValueError("model diagnostic requires a complete semantic state mapping")
    components = [inverse_mapping[state] for state in STATES]
    transition_matrix = artifact.model.transmat_[np.ix_(components, components)]
    figure, axes = plt.subplots(2, 3, figsize=(14, 8.2), constrained_layout=True)
    image = axes[0, 0].imshow(transition_matrix, vmin=0.0, vmax=1.0, cmap="Blues")
    axes[0, 0].set(
        xticks=range(len(STATES)),
        yticks=range(len(STATES)),
        xticklabels=STATES,
        yticklabels=STATES,
        xlabel="next phase",
        ylabel="current phase",
        title="HMM transition probabilities",
    )
    for row in range(len(STATES)):
        for col in range(len(STATES)):
            axes[0, 0].text(col, row, f"{transition_matrix[row, col]:.2f}", ha="center")
    figure.colorbar(image, ax=axes[0, 0], fraction=0.046)

    x = np.arange(len(FEATURE_COLUMNS))
    width = 0.24
    for offset, (component, name) in enumerate(zip(components, STATES, strict=True)):
        axes[0, 1].bar(
            x + (offset - 1) * width,
            artifact.model.means_[component],
            width=width,
            label=name,
        )
    axes[0, 1].axhline(0.0, color="black", linewidth=0.7)
    axes[0, 1].set(
        xticks=x,
        xticklabels=[
            r"$\bar v_z$",
            r"$\bar v_h$",
            r"$\overline{|\omega|}$",
            r"$C_\omega$",
        ],
        ylabel="standardized emission mean",
        title="Gaussian emission means",
    )
    axes[0, 1].legend(frameon=False)

    restart_scores = np.asarray(
        [
            np.nan if score is None else score / max(1, artifact.n_fit_observations)
            for score in artifact.restart_log_likelihoods
        ],
        dtype=float,
    )
    if np.isfinite(restart_scores).any():
        axes[0, 2].plot(
            np.arange(len(restart_scores)), restart_scores, marker="o", linewidth=1.0
        )
        axes[0, 2].axvline(
            artifact.selected_restart,
            color="#B5482A",
            linestyle="--",
            label="selected",
        )
        axes[0, 2].legend(frameon=False)
        axes[0, 2].set(
            xlabel="restart",
            ylabel="training log likelihood / observation",
            title="Initialization stability",
        )
    else:
        axes[0, 2].set_axis_off()

    short_labels = [r"$\bar v_z$", r"$\bar v_h$", r"$|\omega|$", r"$C_\omega$"]
    covariance_limit = float(np.nanmax(np.abs(artifact.model.covars_)))
    for axis_index, (component, name) in enumerate(
        zip(components, STATES, strict=True)
    ):
        covariance = artifact.model.covars_[component]
        covariance_image = axes[1, axis_index].imshow(
            covariance,
            cmap="RdBu_r",
            vmin=-covariance_limit,
            vmax=covariance_limit,
        )
        axes[1, axis_index].set(
            xticks=range(len(FEATURE_COLUMNS)),
            yticks=range(len(FEATURE_COLUMNS)),
            xticklabels=short_labels,
            yticklabels=short_labels,
            title=f"{name}: emission covariance",
        )
        figure.colorbar(covariance_image, ax=axes[1, axis_index], fraction=0.046)
    figure.suptitle(f"State naming: {artifact.mapping_method}", fontsize=10)
    figure.savefig(output, dpi=180)
    plt.close(figure)


def plot_phase_trajectory(points: pd.DataFrame, output: str | Path) -> None:
    """Draw one decoded trajectory with its kinematics and state uncertainty."""
    import matplotlib.pyplot as plt

    required = {
        "t",
        "E",
        "N",
        "z",
        "phase",
        "mean_v_z",
        "mean_v_h",
        "mean_abs_turn_rate",
        "turn_coherence",
        "p_transition",
        "p_search",
        "p_climb",
    }
    missing = required.difference(points.columns)
    if missing:
        raise ValueError(
            f"phase trajectory figure is missing columns: {sorted(missing)}"
        )
    palette = {"transition": "#3477A8", "search": "#B5482A", "climb": "#4E8A5B"}
    ordered = points.sort_values("t", kind="stable")
    elapsed = (ordered["t"] - ordered["t"].iloc[0]) / 60.0
    figure = plt.figure(figsize=(11.5, 8.5), constrained_layout=True)
    grid = figure.add_gridspec(3, 2, height_ratios=[1.15, 1.0, 0.9])
    map_axis = figure.add_subplot(grid[0, 0])
    altitude_axis = figure.add_subplot(grid[0, 1])
    speed_axis = figure.add_subplot(grid[1, 0])
    turn_axis = figure.add_subplot(grid[1, 1])
    posterior_axis = figure.add_subplot(grid[2, :])

    map_axis.plot(ordered["E"], ordered["N"], color="#BDBDBD", linewidth=0.7)
    altitude_axis.plot(elapsed, ordered["z"], color="#BDBDBD", linewidth=0.8)
    for phase in (*STATES, "unclassified"):
        selected = ordered["phase"] == phase
        if not selected.any():
            continue
        color = palette.get(phase, "#9E9E9E")
        map_axis.scatter(
            ordered.loc[selected, "E"],
            ordered.loc[selected, "N"],
            s=8,
            color=color,
            label=phase,
            linewidths=0,
        )
        altitude_axis.scatter(
            elapsed.loc[selected],
            ordered.loc[selected, "z"],
            s=8,
            color=color,
            linewidths=0,
        )
    map_axis.set(
        xlabel="east (m)",
        ylabel="north (m)",
        aspect="equal",
        title="(a) Viterbi path",
    )
    map_axis.legend(frameon=False, markerscale=1.8, fontsize=8)
    altitude_axis.set(
        xlabel="elapsed time (min)", ylabel="altitude (m)", title="(b) Altitude"
    )

    speed_axis.plot(elapsed, ordered["mean_v_z"], color="#4E8A5B", label=r"$\bar v_z$")
    speed_axis.axhline(0.0, color="black", linewidth=0.6)
    speed_axis.set(
        xlabel="elapsed time (min)",
        ylabel=r"$\bar v_z$ (m s$^{-1}$)",
        title="(c) Speed features",
    )
    horizontal_axis = speed_axis.twinx()
    horizontal_axis.plot(
        elapsed,
        ordered["mean_v_h"],
        color="#3477A8",
        alpha=0.8,
        label=r"$\bar v_h$",
    )
    horizontal_axis.set_ylabel(r"$\bar v_h$ (m s$^{-1}$)")

    turn_axis.plot(
        elapsed,
        np.degrees(ordered["mean_abs_turn_rate"]),
        color="#B5482A",
        label=r"$\overline{|\omega|}$",
    )
    coherence_axis = turn_axis.twinx()
    coherence_axis.plot(
        elapsed,
        ordered["turn_coherence"],
        color="#4D4D4D",
        alpha=0.8,
        label=r"$C_\omega$",
    )
    turn_axis.set(
        xlabel="elapsed time (min)",
        ylabel=r"turn rate (deg s$^{-1}$)",
        title="(d) Turning features",
    )
    coherence_axis.set_ylabel("turn coherence")
    coherence_axis.set_ylim(-0.03, 1.03)

    for state in STATES:
        posterior_axis.plot(
            elapsed,
            ordered[f"p_{state}"],
            color=palette[state],
            label=state,
        )
    posterior_axis.set(
        xlabel="elapsed time (min)",
        ylabel="smoothed posterior",
        ylim=(-0.03, 1.03),
        title="(e) State uncertainty",
    )
    posterior_axis.legend(frameon=False, ncol=3, loc="upper right")
    figure.savefig(output, dpi=180)
    plt.close(figure)


def plot_confusion_matrix(
    truth: np.ndarray, prediction: np.ndarray, output: str | Path, *, title: str
) -> None:
    """Draw an integer confusion matrix in the fixed semantic phase order."""
    import matplotlib.pyplot as plt

    matrix = np.zeros((len(STATES), len(STATES)), dtype=int)
    for row, expected in enumerate(STATES):
        for col, inferred in enumerate(STATES):
            matrix[row, col] = int(
                np.sum((truth == expected) & (prediction == inferred))
            )
    figure, axis = plt.subplots(figsize=(4.5, 4.0), constrained_layout=True)
    image = axis.imshow(matrix, cmap="Blues")
    axis.set(
        xticks=range(len(STATES)),
        yticks=range(len(STATES)),
        xticklabels=STATES,
        yticklabels=STATES,
        xlabel="inferred phase",
        ylabel="manual phase",
        title=title,
    )
    for row in range(len(STATES)):
        for col in range(len(STATES)):
            axis.text(col, row, str(matrix[row, col]), ha="center")
    figure.colorbar(image, ax=axis, fraction=0.046)
    figure.savefig(output, dpi=180)
    plt.close(figure)
