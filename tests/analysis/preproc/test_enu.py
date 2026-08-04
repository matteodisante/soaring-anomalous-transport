import numpy as np
import pandas as pd
import pytest

from soaring.analysis.preproc.enu import (
    LOCAL_COLUMNS,
    WGS84_A_M,
    WGS84_E2,
    WGS84_F,
    LocalFrame,
    enu_rotation_matrix,
    geodetic_to_ecef,
    geodetic_to_enu,
    prime_vertical_radius_m,
    to_local_frame,
)
from soaring.analysis.preprocessing import great_circle_m

WGS84_B_M = WGS84_A_M * (1.0 - WGS84_F)  # semi-minor axis


def _ecef_to_geodetic(x, y, z):
    """Inverse of geodetic_to_ecef (Bowring), for building synthetic tracks in ENU.

    Only the tests need it -- nothing in the pipeline ever maps back -- and its own
    correctness is asserted against the forward transform by
    ``test_ecef_roundtrip_helper_is_exact`` before any other test relies on it.
    """
    x, y, z = float(x), float(y), float(z)
    ep2 = (WGS84_A_M**2 - WGS84_B_M**2) / WGS84_B_M**2
    p = np.hypot(x, y)
    theta = np.arctan2(z * WGS84_A_M, p * WGS84_B_M)
    lat = np.arctan2(
        z + ep2 * WGS84_B_M * np.sin(theta) ** 3,
        p - WGS84_E2 * WGS84_A_M * np.cos(theta) ** 3,
    )
    lon = np.arctan2(y, x)
    n_rad = WGS84_A_M / np.sqrt(1.0 - WGS84_E2 * np.sin(lat) ** 2)
    alt = p / np.cos(lat) - n_rad
    return np.degrees(lat), np.degrees(lon), alt


def _enu_to_geodetic(east, north, up, lat0, lon0, alt0):
    """Place points given by their exact ENU coordinates back on the ellipsoid."""
    x0, y0, z0 = geodetic_to_ecef(lat0, lon0, alt0)
    rot = enu_rotation_matrix(lat0, lon0)
    enu = np.vstack([np.atleast_1d(east), np.atleast_1d(north), np.atleast_1d(up)])
    delta = rot.T @ enu
    out = [
        _ecef_to_geodetic(float(x0) + dx, float(y0) + dy, float(z0) + dz)
        for dx, dy, dz in delta.T
    ]
    lats, lons, alts = (np.array(c) for c in zip(*out, strict=True))
    return lats, lons, alts


# --------------------------------------------------------------------------------
# Step 1: geodetic -> ECEF (thesis eq:ecef)
# --------------------------------------------------------------------------------


def test_prime_vertical_radius_at_equator_and_pole():
    # N(0) = a exactly; N(90) = a / sqrt(1 - e^2) = a^2 / b, the polar value.
    assert float(prime_vertical_radius_m(0.0)) == pytest.approx(WGS84_A_M)
    assert float(prime_vertical_radius_m(90.0)) == pytest.approx(
        WGS84_A_M**2 / WGS84_B_M
    )
    # It grows monotonically with |latitude| (the ellipsoid flattens towards the poles).
    lats = np.linspace(0.0, 90.0, 40)
    assert np.all(np.diff(prime_vertical_radius_m(lats)) > 0)


def test_ecef_of_the_three_reference_points():
    # The three points where the ECEF axes pierce the ellipsoid, by definition of the
    # frame: X through (0 deg, 0 deg), Y through (0 deg, 90 deg E), Z through the pole.
    # (abs, not rel: the components that vanish do so through cos/sin of a right angle,
    # which leaves sub-micrometre floating-point dust rather than an exact zero.)
    def ecef(lat, lon):
        return tuple(float(c) for c in geodetic_to_ecef(lat, lon, 0.0))

    assert ecef(0.0, 0.0) == pytest.approx((WGS84_A_M, 0.0, 0.0), abs=1e-6)
    assert ecef(0.0, 90.0) == pytest.approx((0.0, WGS84_A_M, 0.0), abs=1e-6)
    # The polar radius is b = a(1 - f), NOT a: this is the flattening itself, ~21 km.
    assert ecef(90.0, 0.0) == pytest.approx((0.0, 0.0, WGS84_B_M), abs=1e-6)
    polar_deficit_m = WGS84_A_M - WGS84_B_M
    assert polar_deficit_m == pytest.approx(21385.0, abs=1.0)


