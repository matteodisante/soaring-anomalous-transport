"""Check every UTC phase of coarser sampling against the archived hourly mean."""

import gzip
import importlib.util
import json
from pathlib import Path

import numpy as np

root = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location(
    "wind",
    root / "scripts/reporting/ch3_global_transport/generate_channel_wind_comparison.py",
)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
source = root / "revisions/channel-wind-2026-09-12"
records = json.loads((source / "input-manifest.json").read_text())["files"]
u = []
v = []
for r in records:
    d = json.loads(gzip.decompress((source / r["file"]).read_bytes()))
    a, b = m.components(
        d["hourly"]["wind_speed_10m"], d["hourly"]["wind_direction_10m"]
    )
    u.append(a)
    v.append(b)
u = np.array(u)
v = np.array(v)
w = np.cos(np.deg2rad([r["latitude"] for r in records]))
full = m.summarise(u, v, w)["axis_deg"]
checks = {}
for step in (3, 6, 12, 24):
    values = [
        m.summarise(u[:, offset::step], v[:, offset::step], w)["axis_deg"]
        for offset in range(step)
    ]
    errors = [abs((a - full + 90) % 180 - 90) for a in values]
    checks[str(step)] = {
        "axes_by_UTC_start_hour_deg": values,
        "maximum_separation_from_hourly_deg": max(errors),
    }
result = {
    "scope": (
        "Temporal subsampling of all-hour 10 m reference only; every phase "
        "offset tested; no new weather requests."
    ),
    "hourly_axis_deg": full,
    "subsampling_hours": checks,
}
(source / "sampling-check.json").write_text(json.dumps(result, indent=2) + "\n")
print(
    json.dumps(
        {k: v["maximum_separation_from_hourly_deg"] for k, v in checks.items()},
        indent=2,
    )
)
