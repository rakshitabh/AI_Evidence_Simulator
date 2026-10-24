"""
Test suite for contradiction detection engine (Test Requirements 1 and 2).
"""

import pytest
from src.conflict_detector import ConflictDetector
from src.database import init_db
from src.document_processor import ingest_all_case_documents


@pytest.fixture(autouse=True)
def setup_database(tmp_path):
    """Initializes test database with synthetic documents."""
    test_db = tmp_path / "test_sim.db"
    init_db(str(test_db))
    # Ingest documents into test_db
    from src.database import save_evidence_record
    # Re-run ingestion pointing to test_db
    from src.document_processor import ingest_file
    from config import AVAILABLE_DATA_DIR, RESTRICTED_DATA_DIR

    for p in AVAILABLE_DATA_DIR.glob("*.*"):
        if p.suffix.lower() in [".pdf", ".eml"]:
            rec = ingest_file(p, default_access="available")
            if rec:
                save_evidence_record(rec, db_path=str(test_db))

    for p in RESTRICTED_DATA_DIR.glob("*.*"):
        if p.suffix.lower() in [".pdf", ".eml"]:
            rec = ingest_file(p, default_access="restricted")
            if rec:
                save_evidence_record(rec, db_path=str(test_db))

    return str(test_db)


def test_conflicting_quantities_identifies_both_valid_source_ids(setup_database):
    """
    Requirement 1: Two documents report conflicting quantities or dates;
    the conflict identifies both valid source IDs (E-002 and E-004).
    """
    db_path = setup_database
    detector = ConflictDetector(db_path=db_path)
    conflicts = detector.detect_conflicts(only_available=True)

    # Locate quantity mismatch conflict
    qty_conflicts = [c for c in conflicts if c["conflict_type"] == "quantity_mismatch"]
    assert len(qty_conflicts) >= 1, "Must detect quantity mismatch conflict"

    c = qty_conflicts[0]
    assert "E-002" in c["evidence_ids"], "Conflict must reference Supplier Dispatch E-002"
    assert "E-004" in c["evidence_ids"], "Conflict must reference Warehouse Report E-004"
    assert c["severity"] == "high"
    assert c["status"] == "unresolved"


def test_courier_delivery_status_without_quantity_not_treated_as_full_delivery(setup_database):
    """
    Requirement 2: A delivery record confirms delivery status but provides no quantity;
    the system must not conclude that all 500 units arrived.
    """
    db_path = setup_database
    detector = ConflictDetector(db_path=db_path)
    conflicts = detector.detect_conflicts(only_available=True)

    status_conflicts = [
        c for c in conflicts if c["conflict_type"] == "delivery_status_without_quantity_verification"
    ]
    assert len(status_conflicts) >= 1, "Must flag delivery status without itemized quantity"

    c = status_conflicts[0]
    assert "E-003" in c["evidence_ids"]
    assert "E-004" in c["evidence_ids"]
    assert "without" in c["description"].lower() or "not" in c["description"].lower()
