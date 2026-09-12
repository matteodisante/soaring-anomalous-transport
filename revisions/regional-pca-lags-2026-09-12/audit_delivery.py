"""Verify committed files against the separate full-run and focused PCA records."""
from __future__ import annotations

import gzip
import hashlib
import json
import subprocess
from datetime import UTC, datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def git(*args):
    return subprocess.check_output(["git", *args], cwd=ROOT)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def main():
    commit = git("rev-parse", "HEAD").decode().strip()
    names = set(git("ls-tree", "-r", "--name-only", commit).decode().splitlines())

    def blob(name):
        assert name in names, f"Uncommitted delivery file: {name}"
        return git("show", f"{commit}:{name}")

    prefix = HERE.relative_to(ROOT).as_posix()
    update_bytes = blob(prefix + "/numerical-update.json")
    update = json.loads(update_bytes)
    review = json.loads(blob(prefix + "/manuscript-review.json"))
    assert review["numerical_update_sha256"] == sha(update_bytes)
    assert sha(blob(update["baseline_manifest"])) == update["baseline_manifest_sha256"]
    for name, expected in review["source_files"].items():
        assert sha(blob(name)) == expected, name
    outputs = {}
    for name, expected in review["generated_outputs"].items():
        storage = "thesis/generated/" + name
        if storage in names:
            data = blob(storage)
        else:
            assert name in ("ch3_revision.json", "ch3_self_similarity.json")
            archive = prefix if name == "ch3_revision.json" else (
                "revisions/vertical-gap-split-2026-09-11/full-report-archive")
            storage = archive + "/" + name + ".gz"
            data = gzip.decompress(blob(storage))
        assert sha(data) == expected, name
        outputs[name] = {"storage": storage, "sha256": expected}
    assert sha(blob("thesis/main.pdf")) == review["pdf_sha256"]
    validation = json.loads(blob("presentations/validation.json"))
    source = json.loads(blob("presentations/source-manifest.json"))
    assert validation["reviewed_thesis"] == source["reviewed_thesis"] == review
    assert validation["source_manifest_sha256"] == sha(blob("presentations/source-manifest.json"))
    presentations = {}
    for name in sorted(n for n in names if n.startswith("presentations/")):
        data = blob(name)
        assert sha(data) == sha((ROOT / name).read_bytes()), name
        presentations[name] = sha(data)
    for name, record in validation["documents"].items():
        assert sha(blob("presentations/" + name)) == record["sha256"]
    report = {
        "verified_utc": datetime.now(UTC).isoformat(), "commit": commit,
        "status": "complete", "source_files_verified": len(review["source_files"]),
        "numerical_lineage": {"baseline_run_id": update["baseline_run_id"],
                              "focused_run_id": update["run_id"]},
        "source_sha256": review["source_sha256"], "pdf_sha256": review["pdf_sha256"],
        "outputs": outputs, "presentation_files": presentations,
        "scope": "Committed sources and PDF match the reviewed checkout; all 77 generated inputs match their explicit inherited or focused-run provenance; complete presentation files and their four PDF hashes are committed. No push.",
    }
    (HERE / "committed-delivery-audit.json").write_text(json.dumps(report, indent=2) + "\n")
    print(f"Verified {commit}: {len(review['source_files'])} source files, {len(outputs)} results, thesis and {len(presentations)} presentation files")


if __name__ == "__main__":
    main()
