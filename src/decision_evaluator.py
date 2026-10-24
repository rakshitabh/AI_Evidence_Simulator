"""
Decision Evaluator and Deterministic Rubric Engine for AI Evidence Simulator.
Evaluates investigator decision submissions entirely in Python (0-100 points),
validates citations against released evidence, scores reasoning quality against
evidence-grounded expectations, generates criterion-level feedback, and records
immutable submission attempts with exact evidence snapshots.
"""

import uuid
from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple

from config import CASE_ID, RUBRIC_MAX_SCORES
from src.database import (
    get_all_evidence,
    save_decision_attempt,
    get_decision_attempts,
    get_latest_attempt
)
from src.validators import (
    DecisionSubmission,
    DecisionEvaluationResult,
    CriterionScore
)


class DecisionEvaluator:
    """Evaluates case decisions against deterministic evidence rules."""

    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path

    def evaluate_submission(self, submission: DecisionSubmission) -> Tuple[DecisionEvaluationResult, Dict[str, Any]]:
        """
        Evaluates a submitted investigative conclusion.
        Calculates scores deterministically across 7 rubric categories (total 100 points).
        Stores attempt in SQLite with snapshot of active evidence and access states.
        """
        all_records = get_all_evidence(only_available=False, db_path=self.db_path)
        all_record_map = {r["evidence_id"]: r for r in all_records}
        released_record_map = {r["evidence_id"]: r for r in all_records if r["access_status"] == "available"}
        released_ids = set(released_record_map.keys())

        # Access snapshot at this exact moment
        access_snapshot = {r["evidence_id"]: r["access_status"] for r in all_records}
        status_snapshot = {r["evidence_id"]: r["verification_status"] for r in all_records}
        evidence_snapshot = [
            {"evidence_id": r["evidence_id"], "title": r["document_title"], "status": r["access_status"]}
            for r in all_records
        ]

        # 1. Validate Submitted Evidence IDs
        invalid_or_hidden_supporting = [
            eid for eid in submission.supporting_evidence_ids if eid not in released_ids
        ]
        invalid_or_hidden_counter = [
            eid for eid in submission.counter_evidence_ids if eid not in released_ids
        ]

        valid_supporting = [eid for eid in submission.supporting_evidence_ids if eid in released_ids]
        valid_counter = [eid for eid in submission.counter_evidence_ids if eid in released_ids]

        # Tracking missing items & unsupported claims
        missing_evidence = []
        unsupported_claims = []

        # Rubric criteria scores
        criteria: List[CriterionScore] = []

        # -------------------------------------------------------------
        # Criterion 1: Evidence Extraction & Source Traceability (15 pts)
        # -------------------------------------------------------------
        max_c1 = RUBRIC_MAX_SCORES["evidence_extraction"]
        score_c1 = 0.0
        reasons_c1 = []

        if not invalid_or_hidden_supporting and not invalid_or_hidden_counter:
            score_c1 += 8.0
            reasons_c1.append("All cited evidence IDs are valid, released case records.")
        else:
            bad_citations = invalid_or_hidden_supporting + invalid_or_hidden_counter
            unsupported_claims.append(f"Citations reference unreleased or non-existent records: {', '.join(bad_citations)}")
            reasons_c1.append(f"Deduction: Cited unreleased or non-existent IDs ({', '.join(bad_citations)}).")

        # Baseline records cited
        if "E-001" in valid_supporting or "E-002" in valid_supporting or "E-004" in valid_supporting or "E-004" in valid_counter:
            score_c1 += 7.0
            reasons_c1.append("Traceable foundation established with core business documents (PO/Dispatch/Warehouse).")
        else:
            missing_evidence.append("Core transaction records (E-001, E-002, or E-004) were omitted.")
            reasons_c1.append("Missing core document citations for order or receipt.")

        criteria.append(CriterionScore(
            criterion_name="Evidence Extraction & Source Traceability",
            points_earned=min(score_c1, max_c1),
            max_points=max_c1,
            reason=" ".join(reasons_c1),
            actionable_advice="Ensure every claim references an accessible, verified evidence ID."
        ))

        # -------------------------------------------------------------
        # Criterion 2: Grounded Analysis & Citation Correctness (20 pts)
        # -------------------------------------------------------------
        max_c2 = RUBRIC_MAX_SCORES["grounded_analysis"]
        score_c2 = 0.0
        reasons_c2 = []

        conclusion_lower = submission.overall_conclusion.lower()

        # Did investigator distinguish courier delivery status from item count?
        if "E-003" in valid_supporting and "E-004" not in valid_counter and ("all 500" in conclusion_lower or "fully delivered" in conclusion_lower):
            unsupported_claims.append("Asserting all 500 units were delivered based solely on courier status is contradicted by warehouse count E-004.")
            reasons_c2.append("Courier delivery status (E-003) was cited without acknowledging contradictory warehouse count (E-004).")
        else:
            score_c2 += 10.0
            reasons_c2.append("Appropriately contextualized delivery records without conflating shipment arrival with verified item count.")

        # Correct pairing of supporting and counter evidence
        if valid_counter:
            score_c2 += 10.0
            reasons_c2.append(f"Identified substantive counter-evidence ({', '.join(valid_counter)}) challenging unilateral claims.")
        else:
            missing_evidence.append("No counter-evidence was identified to challenge contradictory assertions.")
            reasons_c2.append("No counter-evidence provided; unilateral claims were left unexamined.")

        criteria.append(CriterionScore(
            criterion_name="Grounded Analysis & Citation Correctness",
            points_earned=min(score_c2, max_c2),
            max_points=max_c2,
            reason=" ".join(reasons_c2),
            actionable_advice="Explicitly cite conflicting records as counter-evidence when investigating discrepancies."
        ))

        # -------------------------------------------------------------
        # Criterion 3: Contradiction Detection & Investigation Logic (20 pts)
        # -------------------------------------------------------------
        max_c3 = RUBRIC_MAX_SCORES["conflict_detection"]
        score_c3 = 0.0
        reasons_c3 = []

        conflicts_addressed = 0
        total_conflicts = 3  # Quantity, Delivery scope, Address authorization

        # Quantity contradiction check
        if ("500" in conclusion_lower and "350" in conclusion_lower) or ("shortfall" in conclusion_lower or "deficit" in conclusion_lower or "missing 150" in conclusion_lower or "discrepancy" in conclusion_lower):
            score_c3 += 7.0
            conflicts_addressed += 1
            reasons_c3.append("Identified the 150-unit quantity discrepancy between dispatch and receipt.")
        else:
            reasons_c3.append("Did not explicitly quantify the 150-unit shortage between dispatch and receipt.")

        # Address change / authorization check
        if "address" in conclusion_lower or "reroute" in conclusion_lower or "unauthorized" in conclusion_lower or "electronic city" in conclusion_lower:
            score_c3 += 7.0
            conflicts_addressed += 1
            reasons_c3.append("Addressed the delivery destination discrepancy and authorization uncertainty.")
        else:
            reasons_c3.append("Did not address the unauthorized address rerouting email.")

        # Courier transit / seal breach awareness
        if "seal" in conclusion_lower or "box 3" in conclusion_lower or "carton" in conclusion_lower or "transit" in conclusion_lower or "courier" in conclusion_lower:
            score_c3 += 6.0
            conflicts_addressed += 1
            reasons_c3.append("Recognized packaging seal breach or transit-stage vulnerability.")
        else:
            reasons_c3.append("Did not evaluate physical packaging condition or transit custody.")

        criteria.append(CriterionScore(
            criterion_name="Contradiction Detection & Investigation Logic",
            points_earned=min(score_c3, max_c3),
            max_points=max_c3,
            reason=" ".join(reasons_c3),
            actionable_advice="Directly address both the quantity mismatch and the unverified address change."
        ))

        # -------------------------------------------------------------
        # Criterion 4: Controlled Evidence Requests & Adaptive Retries (15 pts)
        # -------------------------------------------------------------
        max_c4 = RUBRIC_MAX_SCORES["controlled_requests"]
        score_c4 = 0.0
        reasons_c4 = []

        # Check if investigator unlocked any restricted documents to resolve questions
        unlocked_restricted = [eid for eid in ["E-007", "E-008", "E-009", "E-010", "E-011"] if eid in released_ids]
        cited_restricted = [eid for eid in unlocked_restricted if eid in valid_supporting or eid in valid_counter]

        if unlocked_restricted:
            score_c4 += 8.0
            reasons_c4.append(f"Successfully requested and unlocked restricted records ({', '.join(unlocked_restricted)}).")
            if cited_restricted:
                score_c4 += 7.0
                reasons_c4.append(f"Integrated unlocked records ({', '.join(cited_restricted)}) into investigative findings.")
            else:
                reasons_c4.append("Unlocked records were not cited in the conclusion.")
        else:
            reasons_c4.append("No restricted records were requested to resolve underlying uncertainties.")

        criteria.append(CriterionScore(
            criterion_name="Controlled Evidence Requests & Integration",
            points_earned=min(score_c4, max_c4),
            max_points=max_c4,
            reason=" ".join(reasons_c4),
            actionable_advice="Request restricted records (e.g. Courier Hub Weight Log or Audit Memo) to uncover in-transit facts."
        ))

        # -------------------------------------------------------------
        # Criterion 5: Scoring Correctness & Uncertainty Handling (15 pts)
        # -------------------------------------------------------------
        max_c5 = RUBRIC_MAX_SCORES["scoring_validation"]
        score_c5 = 0.0
        reasons_c5 = []

        # Check uncertainty handling: Did investigator avoid making unfounded criminal accusations without proof?
        premature_blame = ("criminal" in conclusion_lower or "fraud" in conclusion_lower or "stole" in conclusion_lower) and ("E-011" not in released_ids)
        if premature_blame:
            unsupported_claims.append("Prematurely declared criminal fraud or theft without telemetric transit records.")
            reasons_c5.append("Deduction: Premature criminal accusation made without conclusive corroborating proof.")
        else:
            score_c5 += 8.0
            reasons_c5.append("Appropriately balanced assertions without making unsupported criminal accusations.")

        # Explicit explanation of uncertainty
        if len(submission.unresolved_uncertainty.strip()) >= 20:
            score_c5 += 7.0
            reasons_c5.append("Articulated specific unresolved uncertainties and limits of current evidence.")
        else:
            reasons_c5.append("Uncertainty explanation was too sparse.")

        criteria.append(CriterionScore(
            criterion_name="Scoring Correctness & Uncertainty Handling",
            points_earned=min(score_c5, max_c5),
            max_points=max_c5,
            reason=" ".join(reasons_c5),
            actionable_advice="Clearly document what remains unknown rather than jumping to unsubstantiated blame."
        ))

        # -------------------------------------------------------------
        # Criterion 6: Interface & Report Quality (5 pts)
        # -------------------------------------------------------------
        max_c6 = RUBRIC_MAX_SCORES["interface_report"]
        score_c6 = 0.0
        reasons_c6 = []

        if len(submission.recommended_next_action.strip()) >= 25:
            score_c6 += 5.0
            reasons_c6.append("Provided a concrete, actionable next investigative recommendation.")
        else:
            score_c6 += 2.0
            reasons_c6.append("Recommended next action was brief; more detail recommended.")

        criteria.append(CriterionScore(
            criterion_name="Actionable Recommendation & Completeness",
            points_earned=min(score_c6, max_c6),
            max_points=max_c6,
            reason=" ".join(reasons_c6),
            actionable_advice="Specify concrete next investigative steps (e.g. carrier claim filing or joint audit)."
        ))

        # -------------------------------------------------------------
        # Criterion 7: Code Quality & Investigation Rigor (10 pts)
        # -------------------------------------------------------------
        max_c7 = RUBRIC_MAX_SCORES["code_quality"]
        score_c7 = 10.0  # Full credit for well-structured, validated submission
        criteria.append(CriterionScore(
            criterion_name="Investigation Rigor & Validated Submission",
            points_earned=score_c7,
            max_points=max_c7,
            reason="Submission passed all Pydantic structural validations and schema constraints.",
            actionable_advice="Continue submitting well-structured decisions with complete citations."
        ))

        # Total Calculation
        total_score = round(sum(c.points_earned for c in criteria), 1)
        percentage = round((total_score / 100.0) * 100.0, 1)

        summary_feedback = (
            f"Decision Evaluation: {total_score}/100 ({percentage}%). "
            f"Addressed {conflicts_addressed} of {total_conflicts} core case contradictions. "
        )
        if total_score >= 80:
            summary_feedback += "Excellent forensic inquiry with strong grounding in documented evidence."
        elif total_score >= 60:
            summary_feedback += "Competent evaluation; requesting further restricted records will strengthen resolution."
        else:
            summary_feedback += "Inquiry requires additional evidence grounding, counter-evidence citation, and conflict reconciliation."

        eval_result = DecisionEvaluationResult(
            overall_score=total_score,
            max_score=100.0,
            percentage=percentage,
            criteria_breakdown=criteria,
            summary_feedback=summary_feedback,
            missing_evidence_ids=missing_evidence,
            unsupported_claims=unsupported_claims,
            identified_conflicts_addressed=conflicts_addressed,
            total_relevant_conflicts=total_conflicts
        )

        # Retrieve prior attempts to determine attempt number
        prior_attempts = get_decision_attempts(submission.case_id, db_path=self.db_path)
        attempt_number = len(prior_attempts) + 1
        attempt_id = f"ATTEMPT-{uuid.uuid4().hex[:8].upper()}"

        attempt_record = {
            "attempt_id": attempt_id,
            "case_id": submission.case_id,
            "attempt_number": attempt_number,
            "timestamp": datetime.now().isoformat(),
            "conclusion": submission.overall_conclusion,
            "supporting_evidence_ids": submission.supporting_evidence_ids,
            "counter_evidence_ids": submission.counter_evidence_ids,
            "unresolved_uncertainty": submission.unresolved_uncertainty,
            "confidence": submission.confidence,
            "recommended_next_action": submission.recommended_next_action,
            "notes": submission.notes or "",
            "total_score": total_score,
            "max_score": 100.0,
            "percentage": percentage,
            "breakdown": [c.model_dump() for c in criteria],
            "feedback": summary_feedback,
            "evidence_snapshot": evidence_snapshot,
            "access_snapshot": access_snapshot,
            "status_snapshot": status_snapshot
        }

        # Persist immutable attempt
        save_decision_attempt(attempt_record, db_path=self.db_path)
        return eval_result, attempt_record

    def get_history(self, case_id: str = CASE_ID) -> List[Dict[str, Any]]:
        """Retrieves full immutable history of decision attempts."""
        return get_decision_attempts(case_id, db_path=self.db_path)
