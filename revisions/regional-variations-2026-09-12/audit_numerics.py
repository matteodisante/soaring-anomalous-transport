"""Independently check support, moments, mixture distributions and saved inputs."""

from __future__ import annotations

import gzip
import hashlib
import json
from pathlib import Path

import numpy as np

from soaring.analysis.observables.archive_diagnostics import DiskFrames
from soaring.reporting import DISCIPLINES

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent


def digest(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def main():
    raw = gzip.decompress((HERE / "report.json.gz").read_bytes())
    report = json.loads(raw)
    assert report["status"] == "complete"
    assert raw == (HERE / "report.json").read_bytes()
    for name, expected in report["sources"].items():
        if digest(ROOT / name) != expected:
            assert name.endswith("/measure_regional_variations.py"), name
            executed = gzip.decompress((HERE / "executed-measure-regional-variations.py.gz").read_bytes())
            assert hashlib.sha256(executed).hexdigest() == expected
            # Only CLI coordinate-path resolution changed after this measured run.
            # Every numerical and statistical function retains the same Python AST.
            import ast
            old = {n.name: ast.dump(n) for n in ast.parse(executed).body if isinstance(n, ast.FunctionDef) and n.name != "main"}
            current = {n.name: ast.dump(n) for n in ast.parse((ROOT / name).read_text()).body if isinstance(n, ast.FunctionDef) and n.name != "main"}
            assert old == current
    for path, identity in report["inputs"].items():
        assert digest(path) == identity["sha256"], path
    audits = {}
    lags = np.array(report["contract"]["lags_s"])
    for name, glider in DISCIPLINES.items():
        directory = HERE / "arrays" / glider.slug
        rows = json.loads((directory / "flights.json").read_text())
        moments = np.load(directory / "moments.npy", mmap_mode="r")
        counts = np.load(directory / "counts.npy", mmap_mode="r")
        cache = json.loads((directory / "measurement.json").read_text())
        for filename, expected in cache["outputs"].items():
            assert digest(directory / filename) == expected
        original = next(Path(p).parent for p in report["inputs"]
                        if p.endswith(f"ch3-full-{glider.slug}/flights.json"))
        frames = DiskFrames(original)
        indexes = {row["flight_id"]: i for i, row in enumerate(frames.rows)}
        ids = [row["flight_id"] for row in rows]
        assert len(ids) == len(set(ids)) == report["results"][name]["n_regional_flights"]
        assert set(ids) == {row["flight_id"] for row in frames.rows
                            if row["region"] in report["contract"]["regions"]}
        np.testing.assert_array_equal(counts[:, 1, :, 0], counts[:, 1, :, 1])
        np.testing.assert_array_equal(counts[:, 1, :, 0], counts[:, 1, :, 2])
        assert np.all(counts[:, 1] <= counts[:, 0])
        common = counts[:, 2, lags <= 1000]
        np.testing.assert_array_equal(common, np.broadcast_to(common[:, :1, :1], common.shape))
        assert not counts[:, 2, lags > 1000].any()
        max_error = 0.0
        # Deterministic audit sample spans the entire archive order, including late flights.
        selected = np.unique(np.linspace(0, len(rows) - 1, 45).astype(int))
        for i in selected:
            row, positions = frames[indexes[ids[i]]]
            for j, tau in enumerate(lags):
                lag = int(tau / 10)
                for variant in range(3):
                    for p in (1, 2, 3):
                        pieces = []
                        for start, stop in row["segments"]:
                            span = p * lag if variant == 0 else 3 * lag
                            stride = lag
                            if variant == 2:
                                if tau > 1000:
                                    continue
                                span, stride = 300, 1
                            origins = np.arange(start, stop - span, stride)
                            # Direct binomial stencil, independent of the implementation's np.diff.
                            coefficients = {1: [-1, 1], 2: [1, -2, 1], 3: [-1, 3, -3, 1]}[p]
                            values = sum(c * positions[origins + k * lag]
                                         for k, c in enumerate(coefficients))
                            pieces.append(values)
                        values = np.concatenate(pieces) if pieces else np.empty((0, 2))
                        assert len(values) == counts[i, variant, j, p - 1]
                        if not len(values):
                            assert np.isnan(moments[i, variant, j, p - 1]).all()
                            continue
                        m = moments[i, variant, j, p - 1]
                        actual = (values**2).sum(axis=1).mean()
                        saved = m[2] + m[4] + m[0]**2 + m[1]**2
                        np.testing.assert_allclose(saved, actual, rtol=1e-9, atol=1e-7)
                        max_error = max(max_error, abs(saved - actual))
        result = report["results"][name]
        for distribution in result["distributions"]:
            probability = np.array(distribution["probability"])
            energy = np.array(distribution["change_squared_contribution"])
            np.testing.assert_allclose(probability.sum(), 1, atol=1e-11)
            assert np.all(probability >= 0) and np.all(energy >= 0)
            j = list(lags).index(distribution["lag_s"])
            record = result["regions"][distribution["region"]][distribution["variant"]]
            np.testing.assert_allclose(energy.sum(), record["rms_velocity_change_m_s"][j]**2, rtol=1e-10)
            assert 0 <= distribution["upper_decile_energy_share_bounds"][0] <= distribution["upper_decile_energy_share_bounds"][1] <= 1 + 1e-12
        standard = result["standardisation"]
        for region, record in standard["regions"].items():
            assert record["n_flights"] == sum(s["regional_counts"][region] for s in standard["strata"])
        audits[name] = {"all_regional_flights_verified": len(rows),
                        "direct_stencil_audit_flights": len(selected),
                        "largest_raw_moment_absolute_difference": max_error,
                        "distribution_moment_checks": len(result["distributions"]),
                        "standardisation_strata": standard["n_strata"]}
    record = {"status": "complete", "report_sha256": hashlib.sha256(raw).hexdigest(),
              "report_gzip_sha256": digest(HERE / "report.json.gz"), "checks": audits}
    (HERE / "numerical-audit.json").write_text(json.dumps(record, indent=2) + "\n")
    print(json.dumps(record, indent=2))


if __name__ == "__main__":
    main()
