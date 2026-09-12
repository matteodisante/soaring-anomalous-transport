"""Compare the coastal flight PCA with an independent ERA5 wind climatology.

Use the archived hourly 2016--2025 wind at nine cells selected across the exact
Channel Coast box. Average East/North velocity components, never degree angles.
This is a regional orientation reference, not weather matched to the flights.
"""

from __future__ import annotations

import ast
import gzip
import hashlib
import json
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "src"))
from soaring.reporting import write_macros  # noqa: E402
from soaring.reporting.style import COMPONENT_COLORS, paper_style  # noqa: E402

SOURCE = ROOT / "revisions/channel-wind-2026-09-12"
OUT = ROOT / "thesis/generated"
GENERATED_OUTPUTS = (
    "ch3_channel_wind.pdf",
    "ch3_channel_wind_values.tex",
    "ch3_channel_wind.json",
)


def digest(path):
    """Identify exact archived input bytes."""
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def components(speed, direction_from_deg):
    """Convert meteorological from-north, clockwise degrees to air-motion E/N."""
    phi = np.deg2rad(direction_from_deg)
    return -np.asarray(speed) * np.sin(phi), -np.asarray(speed) * np.cos(phi)


def summarise(u, v, weights):
    """Average vectors in time and approximately by represented cell area."""
    east = float(np.average(u.mean(axis=1), weights=weights))
    north = float(np.average(v.mean(axis=1), weights=weights))
    mean_speed = float(np.average(np.hypot(u, v).mean(axis=1), weights=weights))
    resultant_speed = float(np.hypot(east, north))
    if resultant_speed < 1e-12:
        raise ValueError("Mean wind direction is undefined for a zero mean vector")
    angle = float(np.rad2deg(np.arctan2(north, east)) % 360)
    return {
        "mean_east_ms": east,
        "mean_north_ms": north,
        "mean_speed_ms": mean_speed,
        "resultant_speed_ms": resultant_speed,
        "resultant_fraction": resultant_speed / mean_speed if mean_speed else 0,
        "direction_to_from_east_deg": angle,
        "axis_deg": angle % 180,
        "meteorological_from_deg": (270 - angle) % 360,
        "hours_per_cell": u.shape[1],
        "cells": u.shape[0],
    }


def render(report):
    """Show the spread of wind directions and the chosen sensitivity comparisons."""
    paper_style()
    plt.rcParams.update(
        {
            "font.size": 9,
            "axes.labelsize": 9,
            "axes.titlesize": 9,
            "xtick.labelsize": 8,
            "ytick.labelsize": 8,
        }
    )
    color = next(iter(COMPONENT_COLORS.values()))
    fig = plt.figure(figsize=(6.1, 3.6), layout="constrained")
    left = fig.add_subplot(121, projection="polar")
    right = fig.add_subplot(122)
    theta = np.deg2rad(report["wind_rose"]["centres_deg"])
    probability = np.array(report["wind_rose"]["frequency_percent"])
    left.bar(theta, probability, width=np.deg2rad(14), color=color, alpha=0.7)
    limit = float(probability.max()) * 1.22
    left.set_ylim(0, limit)
    left.set_xticks(np.deg2rad([0, 90, 180, 270]), ["E", "N", "W", "S"])
    left.set_rlabel_position(145)
    left.set_title(
        "Air motion towards each sector\nFrequency [%], speed ≥ 0.5 m/s", pad=15
    )
    angle = np.deg2rad(
        report["estimates"]["10m_all_hours"]["direction_to_from_east_deg"]
    )
    left.annotate(
        "",
        xy=(angle, limit * 0.97),
        xytext=(angle, 0),
        arrowprops={"arrowstyle": "->", "color": color, "lw": 2.3},
    )
    axis = np.deg2rad(report["flight_axis_deg"])
    for phi in (axis, axis + np.pi):
        left.plot([phi, phi], [0, limit], "--", color=".15", lw=1.3)
    keys = ("10m_all_hours", "100m_all_hours", "10m_warm_daytime")
    labels = ("10 m\nAll hours", "100 m\nAll hours", "10 m, Apr-Sep\n09-17 UTC")
    angles = [report["estimates"][k]["axis_deg"] for k in keys]
    for y, value in enumerate(angles):
        right.plot(value, y, "o", color=color, ms=6)
        right.annotate(
            f"{value:.1f}°",
            (value, y),
            xytext=(0, 9),
            textcoords="offset points",
            ha="center",
            fontsize=8,
        )
    right.axvline(
        report["flight_axis_deg"], color=".15", ls="--", label="Flight PCA, 10,000 s"
    )
    site_angles = [r["axis_deg"] for r in report["site_estimates_10m"]]
    right.plot(
        site_angles,
        np.full(len(site_angles), -0.40),
        "|",
        color=".55",
        ms=6,
        label="Individual cells, 10 m",
    )
    lower = min(*angles, *site_angles, report["flight_axis_deg"]) - 5
    upper = max(*angles, *site_angles, report["flight_axis_deg"]) + 5
    right.set(
        yticks=range(3),
        yticklabels=labels,
        ylim=(2.5, -0.65),
        xlim=(lower, upper),
        xlabel="Axis from east [degrees, mod 180]",
        title="Mean-vector orientation",
    )
    right.legend(
        loc="upper center", bbox_to_anchor=(0.5, -0.24), frameon=False, fontsize=7
    )
    fig.savefig(
        OUT / "ch3_channel_wind.pdf",
        bbox_inches="tight",
        pad_inches=0.05,
        metadata={"CreationDate": None, "Creator": "soaring.analysis"},
    )
    plt.close(fig)


