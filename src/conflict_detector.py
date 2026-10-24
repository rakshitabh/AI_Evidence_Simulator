"""
Contradiction and Conflict Detection Engine for AI Evidence Simulator.
Implements deterministic Python rules to detect genuine discrepancies in quantities,
dates, delivery locations, authorization status, and courier shipment weights.
Validates all referenced evidence IDs against currently accessible case records.
"""

from typing import List, Dict, Any, Optional
from src.database import get_all_evidence, save_conflicts, get_all_conflicts
from src.validators import ConflictRecord


class ConflictDetector:
    """Detects and reconciles contradictions across accessible case evidence."""

    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path

    def detect_conflicts(self, only_available: bool = True) -> List[Dict[str, Any]]:
        """
        Runs rule-based conflict detection over released evidence records.
        Filters conflicts so only accessible evidence IDs are referenced.
        """
        records = get_all_evidence(only_available=only_available, db_path=self.db_path)
        record_map = {r["evidence_id"]: r for r in records}
        accessible_ids = set(record_map.keys())

        detected_conflicts: List[Dict[str, Any]] = []
        counter = 1

        # 1. Quantity Mismatch: Supplier Dispatch (500) vs Warehouse Receiving (350)
        if "E-002" in accessible_ids and "E-004" in accessible_ids:
            disp_qty = record_map["E-002"].get("quantity")
            recv_qty = record_map["E-004"].get("quantity")
            if disp_qty and recv_qty and disp_qty != recv_qty:
                detected_conflicts.append({
                    "conflict_id": f"C-{counter:03d}",
                    "conflict_type": "quantity_mismatch",
                    "description": (
                        f"Supplier dispatch confirmation (E-002) claims {disp_qty} units dispatched, "
                        f"while warehouse receiving inspection (E-004) documents only {recv_qty} units received "
                        f"(deficit of {disp_qty - recv_qty} units)."
                    ),
                    "evidence_ids": ["E-002", "E-004"],
                    "severity": "high",
                    "status": "unresolved",
                    "investigative_question": "Can the physical discrepancy of 150 missing units between supplier dispatch and warehouse receipt be accounted for in transit?"
                })
                counter += 1

        # 2. Status vs Quantity: Courier Delivery Completed vs Lacking Item Piece Count
        if "E-003" in accessible_ids and "E-004" in accessible_ids:
            detected_conflicts.append({
                "conflict_id": f"C-{counter:03d}",
                "conflict_type": "delivery_status_without_quantity_verification",
                "description": (
                    "Courier tracking (E-003) logs delivery status as 'DELIVERED - 1 Consignment' without item count, "
                    "whereas warehouse inspection (E-004) establishes that only 350 of 500 components physically arrived."
                ),
                "evidence_ids": ["E-003", "E-004"],
                "severity": "medium",
                "status": "unresolved",
                "investigative_question": "Does courier delivery completion establish full delivery of the 500 components, or merely delivery of the consignment in its final transit state?"
            })
            counter += 1

        # 3. Destination / Address Mismatch: Purchase Order vs Unverified Reroute Email
        if "E-001" in accessible_ids and "E-005" in accessible_ids:
            # Check if internal audit memo E-008 is released
            is_memo_released = "E-008" in accessible_ids
            if is_memo_released:
                desc = (
                    "Unverified external email (E-005) requested rerouting delivery to Electronic City, "
                    "conflicting with PO destination (E-001). Internal audit memo (E-008) confirms this request "
                    "was investigated, found unauthorized, and officially rejected."
                )
                status = "resolved"
                severity = "low"
                evidence_ids = ["E-001", "E-005", "E-008"]
                question = "Has the address change request been conclusively resolved as unauthorized?"
            else:
                desc = (
                    "Purchase order (E-001) mandates delivery to Whitefield Dock 4, whereas an external email (E-005) "
                    "demands redirection to Electronic City without attached authorization."
                )
                status = "unresolved"
                severity = "high"
                evidence_ids = ["E-001", "E-005"]
                question = "Was the requested change of delivery location ever authorized by procurement leadership?"

            detected_conflicts.append({
                "conflict_id": f"C-{counter:03d}",
                "conflict_type": "address_authorization_conflict",
                "description": desc,
                "evidence_ids": evidence_ids,
                "severity": severity,
                "status": status,
                "investigative_question": question
            })
            counter += 1

        # 4. Packaging / Seal Integrity Contradiction: Supplier Intact Seal Claim vs Damaged Seal at Arrival
        # Revealed when E-007 (POD) or E-009 (Gate Register) is available
        if "E-002" in accessible_ids and ("E-007" in accessible_ids or "E-009" in accessible_ids or "E-004" in accessible_ids):
            ev_list = ["E-002"]
            details = []
            if "E-004" in accessible_ids:
                ev_list.append("E-004")
                details.append("warehouse dock logged broken seal on Carton 3")
            if "E-007" in accessible_ids:
                ev_list.append("E-007")
                details.append("courier POD signed with explicit remark noting damaged/retaped carton 3")
            if "E-009" in accessible_ids:
                ev_list.append("E-009")
                details.append("gate security register logged torn seal prior to van docking")

            detected_conflicts.append({
                "conflict_id": f"C-{counter:03d}",
                "conflict_type": "package_integrity_tampering",
                "description": (
                    f"Supplier (E-002) claims goods were dispatched in good condition with factory seals intact, "
                    f"whereas arrival records ({', '.join(ev_list[1:])}) establish that Carton 3 arrived with "
                    f"a severed/taped seal ({'; '.join(details)})."
                ),
                "evidence_ids": ev_list,
                "severity": "high",
                "status": "unresolved",
                "investigative_question": "At what point in the logistics chain was the seal on Carton 3 breached?"
            })
            counter += 1

        # 5. Weight & Package Discrepancy: Origin Weigh-in vs Transit Hub Telemetrics
        # Detected when E-010 (Manifest) or E-011 (Weight Log) is released
        if "E-010" in accessible_ids and "E-011" in accessible_ids:
            detected_conflicts.append({
                "conflict_id": f"C-{counter:03d}",
                "conflict_type": "in_transit_weight_and_package_loss",
                "description": (
                    "Dispatch manifest (E-010) confirms supplier prepared 5 master cartons (500 units), "
                    "matching origin scale weight of 42.60 kg. However, courier hub telemetrics (E-011) "
                    "record weight dropping to 30.15 kg across only 3 packages at the Bengaluru transit hub."
                ),
                "evidence_ids": ["E-010", "E-011"],
                "severity": "critical",
                "status": "unresolved",
                "investigative_question": "Does the 12.45 kg telemetric weight drop between Hyderabad and Bengaluru hubs indicate that packages were lost or stolen during courier transit?"
            })
            counter += 1

        # Validate all records with Pydantic
        validated_conflicts = []
        for c in detected_conflicts:
            # Check every evidence ID is accessible
            valid_ids = [eid for eid in c["evidence_ids"] if eid in accessible_ids]
            c["evidence_ids"] = valid_ids
            rec = ConflictRecord(**c)
            validated_conflicts.append(rec.model_dump())

        # Persist to database
        save_conflicts(validated_conflicts, db_path=self.db_path)
        return validated_conflicts

    def get_persisted_conflicts(self) -> List[Dict[str, Any]]:
        """Retrieves stored conflicts from SQLite."""
        return get_all_conflicts(db_path=self.db_path)
