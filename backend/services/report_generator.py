from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
)

SEVERITY_COLORS = {
    "critical": colors.HexColor("#FF4444"),
    "high": colors.HexColor("#FF8800"),
    "medium": colors.HexColor("#FFCC00"),
    "low": colors.HexColor("#44BB44"),
    "unknown": colors.HexColor("#AAAAAA"),
}

SEVERITY_TEXT_COLORS = {
    "critical": colors.white,
    "high": colors.white,
    "medium": colors.black,
    "low": colors.white,
    "unknown": colors.black,
}


def build_pdf(path: str, filename: str, executive_summary: str, clauses: list[dict]) -> None:
    doc = SimpleDocTemplate(
        path,
        pagesize=A4,
        rightMargin=2 * cm,
        leftMargin=2 * cm,
        topMargin=2 * cm,
        bottomMargin=2 * cm,
    )
    styles = getSampleStyleSheet()
    elements = []

    # Title
    title_style = ParagraphStyle(
        "Title", parent=styles["Title"],
        fontSize=20, spaceAfter=6, textColor=colors.HexColor("#1A1A2E")
    )
    elements.append(Paragraph("Legal Contract Risk Analysis Report", title_style))
    elements.append(Paragraph(f"<b>Contract:</b> {filename}", styles["Normal"]))
    elements.append(Spacer(1, 0.4 * cm))
    elements.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#1A1A2E")))
    elements.append(Spacer(1, 0.4 * cm))

    # Risk summary counts
    severity_counts = {}
    for c in clauses:
        sev = c.get("risk_severity", "unknown")
        severity_counts[sev] = severity_counts.get(sev, 0) + 1

    summary_rows = [["Severity", "Count"]]
    for sev in ["critical", "high", "medium", "low"]:
        summary_rows.append([sev.upper(), str(severity_counts.get(sev, 0))])

    summary_table = Table(summary_rows, colWidths=[6 * cm, 3 * cm])
    summary_style = TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1A1A2E")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("ALIGN", (1, 0), (1, -1), "CENTER"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.whitesmoke, colors.white]),
    ])
    for i, row in enumerate(summary_rows[1:], start=1):
        sev_key = row[0].lower()
        bg = SEVERITY_COLORS.get(sev_key, colors.white)
        tc = SEVERITY_TEXT_COLORS.get(sev_key, colors.black)
        summary_style.add("BACKGROUND", (0, i), (0, i), bg)
        summary_style.add("TEXTCOLOR", (0, i), (0, i), tc)
    summary_table.setStyle(summary_style)

    elements.append(Paragraph("Risk Summary", styles["Heading2"]))
    elements.append(summary_table)
    elements.append(Spacer(1, 0.6 * cm))

    # Executive summary
    elements.append(Paragraph("Executive Summary", styles["Heading2"]))
    for para in executive_summary.split("\n\n"):
        if para.strip():
            elements.append(Paragraph(para.strip(), styles["BodyText"]))
            elements.append(Spacer(1, 0.3 * cm))
    elements.append(Spacer(1, 0.4 * cm))

    # Clause table
    elements.append(Paragraph("Clause-by-Clause Analysis", styles["Heading2"]))
    elements.append(Spacer(1, 0.2 * cm))

    table_data = [["#", "Type", "Severity", "Score", "Rationale", "Deviation"]]
    for c in sorted(clauses, key=lambda x: x.get("risk_score", 0), reverse=True):
        table_data.append([
            str(c.get("clause_number", "")),
            (c.get("clause_type") or "other").capitalize(),
            (c.get("risk_severity") or "unknown").upper(),
            f"{c.get('risk_score', 0):.2f}",
            Paragraph(c.get("risk_rationale", "")[:200], styles["BodyText"]),
            Paragraph(c.get("deviation_notes", "") or "—", styles["BodyText"]),
        ])

    col_widths = [1 * cm, 2.5 * cm, 2 * cm, 1.5 * cm, 5 * cm, 5 * cm]
    clause_table = Table(table_data, colWidths=col_widths, repeatRows=1)

    clause_style = TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1A1A2E")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("GRID", (0, 0), (-1, -1), 0.3, colors.grey),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.whitesmoke, colors.white]),
    ])
    for i, row in enumerate(table_data[1:], start=1):
        sev_key = (row[2] if isinstance(row[2], str) else "unknown").lower()
        bg = SEVERITY_COLORS.get(sev_key, colors.white)
        tc = SEVERITY_TEXT_COLORS.get(sev_key, colors.black)
        clause_style.add("BACKGROUND", (2, i), (2, i), bg)
        clause_style.add("TEXTCOLOR", (2, i), (2, i), tc)
    clause_table.setStyle(clause_style)

    elements.append(clause_table)

    doc.build(elements)
