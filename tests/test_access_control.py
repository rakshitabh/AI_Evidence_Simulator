"""
Test suite for access control and restricted evidence boundaries
(Test Requirements 3, 4, 5, and 6).
"""

import pytest
from src.access_control import AccessControlService
from src.database import init_db, get_evidence_by_id, get_all_evidence
from src.document_processor import ingest_file
from src.llm_service import LLMService
from config import AVAILABLE_DATA_DIR, RESTRICTED_DATA_DIR


@pytest.fixture
def test_db(tmp_path):
    """Initializes isolated database for access control tests."""
    db_file = tmp_path / "test_access.db"
    init_db(str(db_file))

    from src.database import save_evidence_record

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


def test_nonexistent_evidence_id_rejected_safely(test_db):
    """
    Requirement 3: A nonexistent evidence ID is rejected safely.
    """
    ac = AccessControlService(db_path=test_db)
    success, message = ac.evaluate_request(
        evidence_id="E-999",
        investigative_reason="This is a detailed reason requesting a completely non-existent evidence record."
    )
    assert not success, "Must reject non-existent ID"
    assert "does not exist" in message.lower() or "invalid" in message.lower()


def test_hidden_record_cannot_be_retrieved_in_llm_context_before_release(test_db):
    """
    Requirement 4: A hidden record cannot be retrieved or included in an LLM request before release.
    """
    # E-011 is restricted initially
    rec_e011 = get_evidence_by_id("E-011", db_path=test_db)
    assert rec_e011 is not None
    assert rec_e011["access_status"] == "restricted"

    llm = LLMService(db_path=test_db)
    context, valid_map = llm._get_released_evidence_context()

    # Verify E-011 is strictly absent from context and manifest
    assert "E-011" not in valid_map, "E-011 must not be in valid released evidence map"
    assert "COURIER_WEIGHT_LOG" not in context, "Restricted file content must not leak into LLM context"
    assert "Exc-transit-loss" not in context.lower(), "Internal restricted keywords must not appear"


def test_valid_request_with_sufficient_reason_releases_record(test_db):
    """
    Requirement 5: A valid request with a sufficient reason follows the configured approval policy
    and releases the record only after authorization.
    """
    ac = AccessControlService(db_path=test_db)

    # Initial state: E-007 is restricted
    initial_rec = get_evidence_by_id("E-007", db_path=test_db)
    assert initial_rec["access_status"] == "restricted"

    # Submit valid, substantive request with domain keywords
    reason = (
        "We need to inspect the courier proof of delivery slip and recipient signature "
        "at Dock 4 to verify carton condition and handover details upon arrival."
    )
    success, message = ac.evaluate_request("E-007", reason)
    assert success, f"Expected approval, got message: {message}"
    assert "Access Approved" in message

    # Verify access status is updated to available in DB
    updated_rec = get_evidence_by_id("E-007", db_path=test_db)
    assert updated_rec["access_status"] == "available"


def test_insufficient_reason_rejected_without_exposing_contents(test_db):
    """
    Requirement 6: An insufficient reason is rejected without exposing document contents.
    """
    ac = AccessControlService(db_path=test_db)

    # Short reason that fails minimum length and relevance
    weak_reason = "I want this file now."
    success, message = ac.evaluate_request("E-011", weak_reason)

    assert not success, "Must reject insufficient reason"
    assert "Insufficient" in message or "too brief" in message

    # Verify record remains restricted
    rec = get_evidence_by_id("E-011", db_path=test_db)
    assert rec["access_status"] == "restricted"

    # Verify message does NOT contain restricted document contents
    assert "42.60 kg" not in message
    assert "30.15 kg" not in message
    assert "EXC-TRANSIT-LOSS" not in message
