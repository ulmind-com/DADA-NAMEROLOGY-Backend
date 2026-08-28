"""The engine is checked against the values printed on the client's own spreadsheet."""

from datetime import date

from app.numerology.chaldean import analyse_name, destiny_number, radical_number, reduce_to_root
from app.numerology.mobile import analyse_mobile, clean_number, pair_grid
from app.numerology.name import full_name_report, quick_name
from app.numerology.vehicle import analyse_vehicle


class TestChaldean:
    def test_client_sheet_name(self):
        """'Pankaj Kabiraj' -> Pankaj 18 + Kabiraj 10 = compound 28, total 1."""
        r = analyse_name("Pankaj Kabiraj")
        assert [w["compound"] for w in r["words"]] == [18, 10]
        assert r["compound"] == 28
        assert r["root"] == 1
        assert r["chain"] == [28, 10, 1]

    def test_normalisation_ignores_case_and_punctuation(self):
        assert analyse_name("pankaj  kabiraj")["compound"] == 28
        assert analyse_name("Pankaj-Kabiraj!")["compound"] == 28

    def test_reduce(self):
        assert reduce_to_root(28) == 1
        assert reduce_to_root(9) == 9
        assert reduce_to_root(50) == 5

    def test_birth_numbers(self):
        assert radical_number(15) == 6
        assert radical_number(9) == 9
        # 15/08/1995 -> 1+5+0+8+1+9+9+5 = 38 -> 11 -> 2
        assert destiny_number(15, 8, 1995) == 2


class TestNameReport:
    def test_quick_matches_sheet_text(self):
        r = quick_name("Pankaj Kabiraj")
        assert r["compound"] == 28
        assert r["total"] == 1
        assert "again and again" in r["short"]
        assert r["needs_correction"] is True
        assert "not perfectly aligned" in r["suggest"]

    def test_favourable_name_needs_no_correction(self):
        r = quick_name("Ravi")  # R2+A1+V6+I1 = 10, the Wheel of Fortune
        assert r["compound"] == 10
        assert r["needs_correction"] is False
        assert "No correction is required" in r["suggest"]

    def test_full_report_shape(self):
        r = full_name_report("Pankaj Kabiraj", date(1995, 8, 15), "male")
        assert r["radical"]["number"] == 6
        assert r["destiny"]["number"] == 2
        assert 0 <= r["alignment_score"] <= 100
        assert r["word_details"][0]["word"] == "Pankaj"
        assert r["remedies"] and r["case_study"]["summary"]

    def test_corrections_are_favourable_and_similar(self):
        r = full_name_report("Pankaj Kabiraj", date(1995, 8, 15))
        assert r["similar_names"], "expected at least one correction"
        for s in r["similar_names"]:
            assert s["rating"] in ("excellent", "good")
            assert s["name"].lower().startswith("pankaj") or "kabiraj" in s["name"].lower()


class TestMobile:
    def test_client_sheet_number(self):
        """9531199355 -> compounding 50, total 5, and the nine pairs from the sheet."""
        r = analyse_mobile("9531199355")
        assert r["compound"] == 50
        assert r["total"] == 5
        assert [g["pair"] for g in r["grid"]] == [
            "9:5", "5:3", "3:1", "1:1", "1:9", "9:9", "9:3", "3:5", "5:5",
        ]
        assert r["grid_summary"]["total_pairs"] == 9

    def test_country_code_is_stripped(self):
        assert clean_number("+91 95311 99355") == "9531199355"
        assert clean_number("09531199355") == "9531199355"

    def test_zero_is_treated_as_an_amplifier(self):
        grid = pair_grid("109")
        assert grid[0]["pair"] == "1:0"
        assert "magnifies" in grid[0]["impact"]

    def test_owner_dob_changes_the_score(self):
        plain = analyse_mobile("9531199355")
        owned = analyse_mobile("9531199355", date(1995, 8, 15))
        assert "owner" in owned and "owner" not in plain
        assert owned["owner"]["radical"] == 6

    def test_short_number_is_invalid(self):
        assert analyse_mobile("12345")["valid"] is False


class TestVehicle:
    def test_plate_is_parsed(self):
        r = analyse_vehicle("WB 06 AB 1234")
        assert r["parts"]["state"] == "WB"
        assert r["running_number"] == "1234"
        assert r["compound"] == 10
        assert r["total"] == 1
        assert r["formatted"] == "WB 06 AB 1234"

    def test_unstructured_plate_still_scores(self):
        r = analyse_vehicle("XYZ789")
        assert r["total"] > 0
        assert 0 <= r["score"] <= 100
