"""
Test suite for LLM failure modes, schema resilience, and citation validation
(Test Requirements 8, 9, 10, and 11).
"""

import pytest
from unittest.mock import patch, MagicMock
from src.database import init_db, save_evidence_record
from src.document_processor import ingest_file
from src.llm_service import LLMService
from config import AVAILABLE_DATA_DIR, RESTRICTED_DATA_DIR


@pytest.fixture
def test_db(tmp_path):
    db_file = tmp_path / "test_llm.db"
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


def test_malformed_llm_json_handled_without_crashing(test_db):
    """
    Requirement 8: Malformed LLM JSON is handled without crashing.
    """
    llm = LLMService(db_path=test_db)
    llm.provider = "openai"
    llm.api_key = "test_key"

    # Mock _call_llm_api to return broken, invalid JSON text
    with patch.object(llm, "_call_llm_api", return_value="This is definitely not JSON { broken syntax"):
        ans = llm.answer_question("What evidence exists for the order?")
        assert ans is not None
        assert isinstance(ans.answer, str)
        assert len(ans.answer) > 10
        assert "fallback" in ans.answer.lower() or "500" in ans.answer


def test_llm_api_failure_triggers_useful_fallback(test_db):
    """
    Requirement 9: LLM API failure (e.g. timeout, connection error) triggers a useful fallback.
    """
    llm = LLMService(db_path=test_db)
    llm.provider = "openai"
    llm.api_key = "test_key"

    # Mock _call_llm_api to raise network exception
    with patch.object(llm, "_call_llm_api", side_effect=Exception("Connection Timeout to LLM Service")):
        ans = llm.answer_question("Does courier tracking prove that all 500 components arrived?")
        assert ans is not None
        assert "E-003" in ans.supporting_evidence_ids or "E-004" in ans.counter_evidence_ids
        assert "fallback" in ans.answer.lower()
        assert "350" in ans.answer or "not" in ans.answer.lower()


def test_invalid_or_unauthorized_citations_are_rejected(test_db):
    """
    Requirement 10: Invalid or unauthorized citations are rejected.
    If LLM returns a hallucinated ID (E-999) or a restricted ID (E-011),
    Python validation strips them out.
    """
    llm = LLMService(db_path=test_db)

    # Fake LLM response containing valid (E-001), hallucinated (E-999), and restricted (E-011)
    fake_llm_output = {
        "answer": "The order was placed for 500 units as per official records.",
        "supporting_evidence_ids": ["E-001", "E-999", "E-011"],
        "counter_evidence_ids": ["E-888"],
        "unknowns": ["Transit verification"],
        "recommended_next_step": "Request courier weight records.",
        "confidence": "high"
    }

    _, valid_evidence_map = llm._get_released_evidence_context()
    validated = llm._validate_and_sanitize_answer(fake_llm_output, valid_evidence_map)

    # Valid E-001 must be preserved
    assert "E-001" in validated.supporting_evidence_ids

    # E-999 (hallucinated) and E-011 (restricted) must be rejected/stripped
    assert "E-999" not in validated.supporting_evidence_ids
    assert "E-011" not in validated.supporting_evidence_ids
    assert "E-888" not in validated.counter_evidence_ids
    assert "Removed unreleased or invalid citations" in validated.answer


def test_insufficient_evidence_results_in_appropriately_qualified_conclusion(test_db):
    """
    Requirement 11: Insufficient evidence results in an appropriately qualified conclusion.
    """
    llm = LLMService(db_path=test_db)
    # Asking to assign blame/responsibility when restricted weight telemetry is unreleased
    ans = llm.answer_question("Who is responsible and committed fraud for the missing items?")

    # Should not assert criminal guilt, must declare unknowns
    assert len(ans.unknowns) >= 1
    assert "not" in ans.answer.lower() or "insufficient" in ans.answer.lower() or "cannot" in ans.answer.lower()
