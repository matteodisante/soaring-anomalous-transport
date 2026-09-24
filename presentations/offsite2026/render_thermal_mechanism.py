"""Draw the slide-10 schematic: slope-bound mountain thermals against scattered lowland triggers.

Conceptual only. The mountain panel shows strong thermals fed by upslope flow along
sun-facing spurs and released along the crest, so the release pattern traces the relief.
The lowland panel shows weaker, vertical thermals rising from heated surfaces of several
kinds, placed irregularly across the plain. No wind is drawn in either panel.
"""
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.collections import PolyCollection

OUT = Path(__file__).resolve().parent / "assets"
PHI, EPS = np.radians(-18), np.radians(30)  # camera azimuth and elevation
LX, LY, SLAB = 64.0, 32.0, 3.0  # block size and slab thickness, arbitrary units
GAP = 14.0  # horizontal screen gap between the panels
SUN = np.array([-0.45, -0.75, 0.62]) / np.linalg.norm([-0.45, -0.75, 0.62])
# Summits along the crest (x, extra height, width); a spur descends towards the viewer from each.
PEAKS = ((9.0, 3.5, 4.5), (20.0, 7.0, 5.5), (32.0, 2.5, 4.0), (44.0, 8.0, 5.5), (55.5, 4.5, 4.5))
SPURS = tuple(peak[0] for peak in PEAKS)
GULLIES = tuple((a + b) / 2 for a, b in zip(SPURS[:-1], SPURS[1:]))
STRONG = dict(color="#D9480F", envelope="#F08A4B", lw=1.35, alpha=0.30)
WEAK = dict(color="#EE8C45", envelope="#F5B27F", lw=1.0, alpha=0.24)
EDGE = "#4A4A4A"


def project(x, y, z, shift=0.0):
    """Orthographic screen coordinates (u, v) and depth (larger is further away)."""
    x1 = x * np.cos(PHI) - y * np.sin(PHI)
    y1 = x * np.sin(PHI) + y * np.cos(PHI)
    return x1 + shift, z * np.cos(EPS) + y1 * np.sin(EPS), y1 * np.cos(EPS) - z * np.sin(EPS)


# Mountain terrain ---------------------------------------------------------------------------

def ridge_y(x):
    return 20.5 + 2.8 * np.sin(2 * np.pi * x / LX * 1.1 + 0.4)


def crest_height(x):
    return 7.5 + sum(a * np.exp(-((x - c) / w) ** 2) for c, a, w in PEAKS)


def mountain(x, y):
    """Sharp-crested ridge with spurs and gullies on the sunny front face."""
    yc, top = ridge_y(x), crest_height(x)
    d = y - yc
    front = d < 0
    main = top * np.exp(-(np.abs(d) / np.where(front, 10.5, 6.5)) ** 1.25)
    shoulder = np.where(front, 1 - np.exp(-(d / 3.0) ** 2), 0.0)
    spurs = sum(np.exp(-((x - xs) / 2.0) ** 2) for xs in SPURS)
    spurs -= 0.45 * sum(np.exp(-((x - xg) / 1.7) ** 2) for xg in GULLIES)
    rough = 0.45 * np.sin(x / 1.9 + 0.3) * np.sin(y / 1.6) + 0.3 * np.sin(x / 1.1 + 1.1) * np.cos(y / 1.3 + 0.5)
    return 1.0 + main * (1 + 0.32 * spurs * shoulder) + rough * main / top + 0.35 * np.sin(x / 6) * np.sin(y / 5)


def gradient(f, x, y, h=0.05):
    return (f(x + h, y) - f(x - h, y)) / (2 * h), (f(x, y + h) - f(x, y - h)) / (2 * h)


def shaded(base, normal, heat=0.0):
    light = 0.48 + 0.52 * max(0.0, float(normal @ SUN))
    colour = np.clip(np.asarray(base) * light, 0, 1)
    return np.clip(colour * (1 - heat) + np.array([0.95, 0.78, 0.52]) * heat, 0, 1)


