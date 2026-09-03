#!/usr/bin/env python3
"""Regenerate the Savitzky-Golay explainer figure for the thesis (thesis, sec:savgol).

Writes ``thesis/generated/savgol_explainer.pdf``: one highlighted window's local
polynomial fit, next to the real filter output -- :func:`scipy.signal.savgol_filter`,
``mode='interp'``, edge samples included -- run on a synthetic series,
``sin(0.28 * j) + noise``, ``noise ~ N(0, 0.35**2)`` i.i.d.; for intuition only, not
flight data. The window and polynomial order come from ``configs/preprocessing.yaml``
(the ``savgol`` key) via :func:`soaring.analysis.preproc.smoothing.savgol_window`. The
kernel weights themselves (the actual numbers :func:`smooth_segment` convolves the
signal with, computed with :func:`scipy.signal.savgol_coeffs`) are tabulated directly
in the thesis (Table ``tab:savgol-kernels``), not drawn here.

Needs no flight data (a closed-form computation plus one synthetic panel), so it
always regenerates when matplotlib/scipy are present::

    uv run python scripts/reporting/ch2_dataset/generate_savgol_figure.py
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "thesis" / "generated" / "savgol_explainer.pdf"
SEED = 8  # fixed (chosen so the centre sample visibly differs from a_0), reproducible

_SRC = str(ROOT / "src")
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

# The sys.path line above is what makes this resolvable when the script is run
# directly, so the import cannot move to the top of the file.
from soaring.reporting import bare_cli  # noqa: E402

# Deterministic PDF metadata -> committing the figure produces clean diffs.
_PDF_METADATA = {
    "Creator": "soaring.analysis",
    "Producer": "soaring.analysis",
    "CreationDate": None,
}

_COLOR_RAW = "#8a949c"
_COLOR_FIT = "#b5482a"
_COLOR_CENTER = "#1c2321"
_COLOR_A0 = "#3477a8"


def _make_figure(w: int, p: int, *, seed: int):
    """Build the figure.

    Kept in this script: drawn once, by one caller
    (:mod:`soaring.analysis.figures` is for panels more than one caller needs).
    """
    import matplotlib.pyplot as plt
    import numpy as np
    from scipy.signal import savgol_filter

    m = w // 2

    # A little context either side of the highlighted window, not a wall of unrelated
    # points: the window itself has to read as the subject of the panel.
    ctx = m + 3
    j = np.arange(-ctx, ctx + 1)
    freq, noise_sd = 0.28, 0.35
    rng = np.random.default_rng(seed)
    x = np.sin(freq * j) + rng.normal(scale=noise_sd, size=j.size)

    # The real filter, run on the whole shown span exactly as smooth_segment() runs
    # it on a flight segment: mode='interp' fits the first/last w samples once and
    # evaluates that one polynomial off-centre for the m points nearest each edge,
    # instead of re-centring a window that would run past the data.
    smoothed = savgol_filter(x, window_length=w, polyorder=p, deriv=0, delta=1.0,
                              mode="interp")
    edge = np.zeros(j.size, dtype=bool)
    edge[:m] = True
    edge[-m:] = True

    # The one highlighted window's own continuous fit, shown only across its span --
    # this is what a_0 and the slope a_1 are read off, at u = 0.
    in_window = np.abs(j) <= m
    u = j[in_window]
    vander = np.vander(u, N=p + 1, increasing=True)
    a, *_ = np.linalg.lstsq(vander, x[in_window], rcond=None)
    u_fine = np.linspace(-m, m, 200)
    fit_fine = sum(a[k] * u_fine**k for k in range(p + 1))
    x_centre = x[ctx]  # the one raw sample the smoothing replaces, at j = 0

    fig, ax_a = plt.subplots(1, 1, figsize=(5.8, 4.3))

    ax_a.axvspan(-m - 0.5, m + 0.5, color="#eef1f3", zorder=0)
    ax_a.plot(j, x, "o", ms=4.2, color=_COLOR_RAW, zorder=2, label="raw samples")
    ax_a.plot(u_fine, fit_fine, "-", lw=2, color=_COLOR_FIT, zorder=3,
              label=f"local fit, this window ($p={p}$)")
    tang = np.array([-0.9, 0.9])
    ax_a.plot(tang, a[0] + a[1] * tang, "--", lw=1.4, color=_COLOR_CENTER, zorder=4,
              label="slope $a_1$")
    ax_a.plot(j[~edge], smoothed[~edge], "o", ms=4.2, color=_COLOR_A0, zorder=4,
              label="smoothed output")
    ax_a.plot(j[edge], smoothed[edge], "s", ms=5.5, mfc="white", mec=_COLOR_A0,
              mew=1.3, zorder=4, label="smoothed output, edge (off-centre)")
    ax_a.plot(0, smoothed[ctx], "o", ms=7.5, color=_COLOR_A0, mec=_COLOR_CENTER,
              mew=1.3, zorder=6, label="$a_0$, this window's centre")
    ax_a.set_xlim(-ctx - 0.5, ctx + 0.5)
    ax_a.set_xlabel("sample index $j-i$")
    ax_a.set_ylabel("signal (arb. units)")
    ax_a.set_title("local fit and real filter output", fontsize=10)
    ax_a.legend(fontsize=6.3, frameon=False, loc="upper center",
                bbox_to_anchor=(0.5, -0.22), ncols=2, handlelength=1.6,
                columnspacing=1.0, labelspacing=0.5)

    # Inset: zoom on the centre sample, where the fit trades x_i for a_0.
    axins = ax_a.inset_axes((0.04, 0.52, 0.42, 0.42))
    zoom = 0.6
    fine = np.abs(u_fine) <= zoom
    axins.plot(u_fine[fine], fit_fine[fine], "-", lw=2, color=_COLOR_FIT, zorder=2)
    axins.plot(0, x_centre, "o", ms=6.5, color=_COLOR_RAW, mec="0.25", mew=0.7,
               zorder=3, label="raw $x_i$")
    axins.plot(0, smoothed[ctx], "o", ms=6.5, color=_COLOR_A0, mec=_COLOR_CENTER,
               mew=0.9, zorder=3, label="smoothed $a_0$")
    axins.plot([0, 0], [x_centre, smoothed[ctx]], ":", lw=1.2, color="0.25", zorder=1)
    y_all = np.concatenate([fit_fine[fine], [x_centre, smoothed[ctx]]])
    lo, hi = y_all.min(), y_all.max()
    pad = max(0.18 * (hi - lo), 0.03)
    axins.set_xlim(-zoom, zoom)
    axins.set_ylim(lo - pad, hi + pad)
    axins.set_xticks([])
    axins.set_yticks([])
    axins.set_title("centre, zoomed", fontsize=7, pad=2)
    axins.legend(fontsize=6, frameon=False, loc="lower right", handlelength=1.0,
                 borderaxespad=0.2, labelspacing=0.3)
    for spine in axins.spines.values():
        spine.set_edgecolor("0.5")
        spine.set_linewidth(0.8)

    fig.tight_layout()
    return fig


def main() -> int:
    """Regenerate the figure and write it to :data:`OUT`."""
    try:
        import matplotlib
    except ImportError:
        print("matplotlib missing ('analysis' dependency group); keeping the figure.")
        return 0
    matplotlib.use("Agg")

    from soaring.analysis.config import load_preproc_config
    from soaring.analysis.preproc.smoothing import savgol_window

    savgol = load_preproc_config().savgol
    w = savgol_window(savgol.tau_c_horizontal_s, dt_s=1.0, polyorder=savgol.polyorder)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    _make_figure(w, savgol.polyorder, seed=SEED).savefig(
        OUT, metadata=_PDF_METADATA, bbox_inches="tight"
    )
    print(f"Wrote {OUT.name} (w={w}, p={savgol.polyorder}).")
    return 0


if __name__ == "__main__":
    bare_cli(__doc__, known=[])

    raise SystemExit(main())
