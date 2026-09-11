"""Manuscript-only compilation cannot certify altered numerical results."""

import hashlib
import runpy
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
REVIEW = runpy.run_path(str(ROOT / "scripts/review_thesis.py"))


@pytest.fixture
def release(tmp_path):
    (tmp_path / "uv.lock").write_text("test environment")
    output = tmp_path / "thesis/generated/result.tex"
    output.parent.mkdir(parents=True)
    output.write_text("measured result")
    manifest = {
        "status": "complete",
        "pdf_sha256": "original PDF",
        "numerical_source_sha256": REVIEW["DRIVER"]["numerical_source_hash"](tmp_path),
        "outputs": {
            "result.tex": {"sha256": hashlib.sha256(output.read_bytes()).hexdigest()}
        },
    }
    return tmp_path, manifest


def test_authored_text_can_change_without_rewriting_numerical_provenance(release):
    root, manifest = release
    (root / "thesis/main.tex").write_text("A revised interpretation")
    REVIEW["validate_results"](root, manifest, {"result.tex"})


def test_changed_result_or_new_input_is_rejected(release):
    root, manifest = release
    with pytest.raises(ValueError, match="absent"):
        REVIEW["validate_results"](root, manifest, {"another.tex"})
    (root / "thesis/generated/result.tex").write_text("different measurement")
    with pytest.raises(ValueError, match="Generated result changed"):
        REVIEW["validate_results"](root, manifest, {"result.tex"})


def test_numerical_change_or_partial_run_requires_rebuild(release):
    root, manifest = release
    manifest["status"] = "failed"
    with pytest.raises(ValueError, match="complete numerical rebuild"):
        REVIEW["validate_results"](root, manifest, {"result.tex"})
    manifest["status"] = "complete"
    (root / "uv.lock").write_text("changed environment")
    with pytest.raises(ValueError, match="Numerical sources changed"):
        REVIEW["validate_results"](root, manifest, {"result.tex"})
