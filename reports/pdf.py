"""
Generate a PDF investigation dossier for a single airport.
"""

from datetime import datetime
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable,
)

from data.models import AirportStats
from analysis.seasonal import SEASON_ORDER

OUTPUT_DIR = Path("output/dossiers")

_DAMAGE_COLOR = colors.HexColor("#c0392b")
_HEADER_COLOR = colors.HexColor("#1a237e")
_ACCENT_COLOR = colors.HexColor("#e3f2fd")
_RISK_HIGH    = colors.HexColor("#c0392b")
_RISK_MED     = colors.HexColor("#e67e22")
_RISK_LOW     = colors.HexColor("#27ae60")


def generate_airport_dossier(
    airport: AirportStats,
    all_airports: list[AirportStats],
    output_path: Path | None = None,
) -> Path:
    if output_path is None:
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = OUTPUT_DIR / f"dossier_{airport.airport_id}_{ts}.pdf"

    doc = SimpleDocTemplate(
        str(output_path),
        pagesize=letter,
        rightMargin=0.75 * inch,
        leftMargin=0.75 * inch,
        topMargin=0.75 * inch,
        bottomMargin=0.75 * inch,
    )

    styles = getSampleStyleSheet()
    story = []

    # ---- Header ----
    title_style = ParagraphStyle(
        "title", parent=styles["Title"],
        fontSize=18, textColor=_HEADER_COLOR, spaceAfter=4,
    )
    subtitle_style = ParagraphStyle(
        "subtitle", parent=styles["Normal"],
        fontSize=11, textColor=colors.grey, spaceAfter=2,
    )
    story.append(Paragraph("FAA Wildlife Strike — Airport Dossier", title_style))
    story.append(Paragraph(
        f"{airport.airport_name or airport.airport_id}  ({airport.airport_id})",
        subtitle_style,
    ))
    story.append(Paragraph(
        f"State: {airport.state or '—'}  |  Flyway: {airport.flyway}  |  "
        f"Generated: {datetime.now().strftime('%B %d, %Y')}",
        subtitle_style,
    ))
    story.append(HRFlowable(width="100%", thickness=1, color=_HEADER_COLOR, spaceAfter=10))

    # ---- Summary Stats ----
    story.append(_section_heading("Strike Summary", styles))
    percentile = _percentile_rank(airport, all_airports, "total_strikes")
    peer_avg_strikes = sum(a.total_strikes for a in all_airports) / len(all_airports) if all_airports else 0
    peer_avg_damage = sum(a.damage_rate for a in all_airports) / len(all_airports) if all_airports else 0

    summary_data = [
        ["Metric", "This Airport", "Peer Average"],
        ["Total Strikes", f"{airport.total_strikes:,}", f"{peer_avg_strikes:,.0f}"],
        ["Damage Rate", f"{airport.damage_rate:.1%}", f"{peer_avg_damage:.1%}"],
        ["Avg Repair Cost", f"${airport.avg_cost_per_strike:,.0f}", "—"],
        ["Risk Score", f"{airport.risk_score:.0%}", "—"],
        ["Strike Volume Percentile", f"{percentile}th", "50th"],
    ]
    story.append(_styled_table(summary_data))
    story.append(Spacer(1, 10))

    # ---- Risk Score Bar ----
    story.append(_section_heading("Risk Assessment", styles))
    risk_color = _RISK_HIGH if airport.risk_score >= 0.7 else (_RISK_MED if airport.risk_score >= 0.4 else _RISK_LOW)
    risk_label = "HIGH" if airport.risk_score >= 0.7 else ("MODERATE" if airport.risk_score >= 0.4 else "LOW")
    risk_style = ParagraphStyle(
        "risk", parent=styles["Normal"],
        fontSize=13, textColor=risk_color, fontName="Helvetica-Bold", spaceAfter=8,
    )
    story.append(Paragraph(f"Risk Level: {risk_label}  ({airport.risk_score:.0%})", risk_style))

    # ---- Seasonal Breakdown ----
    story.append(_section_heading("Seasonal Strike Breakdown", styles))
    season_data = [["Season", "Strikes", "% of Annual"]]
    total_annual = sum(airport.seasonal_counts.get(s, 0) for s in SEASON_ORDER) or 1
    for season in SEASON_ORDER:
        count = airport.seasonal_counts.get(season, 0)
        pct = count / total_annual
        season_data.append([season, f"{count:,}", f"{pct:.1%}"])
    story.append(_styled_table(season_data))
    story.append(Spacer(1, 10))

    # ---- Top Species ----
    if airport.top_species:
        story.append(_section_heading("Most Frequently Struck Species", styles))
        sp_data = [["Rank", "Species"]] + [
            [str(i + 1), sp] for i, sp in enumerate(airport.top_species[:10])
        ]
        story.append(_styled_table(sp_data))
        story.append(Spacer(1, 10))

    # ---- Peer Comparison ----
    story.append(_section_heading("Peer Comparison (Top 10 Riskiest Airports)", styles))
    top_peers = sorted(all_airports, key=lambda a: -a.risk_score)[:10]
    peer_data = [["Rank", "Airport", "State", "Strikes", "Damage Rate", "Risk Score"]]
    for rank, peer in enumerate(top_peers, 1):
        highlight = peer.airport_id == airport.airport_id
        peer_data.append([
            f"{'>> ' if highlight else ''}{rank}",
            peer.airport_id,
            peer.state or "—",
            f"{peer.total_strikes:,}",
            f"{peer.damage_rate:.1%}",
            f"{peer.risk_score:.0%}",
        ])
    story.append(_styled_table(peer_data, highlight_row=_find_highlight_row(top_peers, airport.airport_id)))
    story.append(Spacer(1, 10))

    # ---- Footer ----
    story.append(HRFlowable(width="100%", thickness=0.5, color=colors.grey, spaceAfter=6))
    footer_style = ParagraphStyle(
        "footer", parent=styles["Normal"],
        fontSize=7, textColor=colors.grey,
    )
    story.append(Paragraph(
        "Data source: FAA Wildlife Strike Database (wildlife.faa.gov). "
        "For educational and research purposes only. "
        "Generated by FAA Bird Strike Analyzer.",
        footer_style,
    ))

    doc.build(story)
    return output_path


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _section_heading(text: str, styles) -> Paragraph:
    style = ParagraphStyle(
        "section", parent=styles["Heading2"],
        fontSize=11, textColor=_HEADER_COLOR,
        spaceBefore=8, spaceAfter=4,
        borderPadding=(0, 0, 2, 0),
    )
    return Paragraph(text, style)


