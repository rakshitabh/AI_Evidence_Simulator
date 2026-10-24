"""
Evidence Registry service for AI Evidence Simulator.
Provides queries, search, verification status classification, and
access filtering for all evidence items.
"""

from typing import List, Dict, Any, Optional
import pandas as pd
from src.database import get_all_evidence, get_evidence_by_id


class EvidenceRegistry:
    """Manages access and filtering over the case evidence collection."""

    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path

    def get_all(self, only_available: bool = False) -> List[Dict[str, Any]]:
        """Returns all evidence records, optionally filtered by released/available status."""
        return get_all_evidence(only_available=only_available, db_path=self.db_path)

    def get_by_id(self, evidence_id: str) -> Optional[Dict[str, Any]]:
        """Returns a specific evidence record by ID."""
        return get_evidence_by_id(evidence_id, db_path=self.db_path)

    def get_available_ids(self) -> List[str]:
        """Returns list of currently released/available evidence IDs."""
        records = self.get_all(only_available=True)
        return [r["evidence_id"] for r in records]

    def get_restricted_records(self) -> List[Dict[str, Any]]:
        """Returns restricted records with only public metadata visible (no raw text / secret claims)."""
        all_records = self.get_all(only_available=False)
        restricted = []
        for r in all_records:
            if r["access_status"] == "restricted":
                restricted.append({
                    "evidence_id": r["evidence_id"],
                    "document_title": r["document_title"],
                    "source_file": r["source_file"],
                    "source_type": r["source_type"],
                    "issuing_org": r.get("issuing_org", "External Entity"),
                    "event_date": r.get("event_date", "Pending verification"),
                    "relevance_hint": r.get("relevance_hint", "Investigation relevance pending unlock."),
                    "access_status": "restricted"
                })
        return restricted

    def search_evidence(self, query: str, only_available: bool = True) -> List[Dict[str, Any]]:
        """Performs full-text search across document title, summary, parties, and raw text."""
        records = self.get_all(only_available=only_available)
        if not query or not query.strip():
            return records

        q = query.strip().lower()
        matches = []
        for r in records:
            parties_str = " ".join(r.get("parties", [])).lower()
            text_target = f"{r.get('document_title', '')} {r.get('summary_claim', '')} {r.get('raw_text', '')} {parties_str}".lower()
            if q in text_target or q in r.get("evidence_id", "").lower():
                matches.append(r)
        return matches

    def to_dataframe(self, only_available: bool = True) -> pd.DataFrame:
        """Converts evidence register to a formatted Pandas DataFrame for display."""
        records = self.get_all(only_available=only_available)
        if not records:
            return pd.DataFrame()

        rows = []
        for r in records:
            rows.append({
                "Evidence ID": r["evidence_id"],
                "Document Name": r["document_title"],
                "Source Type": r["source_type"].upper(),
                "Event Date": r.get("event_date") or "N/A",
                "Parties Involved": ", ".join(r.get("parties", [])),
                "Key Claim": r["summary_claim"],
                "Quantity": r.get("quantity") if r.get("quantity") is not None else "Unspecified",
                "Amount (INR)": f"₹{r['amount_inr']:,.2f}" if r.get("amount_inr") else "-",
                "Verification Status": r["verification_status"].replace("_", " ").title(),
                "Access Status": r["access_status"].title(),
                "Source File": r["source_file"]
            })
        return pd.DataFrame(rows)