def test_ecef_surface_point_satisfies_the_ellipsoid_equation():
    # Every h = 0 point must lie on x^2/a^2 + y^2/a^2 + z^2/b^2 = 1.
    lat = np.array([-72.0, -30.0, 0.0, 12.5, 45.0, 67.3])
    lon = np.array([-140.0, -8.0, 0.0, 33.0, 96.0, 179.0])
    x, y, z = geodetic_to_ecef(lat, lon, np.zeros_like(lat))
    residual = (x**2 + y**2) / WGS84_A_M**2 + z**2 / WGS84_B_M**2
    assert residual == pytest.approx(np.ones_like(lat), rel=1e-12)


def test_height_is_measured_along_the_ellipsoid_normal():
    # Raising a fix by h must move it by exactly h, along the unit normal of eq:geo-up.
    lat, lon, h = 44.3, 6.7, 1750.0
    p_surface = np.array([float(c) for c in geodetic_to_ecef(lat, lon, 0.0)])
    p_raised = np.array([float(c) for c in geodetic_to_ecef(lat, lon, h)])
    offset = p_raised - p_surface
    assert np.linalg.norm(offset) == pytest.approx(h, rel=1e-12)
    normal = np.array(
        [
            np.cos(np.radians(lat)) * np.cos(np.radians(lon)),
            np.cos(np.radians(lat)) * np.sin(np.radians(lon)),
            np.sin(np.radians(lat)),
        ]
    )
    assert offset / h == pytest.approx(normal, rel=1e-9)


def test_geodetic_and_geocentric_latitude_differ_as_the_thesis_says():
    # sec:enu: phi - psi ~= (e^2/2) sin(2 phi), peaking at 45 deg at ~0.19 deg (11.5'),
    # which mistaken for one another would misplace a fix by ~20 km of ground distance.
    lat = np.array([0.0, 15.0, 30.0, 45.0, 60.0, 90.0])
    x, y, z = geodetic_to_ecef(lat, np.zeros_like(lat), np.zeros_like(lat))
    geocentric = np.degrees(np.arctan2(z, np.hypot(x, y)))
    predicted = np.degrees(0.5 * WGS84_E2 * np.sin(2.0 * np.radians(lat)))
    # The thesis formula is the first order in e^2 (app:geodesy), so it is right to
    # within its own next order, ~1e-3 degrees, not to machine precision.
    assert lat - geocentric == pytest.approx(predicted, abs=1e-3)
    peak = float((lat - geocentric)[lat == 45.0][0])
    assert peak == pytest.approx(0.192, abs=1e-3)  # = 11.5 arc-minutes
    # Which, taken for the wrong latitude, would displace a fix along the meridian by
    # R * (e^2/2): the ~20 km of sec:enu, 21.4 km computed exactly.
    assert np.radians(peak) * 6371008.8 == pytest.approx(21_400.0, abs=200.0)


# --------------------------------------------------------------------------------
# Step 2: the ENU rotation (thesis app:geodesy-enu)
# --------------------------------------------------------------------------------


def test_enu_rotation_matrix_is_a_rotation():
    # "Rotated" in sec:enu is exact, not loose: orthogonal with unit determinant, so it
    # preserves lengths and angles and only changes the axes.
    for lat0, lon0 in [(0.0, 0.0), (45.0, 7.0), (-33.9, 151.2), (89.0, -179.0)]:
        rot = enu_rotation_matrix(lat0, lon0)
        assert rot.T @ rot == pytest.approx(np.eye(3), abs=1e-12)
        assert float(np.linalg.det(rot)) == pytest.approx(1.0)


def test_east_axis_is_horizontal_and_up_is_the_normal():
    lat0, lon0 = 45.0, 7.0
    rot = enu_rotation_matrix(lat0, lon0)
    # East is tangent to the parallel, so it has no component along the polar axis at
    # any latitude; Up is the ellipsoid normal of eq:geo-up (not the radius to O).
    assert rot[0, 2] == 0.0
    normal = np.array(
        [
            np.cos(np.radians(lat0)) * np.cos(np.radians(lon0)),
            np.cos(np.radians(lat0)) * np.sin(np.radians(lon0)),
            np.sin(np.radians(lat0)),
        ]
    )
    assert rot[2] == pytest.approx(normal, rel=1e-12)


