"""Name / business-name numerology: free result, paid full report, corrections."""

from __future__ import annotations

from datetime import date

from . import rules
from .chaldean import (
    CHALDEAN_MAP,
    analyse_name,
    destiny_number,
    normalize_name,
    radical_number,
    reduce_to_root,
    reduction_chain,
)

# ------------------------------------------------------------------ helpers


def _compat(a: int, b: int) -> dict:
    """How two root numbers sit with each other."""
    pa = rules.root_profile(a)
    if not pa:
        return {"level": "neutral", "label": "Neutral", "color": "#E0A32E", "note": ""}
    if b in pa.get("friendly", []):
        return {
            "level": "friendly", "label": "Friendly", "color": "#1E9E6A",
            "note": f"{pa.get('planet')} supports {rules.root_profile(b).get('planet')} — this combination helps you.",
        }
    if b in pa.get("enemy", []):
        return {
            "level": "enemy", "label": "Enemy", "color": "#D24B4B",
            "note": f"{pa.get('planet')} opposes {rules.root_profile(b).get('planet')} — this combination creates friction.",
        }
    return {
        "level": "neutral", "label": "Neutral", "color": "#E0A32E",
        "note": f"{pa.get('planet')} is neutral to {rules.root_profile(b).get('planet')} — no strong push either way.",
    }


def _luckiest_letters(target_roots: list[int]) -> list[str]:
    return sorted({ch for ch, v in CHALDEAN_MAP.items() if v in target_roots})


# ------------------------------------------------------- free / quick result
def quick_name(name: str, kind: str = "personal") -> dict:
    """The free tier shown on the first screen of the sheet."""
    a = analyse_name(name)
    compound = a["compound"]
    total = a["root"]
    meaning = rules.compound_meaning(compound)
    favourable = rules.is_favourable(meaning.get("rating", "average"))

    if favourable:
        suggest = (
            "Your name is well aligned with its number. No correction is required — "
            "keep the spelling exactly as it is."
        )
    else:
        suggest = (
            "Your Name is not perfectly aligned. It would be advisable to make "
            "the necessary corrections."
        )

    return {
        "kind": kind,
        "name": name,
        "normalized": a["normalized"],
        "compound": compound,
        "total": total,
        "chain": a["chain"],
        "title": meaning.get("title", ""),
        "rating": meaning.get("rating", "average"),
        "rating_color": rules.rating_color(meaning.get("rating", "average")),
        "description": meaning.get("description", ""),
        "short": meaning.get("short", ""),
        "suggest": suggest,
        "needs_correction": not favourable,
        "words": [
            {"word": w["word"], "compound": w["compound"], "root": w["root"]}
            for w in a["words"]
        ],
    }


# --------------------------------------------------------- name corrections
_VARIANT_RULES: list[tuple[str, str]] = [
    ("EE", "I"), ("I", "EE"), ("Y", "I"), ("I", "Y"), ("K", "CK"), ("C", "K"),
    ("S", "Z"), ("Z", "S"), ("OO", "U"), ("U", "OO"), ("PH", "F"), ("F", "PH"),
    ("V", "W"), ("W", "V"), ("AA", "A"), ("A", "AA"),
]
_SUFFIXES = ["A", "H", "E", "AA", "I", "Y"]
_DOUBLES = "BDGKLMNPRSTZ"


def _variants(word: str, limit: int = 400) -> set[str]:
    out: set[str] = set()
    for old, new in _VARIANT_RULES:
        if old in word:
            out.add(word.replace(old, new, 1))
    for suf in _SUFFIXES:
        out.add(word + suf)
    for i, ch in enumerate(word):
        if ch in _DOUBLES:
            out.add(word[: i + 1] + ch + word[i + 1 :])
    # combine one substitution with one suffix for a second layer of options
    layer2: set[str] = set()
    for v in list(out)[:60]:
        for suf in _SUFFIXES[:3]:
            layer2.add(v + suf)
    out |= layer2
    out.discard(word)
    return set(list(out)[:limit])


