"""Mobile-number numerology: compound, total and the consecutive-pair TOTAL GRID."""

from __future__ import annotations

import re
from collections import Counter
from datetime import date

from . import rules
from .chaldean import destiny_number, radical_number, reduce_to_root, reduction_chain

_DIGITS = re.compile(r"\D+")


def clean_number(raw: str) -> str:
    digits = _DIGITS.sub("", raw or "")
    # drop common country prefixes so 10-digit Indian numbers analyse consistently
    if len(digits) == 12 and digits.startswith("91"):
        digits = digits[2:]
    elif len(digits) == 11 and digits.startswith("0"):
        digits = digits[1:]
    return digits


def pair_grid(digits: str) -> list[dict]:
    """Consecutive digit pairs, exactly like the client's TOTAL GRID (9:5, 5:3, 3:1 ...)."""
    grid = []
    for i in range(len(digits) - 1):
        a, b = int(digits[i]), int(digits[i + 1])
        if a == 0 or b == 0:
            # zero has no planet; it amplifies the digit beside it
            other = b if a == 0 else a
            grid.append({
                "pair": f"{a}:{b}",
                "index": i,
                "first": a, "second": b,
                "planets": "Zero (amplifier)",
                "rating": "average",
                "label": "Average",
                "color": "#E0A32E",
                "score": 1,
                "impact": (
                    f"Zero has no planet of its own — it magnifies {other}. "
                    "It makes the neighbouring energy stronger, for better or worse."
                ),
            })
            continue
        m = rules.pair_meaning(a, b)
        grid.append({**m, "index": i})
    return grid


def _grid_score(grid: list[dict]) -> int:
    if not grid:
        return 0
    return round(sum(g["score"] for g in grid) * 100 / (2 * len(grid)))


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
    score = _grid_score(grid)

    counts = Counter(digits)
    missing = [n for n in "123456789" if n not in counts]
    repeated = {d: c for d, c in sorted(counts.items()) if c >= 3}

    rp_total = rules.root_profile(total)
    result: dict = {
        "input": number,
        "number": digits,
        "formatted": " ".join([digits[i : i + 5] for i in range(0, len(digits), 5)]) or digits,
        "name": name,
        "valid": len(digits) >= 6,
        "compound": compound,
        "total": total,
        "chain": reduction_chain(compound),
        "compound_meaning": rules.compound_meaning(compound),
        "total_profile": {
            "number": total,
            "planet": rp_total.get("planet"),
            "title": rp_total.get("title"),
            "description": rp_total.get("description"),
            "colors": rp_total.get("colors", []),
        },
        "grid": grid,
        "grid_summary": {
            "good": sum(1 for g in grid if g["rating"] == "good"),
            "average": sum(1 for g in grid if g["rating"] == "average"),
            "bad": sum(1 for g in grid if g["rating"] == "bad"),
            "total_pairs": len(grid),
        },
        "score": score,
        "verdict": _verdict(score),
        "missing_digits": missing,
        "repeated_digits": repeated,
        "digit_counts": dict(sorted(counts.items())),
    }

    if dob:
        radical = radical_number(dob.day)
        destiny = destiny_number(dob.day, dob.month, dob.year)
        rp_rad = rules.root_profile(radical)
        friendly = rp_rad.get("friendly", [])
        enemy = rp_rad.get("enemy", [])
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
        result["score"] = max(0, min(100, score + {"friendly": 10, "neutral": 0, "enemy": -15}[level]))
        result["verdict"] = _verdict(result["score"])

    result["recommendations"] = _recommendations(result)
    return result


def _recommendations(r: dict) -> list[str]:
    out: list[str] = []
    bad = [g for g in r["grid"] if g["rating"] == "bad"]
    if bad:
        out.append(
            f"{len(bad)} weak pair(s) found: "
            + ", ".join(g["pair"] for g in bad[:6])
            + ". These are the points where the number leaks energy."
        )
    else:
        out.append("No conflicting pairs found — the digit flow of this number is clean.")
    if r["missing_digits"]:
        out.append(
            "Missing digits: " + ", ".join(r["missing_digits"])
            + ". Those energies are absent, so support them through colours, dates and daily habits."
        )
    for d, c in r["repeated_digits"].items():
        planet = rules.root_profile(int(d)).get("planet", "")
        out.append(f"Digit {d} ({planet}) repeats {c} times — that planet's traits are amplified in your daily life.")
    if r["verdict"]["level"] in ("weak", "bad"):
        out.append("Use the 'Check New Number' tool before buying a new SIM and compare the scores side by side.")
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
