"""Branded PDF report generation (reportlab)."""

from __future__ import annotations

import io
from datetime import datetime
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    HRFlowable,
    Image,
    KeepTogether,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

CREAM = colors.HexColor("#FBF3E7")
BRAND = colors.HexColor("#B3441E")
INK = colors.HexColor("#3A2A1E")
MUTED = colors.HexColor("#8A7565")
LINE = colors.HexColor("#EBD9C0")

_ss = getSampleStyleSheet()
H1 = ParagraphStyle("h1", parent=_ss["Title"], fontName="Times-Bold", fontSize=22, textColor=INK, spaceAfter=2)
GANESHA = Path(__file__).parent / "ganesha.png"
BRAND_BIG = ParagraphStyle("brandBig", parent=_ss["Title"], fontName="Times-Bold",
                           fontSize=40, leading=42, textColor=BRAND, alignment=TA_CENTER, spaceAfter=0)
BRAND_SUB = ParagraphStyle("brandSub", parent=_ss["Normal"], fontName="Helvetica-Bold",
                           fontSize=15, textColor=INK, alignment=TA_CENTER, spaceBefore=2)
KICKER = ParagraphStyle("kick", parent=_ss["Normal"], fontName="Helvetica-Bold", fontSize=9,
                        textColor=BRAND, alignment=TA_CENTER, spaceAfter=4)
H2 = ParagraphStyle("h2", parent=_ss["Heading2"], fontName="Helvetica-Bold", fontSize=12.5,
                    textColor=BRAND, spaceBefore=14, spaceAfter=6)
BODY = ParagraphStyle("body", parent=_ss["Normal"], fontName="Helvetica", fontSize=10,
                      leading=15.5, textColor=INK)
SMALL = ParagraphStyle("small", parent=BODY, fontSize=8.5, textColor=MUTED)
CENTER = ParagraphStyle("center", parent=BODY, alignment=TA_CENTER)


def _decor(canvas, doc):
    canvas.saveState()
    canvas.setFillColor(CREAM)
    canvas.rect(0, 0, A4[0], A4[1], stroke=0, fill=1)
    # sun rays motif, top-right corner
    canvas.setStrokeColor(colors.HexColor("#E8D3B6"))
    canvas.setLineWidth(0.6)
    cx, cy, r = A4[0] - 22 * mm, A4[1] - 20 * mm, 15 * mm
    canvas.circle(cx, cy, r * 0.42, stroke=1, fill=0)
    import math
    for i in range(24):
        a = i * math.pi / 12
        canvas.line(cx + math.cos(a) * r * 0.55, cy + math.sin(a) * r * 0.55,
                    cx + math.cos(a) * r, cy + math.sin(a) * r)
    canvas.setFillColor(MUTED)
    canvas.setFont("Helvetica", 7.5)
    canvas.drawString(20 * mm, 12 * mm, "DADA'S NUMEROLOGY")
    canvas.drawRightString(A4[0] - 20 * mm, 12 * mm, f"Page {doc.page}")
    canvas.restoreState()


def _kv_table(rows: list[tuple[str, str]], widths=(48 * mm, 112 * mm)) -> Table:
    data = [[Paragraph(f"<b>{k}</b>", BODY), Paragraph(str(v), BODY)] for k, v in rows]
    t = Table(data, colWidths=list(widths))
    t.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("LINEBELOW", (0, 0), (-1, -2), 0.4, LINE),
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#FFFDF8")),
        ("LEFTPADDING", (0, 0), (-1, -1), 10),
        ("RIGHTPADDING", (0, 0), (-1, -1), 10),
    ]))
    return t


def _grid_table(grid: list[dict]) -> Table:
    data = [[Paragraph("<b>Pair</b>", SMALL), Paragraph("<b>Planets</b>", SMALL),
             Paragraph("<b>Rating</b>", SMALL), Paragraph("<b>Impact</b>", SMALL)]]
    for g in grid:
        data.append([
            Paragraph(f"<b>{g['pair']}</b>", BODY),
            Paragraph(g.get("planets", ""), SMALL),
            Paragraph(f"<font color='{g.get('color', '#000')}'><b>{g.get('label', '')}</b></font>", SMALL),
            Paragraph(g.get("impact", ""), SMALL),
        ])
    t = Table(data, colWidths=[16 * mm, 34 * mm, 20 * mm, 90 * mm], repeatRows=1)
    t.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#F5E7D2")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.HexColor("#FFFDF8"), colors.HexColor("#FDF7EC")]),
        ("GRID", (0, 0), (-1, -1), 0.35, LINE),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    return t


