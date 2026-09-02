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
    def test_quick_uses_client_chart(self):
        """Pankaj Kabiraj -> compound 28, total 1, meaning from the client's chart."""
        r = quick_name("Pankaj Kabiraj")
        assert r["compound"] == 28
        assert r["total"] == 1
        assert r["title"] == "Name Number 28"
        # description is the client's exact Name Number 28 text
        assert "emotional pain" in r["description"]
        # short is the client's one-line meaning for the root (1 = Communication)
        assert "Communication" in r["short"]
        # 28 is not on the client's avoid list, so no correction is forced
        assert r["needs_correction"] is False

    def test_client_avoid_number_needs_correction(self):
        """Compound 9 is on the client's explicit 'Avoid this name number' list."""
        from app.numerology.rules import name_favourable
        assert name_favourable(9) is False
        assert name_favourable(28) is True

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

    def test_zeros_are_excluded_from_pairs(self):
        """Client's Mobile Numerology notes exclude zeros before pairing."""
        grid = pair_grid("109")
        assert [g["pair"] for g in grid] == ["1:9"]  # the 0 is dropped
        assert all(g["rating"] in ("benefic", "neutral", "malefic") for g in grid)

    def test_universal_benefic_total(self):
        """Client rule: total 1/3/5/6 benefic, 4/7/8 malefic, 2/9 neutral."""
        assert analyse_mobile("9531199355")["total_class"] == "benefic"  # total 5

    def test_owner_dob_changes_the_score(self):
        plain = analyse_mobile("9531199355")
        owned = analyse_mobile("9531199355", date(1995, 8, 15))
        assert "owner" in owned and "owner" not in plain
        assert owned["owner"]["radical"] == 6

    def test_short_number_is_invalid(self):
        assert analyse_mobile("12345")["valid"] is False


class TestVehicle:
    def test_plate_uses_client_master(self):
        r = analyse_vehicle("WB 06 AB 1234")
        assert r["parts"]["state"] == "WB"
        assert r["running_number"] == "1234"
        assert r["compound"] == 10  # 1+2+3+4
        assert r["total"] == 1
        # planet, colours and score come from the client's 1-99 master
        assert "Sun" in r["total_profile"]["planet"]
        assert r["colors"]  # client-supplied favoured colours
        assert 0 <= r["score"] <= 100
        assert r["grade"]

    def test_unstructured_plate_still_scores(self):
        r = analyse_vehicle("XYZ789")
        assert r["total"] > 0
        assert 0 <= r["score"] <= 100
