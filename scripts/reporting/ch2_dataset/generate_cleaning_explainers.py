#!/usr/bin/env python3
"""Draw reproducible cleaning schematics using the implemented altitude rules.

Synthetic figures are deliberately labelled as illustrations, not measured error rates.
No external dataset is needed. Run with ``uv run python`` from the repository root.
"""

from __future__ import annotations

import sys
from pathlib import Path

import matplotlib
import numpy as np
import pandas as pd

matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[3]
# Static output contract for the provenance checker; paths may be built dynamically.
GENERATED_OUTPUTS = (
    "cleaning_defects_schematic.pdf",
    "vertical_median_explainer.pdf",
)

sys.path.insert(0, str(ROOT / "src"))
from soaring.analysis.config import load_preproc_config  # noqa: E402
from soaring.analysis.preproc.cleaning import (  # noqa: E402
    clean_flight,
    local_vz,
    step_vz,
)
from soaring.reporting.style import ILLUSTRATION_COLORS, paper_style  # noqa: E402

# These schematics face measured figures, so they take the same house style:
# boxed axes, left-set panel titles and 9pt DejaVu Sans.
paper_style()

OUT = ROOT / "thesis" / "generated"
BLUE = ILLUSTRATION_COLORS["primary"]
RED = ILLUSTRATION_COLORS["secondary"]
GREY = ILLUSTRATION_COLORS["reference"]
META = {
    "Creator": "soaring.analysis",
    "Producer": "soaring.analysis",
    "CreationDate": None,
}


def frame(t, altitude):
    """A plausible eastward flight accompanying a synthetic altitude signal."""
    return pd.DataFrame(
        {
            "t": t,
            "lat": np.full(len(t), 45.0),
            "lon": 7 + 12 * t / (111320 * np.cos(np.deg2rad(45))),
            "alt": altitude,
            "baro_alt": 1500 + 2 * t,
            "valid": True,
        }
    )


def save(fig, name):
    """Save an archival PDF and close its figure."""
    OUT.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT / f"{name}.pdf", metadata=META, bbox_inches="tight")
    fig.savefig(Path("/tmp") / f"{name}.png", dpi=130, bbox_inches="tight")
    plt.close(fig)


def defects():
    """Contrast horizontal removal, structural splitting and altitude censoring."""
    fig, grid = plt.subplots(
        3, 2, figsize=(6.1, 6.9), sharey="row", constrained_layout=True
    )
    ax = grid.T
    t = np.arange(0, 121, 5, dtype=float)
    x = 10 * t
    spike = x.copy()
    spike[12] += 700
    frozen = x.copy()
    frozen[6:20] = frozen[6]
    altitude = 1600 + 2 * t
    corrupt = altitude.copy()
    corrupt[12] += 400
    series = [spike, frozen, corrupt]
    masks = [
        np.arange(len(t)) == 12,
        (np.arange(len(t)) >= 6) & (np.arange(len(t)) < 20),
        np.arange(len(t)) == 12,
    ]
    names = [
        "(a) Position spike",
        "(c) Repeated position",
        "(e) Altitude spike",
    ]
    for col, (y, mask, title) in enumerate(zip(series, masks, names, strict=True)):
        ax[0, col].plot(t, y, "o-", color=GREY, ms=3, lw=1)
        ax[0, col].plot(t[mask], y[mask], "x", color=RED, ms=7, mew=1.7)
        ax[0, col].set_title(title, loc="left", fontsize=9)
        if col == 1:
            # Do not join either retained side across unobserved motion.
            for keep in (np.arange(len(t)) < 6, np.arange(len(t)) >= 20):
                ax[1, col].plot(t[keep], y[keep], "o-", color=BLUE, ms=3)
            ax[1, col].axvspan(t[6], t[19], color=RED, alpha=0.08)
            note = "(d) Interval removed; split"
        else:
            ax[1, col].plot(t[~mask], y[~mask], "o", color=BLUE, ms=3)
            ax[1, col].plot(t[~mask], y[~mask], "--", color=BLUE, lw=1)
            note = (
                "(b) Position removed; short gap"
                if col == 0
                else "(f) Altitude missing; xy retained"
            )
        ax[1, col].set_title(note, loc="left", fontsize=9)
        for row in range(2):
            ax[row, col].set_xlabel("Time [s]")
            ax[row, col].set_ylabel("East position [m]" if col < 2 else "Altitude [m]")
            ax[row, col].grid(visible=True, which="major", color=".9", lw=0.5)
    save(fig, "cleaning_defects_schematic")


def median():
    """Show the real configured median/spike decisions on three controlled signals."""
    cfg = load_preproc_config()
    t = np.arange(61, dtype=float)
    change = 1700 + 2 * t + 3 * np.maximum(t - 30, 0)
    spike = 1700 + 2 * t
    spike[30] += 60
    sustained = 1700 + 2 * t + cfg.fix.max_vertical_speed_mps * np.clip(t - 22, 0, 16)
    cases = [change, spike, sustained]
    titles = [
        "(a) Climb-rate change",
        "(c) Isolated spike",
        "(e) Sustained excess",
    ]
    fig, grid = plt.subplots(
        3, 2, figsize=(6.1, 6.9), sharex=True, constrained_layout=True
    )
    axes = grid.T
    for col, (alt, title) in enumerate(zip(cases, titles, strict=True)):
        cleaned = clean_flight(frame(t, alt), cfg.fix, discipline="paragliders")
        rejected = cleaned.fixes.alt_invalidated.to_numpy()
        vz = step_vz(t, alt)
        med, _ = local_vz(t, vz, cfg.fix.vz_window_s)
        mid = (t[1:] + t[:-1]) / 2
        axes[0, col].plot(t, alt, color=GREY, lw=1.4)
        axes[0, col].plot(t[rejected], alt[rejected], "x", color=RED, ms=5)
        axes[0, col].set_title(title, loc="left", fontsize=9)
        axes[1, col].set_title(
            f"({chr(98 + col * 2)}) Step and window speeds", loc="left", fontsize=9
        )
        axes[1, col].plot(mid, np.abs(vz), color=GREY, lw=1, label="Step magnitude")
        axes[1, col].plot(mid, med, color=BLUE, lw=2, label="Window median")
        axes[1, col].axhline(
            cfg.fix.max_vertical_speed_mps,
            color=RED,
            ls="--",
            lw=1,
            label="Threshold",
        )
        axes[1, col].set_ylim(
            0, max(cfg.fix.max_vertical_speed_mps * 1.5, np.max(np.abs(vz)) * 1.08)
        )
        axes[1, col].set_xlabel("Time [s]")
        axes[0, col].set_ylabel("Altitude [m]")
        axes[1, col].set_ylabel(r"$|v_z|$ [m/s]")
        axes[1, col].axvspan(
            30 - cfg.fix.vz_window_s, 30 + cfg.fix.vz_window_s, color=BLUE, alpha=0.07
        )
        for row in range(2):
            axes[row, col].grid(visible=True, which="major", color=".9", lw=0.5)
    axes[1, 0].legend(loc="upper left", fontsize=8, frameon=False)
    save(fig, "vertical_median_explainer")


if __name__ == "__main__":
    defects()
    median()
