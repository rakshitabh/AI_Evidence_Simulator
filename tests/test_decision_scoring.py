"""
Test suite for decision submission, deterministic rubric evaluation,
immutable attempt history, and snapshot isolation (Test Requirements 12, 13, 14, and 16).
"""

import pytest
from src.database import init_db, save_evidence_record, get_decision_attempts
from src.document_processor import ingest_file
from src.access_control import AccessControlService
from src.decision_evaluator import DecisionEvaluator
from src.validators import DecisionSubmission
from config import AVAILABLE_DATA_DIR, RESTRICTED_DATA_DIR, CASE_ID


@pytest.fixture
def test_db(tmp_path):
    db_file = tmp_path / "test_eval.db"
    init_db(str(db_file))

    for p in AVAILABLE_DATA_DIR.glob("*.*"):
        if p.suffix.lower() in [".pdf", ".eml"]:
            rec = ingest_file(p, default_access="available")
            if rec:
                save_evidence_record(rec, db_path=str(db_file))

    for p in RESTRICTED_DATA_DIR.glob("*.*"):
        if p.suffix.lower() in [".pdf", ".eml"]:
            rec = ingest_file(p, default_access="restricted")
            if rec:
                save_evidence_record(rec, db_path=str(db_file))

    return str(db_file)


def test_decision_submission_is_saved_and_retrieved(test_db):
    """
    Requirement 12: A decision submission is saved and can be retrieved.
    """
    evaluator = DecisionEvaluator(db_path=test_db)
    sub = DecisionSubmission(
        case_id=CASE_ID,
        overall_conclusion="The available records confirm 500 units were dispatched (E-002), but warehouse inspection (E-004) documented only 350 units received.",
        supporting_evidence_ids=["E-001", "E-002"],
        counter_evidence_ids=["E-004"],
        unresolved_uncertainty="The exact point of transit failure remains unverified.",
        confidence="medium",
        recommended_next_action="Request courier transit weight records and gate registers."
    )

    eval_result, attempt_record = evaluator.evaluate_submission(sub)

    assert eval_result.overall_score >= 0.0
    assert attempt_record["attempt_id"] is not None

    # Retrieve from DB
    history = evaluator.get_history(CASE_ID)
    assert len(history) == 1
    assert history[0]["attempt_id"] == attempt_record["attempt_id"]
    assert history[0]["conclusion"] == sub.overall_conclusion


def test_revising_decision_creates_new_attempt_without_overwriting(test_db):
    """
    Requirement 13: Revising a decision creates a new attempt without overwriting the previous attempt.
    """
    evaluator = DecisionEvaluator(db_path=test_db)

    # First attempt
    sub1 = DecisionSubmission(
        case_id=CASE_ID,
        overall_conclusion="Initial assessment: 500 components were claimed dispatched but only 350 arrived.",
        supporting_evidence_ids=["E-002"],
        counter_evidence_ids=["E-004"],
        unresolved_uncertainty="Delivery address change is unverified.",
        confidence="low",
        recommended_next_action="Inspect courier proof of delivery slip."
    )
    _, att1 = evaluator.evaluate_submission(sub1)

    # Revised attempt
    sub2 = DecisionSubmission(
        case_id=CASE_ID,
        overall_conclusion="Revised assessment: The 150-unit deficit represents a physical shortfall between dispatch E-002 and dock inspection E-004.",
        supporting_evidence_ids=["E-001", "E-002"],
        counter_evidence_ids=["E-004", "E-003"],
        unresolved_uncertainty="Tampered packaging indicates in-transit breach.",
        confidence="high",
        recommended_next_action="Conduct telemetric scale review."
    )
    _, att2 = evaluator.evaluate_submission(sub2)

    history = evaluator.get_history(CASE_ID)
    assert len(history) == 2, "Both attempts must exist in history"
    assert history[0]["attempt_number"] == 1
    assert history[1]["attempt_number"] == 2
    assert history[0]["attempt_id"] != history[1]["attempt_id"]
    assert history[0]["conclusion"] == sub1.overall_conclusion
    assert history[1]["conclusion"] == sub2.overall_conclusion


def test_scores_calculated_by_python_remain_within_bounds(test_db):
    """
    Requirement 14: Scores are calculated by Python and remain within the defined bounds (0 to 100).
    """
    evaluator = DecisionEvaluator(db_path=test_db)
    sub = DecisionSubmission(
        case_id=CASE_ID,
        overall_conclusion="Comprehensive inquiry into 150 unit shortage between supplier 500 and warehouse 350.",
        supporting_evidence_ids=["E-001", "E-002"],
        counter_evidence_ids=["E-004"],
        unresolved_uncertainty="Packaging seal breach details pending.",
        confidence="medium",
        recommended_next_action="Perform joint audit with carrier."
    )
    eval_result, _ = evaluator.evaluate_submission(sub)

    assert 0.0 <= eval_result.overall_score <= 100.0
    assert eval_result.max_score == 100.0
    for crit in eval_result.criteria_breakdown:
        assert 0.0 <= crit.points_earned <= crit.max_points


def test_earlier_decisions_retain_original_evidence_snapshots_after_new_releases(test_db):
    """
    Requirement 16: Previously submitted decisions retain their original evidence snapshots
    after new records are released.
    """
    evaluator = DecisionEvaluator(db_path=test_db)
    ac = AccessControlService(db_path=test_db)

    # 1. Submit attempt 1 while E-011 is restricted
    sub1 = DecisionSubmission(
        case_id=CASE_ID,
        overall_conclusion="Preliminary review before requesting courier weight log.",
        supporting_evidence_ids=["E-001"],
        counter_evidence_ids=["E-004"],
        unresolved_uncertainty="Transit weight remains unknown.",
        confidence="low",
        recommended_next_action="Request E-011 weight log."
    )
    _, att1 = evaluator.evaluate_submission(sub1)

    # Verify attempt 1 snapshot records E-011 as restricted
    assert att1["access_snapshot"]["E-011"] == "restricted"

    # 2. Now unlock/release E-011
    success, _ = ac.evaluate_request(
        "E-011",
        "We need to examine the conveyor scales and transit hub gross weight telemetry to check for mass loss in transit."
    )
    assert success, "E-011 unlock must succeed"

    # 3. Retrieve attempt 1 from database and verify its snapshot is still 'restricted'
    history = evaluator.get_history(CASE_ID)
    att1_reloaded = history[0]

    assert att1_reloaded["access_snapshot"]["E-011"] == "restricted", (
        "Historical attempt snapshot must preserve original access status 'restricted', even after subsequent release."
    )
