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


class TestBusinessNumerology:
    """Business names read the client's own Business Numerology database."""

    def test_uses_the_business_database_not_the_personal_chart(self):
        from app.numerology.name import quick_name
        from app.numerology.rules import business_compound, name_chart

        b = quick_name("Shree Traders", "business")
        assert "business" in b
        # the text is the client's "For Business" wording, not the personal chart
        assert b["description"] == business_compound(b["compound"])["business_text"]
        assert b["description"] != name_chart(b["compound"]).get("description")

    def test_carries_the_client_master_columns(self):
        from app.numerology.name import quick_name

        biz = quick_name("Shree Traders", "business")["business"]
        for field in ("archetype", "industries", "founder_compatibility",
                      "financial", "customer", "risk"):
            assert biz[field], f"{field} missing from the client master"
        assert 0 <= biz["stability_score"] <= 1
        assert 0 <= biz["expansion_score"] <= 1

    def test_client_star_ratings_drive_favourability(self):
        from app.numerology.rules import business_compound, business_favourable

        assert business_compound(1)["stars"] == 5
        assert business_favourable(1) is True
        # 13 is worded "challenging" by the client
        assert business_favourable(13) is False


class TestMobileClientChecklist:
    """The headline figure is the client's own Points to Remember, not a formula."""

    def test_checklist_maps_to_the_clients_points(self):
        r = analyse_mobile("9531199355")
        assert len(r["checklist"]) == 5
        assert r["score"] == round(sum(c["passed"] for c in r["checklist"]) * 100 / 5)

    def test_client_repeat_limits_are_enforced(self):
        r = analyse_mobile("9531199355")
        by_point = {c["point"]: c for c in r["checklist"]}
        # 9 repeats three times -> client says avoid multiples of 2,4,7,8,9
        assert by_point["Avoid multiples of 2, 4, 7, 8, 9."]["passed"] is False
        # 5 repeats three times -> client allows benefic digits at most twice
        assert by_point[
            "Multiples of benefic numbers 1, 3, 5, 6 should not be taken more than two times."
        ]["passed"] is False

    def test_multiple_number_traits_come_from_the_client(self):
        from app.numerology.rules import mobile_multiples

        r = analyse_mobile("9531199355")
        nine = next(m for m in r["multiples"] if m["digit"] == 9)
        assert nine["traits"] == mobile_multiples(9)["traits"]

    def test_a_clean_number_passes_every_point(self):
        # total 6 (benefic), benefic digits repeated at most twice, no zeroes
        r = analyse_mobile("112335")
        assert all(c["passed"] for c in r["checklist"]), r["checklist"]
        assert r["score"] == 100


class TestPdfSafety:
    def test_non_latin_and_bullets_are_stripped_not_boxed(self):
        """The base PDF fonts are Latin-1, so Devanagari would render as boxes."""
        from app.services.pdf import pdf_text

        assert pdf_text("Mercury (बुध)") == "Mercury"
        assert pdf_text("• point") == "· point"
        assert pdf_text(None) == ""

    def test_doubled_digits_fall_back_to_multiple_numbers(self):
        """The client lists no cross-combination for 1:1; its meaning comes from
        'Multiple Numbers and Their Effects' instead of being left blank."""
        from app.numerology.rules import mobile_multiples

        r = analyse_mobile("9531199355")
        cell = next(g for g in r["grid"] if g["pair"] == "1:1")
        assert cell["planets"] == mobile_multiples(1)["planet"]
        assert cell["impact"]
