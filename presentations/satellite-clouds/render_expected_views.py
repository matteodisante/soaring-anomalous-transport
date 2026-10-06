"""Draw what each satellite dataset would show over a 10 x 10 km cell.

Everything here is an illustration: a synthetic field of fair-weather cumuli,
not satellite data. Each dataset is imitated by averaging the synthetic
reflectance over its pixels (approximate sizes over France) and by keeping only
its acquisition times. Real images are blurrier (instrument point-spread
function) and shifted north by parallax; both are left out on purpose.

Outputs, in assets/expected/:
    grids.pdf               pixel grids of each dataset over the cell
    snapshot.pdf            the five views at one moment
    frames/frame-NN.png     one hour, one frame per minute (for the PDF animation)
    expected-views.gif      the same hour as a GIF

Run from the repository root:
    uv run python presentations/satellite-clouds/render_expected_views.py
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
from matplotlib.colors import ListedColormap  # noqa: E402
from matplotlib.patches import Rectangle  # noqa: E402
from PIL import Image  # noqa: E402

OUT = Path(__file__).resolve().parent / "assets" / "expected"
HALF_VIEW, STEP = 7.0, 0.05  # km: view of the cell plus 2 km, fine grid spacing
MINUTES = 60
WIND_KM_PER_MIN = 0.12  # 2 m/s towards the east
INK, CELL, NOTE = "#13233A", "#C2610F", "#9C4A06"
BANNER = "Illustration of what to expect: synthetic clouds, not real satellite data"


@dataclass(frozen=True)
class Sensor:
    """A dataset imitated by its pixel size (km, east x north) and cadence (min)."""

    title: str
    dx: float
    dy: float
    every: int
    offset: tuple[float, float]
    mask: bool = False


SENSORS = (
    Sensor("SEVIRI VIS0.6, 3 x 5 km", 3.0, 5.0, 5, (0.7, -1.3)),
    Sensor("SEVIRI HRV, 1 x 2 km", 1.0, 2.0, 5, (0.35, 0.6)),
    Sensor("MTG VIS0.6, 0.6 x 0.9 km", 0.6, 0.9, 10, (0.2, 0.25)),
    Sensor("Cloud mask, white = cloud", 3.0, 5.0, 5, (0.7, -1.3), mask=True),
)

axis = np.arange(-HALF_VIEW, HALF_VIEW, STEP) + STEP / 2
X, Y = np.meshgrid(axis, axis)
rng = np.random.default_rng(20261006)


def _smooth_noise(scale_km: float) -> np.ndarray:
    """Low-contrast terrain texture in [0, 1]."""
    field = rng.normal(size=X.shape)
    k = np.fft.fftfreq(len(axis), STEP)
    kx, ky = np.meshgrid(k, k)
    field = np.real(np.fft.ifft2(np.fft.fft2(field) * np.exp(-((kx**2 + ky**2) * scale_km**2))))
    return (field - field.min()) / np.ptp(field)


GROUND = 0.13 + 0.07 * _smooth_noise(0.8)
HOT_SPOTS = np.array([(-3.5, 1.5), (0.5, -2.5), (2.5, 3.0), (-1.0, 4.5)])


def _clouds() -> list[dict]:
    """Cumuli born over hot spots (or anywhere), growing, drifting and decaying."""
    clouds = []
    for _ in range(110):
        if rng.random() < 0.75:
            x0, y0 = HOT_SPOTS[rng.integers(len(HOT_SPOTS))] + rng.normal(0, 0.6, 2)
        else:
            x0, y0 = rng.uniform(-HALF_VIEW - 3, HALF_VIEW, 2)
        clouds.append({
            "x0": x0, "y0": y0,
            "born": rng.uniform(-35, MINUTES), "life": rng.uniform(15, 35),
            "rmax": rng.uniform(0.35, 1.3),
            "lobes": rng.uniform(0, 2 * np.pi, 3), "amps": rng.uniform(0.05, 0.18, 3),
        })
    return clouds


CLOUDS = _clouds()


def cloud_fraction(t: float) -> np.ndarray:
    """Cloud cover in [0, 1] on the fine grid at minute ``t``."""
    cover = np.zeros_like(X)
    for c in CLOUDS:
        age = (t - c["born"]) / c["life"]
        if not 0 < age < 1:
            continue
        r = c["rmax"] * np.sin(np.pi * age)
        cx = c["x0"] + WIND_KM_PER_MIN * (t - c["born"])
        dx, dy = X - cx, Y - c["y0"]
        theta = np.arctan2(dy, dx)
        edge = r * (1 + sum(a * np.sin((k + 3) * theta + p)
                            for k, (a, p) in enumerate(zip(c["amps"], c["lobes"], strict=True))))
        cover = np.maximum(cover, 1 / (1 + np.exp((np.hypot(dx, dy) - edge) / 0.06)))
    return cover


def reflectance(cover: np.ndarray) -> np.ndarray:
    """Visible reflectance: dark ground, bright cloud."""
    return GROUND + (0.75 - GROUND) * cover


def pixel_average(values: np.ndarray, s: Sensor) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Average ``values`` over the sensor's pixels; return edges and pixel means."""
    xe = np.arange(-HALF_VIEW - s.dx + s.offset[0] % s.dx, HALF_VIEW + s.dx, s.dx)
    ye = np.arange(-HALF_VIEW - s.dy + s.offset[1] % s.dy, HALF_VIEW + s.dy, s.dy)
    ix = np.clip(np.searchsorted(xe, X, side="right") - 1, 0, len(xe) - 2)
    iy = np.clip(np.searchsorted(ye, Y, side="right") - 1, 0, len(ye) - 2)
    flat = iy * (len(xe) - 1) + ix
    sums = np.bincount(flat.ravel(), values.ravel(), (len(xe) - 1) * (len(ye) - 1))
    counts = np.bincount(flat.ravel(), minlength=(len(xe) - 1) * (len(ye) - 1))
    means = np.where(counts > 0, sums / np.maximum(counts, 1), np.nan)
    return xe, ye, means.reshape(len(ye) - 1, len(xe) - 1)


