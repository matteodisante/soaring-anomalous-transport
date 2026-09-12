"""Verify committed source/results against the completed numerical and PDF review.

Read Git blobs, not the working tree: unrelated uncommitted viewer edits must not
be mistaken for executed scientific source. Large report JSON may be stored as its
complete, byte-preserving gzip archive. No remote operation is performed.
"""
from __future__ import annotations

import argparse
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


def numerical(name):
    path = Path(name)
    return ((name.startswith(("src/", "scripts/")) and path.suffix == ".py")
            or (path.parent.as_posix() == "configs" and path.suffix == ".yaml")
            or name == "uv.lock")


def guarded(name):
    path = Path(name)
    return (numerical(name)
            or (path.parent.as_posix() == "thesis/sections" and path.suffix == ".tex")
            or (name.startswith("thesis/appendices/") and path.suffix == ".tex")
            or name in ("thesis/main.tex", "thesis/references.bib"))


def main(run, revision, output):
    commit = git("rev-parse", "--verify", f"{revision}^{{commit}}").decode().strip()
    manifest = json.loads((run / "review-inputs/manifest.json").read_text())
    review = json.loads((run / "review-inputs/manuscript-review.json").read_text())
    if manifest["status"] != "complete":
        raise ValueError("A completed numerical run is required")
    if sha((run / "review-inputs/manifest.json").read_bytes()) != review["numerical_manifest_sha256"]:
        raise ValueError("Review refers to different numerical inputs")
    names = set(git("ls-tree", "-r", "--name-only", "-z", commit).decode().rstrip("\0").split("\0"))

    def blob(name):
        if name not in names:
            raise ValueError(f"Required committed file missing: {name}")
        return git("show", f"{commit}:{name}")

    sources = {name: blob(name) for name in sorted(names) if guarded(name)}

    def source_digest(predicate):
        digest = hashlib.sha256()
        for name, data in sources.items():
            if predicate(name):
                digest.update(name.encode() + b"\0")
                digest.update(data)
        return digest.hexdigest()

    full = source_digest(guarded)
    numeric = source_digest(numerical)
    if numeric != manifest["numerical_source_sha256"]:
        raise ValueError("Committed numerical source differs from the executed run")
    if full != review["source_sha256"]:
        raise ValueError("Committed manuscript/source differs from the reviewed PDF")
    results = {}
    for name, expected in manifest["outputs"].items():
        path = "thesis/generated/" + name
        if path in names:
            data = blob(path)
            storage = path
        elif name in ("ch3_revision.json", "ch3_self_similarity.json"):
            storage = HERE.relative_to(ROOT).as_posix() + "/full-report-archive/" + name + ".gz"
            data = gzip.decompress(blob(storage))
        else:
            raise ValueError(f"Numerical input not committed: {path}")
        if sha(data) != expected["sha256"]:
            raise ValueError(f"Committed numerical result differs: {name}")
        results[name] = {"storage": storage, "sha256": sha(data)}
    if sha(blob("thesis/main.pdf")) != review["pdf_sha256"]:
        raise ValueError("Committed PDF differs from the final reviewed PDF")
    report = {
        "verified_utc": datetime.now(UTC).isoformat(), "commit": commit,
        "numerical_run": manifest["run_id"],
        "source_sha256": full, "numerical_source_sha256": numeric,
        "source_files": len(sources), "results": results,
        "pdf_sha256": review["pdf_sha256"],
        "scope": "Committed code/configuration matches the executed numerical run; committed manuscript and PDF match the final review; every recorded input is present with identical bytes, directly or in lossless gzip storage.",
    }
    output.write_text(json.dumps(report, indent=2) + "\n")
    print(f"Verified {commit}: {len(sources)} source files, {len(results)} results and final PDF")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", required=True, type=Path)
    parser.add_argument("--revision", default="HEAD")
    parser.add_argument("--output", type=Path, default=HERE / "committed-release-audit.json")
    args = parser.parse_args()
    main(args.run.resolve(), args.revision, args.output)
