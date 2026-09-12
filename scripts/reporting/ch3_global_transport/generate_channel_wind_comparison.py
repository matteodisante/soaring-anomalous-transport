"""Compare the coastal PCA with ERA5 wind at the measured mean flight altitude.

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
from soaring.analysis.observables.wind_reference import wind_at_height  # noqa: E402
from soaring.reporting import write_macros  # noqa: E402
from soaring.reporting.style import CONTROL_COLORS, paper_style  # noqa: E402

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
    """Compare time selections at the measured flight height and near the surface."""
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
    colors = CONTROL_COLORS[1:4]
    fig = plt.figure(figsize=(6.1, 3.6), layout="constrained")
    left = fig.add_subplot(121, projection="polar")
    right = fig.add_subplot(122)
    roses = report["height_wind_roses"]
    limit = max(max(r["frequency_percent"]) for r in roses.values()) * 1.18
    for index, key in enumerate(("all_hours", "daytime")):
        rose = roses[key]
        theta = np.deg2rad(rose["centres_deg"])
        probability = np.array(rose["frequency_percent"])
        left.plot(
            np.r_[theta, theta[0]],
            np.r_[probability, probability[0]],
            color=colors[index],
            lw=1.5,
            ls="-" if index == 0 else "--",
        )
        if index == 0:
            left.fill(
                np.r_[theta, theta[0]],
                np.r_[probability, probability[0]],
                color=colors[index],
                alpha=0.15,
            )
        angle = np.deg2rad(
            report["estimates"]["height_" + key]["direction_to_from_east_deg"]
        )
        left.annotate(
            "",
            xy=(angle, limit * 0.97),
            xytext=(angle, 0),
            arrowprops={"arrowstyle": "->", "color": colors[index], "lw": 1.5},
        )
    left.set_ylim(0, limit)
    left.set_xticks(np.deg2rad([0, 90, 180, 270]), ["E", "N", "W", "S"])
    left.set_rlabel_position(145)
    left.set_title(
        f"At mean flight altitude: {report['flight_altitude_m']:.0f} m\n"
        "Towards-sector frequency [%]",
        pad=15,
    )
    axis = np.deg2rad(report["flight_axis_deg"])
    for angle in (axis, axis + np.pi):
        left.plot([angle, angle], [0, limit], "--", color=".15", lw=1.2)
    displayed_angles = [report["flight_axis_deg"]]
    for index, (period, label) in enumerate(
        (
            ("all_hours", "All year, all hours"),
            ("daytime", "All year, 09-17 UTC"),
            ("warm_daytime", "Apr-Sep, 09-17 UTC"),
        )
    ):
        angles = [
            report["flight_axis_deg"]
            + (
                report["estimates"][f"{height}_{period}"]["axis_deg"]
                - report["flight_axis_deg"]
                + 90
            )
            % 180
            - 90
            for height in ("10m", "100m", "height")
        ]
        displayed_angles.extend(angles)
        right.plot(
            angles,
            np.arange(3) + (index - 1) * 0.15,
            "o",
            color=colors[index],
            ms=4.5,
            label=label,
        )
    right.axvline(
        report["flight_axis_deg"],
        color=".15",
        ls="--",
        lw=1.2,
        label="Flight PCA, 10,000 s",
    )
    right.set(
        yticks=range(3),
        yticklabels=[
            "10 m\nAGL",
            "100 m\nAGL",
            f"{report['flight_altitude_m']:.0f} m\nMSL proxy",
        ],
        ylim=(2.5, -0.5),
        xlim=(min(displayed_angles) - 3, max(displayed_angles) + 3),
        xlabel="Axis from east [degrees, mod 180]",
        title="Height and time selection",
    )
    right.legend(
        loc="upper center", bbox_to_anchor=(0.35, -0.20), frameon=False, fontsize=7
    )
    fig.savefig(
        OUT / "ch3_channel_wind.pdf",
        bbox_inches="tight",
        pad_inches=0.05,
        metadata={"CreationDate": None, "Creator": "soaring.analysis"},
    )
    plt.close(fig)


def rose(u, v, weights):
    """Return a weighted towards-direction histogram; means keep calm hours."""
    speed = np.hypot(u, v)
    towards = np.rad2deg(np.arctan2(v, u)) % 360
    included = speed >= 0.5
    cell_weights = np.broadcast_to(weights[:, None], speed.shape)
    frequency, _ = np.histogram(
        (towards[included] + 7.5) % 360,
        bins=np.arange(0, 361, 15),
        weights=cell_weights[included],
    )
    return {
        "centres_deg": np.arange(0, 360, 15).tolist(),
        "frequency_percent": (100 * frequency / frequency.sum()).tolist(),
        "calm_fraction": float(np.sum(cell_weights[~included]) / cell_weights.sum()),
    }


def pressure_reference(time, locations, weights, masks):
    """Interpolate archived pressure-level vectors at the measured flight height."""
    directory = ROOT / "revisions/channel-wind-flight-altitude-2026-09-13"
    manifest_path = directory / "pressure-input-manifest.json"
    manifest = json.loads(manifest_path.read_text())
    for name in ("u", "v"):
        assert manifest["variables"][name]["units"] == "m s**-1"
        assert manifest["variables"][name]["GRIB_uvRelativeToGrid"] == 0
    for name in ("z", "z_sfc"):
        assert manifest["variables"][name]["units"] == "m**2 s**-2"
    path = directory / "pressure-wind.npz"
    assert digest(path) == manifest["files_sha256"][path.name]
    altitude_path = OUT / "ch3_channel_flight_altitude.json"
    altitude = json.loads(altitude_path.read_text())
    for name, expected in altitude["sources"].items():
        assert digest(ROOT / name) == expected, name
    assert altitude["flight_report_sha256"] == digest(OUT / "ch3_revision.json")
    with np.load(path) as data:
        assert np.array_equal(
            data["time_hours_since_epoch"],
            np.array(time, dtype="datetime64[h]").astype("int64"),
        )
        np.testing.assert_array_equal(
            np.column_stack((data["latitude"], data["longitude"])), locations
        )
        assert data["pressure_hpa"].tolist() == [1000, 925, 850, 700]
        # ECMWF's spherical conversion from geopotential to geometric height.
        g0, radius = 9.80665, 6371000.0
        potential_height = data["z"].astype(float) / g0
        height = radius * potential_height / (radius - potential_height)
        ground_h = data["surface_geopotential"].astype(float) / g0
        ground = radius * ground_h / (radius - ground_h)
        target = altitude["mean_altitude_m"]
        u, v = wind_at_height(
            data["u"], data["v"], height, target, surface_height_m=ground[:, None]
        )
        estimates = {
            "height_" + key: summarise(u[:, mask], v[:, mask], weights)
            for key, mask in masks.items()
        }
        sensitivity = {}
        targets = {
            "same_hours_mean_height": target,
            "lower_quartile": altitude["window_mean_quantiles_m"]["q25"],
            "upper_quartile": altitude["window_mean_quantiles_m"]["q75"],
            "equal_flight_mean": altitude["equal_flight_mean_altitude_m"],
        }
        # The lowest target occasionally lies below the lowest above-ground
        # pressure level. Use identical supported hours at all nine cells for
        # every height sensitivity, including a matched main-height reference.
        low, high = min(targets.values()), max(targets.values())
        supported = np.any(
            (height <= low) & (height >= ground[:, None, None]), axis=-1
        ) & (height[..., -1] >= high)
        common_hours = supported.all(axis=0)
        for name, value in targets.items():
            a, b = wind_at_height(
                data["u"][:, common_hours],
                data["v"][:, common_hours],
                height[:, common_hours],
                value,
                surface_height_m=ground[:, None],
            )
            sensitivity[name] = {
                "height_m": value,
                "estimates": {
                    key: summarise(
                        a[:, mask[common_hours]], b[:, mask[common_hours]], weights
                    )
                    for key, mask in masks.items()
                },
            }
        coverage = {
            "profiles": int(np.prod(height.shape[:-1])),
            "all_profiles_bracketed_above_ground": True,
            "model_surface_height_range_m": [float(ground.min()), float(ground.max())],
            "sensitivity_common_hours_per_cell": int(common_hours.sum()),
            "sensitivity_excluded_hours_per_cell": int((~common_hours).sum()),
            "sensitivity_rule": (
                "All nine cells must bracket every tested height above ground; "
                "identical supported hours at every height, including the mean"
            ),
        }
    return {
        "flight_altitude_m": target,
        "flight_altitude": altitude,
        "flight_altitude_sha256": digest(altitude_path),
        "pressure_input_manifest_sha256": digest(manifest_path),
        "pressure_input_manifest": str(manifest_path.relative_to(ROOT)),
        "pressure_snapshot_id": manifest["snapshot_id"],
        "height_estimates": estimates,
        "height_sensitivity": sensitivity,
        "height_wind_roses": {
            key: rose(u[:, masks[key]], v[:, masks[key]], weights)
            for key in ("all_hours", "daytime")
        },
        "vertical_coverage": coverage,
    }


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
    daytime = (hour >= 9) & (hour <= 17)
    masks = {
        "all_hours": np.ones(len(time), dtype=bool),
        "daytime": daytime,
        "warm_all_hours": (month >= 4) & (month <= 9),
        "warm_daytime": warm_day,
    }
    estimates = {
        f"{h}m_{key}": summarise(
            east[h] if key == "all_hours" else east[h][:, mask],
            north[h] if key == "all_hours" else north[h][:, mask],
            weights,
        )
        for h in (10, 100)
        for key, mask in masks.items()
    }
    pressure = pressure_reference(time, locations, weights, masks)
    estimates.update(pressure.pop("height_estimates"))
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
        **pressure,
        "model": "ERA5; surface via Open-Meteo, pressure levels via Earthmover",
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
            "Hourly E/N vectors averaged over 2016-2025 and the same nine ERA5 cells, "
            "with cos(latitude) area weights. Main reference: mean cleaned GNSS "
            "altitude on the exact 10,000-s PCA windows, used as an approximate MSL "
            "height. Convert pressure geopotential with g=9.80665 and spherical "
            "R=6371000 m, then linearly interpolate u/v against each hourly profile's "
            "geometric level heights, with no extrapolation or below-ground bracket. "
            "All-year all hours and all-year 09-17 UTC are distinct comparisons; "
            "April-September is a separate seasonal sensitivity. Surface 10/100 m "
            "AGL references remain controls. Towards angles are counterclockwise "
            "from east; comparison with PCA uses axes modulo 180 degrees."
        ),
        "limits": [
            (
                "Recent-decade climatology on a sparse regular grid; not weather "
                "matched to flight dates, positions or instantaneous flight altitude."
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
    altitude = pressure["flight_altitude"]
    height_quantiles = altitude["window_mean_quantiles_m"]
    macros = {
        "StatWindFlightAngle": f"{flight['angle_deg']:.1f}",
        "StatWindFlights": str(flight["n_flights"]),
        "StatWindHeightM": f"{pressure['flight_altitude_m']:.0f}",
        "StatWindHeightFlightM": f"{altitude['equal_flight_mean_altitude_m']:.0f}",
        "StatWindHeightLowM": f"{height_quantiles['q25']:.0f}",
        "StatWindHeightHighM": f"{height_quantiles['q75']:.0f}",
        "StatWindWindows": str(pressure["flight_altitude"]["n_windows"]),
        "StatWindSensitivityExcludedHours": str(
            pressure["vertical_coverage"]["sensitivity_excluded_hours_per_cell"]
        ),
    }
    for key, prefix in (("all_hours", "All"), ("daytime", "Day")):
        values = [
            pressure["height_sensitivity"][name]["estimates"][key]["axis_deg"]
            for name in ("lower_quartile", "upper_quartile")
        ]
        macros["StatWindSensitivity" + prefix + "LowAngle"] = f"{min(values):.1f}"
        macros["StatWindSensitivity" + prefix + "HighAngle"] = f"{max(values):.1f}"
    for name, prefix in (
        ("10m_all_hours", "Surface"),
        ("100m_all_hours", "Hundred"),
        ("10m_warm_daytime", "WarmDay"),
        ("10m_daytime", "SurfaceDay"),
        ("100m_daytime", "HundredDay"),
        ("height_all_hours", "HeightAll"),
        ("height_daytime", "HeightDay"),
        ("height_warm_all_hours", "HeightWarmAll"),
        ("height_warm_daytime", "HeightWarmDay"),
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
