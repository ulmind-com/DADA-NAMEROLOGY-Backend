"""Mobile-number numerology: compound, total and the consecutive-pair TOTAL GRID."""

from __future__ import annotations

import re
from collections import Counter
from datetime import date

from . import rules
from .chaldean import destiny_number, radical_number, reduce_to_root, reduction_chain
from .numeroscope import build as build_numeroscope
from .numeroscope import good_compounds_for

_DIGITS = re.compile(r"\D+")


def clean_number(raw: str) -> str:
    digits = _DIGITS.sub("", raw or "")
    # drop common country prefixes so 10-digit Indian numbers analyse consistently
    if len(digits) == 12 and digits.startswith("91"):
        digits = digits[2:]
    elif len(digits) == 11 and digits.startswith("0"):
        digits = digits[1:]
    return digits


_RATING_META = {
    "benefic": {"label": "Benefic", "color": "#1E9E6A", "score": 2},
    "neutral": {"label": "Neutral", "color": "#E0A32E", "score": 1},
    "malefic": {"label": "Malefic", "color": "#D24B4B", "score": 0},
}


def pair_grid(digits: str) -> list[dict]:
    """Internal combinations per the client's Mobile Numerology notes: zeros are
    excluded, then consecutive digit pairs are read and classified benefic /
    neutral / malefic from the client's combination tables."""
    clean = digits.replace("0", "")
    grid = []
    for i in range(len(clean) - 1):
        a, b = int(clean[i]), int(clean[i + 1])
        combo = rules.mobile_combination(a, b)
        if a == b and not combo:
            # the client lists no cross-combination for a doubled digit; its effect is
            # covered by "Multiple Numbers and Their Effects" instead
            mult = rules.mobile_multiples(a)
            combo = {
                "rating": "benefic" if a in rules.mobile_multiple_rules().get("benefic_digits", []) else "neutral",
                "planets": mult.get("planet", ""),
                "traits": mult.get("traits", []),
            }
        rating = combo.get("rating", "neutral")
        meta = _RATING_META[rating]
        traits = combo.get("traits", [])
        grid.append({
            "pair": f"{a}:{b}",
            "index": i,
            "first": a, "second": b,
            "planets": combo.get("planets", ""),
            "rating": rating,
            "label": meta["label"],
            "color": meta["color"],
            "score": meta["score"],
            "impact": "; ".join(traits[:4]) if traits else "",
        })
    return grid


def _grid_score(grid: list[dict]) -> int:
    if not grid:
        return 0
    return round(sum(g["score"] for g in grid) * 100 / (2 * len(grid)))


