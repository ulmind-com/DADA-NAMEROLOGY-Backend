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


class TestNumeroscope:
    """Reproduces the two worked examples printed in the client's notes."""

    def test_client_example_18_6_1985(self):
        from datetime import date

        from app.numerology.numeroscope import build

        n = build(date(1985, 6, 18))
        assert (n["mulank"], n["bhagyank"]) == (9, 2)
        # the client prints:  x 99 2 / x 5 x / 88 11 6
        assert [[c["display"] or "x" for c in row] for row in n["grid"]] == [
            ["x", "99", "2"],
            ["x", "5", "x"],
            ["88", "11", "6"],
        ]
        assert sorted(n["missing_numbers"]) == [3, 4, 7]      # client: 4,3,7
        assert n["lucky_numbers"] == [1, 3, 5]                # client: 1,5,3
        assert n["unlucky_numbers"] == [2, 4, 8, 9]           # client: 2,4,8,9
        assert n["neutral_numbers"] == [6, 7]                 # client: 6,7

    def test_client_example_12_11_1995(self):
        from datetime import date

        from app.numerology.numeroscope import build

        n = build(date(1995, 11, 12))
        assert (n["mulank"], n["bhagyank"]) == (3, 2)         # client: M=3, B=2

    def test_single_placement_day_rule(self):
        """Born on 1-9, 20 or 30 the Mulank is already in the date, so it is not
        placed twice (client's rule, example 2/4/1984)."""
        from datetime import date

        from app.numerology.numeroscope import build

        n = build(date(1984, 4, 2))
        assert (n["mulank"], n["bhagyank"]) == (2, 1)         # client: M=2, B=1
        # digits of 02/04/1984 are 2,4,1,9,8,4 plus Bhagyank 1 -> two 1s, two 4s
        assert n["counts"]["2"] == 1                          # Mulank not added again
        assert n["counts"]["1"] == 2

    def test_ideal_grid_is_the_clients(self):
        from app.numerology.rules import ideal_grid

        assert ideal_grid() == [[4, 9, 2], [3, 5, 7], [8, 1, 6]]


class TestGoodCompounds:
    def test_client_good_compounds(self):
        from app.numerology.rules import good_compounds

        assert good_compounds(1)["compounds"] == [46, 64, 37, 55]
        assert good_compounds(3)["compounds"] == [66, 39, 30]
        assert good_compounds(5)["compounds"] == [41, 32, 50, 59]

    def test_number_flagged_when_its_compound_is_listed(self):
        from datetime import date

        # 9531199355 -> compound 50, which the client lists under compounds of 5
        r = analyse_mobile("9531199355", date(1985, 6, 18))
        assert r["good_compounds"]["is_listed"] is True
        assert r["good_compounds"]["root"] == 5


class TestCompatibilityTable:
    def test_matches_the_clients_printed_rows(self):
        from app.numerology.rules import number_compatibility

        one = number_compatibility(1)
        assert (one["planet"], one["role"]) == ("Sun", "King")
        assert one["lucky"] == [1, 2, 3, 5, 6, 9] and one["enemy"] == [8]
        assert one["neutral"] == [4, 7]
        five = number_compatibility(5)
        assert five["enemy"] == []          # client prints "None"
        four = number_compatibility(4)
        # 8* and 4* are the client's conditional relations
        assert 8 in four["lucky_conditional"] or 8 in four["enemy_conditional"]


class TestVehicleSequences:
    """The client's third pattern table: Serial & Sequential Series."""

    def test_ascending_and_descending_are_detected(self):
        asc = analyse_vehicle("WB 06 AB 1234")
        assert asc["sequence"]["pattern"].startswith("Ascending")
        desc = analyse_vehicle("KA 05 CD 9876")
        assert desc["sequence"]["pattern"].startswith("Descending")

    def test_no_sequence_reported_when_none_present(self):
        assert analyse_vehicle("WB 06 AB 1517")["sequence"] is None

    def test_smart_punctuation_survives(self):
        """Curly quotes must be converted, not dropped, or "won't" becomes "wont"."""
        from app.services.pdf import pdf_text

        assert pdf_text("won’t") == "won't"
        assert pdf_text("a — b") == "a - b"


class TestFinalisingAMobileNumber:
    """The client's third worked example, from 'Finalizing a beneficial mobile number'."""

    def test_client_example_11_3_1986(self):
        from datetime import date

        from app.numerology.numeroscope import recommend_mobile_total

        r = recommend_mobile_total(date(1986, 3, 11))
        assert (r["mulank"], r["bhagyank"]) == (2, 2)        # client: M=2, B=2
        assert sorted(r["missing_numbers"]) == [4, 5, 7]     # client: 4,5,7
        assert r["lucky_numbers"] == [1, 2, 3, 5]            # client: 1,2,3,5
        assert r["unlucky_numbers"] == [4, 8, 9]             # client: 4,8,9
        assert r["neutral_numbers"] == [6, 7]                # client: 6,7
        # the client concludes 5 can be recommended as the mobile total
        assert r["recommended_totals"] == [5]

    def test_recommendation_only_offers_benefic_totals(self):
        from datetime import date

        from app.numerology.numeroscope import recommend_mobile_total
        from app.numerology.rules import MOBILE_TOTAL_CLASS

        for d in (date(1990, 1, 15), date(1978, 7, 3), date(2001, 12, 28)):
            r = recommend_mobile_total(d)
            for n in r["recommended_totals"]:
                assert MOBILE_TOTAL_CLASS[n] == "benefic"
                assert n in r["lucky_numbers"]
                assert r["counts"][str(n)] == 0               # absent from the grid


class TestVehicleClientLists:
    """The client's 'Favorable vs Unfavorable Vehicle Numbers' summary."""

    def test_favourable_numbers_are_flagged(self):
        assert analyse_vehicle("WB 26 J 0050")["client_list"]["standing"] == "most_favourable"
        assert analyse_vehicle("WB 06 AB 1234")["client_list"]["standing"] == "most_favourable"

    def test_caution_numbers_are_flagged(self):
        c = analyse_vehicle("KA 01 AB 0013")["client_list"]
        assert c["standing"] == "caution" and c["label"] == "Karmic Rahu"
        assert analyse_vehicle("WB 06 AB 0016")["client_list"]["label"] == "Shattered Citadel"

    def test_unlisted_number_reports_nothing(self):
        assert analyse_vehicle("WB 06 AB 0021")["client_list"] is None
