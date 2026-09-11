#!/usr/bin/env python3
r"""Plot raw coordinate spectra used to motivate the working smoothing timescale.

Writes ``savgol_spectrum.pdf`` and ``savgol_spectrum_stats.tex``. A seeded sample
of up to 900 flights per discipline contributes each available channel independently.
Spectra use the longest uninterrupted finite interval near 1 Hz. The marked frequencies
are visual references, not fitted cutoffs. Cached NPZ version 2 records this selection;
``--rescan`` forces a fresh collection. This diagnostic does not identify quantization
as the source of the knee or certify the configured filter for every cadence.
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
from soaring.reporting.style import CHANNEL_COLORS  # noqa: E402

_PDF_METADATA = {
    "Creator": "soaring.analysis",
    "Producer": "soaring.analysis",
    "CreationDate": None,
}

_CHANNELS = ["horizontal", "vertical_baro", "vertical_gnss"]
_CHANNEL_LABEL = {
    "horizontal": "horizontal ($E,N$)",
    "vertical_baro": "barometric altitude",
    "vertical_gnss": "GNSS altitude",
}
# The two altitude sources and the horizontal channel; see style.CHANNEL_COLORS.
_CHANNEL_COLOR = CHANNEL_COLORS
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
    import numpy as np

    from soaring.analysis.altitude_noise import longest_regular_block
    from soaring.analysis.igc import (
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
        th, horizontal = longest_regular_block(t, np.column_stack([east, north]), 1.0)
        if len(th) >= NPERSEG:
            f, s_e = _psd_1hz(th, horizontal[:, 0])
            _, s_n = _psd_1hz(th, horizontal[:, 1])
            if f is not None:
                freqs = f
                stacks["horizontal"] += [s_e, s_n]
        for column, channel in (
            ("baro_alt", "vertical_baro"),
            ("gnss_alt", "vertical_gnss"),
        ):
            z = fixes[column].to_numpy(dtype=float).copy()
            z[z == 0] = np.nan
            if column == "gnss_alt":
                z[~fixes["valid"].to_numpy(dtype=bool)] = np.nan
            tz, zv = longest_regular_block(t, z, 1.0)
            if len(tz) < NPERSEG:
                continue
            f, s_z = _psd_1hz(tz, zv)
            if f is not None:
                freqs = f
                stacks[channel].append(s_z)
    if freqs is None:
        return None, {}, {}
    counts = {
        "horizontal": len(stacks["horizontal"]) // 2,
        "vertical_baro": len(stacks["vertical_baro"]),
        "vertical_gnss": len(stacks["vertical_gnss"]),
    }
    return freqs, stacks, counts


def _load_or_collect(igc_dir: Path, cache_path: Path, *, rescan: bool = False):
    """Load a cached PSD sample, or run :func:`_collect` and cache the result.

    Cached arrays contain separately selected channel samples and a selection-policy
    version. Each horizontal flight contributes two component spectra; each available
    altitude channel can contribute one. Pass ``rescan=True`` if sample size, seed or
    raw archive content changes.
    """
    import numpy as np

    if cache_path.is_file() and not rescan:
        data = np.load(cache_path)
        rescan = int(data.get("cache_version", 0)) != 2
    if cache_path.is_file() and not rescan:
        data = np.load(cache_path)
        freqs = data["freqs"]
        stacks = {ch: list(data[ch]) for ch in _CHANNELS}
        counts = {
            "horizontal": len(stacks["horizontal"]) // 2,
            "vertical_baro": len(stacks["vertical_baro"]),
            "vertical_gnss": len(stacks["vertical_gnss"]),
        }
        print(f"Using cached PSD sample at {cache_path} (delete to resample).")
        return freqs, stacks, counts

    freqs, stacks, counts = _collect(igc_dir)
    if freqs is not None:
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        np.savez_compressed(
            cache_path,
            cache_version=np.int64(2),
            freqs=freqs,
            **{
                ch: (np.vstack(stacks[ch]) if stacks[ch] else np.empty((0, len(freqs))))
                for ch in _CHANNELS
            },
        )
        print(f"Cached PSD sample to {cache_path}.")
    return freqs, stacks, counts


def _make_figure(per_discipline):
    """Draw one panel per discipline from a ``{name: (freqs, channels)}`` mapping."""
    import matplotlib.pyplot as plt

    fig, axes = plt.subplots(
        1, len(per_discipline), figsize=(3.05 * len(per_discipline), 3.4), sharey=True
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
            ax.loglog(
                freqs,
                psd,
                color=_CHANNEL_COLOR[ch],
                lw=1.3,
                label=f"{_CHANNEL_LABEL[ch]} ($n={n}$)",
            )
        knee = MANUAL_KNEE_HZ.get(disc_name)
        if knee is not None:
            ax.axvline(
                knee,
                color="0.3",
                ls=":",
                lw=1.2,
                label=f"visual reference ({knee:.2f} Hz)",
            )
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        ax.tick_params(labelsize=9)
        ax.set_title(disc_name, fontsize=10)
        ax.set_xlabel("frequency (Hz)")
        ax.set_xlim(freqs[1], freqs[-1])
        ax.legend(fontsize=8, frameon=False, loc="lower left")
    axes[0].set_ylabel(r"median PSD ($\mathrm{m^2/Hz}$)")
    fig.tight_layout()
    return fig


def main(argv: list[str] | None = None) -> int:
    """Regenerate the figure and macros, best-effort across the two disciplines."""
    argv = sys.argv[1:] if argv is None else argv
    rescan = "--rescan" in argv
    try:
        import matplotlib
        import numpy as np
    except ImportError:
        print("matplotlib/numpy missing ('analysis' dependency group); keeping files.")
        return 0
    matplotlib.use("Agg")
    from soaring.reporting.style import paper_style

    paper_style()

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
        missing,
        OUT_FIG.name,
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
        cache_path = cfg.derived_dir / "savgol_psd_sample.npz"
        freqs, stacks, counts = _load_or_collect(cfg.igc_dir, cache_path, rescan=rescan)
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
        OUT_TEX,
        values,
        generator="scripts/reporting/ch2_dataset/generate_savgol_spectrum_figure.py",
    )
    print(f"Wrote {OUT_FIG.name} and {OUT_TEX.name} ({len(values)} macros).")
    return 0


if __name__ == "__main__":
    bare_cli(__doc__, known=["--allow-partial", "--rescan"])

    raise SystemExit(main())