def _cell(ax) -> None:
    ax.add_patch(Rectangle((-5, -5), 10, 10, fill=False, ec=CELL, lw=1.6))
    ax.set_xlim(-HALF_VIEW, HALF_VIEW)
    ax.set_ylim(-HALF_VIEW, HALF_VIEW)
    ax.set_xticks([])
    ax.set_yticks([])
    ax.set_aspect("equal")


MASK_CMAP = ListedColormap(["#000000", "#F5F3EE"])


def draw_views(fig, t: int, axes) -> None:
    """The synthetic field and each dataset's latest image at minute ``t``."""
    truth = reflectance(cloud_fraction(t))
    axes[0].imshow(truth, origin="lower", cmap="gray", vmin=0.0, vmax=0.8, rasterized=True,
                   extent=(-HALF_VIEW, HALF_VIEW, -HALF_VIEW, HALF_VIEW))
    axes[0].set_title("Synthetic cumuli\n(what is really there)", fontsize=9, color=INK)
    _cell(axes[0])
    for ax, s in zip(axes[1:], SENSORS, strict=True):
        shot = t - t % s.every
        cover = cloud_fraction(shot)
        values = cover if s.mask else reflectance(cover)
        xe, ye, means = pixel_average(values, s)
        if s.mask:
            ax.pcolormesh(xe, ye, (means > 0.25).astype(float), cmap=MASK_CMAP, vmin=0, vmax=1,
                          rasterized=True)
        else:
            ax.pcolormesh(xe, ye, means, cmap="gray", vmin=0.0, vmax=0.8, rasterized=True)
        ax.set_title(f"{s.title}\nevery {s.every} min, image of 12:{shot:02d}", fontsize=9, color=INK)
        _cell(ax)


