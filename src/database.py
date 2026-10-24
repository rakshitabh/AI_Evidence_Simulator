"""
Database persistence layer using SQLite.
Manages persistent state for cases, evidence registry, claims, conflicts,
access control requests, audit logs, and immutable decision attempts.
"""

import sqlite3
import json
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime
from config import DATABASE_PATH

logger = logging.getLogger(__name__)


def get_connection(db_path: Optional[str] = None) -> sqlite3.Connection:
    """Creates a thread-safe connection with row_factory and foreign keys enabled."""
    path = db_path or str(DATABASE_PATH)
    conn = sqlite3.connect(path, timeout=10.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def init_db(db_path: Optional[str] = None) -> None:
    """Initializes the database schema if tables do not exist."""
    with get_connection(db_path) as conn:
        cursor = conn.cursor()

        # 1. Cases table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS cases (
                case_id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                description TEXT,
                order_value REAL,
                status TEXT DEFAULT 'open',
                created_at TEXT NOT NULL
            );
        """)

        # 2. Evidence table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS evidence (
                evidence_id TEXT PRIMARY KEY,
                source_file TEXT NOT NULL,
                source_type TEXT NOT NULL,
                file_hash TEXT UNIQUE NOT NULL,
                page_number INTEGER DEFAULT 1,
                event_date TEXT,
                parties_json TEXT,
                document_title TEXT NOT NULL,
                summary_claim TEXT NOT NULL,
                claim_type TEXT NOT NULL,
                quantity INTEGER,
                amount_inr REAL,
                raw_text TEXT NOT NULL,
                verification_status TEXT NOT NULL,
                access_status TEXT NOT NULL,
                issuing_org TEXT,
                relevance_hint TEXT,
                created_at TEXT NOT NULL
            );
        """)

        # 3. Evidence Claims table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS evidence_claims (
                claim_id TEXT PRIMARY KEY,
                evidence_id TEXT NOT NULL,
                claim_type TEXT NOT NULL,
                event_date TEXT,
                parties_json TEXT,
                quantity INTEGER,
                amount_inr REAL,
                claim_text TEXT NOT NULL,
                verification_status TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY (evidence_id) REFERENCES evidence (evidence_id) ON DELETE CASCADE
            );
        """)

        # 4. Conflicts table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS conflicts (
                conflict_id TEXT PRIMARY KEY,
                conflict_type TEXT NOT NULL,
                description TEXT NOT NULL,
                evidence_ids_json TEXT NOT NULL,
                severity TEXT NOT NULL,
                status TEXT NOT NULL,
                investigative_question TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
        """)

        # 5. Evidence Requests table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS evidence_requests (
                request_id TEXT PRIMARY KEY,
                evidence_id TEXT NOT NULL,
                investigative_reason TEXT NOT NULL,
                status TEXT NOT NULL,
                decision_notes TEXT,
                requested_at TEXT NOT NULL,
                decided_at TEXT,
                FOREIGN KEY (evidence_id) REFERENCES evidence (evidence_id)
            );
        """)

        # 6. Access Audit table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS access_audit (
                audit_id INTEGER PRIMARY KEY AUTOINCREMENT,
                action TEXT NOT NULL,
                evidence_id TEXT NOT NULL,
                actor TEXT NOT NULL,
                reason TEXT NOT NULL,
                metadata_json TEXT,
                timestamp TEXT NOT NULL
            );
        """)

        # 7. Decision Attempts table (Immutable history)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS decision_attempts (
                attempt_id TEXT PRIMARY KEY,
                case_id TEXT NOT NULL,
                attempt_number INTEGER NOT NULL,
                timestamp TEXT NOT NULL,
                conclusion TEXT NOT NULL,
                supporting_ids_json TEXT NOT NULL,
                counter_ids_json TEXT NOT NULL,
                uncertainty TEXT NOT NULL,
                confidence TEXT NOT NULL,
                next_action TEXT NOT NULL,
                notes TEXT,
                total_score REAL NOT NULL,
                max_score REAL NOT NULL,
                percentage REAL NOT NULL,
                breakdown_json TEXT NOT NULL,
                feedback TEXT NOT NULL,
                evidence_snapshot_json TEXT NOT NULL,
                access_snapshot_json TEXT NOT NULL,
                FOREIGN KEY (case_id) REFERENCES cases (case_id)
            );
        """)

        # 8. Decision Evidence Snapshots (Fine-grained mapping)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS decision_evidence_snapshots (
                snapshot_id INTEGER PRIMARY KEY AUTOINCREMENT,
                attempt_id TEXT NOT NULL,
                evidence_id TEXT NOT NULL,
                access_status_at_submission TEXT NOT NULL,
                verification_status_at_submission TEXT NOT NULL,
                FOREIGN KEY (attempt_id) REFERENCES decision_attempts (attempt_id) ON DELETE CASCADE
            );
        """)

        # Indexing for performance
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_evidence_access ON evidence (access_status);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_evidence_type ON evidence (claim_type);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_claims_evidence ON evidence_claims (evidence_id);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_attempts_case ON decision_attempts (case_id, attempt_number);")

        # Seed default case record so foreign keys succeed
        cursor.execute("""
            INSERT OR IGNORE INTO cases (case_id, title, description, order_value, status, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            "NEXUS-CASE-2026-88",
            "Fictional Shipment Discrepancy: Nexus Electronics vs Vertex Semiconductor",
            "Investigation into 150-unit component shortage for PO-2026-8841",
            1800000.0,
            "open",
            datetime.now().isoformat()
        ))

        conn.commit()
        logger.info("Database schema initialized successfully.")


# Database operation helpers
def save_case(case_data: Dict[str, Any], db_path: Optional[str] = None) -> None:
    with get_connection(db_path) as conn:
        conn.execute("""
            INSERT OR REPLACE INTO cases (case_id, title, description, order_value, status, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            case_data["case_id"],
            case_data["title"],
            case_data.get("description", ""),
            case_data.get("order_value", 0.0),
            case_data.get("status", "open"),
            case_data.get("created_at", datetime.now().isoformat())
        ))
        conn.commit()


