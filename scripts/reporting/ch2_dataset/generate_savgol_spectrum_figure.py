#!/usr/bin/env python3
r"""Regenerate the Savitzky-Golay noise-spectrum figure for the thesis (sec:savgol).

Writes ``thesis/generated/savgol_spectrum.pdf``: one panel per discipline
(paragliders, hang gliders), each the ensemble Welch PSD of the horizontal
(``E``, ``N`` pooled), barometric-vertical and GNSS-vertical channels. What sec:savgol
states in words -- that the three channels' knees coincide -- is what this figure lets
a reader check by eye, per discipline (so also across disciplines, which the text does
not separately claim).

The knee frequency marked on each panel (:data:`MANUAL_KNEE_HZ`) is read off the curves
by eye, not estimated by a rule in this script: the point of the figure is that a reader
can see the coincidence directly, so an automated floor-crossing estimate would only be
a second, indirect way of asserting what the plot already shows. (The pipeline's own
``tau_c``, in ``configs/preprocessing.yaml``, was set by such a rule --
``scripts/reporting/tools/estimate_savgol_timescales.py`` -- which this figure is
consistent with but does not re-derive.)

Also writes ``thesis/generated/savgol_spectrum_stats.tex``: per discipline and channel,
how many flights of the seeded sample were actually usable (\StatSavgolSpecParaHorizN,
\dots) -- the sample is not the full archive, so the count the thesis quotes has to come
from this run, not be typed in by hand.

Needs the SSD (real IGC tracks); best-effort like every reporting script -- a
discipline whose archive is not reachable is skipped, and the run refuses to write a
partial figure unless ``--allow-partial`` is given. Run with (``uv run`` already
includes the ``analysis`` dependency group by default)::

    SOARING_PARA_DATA_ROOT=/Volumes/SSD_DISANTE/paragliders/ffvl_cfd_igc \
    SOARING_DELTA_DATA_ROOT=/Volumes/SSD_DISANTE/hang_gliders/delta_cfd_igc \
    uv run python scripts/reporting/ch2_dataset/generate_savgol_spectrum_figure.py
"""

from __future__ import annotations

import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
OUT_FIG = ROOT / "thesis" / "generated" / "savgol_spectrum.pdf"
OUT_TEX = ROOT / "thesis" / "generated" / "savgol_spectrum_stats.tex"

# Sampling and Welch settings, identical to tools/estimate_savgol_timescales.py.
N_SAMPLE = 900
SEED = 42
NPERSEG = 256
DT_TOL = 0.25

# The knee frequency to mark on each panel, read by eye off the plotted curves (see the
# module docstring) -- not computed here.
MANUAL_KNEE_HZ = {
    "paragliders": 0.20,
    "hang gliders": 0.23,
}

_SRC = str(ROOT / "src")
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

# The sys.path line above is what makes this resolvable when the script is run
# directly, so the import cannot move to the top of the file.
from soaring.reporting import (  # noqa: E402
    DISCIPLINES,
    bare_cli,
    partial_write_refusal,
    unreachable_reason,
    write_macros,
)

_PDF_METADATA = {
    "Creator": "soaring.analysis",
    "Producer": "soaring.analysis",
    "CreationDate": None,
}

_CHANNELS = ["horizontal", "vertical_baro", "vertical_gnss"]
_CHANNEL_LABEL = {
    "horizontal": "horizontal ($E,N$)",
    "vertical_baro": "vertical, barometric",
    "vertical_gnss": "vertical, GNSS",
}
_CHANNEL_COLOR = {
    "horizontal": "#3477a8",
    "vertical_baro": "#b5482a",
    "vertical_gnss": "#3d8c54",
}
_CHANNEL_TAG = {
    "horizontal": "Horiz",
    "vertical_baro": "Baro",
    "vertical_gnss": "Gnss",
}


def _local_en(lat, lon):
    """Equirectangular metres about the track mean (spectral use only)."""
    import numpy as np

    lat0 = float(np.nanmean(lat))
    east = (
        np.radians(lon - float(np.nanmean(lon))) * 6371008.8 * np.cos(np.radians(lat0))
    )
    north = np.radians(lat - lat0) * 6371008.8
    return east, north