def test_enu_is_zero_at_the_origin_fix():
    east, north, up = geodetic_to_enu(45.0, 7.0, 1200.0, 45.0, 7.0, 1200.0)
    origin = (float(east), float(north), float(up))
    assert origin == pytest.approx((0.0, 0.0, 0.0), abs=1e-9)


def test_pure_vertical_displacement_goes_entirely_into_up():
    lat0, lon0, alt0 = 45.0, 7.0, 1200.0
    east, north, up = geodetic_to_enu(lat0, lon0, alt0 + 350.0, lat0, lon0, alt0)
    assert float(up) == pytest.approx(350.0, rel=1e-12)
    assert float(east) == pytest.approx(0.0, abs=1e-6)
    assert float(north) == pytest.approx(0.0, abs=1e-6)


def test_small_north_step_matches_the_meridian_radius():
    # Moving by d(phi) along the meridian advances North by M(phi) d(phi), with M the
    # meridian radius of curvature -- a different radius from N(phi), which is why the
    # ellipsoid cannot be replaced by "a sphere of radius R".
    lat0, lon0, alt0 = 45.0, 7.0, 0.0
    dlat = 0.01
    east, north, _ = geodetic_to_enu(lat0 + dlat, lon0, alt0, lat0, lon0, alt0)
    m_rad = (
        WGS84_A_M
        * (1.0 - WGS84_E2)
        / (1.0 - WGS84_E2 * np.sin(np.radians(lat0)) ** 2) ** 1.5
    )
    assert float(north) == pytest.approx(m_rad * np.radians(dlat), rel=1e-5)
    assert float(east) == pytest.approx(0.0, abs=1e-9)


def test_small_east_step_matches_the_parallel_radius():
    # Along a parallel the radius is N(phi) cos(phi), the distance to the polar axis.
    lat0, lon0, alt0 = 45.0, 7.0, 0.0
    dlon = 0.01
    east, north, _ = geodetic_to_enu(lat0, lon0 + dlon, alt0, lat0, lon0, alt0)
    r_parallel = float(prime_vertical_radius_m(lat0)) * np.cos(np.radians(lat0))
    assert float(east) == pytest.approx(r_parallel * np.radians(dlon), rel=1e-5)
    # North picks up the meridian convergence, second order in the step: a parallel is
    # not a great circle, so following it bends slightly away from the tangent frame's
    # East axis by d^2 tan(phi) / (2 R) -- 5 cm over this 800 m step.
    d_m = r_parallel * np.radians(dlon)
    assert float(north) == pytest.approx(
        d_m**2 * np.tan(np.radians(lat0)) / (2.0 * 6_371_008.8), rel=0.02
    )


def test_rotation_preserves_the_ecef_distance():
    lat = np.array([44.0, 44.5, 45.5, 46.0])
    lon = np.array([6.0, 6.5, 7.5, 8.0])
    alt = np.array([1000.0, 2200.0, 1800.0, 900.0])
    lat0, lon0, alt0 = 45.0, 7.0, 1500.0
    east, north, up = geodetic_to_enu(lat, lon, alt, lat0, lon0, alt0)
    x, y, z = geodetic_to_ecef(lat, lon, alt)
    x0, y0, z0 = geodetic_to_ecef(lat0, lon0, alt0)
    ecef_norm = np.sqrt((x - x0) ** 2 + (y - y0) ** 2 + (z - z0) ** 2)
    assert np.sqrt(east**2 + north**2 + up**2) == pytest.approx(ecef_norm, rel=1e-12)


# --------------------------------------------------------------------------------
# The tangent-plane error budget quoted in sec:enu / app:geodesy-error
# --------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("d_m", "quoted_cm", "tol_cm"), [(20_000.0, 1.0, 0.5), (50_000.0, 13.0, 0.5)]
)
def test_chord_shortening_matches_the_quoted_centimetres(d_m, quoted_cm, tol_cm):
    # Measured along the equator, where the section of the ellipsoid is a circle of
    # radius exactly a, so the geometry is exactly the spherical one of app:geodesy: the
    # chord falls short of the arc d by d^3 / (24 R^2) -- ~1 cm at 20 km, 13 cm at
    # 50 km, against metre-scale GPS noise. This is why a fixed tangent frame is safe
    # over the extent of one flight.
    dlon = np.degrees(d_m / WGS84_A_M)
    east, north, up = geodetic_to_enu(0.0, dlon, 0.0, 0.0, 0.0, 0.0)
    chord = float(np.sqrt(east**2 + north**2 + up**2))
    deficit = d_m - chord
    assert deficit == pytest.approx(d_m**3 / (24.0 * WGS84_A_M**2), rel=1e-3)
    assert deficit * 100.0 == pytest.approx(quoted_cm, abs=tol_cm)