def _bullets(items: list[str]) -> list:
    return [Paragraph(f"• {i}", BODY) for i in items]


def build_report_pdf(report_type: str, title: str, result: dict, user_name: str = "") -> bytes:
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        leftMargin=20 * mm, rightMargin=20 * mm, topMargin=22 * mm, bottomMargin=20 * mm,
        title=f"{title} — DADA'S NUMEROLOGY", author="DADA'S NUMEROLOGY",
    )
    S: list = []
    if GANESHA.exists():
        img = Image(str(GANESHA), width=34 * mm, height=34 * mm)
        img.hAlign = "CENTER"
        S += [img, Spacer(1, 4)]
    S += [
        Paragraph("DADA'S", BRAND_BIG),
        Paragraph("NUMEROLOGY", BRAND_SUB),
        Spacer(1, 6),
        Paragraph(
            f"{report_type.upper()} REPORT &nbsp;·&nbsp; {datetime.now().strftime('%d %B %Y')}",
            ParagraphStyle("sub", parent=SMALL, alignment=TA_CENTER),
        ),
        Spacer(1, 8),
        HRFlowable(width="100%", thickness=0.8, color=LINE),
        Spacer(1, 12),
        Paragraph(title, ParagraphStyle("t", parent=H1, fontSize=17, alignment=TA_CENTER)),
    ]
    if user_name:
        S.append(Paragraph(f"Prepared for {user_name}", ParagraphStyle("pf", parent=SMALL, alignment=TA_CENTER)))
    S.append(Spacer(1, 14))

    if report_type in ("name", "business"):
        S += _name_sections(result)
    elif report_type == "mobile":
        S += _mobile_sections(result)
    elif report_type == "vehicle":
        S += _vehicle_sections(result)
    elif report_type == "newborn":
        S += _newborn_sections(result)

    S += [
        Spacer(1, 18),
        HRFlowable(width="100%", thickness=0.6, color=LINE),
        Spacer(1, 6),
        Paragraph(
            "This report is generated from the classical Chaldean numerology system for guidance "
            "and self-reflection. It is not a substitute for professional medical, legal or "
            "financial advice.", SMALL,
        ),
    ]
    doc.build(S, onFirstPage=_decor, onLaterPages=_decor)
    return buf.getvalue()


def _name_sections(r: dict) -> list:
    S = [Paragraph("Core Numbers", H2)]
    rows = [
        ("Name", r.get("normalized", "")),
        ("Compound Number", str(r.get("compound", ""))),
        ("Total (Root)", str(r.get("total", ""))),
        ("Vibration", f"{r.get('title', '')} — {str(r.get('rating', '')).title()}"),
    ]
    if r.get("radical"):
        rows += [
            ("Radical (Mulank)", f"{r['radical']['number']} — {r['radical'].get('planet', '')}"),
            ("Destiny (Bhagyank)", f"{r['destiny']['number']} — {r['destiny'].get('planet', '')}"),
            ("Friendly Numbers", ", ".join(map(str, r.get("friendly_numbers", [])))),
            ("Enemy Numbers", ", ".join(map(str, r.get("enemy_numbers", [])))),
            ("Alignment Score", f"{r.get('alignment_score', 0)}%"),
        ]
    S += [_kv_table(rows), Paragraph("Description", H2), Paragraph(r.get("description", ""), BODY)]

    if r.get("word_details"):
        S.append(Paragraph("Name Words Details", H2))
        data = [[Paragraph("<b>Word</b>", SMALL), Paragraph("<b>Compound</b>", SMALL),
                 Paragraph("<b>Total</b>", SMALL), Paragraph("<b>Meaning</b>", SMALL)]]
        for w in r["word_details"]:
            data.append([Paragraph(w["word"], BODY), Paragraph(str(w["compound"]), BODY),
                         Paragraph(str(w["root"]), BODY), Paragraph(w.get("meaning", ""), SMALL)])
        t = Table(data, colWidths=[38 * mm, 24 * mm, 20 * mm, 78 * mm], repeatRows=1)
        t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#F5E7D2")),
            ("GRID", (0, 0), (-1, -1), 0.35, LINE),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ]))
        S.append(t)

    if r.get("similar_names"):
        S.append(Paragraph("Suggested Name Corrections", H2))
        data = [[Paragraph("<b>Name</b>", SMALL), Paragraph("<b>Compound</b>", SMALL),
                 Paragraph("<b>Total</b>", SMALL), Paragraph("<b>Vibration</b>", SMALL)]]
        for s in r["similar_names"][:8]:
            data.append([Paragraph(s["name"], BODY), Paragraph(str(s["compound"]), BODY),
                         Paragraph(str(s["total"]), BODY), Paragraph(s.get("title", ""), SMALL)])
        t = Table(data, colWidths=[52 * mm, 24 * mm, 20 * mm, 64 * mm], repeatRows=1)
        t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#F5E7D2")),
            ("GRID", (0, 0), (-1, -1), 0.35, LINE),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ]))
        S.append(t)

    if r.get("case_study"):
        S += [Paragraph("Case Study", H2), Paragraph(r["case_study"]["summary"], BODY)]
    if r.get("remedies"):
        S.append(Paragraph("Remedies & Recommendations", H2))
        S += _bullets(r["remedies"])
    if r.get("suggest"):
        S += [Spacer(1, 8), Paragraph(f"<b>Suggestion:</b> {r['suggest']}", BODY)]
    return S


