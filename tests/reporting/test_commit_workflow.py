"""Committing or compiling reviewed inputs must not regenerate scientific products."""

import os
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


def git(root, *args):
    return subprocess.run(
        ["git", *args], cwd=root, capture_output=True, check=True
    ).stdout


@pytest.mark.parametrize(
    "staged_bad,working_bad", [(False, False), (False, True), (True, True)]
)
@pytest.mark.parametrize("eol", ["\n", "\r\n"])
def test_commit_checks_index_without_regeneration_or_staging(
    tmp_path, staged_bad, working_bad, eol
):
    git(tmp_path, "init", "-q")
    manuscript = tmp_path / "thesis/main.tex"
    manuscript.parent.mkdir()
    manuscript.write_text("staged text" + ("  " if staged_bad else "") + eol)
    git(tmp_path, "add", "thesis/main.tex")
    manuscript.write_text("working text" + ("  " if working_bad else "") + eol)
    staged_before = git(tmp_path, "diff", "--cached", "--binary")
    working_before = manuscript.read_bytes()
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    marker = tmp_path / "unexpected-generator-call"
    python = fake_bin / "python3"
    python.write_text('#!/bin/sh\nprintf called > "$AUDIT_TOOL_LOG"\nexit 0\n')
    python.chmod(0o755)
    result = subprocess.run(
        ["bash", str(ROOT / ".githooks/pre-commit")],
        cwd=tmp_path,
        env={
            **os.environ,
            "PATH": str(fake_bin) + os.pathsep + os.environ["PATH"],
            "AUDIT_TOOL_LOG": str(marker),
        },
        capture_output=True,
    )
    assert (result.returncode != 0) == staged_bad
    assert not marker.exists()
    assert manuscript.read_bytes() == working_before
    assert git(tmp_path, "diff", "--cached", "--binary") == staged_before


def test_convenience_compilation_does_not_regenerate_statistics(tmp_path):
    (tmp_path / "scripts").mkdir()
    helper = tmp_path / "scripts/build_docs.sh"
    shutil.copyfile(ROOT / "scripts/build_docs.sh", helper)
    (tmp_path / "thesis/generated").mkdir(parents=True)
    statistics = tmp_path / "thesis/generated/stats.tex"
    statistics.write_text("reviewed numbers\n")
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    for name, message in [("latexmk", "compile"), ("python3", "regenerate")]:
        executable = fake_bin / name
        executable.write_text(
            f'#!/bin/sh\nprintf "{message}\\n" >> "$AUDIT_TOOL_LOG"\n'
        )
        executable.chmod(0o755)
    calls = tmp_path / "tool-calls"
    subprocess.run(
        ["bash", str(helper), "thesis"],
        cwd=tmp_path,
        env={
            **os.environ,
            "PATH": str(fake_bin) + os.pathsep + os.environ["PATH"],
            "AUDIT_TOOL_LOG": str(calls),
        },
        capture_output=True,
        check=True,
    )
    assert calls.read_text() == "compile\n"
    assert statistics.read_text() == "reviewed numbers\n"
