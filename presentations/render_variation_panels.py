"""Prepare readable regional-variation panels from frozen, reviewed inputs."""

from __future__ import annotations

import gzip
import hashlib
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from pypdf import PdfReader, PdfWriter
from pypdf.generic import RectangleObject

ROOT = Path(__file__).resolve().parent
COLORS = {"Alps": "#207f86", "Pyrenees": "#a04c42", "Channel Coast": "#a07a22"}


def digest(path):
    """Identify the complete bytes of a frozen input or output."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    """Draw and record the five presentation panels from reviewed inputs."""
    source = json.loads((ROOT / "source-manifest.json").read_text())
    record = source["compressed_reports"]["ch3_regional_variations.json"]
    frozen = ROOT / "data" / record["archive_name"]
    assert digest(frozen) == record["gzip_sha256"]
    report = json.loads(gzip.decompress(frozen.read_bytes()))
    data = report["results"]["paragliders"]
    lags = np.asarray(report["contract"]["lags_s"], dtype=float)
    inputs = {str(frozen.relative_to(ROOT)): digest(frozen)}
    outputs = {}
    portrait = ROOT / "assets/ch3_regional_variations.pdf"
    assert (
        digest(portrait)
        == source["regional_variations_update"]["outputs"][portrait.name]["sha256"]
    )
    inputs[str(portrait.relative_to(ROOT))] = digest(portrait)
    for k, region in enumerate(("alps", "pyrenees", "coast")):
        page = PdfReader(portrait).pages[0]
        width, height = float(page.mediabox.width), float(page.mediabox.height)
        box = RectangleObject((0, height * (2 - k) / 3, width, height * (3 - k) / 3))
        page.mediabox = box
        page.cropbox = box
        writer = PdfWriter()
        writer.add_page(page)
        target = ROOT / "assets" / f"variation-region-{region}.pdf"
        with target.open("wb") as stream:
            writer.write(stream)
        outputs[target.name] = digest(target)
    plt.rcParams.update(
        {
            "font.family": "DejaVu Sans",
            "font.size": 10,
            "legend.fontsize": 9,
            "axes.spines.top": False,
            "axes.spines.right": False,
            "pdf.fonttype": 42,
        }
    )
    fig, ax = plt.subplots(figsize=(7.1, 2.7), layout="constrained")
    for region, color in COLORS.items():
        row = data["regions"][region]["matched"]
        curve = np.asarray(row["v3_over_v2"], dtype=float)
        curve[np.asarray(row["n_flights"])[:, 0] < 8] = np.nan
        ax.semilogx(lags, curve, color=color, label=region)
        ax.fill_between(
            lags,
            *np.asarray(row["pointwise_95"]["v3_over_v2"], dtype=float),
            color=color,
            alpha=0.17,
        )
    ax.axhline(3, color=".45", ls=":", label="Brownian + constant velocity")
    ax.set(xlabel=r"Lag $\tau$ [s]", ylabel=r"$V_3/V_2$")
    ax.legend(loc="best", ncol=2)
    target = ROOT / "assets/variation-order-ratios.pdf"
    fig.savefig(target, metadata={"CreationDate": None, "ModDate": None})
    plt.close(fig)
    outputs[target.name] = digest(target)
    fig, axes = plt.subplots(1, 2, figsize=(7.1, 2.7), layout="constrained")
    edges = np.asarray(report["contract"]["distribution_edges_m_s"], dtype=float)
    for ax, lag in zip(axes, (100, 1000), strict=True):
        for region, color in COLORS.items():
            row = next(
                r
                for r in data["distributions"]
                if r["region"] == region
                and r["variant"] == "matched"
                and r["lag_s"] == lag
            )
            cumulative = np.cumsum(row["probability"])
            finite = np.isfinite(edges[1:])
            ax.semilogx(
                edges[1:][finite], cumulative[finite], color=color, label=region
            )
        ax.set(
            title=rf"$\tau={lag}$ s",
            xlabel=r"$|A_2\mathbf{r}|/\tau$ [m/s]",
            ylabel="Cumulative probability",
            xlim=(0.03, 40),
            ylim=(0, 1.01),
        )
    axes[0].legend(loc="upper left")
    target = ROOT / "assets/variation-change-distributions.pdf"
    fig.savefig(target, metadata={"CreationDate": None, "ModDate": None})
    plt.close(fig)
    outputs[target.name] = digest(target)
    manifest = {
        "operation": (
            "vector row crops and redraws of saved aggregate curves; "
            "no new measurements or fits"
        ),
        "run_id": report["run_id"],
        "inputs": inputs,
        "outputs": outputs,
        "script_sha256": digest(Path(__file__)),
    }
    (ROOT / "variation-panel-manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n"
    )
    print(f"Prepared {len(outputs)} readable variation panels")


if __name__ == "__main__":
    main()