def save_evidence_record(rec: Dict[str, Any], db_path: Optional[str] = None) -> None:
    parties = json.dumps(rec.get("parties", []))
    with get_connection(db_path) as conn:
        created_at = rec.get("created_at") or datetime.now().isoformat()
        conn.execute("""
            INSERT OR REPLACE INTO evidence (
                evidence_id, source_file, source_type, file_hash, page_number,
                event_date, parties_json, document_title, summary_claim,
                claim_type, quantity, amount_inr, raw_text, verification_status,
                access_status, issuing_org, relevance_hint, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            rec["evidence_id"],
            rec["source_file"],
            rec["source_type"],
            rec["file_hash"],
            rec.get("page_number", 1),
            rec.get("event_date"),
            parties,
            rec["document_title"],
            rec["summary_claim"],
            rec["claim_type"],
            rec.get("quantity"),
            rec.get("amount_inr"),
            rec["raw_text"],
            rec["verification_status"],
            rec["access_status"],
            rec.get("issuing_org"),
            rec.get("relevance_hint"),
            created_at
        ))
        conn.commit()


def get_all_evidence(only_available: bool = False, db_path: Optional[str] = None) -> List[Dict[str, Any]]:
    with get_connection(db_path) as conn:
        query = "SELECT * FROM evidence"
        params = []
        if only_available:
            query += " WHERE access_status = 'available'"
        query += " ORDER BY evidence_id ASC"
        rows = conn.execute(query, params).fetchall()

        results = []
        for r in rows:
            d = dict(r)
            d["parties"] = json.loads(d.get("parties_json") or "[]")
            results.append(d)
        return results


def get_evidence_by_id(evidence_id: str, db_path: Optional[str] = None) -> Optional[Dict[str, Any]]:
    with get_connection(db_path) as conn:
        row = conn.execute("SELECT * FROM evidence WHERE evidence_id = ?", (evidence_id,)).fetchone()
        if not row:
            return None
        d = dict(row)
        d["parties"] = json.loads(d.get("parties_json") or "[]")
        return d


def update_evidence_access(evidence_id: str, new_status: str, db_path: Optional[str] = None) -> bool:
    with get_connection(db_path) as conn:
        cur = conn.execute("UPDATE evidence SET access_status = ? WHERE evidence_id = ?", (new_status, evidence_id))
        conn.commit()
        return cur.rowcount > 0


def log_access_audit(action: str, evidence_id: str, actor: str, reason: str, metadata: Optional[Dict[str, Any]] = None, db_path: Optional[str] = None) -> None:
    meta_json = json.dumps(metadata or {})
    with get_connection(db_path) as conn:
        conn.execute("""
            INSERT INTO access_audit (action, evidence_id, actor, reason, metadata_json, timestamp)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (action, evidence_id, actor, reason, meta_json, datetime.now().isoformat()))
        conn.commit()