def terrain_colour(z, normal):
    t = np.clip((z - 3.0) / 11.0, 0, 1) ** 1.3
    low, high = np.array([0.60, 0.72, 0.50]), np.array([0.84, 0.82, 0.78])
    base = low * (1 - t) + high * t
    sunny = max(0.0, float(normal @ SUN) - 0.82) / 0.18
    return shaded(base, normal, heat=0.22 * sunny * t)


def draw_heightfield(ax, f, shift, nx=120, ny=64):
    xs, ys = np.linspace(0, LX, nx + 1), np.linspace(0, LY, ny + 1)
    X, Y = np.meshgrid(xs, ys)
    Z = f(X, Y)
    polys, colours, depths = [], [], []
    for j in range(ny):
        for i in range(nx):
            cx, cy = X[j, i:i + 2].mean(), Y[j:j + 2, i].mean()
            gx, gy = gradient(f, cx, cy)
            normal = np.array([-gx, -gy, 1.0]) / np.sqrt(gx * gx + gy * gy + 1)
            corners = [(j, i), (j, i + 1), (j + 1, i + 1), (j + 1, i)]
            u, v, d = project(np.array([X[c] for c in corners]), np.array([Y[c] for c in corners]),
                              np.array([Z[c] for c in corners]), shift)
            polys.append(np.column_stack([u, v]))
            colours.append(terrain_colour(Z[j:j + 2, i:i + 2].mean(), normal))
            depths.append(d.mean())
    order = np.argsort(depths)[::-1]
    ax.add_collection(PolyCollection([polys[k] for k in order], facecolors=[colours[k] for k in order],
                                     edgecolors=[colours[k] for k in order], linewidths=0.25))


def draw_slab(ax, top, shift):
    """Front and right faces of the terrain block, below the given top-surface function."""
    x = np.linspace(0, LX, 200)
    y = np.linspace(0, LY, 120)
    for xs, ys, fill in ((x, np.zeros_like(x), "#BDBDBD"), (np.full_like(y, LX), y, "#9E9E9E")):
        zs = top(xs, ys)
        u, v, _ = project(np.r_[xs, xs[::-1]], np.r_[ys, ys[::-1]], np.r_[zs, np.full_like(zs, -SLAB)], shift)
        ax.fill(u, v, color=fill, lw=0.5, ec=EDGE, zorder=2)


# Airflow -----------------------------------------------------------------------------------

def arrowhead(ax, p, q, colour, size, zorder):
    length = np.linalg.norm(q - p)
    if length < 1e-9:
        return
    direction = (q - p) / length
    normal = np.array([-direction[1], direction[0]])
    tip = q + direction * size * 0.6
    ax.fill(*np.array([tip, q - direction * size * 0.6 + normal * size * 0.55,
                       q - direction * size * 0.6 - normal * size * 0.55]).T,
            color=colour, lw=0, zorder=zorder)


def column(ax, base, height, style, amp, turns, zorder, shift):
    """Rising-air column: translucent envelope, a wavy ascent line and an upward arrowhead."""
    u0, v0, _ = project(*base, shift)
    top = v0 + height * np.cos(EPS)
    s = np.linspace(0, 1, 240)
    half = amp * (1.55 + 0.35 * s)
    cap = np.linspace(0, np.pi, 40)
    envelope = np.r_[np.column_stack([u0 - half, v0 + s * (top - v0)]),
                     np.column_stack([u0 - half[-1] * np.cos(cap), top + 0.9 * half[-1] * np.sin(cap)]),
                     np.column_stack([u0 + half[::-1], v0 + s[::-1] * (top - v0)])]
    ax.fill(*envelope.T, color=style["envelope"], alpha=style["alpha"], lw=0, zorder=zorder)
    taper = np.clip(6 * s, 0, 1) * np.clip((0.97 - s) / 0.1, 0, 1)
    wave = np.column_stack([u0 + amp * np.sin(2 * np.pi * turns * s) * taper, v0 + s * (top - v0)])
    ax.plot(*wave.T, color=style["color"], lw=style["lw"], solid_capstyle="round", zorder=zorder + 0.1)
    arrowhead(ax, wave[-6], wave[-1], style["color"], 1.5 * style["lw"], zorder + 0.2)