def test_up_is_not_an_altitude_over_a_flight_extent():
    # The reason the analysis keeps z = h instead of the rotation's U: a point ON the
    # surface 20 km away sits ~31 m BELOW the tangent plane (the sagitta d^2 / 2R), tens
    # of metres of pure geometry that have nothing to do with the flight's climb.
    d_m = 20_000.0
    dlon = np.degrees(d_m / WGS84_A_M)
    _, _, up = geodetic_to_enu(0.0, dlon, 0.0, 0.0, 0.0, 0.0)
    assert float(up) == pytest.approx(-(d_m**2) / (2.0 * WGS84_A_M), rel=1e-3)
    assert -float(up) == pytest.approx(31.4, abs=0.5)


def test_horizontal_coordinates_are_insensitive_to_the_altitude_channel():
    # sec:enu: h enters the horizontal ECEF components only through the radius factor
    # (N + h), so switching altitude channel -- at most a ~100 m inter-reference offset
    # -- rescales them by <~ 2e-5, under a metre across the ~50 km extent of a flight.
    lat0, lon0 = 45.0, 7.0
    lat = np.array([45.0, 45.11, 45.22, 45.33])
    lon = np.array([7.0, 7.143, 7.286, 7.43])
    alt = np.array([1200.0, 2400.0, 3000.0, 2100.0])
    east_a, north_a, _ = geodetic_to_enu(lat, lon, alt, lat0, lon0, alt[0])
    east_b, north_b, _ = geodetic_to_enu(
        lat, lon, alt + 100.0, lat0, lon0, alt[0] + 100.0
    )
    extent = float(np.max(np.hypot(east_a, north_a)))
    assert extent == pytest.approx(50_000.0, rel=0.05)  # a flight's worth of ground
    shift = np.hypot(east_b - east_a, north_b - north_a)
    assert float(np.max(shift)) < 1.0


def test_horizontal_distance_agrees_with_the_great_circle_distance():
    # Cross-check against the independent haversine used by the census scan. They differ
    # by the sphere-vs-ellipsoid model, not by an implementation error: a few parts in
    # 1e3 over tens of kilometres.
    lat0, lon0 = 45.0, 7.0
    lat = np.array([45.0, 45.1, 45.25, 44.9])
    lon = np.array([7.0, 7.1, 6.85, 7.3])
    east, north, _ = geodetic_to_enu(lat, lon, np.zeros_like(lat), lat0, lon0, 0.0)
    assert np.hypot(east, north) == pytest.approx(
        great_circle_m(lat0, lon0, lat, lon), rel=5e-3
    )


# --------------------------------------------------------------------------------
# Synthetic tracks with exactly known ENU geometry
# --------------------------------------------------------------------------------


def test_ecef_roundtrip_helper_is_exact():
    # Validates the test helper itself (Bowring's inverse) before the tracks below rely
    # on it: sub-micrometre and sub-nanodegree over the range of a real flight.
    lat = np.array([-45.0, 0.0, 12.0, 45.0, 67.0])
    lon = np.array([-179.0, 0.0, 45.0, 7.0, 120.0])
    alt = np.array([-50.0, 0.0, 900.0, 4200.0, 8000.0])
    x, y, z = geodetic_to_ecef(lat, lon, alt)
    back = np.array([_ecef_to_geodetic(*p) for p in zip(x, y, z, strict=True)])
    assert back[:, 0] == pytest.approx(lat, abs=1e-9)
    assert back[:, 1] == pytest.approx(lon, abs=1e-9)
    assert back[:, 2] == pytest.approx(alt, abs=1e-6)