def save_access_request(req_data: Dict[str, Any], db_path: Optional[str] = None) -> None:
    with get_connection(db_path) as conn:
        conn.execute("""
            INSERT OR REPLACE INTO evidence_requests (
                request_id, evidence_id, investigative_reason, status, decision_notes, requested_at, decided_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            req_data["request_id"],
            req_data["evidence_id"],
            req_data["investigative_reason"],
            req_data["status"],
            req_data.get("decision_notes"),
            req_data.get("requested_at", datetime.now().isoformat()),
            req_data.get("decided_at")
        ))
        conn.commit()


def get_all_access_requests(db_path: Optional[str] = None) -> List[Dict[str, Any]]:
    with get_connection(db_path) as conn:
        rows = conn.execute("SELECT * FROM evidence_requests ORDER BY requested_at DESC").fetchall()
        return [dict(r) for r in rows]


def get_all_audit_logs(db_path: Optional[str] = None) -> List[Dict[str, Any]]:
    with get_connection(db_path) as conn:
        rows = conn.execute("SELECT * FROM access_audit ORDER BY timestamp DESC").fetchall()
        return [dict(r) for r in rows]


def save_conflicts(conflicts: List[Dict[str, Any]], db_path: Optional[str] = None) -> None:
    with get_connection(db_path) as conn:
        # Clear previous conflicts before inserting freshly detected conflicts
        conn.execute("DELETE FROM conflicts")
        for c in conflicts:
            conn.execute("""
                INSERT OR REPLACE INTO conflicts (
                    conflict_id, conflict_type, description, evidence_ids_json, severity, status, investigative_question, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                c["conflict_id"],
                c["conflict_type"],
                c["description"],
                json.dumps(c.get("evidence_ids", [])),
                c.get("severity", "high"),
                c.get("status", "unresolved"),
                c["investigative_question"],
                c.get("created_at", datetime.now().isoformat())
            ))
        conn.commit()


def get_all_conflicts(db_path: Optional[str] = None) -> List[Dict[str, Any]]:
    with get_connection(db_path) as conn:
        rows = conn.execute("SELECT * FROM conflicts ORDER BY conflict_id ASC").fetchall()
        results = []
        for r in rows:
            d = dict(r)
            d["evidence_ids"] = json.loads(d.get("evidence_ids_json") or "[]")
            results.append(d)
        return results


def save_decision_attempt(attempt: Dict[str, Any], db_path: Optional[str] = None) -> None:
    with get_connection(db_path) as conn:
        conn.execute("""
            INSERT INTO decision_attempts (
                attempt_id, case_id, attempt_number, timestamp, conclusion,
                supporting_ids_json, counter_ids_json, uncertainty, confidence,
                next_action, notes, total_score, max_score, percentage,
                breakdown_json, feedback, evidence_snapshot_json, access_snapshot_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            attempt["attempt_id"],
            attempt["case_id"],
            attempt["attempt_number"],
            attempt["timestamp"],
            attempt["conclusion"],
            json.dumps(attempt.get("supporting_evidence_ids", [])),
            json.dumps(attempt.get("counter_evidence_ids", [])),
            attempt["unresolved_uncertainty"],
            attempt["confidence"],
            attempt["recommended_next_action"],
            attempt.get("notes", ""),
            attempt["total_score"],
            attempt.get("max_score", 100.0),
            attempt["percentage"],
            json.dumps(attempt.get("breakdown", [])),
            attempt["feedback"],
            json.dumps(attempt.get("evidence_snapshot", [])),
            json.dumps(attempt.get("access_snapshot", {}))
        ))

        # Also store snapshot records in decision_evidence_snapshots
        for ev_id, acc_status in attempt.get("access_snapshot", {}).items():
            conn.execute("""
                INSERT INTO decision_evidence_snapshots (
                    attempt_id, evidence_id, access_status_at_submission, verification_status_at_submission
                ) VALUES (?, ?, ?, ?)
            """, (
                attempt["attempt_id"],
                ev_id,
                acc_status,
                attempt.get("status_snapshot", {}).get(ev_id, "unknown")
            ))
        conn.commit()


def get_decision_attempts(case_id: str, db_path: Optional[str] = None) -> List[Dict[str, Any]]:
    with get_connection(db_path) as conn:
        rows = conn.execute("""
            SELECT * FROM decision_attempts
            WHERE case_id = ?
            ORDER BY attempt_number ASC
        """, (case_id,)).fetchall()

        results = []
        for r in rows:
            d = dict(r)
            d["supporting_evidence_ids"] = json.loads(d.get("supporting_ids_json") or "[]")
            d["counter_evidence_ids"] = json.loads(d.get("counter_ids_json") or "[]")
            d["breakdown"] = json.loads(d.get("breakdown_json") or "[]")
            d["evidence_snapshot"] = json.loads(d.get("evidence_snapshot_json") or "[]")
            d["access_snapshot"] = json.loads(d.get("access_snapshot_json") or "{}")
            results.append(d)
        return results


def get_latest_attempt(case_id: str, db_path: Optional[str] = None) -> Optional[Dict[str, Any]]:
    attempts = get_decision_attempts(case_id, db_path)
    return attempts[-1] if attempts else None
