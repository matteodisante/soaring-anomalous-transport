"""Indicative mountain-footprint axes from independent NOAA ETOPO 2022 elevations.

This is a small geographical comparison, not a fitted wind or flight model.
The operational mountain footprint is terrain >= 1000 m inside the thesis boxes;
500 and 1500 m expose the sensitivity to that choice. No threshold is optimized
against the flight directions.
"""
from __future__ import annotations

import ast
import hashlib
import json
import sys
import urllib.parse
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from scipy.io import netcdf_file

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / "src"))
from soaring.analysis.preproc.enu import geodetic_to_enu

REPORTER = ROOT / "scripts/reporting/ch3_global_transport/generate_revision_diagnostics.py"
REGIONS = next(ast.literal_eval(node.value) for node in ast.parse(REPORTER.read_text()).body
               if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "REGIONS" for t in node.targets))
FLIGHTS = ROOT / "revisions/regional-pca-lags-2026-09-12/regional-pca.json"
BASE_URL = "https://coastwatch.pfeg.noaa.gov/erddap/griddap/ETOPO_2022_v1_15s.nc?"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def axis(xy, weights):
    mean = np.average(xy, axis=0, weights=weights)
    centred = xy - mean
    covariance = (centred * weights[:, None]).T @ centred / weights.sum()
    values, vectors = np.linalg.eigh(covariance)
    v = vectors[:, -1]
    return {"angle_deg": float(np.degrees(np.arctan2(v[1], v[0])) % 180),
            "ratio": float(values[-1] / values[0]), "centre_km": mean.tolist(),
            "covariance_km2": covariance.tolist(), "cells": len(xy)}


def difference(a, b):
    return abs((a - b + 90) % 180 - 90)