def suggest_corrections(
    name: str,
    radical: int | None = None,
    destiny: int | None = None,
    limit: int = 8,
) -> list[dict]:
    """Spelling variants of the same name that carry a favourable compound number."""
    norm = normalize_name(name)
    words = norm.split(" ")
    if not words or not norm:
        return []

    base_rest = words[:-1]
    last = words[-1]

    candidates: dict[str, dict] = {}

    def consider(full_words: list[str]) -> None:
        full = " ".join(full_words)
        if full == norm or full in candidates:
            return
        a = analyse_name(full)
        meaning = rules.compound_meaning(a["compound"])
        rating = meaning.get("rating", "average")
        if not rules.is_favourable(rating):
            return
        score = rules.RATING_ORDER.get(rating, 2) * 10
        # bonus when the corrected root befriends the birth numbers
        for birth in (radical, destiny):
            if birth:
                lvl = _compat(a["root"], birth)["level"]
                score += {"friendly": 6, "neutral": 2, "enemy": -12}[lvl]
        score -= abs(len(full) - len(norm))  # prefer minimal edits
        candidates[full] = {
            "name": " ".join(w.capitalize() for w in full_words),
            "compound": a["compound"],
            "total": a["root"],
            "title": meaning.get("title", ""),
            "rating": rating,
            "rating_color": rules.rating_color(rating),
            "short": meaning.get("short", ""),
            "score": score,
            "change": _describe_change(norm, full),
        }

    # vary the surname (most common correction), then the first name
    for v in _variants(last):
        consider(base_rest + [v])
    if len(words) > 1:
        first = words[0]
        for v in _variants(first):
            consider([v] + words[1:])

    ranked = sorted(candidates.values(), key=lambda c: (-c["score"], c["compound"]))
    for c in ranked:
        c.pop("score", None)
    return ranked[:limit]


def _describe_change(old: str, new: str) -> str:
    if len(new) > len(old):
        return f"Added {len(new) - len(old)} letter(s)"
    if len(new) < len(old):
        return f"Removed {len(old) - len(new)} letter(s)"
    return "Changed spelling"


# ------------------------------------------------------------- full report
def full_name_report(
    name: str,
    dob: date,
    gender: str = "",
    kind: str = "personal",
) -> dict:
    a = analyse_name(name)
    quick = quick_name(name, kind)

    radical = radical_number(dob.day)
    destiny = destiny_number(dob.day, dob.month, dob.year)
    rp_rad = rules.root_profile(radical)
    rp_des = rules.root_profile(destiny)
    rp_name = rules.root_profile(a["root"])

    friendly = sorted(set(rp_rad.get("friendly", [])) & set(rp_des.get("friendly", [])))
    enemy = sorted(set(rp_rad.get("enemy", [])) | set(rp_des.get("enemy", [])))
    neutral = sorted(set(range(1, 10)) - set(friendly) - set(enemy))

    name_vs_radical = _compat(a["root"], radical)
    name_vs_destiny = _compat(a["root"], destiny)

    corrections = suggest_corrections(name, radical, destiny)

    verdict_score = 0
    verdict_score += rules.RATING_ORDER.get(quick["rating"], 2) * 15
    verdict_score += {"friendly": 20, "neutral": 8, "enemy": 0}[name_vs_radical["level"]]
    verdict_score += {"friendly": 20, "neutral": 8, "enemy": 0}[name_vs_destiny["level"]]
    verdict_score = min(100, int(verdict_score * 100 / 100))

    return {
        **quick,
        "dob": dob.isoformat(),
        "gender": gender,
        "radical": {
            "number": radical, "planet": rp_rad.get("planet"),
            "title": rp_rad.get("title"), "description": rp_rad.get("description"),
            "colors": rp_rad.get("colors", []), "gem": rp_rad.get("gem"),
            "lucky_days": rp_rad.get("lucky_days", []),
            "lucky_dates": rp_rad.get("lucky_dates", []),
        },
        "destiny": {
            "number": destiny, "planet": rp_des.get("planet"),
            "title": rp_des.get("title"), "description": rp_des.get("description"),
            "career": rp_des.get("career", []),
        },
        "name_number": {
            "number": a["root"], "compound": a["compound"],
            "planet": rp_name.get("planet"), "title": rp_name.get("title"),
        },
        "soul_urge": {"number": a["soul_urge"], "planet": rules.root_profile(a["soul_urge"]).get("planet"),
                      "note": "What you truly want, drawn from the vowels of your name."},
        "personality": {"number": a["personality"], "planet": rules.root_profile(a["personality"]).get("planet"),
                        "note": "How the world reads you, drawn from the consonants of your name."},
        "friendly_numbers": friendly,
        "neutral_numbers": neutral,
        "enemy_numbers": enemy,
        "lucky_letters": _luckiest_letters(friendly),
        "avoid_letters": _luckiest_letters(enemy),
        "word_details": [
            {
                "word": w["word"].capitalize(),
                "compound": w["compound"],
                "root": w["root"],
                "chain": w["chain"],
                "letters": w["letters"],
                "meaning": rules.compound_meaning(w["compound"]).get("short", ""),
            }
            for w in a["words"]
        ],
        "compatibility": {
            "name_vs_radical": name_vs_radical,
            "name_vs_destiny": name_vs_destiny,
        },
        "alignment_score": verdict_score,
        "similar_names": corrections,
        "case_study": _case_study(a["compound"], a["root"], radical, destiny),
        "remedies": _remedies(radical, destiny, quick["rating"]),
    }


