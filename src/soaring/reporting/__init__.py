r"""What the reporting scripts share: the disciplines, and the generated-macro contract.

``scripts/reporting/`` holds twenty-seven command-line entry points that measure the
archive and write ``thesis/generated/``, grouped into ``ch2_dataset/`` and
``ch3_global_transport/`` by the thesis chapter they feed, plus ``checks/`` and
``tools/`` for what is not chapter-specific. They are deliberately separate programs --
a pass costs hours and a reduction costs seconds, and mixing them would mean paying for
the pass to redraw a panel. What they are not is twenty-seven answers to *where is the
data* and *how is a macro written*, which is what they had become: this package holds
the one answer to each.

* :mod:`~soaring.reporting.disciplines` -- the two archives, their names in a macro and
  in a filename, and the resolver that reaches their processed tables.
* :mod:`~soaring.reporting.glider_class` -- the raw FFVL ``aile_class`` codes mapped onto
  the canonical labels of Table~\ref{tab:aileclass}.
* :mod:`~soaring.reporting.macros` -- writing the ``\\newcommand`` files, with the check
  for names LaTeX cannot accept applied at the point of writing.
* :mod:`~soaring.reporting.guards` -- refusing to write a file covering one discipline
  of two, and giving a script with no option parser the manners of one.
"""

from .disciplines import DISCIPLINES, HANG_GLIDERS, PARAGLIDERS, Discipline
from .glider_class import HANG_CLASS_MAP, PARA_CLASS_MAP, canonical_wing_class
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
    "HANG_CLASS_MAP",
    "HANG_GLIDERS",
    "PARAGLIDERS",
    "PARA_CLASS_MAP",
    "Discipline",
    "MacroNameError",
    "MacroWriter",
    "bare_cli",
    "canonical_wing_class",
    "check_name",
    "partial_write_refusal",
    "pct_of",
    "pct_true",
    "tex_int",
    "unreachable_reason",
    "write_macros",
]
