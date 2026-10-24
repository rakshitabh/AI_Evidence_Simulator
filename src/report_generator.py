"""
Report generation module for AI Evidence Simulator.
Generates comprehensive exportable PDF and JSON reports containing case background,
evidence register, timeline, identified conflicts, access request audit,
decision history, rubric scores, and forensic disclaimers.
Handles currency symbols and page numbers cleanly using ReportLab.
"""

import json
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List, Optional

from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    KeepTogether,
    HRFlowable
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.pdfgen import canvas

from config import (
    CASE_ID,
    CASE_TITLE,
    ORDER_VALUE_INR,
    ORDERED_QUANTITY,
    BUYER_NAME,
    SUPPLIER_NAME,
    COURIER_NAME,
    REPORTS_DIR
)
from src.database import (
    get_all_evidence,
    get_all_conflicts,
    get_all_access_requests,
    get_decision_attempts,
    get_latest_attempt
)
from src.timeline import build_timeline_events


class NumberedCanvas(canvas.Canvas):
    """Custom canvas that calculates total pages dynamically and adds headers/footers."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_header_footer(num_pages)
            canvas.Canvas.showPage(self)
        canvas.Canvas.save(self)

    def draw_header_footer(self, page_count):
        self.saveState()
        self.setFont("Helvetica", 8)
        self.setFillColor(colors.HexColor("#64748B"))

        # Header (Top)
        self.drawString(40, 760, f"Case Ref: {CASE_ID} | AI Evidence-to-Decision Simulator")
        self.drawRightString(572, 760, "CONFIDENTIAL INVESTIGATION REPORT")
        self.setStrokeColor(colors.HexColor("#CBD5E1"))
        self.setLineWidth(0.5)
        self.line(40, 755, 572, 755)

        # Footer (Bottom)
        page_str = f"Page {self._pageNumber} of {page_count}"
        self.drawString(40, 35, "[SYNTHETIC FICTIONAL CASE DATA - FOR SIMULATION PURPOSES ONLY]")
        self.drawRightString(572, 35, page_str)
        self.line(40, 45, 572, 45)

        self.restoreState()


class ReportGenerator:
    """Generates official forensic PDF and JSON case reports."""

    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path

    def generate_json_report(self, case_id: str = CASE_ID) -> Dict[str, Any]:
        """Compiles complete structured case findings into JSON format."""
        evidence_list = get_all_evidence(only_available=False, db_path=self.db_path)
        conflicts = get_all_conflicts(db_path=self.db_path)
        requests = get_all_access_requests(db_path=self.db_path)
        attempts = get_decision_attempts(case_id, db_path=self.db_path)
        timeline = build_timeline_events(only_available=False, db_path=self.db_path)

        latest_attempt = attempts[-1] if attempts else None

        report_data = {
            "report_metadata": {
                "generated_at": datetime.now().isoformat(),
                "generator": "AI Evidence-to-Decision Simulator v1.0",
                "disclaimer": "SYNTHETIC CASE DATA - ALL PARTIES, DATES, AND TRANSACTIONS ARE FICTIONAL"
            },
            "case_overview": {
                "case_id": case_id,
                "case_title": CASE_TITLE,
                "buyer": BUYER_NAME,
                "supplier": SUPPLIER_NAME,
                "courier": COURIER_NAME,
                "ordered_quantity": ORDERED_QUANTITY,
                "order_value_inr": ORDER_VALUE_INR,
                "reported_receipt_quantity": 350,
                "unaccounted_quantity": 150
            },
            "evidence_register": evidence_list,
            "chronological_timeline": timeline,
            "detected_conflicts": conflicts,
            "access_requests_audit": requests,
            "decision_history": attempts,
            "latest_evaluation": latest_attempt
        }
        return report_data

    def export_json_report(self, filepath: Optional[Path] = None) -> Path:
        """Exports JSON report to disk."""
        target_path = filepath or (REPORTS_DIR / f"Investigation_Report_{CASE_ID}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
        data = self.generate_json_report()
        with open(target_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        return target_path

    def export_pdf_report(self, filepath: Optional[Path] = None) -> Path:
        """Generates publication-quality PDF report using ReportLab."""
        target_path = filepath or (REPORTS_DIR / f"Investigation_Report_{CASE_ID}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf")

        doc = SimpleDocTemplate(
            str(target_path),
            pagesize=letter,
            rightMargin=40,
            leftMargin=40,
            topMargin=50,
            bottomMargin=50
        )

        styles = getSampleStyleSheet()

        title_style = ParagraphStyle(
            'RepTitle', parent=styles['Heading1'],
            fontName='Helvetica-Bold', fontSize=20, leading=24, textColor=colors.HexColor("#0F172A")
        )
        h2_style = ParagraphStyle(
            'RepH2', parent=styles['Heading2'],
            fontName='Helvetica-Bold', fontSize=13, leading=16, textColor=colors.HexColor("#0D9488"),
            spaceBefore=14, spaceAfter=6
        )
        body_style = ParagraphStyle(
            'RepBody', parent=styles['Normal'],
            fontName='Helvetica', fontSize=9, leading=13, textColor=colors.HexColor("#334155")
        )
        bold_body = ParagraphStyle(
            'RepBold', parent=body_style,
            fontName='Helvetica-Bold', textColor=colors.HexColor("#0F172A")
        )
        disclaimer_style = ParagraphStyle(
            'RepDisc', parent=styles['Italic'],
            fontName='Helvetica-Oblique', fontSize=8, leading=11, textColor=colors.HexColor("#DC2626")
        )

        story = []

        # Title Banner
        story.append(Paragraph("FINAL FORENSIC INVESTIGATION REPORT", title_style))
        story.append(Spacer(1, 4))
        story.append(Paragraph(f"<b>Case Title:</b> {CASE_TITLE} | <b>Case Ref:</b> {CASE_ID}", body_style))
        story.append(Spacer(1, 10))

        # Disclaimer Box
        disc_text = (
            "<b>SYNTHETIC DATA DISCLAIMER:</b> This case scenario, company names, transactions, documents, and figures "
            "are entirely fictional and generated for educational and evaluation purposes. No real-world entities are depicted."
        )
        story.append(Table([[Paragraph(disc_text, disclaimer_style)]], colWidths=[532], style=[
            ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor("#FEF2F2")),
            ('BOX', (0, 0), (-1, -1), 1, colors.HexColor("#FCA5A5")),
            ('PADDING', (0, 0), (-1, -1), 6),
        ]))
        story.append(Spacer(1, 12))

        # 1. Executive Summary & Case Background
        story.append(Paragraph("1. Executive Case Summary", h2_style))
        summary_p = (
            f"An investigation was launched regarding Purchase Order <b>PO-2026-8841</b> placed by <b>{BUYER_NAME}</b> "
            f"with <b>{SUPPLIER_NAME}</b> for 500 Industrial IoT sensor modules valued at <b>INR 18,00,000.00</b>. "
            f"While the supplier claimed complete dispatch of 500 units via SwiftLogistics (SWIFT-994821), "
            f"warehouse inward inspection documented arrival of only 350 units (shortfall of 150 units). "
            f"This report synthesizes all available documentary evidence, courier telemetry, and decision evaluations."
        )
        story.append(Paragraph(summary_p, body_style))
        story.append(Spacer(1, 8))

        # Case Metrics Table
        metrics_data = [
            ["Order Value", f"INR {ORDER_VALUE_INR:,.2f}", "Ordered Quantity", f"{ORDERED_QUANTITY} units"],
            ["Documented Receipt", "350 units", "Unaccounted Shortfall", "150 units (INR 5,40,000.00)"],
            ["Origin Hub Weight", "42.60 kg (5 pkgs)", "Transit Hub Weight", "30.15 kg (3 pkgs - Deficit 12.45 kg)"],
        ]
        t_metrics = Table(metrics_data, colWidths=[120, 146, 120, 146], style=[
            ('BACKGROUND', (0, 0), (0, -1), colors.HexColor("#F1F5F9")),
            ('BACKGROUND', (2, 0), (2, -1), colors.HexColor("#F1F5F9")),
            ('FONTNAME', (0, 0), (-1, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 8),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
            ('PADDING', (0, 0), (-1, -1), 4),
        ])
        story.append(t_metrics)
        story.append(Spacer(1, 14))

        # 2. Evidence Register Table
        story.append(Paragraph("2. Evidence Register & Status", h2_style))
        evidence_list = get_all_evidence(only_available=False, db_path=self.db_path)

        ev_table_rows = [["ID", "Document Title", "Type", "Date", "Status", "Access"]]
        for ev in evidence_list:
            ev_table_rows.append([
                ev["evidence_id"],
                Paragraph(ev["document_title"][:38], body_style),
                ev["source_type"].upper(),
                ev.get("event_date") or "-",
                ev["verification_status"].replace("_", " ").title()[:12],
                ev["access_status"].title()
            ])

        t_ev = Table(ev_table_rows, colWidths=[40, 222, 50, 70, 80, 70], style=[
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#0F172A")),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 8),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")),
            ('PADDING', (0, 0), (-1, -1), 4),
        ])
        story.append(t_ev)
        story.append(Spacer(1, 14))

        # 3. Detected Contradictions
        story.append(Paragraph("3. Contradictions & Conflict Analysis", h2_style))
        conflicts = get_all_conflicts(db_path=self.db_path)
        if conflicts:
            conf_rows = [["ID", "Conflict Type", "Sources", "Severity", "Status"]]
            for c in conflicts:
                conf_rows.append([
                    c["conflict_id"],
                    Paragraph(c["conflict_type"].replace("_", " ").title(), body_style),
                    ", ".join(c.get("evidence_ids", [])),
                    c.get("severity", "high").title(),
                    c.get("status", "unresolved").title()
                ])
            t_conf = Table(conf_rows, colWidths=[45, 177, 120, 80, 110], style=[
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#0F172A")),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, -1), 8),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")),
                ('PADDING', (0, 0), (-1, -1), 4),
            ])
            story.append(t_conf)
        else:
            story.append(Paragraph("No active conflicts detected.", body_style))
        story.append(Spacer(1, 14))

        # 4. Latest Decision Submission & Rubric Evaluation
        story.append(Paragraph("4. Investigator Decision & Rubric Scoring", h2_style))
        attempts = get_decision_attempts(CASE_ID, db_path=self.db_path)
        if attempts:
            latest = attempts[-1]
            story.append(Paragraph(f"<b>Attempt Number:</b> {latest['attempt_number']} | <b>Submitted:</b> {latest['timestamp'][:19]}", bold_body))
            story.append(Spacer(1, 4))
            story.append(Paragraph(f"<b>Overall Score:</b> {latest['total_score']} / {latest['max_score']} ({latest['percentage']}%)", bold_body))
            story.append(Spacer(1, 6))

            story.append(Paragraph(f"<b>Investigator Conclusion:</b><br>{latest['conclusion']}", body_style))
            story.append(Spacer(1, 4))
            story.append(Paragraph(f"<b>Supporting Evidence:</b> {', '.join(latest.get('supporting_evidence_ids', []))}", body_style))
            story.append(Paragraph(f"<b>Counter-Evidence:</b> {', '.join(latest.get('counter_evidence_ids', [])) or 'None cited'}", body_style))
            story.append(Spacer(1, 4))
            story.append(Paragraph(f"<b>Unresolved Uncertainty:</b> {latest['unresolved_uncertainty']}", body_style))
            story.append(Paragraph(f"<b>Recommended Action:</b> {latest['recommended_next_action']}", body_style))
            story.append(Spacer(1, 8))

            # Rubric breakdown table
            score_rows = [["Criterion", "Points Earned", "Max", "Evaluation Finding"]]
            for item in latest.get("breakdown", []):
                score_rows.append([
                    Paragraph(item["criterion_name"], body_style),
                    f"{item['points_earned']:.1f}",
                    f"{item['max_points']:.1f}",
                    Paragraph(item.get("reason", "")[:120], body_style)
                ])
            t_score = Table(score_rows, colWidths=[150, 60, 50, 272], style=[
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#0D9488")),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, -1), 8),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
                ('PADDING', (0, 0), (-1, -1), 4),
            ])
            story.append(t_score)
        else:
            story.append(Paragraph("No decision attempt has been submitted yet for this case.", body_style))

        # Build document with custom canvas for page numbering
        doc.build(story, canvasmaker=NumberedCanvas)
        return target_path
