"""A half-written file and a --help that starts a 43 GB pass: both guards, pinned.

Both failures happened. The first is silent when what it truncates is a figure -- the
build succeeds and a panel loses a curve -- and the second is silent by construction,
because a script with no argument parser cannot tell an option from nothing at all.
"""

from __future__ import annotations

import pytest

from soaring.reporting import DISCIPLINES, bare_cli
from soaring.reporting.guards import partial_write_refusal, unreachable_reason


class TestPartialWriteRefusal:
    def test_nothing_missing_is_no_refusal(self):
        assert partial_write_refusal([], "msd.tex") is None

    def test_a_missing_discipline_refuses_and_names_the_target(self):
        message = partial_write_refusal(["paragliders"], "msd.tex")
        assert message is not None
        assert "msd.tex" in message and "paragliders" in message

    def test_allow_partial_is_the_opt_out(self):
        assert (
            partial_write_refusal(["paragliders"], "msd.tex", allow_partial=True)
            is None
        )

    def test_the_reasons_are_carried_into_the_message(self):
        message = partial_write_refusal(
            ["paragliders"],
            "msd.tex",
            reasons=["paragliders: the disk is not mounted."],
        )
        assert "the disk is not mounted" in message

    def test_an_iterator_is_accepted_not_consumed_into_emptiness(self):
        """A generator passed for `missing` must not test as empty after one read."""
        assert partial_write_refusal(iter(["paragliders"]), "msd.tex") is not None


class TestUnreachableReason:
    def test_the_shipped_placeholder_is_named_as_such(self, monkeypatch):
        """The failure that caused this module: a data_root nobody configured."""
        monkeypatch.delenv("SOARING_PARA_DATA_ROOT", raising=False)
        reason = unreachable_reason(DISCIPLINES["paragliders"])
        assert reason is not None
        assert "placeholder" in reason
        assert "SOARING_PARA_DATA_ROOT" in reason, "it must name the variable to export"

    def test_an_unmounted_disk_is_not_reported_as_a_placeholder(self, monkeypatch):
        monkeypatch.setenv("SOARING_PARA_DATA_ROOT", "/nonexistent/soaring-test")
        reason = unreachable_reason(DISCIPLINES["paragliders"])
        assert reason is not None
        assert "not mounted" in reason
        assert "placeholder" not in reason


class TestBareCli:
    @pytest.mark.parametrize("flag", ["--help", "-h"])
    def test_help_prints_the_docstring_and_exits_zero(self, flag, capsys):
        with pytest.raises(SystemExit) as exit:
            bare_cli("What this script does.", argv=[flag])
        assert exit.value.code == 0
        assert "What this script does." in capsys.readouterr().out

    def test_help_lists_the_flags_the_script_does_handle(self, capsys):
        with pytest.raises(SystemExit):
            bare_cli("doc", argv=["--help"], known=["--redraw"])
        assert "--redraw" in capsys.readouterr().out

    def test_an_unknown_argument_exits_two_rather_than_working(self):
        """The failure this guards: --help fell through to main() and started a pass."""
        with pytest.raises(SystemExit) as exit:
            bare_cli("doc", argv=["--redrww"])
        assert exit.value.code == 2

    def test_a_known_flag_passes_through_untouched(self):
        assert bare_cli("doc", argv=["--redraw"], known=["--redraw"]) is None

    def test_no_arguments_is_the_normal_case_and_returns(self):
        assert bare_cli("doc", argv=[]) is None
