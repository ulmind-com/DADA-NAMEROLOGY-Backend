"""Chaldean numerology core.

Verified against the client's sheet:
    "Pankaj Kabiraj" -> Pankaj(18) + Kabiraj(10) = compound 28 -> root 1
"""

from __future__ import annotations

import re
import unicodedata

# Chaldean letter -> value. Note: Chaldean has no 9 (9 is considered sacred).
CHALDEAN_MAP: dict[str, int] = {
    "A": 1, "I": 1, "J": 1, "Q": 1, "Y": 1,
    "B": 2, "K": 2, "R": 2,
    "C": 3, "G": 3, "L": 3, "S": 3,
    "D": 4, "M": 4, "T": 4,
    "E": 5, "H": 5, "N": 5, "X": 5,
    "U": 6, "V": 6, "W": 6,
    "O": 7, "Z": 7,
    "F": 8, "P": 8,
}

# Pythagorean map, kept for cross-reference in the full/paid report.
PYTHAGOREAN_MAP: dict[str, int] = {
    **{c: 1 for c in "AJS"}, **{c: 2 for c in "BKT"}, **{c: 3 for c in "CLU"},
    **{c: 4 for c in "DMV"}, **{c: 5 for c in "ENW"}, **{c: 6 for c in "FOX"},
    **{c: 7 for c in "GPY"}, **{c: 8 for c in "HQZ"}, **{c: 9 for c in "IR"},
}

VOWELS = set("AEIOU")

_NON_ALPHA = re.compile(r"[^A-Z ]+")


def normalize_name(raw: str) -> str:
    """Uppercase, strip accents/punctuation, collapse whitespace."""
    if not raw:
        return ""
    decomposed = unicodedata.normalize("NFKD", raw)
    ascii_only = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
    upper = ascii_only.upper().replace("-", " ").replace(".", " ").replace("'", "")
    cleaned = _NON_ALPHA.sub(" ", upper)
    return " ".join(cleaned.split())


def reduce_to_root(number: int) -> int:
    """Repeatedly add digits until a single digit (1-9) remains. 0 -> 0."""
    n = abs(int(number))
    while n > 9:
        n = sum(int(d) for d in str(n))
    return n


def reduction_chain(number: int) -> list[int]:
    """e.g. 28 -> [28, 10, 1]"""
    chain = [abs(int(number))]
    n = chain[0]
    while n > 9:
        n = sum(int(d) for d in str(n))
        chain.append(n)
    return chain


def letter_value(letter: str, system: str = "chaldean") -> int:
    table = CHALDEAN_MAP if system == "chaldean" else PYTHAGOREAN_MAP
    return table.get(letter.upper(), 0)


def word_breakdown(word: str, system: str = "chaldean") -> dict:
    """Per-letter values for one word plus its compound + root."""
    letters = [
        {"letter": ch, "value": letter_value(ch, system), "vowel": ch in VOWELS}
        for ch in word
        if ch.isalpha()
    ]
    compound = sum(item["value"] for item in letters)
    return {
        "word": word,
        "letters": letters,
        "compound": compound,
        "root": reduce_to_root(compound),
        "chain": reduction_chain(compound),
    }


def analyse_name(raw_name: str, system: str = "chaldean") -> dict:
    """Full letter-by-letter, word-by-word breakdown of a name."""
    name = normalize_name(raw_name)
    words = [w for w in name.split(" ") if w]
    breakdowns = [word_breakdown(w, system) for w in words]
    compound = sum(b["compound"] for b in breakdowns)

    vowel_total = sum(
        letter_value(ch, system) for ch in name if ch in VOWELS
    )
    consonant_total = sum(
        letter_value(ch, system) for ch in name if ch.isalpha() and ch not in VOWELS
    )

    return {
        "input": raw_name,
        "normalized": name,
        "system": system,
        "words": breakdowns,
        "compound": compound,
        "root": reduce_to_root(compound),
        "chain": reduction_chain(compound),
        "soul_urge": reduce_to_root(vowel_total),        # vowels  = inner desire
        "personality": reduce_to_root(consonant_total),  # consonants = outer image
        "vowel_total": vowel_total,
        "consonant_total": consonant_total,
        "letter_count": len([c for c in name if c.isalpha()]),
    }


# ---------------------------------------------------------------- date maths
def radical_number(day: int) -> int:
    """Mulank / Radical / Birth number = reduced day of month."""
    return reduce_to_root(day)


def destiny_number(day: int, month: int, year: int) -> int:
    """Bhagyank / Destiny / Life-path = reduced sum of the full date."""
    total = sum(int(d) for d in f"{day:02d}{month:02d}{year:04d}")
    return reduce_to_root(total)


def kua_number(year: int, gender: str) -> int:
    """Kua number (used for direction / vastu tips in the full report)."""
    y = reduce_to_root(sum(int(d) for d in str(year)))
    if gender.lower().startswith("f"):
        k = y + 5
    else:
        k = 11 - y
    k = reduce_to_root(k)
    return 5 if k == 0 else k
