r"""What the reporting scripts share: the disciplines, and the generated-macro contract.

``scripts/reporting/`` holds twenty-six command-line entry points that measure the
archive and write ``thesis/generated/``. They are deliberately separate programs -- a
pass costs hours and a reduction costs seconds, and mixing them would mean paying for
the pass to redraw a panel. What they are not is twenty-six answers to *where is the
data* and *how is a macro written*, which is what they had become: this package holds
the one answer to each.

* :mod:`~soaring.reporting.disciplines` -- the two archives, their names in a macro and
  in a filename, and the resolver that reaches their processed tables.
* :mod:`~soaring.reporting.macros` -- writing the ``\\newcommand`` files, with the check
  for names LaTeX cannot accept applied at the point of writing.
* :mod:`~soaring.reporting.guards` -- refusing to write a file covering one discipline
  of two, and giving a script with no option parser the manners of one.
"""

from .disciplines import DISCIPLINES, HANG_GLIDERS, PARAGLIDERS, Discipline
from .guards import bare_cli, partial_write_refusal, unreachable_reason
from .macros import (
    MacroNameError,
    MacroWriter,
    check_name,
    pct_of,
    pct_true,
    tex_int,
    write_macros,
)

__all__ = [
    "DISCIPLINES",
    "HANG_GLIDERS",
    "PARAGLIDERS",
    "Discipline",
    "MacroNameError",
    "MacroWriter",
    "bare_cli",
    "check_name",
    "partial_write_refusal",
    "pct_of",
    "pct_true",
    "tex_int",
    "unreachable_reason",
    "write_macros",
]
