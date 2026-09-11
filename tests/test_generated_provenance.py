"""Provenance contracts are metadata, not executable reporting code."""

import runpy
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
PROVENANCE = runpy.run_path(
    str(ROOT / "scripts/reporting/checks/generate_provenance.py")
)
DECLARED_OUTPUTS = PROVENANCE["declared_outputs"]


def test_dynamic_output_contract_is_read_without_executing_script():
    source = """
raise RuntimeError("a reporting script must never run during a provenance scan")
GENERATED_OUTPUTS = ("per_discipline.pdf", "audit.json")
"""
    assert DECLARED_OUTPUTS(source) == {"per_discipline.pdf", "audit.json"}


def test_mentions_and_input_paths_are_not_output_declarations():
    source = '''
"""Reads the previously generated input.pdf."""
INPUT = ROOT / "thesis" / "generated" / "input.pdf"
OUT_FIG = ROOT / "thesis" / "generated" / "output.pdf"
'''
    assert DECLARED_OUTPUTS(source) == {"output.pdf"}


@pytest.mark.parametrize(
    "contract", ['["figure.pdf"]', '("../figure.pdf",)', 'tuple(["figure.pdf"])']
)
def test_contract_requires_literal_tuple_of_basenames(contract):
    with pytest.raises(ValueError):
        DECLARED_OUTPUTS(f"GENERATED_OUTPUTS = {contract}")


def test_tex_inputs_do_not_claim_use_of_same_stem_json(tmp_path, monkeypatch):
    source = tmp_path / "chapter.tex"
    source.write_text(
        r"\input{generated/report}\includegraphics{generated/report_plot}"
    )
    uses = PROVENANCE["used_in"]
    monkeypatch.setitem(uses.__globals__, "SOURCES", [source])
    monkeypatch.setitem(uses.__globals__, "THESIS", tmp_path)
    _, files = uses(set())
    assert dict(files) == {
        "report.tex": {"chapter.tex"},
        "report_plot.pdf": {"chapter.tex"},
    }


def test_generated_table_references_are_followed_without_counting_definitions(
    tmp_path, monkeypatch
):
    source = tmp_path / "chapter.tex"
    generated = tmp_path / "generated"
    generated.mkdir()
    source.write_text(r"\input{generated/table}\input{generated/values}")
    (generated / "table.tex").write_text(r"Flights: \StatSegFlights")
    (generated / "values.tex").write_text(
        r"\newcommand{\StatSegFlights}{12}\newcommand{\StatUnused}{3}"
    )
    uses = PROVENANCE["used_in"]
    monkeypatch.setitem(uses.__globals__, "SOURCES", [source])
    monkeypatch.setitem(uses.__globals__, "THESIS", tmp_path)
    macros, _ = uses({"StatSegFlights", "StatUnused"})
    assert dict(macros) == {"StatSegFlights": {"generated/table.tex"}}


def test_commented_references_are_not_dependencies(tmp_path, monkeypatch):
    source = tmp_path / "chapter.tex"
    source.write_text(
        "% \\StatUnused \\input{generated/missing}\n"
        "10\\% of \\StatUsed % \\StatUnused\n"
        "line break \\\\% \\StatUnused\n"
    )
    uses = PROVENANCE["used_in"]
    monkeypatch.setitem(uses.__globals__, "SOURCES", [source])
    monkeypatch.setitem(uses.__globals__, "THESIS", tmp_path)
    macros, files = uses({"StatUsed", "StatUnused"})
    assert dict(macros) == {"StatUsed": {"chapter.tex"}}
    assert not files


def test_same_macro_family_from_two_files_keeps_both_producers():
    artefacts = {
        name: {"script": None, "step": None, "hook": False, "used_in": []}
        for name in ["alt_offset.tex", "altitude_noise.tex"]
    }
    macros = {
        "StatAltOffset": {"file": "alt_offset.tex", "used_in": []},
        "StatAltNoiseFlights": {
            "file": "altitude_noise.tex",
            "used_in": ["sections/03-dataset.tex"],
        },
    }
    page = PROVENANCE["render"](artefacts, macros)
    assert r"| `\StatAlt*` | `alt_offset.tex` |" in page
    assert r"| `\StatAlt*` | `altitude_noise.tex` |" in page
