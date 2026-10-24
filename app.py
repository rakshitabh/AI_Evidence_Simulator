"""
AI Evidence-to-Decision Simulator - Streamlit Web Application.
A streamlined, professional forensic investigation dashboard.
Features a warm creamish-white palette, intuitive case flow, clear evidence explorer,
rule-based contradiction detection, AI inquiry, evidence unlock requests,
deterministic 100-point rubric scoring, and 1-click PDF/JSON report exports.
Designed to be clean, elegant, and completely pyarrow-independent.
"""

import os
import json
from pathlib import Path
from datetime import datetime
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go

from config import (
    CASE_ID,
    CASE_TITLE,
    ORDER_VALUE_INR,
    ORDERED_QUANTITY,
    BUYER_NAME,
    SUPPLIER_NAME,
    COURIER_NAME,
    WAREHOUSE_LOCATION,
    LLM_PROVIDER,
    LLM_MODEL
)
from src.database import (
    init_db,
    get_all_evidence,
    get_all_conflicts,
    get_all_access_requests,
    get_decision_attempts
)
from src.document_processor import ingest_all_case_documents, ingest_file
from src.evidence_registry import EvidenceRegistry
from src.timeline import build_timeline_events, create_timeline_chart
from src.conflict_detector import ConflictDetector
from src.access_control import AccessControlService
from src.llm_service import LLMService
from src.decision_evaluator import DecisionEvaluator
from src.report_generator import ReportGenerator
from src.validators import DecisionSubmission