def _mobile_sections(r: dict) -> list:
    rows = [
        ("Mobile Number", r.get("formatted", "")),
        ("Compounding", str(r.get("compound", ""))),
        ("Total", str(r.get("total", ""))),
        ("Ruling Planet", r.get("total_profile", {}).get("planet", "")),
        ("Score", f"{r.get('score', 0)}%  ({r.get('verdict', {}).get('label', '')})"),
    ]
    if r.get("owner"):
        rows += [
            ("Radical Number", str(r["owner"]["radical"])),
            ("Destiny Number", str(r["owner"]["destiny"])),
            ("Personal Match", r["owner"]["match"]["label"]),
        ]
    S = [Paragraph("Result", H2), _kv_table(rows)]
    if r.get("owner"):
        S += [Spacer(1, 6), Paragraph(r["owner"]["match"]["note"], BODY)]
    S += [Paragraph("Total Grid — Impact, Colour & Rating", H2), _grid_table(r.get("grid", []))]
    if r.get("recommendations"):
        S.append(Paragraph("Recommendations", H2))
        S += _bullets(r["recommendations"])
    return S


def _vehicle_sections(r: dict) -> list:
    rows = [
        ("Registration", r.get("formatted", "")),
        ("Vehicle Type", str(r.get("vehicle_type", "")).title()),
        ("Running Number", r.get("running_number", "")),
        ("Compounding", str(r.get("compound", ""))),
        ("Total", str(r.get("total", ""))),
        ("Full Plate Total", str(r.get("full_total", ""))),
        ("Score", f"{r.get('score', 0)}%  ({r.get('verdict', {}).get('label', '')})"),
    ]
    S = [Paragraph("Result", H2), _kv_table(rows)]
    if r.get("owner"):
        S += [Spacer(1, 6), Paragraph(r["owner"]["match"]["note"], BODY)]
    if r.get("grid"):
        S += [Paragraph("Digit Pair Grid", H2), _grid_table(r["grid"])]
    if r.get("recommendations"):
        S.append(Paragraph("Recommendations", H2))
        S += _bullets(r["recommendations"])
    return S


def _newborn_sections(r: dict) -> list:
    rows = [
        ("Date of Birth", r.get("dob", "")),
        ("Time", r.get("time", "") or "—"),
        ("Place", r.get("place", "") or "—"),
        ("Radical (Mulank)", f"{r['radical']['number']} — {r['radical'].get('planet', '')}"),
        ("Destiny (Bhagyank)", f"{r['destiny']['number']} — {r['destiny'].get('planet', '')}"),
        ("Favourable Numbers", ", ".join(map(str, r.get("favourable_numbers", [])))),
        ("Numbers to Avoid", ", ".join(map(str, r.get("avoid_numbers", [])))),
        ("Best Starting Letters", ", ".join(r.get("start_letters", []))),
    ]
    S = [Paragraph("Birth Numbers", H2), _kv_table(rows),
         Paragraph("Naming Guidance", H2), Paragraph(r.get("guidance", ""), BODY)]
    if r.get("target_compounds"):
        S.append(Paragraph("Recommended Name Totals", H2))
        S += _bullets([
            f"Compound {c['compound']} — {c.get('title', '')}: {c.get('short', '')}"
            for c in r["target_compounds"][:8]
        ])
    return S


__all__ = ["build_report_pdf", "KeepTogether", "PageBreak"]
