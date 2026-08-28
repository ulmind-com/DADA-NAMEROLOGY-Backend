# How the engine works

Everything is **Chaldean**, matching the values on `DADAS NAMEROLOGY.xlsx`. This page
explains the maths and, at the end, exactly how to hand over your own rules.

## Letter values

| Value | Letters |
| --- | --- |
| 1 | A · I · J · Q · Y |
| 2 | B · K · R |
| 3 | C · G · L · S |
| 4 | D · M · T |
| 5 | E · H · N · X |
| 6 | U · V · W |
| 7 | O · Z |
| 8 | F · P |

Chaldean assigns no letter to 9 — it is treated as sacred. Names are uppercased,
accents and punctuation stripped, and spaces used to split words.

## The two numbers on every result

**Compound number** — the raw sum, kept as-is. This is where the real meaning sits,
which is why 28 and 37 say very different things even though both reduce to 1.

**Total (root)** — the compound reduced to a single digit by adding its digits
repeatedly. This is the ruling planet.

Worked from the client's sheet:

```
P A N K A J    8+1+5+2+1+1 = 18
K A B I R A J  2+1+2+1+2+1+1 = 10
                             ----
              compound        28  →  2+8 = 10 → 1+0 = 1   Total = 1
```

28 is *"The Trusting Lamb"* — promise, but loss through trusting others and having to
begin again. So the free result tells the user their name is not perfectly aligned and
offers corrections.

## Birth numbers

| Name | How it is found | Example: 15 Aug 1995 |
| --- | --- | --- |
| **Radical** (Mulank) | Day of the month, reduced | 15 → **6** (Venus) |
| **Destiny** (Bhagyank) | Whole date, reduced | 1+5+0+8+1+9+9+5 = 38 → 11 → **2** (Moon) |
| Soul urge | Vowels of the name, reduced | inner desire |
| Personality | Consonants of the name, reduced | outer impression |

## Friendly and enemy numbers

Each number is a planet, and planets have relationships. Number 1 (Sun) is friendly with
1, 2, 3, 5, 9; neutral to 4 and 7; and opposed by 6 and 8. The full table lives in
`root_profiles.json` and drives the alignment score, the pair grid and every
compatibility verdict.

A name is **aligned** when its total befriends the radical and destiny numbers. When it
does not, effort keeps resetting instead of compounding — which is what the correction
feature fixes.

## Name correction

The engine generates spelling variants that keep the name recognisable — doubling a
consonant, `i`/`ee`, `k`/`ck`, `f`/`ph`, a trailing `a`/`h`/`e` — then keeps only the
ones whose compound number carries a favourable rating, and ranks them by:

1. how good the new compound is,
2. whether the new total befriends the radical and destiny numbers,
3. how few letters changed.

`Pankaj Kabiraj` (28, caution) → **`Pankaj Kabirajh`** (33 — *Gain Through Love*).

## Mobile numbers — the TOTAL GRID

Two things are measured.

**The whole number**: every digit summed for the compounding, reduced for the total.

```
9 5 3 1 1 9 9 3 5 5  →  compounding 50  →  5+0 = 5   (Mercury)
```

**Consecutive pairs**, which is what the grid on the client's sheet shows:

```
9:5  5:3  3:1  1:1  1:9  9:9  9:3  3:5  5:5
```

A ten-digit number gives nine pairs. Each pair is two planets meeting, rated **Good**,
**Average** or **Bad**, with a colour and a written impact. The score is the share of
pairs that are good, adjusted for how well the total suits the owner's radical number.

A `0` has no planet. It is reported as an amplifier of the digit beside it.

The same pair logic runs on the running number of a vehicle plate.

## Vehicle numbers

`WB 06 AB 1234` is split into state · RTO · series · running number. The **running
number** (`1234`) carries the most weight — its compound, total, and digit-pair grid —
with the whole plate (letters converted through the same Chaldean table) reported
alongside. Owner compatibility, favourable colours and a road-safety note come from the
running number's planet.

> The client's final vehicle rules are still pending. Until they arrive this module runs
> on the same verified base as Name and Mobile, and every sentence it prints comes from
> the editable rule store — so switching to the final rules is a data change, not a code
> change.

## Handing over your own rules

Three files under `backend/app/numerology/data/`. Edit them in the admin panel
(**Numerology Rules**) for instant effect, or replace the files and restart.

### `compound_meanings.json` — numbers 1 to 52

```jsonc
"28": {
  "title": "The Trusting Lamb",
  "rating": "caution",           // excellent | good | average | caution | bad
  "short": "You have to start your projects again and again to get success.",
  "description": "A number full of contradictions…"
}
```

`rating` is what decides whether a name is flagged for correction: **excellent** and
**good** pass, everything else prompts a correction.

### `root_profiles.json` — numbers 1 to 9

```jsonc
"5": {
  "number": 5, "planet": "Mercury", "title": "The Communicator",
  "colors": ["Green", "Turquoise"], "avoid_colors": ["Red"],
  "lucky_days": ["Wednesday", "Friday"], "lucky_dates": [5, 14, 23],
  "gem": "Emerald", "direction": "North",
  "friendly": [1,3,4,5,6,7,8,9], "neutral": [], "enemy": [2],
  "traits": ["Quick-witted"], "shadow": ["Restlessness"],
  "career": ["Business"], "description": "…"
}
```

`friendly` / `neutral` / `enemy` are the important ones — they drive the pair ratings,
the alignment score and the correction ranking.

### `pair_meanings.json` — all 81 pairs

```jsonc
"9:5": {
  "pair": "9:5", "first": 9, "second": 5,
  "planets": "Mars + Mercury",
  "rating": "good",              // good | average | bad
  "label": "Good", "color": "#1E9E6A", "score": 2,
  "impact": "Mars with Mercury — decisive action backed by sharp negotiation…"
}
```

`score` feeds the percentage: 2 = good, 1 = average, 0 = bad.

### Sending them as a spreadsheet

A sheet with one row per rule works too — for compound numbers:
`number | title | rating | short | description`; for pairs:
`pair | rating | impact`. We convert it into these JSON files.

---

## A note on interpretation

Numerology is a tradition, not a measurement. The app presents readings as guidance and
carries a line on every PDF saying so. Nothing in it should be read as medical, legal or
financial advice.
