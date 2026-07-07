#!/usr/bin/env python3
r"""Estimate the Savitzky-Golay smoothing timescales from the ENU power spectra.

Implements the noise-matched procedure of the thesis (sec:savgol) to measure the three
``tau_c`` values that were placeholders in ``configs/preprocessing.yaml``: the knee
frequency ``f_c`` where each channel's dynamical spectrum meets its flat noise floor,
read from the per-frequency *median* Welch spectrum over a seeded sample of 1 Hz
flights, exactly as in the altitude-noise study (impl:altchannel): modal
``dt = 1 s``, flights within 0.25 s of it and with at least 256 fixes, linear
resampling onto the 1 s grid, ``scipy.signal.welch`` with ``nperseg=256``, Hann
window, 50% overlap, linear detrending per segment.

Channels: the horizontal components ``E`` and ``N`` (local equirectangular metres
about each track's mean -- exact enough for a spectral knee), pooled into one
horizontal estimate; the barometric altitude on barometric flights; the GNSS altitude
on GNSS-fallback flights (the channel each actually uses, sec:savgol).

Knee rule, stated once and used for every channel: the floor is the median of the
median-PSD over the top of the band (0.35-0.5 Hz); ``f_c`` is the lowest frequency
whose PSD falls below three times that floor; ``tau_c = 1/f_c``, rounded to the
second. The factor 3 marks the end of the dynamical roll-off without chasing the
floor's own scatter; the validation of sec:savgol (flat residual spectrum, stability
under one window step) is what ultimately confirms the choice.

Read-only and best-effort like every reporting script: it needs the SSD and prints
the measured values; adopting them in the YAML is a deliberate, separate edit.

Run::

    SOARING_PARA_DATA_ROOT=... SOARING_DELTA_DATA_ROOT=... \
    uv run python scripts/reporting/estimate_savgol_timescales.py
"""

from __future__ import annotations

import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
_SRC = str(ROOT / "src")
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

N_SAMPLE = 900  # seeded sample per discipline; a few hundred 1 Hz survivors suffice
SEED = 42
NPERSEG = 256
DT_TOL = 0.25  # s, distance from the modal 1 s cadence
FLOOR_BAND = (0.35, 0.5)  # Hz, where the flat noise floor is read
KNEE_FACTOR = 3.0


def _local_en(lat, lon):
    """Equirectangular metres about the track mean (spectral use only)."""
    import numpy as np

    lat0 = float(np.nanmean(lat))
    east = np.radians(lon - float(np.nanmean(lon))) * 6371008.8 * np.cos(
        np.radians(lat0)
    )
    north = np.radians(lat - lat0) * 6371008.8
    return east, north


def _psd_1hz(t, x):
    """Welch PSD of ``x(t)`` resampled onto a 1 s grid (see module docstring)."""
    import numpy as np
    from scipy.signal import welch

    grid = np.arange(t[0], t[-1], 1.0)
    xg = np.interp(grid, t, x)
    if len(xg) < NPERSEG:
        return None, None
    f, s = welch(
        xg, fs=1.0, nperseg=NPERSEG, noverlap=NPERSEG // 2, detrend="linear"
    )
    return f, s


def _knee_tau(f, s_median):
    """The knee rule of the module docstring, on a median PSD."""
    import numpy as np

    floor_mask = (f >= FLOOR_BAND[0]) & (f <= FLOOR_BAND[1])
    floor = float(np.median(s_median[floor_mask]))
    below = np.where((f > 0) & (s_median <= KNEE_FACTOR * floor))[0]
    if below.size == 0:
        return float("nan"), floor
    return 1.0 / float(f[below[0]]), floor


def main() -> int:
    """Sample, compute the median (and p90) spectra, print the knee timescales."""
    import numpy as np

    from soaring.acquisition.ffvl.config import load_config
    from soaring.analysis.igc import (
        baro_present_fraction,
        median_sampling_period,
        parse_igc,
    )

    disciplines = {
        "para": ("configs/para_download.yaml", "SOARING_PARA_DATA_ROOT"),
        "hang": ("configs/delta_download.yaml", "SOARING_DELTA_DATA_ROOT"),
    }
    spectra = {"horizontal": [], "vertical_baro": [], "vertical_gnss": []}
    counts = dict.fromkeys(spectra, 0)
    freqs = None

    for name, (config_path, env) in disciplines.items():
        cfg = load_config(str(ROOT / config_path), data_root_env=env)
        paths = sorted((cfg.data_root / "raw" / "igc").rglob("*.igc"))
        rng = random.Random(SEED)
        sample = rng.sample(paths, min(N_SAMPLE, len(paths)))
        used = 0
        for p in sample:
            fixes = parse_igc(p)
            if len(fixes) < NPERSEG:
                continue
            dt = median_sampling_period(fixes)
            if not (abs(dt - 1.0) <= DT_TOL):
                continue
            t = fixes["t"].to_numpy(dtype=float)
            east, north = _local_en(
                fixes["lat"].to_numpy(dtype=float),
                fixes["lon"].to_numpy(dtype=float),
            )
            f, s_e = _psd_1hz(t, east)
            if f is None:
                continue
            _, s_n = _psd_1hz(t, north)
            freqs = f
            spectra["horizontal"] += [s_e, s_n]
            counts["horizontal"] += 1
            if baro_present_fraction(fixes) >= 0.5:
                _, s_z = _psd_1hz(t, fixes["baro_alt"].to_numpy(dtype=float))
                spectra["vertical_baro"].append(s_z)
                counts["vertical_baro"] += 1
            else:
                _, s_z = _psd_1hz(t, fixes["gnss_alt"].to_numpy(dtype=float))
                spectra["vertical_gnss"].append(s_z)
                counts["vertical_gnss"] += 1
            used += 1
        print(f"{name}: {used} usable 1 Hz flights of {len(sample)} sampled")

    print("\nchannel        n_flights  tau_c[s]  f_c[Hz]   floor[m2/Hz]  tau_c(p90)[s]")
    for ch, stack in spectra.items():
        if not stack:
            print(f"{ch:14s} 0 -- no data")
            continue
        arr = np.vstack(stack)
        s_med = np.median(arr, axis=0)
        tau, floor = _knee_tau(freqs, s_med)
        fc = 1.0 / tau if np.isfinite(tau) else float("nan")
        # The 90th-percentile spectrum: the noisy edge of the band. Relevant for the
        # GNSS vertical, whose median coincides with the barometric one while its
        # noisy minority does not (impl:altchannel).
        tau90, _ = _knee_tau(freqs, np.quantile(arr, 0.90, axis=0))
        print(
            f"{ch:14s} {counts[ch]:9d}  {tau:7.1f}  {fc:8.4f}  {floor:11.3g}"
            f"   {tau90:7.1f}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