def draw_timeline(ax, t: int) -> None:
    """Acquisition times of each cadence and the current minute."""
    for row, (label, every, colour) in enumerate((("SEVIRI images", 5, "#2F6690"),
                                                  ("MTG images", 10, CELL))):
        y = 1 - row
        ax.text(-1, y, label, ha="right", va="center", fontsize=8, color=colour)
        ax.plot([0, MINUTES], [y, y], color="#C9C3B8", lw=1)
        shots = np.arange(0, MINUTES + 1, every)
        ax.scatter(shots, np.full(len(shots), y), s=14, color=colour, zorder=3)
    ax.plot([t, t], [-0.5, 1.6], color=INK, lw=1.5)
    ax.text(t, 1.75, f"now 12:{t:02d}", ha="center", va="bottom", fontsize=8, color=INK)
    ax.set_xlim(-12, MINUTES + 1)
    ax.set_ylim(-0.6, 2.6)
    ax.axis("off")


def frame(t: int, path: Path) -> None:
    """One animation frame: five views, the timeline and the banner."""
    fig = plt.figure(figsize=(10, 3.4), dpi=110)
    axes = [fig.add_axes((0.01 + k * 0.198, 0.27, 0.18, 0.55)) for k in range(5)]
    draw_views(fig, t, axes)
    draw_timeline(fig.add_axes((0.12, 0.02, 0.8, 0.17)), t)
    fig.text(0.5, 0.95, BANNER, ha="center", fontsize=11, color=NOTE, weight="bold")
    fig.savefig(path, facecolor="white")
    plt.close(fig)
    # 128 colours are plenty for grey panels and keep the PDF animation light.
    Image.open(path).convert("RGB").quantize(128).save(path, optimize=True)


def snapshot(t: int, path: Path) -> None:
    """The five views at minute ``t``, as a vector figure for the slides."""
    fig = plt.figure(figsize=(10, 2.8))
    axes = [fig.add_axes((0.01 + k * 0.198, 0.05, 0.18, 0.66)) for k in range(5)]
    draw_views(fig, t, axes)
    fig.text(0.5, 0.94, BANNER, ha="center", fontsize=11, color=NOTE, weight="bold")
    fig.savefig(path, dpi=200)
    plt.close(fig)


def grids(t: int, path: Path) -> None:
    """Each dataset's pixel grid over the cell, on a faded synthetic field."""
    truth = reflectance(cloud_fraction(t))
    fig = plt.figure(figsize=(10, 3.6))
    for k, s in enumerate(SENSORS[:3]):
        ax = fig.add_axes((0.04 + k * 0.32, 0.04, 0.27, 0.74))
        ax.imshow(truth, origin="lower", cmap="gray", vmin=-0.4, vmax=0.9, alpha=0.6, rasterized=True,
                  extent=(-HALF_VIEW, HALF_VIEW, -HALF_VIEW, HALF_VIEW))
        xe, ye, _ = pixel_average(truth, s)
        ax.vlines(xe, -HALF_VIEW, HALF_VIEW, color="#2F6690", lw=0.7)
        ax.hlines(ye, -HALF_VIEW, HALF_VIEW, color="#2F6690", lw=0.7)
        touching = sum(1 for i in range(len(xe) - 1) for j in range(len(ye) - 1)
                       if xe[i + 1] > -5 and xe[i] < 5 and ye[j + 1] > -5 and ye[j] < 5)
        ax.set_title(f"{s.title}\n{touching} pixels touch the cell", fontsize=10, color=INK)
        _cell(ax)
    fig.text(0.5, 0.95, "Pixel grids over a 10 x 10 km cell (orange); background: synthetic clouds",
             ha="center", fontsize=11, color=NOTE, weight="bold")
    fig.savefig(path, dpi=200)
    plt.close(fig)


def main() -> None:
    """Write the grids figure, the snapshot, the frames and the GIF."""
    frames_dir = OUT / "frames"
    frames_dir.mkdir(parents=True, exist_ok=True)
    grids(30, OUT / "grids.pdf")
    snapshot(33, OUT / "snapshot.pdf")
    paths = []
    for t in range(MINUTES + 1):
        path = frames_dir / f"frame-{t:02d}.png"
        frame(t, path)
        paths.append(path)
    images = [Image.open(p) for p in paths]
    images[0].save(OUT / "expected-views.gif", save_all=True, append_images=images[1:],
                   duration=250, loop=0, optimize=True)
    print(f"Wrote {len(paths)} frames, grids.pdf, snapshot.pdf and the GIF to {OUT}")


if __name__ == "__main__":
    main()
