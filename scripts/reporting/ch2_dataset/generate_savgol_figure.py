#!/usr/bin/env python3
"""Draw the configured Savitzky--Golay fit and its exact spectral/noise effects.

Both figures use scipy.signal.savgol_filter/savgol_coeffs with the working YAML
configuration. The signal example is synthetic; the response and noise bias are
analytical calculations, not a calibration of GNSS errors.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "src"))
from soaring.reporting import bare_cli  # noqa: E402

GENERATED_OUTPUTS = ("savgol_explainer.pdf", "savgol_response.pdf")
META = {
    "Creator": "soaring.analysis",
    "Producer": "soaring.analysis",
    "CreationDate": None,
}
BLUE, ORANGE, GREY = "#3477A8", "#B5482A", "#77818A"


def main() -> int:
    """Render both diagnostics from the current window configuration."""
    import matplotlib

    matplotlib.use("Agg")
    from soaring.reporting.style import paper_style

    paper_style()
    import matplotlib.pyplot as plt
    import numpy as np
    from scipy.signal import savgol_coeffs, savgol_filter

    from soaring.analysis.config import load_preproc_config
    from soaring.analysis.preproc.smoothing import savgol_window

    cfg = load_preproc_config().savgol
    w = savgol_window(cfg.tau_c_horizontal_s, 1.0, cfg.polyorder)
    m, p = w // 2, cfg.polyorder
    plt.rcParams.update(
        {
            "font.size": 10,
            "axes.labelsize": 10,
            "axes.titlesize": 10,
            "xtick.labelsize": 9,
            "ytick.labelsize": 9,
            "legend.fontsize": 9,
            "axes.spines.top": False,
            "axes.spines.right": False,
            "pdf.fonttype": 42,
            "axes.titlelocation": "left",
        }
    )
    j = np.arange(-m - 3, m + 4)
    x = np.sin(0.28 * j) + np.random.default_rng(8).normal(0, 0.35, len(j))
    fitted = savgol_filter(x, w, p, mode="interp")
    window = np.abs(j) <= m
    a = np.polynomial.polynomial.polyfit(j[window], x[window], p)
    uf = np.linspace(-m, m, 200)
    fig, axes = plt.subplots(1, 2, figsize=(6.1, 3.25), layout="constrained")
    ax = axes[0]
    ax.plot(j[window], x[window], "o", color=GREY, ms=5, label="observations")
    ax.plot(
        uf,
        np.polynomial.polynomial.polyval(uf, a),
        color=ORANGE,
        lw=2,
        label="cubic fit",
    )
    tangent = np.array([-0.65, 0.65])
    ax.plot(
        tangent, a[0] + a[1] * tangent, "--", color=".2", lw=1.3, label="centre slope"
    )
    ax.plot(0, a[0], "o", color=BLUE, ms=6)
    ax.set(
        xlabel="sample offset",
        ylabel="signal [arbitrary units]",
        title="(a) One fitted window",
    )
    ax.legend(frameon=False, loc="upper left")
    ax = axes[1]
    ax.plot(j, x, "o", color=GREY, ms=4, label="observations")
    ax.plot(j, fitted, "-", color=BLUE, lw=1.6, label="filtered signal")
    edge = (j < j[0] + m) | (j > j[-1] - m)
    ax.plot(j[edge], fitted[edge], "s", mfc="white", mec=BLUE, ms=5, label="edge fit")
    ax.set(
        xlabel="sample index",
        ylabel="signal [arbitrary units]",
        title="(b) Whole segment",
    )
    ax.legend(frameon=False, loc="upper left")
    fig.savefig(ROOT / "thesis/generated/savgol_explainer.pdf", metadata=META)
    plt.close(fig)

    c = savgol_coeffs(w, p, use="dot")
    f = np.linspace(0, 0.5, 600)
    gain = np.abs(np.exp(2j * np.pi * np.outer(f, np.arange(-m, m + 1))) @ c) ** 2
    ell = np.arange(0, max(11, 2 * w))
    norm = np.dot(c, c)
    cov = np.array(
        [np.dot(c[k:], c[:-k]) if 0 < k < w else norm if k == 0 else 0 for k in ell]
    )
    bias = 2 * (norm - cov)
    fig, axes = plt.subplots(1, 2, figsize=(6.1, 3.05), layout="constrained")
    ax = axes[0]
    ax.plot(f, gain, color=BLUE, lw=2)
    ax.axhline(0.5, color=".65", ls=":", lw=1)
    ax.set(
        xlabel=r"normalized frequency $f\Delta t$",
        ylabel=r"power transmission $|G|^2$",
        title=f"(a) Filter response ($w={w}$, $p={p}$)",
        xlim=(0, 0.5),
        ylim=(0, 1.05),
    )
    ax = axes[1]
    ax.plot(
        ell,
        np.where(ell == 0, 0.0, 2.0),
        color=ORANGE,
        ls="--",
        lw=1.5,
        label="unfiltered",
    )
    ax.plot(ell, bias, "o-", color=BLUE, lw=1.6, ms=4, label="filtered")
    ax.set(
        xlabel=r"lag $\ell=\tau/\Delta t$",
        ylabel=r"noise contribution $B(\ell)/\sigma^2$",
        title="(b) One-coordinate MSD bias",
        xlim=(0, ell[-1]),
        ylim=(0, 2.2),
    )
    ax.legend(frameon=False, loc="lower right")
    fig.savefig(ROOT / "thesis/generated/savgol_response.pdf", metadata=META)
    plt.close(fig)
    print(f"Wrote {', '.join(GENERATED_OUTPUTS)} (w={w}, p={p}).")
    return 0


if __name__ == "__main__":
    bare_cli(__doc__, known=[])
    raise SystemExit(main())
