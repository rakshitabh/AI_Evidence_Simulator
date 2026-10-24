"""
Pydantic validators and data transfer schemas for AI Evidence Simulator.
Enforces rigorous validation on evidence records, claims, conflicts, and LLM outputs.
"""

from typing import List, Optional, Literal
from pydantic import BaseModel, Field, field_validator
from datetime import date, datetime

# Evidence Verification Statuses
VerificationStatus = Literal[
    "verified_fact",
    "documented_claim",
    "conflicting_claim",
    "unknown_or_unresolved"
]

# Evidence Access Statuses
AccessStatus = Literal[
    "available",
    "restricted"
]

# Source Document Types
SourceType = Literal[
    "pdf",
    "eml",
    "docx",
    "system_record"
]

# Confidence Levels
ConfidenceLevel = Literal[
    "low",
    "medium",
    "high"
]


class EvidenceClaim(BaseModel):
    """Structured claim extracted from a document."""
    claim_id: Optional[str] = None
    evidence_id: str
    claim_type: str = Field(..., description="e.g., ordered_quantity, dispatched_quantity, delivered_status, received_quantity, address_change")
    event_date: Optional[str] = None
    parties: List[str] = Field(default_factory=list)
    quantity: Optional[int] = None
    amount_inr: Optional[float] = None
    claim_text: str = Field(..., min_length=5)
    verification_status: VerificationStatus = "documented_claim"


class EvidenceRecord(BaseModel):
    """Complete structured evidence item stored in the registry."""
    evidence_id: str = Field(..., pattern=r"^E-\d{3}$")
    source_file: str
    source_type: SourceType
    file_hash: str
    page_number: Optional[int] = 1
    event_date: Optional[str] = None
    parties: List[str] = Field(default_factory=list)
    document_title: str
    summary_claim: str
    claim_type: str
    quantity: Optional[int] = None
    amount_inr: Optional[float] = None
    raw_text: str
    verification_status: VerificationStatus = "documented_claim"
    access_status: AccessStatus = "available"
    issuing_org: Optional[str] = None
    relevance_hint: Optional[str] = None
    created_at: Optional[str] = None

    @field_validator("evidence_id")
    def validate_id_format(cls, v):
        if not v.startswith("E-"):
            raise ValueError(f"Evidence ID must start with 'E-', got {v}")
        return v


class ConflictRecord(BaseModel):
    """Structured representation of an identified conflict/contradiction."""
    conflict_id: str = Field(..., pattern=r"^C-\d{3}$")
    conflict_type: str
    description: str
    evidence_ids: List[str]
    severity: Literal["low", "medium", "high", "critical"] = "high"
    status: Literal["unresolved", "resolved", "partially_resolved"] = "unresolved"
    investigative_question: str


class EvidenceAccessRequest(BaseModel):
    """Request submitted by an investigator to unlock a restricted record."""
    request_id: Optional[str] = None
    evidence_id: str = Field(..., pattern=r"^E-\d{3}$")
    investigative_reason: str = Field(..., min_length=15, description="Substantive justification for requesting access")
    status: Literal["pending", "approved", "rejected"] = "pending"
    decision_notes: Optional[str] = None
    requested_at: Optional[str] = None
    decided_at: Optional[str] = None


class DecisionSubmission(BaseModel):
    """Investigator's submitted conclusion and evaluation payload."""
    case_id: str
    overall_conclusion: str = Field(..., min_length=20, description="Comprehensive investigative conclusion")
    supporting_evidence_ids: List[str] = Field(..., min_length=1)
    counter_evidence_ids: List[str] = Field(default_factory=list)
    unresolved_uncertainty: str = Field(..., min_length=10)
    confidence: ConfidenceLevel
    recommended_next_action: str = Field(..., min_length=15)
    notes: Optional[str] = None


class CriterionScore(BaseModel):
    """Score and feedback for an individual evaluation criterion."""
    criterion_name: str
    points_earned: float
    max_points: float
    reason: str
    actionable_advice: Optional[str] = None


class DecisionEvaluationResult(BaseModel):
    """Complete rubric evaluation result calculated in Python."""
    overall_score: float
    max_score: float = 100.0
    percentage: float
    criteria_breakdown: List[CriterionScore]
    summary_feedback: str
    missing_evidence_ids: List[str] = Field(default_factory=list)
    unsupported_claims: List[str] = Field(default_factory=list)
    identified_conflicts_addressed: int
    total_relevant_conflicts: int


class InvestigationAnswer(BaseModel):
    """Strict structured JSON response from LLM / Q&A Service."""
    answer: str = Field(..., min_length=10, description="Objective, evidence-grounded answer")
    supporting_evidence_ids: List[str] = Field(default_factory=list)
    counter_evidence_ids: List[str] = Field(default_factory=list)
    unknowns: List[str] = Field(default_factory=list)
    recommended_next_step: str = Field(..., min_length=10)
    confidence: ConfidenceLevel = "medium"