def _case_study(compound: int, name_root: int, radical: int, destiny: int) -> dict:
    meaning = rules.compound_meaning(compound)
    rp = rules.root_profile(name_root)
    lines = [
        f"Your name carries compound number {compound} ({meaning.get('title', '')}), "
        f"which reduces to {name_root} — ruled by {rp.get('planet')}.",
        f"Your radical number is {radical} and your destiny number is {destiny}.",
    ]
    c1 = _compat(name_root, radical)
    c2 = _compat(name_root, destiny)
    lines.append(c1["note"])
    lines.append(c2["note"])
    if c1["level"] == "enemy" or c2["level"] == "enemy":
        lines.append(
            "Because the name number conflicts with your birth numbers, effort does not "
            "convert into result at the expected rate. A small spelling correction usually "
            "resolves this without changing how the name sounds."
        )
    else:
        lines.append(
            "The name number cooperates with your birth numbers, so your efforts compound "
            "over time rather than resetting."
        )
    return {"summary": " ".join(lines), "points": lines}


def _remedies(radical: int, destiny: int, rating: str) -> list[str]:
    rp = rules.root_profile(radical)
    rd = rules.root_profile(destiny)
    out = [
        f"Favourable colours: {', '.join(rp.get('colors', []))}.",
        f"Keep important work on {', '.join(rp.get('lucky_days', []))}.",
        f"Preferred dates of the month: {', '.join(str(d) for d in rp.get('lucky_dates', []))}.",
        f"Supportive gemstone (consult before wearing): {rp.get('gem')}.",
        f"Career directions that suit your destiny number: {', '.join(rd.get('career', [])[:3])}.",
    ]
    if not rules.is_favourable(rating):
        out.insert(0, "Apply the suggested spelling correction and use it consistently everywhere — signature, documents and social media.")
    return out


# --------------------------------------------------------------- new born
def newborn_report(dob: date, birth_time: str = "", place: str = "", gender: str = "") -> dict:
    radical = radical_number(dob.day)
    destiny = destiny_number(dob.day, dob.month, dob.year)
    rp_rad = rules.root_profile(radical)
    rp_des = rules.root_profile(destiny)

    friendly = sorted(set(rp_rad.get("friendly", [])) & set(rp_des.get("friendly", [])))
    if not friendly:
        friendly = rp_rad.get("friendly", [])
    enemy = sorted(set(rp_rad.get("enemy", [])) | set(rp_des.get("enemy", [])))

    good_compounds = [
        {"compound": c, **rules.compound_meaning(c)}
        for c in range(10, 53)
        if rules.is_favourable(rules.compound_meaning(c).get("rating", "average"))
        and reduce_to_root(c) in friendly
    ][:10]

    return {
        "dob": dob.isoformat(),
        "time": birth_time,
        "place": place,
        "gender": gender,
        "radical": {"number": radical, "planet": rp_rad.get("planet"), "title": rp_rad.get("title"),
                    "description": rp_rad.get("description")},
        "destiny": {"number": destiny, "planet": rp_des.get("planet"), "title": rp_des.get("title"),
                    "description": rp_des.get("description")},
        "chain": reduction_chain(int(f"{dob.day:02d}{dob.month:02d}{dob.year}")),
        "favourable_numbers": friendly,
        "avoid_numbers": enemy,
        "start_letters": _luckiest_letters(friendly),
        "avoid_letters": _luckiest_letters(enemy),
        "target_compounds": good_compounds,
        "guidance": (
            f"Choose a name whose Chaldean compound reduces to one of {friendly}. "
            f"Starting the name with these letters — {', '.join(_luckiest_letters(friendly)[:12])} — "
            "gives the child a naturally supportive vibration. "
            f"Avoid names that total to {enemy}."
        ),
        "colors": rp_rad.get("colors", []),
        "lucky_days": rp_rad.get("lucky_days", []),
    }
