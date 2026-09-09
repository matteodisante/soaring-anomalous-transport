"""Diagnostic figures for fitted phase models and their decoded trajectories."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from .features import FEATURE_COLUMNS
from .labels import STATES
from .model import HMMArtifact


def plot_model_diagnostics(artifact: HMMArtifact, output: str | Path) -> None:
    """Draw the semantic transition matrix and standardized emission means."""
    import matplotlib.pyplot as plt

    names = [artifact.state_mapping[index] for index in range(len(STATES))]
    figure, axes = plt.subplots(1, 2, figsize=(10, 4.3), constrained_layout=True)
    image = axes[0].imshow(artifact.model.transmat_, vmin=0.0, vmax=1.0, cmap="Blues")
    axes[0].set(
        xticks=range(len(names)),
        yticks=range(len(names)),
        xticklabels=names,
        yticklabels=names,
        xlabel="next phase",
        ylabel="current phase",
        title="HMM transition probabilities",
    )
    for row in range(len(names)):
        for col in range(len(names)):
            axes[0].text(
                col, row, f"{artifact.model.transmat_[row, col]:.2f}", ha="center"
            )
    figure.colorbar(image, ax=axes[0], fraction=0.046)

    x = np.arange(len(FEATURE_COLUMNS))
    width = 0.24
    for component, name in enumerate(names):
        axes[1].bar(
            x + (component - 1) * width,
            artifact.model.means_[component],
            width=width,
            label=name,
        )
    axes[1].axhline(0.0, color="black", linewidth=0.7)
    axes[1].set(
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
    axes[1].legend(frameon=False)
    figure.savefig(output, dpi=180)
    plt.close(figure)


def plot_phase_trajectory(points: pd.DataFrame, output: str | Path) -> None:
    """Draw one decoded trajectory on its local EN plane, colored by Viterbi phase."""
    import matplotlib.pyplot as plt

    required = {"E", "N", "phase"}
    missing = required.difference(points.columns)
    if missing:
        raise ValueError(
            f"phase trajectory figure is missing columns: {sorted(missing)}"
        )
    palette = {"transition": "#3477A8", "search": "#B5482A", "climb": "#4E8A5B"}
    figure, axis = plt.subplots(figsize=(5.2, 5.0), constrained_layout=True)
    for phase, group in points.groupby("phase", sort=False):
        axis.scatter(
            group["E"],
            group["N"],
            s=10,
            color=palette.get(str(phase), "#9E9E9E"),
            label=phase,
            linewidths=0,
        )
    axis.set(xlabel="east (m)", ylabel="north (m)", aspect="equal")
    axis.legend(frameon=False, markerscale=1.8)
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