def main():
    """Validate all hourly inputs and publish the fixed climatology comparison."""
    manifest_path = SOURCE / "input-manifest.json"
    manifest = json.loads(manifest_path.read_text())
    assert manifest["model"] == "ERA5" and manifest["period"] == [
        "2016-01-01",
        "2025-12-31",
    ]
    reporter = (
        ROOT / "scripts/reporting/ch3_global_transport/generate_revision_diagnostics.py"
    )
    regions = next(
        ast.literal_eval(node.value)
        for node in ast.parse(reporter.read_text()).body
        if isinstance(node, ast.Assign)
        and any(isinstance(t, ast.Name) and t.id == "REGIONS" for t in node.targets)
    )
    assert list(regions["Channel Coast"]) == manifest["box_lon_lat_deg"]
    east, north = {10: [], 100: []}, {10: [], 100: []}
    locations, time = [], None
    for record in manifest["files"]:
        path = SOURCE / record["file"]
        assert digest(path) == record["sha256"]
        raw = gzip.decompress(path.read_bytes())
        assert hashlib.sha256(raw).hexdigest() == record["raw_sha256"]
        data = json.loads(raw)
        if time is None:
            time = data["hourly"]["time"]
        assert data["hourly"]["time"] == time
        locations.append((data["latitude"], data["longitude"]))
        for height in (10, 100):
            speed = np.asarray(data["hourly"][f"wind_speed_{height}m"], dtype=float)
            direction = np.asarray(
                data["hourly"][f"wind_direction_{height}m"], dtype=float
            )
            assert np.isfinite(speed).all() and np.isfinite(direction).all()
            assert (speed >= 0).all() and ((direction >= 0) & (direction <= 360)).all()
            assert data["hourly_units"][f"wind_speed_{height}m"] == "m/s"
            assert data["hourly_units"][f"wind_direction_{height}m"] == "°"
            u, v = components(speed, direction)
            east[height].append(u)
            north[height].append(v)
    assert len(locations) == len(set(locations)) == 9 and len(time) == 87672
    timestamps = np.array(time, dtype="datetime64[h]")
    assert np.all(np.diff(timestamps) == np.timedelta64(1, "h"))
    assert time[0] == "2016-01-01T00:00" and time[-1] == "2025-12-31T23:00"
    month = timestamps.astype("datetime64[M]").astype(int) % 12 + 1
    hour = timestamps.astype(int) % 24
    warm_day = (month >= 4) & (month <= 9) & (hour >= 9) & (hour <= 17)
    weights = np.cos(np.deg2rad(np.array(locations)[:, 0]))
    east, north = (
        {h: np.array(v) for h, v in east.items()},
        {h: np.array(v) for h, v in north.items()},
    )
    estimates = {
        f"{h}m_all_hours": summarise(east[h], north[h], weights) for h in (10, 100)
    }
    estimates["10m_warm_daytime"] = summarise(
        east[10][:, warm_day], north[10][:, warm_day], weights
    )
    sites = [
        {
            "latitude": lat,
            "longitude": lon,
            **summarise(east[10][i : i + 1], north[10][i : i + 1], [1]),
        }
        for i, (lat, lon) in enumerate(locations)
    ]
    flight_path = OUT / "ch3_revision.json"
    rows = json.loads(flight_path.read_text())["results"]["paragliders"]["pca"]
    flight = next(
        r for r in rows if r["region"] == "Channel Coast" and r["lag_s"] == 10000
    )
    for estimate in estimates.values():
        estimate["difference_from_flight_axis_deg"] = abs(
            (estimate["axis_deg"] - flight["angle_deg"] + 90) % 180 - 90
        )
    speed = np.hypot(east[10], north[10])
    towards = np.rad2deg(np.arctan2(north[10], east[10])) % 360
    included = speed >= 0.5
    cell_weights = np.broadcast_to(weights[:, None], speed.shape)
    frequency, _ = np.histogram(
        (towards[included] + 7.5) % 360,
        bins=np.arange(0, 361, 15),
        weights=cell_weights[included],
    )
    report = {
        "model": "ERA5 via Open-Meteo",
        "period": manifest["period"],
        "input_manifest": str(manifest_path.relative_to(ROOT)),
        "input_manifest_sha256": digest(manifest_path),
        "producer_sha256": digest(__file__),
        "flight_report_sha256": digest(flight_path),
        "flight_axis_deg": flight["angle_deg"],
        "flight_lag_s": 10000,
        "flight_n": flight["n_flights"],
        "box_lon_lat_deg": manifest["box_lon_lat_deg"],
        "estimates": estimates,
        "site_estimates_10m": sites,
        "wind_rose": {
            "centres_deg": np.arange(0, 360, 15).tolist(),
            "frequency_percent": (100 * frequency / frequency.sum()).tolist(),
            "calm_fraction": float(
                np.sum(cell_weights[~included]) / cell_weights.sum()
            ),
        },
        "method": (
            "Hourly E/N velocity components averaged over 2016-2025 and nine "
            "representative ERA5 cells, with cos(latitude) area weights; no "
            "arithmetic average of direction angles. Main reference: 10 m above "
            "ground, all hours. Sensitivities: 100 m all hours and 10 m April-"
            "September 09-17 UTC. Wind direction refers to air motion towards an "
            "angle counterclockwise from east; comparison with PCA uses axes "
            "modulo 180 degrees."
        ),
        "limits": [
            (
                "Recent-decade climatology on a sparse regular grid; not weather "
                "matched to flight dates, take-off sites or flight altitude."
            ),
            (
                "The resultant fraction describes directional cancellation, not "
                "confidence or an error bound."
            ),
            (
                "Climatological mean wind direction and centred displacement "
                "covariance are different statistics; agreement cannot establish "
                "causality."
            ),
            (
                "A constant additive wind is removed by displacement centring at "
                "fixed lag; variable wind and route choices can still affect the "
                "covariance."
            ),
        ],
    }
    (OUT / "ch3_channel_wind.json").write_text(json.dumps(report, indent=2) + "\n")
    macros = {
        "StatWindFlightAngle": f"{flight['angle_deg']:.1f}",
        "StatWindFlights": str(flight["n_flights"]),
    }
    for name, prefix in (
        ("10m_all_hours", "Surface"),
        ("100m_all_hours", "Hundred"),
        ("10m_warm_daytime", "WarmDay"),
    ):
        r = estimates[name]
        for key, field in (
            ("Angle", "axis_deg"),
            ("From", "meteorological_from_deg"),
            ("Difference", "difference_from_flight_axis_deg"),
        ):
            macros["StatWind" + prefix + key] = f"{r[field]:.1f}"
        macros["StatWind" + prefix + "Resultant"] = f"{r['resultant_fraction']:.2f}"
    write_macros(
        OUT / "ch3_channel_wind_values.tex",
        macros,
        generator=str(Path(__file__).relative_to(ROOT)),
    )
    render(report)
    print(json.dumps(estimates, indent=2))


if __name__ == "__main__":
    main()