def main():
    flights = json.loads(FLIGHTS.read_text())["paragliders"]
    results, inputs = {}, {}
    fig, axs = plt.subplots(1, 2, figsize=(12, 5.8), layout="constrained")
    for ax, (name, tag) in zip(axs, [("Alps", "alps"), ("Pyrenees", "pyrenees")], strict=True):
        west, east, south, north = REGIONS[name]
        # A narrow plotting buffer is downloaded; measurements use the exact box.
        query = f"z[({south-.2:g}):4:({north+.2:g})][({west-.2:g}):4:({east+.2:g})]"
        url = BASE_URL + urllib.parse.quote(query, safe="(),:")
        path = HERE / (tag + "-etopo2022.nc")
        if not path.exists():
            with urllib.request.urlopen(url, timeout=45) as response:
                path.write_bytes(response.read())
        inputs[path.name] = {"url": url, "sha256": sha(path), "bytes": path.stat().st_size}
        with netcdf_file(path, mmap=False) as nc:
            latitude = nc.variables["latitude"][:].copy()
            longitude = nc.variables["longitude"][:].copy()
            elevation = nc.variables["z"][:].copy()
        lon, lat = np.meshgrid(longitude, latitude)
        inside = (lon >= west) & (lon <= east) & (lat >= south) & (lat <= north)
        e, n, _ = geodetic_to_enu(lat, lon, np.zeros_like(elevation),
                                 (north + south) / 2, (west + east) / 2, 0)
        e, n = e / 1000, n / 1000
        xy = np.column_stack((e.ravel(), n.ravel()))
        sensitivity = {}
        flight = next(r for r in flights if r["region"] == name and r["lag_s"] == 10000)
        for threshold in (500, 1000, 1500):
            mask = inside & np.isfinite(elevation) & (elevation >= threshold)
            # Cos(latitude) approximates the relative area of equal-angle cells.
            fitted = axis(xy[mask.ravel()], np.cos(np.deg2rad(lat[mask])))
            fitted["difference_from_flight_axis_deg"] = difference(fitted["angle_deg"], flight["angle_deg"])
            sensitivity[str(threshold)] = fitted
        chosen = sensitivity["1000"]
        results[name] = {"box_lon_lat_deg": REGIONS[name], "terrain_threshold_m": 1000,
                         "terrain": chosen, "threshold_sensitivity": sensitivity,
                         "flight_lag_s": 10000, "flight_angle_deg": flight["angle_deg"],
                         "flight_n": flight["n_flights"], "flight_ratio": flight["ratio"]}
        shown = np.where(inside, elevation, np.nan)
        im = ax.pcolormesh(e, n, shown, shading="auto", cmap="terrain", vmin=0, vmax=3500,
                           rasterized=True)
        ax.contour(e, n, shown, levels=[1000], colors=".15", linewidths=.45)
        corners_lon = np.array([west, east, east, west, west])
        corners_lat = np.array([south, south, north, north, south])
        be, bn, _ = geodetic_to_enu(corners_lat, corners_lon, np.zeros(5),
                                    (north+south)/2, (west+east)/2, 0)
        ax.plot(be/1000, bn/1000, color=".15", lw=.9)
        centre = np.array(chosen["centre_km"])
        half_length = .4 * min(np.ptp(e[inside]), np.ptp(n[inside]))
        for angle, color, style, label in (
                (chosen["angle_deg"], "#202020", "-", f"Terrain axis: {chosen['angle_deg']:.1f}°"),
                (flight["angle_deg"], "#C43877", "--", f"Flight axis at 10,000 s: {flight['angle_deg']:.1f}°")):
            unit = np.array([np.cos(np.deg2rad(angle)), np.sin(np.deg2rad(angle))])
            line = centre[:, None] + unit[:, None] * np.array([-half_length, half_length])
            if style == "-" or chosen['difference_from_flight_axis_deg'] >= 1:
                ax.plot(*line, color="white", lw=5, zorder=4)
            ax.plot(*line, color=color, ls=style, lw=2.6, label=label, zorder=5)
        difference_label = ("<1" if chosen['difference_from_flight_axis_deg'] < 1
                            else f"{chosen['difference_from_flight_axis_deg']:.0f}")
        ax.set(aspect="equal", xlabel="East from box centre [km]", ylabel="North from box centre [km]",
               title=f"{name}: indicative terrain orientation\nTerrain ≥ 1000 m; axis difference {difference_label}°")
        ax.legend(loc="upper center", bbox_to_anchor=(.5, -.2), frameon=False, fontsize=10)
    fig.colorbar(im, ax=axs, label="ETOPO 2022 elevation [m]", shrink=.7, pad=.025)
    fig.suptitle("Independent terrain data in the same flight-selection boxes\nAxes counterclockwise from east, modulo 180°; outline contour at 1000 m", fontsize=12)
    fig.savefig(HERE / "terrain-versus-flight-axes.pdf", bbox_inches="tight", metadata={"CreationDate": None})
    fig.savefig(HERE / "terrain-versus-flight-axes.png", bbox_inches="tight", dpi=180)
    plt.close(fig)
    report = {"created_utc": datetime.now(UTC).isoformat(),
              "source": "NOAA NCEI ETOPO 2022, 15 arc-second surface elevations via ERDDAP; every fourth cell in both directions (1 arc-minute spacing)",
              "source_url": "https://www.ncei.noaa.gov/products/etopo-global-relief-model",
              "doi": "https://doi.org/10.25921/fd45-gt74", "inputs": inputs,
              "method": "Area-weighted spatial covariance of DEM cell centres at or above 1000 m within the exact box. WGS84 local East/North coordinates at sea level, tangent at box centre; approximate area weights cos(latitude). No elevation weighting above the threshold. Largest eigenvector gives an unoriented axis. Thresholds 500 and 1500 m are sensitivity checks, not confidence bounds.",
              "flight_results_path": str(FLIGHTS.relative_to(ROOT)), "flight_results_sha256": sha(FLIGHTS),
              "script_sha256": sha(__file__), "box_source_sha256": sha(REPORTER),
              "coordinate_source_sha256": sha(ROOT / "src/soaring/analysis/preproc/enu.py"),
              "results": results,
              "limits": ["Indicative axis of the highland footprint, not an extracted crest or geological chain boundary.",
                         "Box shape, truncation, curved chains, plateaux and the elevation threshold influence the angle.",
                         "The flight box selects take-offs; some flight increments can extend beyond the box.",
                         "Terrain has a box-centred tangent frame, whereas flight increments pool flight-centred frames; this is an approximate regional comparison.",
                         "Alignment is descriptive evidence only: wind, routes and selection can also align displacement; no causal terrain attribution or uncertainty interval is inferred."]}
    (HERE / "terrain-axis.json").write_text(json.dumps(report, indent=2) + "\n")
    for name, record in results.items():
        print(name, "terrain", round(record['terrain']['angle_deg'], 1),
              "flights", round(record['flight_angle_deg'], 1),
              "difference", round(record['terrain']['difference_from_flight_axis_deg'], 1))


if __name__ == "__main__":
    main()
