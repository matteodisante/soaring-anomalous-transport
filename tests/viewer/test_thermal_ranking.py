"""Ground quality screening must not manufacture a new launch altitude."""

from soaring.viewer.thermal_ranking import launch_quality


def _records(path, altitudes, valid="A"):
    lines = ["HFDTE010120"]
    for i, z in enumerate(altitudes):
        seconds = i * 30
        lines.append(
            f"B12{seconds // 60:02d}{seconds % 60:02d}"
            f"4544836N00626542E{valid}01638{z:05d}"
        )
    path.write_text("\n".join(lines))
    return path


def test_first_altitude_jump_requires_two_witnesses(tmp_path):
    path = _records(tmp_path / "bad.igc", [-7, 1724, 1726])
    assert launch_quality(path, 45, 10) == "altitude_jump"
    path = _records(path, [500, 1724, 502])
    assert launch_quality(path, 45, 10) == "accepted"


def test_receiver_invalid_origin_is_excluded_but_missing_support_is_explicit(tmp_path):
    path = _records(tmp_path / "invalid.igc", [500, 501, 502], valid="V")
    assert launch_quality(path, 45, 10) == "invalid_gnss"
    path = _records(path, [500])
    assert launch_quality(path, 45, 10) == "unchecked"
