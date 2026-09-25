"""Draw the slide-10 block diagrams: sunlit mountain slopes against scattered lowland triggers.

The relief comes from the IGN RGE ALTI tiles saved for the plane-cell slides: the Tournette
massif above Lake Annecy (Alps cell), seen from the west, and a flat stretch of the
Champagne cell floor. Land cover, heated sources, rising air and circling paths are schematic.
One sun direction lights both blocks, including hillshade and cast shadows.
"""
from pathlib import Path
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.path import Path as MPath
from PIL import Image
from scipy.ndimage import binary_dilation, gaussian_filter, map_coordinates

HERE = Path(__file__).resolve().parent
CELLS = HERE / "assets/plane-cells"
OUT = Path(sys.argv[1]) if len(sys.argv) > 1 else HERE / "assets"

PHI, EPS = np.radians(22), np.radians(30)  # camera azimuth and elevation
NX, NY = 3000, 1500  # texels per block: unit width, half-unit depth
SS = 2  # supersampling of the terrain raster
PX = 1400 * SS  # raster pixels per unit of block width
SUN_AZ, SUN_EL = np.radians(235), np.radians(50)  # compass azimuth: south-west, mid-afternoon
# Local frame: x to the right along the front edge, y away from the viewer, z up. Both blocks face
# west, so x points south and y east; the toward-sun vector below uses that frame for both.
SUN = np.array([-np.cos(SUN_AZ) * np.cos(SUN_EL), np.sin(SUN_AZ) * np.cos(SUN_EL), np.sin(SUN_EL)])
GAP = 0.16  # screen gap between blocks
FIG_W, FIG_H = 146 / 25.4, 146 / 25.4 / 3

V_TOP = 0.70  # screen height where every column fades out: a common thermal top
SUN_UV = (0.84, 0.68)  # sun disc in each panel's screen coordinates
MOUNTAIN_REACH, LOWLAND_REACH = 0.42, 0.60  # longest ray, screen units

RISING = "#EE7A3B"
RISING_DARK = "#C4541D"
PATH = "#9A3A12"
RAY = "#E2A62B"
SUN_COLOUR = "#F3C646"
WING = "#1F3A63"
EDGE = "#5A5750"


def project(x, y, z):
    """Orthographic screen coordinates (u, v) and depth (larger is further away)."""
    c, s = np.cos(PHI), np.sin(PHI)
    x1, y1 = x * c - y * s, x * s + y * c
    return x1, z * np.cos(EPS) + y1 * np.sin(EPS), y1 * np.cos(EPS) - z * np.sin(EPS)


def noise(shape, cell, rng, octaves=1):
    """Smooth random field, unit variance, with features about ``cell`` texels across."""
    total = np.zeros(shape)
    for k in range(octaves):
        size = cell / 2 ** k
        coarse = rng.standard_normal((int(shape[0] / size) + 4, int(shape[1] / size) + 4))
        Y, X = np.meshgrid(np.arange(shape[0]) / size + 1, np.arange(shape[1]) / size + 1, indexing="ij")
        total += 0.55 ** k * map_coordinates(coarse, [Y, X], order=3, mode="nearest")
    return (total - total.mean()) / total.std()


def smoothstep(a, b, t):
    t = np.clip((t - a) / (b - a), 0, 1)
    return t * t * (3 - 2 * t)


def mix(a, b, t):
    t = np.asarray(t)[..., None]
    return np.asarray(a) * (1 - t) + np.asarray(b) * t


# Terrain ---------------------------------------------------------------------------------------

