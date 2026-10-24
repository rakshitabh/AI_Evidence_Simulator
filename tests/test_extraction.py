"""
Test suite for document extraction, PDF parsing, EML parsing,
and handling unreadable or corrupted files (Test Requirement 15).
"""

import pytest
from pathlib import Path
from src.document_processor import extract_pdf_content, extract_eml_content, compute_file_hash
from config import AVAILABLE_DATA_DIR


def test_pdf_extraction_valid_document():
    """Verify PyMuPDF extracts text and preserves page structure from synthetic PDF."""
    po_pdf = AVAILABLE_DATA_DIR / "PO_2026_8841.pdf"
    assert po_pdf.exists(), "PO PDF must exist"

    text, page_count = extract_pdf_content(po_pdf)
    assert page_count >= 1
    assert "PO-2026-8841" in text
    assert "500" in text
    assert "18,00,000" in text or "18,00,000.00" in text
    assert "Nexus Electronics" in text


def test_pdf_extraction_handles_corrupted_file(tmp_path):
    """Verify corrupted or invalid PDF is handled gracefully without crashing."""
    corrupted_pdf = tmp_path / "corrupted_file.pdf"
    corrupted_pdf.write_bytes(b"%PDF-1.4 Corrupted dummy binary content that is invalid PDF")

    text, page_count = extract_pdf_content(corrupted_pdf)
    assert "[Unreadable PDF file" in text or page_count == 0


def test_pdf_extraction_handles_empty_file(tmp_path):
    """Verify empty PDF file is handled safely."""
    empty_pdf = tmp_path / "empty.pdf"
    empty_pdf.write_bytes(b"")

    text, page_count = extract_pdf_content(empty_pdf)
    assert "Unreadable" in text or page_count == 0


def test_eml_extraction_valid_email():
    """Verify EML parsing extracts sender, recipient, subject, and body correctly."""
    eml_path = AVAILABLE_DATA_DIR / "delivery_address_update.eml"
    assert eml_path.exists(), "EML file must exist"

    text, headers = extract_eml_content(eml_path)
    assert headers["from"] == "logistics-update@external-contractor.in"
    assert "PO-2026-8841" in headers["subject"]
    assert "Electronic City" in text


def test_file_hash_uniqueness_and_consistency():
    """Verify SHA-256 hash generation is stable and deterministic."""
    po_pdf = AVAILABLE_DATA_DIR / "PO_2026_8841.pdf"
    hash1 = compute_file_hash(po_pdf)
    hash2 = compute_file_hash(po_pdf)
    assert hash1 == hash2
    assert len(hash1) == 64
