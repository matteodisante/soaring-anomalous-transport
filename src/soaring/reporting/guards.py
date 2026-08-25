r"""Two ways a reporting script can quietly give a wrong answer, and their guards.

Both were found the same way: by causing them.

**A generator that reaches one discipline of two writes half a file.** It does not
fail -- it prints a skip line and carries on -- and the ``.tex`` it leaves behind is
missing every macro the absent discipline owns. The thesis then fails to build on a
macro it quotes, and the message names a LaTeX line rather than the run that truncated
the file. Worse, if what it truncates is a *figure*, nothing fails at all: the build
succeeds and one panel silently loses a curve. :func:`partial_write_refusal` is the
shared refusal, and :func:`unreachable_reason` says *why* a discipline was missed,
which is the part that turns a long confusion into a one-line fix.

**A script with no argument parser treats ``--help`` as work.** Ten of these read
``sys.argv`` informally or not at all, so ``--help`` falls through to ``main()`` and
starts a pass over a 43 GB table. :func:`bare_cli` gives them the one behaviour every
command-line tool is expected to have, without making each grow an ``ArgumentParser``
it has no options to put in.
"""

from __future__ import annotations

import sys
from collections.abc import Iterable, Sequence
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .disciplines import Discipline

# A data_root left as a placeholder, e.g. `/Volumes/<YOUR_DISK>/paragliders/igc`.
# It is a path that resolves, exists nowhere, and is indistinguishable from an unmounted
# disk unless it is looked for -- which is why it is looked for. Both configs in this
# repository carry a real path now; a checkout on another machine will not.
_PLACEHOLDER = ("<", ">")


def unreachable_reason(
    discipline: Discipline, require: str = "fixes.parquet"
) -> str | None:
    """Why this discipline's tables cannot be read, in words a caller can print.

    Args:
        discipline: A :class:`~soaring.reporting.disciplines.Discipline`.
        require: The table the caller needs, as for
            :meth:`~soaring.reporting.disciplines.Discipline.derived_dir`.

    Returns:
        One sentence naming the cause and the fix, or ``None`` if the tables read.
        The four causes are kept apart because their fixes differ: an unconfigured
        config needs an environment variable, an unmounted disk needs the disk, and a
        missing table needs the pass that writes it re-run.
    """
    try:
        cfg = discipline.config()
    except FileNotFoundError:
        return f"{discipline.name}: no config file for it; nothing to read."
    except KeyError:
        return (
            f"{discipline.name}: no data_root configured. "
            f"Export {discipline.env} to point at the archive."
        )

    root = str(cfg.data_root)
    if any(ch in root for ch in _PLACEHOLDER):
        return (
            f"{discipline.name}: data_root is still a placeholder ({root}). "
            f"Export {discipline.env} to point at the real archive -- without it this "
            "discipline is skipped and whatever is written covers the other one alone."
        )
    if not cfg.data_root.is_dir():
        return f"{discipline.name}: {root} is not mounted."
    if not (cfg.derived_dir / require).is_file():
        return (
            f"{discipline.name}: {cfg.derived_dir / require} is missing. "
            "Run the pass that writes it."
        )
    return None


def partial_write_refusal(
    missing: Iterable[str],
    target: str,
    *,
    allow_partial: bool = False,
    reasons: Iterable[str] = (),
) -> str | None:
    """The message to print, and stop on, when only some disciplines were reached.

    Args:
        missing: Names of the disciplines that were not reached.
        target: What would have been written, for the message (``"msd.tex"``).
        allow_partial: The caller's opt-out. When true this always returns ``None``.
        reasons: Per-discipline explanations, normally from :func:`unreachable_reason`.

    Returns:
        The message, or ``None`` when there is nothing to refuse -- either because every
        discipline was reached or because the caller asked for a partial run. A caller
        prints it and returns a non-zero exit code; it never writes and then complains.
    """
    missing = list(missing)
    if not missing or allow_partial:
        return None
    lines = [
        f"refusing to write {target}: {', '.join(missing)} not reached.",
        "It would carry the other discipline alone -- a half table of macros the "
        "thesis fails to build on, or a figure that silently loses a curve.",
    ]
    lines += [f"  {r}" for r in reasons if r]
    lines.append(
        "Fix the above, or pass --allow-partial if a one-discipline run is meant."
    )
    return "\n".join(lines)


def bare_cli(
    doc: str | None,
    *,
    argv: Sequence[str] | None = None,
    known: Iterable[str] = (),
) -> None:
    """Give a script with no option parser the manners of one, then return.

    ``--help`` prints the module docstring and exits 0; anything unrecognised exits 2
    with a message. Without this a script whose ``main()`` takes no arguments treats
    ``--help`` as an instruction to start work -- which on this repository means a pass
    over the fix table.

    Args:
        doc: The module docstring, normally ``__doc__``.
        argv: Arguments to inspect; defaults to ``sys.argv[1:]``.
        known: Flags the script does handle itself, e.g. ``["--redraw"]``.

    Raises:
        SystemExit: 0 for ``--help``/``-h``, 2 for anything unrecognised.
    """
    args = list(sys.argv[1:] if argv is None else argv)
    if "--help" in args or "-h" in args:
        print((doc or "No description.").strip())
        extra = list(known)
        if extra:
            print("\nOptions: " + ", ".join(extra))
        raise SystemExit(0)
    unknown = [a for a in args if a not in set(known)]
    if unknown:
        print(
            f"unrecognised argument(s): {' '.join(unknown)}\n"
            "This script takes no options beyond "
            f"{', '.join(['--help', *known])}.",
            file=sys.stderr,
        )
        raise SystemExit(2)