def test_prescribed_enu_track_is_recovered_exactly():
    # A thermal: 3 turns of an exactly 200 m circle climbing at 2 m/s, prescribed in
    # ENU, projected onto the ellipsoid, and read back. Radius, centre, climb rate and
    # closure must come back to the micrometre -- the round trip has no free parameter.
    lat0, lon0, alt0 = 45.0, 7.0, 1500.0
    radius_m, climb_mps = 200.0, 2.0
    t = np.arange(0.0, 180.0, 1.0)
    angle = 2.0 * np.pi * t / 60.0
    east_true = radius_m * np.sin(angle)
    north_true = radius_m * (1.0 - np.cos(angle))
    up_true = climb_mps * t

    lat, lon, alt = _enu_to_geodetic(east_true, north_true, up_true, lat0, lon0, alt0)
    east, north, up = geodetic_to_enu(lat, lon, alt, lat0, lon0, alt0)

    assert east == pytest.approx(east_true, abs=1e-6)
    assert north == pytest.approx(north_true, abs=1e-6)
    assert up == pytest.approx(up_true, abs=1e-6)
    # The known properties, read back off the recovered track.
    assert np.hypot(east, north - radius_m) == pytest.approx(
        np.full(t.size, radius_m), abs=1e-6
    )
    assert np.polyfit(t, up, 1)[0] == pytest.approx(climb_mps, rel=1e-9)


# --------------------------------------------------------------------------------
# The stage as the pipeline calls it
# --------------------------------------------------------------------------------


def _synthetic_flight():
    """A 5-fix flight: straight leg east-north-east, climbing, with a stage-(ii) flag.

    Built backwards from exactly known ENU coordinates, so the stage under test has an
    exact answer to reproduce. The altitudes are the ones the prescribed ``up`` implies:
    ``h`` enters the horizontal components through the radius factor of eq:ecef, so a
    climb the geometry does not know about would shift ``E``/``N`` by a few centimetres
    -- small, real, and enough to blur what the assertion is checking.
    """
    lat0, lon0, alt0 = 45.0, 7.0, 1500.0
    east = np.array([0.0, 1000.0, 2000.0, 3000.0, 4000.0])
    north = np.array([0.0, 500.0, 1000.0, 1500.0, 2000.0])
    up = np.array([0.0, 20.0, 45.0, 60.0, 80.0])
    lat, lon, alt = _enu_to_geodetic(east, north, up, lat0, lon0, alt0)
    return pd.DataFrame(
        {
            "t": [0.0, 10.0, 20.0, 30.0, 40.0],
            "lat": lat,
            "lon": lon,
            "alt": alt,
            "alt_flagged": [False, False, True, False, False],
        }
    ), (east, north)


def test_to_local_frame_starts_at_the_horizontal_origin():
    fixes, (east_true, north_true) = _synthetic_flight()
    local, frame = to_local_frame(fixes)
    assert LOCAL_COLUMNS == ["t", "E", "N", "z"]
    assert list(local.columns)[: len(LOCAL_COLUMNS)] == LOCAL_COLUMNS
    # r(0) = 0 by construction (sec:notation).
    assert (local["E"].iloc[0], local["N"].iloc[0]) == pytest.approx((0.0, 0.0))
    assert local["E"].to_numpy() == pytest.approx(east_true, abs=1e-6)
    assert local["N"].to_numpy() == pytest.approx(north_true, abs=1e-6)
    # The frame is pinned to the first fix, which at this point in the pipeline is the
    # first fix of the trimmed track (sec:enu).
    assert frame == LocalFrame(
        lat0_deg=float(fixes["lat"].iloc[0]),
        lon0_deg=float(fixes["lon"].iloc[0]),
        alt0_m=float(fixes["alt"].iloc[0]),
    )
    assert frame.alt0_m == pytest.approx(1500.0, abs=1e-6)


def test_to_local_frame_keeps_the_altitude_at_its_measured_value():
    # sec:enu: z is the adopted channel, NOT re-zeroed and NOT the rotation's U. The
    # absolute height stays an observable; increments are unaffected either way.
    fixes, _ = _synthetic_flight()
    local, frame = to_local_frame(fixes)
    # Passed through fix by fix...
    assert local["z"].to_numpy() == pytest.approx(fixes["alt"].to_numpy())
    # ...not re-zeroed: it still reads an absolute ~1500 m at the origin...
    assert local["z"].iloc[0] == pytest.approx(1500.0, abs=1e-6)
    # ...and not the rotation's U, which measures height above the *tangent plane*: the
    # two already part company by the sagitta d^2 / (2 R) over a 4.5 km leg.
    _, _, up = geodetic_to_enu(
        fixes["lat"].to_numpy(),
        fixes["lon"].to_numpy(),
        fixes["alt"].to_numpy(),
        frame.lat0_deg,
        frame.lon0_deg,
        frame.alt0_m,
    )
    d_m = np.hypot(local["E"].to_numpy(), local["N"].to_numpy())
    assert local["z"].to_numpy() - frame.alt0_m - up == pytest.approx(
        d_m**2 / (2.0 * 6_371_008.8), rel=0.02, abs=1e-9
    )


