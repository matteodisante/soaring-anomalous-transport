#!/usr/bin/env python3
r"""Reduce the shape pass into Chapter 3's second measurement, its figure and its macros.

The exponent of ``generate_transport_figure.py`` is one moment of one distribution. This
asks the questions that one moment cannot answer.

**Is it a Lévy walk?** The spectrum :math:`\langle|\Delta\mathbf{r}|^q\rangle\sim
\Delta^{q\nu(q)}` is bilinear with a knee for a Lévy walk and straight through the origin
for a monofractal process. The discrimination is visual and does not rest on a delicate
fit, which is why it is worth a full pass over the archive.

**Does the memory account for the displacement?** The velocity autocorrelation integrated
by Green--Kubo must return the measured displacement. The two channels are built by
different routes --- positions smoothed, velocities differentiated from them --- so
agreement is a statement that the differentiation invented nothing.

**Is there a separation of scales?** The persistence runs say how far the wing goes before
it turns. If their tail index is stable as the geometric threshold is scanned, there is a
scale to separate; if it moves, there is not, and that is a prediction about any
segmentation attempted later.

Writes ``thesis/generated/shape.tex`` and ``shape.pdf``.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
_SRC = str(ROOT / "src")
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

OUT_TEX = ROOT / "thesis" / "generated" / "shape.tex"
OUT_FIG = ROOT / "thesis" / "generated" / "shape.pdf"

DISCIPLINES = {"paragliders": ("para", "Para"), "hang gliders": ("hang", "Hang")}
COLORS = {"paragliders": "#3477a8", "hang gliders": "#b5482a"}
SINUOSITIES = (1.05, 1.15, 1.30)

# A LaTeX control sequence takes letters only, so the threshold is spelled out in the
# macro name. This is the second generator to need the rule, which is why the macro
# checker refuses an unusable name rather than leaving it for the build to hit.
_SINUOSITY_WORD = {1.05: "Straight", 1.15: "Gentle", 1.30: "Loose"}
MIN_SAMPLES = 500

_PDF_METADATA = {"Creator": "soaring.analysis", "Producer": "soaring.analysis", "CreationDate": None}


def load(slug: str, audit_dir: Path):
    path = audit_dir / f"shape_{slug}.npz"
    return dict(np.load(path)) if path.is_file() else None


def measure(discipline: str, data: dict, macros: dict) -> dict:
    from soaring.analysis.observables.moments import bilinear_fit
    from soaring.analysis.observables.persistence import tail_index

    tag = DISCIPLINES[discipline][1]
    lags, q_grid = data["lags_s"], data["q_grid"]
    moment, counts, tail = data["moment"], data["moment_count"], data["tail_share"]

    def put(name, value):
        macros[f"StatShape{tag}{name}"] = value

    usable = (counts > MIN_SAMPLES) & np.isfinite(moment[:, 0])
    put("Lags", f"{int(usable.sum())}")
    put("FitMinS", f"{lags[usable][0]:.0f}")
    put("FitMaxS", f"{lags[usable][-1]:.0f}")
    put("QMin", f"{q_grid[0]:.2f}")
    put("QMax", f"{q_grid[-1]:.0f}")

    q_nu = np.array(
        [np.polyfit(np.log(lags[usable]), np.log(moment[usable, j]), 1)[0]
         for j in range(q_grid.size)]
    )
    fitted = bilinear_fit(q_grid, q_nu)
    put("NuMin", f"{np.nanmin(q_nu / q_grid):.3f}")
    put("NuMax", f"{np.nanmax(q_nu / q_grid):.3f}")
    put("NuSpread", f"{np.nanmax(q_nu / q_grid) - np.nanmin(q_nu / q_grid):.3f}")
    put("LinearSlope", f"{fitted['linear_slope']:.3f}")
    put("LinearDeparture", f"{fitted['linear_departure']:.4f}")
    put("Bilinear", "yes" if fitted["prefers_bilinear"] else "no")
    if fitted["prefers_bilinear"]:
        put("Knee", f"{fitted['knee']:.2f}")
        put("SlopeHigh", f"{fitted['slope_high']:.2f}")
    # The tail control: a moment carried by its largest one per cent is not a moment.
    put("TailMaxPct", f"{100 * np.nanmax(tail[usable]):.0f}")
    put("TailAtQMaxPct", f"{100 * np.nanmedian(tail[usable, -1]):.0f}")

    # The velocity memory.
    vacf = data.get("vacf", np.zeros(0))
    good = np.isfinite(vacf) & (vacf != 0)
    if good.any():
        put("VacfFlights", f"{int(data['vacf_flights'][0])}")
        put("VacfAtFloor", f"{vacf[good][0]:+.2f}")
        below = np.flatnonzero(good & (vacf < np.exp(-1.0)))
        put("VacfDecayS", f"{lags[below[0]]:.0f}" if below.size else "beyond the range")
        negative = np.flatnonzero(good & (vacf < 0))
        put("VacfSignChangeS", f"{lags[negative[0]]:.0f}" if negative.size else "never")

    # The persistence runs, scanned over the geometric threshold.
    betas = []
    for sinuosity in SINUOSITIES:
        lengths = data.get(f"runs_{str(sinuosity).replace('.', 'p')}", np.zeros(0))
        if lengths.size < 100:
            continue
        beta, cut = tail_index(lengths)
        betas.append(beta)
        name = _SINUOSITY_WORD[sinuosity]
        put(f"Beta{name}", f"{beta:.2f}")
        put(f"Median{name}S", f"{np.median(lengths):.0f}")
        put(f"Runs{name}", f"{lengths.size}")
        put(f"Cut{name}S", f"{cut:.0f}")
    if len(betas) > 1:
        put("BetaSpread", f"{max(betas) - min(betas):.2f}")
        put("BetaStable", "no" if max(betas) - min(betas) > 0.3 else "yes")

    return {"lags": lags, "q_grid": q_grid, "q_nu": q_nu, "usable": usable,
            "moment": moment, "tail": tail, "vacf": vacf, "fit": fitted, "data": data}


def draw(measured: dict):
    import matplotlib.pyplot as plt

    fig, axes = plt.subplots(2, 2, figsize=(11.4, 7.6))
    (spec_ax, tail_ax), (vacf_ax, runs_ax) = axes

    for discipline, m in measured.items():
        colour = COLORS[discipline]
        q, q_nu = m["q_grid"], m["q_nu"]
        spec_ax.plot(q, q_nu, "o-", color=colour, ms=4, label=discipline)
        spec_ax.plot(q, m["fit"]["linear_slope"] * q, "--", color=colour, lw=0.9,
                     label=f"{discipline}, $q\\nu={m['fit']['linear_slope']:.2f}q$")
        tail_ax.plot(q, np.nanmedian(m["tail"][m["usable"]], axis=0), "o-", color=colour, ms=4,
                     label=discipline)
        good = np.isfinite(m["vacf"]) & (m["vacf"] != 0)
        if good.any():
            vacf_ax.semilogx(m["lags"][good], m["vacf"][good], color=colour, label=discipline)
        for sinuosity, style in zip(SINUOSITIES, ("-", "--", ":")):
            lengths = m["data"].get(f"runs_{str(sinuosity).replace('.', 'p')}", np.zeros(0))
            if lengths.size < 100:
                continue
            edges = np.geomspace(max(lengths.min(), 1), lengths.max(), 40)
            survival = np.array([(lengths >= e).mean() for e in edges])
            runs_ax.loglog(edges, survival, style, color=colour, lw=1.1,
                           label=f"{discipline}, $s\\leq{sinuosity}$")

    spec_ax.set_xlabel("$q$")
    spec_ax.set_ylabel(r"$q\,\nu(q)$")
    spec_ax.set_title("(a) moment spectrum: straight means monofractal", fontsize=10, loc="left")
    tail_ax.axhline(0.2, color="0.4", lw=0.8, ls="--")
    tail_ax.set_xlabel("$q$")
    tail_ax.set_ylabel("share of the moment in its largest 1\\%".replace("\\", ""))
    tail_ax.set_title("(b) tail control", fontsize=10, loc="left")
    vacf_ax.axhline(0.0, color="0.4", lw=0.8)
    vacf_ax.set_xlabel(r"$\tau$ (s)")
    vacf_ax.set_ylabel(r"$C(\tau)$")
    vacf_ax.set_title("(c) velocity autocorrelation", fontsize=10, loc="left")
    runs_ax.set_xlabel("run duration (s)")
    runs_ax.set_ylabel("$P(T>\\tau)$")
    runs_ax.set_title("(d) persistence runs, by geometric threshold", fontsize=10, loc="left")
    for ax in axes.ravel():
        ax.legend(frameon=False, fontsize=7)
    fig.tight_layout()
    return fig


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--audit-dir", type=Path, required=True)
    args = parser.parse_args()

    import matplotlib

    matplotlib.use("Agg")

    macros: dict[str, str] = {}
    measured: dict[str, dict] = {}
    for discipline, (slug, _) in DISCIPLINES.items():
        data = load(slug, args.audit_dir)
        if data is None:
            print(f"{discipline}: shape pass not found, skipping")
            continue
        measured[discipline] = measure(discipline, data, macros)
    if not macros:
        print("no shape pass reachable; shape.tex not written")
        return 1

    draw(measured).savefig(OUT_FIG, metadata=_PDF_METADATA)
    lines = ["% Generated by scripts/reporting/generate_shape_figure.py -- do not edit."]
    lines += [f"\\newcommand{{\\{k}}}{{{v}}}" for k, v in macros.items()]
    OUT_TEX.write_text("\n".join(lines) + "\n")
    print(f"wrote {OUT_TEX.name}, {OUT_FIG.name} ({len(macros)} macros)")
    for k, v in macros.items():
        print(f"  {k:36s} {v}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