def _styled_table(data: list[list], highlight_row: int | None = None) -> Table:
    col_count = len(data[0]) if data else 1
    col_width = (7.0 * inch) / col_count

    table = Table(data, colWidths=[col_width] * col_count, repeatRows=1)
    style_cmds = [
        ("BACKGROUND",  (0, 0), (-1, 0),  _HEADER_COLOR),
        ("TEXTCOLOR",   (0, 0), (-1, 0),  colors.white),
        ("FONTNAME",    (0, 0), (-1, 0),  "Helvetica-Bold"),
        ("FONTSIZE",    (0, 0), (-1, 0),  9),
        ("FONTSIZE",    (0, 1), (-1, -1), 8),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, _ACCENT_COLOR]),
        ("GRID",        (0, 0), (-1, -1), 0.25, colors.HexColor("#cccccc")),
        ("TOPPADDING",  (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING",(0, 0),(-1, -1), 3),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
    ]
    if highlight_row is not None and highlight_row > 0:
        style_cmds.append(
            ("BACKGROUND", (0, highlight_row), (-1, highlight_row), colors.HexColor("#fff9c4"))
        )
    table.setStyle(TableStyle(style_cmds))
    return table


def _percentile_rank(airport: AirportStats, all_airports: list[AirportStats], field: str) -> int:
    value = getattr(airport, field, 0)
    below = sum(1 for a in all_airports if getattr(a, field, 0) < value)
    return round(below / len(all_airports) * 100) if all_airports else 0


def _find_highlight_row(peers: list[AirportStats], airport_id: str) -> int | None:
    for i, peer in enumerate(peers, 1):
        if peer.airport_id == airport_id:
            return i
    return None
