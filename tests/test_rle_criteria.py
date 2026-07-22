"""Tests for IUCN Criterion B threshold classification (rle.core.rle).

Thresholds are from the IUCN Red List of Ecosystems Guidelines v2.0 (2024),
Section 6.2, p.66:
    B1 (EOO, km²):   CR <= 2,000 ; EN <= 20,000 ; VU <= 50,000
    B2 (AOO, cells): CR <= 2     ; EN <= 20     ; VU <= 50
"""

import pytest

from rle.core.rle import (
    criterion_b_status,
    rle_category,
    CRITERION_B1_EOO_KM2,
    CRITERION_B2_AOO_CELLS,
)


@pytest.mark.unit
class TestCriterionB1EOO:
    """EOO (B1) thresholds map to the correct category (inclusive upper bounds)."""

    @pytest.mark.parametrize(
        "eoo_km2, expected",
        [
            (0, "CR"),
            (2_000, "CR"),        # boundary: <= 2,000
            (2_000.01, "EN"),     # just above CR
            (20_000, "EN"),       # boundary: <= 20,000
            (20_001, "VU"),       # just above EN
            (50_000, "VU"),       # boundary: <= 50,000
            (50_001, "LC"),       # above VU -> does not meet Criterion B
            (1_000_000, "LC"),
        ],
    )
    def test_b1_category(self, eoo_km2, expected):
        assert criterion_b_status(eoo_km2=eoo_km2)["B1"] == expected


@pytest.mark.unit
class TestCriterionB2AOO:
    """AOO (B2) thresholds map to the correct category (inclusive upper bounds)."""

    @pytest.mark.parametrize(
        "aoo_cells, expected",
        [
            (1, "CR"),
            (2, "CR"),     # boundary: <= 2
            (3, "EN"),     # just above CR
            (20, "EN"),    # boundary: <= 20
            (21, "VU"),    # just above EN
            (50, "VU"),    # boundary: <= 50
            (51, "LC"),    # above VU -> does not meet Criterion B
            (500, "LC"),
        ],
    )
    def test_b2_category(self, aoo_cells, expected):
        assert criterion_b_status(aoo_cells=aoo_cells)["B2"] == expected


@pytest.mark.unit
class TestCriterionBOverall:
    """Overall = most-threatened of B1 and B2; None-handling."""

    def test_overall_is_worst_of_b1_b2(self):
        # EOO -> VU (42,000 km²), AOO -> EN (15 cells); overall = EN.
        status = criterion_b_status(eoo_km2=42_000, aoo_cells=15)
        assert status == {"B1": "VU", "B2": "EN", "overall": "EN"}

    def test_overall_when_equal(self):
        status = criterion_b_status(eoo_km2=1_000, aoo_cells=1)
        assert status == {"B1": "CR", "B2": "CR", "overall": "CR"}

    def test_overall_least_concern(self):
        status = criterion_b_status(eoo_km2=200_000, aoo_cells=500)
        assert status == {"B1": "LC", "B2": "LC", "overall": "LC"}

    def test_missing_eoo_uses_aoo_only(self):
        status = criterion_b_status(eoo_km2=None, aoo_cells=10)
        assert status == {"B1": None, "B2": "EN", "overall": "EN"}

    def test_missing_aoo_uses_eoo_only(self):
        status = criterion_b_status(eoo_km2=1_500, aoo_cells=None)
        assert status == {"B1": "CR", "B2": None, "overall": "CR"}

    def test_both_missing(self):
        assert criterion_b_status() == {"B1": None, "B2": None, "overall": None}


@pytest.mark.unit
class TestRleCategoryLookup:
    """rle_category() resolves abbreviations to palette entries."""

    def test_known_category(self):
        vu = rle_category("VU")
        assert vu["name"] == "Vulnerable"
        assert vu["background_color"] == "yellow"
        assert vu["threatened"] is True

    def test_least_concern_not_threatened_flag_absent(self):
        lc = rle_category("LC")
        assert lc["name"] == "Least Concern"
        assert "threatened" not in lc  # only threatened categories carry the flag

    def test_unknown_category_returns_none(self):
        assert rle_category("ZZ") is None

    def test_every_criterion_b_category_is_in_palette(self):
        # Every category the thresholds can emit must resolve in the palette.
        emitted = {cat for _, cat in CRITERION_B1_EOO_KM2 + CRITERION_B2_AOO_CELLS}
        emitted.add("LC")
        for abbr in emitted:
            assert rle_category(abbr) is not None, abbr
