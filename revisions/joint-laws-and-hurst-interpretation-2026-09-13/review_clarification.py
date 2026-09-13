"""Review two interpretive additions against unchanged numerical results."""

from __future__ import annotations

import hashlib
import json
import pickle
import re
import subprocess
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
from scipy.integrate import quad

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
PARENT = ROOT / "revisions/channel-wind-flight-altitude-2026-09-13"
ARRAYS = (
    ROOT
    / "revisions/vertical-gap-split-2026-09-11/recovery-runs"
    / "20260912T104500Z-5cfc4e8c/arrays"
)


def digest(path):
    """Identify complete file bytes without loading large reports twice."""
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def save(name, value):
    """Save a readable review record."""
    (HERE / name).write_text(json.dumps(value, indent=2) + "\n")


def check_interpretation():
    """Check the analytical example and inspect saved variation curves."""
    checks = []
    for x in (0.01, 0.1, 1.0, 10.0):
        # Set sigma_v^2 = t_p = 1. Integrate the covariance over adjacent
        # intervals independently of the closed-form V2 expression.
        increment_variance = (
            2 * quad(lambda s, bound=x: (bound - s) * np.exp(-s), 0, x)[0]
        )
        adjacent_covariance = quad(
            lambda t, bound=x: quad(lambda s: np.exp(-(t - s)), 0, bound)[0], x, 2 * x
        )[0]
        integrated = 2 * increment_variance - 2 * adjacent_covariance
        closed = 2 * (2 * x - 3 + 4 * np.exp(-x) - np.exp(-2 * x))
        np.testing.assert_allclose(closed, integrated, rtol=1e-8, atol=1e-14)
        checks.append(
            {"tau_over_tp": x, "closed_form": closed, "covariance_integral": integrated}
        )
    report_path = ROOT / "thesis/generated/ch3_revision.json"
    report = json.loads(report_path.read_text())
    diagnostics = {}
    for discipline, slug in (("paragliders", "para"), ("hang gliders", "hang")):
        path = ARRAYS / f"ch3-full-{slug}/measurement.pkl"
        with path.open("rb") as stream:
            measured = pickle.load(stream)
        result = report["results"][discipline]
        lag = np.asarray(result["lags_s"], dtype=float)
        variation = np.nanmean(measured["variations"], axis=0)
        slopes = [
            float(np.polyfit(np.log10(lag), np.log10(v), 1)[0]) for v in variation
        ]
        np.testing.assert_allclose(slopes, result["alpha"], rtol=1e-12)
        np.testing.assert_array_equal(
            np.isfinite(measured["variations"][:, 1]).sum(axis=0),
            result["n_order_two"],
        )
        diagnostics[discipline] = {
            "saved_measurement_sha256": digest(path),
            "lags_s": lag.tolist(),
            "equal_flight_v2_m2": variation[1].tolist(),
            "interval_velocity_change_rms_ms": (np.sqrt(variation[1]) / lag).tolist(),
            "reproduced_slopes": slopes,
            "fixed_cohort_slopes_from_report": result["fixed_alpha"],
        }
    return {
        "status": "complete",
        "report_sha256": digest(report_path),
        "analytical_covariance_checks": checks,
        "saved_curve_diagnostics": diagnostics,
        "interpretation": (
            "The exponential-velocity example proves that stationary increments "
            "can coexist with a V2 crossover from cubic to linear growth. It is "
            "not fitted to the flights. Saved flight curves reproduce the current "
            "slopes and reveal a nonmonotone interval-velocity-change scale; they "
            "do not identify a single physical cause."
        ),
    }


def main():
    """Preserve numerical provenance and review the newly compiled manuscript."""
    parent_path = PARENT / "manuscript-review.json"
    parent = json.loads(parent_path.read_text())
    assert parent["status"] == "complete"
    sources = {n: digest(ROOT / n) for n in parent["source_files"]}
    changed = [n for n, h in sources.items() if h != parent["source_files"][n]]
    assert changed == ["thesis/sections/04-global-transport.tex"], changed
    for name, expected in parent["generated_outputs"].items():
        assert digest(ROOT / "thesis/generated" / name) == expected, name
    for name, expected in parent["external_input_files"].items():
        assert digest(ROOT / name) == expected, name
    save("interpretation-check.json", check_interpretation())
    subprocess.run(
        [
            "latexmk",
            "-pdf",
            "-halt-on-error",
            "-interaction=nonstopmode",
            "-cd",
            "thesis/main.tex",
        ],
        cwd=ROOT,
        check=True,
        stdout=subprocess.DEVNULL,
    )
    log = (ROOT / "thesis/main.log").read_text()
    assert not re.search(
        r"Overfull|LaTeX Warning:|Undefined control sequence|Fatal error", log
    )
    assert sources == {n: digest(ROOT / n) for n in sources}
    review = dict(parent)
    review.update(
        {
            "reviewed_utc": datetime.now(UTC).isoformat(),
            "parent_manuscript_review_sha256": digest(parent_path),
            "changed_manuscript_sources": changed,
            "source_files": sources,
            "pdf_sha256": digest(ROOT / "thesis/main.pdf"),
            "pages": int(
                re.search(r"Output written on main.pdf \((\d+) pages", log)[1]
            ),
            "interpretation_check_sha256": digest(HERE / "interpretation-check.json"),
            "review_script_sha256": digest(__file__),
            "scope": (
                "Clarify spatial one-lag versus temporal joint laws, and develop the "
                "kinematic, finite-persistence and sampling explanations for effective "
                "second-difference slopes. All 98 generated numerical products and "
                "all numerical sources remain unchanged."
            ),
        }
    )
    save("manuscript-review.json", review)
    print(f"Reviewed {review['pages']} pages; all numerical identities unchanged")


if __name__ == "__main__":
    main()