class Block:
    """A heightfield in block units (width 1), its colour texture and its rendered raster."""

    def __init__(self, dem_m, width_m, ve, base):
        ny, nx = dem_m.shape
        Y, X = np.meshgrid(np.linspace(0, ny - 1, NY), np.linspace(0, nx - 1, NX), indexing="ij")
        self.elev = map_coordinates(dem_m, [Y, X], order=3, mode="nearest")  # metres
        self.width_m, self.ve = width_m, ve
        self.texel_m = width_m / (NX - 1)
        self.floor = self.elev.min()
        self.base = base  # block units below the lowest ground
        self.extra = np.zeros_like(self.elev)  # canopy height in metres, drawn and casting shadows
        self.blockers = np.zeros_like(self.elev)  # buildings: cast shadows only, drawn as vectors

    def z(self, metres):
        return (metres - self.floor) * self.ve / self.width_m

    def ground(self, x, y):
        """Ground height (block units) at block coordinates, bilinear."""
        x, y = np.broadcast_arrays(np.asarray(x, float), np.asarray(y, float))
        coords = [np.atleast_1d(y) * 2 * (NY - 1), np.atleast_1d(x) * (NX - 1)]
        return self.z(map_coordinates(self.elev, coords, order=1, mode="nearest")).reshape(x.shape)

    def surface(self):
        return self.z(self.elev + self.extra)

    def normals(self, height_m):
        gy, gx = np.gradient(height_m * self.ve, self.texel_m)
        n = np.stack([-gx, -gy, np.ones_like(gx)], axis=-1)
        return n / np.linalg.norm(n, axis=-1, keepdims=True)

    def shadow(self, height_m, step=2.0):
        """1 where the sun is visible, 0 in cast shadow; ray-marched on a coarser copy."""
        k = 4
        h = gaussian_filter(height_m, 1)[::k, ::k] * self.ve
        dx = self.texel_m * k
        sy, sx = np.meshgrid(np.arange(h.shape[0], dtype=float), np.arange(h.shape[1], dtype=float), indexing="ij")
        horizontal = np.hypot(SUN[0], SUN[1])
        ux, uy, rise = SUN[0] / horizontal, SUN[1] / horizontal, SUN[2] / horizontal * dx
        lit = np.ones(h.shape)
        top = h.max()
        for i in range(1, 4000):
            t = i * step
            px, py = sx + ux * t, sy + uy * t
            inside = (px >= 0) & (px <= h.shape[1] - 1) & (py >= 0) & (py <= h.shape[0] - 1)
            if not inside.any():
                break
            ray = h + rise * t
            if (ray[inside] > top).all():
                break
            terrain = map_coordinates(h, [py, px], order=1, mode="nearest")
            lit = np.minimum(lit, np.where(inside, np.clip((ray - terrain) / (0.6 * dx) + 1, 0, 1), 1))
        lit = gaussian_filter(lit, 0.8)
        Y, X = np.meshgrid(np.linspace(0, h.shape[0] - 1, NY), np.linspace(0, h.shape[1] - 1, NX), indexing="ij")
        return map_coordinates(lit, [Y, X], order=1)

    def light(self, albedo, height_m, shade_height_m=None):
        n = self.normals(height_m)
        self.sunlit = self.shadow(height_m if shade_height_m is None else shade_height_m)
        direct = np.clip(n @ SUN, 0, 1) * self.sunlit
        sky = 0.5 + 0.5 * n[..., 2]
        return albedo * (0.34 * sky + 0.78 * direct)[..., None]

    def render(self, colour):
        """Z-buffered point splat of the heightfield: RGBA raster, depth buffer and screen extent."""
        Y, X = np.meshgrid(np.linspace(0, 0.5, NY), np.linspace(0, 1, NX), indexing="ij")
        U, V, D = project(X, Y, self.surface())
        corners = [project(x, y, z) for x in (0, 1) for y in (0, 0.5) for z in (-self.base, self.surface().max())]
        u0 = min(c[0] for c in corners) - 0.01
        u1 = max(c[0] for c in corners) + 0.01
        v0 = min(c[1] for c in corners) - 0.01
        v1 = max(c[1] for c in corners) + 0.01
        W, H = int((u1 - u0) * PX), int((v1 - v0) * PX)
        W, H = W - W % SS, H - H % SS
        col = np.round((U - u0) * PX).astype(np.int64)
        row = (v1 - V) * PX
        # A steep texel covers the screen rows down to its nearer neighbour.
        # Cover down to the lowest neighbour so steep flanks leave no holes.
        gap = np.zeros_like(row)
        gap[1:] = np.maximum(gap[1:], row[:-1] - row[1:])
        gap[:-1] = np.maximum(gap[:-1], row[1:] - row[:-1])
        gap[:, 1:] = np.maximum(gap[:, 1:], row[:, :-1] - row[:, 1:])
        gap[:, :-1] = np.maximum(gap[:, :-1], row[:, 1:] - row[:, :-1])
        span = np.clip(np.ceil(gap), 1, 12).astype(int)
        row = np.round(row).astype(np.int64)
        rows, cols, depths, index = [], [], [], []
        flat_index = np.arange(row.size).reshape(row.shape)
        for k in range(span.max()):
            m = span > k
            rows.append(row[m] + k)
            cols.append(col[m])
            depths.append(D[m] + k * 1e-6)
            index.append(flat_index[m])
        rows, cols, depths, index = map(np.concatenate, (rows, cols, depths, index))
        ok = (rows >= 0) & (rows < H) & (cols >= 0) & (cols < W)
        p = rows[ok] * W + cols[ok]
        depths, index = depths[ok], index[ok]
        order = np.lexsort((depths, p))
        first = order[np.r_[True, p[order][1:] != p[order][:-1]]]
        rgba = np.zeros((H * W, 4))
        rgba[p[first], :3] = colour.reshape(-1, 3)[index[first]]
        rgba[p[first], 3] = 1
        depth = np.full(H * W, np.inf)
        depth[p[first]] = depths[first]
        # Aerial perspective: distant terrain fades slightly towards the sky colour.
        far = np.clip((depth - D.min()) / (D.max() - D.min()), 0, 1)
        rgba[:, :3] = mix(rgba[:, :3], (0.83, 0.87, 0.91), 0.20 * far ** 1.5)
        rgba = rgba.reshape(H, W, 4)
        rgba[..., :3] *= rgba[..., 3:]
        small = rgba.reshape(H // SS, SS, W // SS, SS, 4).mean(axis=(1, 3))
        alpha = small[..., 3:]
        small[..., :3] = np.where(alpha > 0, small[..., :3] / np.maximum(alpha, 1e-9), 1)
        self.image = np.clip(small, 0, 1)
        self.depth = depth.reshape(H, W)[::SS, ::SS]
        self.extent = (u0, u0 + W / PX, v1 - H / PX, v1)
        return self.image

    def pixel(self, u, v):
        u0, u1, v0, v1 = self.extent
        c = np.clip(((np.asarray(u) - u0) * PX / SS).astype(int), 0, self.depth.shape[1] - 1)
        r = np.clip(((v1 - np.asarray(v)) * PX / SS).astype(int), 0, self.depth.shape[0] - 1)
        return r, c

    def unproject(self, u, v):
        """Block coordinates of the terrain seen at screen point (u, v), or None over the sky."""
        d = self.depth[self.pixel(u, v)]
        if not np.isfinite(d):
            return None
        y1, z = np.sin(EPS) * v + np.cos(EPS) * d, np.cos(EPS) * v - np.sin(EPS) * d
        return u * np.cos(PHI) + y1 * np.sin(PHI), -u * np.sin(PHI) + y1 * np.cos(PHI), z

    def lit_at(self, x, y):
        return map_coordinates(self.sunlit, [[y * 2 * (NY - 1)], [x * (NX - 1)]], order=1)[0]

    def visible(self, x, y, z):
        """True where the block-unit point is not hidden by terrain."""
        u, v, d = project(np.asarray(x, float), np.asarray(y, float), np.asarray(z, float))
        return d <= self.depth[self.pixel(u, v)] + 2e-3


def heat(colour, xy, points, radius, strength=0.55):
    """Blend a warm tint around heated source points (block units)."""
    X, Y = xy
    glow = np.zeros(X.shape)
    for x, y in points:
        glow = np.maximum(glow, np.exp(-((X - x) ** 2 + (Y - y) ** 2) / (2 * radius ** 2)))
    return mix(colour, (0.93, 0.55, 0.30), strength * glow)


# Mountain block --------------------------------------------------------------------------------

def mountain_block(sources=((0.19, 0.095), (0.556, 0.307), (0.80, 0.37)), draw=True):
    with Image.open(CELLS / "alps-dem.tif") as im:
        dem = np.asarray(im, dtype=float)
    # Rows run north to south, columns west to east. Seen from the west: x is south, y is east.
    crop = dem[150:630, 405:645].T  # 12 km along the front, 6 km deep
    block = Block(gaussian_filter(crop, 1.5), 12000.0, ve=1.7, base=0.05)
    rng = np.random.default_rng(3)
    elev = block.elev
    gy, gx = np.gradient(elev, block.texel_m)
    slope = np.degrees(np.arctan(np.hypot(gx, gy)))
    shape = elev.shape
    broad = noise(shape, 160, rng, octaves=3)
    patches = noise(shape, 80, rng, octaves=3)

    # Natural-colour relief: pasture on gentle ground, forest on the slopes, rock where steep or high.
    colour = mix((0.68, 0.73, 0.48), (0.61, 0.69, 0.43), smoothstep(-1, 1, broad))
    forest = mix((0.27, 0.38, 0.22), (0.32, 0.42, 0.25), smoothstep(-1, 1, patches))
    wooded = smoothstep(9, 16, slope + 2 * patches) * (1 - smoothstep(1400, 1600, elev + 60 * broad))
    colour = mix(colour, forest, wooded)
    alpine = mix((0.69, 0.69, 0.50), (0.63, 0.65, 0.45), smoothstep(-1, 1, patches))
    colour = mix(colour, alpine, smoothstep(1450, 1650, elev + 60 * broad) * (1 - wooded))
    rock = mix((0.68, 0.65, 0.60), (0.75, 0.72, 0.67), smoothstep(-1, 1, patches))
    rocky = np.maximum(smoothstep(34, 42, slope + 2 * patches), smoothstep(2000, 2200, elev + 60 * patches))
    colour = mix(colour, rock, rocky)
    lake = elev < elev.min() + 1.0
    colour[lake] = (0.40, 0.56, 0.66)
    X, Y = np.meshgrid(np.linspace(0, 1, NX), np.linspace(0, 0.5, NY))
    block.sources = list(sources)
    colour = heat(colour, (X, Y), block.sources, 0.010, strength=0.5)
    shaded = block.light(colour, elev)
    ao = 1 - 0.30 * np.clip((gaussian_filter(elev, 30) - elev) / 200, 0, 1)
    shaded *= ao[..., None]
    shaded[lake] = mix(shaded[lake], (0.45, 0.61, 0.71), 0.7)
    block.slope, block.lit = slope, np.clip(shaded, 0, 1)
    if draw:
        block.render(block.lit)
    return block


# Lowland block ---------------------------------------------------------------------------------

def rasterise(polygons, X, Y):
    """Index of the polygon containing each texel, -1 outside all of them."""
    label = np.full(X.shape, -1)
    for k, poly in enumerate(polygons):
        poly = np.asarray(poly)
        (x0, y0), (x1, y1) = poly.min(axis=0), poly.max(axis=0)
        m = (X >= x0) & (X <= x1) & (Y >= y0) & (Y <= y1)
        inside = MPath(poly).contains_points(np.column_stack([X[m], Y[m]]))
        sub = label[m]
        sub[inside] = k
        label[m] = sub
    return label


def field_layout(rng):
    """Slanted strips split at irregular depths: a patchwork of fields in block units."""
    cuts = np.array([0.0, 0.11, 0.24, 0.35, 0.47, 0.60, 0.72, 0.85, 1.0])
    slant = np.r_[0.0, rng.uniform(-0.08, 0.08, len(cuts) - 2), 0.0]
    fields = []
    for k in range(len(cuts) - 1):
        ys = np.r_[0.0, np.sort(rng.uniform(0.07, 0.43, rng.integers(1, 3))), 0.5]
        for a, b in zip(ys[:-1], ys[1:]):
            left = lambda y: cuts[k] + slant[k] * (y - 0.25)
            right = lambda y: cuts[k + 1] + slant[k + 1] * (y - 0.25)
            fields.append([(left(a), a), (right(a), a), (right(b), b), (left(b), b)])
    return fields, cuts, slant


def plant(block, colour, trees, rng):
    """Raise a round crown on a short trunk for each tree (x, y, radius in block units)."""
    to_m = block.width_m / block.ve
    for x, y, r in trees:
        cx, cy, rr = x * (NX - 1), y * 2 * (NY - 1), r * (NX - 1)
        i0, i1 = max(int(cy - rr) - 1, 0), min(int(cy + rr) + 2, NY)
        j0, j1 = max(int(cx - rr) - 1, 0), min(int(cx + rr) + 2, NX)
        if i0 >= i1 or j0 >= j1:
            continue
        I, J = np.meshgrid(np.arange(i0, i1), np.arange(j0, j1), indexing="ij")
        d2 = ((J - cx) ** 2 + (I - cy) ** 2) / rr ** 2
        crown = np.where(d2 < 1, (0.7 * r + 1.0 * r * np.sqrt(np.clip(1 - d2, 0, 1))) * to_m, 0)
        window = block.extra[i0:i1, j0:j1]
        top = crown > window
        window[top] = crown[top]
        tint = np.array([0.25, 0.37, 0.20]) * (1 + 0.12 * rng.standard_normal()) + rng.uniform(-0.02, 0.03, 3)
        colour[i0:i1, j0:j1][top] = tint


def scatter(mask_fn, spacing, radius, rng, box):
    """Jittered grid of trees inside a region."""
    x0, x1, y0, y1 = box
    trees = []
    for y in np.arange(y0, y1, spacing * 0.87):
        for x in np.arange(x0, x1, spacing):
            px, py = x + rng.uniform(-0.35, 0.35) * spacing, y + rng.uniform(-0.35, 0.35) * spacing
            if mask_fn(px, py):
                trees.append((px, py, radius * rng.uniform(0.8, 1.15)))
    return trees


def row_of_trees(a, b, spacing, radius, rng, keep=0.85):
    a, b = np.asarray(a), np.asarray(b)
    n = int(np.linalg.norm(b - a) / spacing)
    return [tuple(a + (b - a) * t) + (radius * rng.uniform(0.8, 1.15),)
            for t in np.linspace(0, 1, n) if rng.uniform() < keep]


def lowland_block():
    with Image.open(CELLS / "champagne-dem.tif") as im:
        dem = np.asarray(im, dtype=float)
    crop = dem[250:330, 150:190].T  # 2 km along the front, 1 km deep: the flat valley floor
    block = Block(gaussian_filter(crop, 1.5), 2000.0, ve=1.6, base=0.035)
    rng = np.random.default_rng(11)
    shape = block.elev.shape
    X, Y = np.meshgrid(np.linspace(0, 1, NX), np.linspace(0, 0.5, NY))
    fine = noise(shape, 5, rng, octaves=2)
    mottle = noise(shape, 60, rng, octaves=3)

    fields, cuts, slant = field_layout(rng)
    label = rasterise(fields, X, Y)
    crops = [  # base colour, stripe spacing (block units), stripe contrast
        ((0.82, 0.76, 0.54), 0.0035, 0.04),  # ripe cereal
        ((0.58, 0.67, 0.39), 0.0030, 0.05),  # green crop in rows
        ((0.60, 0.68, 0.42), 0.0, 0.0),  # meadow
        ((0.71, 0.74, 0.50), 0.0040, 0.03),  # young crop
        ((0.77, 0.71, 0.54), 0.0030, 0.04),  # stubble
    ]
    ploughed = ((0.50, 0.39, 0.29), 0.0028, 0.10)
    # Heated sources: three bare fields, the car park, the warehouse roof and two house roofs.
    field_sources = [(0.14, 0.15), (0.38, 0.12), (0.93, 0.05)]
    dark = {int(label[int(y * 2 * (NY - 1)), int(x * (NX - 1))]) for x, y in field_sources}
    colour = np.zeros(shape + (3,))
    for k in range(len(fields)):
        m = label == k
        base, spacing, contrast = ploughed if k in dark else crops[(3 * k + 1) % len(crops)]
        angle = 0.35 if k in dark else rng.uniform(0, np.pi)
        value = 1 + 0.04 * rng.standard_normal() + 0.04 * mottle[m] + 0.025 * fine[m]
        if spacing:
            phase = (X[m] * np.cos(angle) + Y[m] * np.sin(angle)) / spacing
            value = value + contrast * np.sin(2 * np.pi * phase)
        colour[m] = np.asarray(base) * value[:, None]
    edges = np.zeros(shape, bool)
    edges[:, 1:] |= label[:, 1:] != label[:, :-1]
    edges[1:, :] |= label[1:, :] != label[:-1, :]
    edges = binary_dilation(edges, iterations=2)
    colour[edges] = mix(colour[edges], (0.60, 0.65, 0.43), 0.8)

    # A road across the plain, a lane into the village, and the industrial plot behind the road.
    road_y = 0.285 + 0.012 * np.sin(5 * X + 0.5) + 0.02 * X
    road = np.abs(Y - road_y) < 0.0032
    lane = (np.abs(X - (0.845 + 0.06 * (Y - 0.3))) < 0.0026) & (Y > road_y) & (Y < 0.5)
    village = ((X - 0.87) / 0.12) ** 2 + ((Y - 0.40) / 0.085) ** 2 < 1
    colour[village] = mix((0.56, 0.64, 0.41), (0.64, 0.68, 0.46), smoothstep(-1, 1, fine[village]))
    plot = (X > 0.34) & (X < 0.72) & (Y > road_y + 0.012) & (Y < 0.40)
    colour[plot] = mix((0.60, 0.65, 0.44), (0.66, 0.67, 0.49), smoothstep(-1, 1, mottle[plot]))
    park = (X > 0.355) & (X < 0.425) & (Y > 0.333) & (Y < 0.378)
    colour[park] = (0.36, 0.37, 0.38) * (1 + 0.03 * fine[park])[:, None]
    stalls = park & (np.abs(((X - 0.355) / 0.0048) % 1 - 0.5) > 0.45) & (np.abs(Y - 0.3555) > 0.005)
    colour[stalls] = (0.84, 0.84, 0.82)
    for k, (cx, cy) in enumerate([(0.3645, 0.341), (0.3790, 0.341), (0.3935, 0.369), (0.4080, 0.341), (0.4175, 0.369)]):
        car = (np.abs(X - cx) < 0.0019) & (np.abs(Y - cy) < 0.0036)
        colour[car] = [(0.75, 0.75, 0.76), (0.28, 0.33, 0.45), (0.62, 0.20, 0.18), (0.88, 0.88, 0.86),
                       (0.25, 0.25, 0.27)][k]
    yard = (X > 0.600) & (X < 0.712) & (Y > 0.325) & (Y < 0.395)
    colour[yard] = (0.63, 0.62, 0.59) * (1 + 0.02 * fine[yard])[:, None]
    colour[road | lane] = (0.50, 0.50, 0.49)

    trees = []
    wood = lambda x, y: ((x - 0.12) / 0.12) ** 2 + ((y - 0.43) / 0.075) ** 2 < 1 + 0.25 * np.sin(40 * x) * np.cos(30 * y)
    trees += scatter(wood, 0.0085, 0.0055, rng, (0.0, 0.26, 0.34, 0.5))
    copse = lambda x, y: ((x - 0.575) / 0.035) ** 2 + ((y - 0.16) / 0.025) ** 2 < 1
    trees += scatter(copse, 0.0085, 0.0055, rng, (0.53, 0.62, 0.13, 0.19))
    for k, (y0, y1) in ((2, (0.02, 0.26)), (4, (0.05, 0.27)), (6, (0.14, 0.27))):
        f = lambda y: cuts[k] + slant[k] * (y - 0.25)
        trees += row_of_trees((f(y0), y0), (f(y1), y1), 0.0065, 0.0046, rng, keep=0.9)
    xs = np.linspace(0.02, 0.98, 70)
    trees += [(x, 0.285 + 0.012 * np.sin(5 * x + 0.5) + 0.02 * x - 0.0085, 0.0045) for x in xs[::2]
              if not 0.30 < x < 0.74 and rng.uniform() < 0.8]
    block.houses = [  # x, y, width, depth; the first two feed thermals
        (0.805, 0.360, 0.030, 0.019), (0.882, 0.398, 0.028, 0.018),
        (0.858, 0.335, 0.027, 0.018), (0.940, 0.392, 0.027, 0.018), (0.912, 0.350, 0.026, 0.018),
        (0.835, 0.432, 0.026, 0.018), (0.905, 0.452, 0.027, 0.018), (0.772, 0.405, 0.024, 0.017),
    ]
    block.warehouse = (0.610, 0.340, 0.090, 0.045)
    footprints = [(x - 0.004, y - 0.004, w + 0.008, d + 0.008) for x, y, w, d in block.houses + [block.warehouse]]

    def clear(x, y):
        return not any(a < x < a + w and b < y < b + d for a, b, w, d in footprints)

    gardens = scatter(lambda x, y: ((x - 0.87) / 0.11) ** 2 + ((y - 0.40) / 0.075) ** 2 < 1 and clear(x, y)
                      and abs(x - (0.845 + 0.06 * (y - 0.3))) > 0.008, 0.02, 0.005, rng, (0.75, 1.0, 0.32, 0.49))
    trees += [t for t in gardens if rng.uniform() < 0.45]
    trees += [(0.30, 0.19, 0.006), (0.745, 0.21, 0.0065), (0.06, 0.24, 0.0055), (0.82, 0.14, 0.006)]
    trees = [t for t in trees if clear(t[0], t[1]) and not (0.34 < t[0] < 0.72 and 0.32 < t[1] < 0.40)]
    plant(block, colour, trees, rng)

    blockers = np.zeros(shape)
    for (x, y, w, d), h in zip(block.houses + [block.warehouse], [HOUSE_H + HOUSE_PITCH] * len(block.houses) + [SHED_H]):
        blockers[(X > x) & (X < x + w) & (Y > y) & (Y < y + d)] = h * block.width_m / block.ve
    park_centre = (0.39, 0.3555)
    block.sources = field_sources + [park_centre]
    colour = heat(colour, (X, Y), block.sources, 0.012, strength=0.30)
    height = block.elev + block.extra
    block.lit = np.clip(block.light(colour, height, shade_height_m=height + blockers), 0, 1)
    block.render(block.lit)
    return block


# Vector overlays -------------------------------------------------------------------------------

HOUSE_H, HOUSE_PITCH, SHED_H = 0.0105, 0.0085, 0.021  # block units


def face_colour(base, normal, ambient=0.55):
    normal = np.asarray(normal, float) / np.linalg.norm(normal)
    light = ambient + (1.0 - ambient) * max(0.0, float(normal @ SUN)) / SUN[2]
    return tuple(np.clip(np.asarray(base) * min(light, 1.08), 0, 1))


def sides(ax, block, shift):
    """Front and left faces of the block, with a soil band and a thin outline."""
    x = np.linspace(0, 1, 600)
    y = np.linspace(0, 0.5, 300)
    for xs, ys, normal in ((x, np.zeros_like(x), (0, -1, 0)), (np.zeros_like(y), y, (-1, 0, 0))):
        top = block.ground(xs, ys)
        u, v, _ = project(np.r_[xs, xs[::-1]], np.r_[ys, ys[::-1]], np.r_[top, np.full_like(top, -block.base)])
        ax.fill(u + shift, v, color=face_colour((0.84, 0.81, 0.76), normal, 0.72), lw=0, zorder=3)
        u, v, _ = project(np.r_[xs, xs[::-1]], np.r_[ys, ys[::-1]], np.r_[top, (top - 0.007)[::-1]])
        ax.fill(u + shift, v, color=face_colour((0.60, 0.50, 0.40), normal, 0.72), lw=0, zorder=3.1)
        for z in (top, np.full_like(top, -block.base)):
            u, v, _ = project(xs, ys, z)
            ax.plot(u + shift, v, color=EDGE, lw=0.35, zorder=3.2)
    for x0, y0 in ((0, 0), (1, 0), (0, 0.5)):
        u, v, _ = project(np.array([x0, x0]), np.array([y0, y0]), np.array([-block.base, float(block.ground(x0, y0))]))
        ax.plot(u + shift, v, color=EDGE, lw=0.35, zorder=3.2)


def building(ax, x, y, w, d, h, roof, walls, shift, zorder, pitch=0.0, ground=0.0):
    """A box seen from the front left, with an optional pitched roof whose ridge runs along x."""
    def P(px, py, pz):
        u, v, _ = project(px, py, pz)
        return (u + shift, v)
    z0, z1, ym = ground, ground + h, y + d / 2
    polys = [([P(x, y, z0), P(x + w, y, z0), P(x + w, y, z1), P(x, y, z1)], face_colour(walls, (0, -1, 0)))]
    if pitch:
        polys += [
            ([P(x, y, z0), P(x, y + d, z0), P(x, y + d, z1), P(x, ym, z1 + pitch), P(x, y, z1)],
             face_colour(walls, (-1, 0, 0))),
            ([P(x, ym, z1 + pitch), P(x + w, ym, z1 + pitch), P(x + w, y + d, z1), P(x, y + d, z1)],
             face_colour(roof, (0, d / 2, pitch))),
            ([P(x, y, z1), P(x + w, y, z1), P(x + w, ym, z1 + pitch), P(x, ym, z1 + pitch)],
             face_colour(roof, (0, -d / 2, pitch))),
        ]
    else:
        polys += [
            ([P(x, y, z0), P(x, y + d, z0), P(x, y + d, z1), P(x, y, z1)], face_colour(walls, (-1, 0, 0))),
            ([P(x, y, z1), P(x + w, y, z1), P(x + w, y + d, z1), P(x, y + d, z1)], face_colour(roof, (0, 0, 1))),
        ]
    for poly, colour in polys:
        ax.fill(*np.array(poly).T, color=colour, ec=tuple(np.array(colour) * 0.75), lw=0.15, zorder=zorder,
                joinstyle="round")


def column(ax, block, base, shift, zorder, width=0.017, helix=False):
    """Rising air: a soft translucent column up to the common top, with an upward arrowhead."""
    if not block.visible(*base):
        print(f"warning: thermal base {base} is hidden")
    u0, v0, _ = project(*base)
    u0 += shift
    height = V_TOP - v0
    rows, cols = 240, 160
    s = np.linspace(0, 1, rows)[:, None]
    half = width * (0.75 + 1.1 * np.sqrt(s))  # a plume that widens with height
    span = width * 2.0
    uu = np.linspace(-span, span, cols)[None, :]
    across = np.exp(-0.5 * (uu / (0.62 * half)) ** 2)
    along = smoothstep(0, 0.04, s) * (1 - smoothstep(0.45, 1.0, s))
    rgba = np.zeros((rows, cols, 4))
    rgba[..., :3] = matplotlib.colors.to_rgb(RISING)
    rgba[..., 3] = 0.50 * across * along
    ax.imshow(rgba[::-1], extent=(u0 - span, u0 + span, v0, v0 + height), interpolation="bilinear",
              zorder=zorder, aspect="auto")
    if helix:
        helix_path(ax, base, shift, zorder, height, width)
    tip = v0 + 0.66 * height
    head_h, head_w = 0.020, 0.017
    ax.plot([u0, u0], [tip - 0.075, tip - head_h * 0.8], color=RISING_DARK, lw=0.8, solid_capstyle="butt",
            zorder=zorder + 0.3)
    ax.fill([u0 - head_w / 2, u0 + head_w / 2, u0], [tip - head_h, tip - head_h, tip], color=RISING_DARK, lw=0,
            zorder=zorder + 0.3)


def helix_path(ax, base, shift, zorder, height, width):
    """Circling flight path around the column axis; the far half passes behind the column."""
    x0, y0, z0 = base
    bottom, top, turns = 0.10 * height, 0.52 * height, 3
    # Start and end at the screen-left extreme of the circle, where the canopy is seen head-on.
    t_left = np.arctan2(np.sin(PHI), -np.cos(PHI))
    t = t_left + np.linspace(0, 2 * np.pi * turns, 1200)
    frac = (t - t[0]) / (t[-1] - t[0])
    r = 1.35 * width * (1 + 0.3 * frac)
    x, y = x0 + r * np.cos(t), y0 + r * np.sin(t)
    z = z0 + (bottom + (top - bottom) * frac) / np.cos(EPS)
    u, v, d = project(x, y, z)
    u += shift
    front = d < project(x0, y0, z0)[2]
    for mask, alpha, zo in ((~front, 0.5, zorder - 0.1), (front, 1.0, zorder + 0.2)):
        ax.plot(np.where(mask, u, np.nan), np.where(mask, v, np.nan), color=PATH, lw=0.55, alpha=alpha,
                solid_capstyle="round", zorder=zo)
    paraglider(ax, u[-1], v[-1], zorder + 0.4)


def paraglider(ax, u, v, zorder, size=0.06):
    """Canopy seen head-on above its pilot, banked towards the thermal axis on its right."""
    bank = np.radians(16)
    up, side = np.array([np.sin(bank), np.cos(bank)]), np.array([np.cos(bank), -np.sin(bank)])
    pilot = np.array([u, v])
    centre = pilot + up * 0.60 * size
    a = np.radians(np.linspace(-70, 70, 60))
    radius = 0.5 * size
    outer = centre + np.outer(radius * np.sin(a), side) + np.outer(0.55 * radius * (np.cos(a) - 1), up)
    inner = outer - np.outer((0.03 + 0.07 * np.cos(a) ** 0.5) * size, up)
    for k in np.linspace(4, 55, 5).astype(int):
        ax.plot([pilot[0], inner[k, 0]], [pilot[1], inner[k, 1]], color="#404040", lw=0.15, zorder=zorder - 0.01)
    ax.fill(*np.vstack([outer, inner[::-1]]).T, color=WING, lw=0, zorder=zorder)
    ax.plot(*outer[3:-3].T, color="#5876A6", lw=0.3, zorder=zorder + 0.01)
    body = pilot - up * 0.035 * size
    ax.add_patch(matplotlib.patches.Ellipse(body, 0.07 * size, 0.13 * size, angle=-np.degrees(bank),
                                            color="#2A2A2A", lw=0, zorder=zorder))


def sun_and_rays(ax, block, shift, reach, zorder=8):
    """Sun disc and three parallel rays, each ending on sunlit ground it can reach unobstructed."""
    du, dv, _ = project(*(-SUN))
    step = np.array([du, dv]) / np.hypot(du, dv)
    across = np.array([-step[1], step[0]])
    sun = np.array(SUN_UV)
    ax.add_patch(matplotlib.patches.Circle(sun + (shift, 0), 0.026, color=SUN_COLOUR, lw=0, zorder=zorder))
    for offset in (-0.032, 0.0, 0.032):
        start = sun + step * 0.05 + across * offset
        end = None
        for t in np.arange(0, reach, 0.002):
            point = start + step * t
            hit = block.unproject(*point)
            if hit is None or block.lit_at(hit[0], hit[1]) < 0.9:
                continue
            # The ray above this point must pass in front of all the terrain it crosses on screen.
            s = np.linspace(0.002, 0.8, 200)[:, None]
            ray = np.asarray(hit)[None, :] + s * SUN[None, :]
            u, v, d = project(ray[:, 0], ray[:, 1], ray[:, 2])
            if np.all(d <= block.depth[block.pixel(u, v)] + 1e-3):
                end = point
        if end is None:
            print(f"warning: no sunlit ground for the ray at offset {offset}")
            continue
        ax.annotate("", xy=end + (shift, 0), xytext=start + (shift, 0), zorder=zorder,
                    arrowprops=dict(arrowstyle="-|>,head_length=0.32,head_width=0.14", color=RAY, lw=0.6,
                                    shrinkA=0, shrinkB=0))


def main():
    mountain = mountain_block()
    lowland = lowland_block()
    shift = mountain.extent[1] - lowland.extent[0] + GAP
    left = mountain.extent[0]
    right = lowland.extent[1] + shift
    bottom = min(mountain.extent[2], lowland.extent[2])
    width = right - left
    fig = plt.figure(figsize=(FIG_W, FIG_W / 3))
    ax = fig.add_axes([0, 0, 1, 1])
    for block, dx in ((mountain, 0.0), (lowland, shift)):
        u0, u1, v0, v1 = block.extent
        ax.imshow(block.image, extent=(u0 + dx, u1 + dx, v0, v1), interpolation="bilinear", zorder=2)
        sides(ax, block, dx)

    # Mountain: three thermals leave sunlit rocky shoulders below the crest.
    for k, (x, y) in enumerate(mountain.sources):
        column(ax, mountain, (x, y, float(mountain.ground(x, y))), 0.0, zorder=10 + k, width=0.017, helix=k == 1)
    sun_and_rays(ax, mountain, 0.0, MOUNTAIN_REACH)

    # Lowland: bare fields, car park, warehouse roof and two house roofs, drawn back to front.
    items = [("house", h) for h in lowland.houses] + [("shed", lowland.warehouse)]
    items += [("column", (x, y, float(lowland.ground(x, y))), k == 1) for k, (x, y) in enumerate(lowland.sources)]
    for x, y, w, d in lowland.houses[:2]:
        items.append(("column", (x + w / 2, y + d / 2, float(lowland.ground(x, y)) + HOUSE_H + HOUSE_PITCH), False))
    x, y, w, d = lowland.warehouse
    items.append(("column", (x + w / 2, y + d / 2, float(lowland.ground(x, y)) + SHED_H), False))

    def depth(item):
        if item[0] == "column":
            return project(*item[1])[2]
        x, y, w, d = item[1]
        return project(x + w / 2, y + d / 2, 0.0)[2]

    for n, item in enumerate(sorted(items, key=lambda it: -depth(it))):
        zorder = 10 + 0.5 * n
        if item[0] == "column":
            column(ax, lowland, item[1], shift, zorder, width=0.015, helix=item[2])
            continue
        x, y, w, d = item[1]
        ground = float(lowland.ground(x, y))
        if item[0] == "house":
            building(ax, x, y, w, d, HOUSE_H, (0.72, 0.38, 0.27), (0.93, 0.91, 0.87), shift, zorder,
                     pitch=HOUSE_PITCH, ground=ground)
        else:
            building(ax, x, y, w, d, SHED_H, (0.40, 0.41, 0.43), (0.86, 0.85, 0.82), shift, zorder, ground=ground)
    sun_and_rays(ax, lowland, shift, LOWLAND_REACH)

    ax.set_xlim(left, right)
    ax.set_ylim(bottom, bottom + width / 3)
    ax.axis("off")
    OUT.mkdir(parents=True, exist_ok=True)
    dpi = PX / SS * width / FIG_W  # one raster pixel per output pixel
    fig.savefig(OUT / "thermal-blocks.png", dpi=dpi, facecolor="white")
    plt.close(fig)


if __name__ == "__main__":
    main()