def test_to_local_frame_does_not_touch_the_clock():
    # The clock zero is set at trimming (sec:trimming/sec:notation), not here; this
    # stage must carry t through untouched, including a non-zero start.
    fixes, _ = _synthetic_flight()
    fixes["t"] = fixes["t"] + 137.0
    local, _ = to_local_frame(fixes)
    assert local["t"].to_numpy() == pytest.approx(fixes["t"].to_numpy())


def test_to_local_frame_carries_other_columns_and_the_index():
    fixes, _ = _synthetic_flight()
    fixes.index = pd.RangeIndex(100, 105)
    local, _ = to_local_frame(fixes)
    assert list(local.columns) == [*LOCAL_COLUMNS, "alt_flagged"]
    assert local["alt_flagged"].tolist() == [False, False, True, False, False]
    assert list(local.index) == list(range(100, 105))
    # The consumed geographic columns are gone: E/N replace lat/lon, z replaces alt.
    assert not {"lat", "lon", "alt"} & set(local.columns)


def test_to_local_frame_honours_a_different_altitude_column():
    fixes, _ = _synthetic_flight()
    fixes = fixes.rename(columns={"alt": "gnss_alt"})
    local, frame = to_local_frame(fixes, alt_column="gnss_alt")
    assert local["z"].iloc[0] == pytest.approx(1500.0, abs=1e-6)
    assert frame.alt0_m == pytest.approx(1500.0, abs=1e-6)


def test_to_local_frame_rejects_an_empty_track():
    empty = pd.DataFrame({c: [] for c in ["t", "lat", "lon", "alt"]})
    with pytest.raises(ValueError, match="empty track"):
        to_local_frame(empty)


def test_to_local_frame_reports_a_missing_column():
    fixes, _ = _synthetic_flight()
    with pytest.raises(ValueError, match="alt"):
        to_local_frame(fixes.drop(columns=["alt"]))


def test_a_missing_altitude_does_not_destroy_the_position():
    # Stage (ii) keeps a fix whose position is good and marks only its altitude invalid.
    # Passed straight into eq:ecef that gap would take the position with it, since h
    # enters the horizontal components through the radius factor (N + h) -- the fix kept
    # because it was intact would come out as nan. The repair is safe for the reason
    # sec:enu gives for the choice of channel itself: h moves E and N by under a metre
    # across a whole flight.
    fixes, (east_true, north_true) = _synthetic_flight()
    intact, _ = to_local_frame(fixes)
    fixes.loc[[1, 3], "alt"] = np.nan
    holed, frame = to_local_frame(fixes)

    assert np.isfinite(holed[["E", "N"]].to_numpy()).all()
    # Millimetres: the interpolated altitude differs from the true one by metres, and
    # that moves the horizontal position by delta_h/(N + h) times it.
    assert holed["E"].to_numpy() == pytest.approx(east_true, abs=0.01)
    assert holed["N"].to_numpy() == pytest.approx(north_true, abs=0.01)
    # ...and the repaired altitude is nowhere near the position it saved: z keeps the
    # gap, for the single audited fill of stage (vi) to close.
    assert np.isnan(holed["z"].to_numpy()[[1, 3]]).all()
    assert holed["E"].to_numpy() == pytest.approx(intact["E"].to_numpy(), abs=0.01)
    assert np.isfinite(frame.alt0_m)


def test_an_altitude_missing_at_the_origin_still_places_the_frame():
    fixes, _ = _synthetic_flight()
    fixes.loc[0, "alt"] = np.nan
    local, frame = to_local_frame(fixes)

    assert np.isfinite(frame.alt0_m)
    assert (local["E"].iloc[0], local["N"].iloc[0]) == pytest.approx(
        (0.0, 0.0), abs=1e-6
    )
    assert np.isnan(local["z"].iloc[0])


def test_a_flight_with_no_altitude_at_all_still_maps():
    fixes, (east_true, _) = _synthetic_flight()
    fixes["alt"] = np.nan
    local, _ = to_local_frame(fixes)
    # Sea level is the fallback; the horizontal is insensitive to the choice at the
    # metre level, which is the whole argument.
    assert local["E"].to_numpy() == pytest.approx(east_true, abs=1.0)
    assert np.isnan(local["z"].to_numpy()).all()
