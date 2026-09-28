"""
utils/audit.py
Audit log writer — writes structured records to data/audit/audit_logs.json.

Schema per record:
  id          — unique audit entry id
  timestamp   — ISO-8601 UTC
  user        — username of the actor (or "system")
  user_id     — user id of the actor
  action      — e.g. "user.login", "case.create", "file.upload"
  case_id     — the fraud case this action relates to (may be None)
  entity_id   — the primary entity operated on (may be None)
  status      — "success" | "failure"
  metadata    — free-form dict with additional context
  ip_address  — remote IP (from Flask request, if available)
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from config.settings import DATA_DIR

AUDIT_DIR  = DATA_DIR / "audit"
AUDIT_FILE = AUDIT_DIR / "audit_logs.json"

_MAX_RECORDS = 50_000   # rotate when file exceeds this count


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _load() -> list[dict]:
    if not AUDIT_FILE.exists():
        return []
    try:
        return json.loads(AUDIT_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []


def _save(records: list[dict]) -> None:
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_FILE.write_text(
        json.dumps(records, indent=2, default=str),
        encoding="utf-8",
    )


def log_audit(
    action:    str,
    user:      str           = "system",
    user_id:   str           = "",
    case_id:   str | None    = None,
    entity_id: str | None    = None,
    status:    str           = "success",
    metadata:  dict[str, Any] | None = None,
    ip_address: str | None   = None,
) -> dict:
    """
    Append one audit record.  Returns the record.
    Never raises — write failures are swallowed so they never break the caller.
    """
    record: dict[str, Any] = {
        "id":         "aud_" + uuid.uuid4().hex[:12],
        "timestamp":  _now_iso(),
        "user":       user,
        "user_id":    user_id,
        "action":     action,
        "case_id":    case_id,
        "entity_id":  entity_id,
        "status":     status,
        "metadata":   metadata or {},
        "ip_address": ip_address,
    }
    try:
        records = _load()
        # Simple rotation: drop oldest half when limit hit
        if len(records) >= _MAX_RECORDS:
            records = records[_MAX_RECORDS // 2 :]
        records.append(record)
        _save(records)
    except Exception:   # pragma: no cover
        pass
    return record


def get_audit_logs(
    user:      str | None    = None,
    action:    str | None    = None,
    case_id:   str | None    = None,
    limit:     int           = 100,
    offset:    int           = 0,
) -> list[dict]:
    """Return audit records, newest-first, with optional filters."""
    records = list(reversed(_load()))
    if user:
        records = [r for r in records if r.get("user") == user]
    if action:
        records = [r for r in records if r.get("action", "").startswith(action)]
    if case_id:
        records = [r for r in records if r.get("case_id") == case_id]
    return records[offset : offset + limit]
