"""
Timeline generation module for AI Evidence Simulator.
Constructs chronological sequence of events from case records with source references
and interactive Plotly visualization.
"""

from typing import List, Dict, Any, Optional
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from src.database import get_all_evidence


def build_timeline_events(only_available: bool = True, db_path: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Constructs an ordered list of timeline events from extracted evidence records.
    Filters out restricted documents unless explicitly permitted.
    """
    evidence_list = get_all_evidence(only_available=only_available, db_path=db_path)
    events = []

    for ev in evidence_list:
        event_date = ev.get("event_date")
        if not event_date:
            continue

        events.append({
            "event_date": event_date,
            "evidence_id": ev["evidence_id"],
            "document_title": ev["document_title"],
            "source_file": ev["source_file"],
            "claim_type": ev["claim_type"],
            "summary": ev["summary_claim"],
            "parties": ", ".join(ev.get("parties", [])),
            "verification_status": ev["verification_status"],
            "access_status": ev["access_status"]
        })

    # Sort chronologically by event_date, then evidence_id
    events.sort(key=lambda x: (x["event_date"], x["evidence_id"]))
    return events


def create_timeline_chart(events: List[Dict[str, Any]]) -> go.Figure:
    """
    Generates an interactive Plotly timeline chart showing milestones,
    verification statuses, and source document links.
    """
    if not events:
        fig = go.Figure()
        fig.update_layout(title="No timeline events available")
        return fig

    df = pd.DataFrame(events)

    color_map = {
        "verified_fact": "#0D9488",       # Teal
        "documented_claim": "#3B82F6",    # Blue
        "conflicting_claim": "#EF4444",   # Red
        "unknown_or_unresolved": "#F59E0B"# Amber
    }

    fig = go.Figure()

    # Add milestone markers on a time axis
    y_positions = [i % 4 for i in range(len(events))]

    for idx, row in df.iterrows():
        color = color_map.get(row["verification_status"], "#64748B")
        fig.add_trace(go.Scatter(
            x=[row["event_date"]],
            y=[y_positions[idx]],
            mode="markers+text",
            name=f"{row['evidence_id']}: {row['document_title']}",
            text=[f"<b>{row['evidence_id']}</b><br>{row['event_date']}"],
            textposition="top center",
            marker=dict(
                size=22,
                color=color,
                line=dict(color="#0F172A", width=1.5),
                symbol="circle"
            ),
            hoverinfo="text",
            hovertext=(
                f"<b>{row['evidence_id']} - {row['document_title']}</b><br>"
                f"<b>Date:</b> {row['event_date']}<br>"
                f"<b>Parties:</b> {row['parties']}<br>"
                f"<b>Status:</b> {row['verification_status']}<br>"
                f"<b>Summary:</b> {row['summary']}"
            )
        ))

    # Add connecting line
    fig.add_trace(go.Scatter(
        x=df["event_date"],
        y=y_positions,
        mode="lines",
        line=dict(color="#CBD5E1", width=2, dash="dot"),
        showlegend=False,
        hoverinfo="skip"
    ))

    fig.update_layout(
        title=dict(text="<b>Chronological Case Timeline & Milestones</b>", font=dict(color="#0F172A", size=16)),
        paper_bgcolor="#FFFFFF",
        plot_bgcolor="#F8FAFC",
        xaxis=dict(
            title="Event Date",
            showgrid=True,
            gridcolor="#E2E8F0",
            type="category"
        ),
        yaxis=dict(
            showticklabels=False,
            showgrid=False,
            zeroline=False,
            range=[-1, 4.5]
        ),
        height=380,
        margin=dict(l=20, r=20, t=50, b=30),
        showlegend=False
    )

    return fig
