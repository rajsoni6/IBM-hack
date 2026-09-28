"""
services/cases_service.py
Business logic for fraud case management — persisted to data/cases/cases.json.
"""

from __future__ import annotations

from typing import Optional

from config.settings import DATA_DIR
from storage.file_store import (
    read_json, write_json, append_json_record,
    update_json_record, search_json_records,
    generate_id, now_iso,
)

CASES_FILE = DATA_DIR / "cases" / "cases.json"

VALID_STATUSES   = {"open", "under_investigation", "closed", "chargesheeted", "archived"}
VALID_SEVERITIES = {"critical", "high", "medium", "low"}
VALID_PATTERNS   = {
    "sim_swap", "mule_network", "transaction_layering",
    "shared_device", "shared_sim", "communication_hub",
    "rapid_multi_hop", "legitimate", "unknown",
}


def _ensure_file() -> None:
    CASES_FILE.parent.mkdir(parents=True, exist_ok=True)
    if not CASES_FILE.exists():
        write_json(CASES_FILE, [])


# ── Create ────────────────────────────────────────────────────────────────────

def create_case(data: dict, created_by: str) -> tuple[dict, str | None]:
    """
    Create a new case.
    Returns (case_dict, error_message).
    """
    _ensure_file()

    title = (data.get("title") or "").strip()
    if not title:
        return {}, "title is required"
    if len(title) > 300:
        return {}, "title must be 300 characters or fewer"

    severity = (data.get("severity") or "medium").lower()
    if severity not in VALID_SEVERITIES:
        return {}, f"severity must be one of: {', '.join(sorted(VALID_SEVERITIES))}"

    status = (data.get("status") or "open").lower()
    if status not in VALID_STATUSES:
        return {}, f"status must be one of: {', '.join(sorted(VALID_STATUSES))}"

    fraud_pattern = (data.get("fraud_pattern") or "unknown").lower()
    if fraud_pattern not in VALID_PATTERNS:
        return {}, f"fraud_pattern must be one of: {', '.join(sorted(VALID_PATTERNS))}"

    now = now_iso()
    case = {
        "id":              generate_id("case"),
        "title":           title,
        "description":     (data.get("description") or "").strip(),
        "fraud_pattern":   fraud_pattern,
        "severity":        severity,
        "status":          status,
        "jurisdiction":    (data.get("jurisdiction") or "").strip(),
        "assigned_to":     (data.get("assigned_to") or "").strip(),
        "total_loss_inr":  float(data.get("total_loss_inr") or 0),
        "victim_ids":      list(data.get("victim_ids") or []),
        "suspect_ids":     list(data.get("suspect_ids") or []),
        "tags":            list(data.get("tags") or []),
        "created_by":      created_by,
        "created_at":      now,
        "updated_at":      now,
        "closed_at":       None,
    }

    records: list[dict] = read_json(CASES_FILE) or []
    records.append(case)
    write_json(CASES_FILE, records)
    return case, None


# ── List ──────────────────────────────────────────────────────────────────────

def list_cases(
    status: str | None = None,
    severity: str | None = None,
    fraud_pattern: str | None = None,
    assigned_to: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> dict:
    _ensure_file()
    records: list[dict] = read_json(CASES_FILE) or []

    # Filter
    if status:
        records = [r for r in records if r.get("status") == status.lower()]
    if severity:
        records = [r for r in records if r.get("severity") == severity.lower()]
    if fraud_pattern:
        records = [r for r in records if r.get("fraud_pattern") == fraud_pattern.lower()]
    if assigned_to:
        records = [r for r in records if r.get("assigned_to", "").lower() == assigned_to.lower()]

    total = len(records)
    # Sort newest first
    records.sort(key=lambda r: r.get("created_at", ""), reverse=True)
    page = records[offset: offset + limit]

    return {
        "cases":  page,
        "total":  total,
        "limit":  limit,
        "offset": offset,
    }


# ── Get one ───────────────────────────────────────────────────────────────────

def get_case(case_id: str) -> Optional[dict]:
    _ensure_file()
    records: list[dict] = read_json(CASES_FILE) or []
    return next((r for r in records if r["id"] == case_id), None)


# ── Update ────────────────────────────────────────────────────────────────────

UPDATABLE_FIELDS = {
    "title", "description", "fraud_pattern", "severity",
    "status", "jurisdiction", "assigned_to", "total_loss_inr",
    "victim_ids", "suspect_ids", "tags",
}


def update_case(case_id: str, data: dict, updated_by: str) -> tuple[dict, str | None]:
    _ensure_file()
    records: list[dict] = read_json(CASES_FILE) or []
    case = next((r for r in records if r["id"] == case_id), None)

    if case is None:
        return {}, "Case not found"

    updates: dict = {}

    for field in UPDATABLE_FIELDS:
        if field not in data:
            continue
        val = data[field]

        if field == "severity" and val.lower() not in VALID_SEVERITIES:
            return {}, f"severity must be one of: {', '.join(sorted(VALID_SEVERITIES))}"
        if field == "status" and val.lower() not in VALID_STATUSES:
            return {}, f"status must be one of: {', '.join(sorted(VALID_STATUSES))}"
        if field == "fraud_pattern" and val.lower() not in VALID_PATTERNS:
            return {}, f"fraud_pattern must be one of: {', '.join(sorted(VALID_PATTERNS))}"

        if field in ("severity", "status", "fraud_pattern"):
            updates[field] = val.lower()
        elif field in ("victim_ids", "suspect_ids", "tags"):
            updates[field] = list(val)
        elif field == "total_loss_inr":
            updates[field] = float(val)
        else:
            updates[field] = str(val).strip()

    if not updates:
        return {}, "No updatable fields provided"

    now = now_iso()
    updates["updated_at"] = now
    updates["updated_by"] = updated_by

    # Handle close timestamp
    if updates.get("status") == "closed" and not case.get("closed_at"):
        updates["closed_at"] = now

    case.update(updates)
    write_json(CASES_FILE, records)
    return case, None
