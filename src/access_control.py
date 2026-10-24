"""
Access Control and Controlled Evidence Request Service.
Enforces strict boundaries around restricted records. Evaluates investigative requests
using a deterministic release policy, records audit trails, and unlocks documents only
upon valid authorized justification.
"""

from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime
import uuid

from config import ACCESS_CONTROL_MODE, MIN_REASON_WORD_COUNT
from src.database import (
    get_all_evidence,
    get_evidence_by_id,
    update_evidence_access,
    log_access_audit,
    save_access_request,
    get_all_access_requests
)
from src.validators import EvidenceAccessRequest

# Keyword relevance mappings for deterministic approval
DOCUMENT_POLICY_KEYWORDS = {
    "E-007": ["pod", "proof of delivery", "signature", "recipient", "handover", "docket", "courier slip", "dock", "carton", "receiving sign", "intact"],
    "E-008": ["address", "reroute", "authorization", "approval", "internal memo", "procurement", "governance", "priya", "divert", "electronic city", "policy"],
    "E-009": ["gate", "security", "vehicle", "van", "truck", "arrival", "logbook", "guard", "entry", "tamper", "seal"],
    "E-010": ["manifest", "packing", "carton", "box", "serial", "breakdown", "dispatch list", "batch", "packaging", "supplier packing"],
    "E-011": ["weight", "scale", "telemetry", "hub", "gross weight", "sorting", "transit scan", "conveyor", "loss in transit", "mass"]
}


class AccessControlService:
    """Manages restricted evidence catalogue and deterministic access requests."""

    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path

    def get_restricted_catalogue(self) -> List[Dict[str, Any]]:
        """
        Returns catalogue of restricted documents with ONLY non-sensitive metadata.
        NEVER leaks raw_text, secret claims, or internal text before release.
        """
        all_records = get_all_evidence(only_available=False, db_path=self.db_path)
        catalogue = []
        for r in all_records:
            if r["access_status"] == "restricted":
                catalogue.append({
                    "evidence_id": r["evidence_id"],
                    "document_title": r["document_title"],
                    "source_file": r["source_file"],
                    "issuing_org": r.get("issuing_org", "External Entity"),
                    "event_date": r.get("event_date") or "Pending access",
                    "relevance_hint": r.get("relevance_hint", "Investigative record required to resolve case uncertainty."),
                    "access_status": "restricted"
                })
        return catalogue

    def evaluate_request(self, evidence_id: str, investigative_reason: str, actor: str = "Lead Investigator") -> Tuple[bool, str]:
        """
        Evaluates an access request deterministically.
        Checks:
        1. Document existence and restricted status.
        2. Substantive reason length (minimum word count).
        3. Domain relevance (keywords matching investigative purpose).
        Updates database and audit logs accordingly.
        """
        clean_reason = investigative_reason.strip() if investigative_reason else ""
        words = clean_reason.split()
        req_id = f"REQ-{uuid.uuid4().hex[:8].upper()}"

        # 1. Validate Evidence ID
        record = get_evidence_by_id(evidence_id, db_path=self.db_path)
        if not record:
            return False, f"Invalid request: Record ID '{evidence_id}' does not exist in the case registry."

        if record["access_status"] == "available":
            return True, f"Record '{evidence_id}' is already released and accessible in the evidence register."

        # 2. Check Word Count / Substantiveness
        if len(words) < MIN_REASON_WORD_COUNT:
            decision_note = (
                f"Insufficient investigative justification. The explanation ({len(words)} words) is too brief. "
                f"Please provide at least {MIN_REASON_WORD_COUNT} words articulating how this record resolves an active case contradiction."
            )
            save_access_request({
                "request_id": req_id,
                "evidence_id": evidence_id,
                "investigative_reason": clean_reason,
                "status": "rejected",
                "decision_notes": decision_note,
                "requested_at": datetime.now().isoformat(),
                "decided_at": datetime.now().isoformat()
            }, db_path=self.db_path)

            log_access_audit(
                action="REQUEST_REJECTED",
                evidence_id=evidence_id,
                actor=actor,
                reason=clean_reason,
                metadata={"reason": "insufficient_word_count", "length": len(words)},
                db_path=self.db_path
            )
            return False, decision_note

        # 3. Check Keyword Relevance to Target Document
        target_keywords = DOCUMENT_POLICY_KEYWORDS.get(evidence_id, [])
        lower_reason = clean_reason.lower()
        matched_keywords = [kw for kw in target_keywords if kw in lower_reason]

        if ACCESS_CONTROL_MODE == "strict" and target_keywords and not matched_keywords:
            decision_note = (
                f"Relevance criteria not met for record {evidence_id}. Your stated reason does not address "
                f"the investigative domain of this record. For example, explain how this document relates to "
                f"verifying {target_keywords[0]} or {target_keywords[1]}."
            )
            save_access_request({
                "request_id": req_id,
                "evidence_id": evidence_id,
                "investigative_reason": clean_reason,
                "status": "rejected",
                "decision_notes": decision_note,
                "requested_at": datetime.now().isoformat(),
                "decided_at": datetime.now().isoformat()
            }, db_path=self.db_path)

            log_access_audit(
                action="REQUEST_REJECTED",
                evidence_id=evidence_id,
                actor=actor,
                reason=clean_reason,
                metadata={"reason": "keyword_relevance_failed"},
                db_path=self.db_path
            )
            return False, decision_note

        # Approved: Unlock record in SQLite
        update_evidence_access(evidence_id, "available", db_path=self.db_path)
        success_note = (
            f"Access Approved: Sufficient investigative justification established "
            f"(matched relevance criteria: {', '.join(matched_keywords) if matched_keywords else 'substantive inquiry'}). "
            f"Record {evidence_id} is now released to the active investigation."
        )

        save_access_request({
            "request_id": req_id,
            "evidence_id": evidence_id,
            "investigative_reason": clean_reason,
            "status": "approved",
            "decision_notes": success_note,
            "requested_at": datetime.now().isoformat(),
            "decided_at": datetime.now().isoformat()
        }, db_path=self.db_path)

        log_access_audit(
            action="REQUEST_APPROVED_AND_RELEASED",
            evidence_id=evidence_id,
            actor=actor,
            reason=clean_reason,
            metadata={"matched_keywords": matched_keywords},
            db_path=self.db_path
        )

        return True, success_note

    def get_request_history(self) -> List[Dict[str, Any]]:
        """Retrieves complete history of submitted evidence requests."""
        return get_all_access_requests(db_path=self.db_path)