def client_checklist(digits: str, total: int, grid: list[dict]) -> list[dict]:
    """The client's own 'Points to Remember' turned into pass/fail checks.

    Every check maps one-to-one to a numbered point in the client's Mobile
    Numerology notes; nothing here is invented.
    """
    counts = Counter(digits)
    mrules = rules.mobile_multiple_rules()
    benefic = mrules.get("benefic_digits", [1, 3, 5, 6])
    max_ben = mrules.get("benefic_max_repeats", 2)
    avoid_multiples = [2, 4, 7, 8, 9]

    total_ok = rules.MOBILE_TOTAL_CLASS.get(total) == "benefic"
    malefic_pairs = [g["pair"] for g in grid if g["rating"] == "malefic"]

    bad_multiples = [
        f"{d}×{counts[str(d)]}" for d in avoid_multiples if counts.get(str(d), 0) > 1
    ]
    over_benefic = [
        f"{d}×{counts[str(d)]}" for d in benefic if counts.get(str(d), 0) > max_ben
    ]

    zeros = counts.get("0", 0)
    n = len(digits)
    zero_at_end = digits.endswith("0")
    zero_in_centre = "0" in digits[max(0, n // 2 - 1): n // 2 + 2]

    return [
        {"point": "The mobile total should be good.",
         "passed": total_ok,
         "detail": f"Total {total} is {rules.MOBILE_TOTAL_CLASS.get(total, 'neutral')}."},
        {"point": "The mobile internal pairs should be good.",
         "passed": not malefic_pairs,
         "detail": ("No malefic pairs." if not malefic_pairs
                    else f"Malefic pairs: {', '.join(malefic_pairs)}.")},
        {"point": "Avoid multiples of 2, 4, 7, 8, 9.",
         "passed": not bad_multiples,
         "detail": ("None repeat." if not bad_multiples
                    else f"Repeated: {', '.join(bad_multiples)}.")},
        {"point": "Multiples of benefic numbers 1, 3, 5, 6 should not be taken more than two times.",
         "passed": not over_benefic,
         "detail": ("Within the limit." if not over_benefic
                    else f"Over the limit: {', '.join(over_benefic)}.")},
        {"point": "Too many zeroes should be avoided, especially at the centre and the end.",
         "passed": zeros <= 1 and not zero_at_end and not zero_in_centre,
         "detail": (f"{zeros} zero(s)"
                    + (", one at the end" if zero_at_end else "")
                    + (", one near the centre" if zero_in_centre else "")
                    + ".") if zeros else "No zeroes."},
    ]


def _verdict(score: int) -> dict:
    if score >= 75:
        return {"level": "excellent", "label": "Excellent Number", "color": "#0E8F5E",
                "note": "This number supports you strongly. Keep it as your primary number."}
    if score >= 60:
        return {"level": "good", "label": "Good Number", "color": "#1E9E6A",
                "note": "A supportive number. Minor weak pairs exist but the overall flow is positive."}
    if score >= 45:
        return {"level": "average", "label": "Average Number", "color": "#E0A32E",
                "note": "Neither helping nor harming. Results depend entirely on your own effort."}
    if score >= 30:
        return {"level": "weak", "label": "Weak Number", "color": "#E07A2E",
                "note": "Several conflicting pairs. Consider switching this to a secondary number."}
    return {"level": "bad", "label": "Not Recommended", "color": "#D24B4B",
            "note": "This number carries too many conflicting pairs. Changing it is strongly advised."}


def analyse_mobile(
    number: str,
    dob: date | None = None,
    name: str = "",
) -> dict:
    digits = clean_number(number)
    compound = sum(int(d) for d in digits) if digits else 0
    total = reduce_to_root(compound)
    grid = pair_grid(digits)
    total_class = rules.MOBILE_TOTAL_CLASS.get(total, "neutral")
    # The client gives no numeric score, only the "Points to Remember" checklist —
    # so the headline figure is simply how many of those points the number passes.
    checklist = client_checklist(digits, total, grid)
    passed = sum(1 for c in checklist if c["passed"])
    score = round(passed * 100 / len(checklist))

    counts = Counter(digits)
    missing = [n for n in "123456789" if n not in counts]
    repeated = {d: c for d, c in sorted(counts.items()) if c >= 3}

    rp_total = rules.root_profile_client(total)
    result: dict = {
        "input": number,
        "number": digits,
        "formatted": " ".join([digits[i : i + 5] for i in range(0, len(digits), 5)]) or digits,
        "name": name,
        "valid": len(digits) >= 6,
        "compound": compound,
        "total": total,
        "chain": reduction_chain(compound),
        "compound_meaning": {
            "title": f"Total {total}",
            "rating": {"benefic": "good", "neutral": "average", "malefic": "bad"}[total_class],
            "short": rules.mobile_total_meaning(total)[:90],
            "description": rules.mobile_total_meaning(total),
        },
        "total_class": total_class,
        "total_profile": {
            "number": total,
            "planet": rp_total.get("planet"),
            "element": rp_total.get("element"),
            "title": {"benefic": "Benefic Total", "neutral": "Neutral Total", "malefic": "Malefic Total"}[total_class],
            "description": rules.mobile_total_meaning(total),
            "colors": rp_total.get("colors", []),
        },
        "grid": grid,
        "grid_summary": {
            "good": sum(1 for g in grid if g["rating"] == "benefic"),
            "average": sum(1 for g in grid if g["rating"] == "neutral"),
            "bad": sum(1 for g in grid if g["rating"] == "malefic"),
            "total_pairs": len(grid),
        },
        "score": score,
        "verdict": _verdict(score),
        "checklist": checklist,
        "points_to_remember": rules.mobile_points(),
        "multiples": [
            {
                "digit": int(d),
                "count": c,
                "planet": rules.mobile_multiples(int(d)).get("planet", ""),
                "traits": rules.mobile_multiples(int(d)).get("traits", []),
            }
            for d, c in sorted(counts.items())
            if c > 1 and rules.mobile_multiples(int(d))
        ],
        "missing_digits": missing,
        "repeated_digits": repeated,
        "digit_counts": dict(sorted(counts.items())),
    }

    # The client's Good Compounds list, for the benefic roots they name
    gc = good_compounds_for(total)
    if gc:
        result["good_compounds"] = {
            "root": gc.get("root"),
            "compounds": gc.get("compounds", []),
            "helps_with": gc.get("helps_with", []),
            "is_listed": compound in gc.get("compounds", []),
        }

    if dob:
        result["numeroscope"] = build_numeroscope(dob)
        radical = radical_number(dob.day)
        destiny = destiny_number(dob.day, dob.month, dob.year)
        rp_rad = rules.root_profile_client(radical)
        # the client's Compatibility of Numbers table decides this
        compat = rules.number_compatibility(radical)
        friendly = compat.get("lucky", [])
        enemy = compat.get("enemy", [])
        level = "friendly" if total in friendly else ("enemy" if total in enemy else "neutral")
        result["owner"] = {
            "dob": dob.isoformat(),
            "radical": radical,
            "destiny": destiny,
            "radical_planet": rp_rad.get("planet"),
            "friendly_numbers": friendly,
            "enemy_numbers": enemy,
            "match": {
                "level": level,
                "label": {"friendly": "Suits You", "neutral": "Neutral", "enemy": "Does Not Suit You"}[level],
                "color": {"friendly": "#1E9E6A", "neutral": "#E0A32E", "enemy": "#D24B4B"}[level],
                "note": (
                    f"The number totals to {total} while your radical number is {radical}. "
                    + {
                        "friendly": "These planets are friends, so the number actively supports your natural energy.",
                        "neutral": "These planets are neutral, so the number neither helps nor blocks you.",
                        "enemy": "These planets oppose each other, which is why this number can feel like it works against you.",
                    }[level]
                ),
            },
        }
        # blend personal fit into the headline score
        # The client's finalising Step 2: "Ensure that the chosen mobile total is
        # compatible with your Mulank and Bhagyank." That is a rule, not a bonus,
        # so it joins the checklist and the score stays "points passed".
        checklist.append({
            "point": "The mobile total should be compatible with your Mulank and Bhagyank.",
            "passed": level == "friendly",
            "detail": (
                f"Total {total} is "
                + {"friendly": "among your lucky numbers",
                   "neutral": "neutral for you",
                   "enemy": "on your unlucky list"}[level]
                + f" (Mulank {radical})."
            ),
        })
        result["checklist"] = checklist
        result["score"] = round(sum(1 for c in checklist if c["passed"]) * 100 / len(checklist))
        result["recommendations"] = _recommendations(result)
        result["verdict"] = _verdict(result["score"])

    result["recommendations"] = _recommendations(result)
    return result


def _recommendations(r: dict) -> list[str]:
    """Built only from the client's own points and multiple-number effects."""
    out: list[str] = []
    for c in r.get("checklist", []):
        if not c["passed"]:
            out.append(f"{c['point']} — {c['detail']}")
    for m in r.get("multiples", []):
        if m["traits"]:
            out.append(
                f"Digit {m['digit']} appears {m['count']} times ({m['planet']}): "
                + ", ".join(m["traits"][:4])
                + "."
            )
    if not out:
        out.append("This number passes every point on the client's checklist.")
    return out




def compare_numbers(current: dict, candidate: dict) -> dict:
    diff = candidate["score"] - current["score"]
    if diff > 8:
        verdict = "The new number is clearly better. Switching is recommended."
    elif diff > 0:
        verdict = "The new number is slightly better — a marginal improvement."
    elif diff == 0:
        verdict = "Both numbers carry the same strength. There is no gain in switching."
    else:
        verdict = "Your current number is stronger. Do not switch to this one."
    return {
        "current_score": current["score"],
        "candidate_score": candidate["score"],
        "difference": diff,
        "better": "candidate" if diff > 0 else ("same" if diff == 0 else "current"),
        "verdict": verdict,
    }