def upslope_path(start, f):
    """Follow the terrain gradient uphill from a slope point until the crest is reached."""
    x, y = start
    points = [(x, y)]
    for _ in range(4000):
        gx, gy = gradient(f, x, y)
        norm = np.hypot(gx, gy)
        if y >= ridge_y(x) - 0.9 or norm < 1e-3:
            break
        x, y = x + 0.08 * gx / norm, y + 0.08 * gy / norm
        points.append((x, y))
    return np.array(points)


def draw_upslope(ax, path, f, shift):
    u, v, _ = project(path[:, 0], path[:, 1], f(path[:, 0], path[:, 1]) + 0.35, shift)
    ax.plot(u, v, color=STRONG["color"], lw=1.25, solid_capstyle="round", zorder=5)
    for k in (len(u) // 2, len(u) - 1):
        p, q = np.array([u[k - 4], v[k - 4]]), np.array([u[k], v[k]])
        arrowhead(ax, p, q, STRONG["color"], 1.3, 5.1)


def mountain_panel(ax):
    draw_heightfield(ax, mountain, 0.0)
    draw_slab(ax, mountain, 0.0)
    x = np.linspace(0, LX, 300)
    u, v, _ = project(x, ridge_y(x), mountain(x, ridge_y(x)) + 0.05)
    ax.plot(u, v, color="#3C3C3C", lw=0.7, zorder=4)
    for xs, height in zip(SPURS, (16, 19, 15, 20, 17)):
        for offset in (-2.6, 2.6):
            draw_upslope(ax, upslope_path((xs + offset, 5.0), mountain), mountain, 0.0)
        yc = ridge_y(xs)
        column(ax, (xs, yc, mountain(xs, yc)), height, STRONG, amp=1.25, turns=4.5, zorder=6, shift=0.0)


# Lowland terrain ---------------------------------------------------------------------------

GROUND = 0.6


def flat(x, y):
    return np.full_like(np.asarray(x, dtype=float), GROUND)


def patch(ax, xy, colour, shift, zorder=3, edge="#8C8C7A", lw=0.35):
    xy = np.asarray(xy, dtype=float)
    u, v, _ = project(xy[:, 0], xy[:, 1], np.full(len(xy), GROUND), shift)
    ax.fill(u, v, color=colour, ec=edge, lw=lw, zorder=zorder)


def fields(ax, shift, rng):
    """Irregular patchwork: slanted strip boundaries, each strip split at its own depths."""
    palette = ["#A9C08A", "#BACB94", "#C8D2A1", "#D6CDA5", "#C7BC93", "#A2B985", "#BCC78F", "#D2D6A6"]
    cuts = [0.0, 9.5, 18.0, 26.5, 35.0, 43.5, 53.0, LX]
    slant = [0.0] + list(rng.uniform(-0.12, 0.12, len(cuts) - 2)) + [0.0]
    for k in range(len(cuts) - 1):
        ys = np.r_[0.0, np.sort(rng.uniform(3, LY - 3, rng.integers(2, 4))), LY]
        for a, b in zip(ys[:-1], ys[1:]):
            left = lambda y: cuts[k] + slant[k] * (y - LY / 2)
            right = lambda y: cuts[k + 1] + slant[k + 1] * (y - LY / 2)
            patch(ax, [(left(a), a), (right(a), a), (right(b), b), (left(b), b)], rng.choice(palette), shift, zorder=2.5)


def ploughed(ax, x0, y0, w, d, shift):
    patch(ax, [(x0, y0), (x0 + w, y0), (x0 + w, y0 + d), (x0, y0 + d)], "#6E5038", shift)
    for x in np.arange(x0 + 0.6, x0 + w, 0.9):
        u, v, _ = project(np.array([x, x]), np.array([y0 + 0.3, y0 + d - 0.3]), np.array([GROUND] * 2), shift)
        ax.plot(u, v, color="#8A6A4E", lw=0.35, zorder=3.1)


def parking(ax, x0, y0, w, d, shift):
    patch(ax, [(x0, y0), (x0 + w, y0), (x0 + w, y0 + d), (x0, y0 + d)], "#54575B", shift, edge="#3C3C3C")
    for x in np.arange(x0 + 0.8, x0 + w - 0.4, 0.9):
        for ya, yb in ((y0 + 0.3, y0 + 1.4), (y0 + d - 1.4, y0 + d - 0.3)):
            u, v, _ = project(np.array([x, x]), np.array([ya, yb]), np.array([GROUND] * 2), shift)
            ax.plot(u, v, color="#E8E8E8", lw=0.3, zorder=3.1)


QUARRY_STEP = 1.0  # depth of each quarry bench


def quarry(ax, cx, cy, shift):
    """Open pit cut in benches: each level shows its lit back wall above a paler bench floor."""
    t = np.linspace(0, 2 * np.pi, 80, endpoint=False)
    r = 3.8 + 0.25 * np.sin(3 * t) + 0.15 * np.cos(5 * t)

    def outline(scale, z):
        u, v, _ = project(cx + 1.25 * scale * r * np.cos(t), cy + scale * r * np.sin(t), np.full(len(t), z), shift)
        return np.column_stack([u, v])

    opening = None
    for k, (scale, wall, floor) in enumerate(((1.0, "#8E806A", "#DDD5C4"), (0.55, "#7E715D", "#CFC5B1"))):
        top, bottom = outline(scale, GROUND - k * QUARRY_STEP), outline(scale, GROUND - (k + 1) * QUARRY_STEP)
        rim = ax.fill(*top.T, color=wall, ec="#6E6352", lw=0.35, zorder=3 + 0.1 * k)[0]
        base = ax.fill(*bottom.T, color=floor, lw=0, zorder=3.05 + 0.1 * k)[0]
        if opening is not None:
            rim.set_clip_path(opening)
        base.set_clip_path(rim)
        opening = rim


def box(x0, y0, w, d, h, roof, walls, ridge=0.0, shift=0.0):
    """Polygons of a building seen from the front right; ridge > 0 adds a pitched roof along x."""
    def P(x, y, z):
        u, v, _ = project(x, y, z, shift)
        return (u, v)
    z0, z1, ym = GROUND, GROUND + h, y0 + d / 2
    faces = [([P(x0, y0, z0), P(x0 + w, y0, z0), P(x0 + w, y0, z1), P(x0, y0, z1)], walls[0])]
    if ridge:
        faces.append(([P(x0 + w, y0, z0), P(x0 + w, y0 + d, z0), P(x0 + w, y0 + d, z1),
                       P(x0 + w, ym, z1 + ridge), P(x0 + w, y0, z1)], walls[1]))
        faces.append(([P(x0, ym, z1 + ridge), P(x0 + w, ym, z1 + ridge), P(x0 + w, y0 + d, z1), P(x0, y0 + d, z1)], roof[1]))
        faces.append(([P(x0, y0, z1), P(x0 + w, y0, z1), P(x0 + w, ym, z1 + ridge), P(x0, ym, z1 + ridge)], roof[0]))
    else:
        faces.append(([P(x0 + w, y0, z0), P(x0 + w, y0 + d, z0), P(x0 + w, y0 + d, z1), P(x0 + w, y0, z1)], walls[1]))
        faces.append(([P(x0, y0, z1), P(x0 + w, y0, z1), P(x0 + w, y0 + d, z1), P(x0, y0 + d, z1)], roof[0]))
    return faces, project(x0 + w / 2, y0 + d / 2, z0)[2]


def lowland_panel(ax, shift):
    rng = np.random.default_rng(7)
    draw_slab(ax, flat, shift)
    u, v, _ = project(np.array([0, LX, LX, 0]), np.array([0, 0, LY, LY]), np.full(4, GROUND), shift)
    ax.fill(u, v, color="#B9C993", lw=0, zorder=2.4)
    fields(ax, shift, rng)
    # Heated surfaces of different kinds, placed irregularly.
    ploughed(ax, 5.5, 19.5, 9.0, 7.0, shift)
    ploughed(ax, 3.5, 7.0, 5.0, 4.0, shift)
    ploughed(ax, 50.0, 14.5, 5.0, 4.0, shift)
    ploughed(ax, 44.0, 2.5, 8.8, 7.3, shift)
    parking(ax, 26.8, 10.8, 6.5, 4.5, shift)
    quarry(ax, 22.0, 5.0, shift)
    objects = []
    for hx, hy, hw in ((53.5, 25.0, 1.9), (56.2, 25.9, 1.7), (54.4, 28.1, 1.8), (57.8, 28.6, 1.6),
                       (52.0, 27.6, 1.5), (59.5, 25.8, 1.7)):
        objects.append(box(hx, hy, hw, 1.6, 1.3, ("#B5543C", "#9C4632"), ("#EFE9DF", "#D6CFC3"), ridge=0.8, shift=shift))
    objects.append(box(33.5, 27.0, 7.0, 4.0, 2.2, ("#4B4E53",), ("#E4E1DA", "#C8C4BC"), shift=shift))
    styles = [
        ((10.0, 23.0), 13.0, 0.95, 3.0, 0.0),  # ploughed field
        ((6.0, 9.0), 9.5, 0.75, 2.5, 0.0),  # small ploughed field
        ((52.5, 16.5), 9.0, 0.70, 2.5, 0.0),  # small ploughed field, right
        ((48.5, 6.0), 10.5, 0.80, 2.5, 0.0),  # ploughed field, front right
        ((30.0, 13.0), 12.0, 0.85, 3.0, 0.0),  # parking lot
        ((22.0, 5.0), 11.0, 0.85, 2.5, -2 * QUARRY_STEP),  # quarry floor
        ((56.5, 27.3), 14.0, 0.95, 3.0, 0.0),  # village roofs
        ((37.0, 29.0), 12.5, 0.90, 3.0, 2.4),  # warehouse roof
    ]
    for (x, y), height, amp, turns, dz in styles:
        d = project(x, y, GROUND)[2]
        objects.append(("column", (x, y, GROUND + dz), height, amp, turns, d))
    objects.sort(key=lambda item: -item[-1])
    for k, item in enumerate(objects):
        z = 7 + 0.5 * k
        if item[0] == "column":
            _, base, height, amp, turns, _ = item
            column(ax, base, 1.15 * height, WEAK, amp=1.15 * amp, turns=turns, zorder=z, shift=shift)
        else:
            for poly, colour in item[0]:
                ax.fill(*np.array(poly).T, color=colour, ec="#6A6A6A", lw=0.3, zorder=z)


def main():
    OUT.mkdir(exist_ok=True)
    fig = plt.figure(figsize=(146 / 25.4, 48 / 25.4))
    ax = fig.add_axes([0, 0, 1, 1])
    mountain_panel(ax)
    shift = project(LX, LY, 0)[0] + GAP
    lowland_panel(ax, shift)
    ax.set_aspect("equal")
    ax.axis("off")
    ax.autoscale_view()
    for suffix in ("pdf", "png"):
        fig.savefig(OUT / f"thermal-mechanism.{suffix}", dpi=400, bbox_inches="tight", pad_inches=0.01, transparent=False)
    plt.close(fig)


if __name__ == "__main__":
    main()
