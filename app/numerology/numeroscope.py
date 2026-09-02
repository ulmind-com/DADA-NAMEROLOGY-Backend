"""Numeroscope, missing / lucky / unlucky numbers.

Every rule here is taken from the client's Mobile Numerology notes, sections 3-5.
The client's own worked examples are reproduced by the tests.
"""

from __future__ import annotations

from collections import Counter
from datetime import date

from . import rules
from .chaldean import destiny_number, radical_number

# The client's rule: when the day of birth is one of these, the Mulank is already
# present in the date digits, so it is not placed a second time.
_SINGLE_PLACEMENT_DAYS = {1, 2, 3, 4, 5, 6, 7, 8, 9, 20, 30}


def build(dob: date) -> dict:
    """Create the numeroscope for a date of birth."""
    mulank = radical_number(dob.day)
    bhagyank = destiny_number(dob.day, dob.month, dob.year)

    # 1. every digit of the date of birth
    digits = [int(c) for c in f"{dob.day:02d}{dob.month:02d}{dob.year:04d}" if c != "0"]

    # 2. the Bhagyank always goes in; the Mulank only when the day is not one of
    #    the client's single-placement days
    digits.append(bhagyank)
    if dob.day not in _SINGLE_PLACEMENT_DAYS:
        digits.append(mulank)

    counts = Counter(digits)
    ideal = rules.ideal_grid()

    grid = [
        [
            {
                "number": n,
                "count": counts.get(n, 0),
                "display": str(n) * counts.get(n, 0) if counts.get(n, 0) else "",
                "present": counts.get(n, 0) > 0,
            }
            for n in row
        ]
        for row in ideal
    ]

    missing = [n for n in range(1, 10) if counts.get(n, 0) == 0]

    cm = rules.number_compatibility(mulank)
    cb = rules.number_compatibility(bhagyank)

    # The client's method, verified against their worked example (18/6/1985):
    #   lucky   = numbers lucky for BOTH Mulank and Bhagyank
    #   unlucky = numbers that are an enemy of EITHER
    #   neutral = numbers neutral to BOTH
    lucky = sorted(set(cm.get("lucky", [])) & set(cb.get("lucky", [])))
    unlucky = sorted(set(cm.get("enemy", [])) | set(cb.get("enemy", [])))
    neutral = sorted(set(cm.get("neutral", [])) & set(cb.get("neutral", [])))

    conditional = sorted(
        set(cm.get("lucky_conditional", []))
        | set(cb.get("lucky_conditional", []))
        | set(cm.get("enemy_conditional", []))
        | set(cb.get("enemy_conditional", []))
    )

    return {
        "dob": dob.isoformat(),
        "mulank": mulank,
        "bhagyank": bhagyank,
        "mulank_planet": cm.get("planet", ""),
        "mulank_role": cm.get("role", ""),
        "bhagyank_planet": cb.get("planet", ""),
        "bhagyank_role": cb.get("role", ""),
        "ideal_grid": ideal,
        "grid": grid,
        "counts": {str(n): counts.get(n, 0) for n in range(1, 10)},
        "missing_numbers": missing,
        "lucky_numbers": lucky,
        "unlucky_numbers": unlucky,
        "neutral_numbers": neutral,
        "conditional_numbers": conditional,
        "conditional_note": rules.compatibility_note() if conditional else "",
    }


def good_compounds_for(total: int) -> dict:
    """The client lists good compounds only for the benefic roots 1, 3, 5 and 6."""
    return rules.good_compounds(total)
