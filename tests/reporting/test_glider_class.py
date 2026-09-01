"""The FFVL codes actually seen in ``catalog.csv``, mapped onto Table~\\ref{tab:aileclass}.

Every raw value asserted here was read off the real catalog (``aile_class``
``value_counts()``, both disciplines) rather than invented, so a future FFVL export that
drops or renames a code is exactly the case ``canonical_wing_class`` should raise on.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from soaring.reporting.glider_class import canonical_wing_class


class TestParagliders:
    @pytest.mark.parametrize(
        "raw, label",
        [
            ("A ou 1", "EN A"),
            ("B ou 1-2", "EN B"),
            ("C ou 2", "EN C"),
            ("D ou 2-3", "EN D"),
            ("CIVL Competition Class", "CCC"),
            ("Biplace", "tandem / non-certified"),
            ("Biplace non homologué", "tandem / non-certified"),
            ("non homologuée", "tandem / non-certified"),
            ("Open Class certification", "tandem / non-certified"),
            ("test en charge seulement", "tandem / non-certified"),
        ],
    )
    def test_a_raw_code_lands_on_its_table_label(self, raw, label):
        result = canonical_wing_class("paragliders", pd.Series([raw]))
        assert result[0] == label

    def test_four_uncertified_codes_pool_into_one_stratum(self):
        """Table~3.1's note: tandem and uncertified wings are pooled in one row."""
        raw = pd.Series(
            ["Biplace", "Biplace non homologué", "non homologuée",
             "Open Class certification", "test en charge seulement"]
        )
        result = canonical_wing_class("paragliders", raw)
        assert set(result) == {"tandem / non-certified"}

    def test_the_placeholder_is_unclassified_not_guessed(self):
        result = canonical_wing_class("paragliders", pd.Series(["0"]))
        assert pd.isna(result[0])

    def test_a_blank_or_missing_entry_is_unclassified(self):
        result = canonical_wing_class("paragliders", pd.Series(["", np.nan]))
        assert pd.isna(result).all()

    def test_surrounding_whitespace_does_not_defeat_the_lookup(self):
        result = canonical_wing_class("paragliders", pd.Series([" C ou 2 "]))
        assert result[0] == "EN C"

    def test_an_uncatalogued_code_raises_rather_than_entering_a_stratum(self):
        with pytest.raises(ValueError, match="paragliders.*Nouvelle Classe"):
            canonical_wing_class("paragliders", pd.Series(["Nouvelle Classe"]))


class TestHangGliders:
    @pytest.mark.parametrize(
        "raw",
        ["Delta Class 1", "Delta Class Sport", "Rigide Class 2", "Rigide Class 5"],
    )
    def test_the_fai_codes_pass_through_unchanged(self, raw):
        result = canonical_wing_class("hang gliders", pd.Series([raw]))
        assert result[0] == raw

    def test_the_placeholder_is_unclassified_here_too(self):
        result = canonical_wing_class("hang gliders", pd.Series(["0"]))
        assert pd.isna(result[0])

    def test_a_paraglider_code_is_not_recognised_for_hang_gliders(self):
        """The two maps are disjoint by discipline; a code from one is unmapped in the other."""
        with pytest.raises(ValueError, match="hang gliders"):
            canonical_wing_class("hang gliders", pd.Series(["C ou 2"]))


class TestUnknownDiscipline:
    def test_a_third_discipline_string_raises(self):
        with pytest.raises(ValueError, match="sailplanes"):
            canonical_wing_class("sailplanes", pd.Series(["A ou 1"]))