# Page Configuration
st.set_page_config(
    page_title="AI Evidence Simulator",
    page_icon="⚖️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom Creamish-White & Warm Minimalist Styling
st.markdown("""
<style>
    /* Warm Creamish-White Base */
    .stApp {
        background-color: #FAF8F5;
        color: #2D3748;
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
    }
    
    /* Top Header */
    .cream-header {
        background: #FFFFFF;
        border: 1px solid #EAE5DB;
        border-radius: 12px;
        padding: 22px 28px;
        margin-bottom: 20px;
        box-shadow: 0 2px 8px rgba(0, 0, 0, 0.03);
    }
    .cream-header h1 {
        font-size: 24px;
        font-weight: 700;
        color: #1F2937;
        margin: 0;
        letter-spacing: -0.3px;
    }
    .cream-header p {
        font-size: 13px;
        color: #6B7280;
        margin: 6px 0 0 0;
    }
    
    /* KPI Summary Cards */
    .kpi-container {
        display: flex;
        gap: 12px;
        margin-bottom: 22px;
    }
    .kpi-card {
        background: #FFFFFF;
        border: 1px solid #EAE5DB;
        border-radius: 10px;
        padding: 14px 18px;
        box-shadow: 0 1px 4px rgba(0, 0, 0, 0.02);
        transition: transform 0.15s ease;
    }
    .kpi-card:hover {
        transform: translateY(-2px);
    }
    .kpi-title {
        font-size: 11px;
        font-weight: 700;
        color: #8C827A;
        text-transform: uppercase;
        letter-spacing: 0.5px;
    }
    .kpi-value {
        font-size: 22px;
        font-weight: 800;
        color: #1F2937;
        margin: 4px 0 2px 0;
    }
    .kpi-sub {
        font-size: 12px;
        font-weight: 500;
        color: #6B7280;
    }

    /* Notice Banner */
    .notice-box {
        background-color: #F5EFEB;
        border: 1px solid #E5DACE;
        color: #78350F;
        padding: 10px 16px;
        border-radius: 8px;
        font-size: 12px;
        margin-bottom: 20px;
    }

    /* Clean Creamish HTML Table */
    .custom-table {
        width: 100%;
        border-collapse: separate;
        border-spacing: 0;
        background: #FFFFFF;
        border: 1px solid #EAE5DB;
        border-radius: 10px;
        overflow: hidden;
        margin-bottom: 20px;
        box-shadow: 0 1px 3px rgba(0,0,0,0.02);
    }
    .custom-table th {
        background-color: #F5F2EB;
        color: #4B5563;
        font-size: 12px;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 0.4px;
        padding: 11px 14px;
        text-align: left;
        border-bottom: 1px solid #EAE5DB;
    }
    .custom-table td {
        font-size: 13px;
        color: #374151;
        padding: 11px 14px;
        border-bottom: 1px solid #F3EFEA;
        vertical-align: middle;
    }
    .custom-table tr:last-child td {
        border-bottom: none;
    }
    .custom-table tr:hover td {
        background-color: #FAF8F5;
    }

    /* Status Pill Badges */
    .badge {
        display: inline-block;
        padding: 3px 9px;
        border-radius: 12px;
        font-size: 11px;
        font-weight: 600;
        text-align: center;
    }
    .badge-verified { background-color: #E6F4EA; color: #137333; }
    .badge-claim { background-color: #E8F0FE; color: #1A73E8; }
    .badge-conflict { background-color: #FCE8E6; color: #C5221F; }
    .badge-restricted { background-color: #FEF3D6; color: #B06000; }
    
    /* Clean Content Cards */
    .content-card {
        background: #FFFFFF;
        border: 1px solid #EAE5DB;
        border-radius: 10px;
        padding: 16px 20px;
        margin-bottom: 14px;
        box-shadow: 0 1px 3px rgba(0, 0, 0, 0.02);
    }
</style>
""", unsafe_allow_html=True)


# Pyarrow-independent HTML Table Renderer
def render_html_table(headers: list, rows: list):
    """Renders a clean, creamish HTML table without relying on pyarrow."""
    th_html = "".join([f"<th>{h}</th>" for h in headers])
    
    tr_html = ""
    for r in rows:
        td_html = "".join([f"<td>{cell}</td>" for cell in r])
        tr_html += f"<tr>{td_html}</tr>"

    html = f"""
    <table class="custom-table">
        <thead><tr>{th_html}</tr></thead>
        <tbody>{tr_html}</tbody>
    </table>
    """
    st.markdown(html, unsafe_allow_html=True)


# Initialize Application State
@st.cache_resource
def bootstrap_app():
    """Initializes SQLite database and ingests initial case documents."""
    init_db()
    ingest_all_case_documents()
    detector = ConflictDetector()
    detector.detect_conflicts(only_available=True)
    return True

bootstrap_app()

# Service Initializations
registry = EvidenceRegistry()
detector = ConflictDetector()
access_service = AccessControlService()
llm_service = LLMService()
evaluator = DecisionEvaluator()
reporter = ReportGenerator()


# Sidebar Navigation
with st.sidebar:
    st.markdown("### ⚖️ Evidence Simulator")
    st.caption(f"Case Ref: **{CASE_ID}**")
    st.markdown("---")

    nav_selection = st.radio(
        "Investigation Steps:",
        [
            "1. Case Overview",
            "2. Evidence Register",
            "3. Timeline & Contradictions",
            "4. Ask Investigator AI",
            "5. Unlock Restricted Records",
            "6. Submit Case Decision",
            "7. Attempt History",
            "8. Export Reports"
        ],
        index=0
    )

    st.markdown("---")
    st.markdown("**System Status:**")
    st.caption(f"Provider: `{LLM_PROVIDER.upper()}` | Model: `{LLM_MODEL}`")

    if st.button("🔄 Sync Case Records", use_container_width=True):
        ingest_all_case_documents()
        detector.detect_conflicts(only_available=True)
        st.success("Case records refreshed.")
        st.rerun()

    st.markdown("---")
    st.caption("AI Evidence-to-Decision Simulator\nAcademic Forensic Inquiry Platform")


# Top Header Banner
st.markdown(f"""
<div class="cream-header">
    <h1>Forensic Case Inquiry: Discrepant Electronics Shipment</h1>
    <p>Buyer: <b>{BUYER_NAME}</b> | Supplier: <b>{SUPPLIER_NAME}</b> | Carrier: <b>{COURIER_NAME}</b></p>
</div>
""", unsafe_allow_html=True)

# Synthetic Disclaimer
st.markdown("""
<div class="notice-box">
    ℹ️ <b>Synthetic Case Notice:</b> All documents, companies, parties, and transaction records in this inquiry are fictional simulations.
</div>
""", unsafe_allow_html=True)


# Dynamic KPI Metric Cards
available_docs = registry.get_all(only_available=True)
restricted_docs = registry.get_restricted_records()
active_conflicts = detector.detect_conflicts(only_available=True)
history = evaluator.get_history(CASE_ID)

k1, k2, k3, k4, k5 = st.columns(5)

with k1:
    st.markdown(f"""
    <div class="kpi-card">
        <div class="kpi-title">Order Commitment</div>
        <div class="kpi-value">₹{ORDER_VALUE_INR:,.0f}</div>
        <div class="kpi-sub">PO-2026-8841</div>
    </div>
    """, unsafe_allow_html=True)

with k2:
    st.markdown(f"""
    <div class="kpi-card">
        <div class="kpi-title">Ordered Quantity</div>
        <div class="kpi-value">{ORDERED_QUANTITY} <span style="font-size:13px; font-weight:normal;">units</span></div>
        <div class="kpi-sub">Supplier Claim: 500</div>
    </div>
    """, unsafe_allow_html=True)

with k3:
    st.markdown(f"""
    <div class="kpi-card">
        <div class="kpi-title">Warehouse Count</div>
        <div class="kpi-value" style="color: #DC2626;">350 <span style="font-size:13px; font-weight:normal;">units</span></div>
        <div class="kpi-sub" style="color: #DC2626;">-150 units deficit</div>
    </div>
    """, unsafe_allow_html=True)

with k4:
    st.markdown(f"""
    <div class="kpi-card">
        <div class="kpi-title">Active Contradictions</div>
        <div class="kpi-value" style="color: #D97706;">{len(active_conflicts)}</div>
        <div class="kpi-sub">Unreconciled issues</div>
    </div>
    """, unsafe_allow_html=True)

with k5:
    st.markdown(f"""
    <div class="kpi-card">
        <div class="kpi-title">Released Records</div>
        <div class="kpi-value" style="color: #059669;">{len(available_docs)} <span style="font-size:13px; font-weight:normal;">/ {len(available_docs) + len(restricted_docs)}</span></div>
        <div class="kpi-sub">{len(restricted_docs)} locked records</div>
    </div>
    """, unsafe_allow_html=True)

st.markdown("<br>", unsafe_allow_html=True)


# -----------------------------------------------------------------------------
# STEP 1: CASE OVERVIEW
# -----------------------------------------------------------------------------
if nav_selection == "1. Case Overview":
    st.subheader("📋 Case Overview")
    
    c_left, c_right = st.columns([3, 2])
    with c_left:
        st.markdown("""
        <div class="content-card">
            <h4 style="margin-top:0; color:#1F2937;">What Happened?</h4>
            <p style="font-size:14px; line-height:1.6; color:#4B5563;">
                <b>Nexus Electronics</b> ordered <b>500 units</b> of Industrial IoT Sensor Modules (₹18,00,000) under Purchase Order <code>PO-2026-8841</code>.
                <br><br>
                The supplier, <b>Vertex Semiconductor</b>, claims all 500 units were packaged and handed over to <b>SwiftLogistics</b>.
                The courier tracking shows status <b>Delivered</b>.
                <br><br>
                However, when the shipment arrived at the warehouse dock, inspectors found only <b>350 units</b>—leaving <b>150 units missing</b> (₹5,40,000 shortfall), with the outer tamper seal on Carton 3 broken.
                An external email was also discovered requesting an unverified address reroute to Electronic City.
            </p>
        </div>
        """, unsafe_allow_html=True)

        st.markdown("""
        <div class="content-card">
            <h4 style="margin-top:0; color:#1F2937;">Key Questions to Resolve</h4>
            <ul style="font-size:13px; line-height:1.8; color:#4B5563; padding-left:20px;">
                <li>Did the supplier actually pack and dispatch 500 units?</li>
                <li>Does courier tracking prove that 500 units physically arrived?</li>
                <li>Was the delivery address change authorized or rejected?</li>
                <li>At what transit point was the package seal breached and weight lost?</li>
            </ul>
        </div>
        """, unsafe_allow_html=True)

    with c_right:
        st.markdown(f"""
        <div class="content-card">
            <h4 style="margin-top:0; color:#1F2937;">Key Parties</h4>
            <p style="font-size:13px; margin:4px 0;"><b>Buyer:</b> {BUYER_NAME} (Whitefield, Bengaluru)</p>
            <p style="font-size:13px; margin:4px 0;"><b>Supplier:</b> {SUPPLIER_NAME} (HITEC City, Hyderabad)</p>
            <p style="font-size:13px; margin:4px 0;"><b>Carrier:</b> {COURIER_NAME} (Waybill SWIFT-994821)</p>
            <p style="font-size:13px; margin:4px 0;"><b>Receiving Dock:</b> Whitefield Central Warehouse Dock 4</p>
        </div>
        """, unsafe_allow_html=True)

        st.markdown("""
        <div class="content-card" style="border-left: 4px solid #D97706;">
            <h4 style="margin-top:0; color:#B45309;">Prompt Injection Defense Notice</h4>
            <p style="font-size:12px; line-height:1.5; color:#78350F;">
                One external email (<code>supplier_urgent_clarification.eml</code>) contains an adversarial prompt injection command 
                attempting to force the AI to declare that all 500 units arrived. The system safely isolates and ignores this command.
            </p>
        </div>
        """, unsafe_allow_html=True)


# -----------------------------------------------------------------------------
# STEP 2: EVIDENCE REGISTER
# -----------------------------------------------------------------------------
elif nav_selection == "2. Evidence Register":
    st.subheader("📁 Case Evidence Register")
    st.caption("Browse, search, and inspect all currently released case documents.")

    col_s1, col_s2 = st.columns([3, 1])
    with col_s1:
        search_kw = st.text_input("🔍 Search documents by keyword or ID:", "")
    with col_s2:
        filter_status = st.selectbox("Status Filter:", ["All", "verified_fact", "documented_claim", "conflicting_claim"])

    records = registry.search_evidence(search_kw, only_available=True)
    if filter_status != "All":
        records = [r for r in records if r["verification_status"] == filter_status]

    if records:
        # Render clean HTML table (No pyarrow dependency!)
        headers = ["ID", "Document Title", "Type", "Event Date", "Key Claim", "Quantity", "Status"]
        table_rows = []
        for r in records:
            status_cls = {
                "verified_fact": "badge-verified",
                "documented_claim": "badge-claim",
                "conflicting_claim": "badge-conflict"
            }.get(r["verification_status"], "badge-claim")

            badge_html = f'<span class="badge {status_cls}">{r["verification_status"].replace("_", " ").title()}</span>'
            qty_text = str(r["quantity"]) if r.get("quantity") is not None else "—"

            table_rows.append([
                f"<b>{r['evidence_id']}</b>",
                r["document_title"],
                f"<code>{r['source_type'].upper()}</code>",
                r.get("event_date") or "—",
                r["summary_claim"],
                qty_text,
                badge_html
            ])

        render_html_table(headers, table_rows)
    else:
        st.info("No matching records found.")

    st.markdown("---")
    st.subheader("📄 Document Excerpts & Verification Hashes")
    for r in records:
        with st.expander(f"📑 {r['evidence_id']} — {r['document_title']} ({r['source_file']})"):
            st.markdown(f"**Document Hash (SHA-256):** `{r['file_hash']}`")
            st.text_area("Extracted Content", r["raw_text"], height=130, key=f"raw_{r['evidence_id']}", disabled=True)


# -----------------------------------------------------------------------------
# STEP 3: TIMELINE & CONTRADICTIONS
# -----------------------------------------------------------------------------
elif nav_selection == "3. Timeline & Contradictions":
    st.subheader("⏱️ Case Timeline")
    st.caption("Chronological progression of transactions, transit checkpoints, and physical inspection events.")

    events = build_timeline_events(only_available=True)
    fig_time = create_timeline_chart(events)
    fig_time.update_layout(paper_bgcolor="#FFFFFF", plot_bgcolor="#FAF8F5")
    st.plotly_chart(fig_time, use_container_width=True)

    st.markdown("---")
    st.subheader("⚡ Identified Contradictions")
    st.caption("Contradictions automatically detected across released records.")

    conflicts = detector.detect_conflicts(only_available=True)
    for c in conflicts:
        sev_color = "#DC2626" if c["severity"] in ["high", "critical"] else "#D97706"
        st.markdown(f"""
        <div class="content-card" style="border-left: 4px solid {sev_color};">
            <div style="display:flex; justify-content:space-between; align-items:center;">
                <b style="color:#1F2937; font-size:15px;">{c['conflict_id']}: {c['conflict_type'].replace('_', ' ').title()}</b>
                <span class="badge" style="background-color:{sev_color}18; color:{sev_color};">
                    {c['severity'].upper()} SEVERITY
                </span>
            </div>
            <p style="font-size:13px; color:#4B5563; margin:8px 0 6px 0;">{c['description']}</p>
            <div style="font-size:12px; color:#6B7280;">
                <b>Sources:</b> {', '.join(c['evidence_ids'])} • <b>Key Question:</b> <i>"{c['investigative_question']}"</i>
            </div>
        </div>
        """, unsafe_allow_html=True)


# -----------------------------------------------------------------------------
# STEP 4: ASK INVESTIGATOR AI
# -----------------------------------------------------------------------------
elif nav_selection == "4. Ask Investigator AI":
    st.subheader("🤖 Ask the Investigation Assistant")
    st.caption("Pose questions to the AI assistant. Answers are grounded in released evidence and protected against prompt injection.")

    st.markdown("**Quick Inquiries (1-Click):**")
    b1, b2, b3 = st.columns(3)
    preset = ""
    with b1:
        if st.button("📦 Did supplier dispatch 500 units?", use_container_width=True):
            preset = "What evidence supports the supplier's dispatch claim?"
    with b2:
        if st.button("🚚 Does tracking prove 500 units arrived?", use_container_width=True):
            preset = "Does courier tracking prove that all 500 components arrived?"
    with b3:
        if st.button("📍 Was address change authorized?", use_container_width=True):
            preset = "Was the delivery address change authorized?"

    q_input = st.text_input("Or enter your question:", value=preset, placeholder="e.g. Which documents conflict about quantities?")

    if st.button("Submit Inquiry", type="primary") or preset:
        if q_input.strip():
            with st.spinner("Analyzing case evidence..."):
                ans = llm_service.answer_question(q_input)

            st.markdown(f"""
            <div class="content-card" style="border-left: 4px solid #059669; margin-top:16px;">
                <h4 style="margin-top:0; color:#065F46;">Investigation Finding</h4>
                <p style="font-size:14px; line-height:1.6; color:#1F2937;">{ans.answer}</p>
            </div>
            """, unsafe_allow_html=True)

            col_c1, col_c2 = st.columns(2)
            with col_c1:
                st.markdown("**Supporting Citations:**")
                if ans.supporting_evidence_ids:
                    for eid in ans.supporting_evidence_ids:
                        rec = registry.get_by_id(eid)
                        st.markdown(f"- 🟢 **{eid}**: {rec['document_title'] if rec else 'Record'}")
                else:
                    st.caption("No supporting citations.")

                st.markdown("**Counter-Evidence Citations:**")
                if ans.counter_evidence_ids:
                    for eid in ans.counter_evidence_ids:
                        rec = registry.get_by_id(eid)
                        st.markdown(f"- 🔴 **{eid}**: {rec['document_title'] if rec else 'Record'}")
                else:
                    st.caption("No counter-evidence identified.")

            with col_c2:
                st.markdown("**Identified Unknowns:**")
                for u in ans.unknowns:
                    st.markdown(f"- ⚠️ {u}")

                st.markdown(f"**Confidence:** `{ans.confidence.upper()}`")
                st.markdown(f"**Recommended Next Action:** _{ans.recommended_next_step}_")


# -----------------------------------------------------------------------------
# STEP 5: UNLOCK RESTRICTED RECORDS
# -----------------------------------------------------------------------------
elif nav_selection == "5. Unlock Restricted Records":
    st.subheader("🔒 Controlled Evidence Catalogue")
    st.caption("Certain records (e.g. courier PODs, hub weight logs) are restricted. Provide an investigative reason to request authorization.")

    restricted_catalogue = access_service.get_restricted_catalogue()

    if not restricted_catalogue:
        st.success("🎉 All restricted case records have been authorized and unlocked into active evidence!")
    else:
        for r in restricted_catalogue:
            st.markdown(f"""
            <div class="content-card">
                <div style="display:flex; justify-content:space-between;">
                    <b style="color:#1F2937; font-size:15px;">🔒 {r['evidence_id']} — {r['document_title']}</b>
                    <span class="badge badge-restricted">LOCKED</span>
                </div>
                <p style="font-size:12px; color:#6B7280; margin:4px 0;"><b>Issuing Entity:</b> {r['issuing_org']} • <b>Date:</b> {r['event_date']}</p>
                <p style="font-size:13px; color:#374151; margin:6px 0 0 0;"><b>Why It Matters:</b> {r['relevance_hint']}</p>
            </div>
            """, unsafe_allow_html=True)

        st.markdown("---")
        st.subheader("Submit Access Request")
        with st.form("req_form"):
            target_doc = st.selectbox(
                "Choose Record to Request:",
                [f"{r['evidence_id']} — {r['document_title']}" for r in restricted_catalogue]
            )
            reason_txt = st.text_area(
                "Investigative Justification (At least 8 words explaining why you need this document):",
                placeholder="e.g. We need to check conveyor scales and hub gross weight telemetry to verify whether mass loss occurred in transit."
            )
            sub_req = st.form_submit_button("Request Record Authorization", type="primary")
            if sub_req:
                eid = target_doc.split(" — ")[0]
                ok, msg = access_service.evaluate_request(eid, reason_txt)
                if ok:
                    st.success(f"✅ {msg}")
                    detector.detect_conflicts(only_available=True)
                    st.rerun()
                else:
                    st.error(f"❌ {msg}")


# -----------------------------------------------------------------------------
# STEP 6: SUBMIT CASE DECISION
# -----------------------------------------------------------------------------
elif nav_selection == "6. Submit Case Decision":
    st.subheader("⚖️ Submit Decision & View Python Rubric Score")
    st.caption("Submit your investigative findings. Decisions are evaluated entirely by a deterministic 100-point Python rubric.")

    available_ids = registry.get_available_ids()

    with st.form("dec_form"):
        col_d1, col_d2 = st.columns([3, 2])
        with col_d1:
            conc = st.text_area(
                "Investigative Conclusion:",
                placeholder="State your findings regarding the 500 units ordered, 350 units received, seal breach, and transit custody...",
                height=120
            )
            unc = st.text_area(
                "Remaining Uncertainties:",
                placeholder="Explain what cannot be conclusively proven with current evidence...",
                height=80
            )
        with col_d2:
            supp = st.multiselect("Supporting Evidence IDs:", available_ids, default=[eid for eid in ["E-001", "E-002"] if eid in available_ids])
            counter = st.multiselect("Counter-Evidence IDs:", available_ids, default=[eid for eid in ["E-004"] if eid in available_ids])
            conf_val = st.selectbox("Confidence:", ["low", "medium", "high"], index=1)
            next_act = st.text_input("Recommended Action:", placeholder="e.g. File carrier transit loss claim with SwiftLogistics")

        sub_dec = st.form_submit_button("Submit Decision for Evaluation", type="primary")

        if sub_dec:
            if len(conc.strip()) < 20:
                st.error("Conclusion is too brief (minimum 20 characters).")
            elif not supp:
                st.error("Please select at least one supporting evidence ID.")
            elif len(unc.strip()) < 10:
                st.error("Please explain remaining uncertainties (minimum 10 characters).")
            elif len(next_act.strip()) < 10:
                st.error("Please provide a recommended next action.")
            else:
                payload = DecisionSubmission(
                    case_id=CASE_ID,
                    overall_conclusion=conc.strip(),
                    supporting_evidence_ids=supp,
                    counter_evidence_ids=counter,
                    unresolved_uncertainty=unc.strip(),
                    confidence=conf_val,
                    recommended_next_action=next_act.strip()
                )
                res, att = evaluator.evaluate_submission(payload)
                st.success(f"✅ Attempt #{att['attempt_number']} evaluated and recorded!")
                st.rerun()

    # Show latest evaluation
    latest_history = evaluator.get_history(CASE_ID)
    if latest_history:
        lat = latest_history[-1]
        st.markdown("---")
        st.subheader(f"Latest Score: Attempt #{lat['attempt_number']}")

        sc1, sc2 = st.columns([1, 3])
        with sc1:
            st.markdown(f"""
            <div class="content-card" style="text-align:center; border: 2px solid #059669;">
                <div style="font-size:12px; font-weight:700; color:#6B7280;">TOTAL SCORE</div>
                <div style="font-size:42px; font-weight:900; color:#059669; margin:4px 0;">{lat['total_score']:.1f}</div>
                <div style="font-size:13px; color:#374151;">out of 100 ({lat['percentage']}%)</div>
            </div>
            """, unsafe_allow_html=True)

        with sc2:
            st.markdown(f"**Evaluator Feedback:**\n{lat['feedback']}")
            st.markdown(f"**Submitted Conclusion:**\n_{lat['conclusion']}_")

        st.markdown("### Criterion Breakdown")
        crit_headers = ["Criterion", "Score", "Max", "Finding", "Advice"]
        crit_rows = []
        for c in lat.get("breakdown", []):
            crit_rows.append([
                f"<b>{c['criterion_name']}</b>",
                f"{c['points_earned']:.1f}",
                f"{c['max_points']:.1f}",
                c["reason"],
                c.get("actionable_advice") or "—"
            ])
        render_html_table(crit_headers, crit_rows)


# -----------------------------------------------------------------------------
# STEP 7: ATTEMPT HISTORY
# -----------------------------------------------------------------------------
elif nav_selection == "7. Attempt History":
    st.subheader("📈 Decision Revision History")
    st.caption("Review all attempts, score changes, and active evidence snapshots over time.")

    attempts = evaluator.get_history(CASE_ID)
    if not attempts:
        st.info("No decision attempts submitted yet.")
    else:
        for a in reversed(attempts):
            with st.expander(f"Attempt #{a['attempt_number']} — Score: {a['total_score']:.1f}/100 ({a['timestamp'][:19]})"):
                st.markdown(f"**Conclusion:** {a['conclusion']}")
                st.markdown(f"**Supporting Evidence:** `{', '.join(a['supporting_evidence_ids'])}` | **Counter-Evidence:** `{', '.join(a['counter_evidence_ids']) or 'None'}`")
                st.markdown(f"**Uncertainty:** {a['unresolved_uncertainty']}")
                st.markdown(f"**Next Action:** {a['recommended_next_action']}")
                st.markdown("**Evidence Snapshot at Submission:**")
                st.json(a.get("access_snapshot", {}))


# -----------------------------------------------------------------------------
# STEP 8: EXPORT REPORTS
# -----------------------------------------------------------------------------
elif nav_selection == "8. Export Reports":
    st.subheader("📑 Final Investigation Report Export")
    st.caption("Download comprehensive, publication-ready PDF and JSON case reports.")

    r_col1, r_col2 = st.columns(2)
    with r_col1:
        st.markdown("""
        <div class="content-card">
            <h4 style="margin-top:0; color:#1F2937;">📄 Formal PDF Report</h4>
            <p style="font-size:13px; color:#4B5563;">
                Complete formal document with executive metrics, evidence register, timeline,
                detected contradictions, attempt history, and dynamic page numbering.
            </p>
        </div>
        """, unsafe_allow_html=True)
        if st.button("Generate & Download PDF", type="primary", use_container_width=True):
            pdf_path = reporter.export_pdf_report()
            with open(pdf_path, "rb") as f:
                pdf_bytes = f.read()
            st.download_button(
                label="⬇️ Click to Download PDF File",
                data=pdf_bytes,
                file_name=pdf_path.name,
                mime="application/pdf",
                use_container_width=True
            )
            st.success(f"PDF ready: `{pdf_path.name}`")

    with r_col2:
        st.markdown("""
        <div class="content-card">
            <h4 style="margin-top:0; color:#1F2937;">💾 Machine-Readable JSON</h4>
            <p style="font-size:13px; color:#4B5563;">
                Full structured JSON export containing case metadata, extracted claims,
                conflict mappings, access audits, and decision snapshots.
            </p>
        </div>
        """, unsafe_allow_html=True)
        if st.button("Generate & Download JSON", use_container_width=True):
            json_path = reporter.export_json_report()
            with open(json_path, "rb") as f:
                json_bytes = f.read()
            st.download_button(
                label="⬇️ Click to Download JSON File",
                data=json_bytes,
                file_name=json_path.name,
                mime="application/json",
                use_container_width=True
            )
            st.success(f"JSON ready: `{json_path.name}`")