def _psd_1hz(t, x):
    """Welch PSD of ``x(t)`` resampled onto a 1 s grid."""
    import numpy as np
    from scipy.signal import welch

    grid = np.arange(t[0], t[-1], 1.0)
    xg = np.interp(grid, t, x)
    if len(xg) < NPERSEG:
        return None, None
    f, s = welch(xg, fs=1.0, nperseg=NPERSEG, noverlap=NPERSEG // 2, detrend="linear")
    return f, s


def _collect(igc_dir):
    """Sample one discipline's archive; return ``freqs`` and per-channel raw PSD stacks.

    Returns:
        ``(freqs, {channel: list[psd]}, {channel: n_flights})``, or ``(None, {}, {})``
        if nothing usable was sampled.
    """
    from soaring.analysis.igc import (
        baro_present_fraction,
        median_sampling_period,
        parse_igc,
    )

    paths = sorted(igc_dir.rglob("*.igc"))
    rng = random.Random(SEED)
    sample = rng.sample(paths, min(N_SAMPLE, len(paths)))
    stacks: dict[str, list] = {c: [] for c in _CHANNELS}
    freqs = None
    for p in sample:
        try:
            fixes = parse_igc(p)
        except (ValueError, OSError):
            continue
        if len(fixes) < NPERSEG:
            continue
        dt = median_sampling_period(fixes)
        if not (abs(dt - 1.0) <= DT_TOL):
            continue
        t = fixes["t"].to_numpy(dtype=float)
        east, north = _local_en(
            fixes["lat"].to_numpy(dtype=float), fixes["lon"].to_numpy(dtype=float)
        )
        f, s_e = _psd_1hz(t, east)
        if f is None:
            continue
        _, s_n = _psd_1hz(t, north)
        freqs = f
        stacks["horizontal"] += [s_e, s_n]
        if baro_present_fraction(fixes) >= 0.5:
            _, s_z = _psd_1hz(t, fixes["baro_alt"].to_numpy(dtype=float))
            stacks["vertical_baro"].append(s_z)
        else:
            _, s_z = _psd_1hz(t, fixes["gnss_alt"].to_numpy(dtype=float))
            stacks["vertical_gnss"].append(s_z)
    if freqs is None:
        return None, {}, {}
    counts = {
        "horizontal": len(stacks["horizontal"]) // 2,
        "vertical_baro": len(stacks["vertical_baro"]),
        "vertical_gnss": len(stacks["vertical_gnss"]),
    }
    return freqs, stacks, counts


def _make_figure(per_discipline):
    """Draw one panel per discipline from a ``{name: (freqs, channels)}`` mapping."""
    import matplotlib.pyplot as plt

    fig, axes = plt.subplots(
        1, len(per_discipline), figsize=(5.4 * len(per_discipline), 4.2), sharey=True
    )
    if len(per_discipline) == 1:
        axes = [axes]
    for ax, (disc_name, (freqs, channels)) in zip(
        axes, per_discipline.items(), strict=True
    ):
        for ch in _CHANNELS:
            if ch not in channels:
                continue
            psd, n = channels[ch]
            ax.loglog(freqs, psd, color=_CHANNEL_COLOR[ch], lw=1.3,
                      label=f"{_CHANNEL_LABEL[ch]} ($n={n}$)")
        knee = MANUAL_KNEE_HZ.get(disc_name)
        if knee is not None:
            ax.axvline(knee, color="0.3", ls=":", lw=1.2,
                       label=f"knee, by eye ({knee:.2f} Hz)")
        ax.set_title(disc_name, fontsize=10)
        ax.set_xlabel("frequency (Hz)")
        ax.set_xlim(freqs[1], freqs[-1])
        ax.legend(fontsize=6.8, frameon=False, loc="lower left")
    axes[0].set_ylabel(r"median PSD ($\mathrm{m^2/Hz}$)")
    fig.tight_layout()
    return fig


def main() -> int:
    """Regenerate the figure and macros, best-effort across the two disciplines."""
    try:
        import matplotlib
        import numpy as np
    except ImportError:
        print("matplotlib/numpy missing ('analysis' dependency group); keeping files.")
        return 0
    matplotlib.use("Agg")

    reachable = {}
    for name, disc in DISCIPLINES.items():
        try:
            cfg = disc.config()
        except (FileNotFoundError, KeyError):
            continue
        if cfg.igc_dir.is_dir():
            reachable[name] = (disc, cfg)

    missing = [d for d in DISCIPLINES if d not in reachable]
    refusal = partial_write_refusal(
        missing, OUT_FIG.name,
        allow_partial="--allow-partial" in sys.argv[1:],
        reasons=[r for d in missing if (r := unreachable_reason(DISCIPLINES[d]))],
    )
    if refusal:
        print(refusal)
        return 1
    if not reachable:
        print("No IGC data reachable on the SSD; keeping the committed files.")
        return 0

    per_discipline: dict[str, tuple] = {}
    values: dict[str, str] = {}
    for name, (disc, cfg) in reachable.items():
        freqs, stacks, counts = _collect(cfg.igc_dir)
        if freqs is None:
            print(f"[{name}] no usable 1 Hz flights in the sample; skipping.")
            continue
        channels = {}
        for ch, stack in stacks.items():
            if not stack:
                continue
            arr = np.vstack(stack)
            s_med = np.median(arr, axis=0)
            channels[ch] = (s_med, counts[ch])
            values[f"StatSavgolSpec{disc.tag}{_CHANNEL_TAG[ch]}N"] = str(counts[ch])
        per_discipline[name] = (freqs, channels)
        print(f"[{name}] " + ", ".join(f"{ch}={n}" for ch, n in counts.items()))

    if not per_discipline:
        print("No usable spectra; keeping the committed files.")
        return 0

    OUT_FIG.parent.mkdir(parents=True, exist_ok=True)
    _make_figure(per_discipline).savefig(
        OUT_FIG, metadata=_PDF_METADATA, bbox_inches="tight"
    )
    write_macros(
        OUT_TEX, values,
        generator="scripts/reporting/ch2_dataset/generate_savgol_spectrum_figure.py",
    )
    print(f"Wrote {OUT_FIG.name} and {OUT_TEX.name} ({len(values)} macros).")
    return 0


if __name__ == "__main__":
    bare_cli(__doc__, known=["--allow-partial"])

    raise SystemExit(main())
