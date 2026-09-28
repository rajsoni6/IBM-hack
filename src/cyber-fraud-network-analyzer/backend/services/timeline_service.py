"""
services/timeline_service.py

Build a chronological investigation timeline from actual data records.

Event types produced (only when source records exist):
  transaction       — from data/sample/transactions.json
  call              — from data/sample/call_records.json
  sim_event         — from data/sample/sims.json (swaps, issue dates)
  device_association— from data/sample/devices.json
  account_activity  — from data/entities/entities.json (BANK_ACCOUNT entities)
  case_event        — from data/cases/cases.json (open / close)
  evidence_event    — from data/evidence/evidence.json

Schema per event:
  {
    event_id    : str
    timestamp   : ISO-8601 str
    event_type  : str
    entity_ids  : list[str]
    description : str
    source      : str
    evidence_id : str | None
  }
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from config.settings import DATA_DIR
from storage.file_store import read_json

# ── Data file paths (module-level so tests can patch them) ────────────────────
TRANSACTIONS_FILE  = DATA_DIR / "sample"    / "transactions.json"
CALL_RECORDS_FILE  = DATA_DIR / "sample"    / "call_records.json"
SIMS_FILE          = DATA_DIR / "sample"    / "sims.json"
DEVICES_FILE       = DATA_DIR / "sample"    / "devices.json"
ENTITIES_FILE      = DATA_DIR / "entities"  / "entities.json"
EVIDENCE_FILE      = DATA_DIR / "evidence"  / "evidence.json"
CASES_FILE         = DATA_DIR / "cases"     / "cases.json"
SAMPLE_EVIDENCE_FILE = DATA_DIR / "sample"  / "evidence.json"


def _iso(val: Optional[str]) -> Optional[str]:
    """Normalise a timestamp string to bare ISO-8601; return None if invalid."""
    if not val:
        return None
    s = str(val).strip()
    # Some sample data has a trailing 'Z' after '+00:00' — remove duplication
    s = s.replace("+00:00Z", "Z")
    return s if s else None


def _filter_case(records: list[dict], case_id: str) -> list[dict]:
    """Return records that match case_id, or all records if none carry the field."""
    tagged = [r for r in records if r.get("case_id") == case_id]
    return tagged if tagged else records


def _load(primary: Path, fallback: Optional[Path] = None) -> list[dict]:
    data = read_json(primary)
    if isinstance(data, list) and data:
        return data
    if fallback:
        data = read_json(fallback)
        if isinstance(data, list):
            return data
    return []


# ── Event builders ────────────────────────────────────────────────────────────

def _transaction_events(case_id: str) -> list[dict]:
    events: list[dict] = []
    records = _filter_case(
        _load(DATA_DIR / "processed" / case_id / "transactions.json", TRANSACTIONS_FILE),
        case_id,
    )
    for i, tx in enumerate(records):
        ts = _iso(tx.get("timestamp") or tx.get("created_at"))
        if not ts:
            continue
        src = tx.get("src_account") or tx.get("src_id") or ""
        dst = tx.get("dst_account") or tx.get("dst_id") or ""
        amount = tx.get("amount", "")
        method = tx.get("method") or tx.get("payment_method") or ""
        events.append({
            "event_id":    f"evt_tx_{tx.get('id', i)}",
            "timestamp":   ts,
            "event_type":  "transaction",
            "entity_ids":  [e for e in [src, dst] if e],
            "description": (
                f"Transaction {tx.get('id', '')} | "
                f"{src} → {dst} | "
                f"₹{amount:,.2f}" if isinstance(amount, (int, float))
                else f"Transaction {tx.get('id', '')} | {src} → {dst} | {amount}"
            ),
            "source":      "transactions",
            "evidence_id": tx.get("evidence_id"),
        })
    return events


def _call_events(case_id: str) -> list[dict]:
    events: list[dict] = []
    records = _filter_case(
        _load(DATA_DIR / "processed" / case_id / "calls.json", CALL_RECORDS_FILE),
        case_id,
    )
    for i, call in enumerate(records):
        ts = _iso(call.get("timestamp") or call.get("created_at"))
        if not ts:
            continue
        caller   = call.get("caller_id") or call.get("caller") or ""
        receiver = call.get("receiver_id") or call.get("receiver") or ""
        dur      = call.get("duration_sec") or call.get("duration") or ""
        events.append({
            "event_id":    f"evt_call_{call.get('id', i)}",
            "timestamp":   ts,
            "event_type":  "call",
            "entity_ids":  [e for e in [caller, receiver] if e],
            "description": f"Call: {caller} → {receiver} | {dur}s",
            "source":      "call_records",
            "evidence_id": call.get("evidence_id"),
        })
    return events


def _sim_events(case_id: str) -> list[dict]:
    events: list[dict] = []
    records = _filter_case(_load(SIMS_FILE), case_id)
    for i, sim in enumerate(records):
        sim_id = sim.get("id") or f"sim_{i}"
        # Issue event
        issue_date = _iso(sim.get("issue_date") or sim.get("created_at"))
        if issue_date:
            phone = sim.get("phone_id") or ""
            events.append({
                "event_id":    f"evt_sim_issue_{sim_id}",
                "timestamp":   issue_date if len(issue_date) > 10 else issue_date + "T00:00:00Z",
                "event_type":  "sim_event",
                "entity_ids":  [e for e in [sim_id, phone] if e],
                "description": (
                    f"SIM {sim_id} issued | operator: {sim.get('operator', '')} | "
                    f"KYC: {'verified' if sim.get('kyc_verified') else 'unverified'}"
                ),
                "source":      "sims",
                "evidence_id": None,
            })
        # Swap event
        swap_date = _iso(sim.get("last_swap_date"))
        if swap_date and sim.get("swap_count", 0):
            events.append({
                "event_id":    f"evt_sim_swap_{sim_id}",
                "timestamp":   swap_date if len(swap_date) > 10 else swap_date + "T00:00:00Z",
                "event_type":  "sim_event",
                "entity_ids":  [sim_id],
                "description": (
                    f"SIM SWAP detected: {sim_id} | "
                    f"total swaps: {sim.get('swap_count', '')}"
                ),
                "source":      "sims",
                "evidence_id": None,
            })
    return events


def _device_events(case_id: str) -> list[dict]:
    events: list[dict] = []
    records = _filter_case(_load(DEVICES_FILE), case_id)
    for i, dev in enumerate(records):
        dev_id = dev.get("id") or f"dev_{i}"
        first = _iso(dev.get("first_seen") or dev.get("created_at"))
        last  = _iso(dev.get("last_seen"))
        owner = dev.get("registered_to") or ""
        brand = dev.get("brand") or ""
        model = dev.get("model") or ""
        if first:
            events.append({
                "event_id":    f"evt_dev_first_{dev_id}",
                "timestamp":   first if len(first) > 10 else first + "T00:00:00Z",
                "event_type":  "device_association",
                "entity_ids":  [e for e in [dev_id, owner] if e],
                "description": f"Device first seen: {brand} {model} (IMEI: {dev.get('imei', '')}) | owner: {owner}",
                "source":      "devices",
                "evidence_id": None,
            })
        if last and last != first:
            events.append({
                "event_id":    f"evt_dev_last_{dev_id}",
                "timestamp":   last if len(last) > 10 else last + "T00:00:00Z",
                "event_type":  "device_association",
                "entity_ids":  [e for e in [dev_id, owner] if e],
                "description": f"Device last seen: {brand} {model} (IMEI: {dev.get('imei', '')}) | owner: {owner}",
                "source":      "devices",
                "evidence_id": None,
            })
    return events


def _account_events(case_id: str) -> list[dict]:
    events: list[dict] = []
    records = read_json(ENTITIES_FILE) or []
    account_entities = [
        e for e in records
        if e.get("type") == "BANK_ACCOUNT" and
        case_id in (e.get("case_ids") or [e.get("case_id", "")])
    ]
    for i, ent in enumerate(account_entities):
        eid = ent.get("entity_id") or ent.get("id") or f"acc_{i}"
        ts  = _iso(ent.get("extracted_at") or ent.get("created_at"))
        if not ts:
            continue
        events.append({
            "event_id":    f"evt_acc_{eid}",
            "timestamp":   ts,
            "event_type":  "account_activity",
            "entity_ids":  [eid],
            "description": (
                f"Account entity extracted: {ent.get('value', eid)} | "
                f"risk: {ent.get('risk_score', 'N/A')}"
            ),
            "source":      "entities",
            "evidence_id": (ent.get("evidence_ids") or [None])[0],
        })
    return events


def _case_events(case_id: str) -> list[dict]:
    events: list[dict] = []
    cases = read_json(CASES_FILE) or []
    # Also check sample cases for demo
    if not cases:
        cases = read_json(DATA_DIR / "sample" / "cases.json") or []
    case_rec = next(
        (c for c in cases if c.get("id") == case_id or c.get("case_id") == case_id),
        None,
    )
    if not case_rec:
        return []

    opened = _iso(case_rec.get("created_at") or case_rec.get("opened_date"))
    if opened:
        events.append({
            "event_id":    f"evt_case_open_{case_id}",
            "timestamp":   opened if len(opened) > 10 else opened + "T00:00:00Z",
            "event_type":  "case_event",
            "entity_ids":  case_rec.get("victim_ids", []),
            "description": (
                f"Case opened: {case_rec.get('title', case_id)} | "
                f"severity: {case_rec.get('severity', '')} | "
                f"pattern: {case_rec.get('fraud_pattern', '')}"
            ),
            "source":      "cases",
            "evidence_id": None,
        })
    closed = _iso(case_rec.get("closed_at"))
    if closed:
        events.append({
            "event_id":    f"evt_case_close_{case_id}",
            "timestamp":   closed,
            "event_type":  "case_event",
            "entity_ids":  [],
            "description": f"Case closed: {case_rec.get('title', case_id)}",
            "source":      "cases",
            "evidence_id": None,
        })
    return events


def _evidence_events(case_id: str) -> list[dict]:
    events: list[dict] = []
    records = read_json(EVIDENCE_FILE) or []
    if not records:
        records = read_json(SAMPLE_EVIDENCE_FILE) or []
    for ev in records:
        if ev.get("case_id") != case_id:
            continue
        ts = _iso(ev.get("collected_at") or ev.get("created_at"))
        if not ts:
            continue
        events.append({
            "event_id":    f"evt_ev_{ev.get('id', '')}",
            "timestamp":   ts,
            "event_type":  "case_event",
            "entity_ids":  [],
            "description": (
                f"Evidence collected: {ev.get('type', '')} — "
                f"{ev.get('description', '')[:120]}"
            ),
            "source":      "evidence",
            "evidence_id": ev.get("id"),
        })
    return events


# ── Public API ────────────────────────────────────────────────────────────────

def get_timeline(case_id: str) -> list[dict]:
    """
    Return all timeline events for *case_id*, sorted chronologically.
    Only events with a valid timestamp are included.
    """
    all_events: list[dict] = []
    all_events.extend(_transaction_events(case_id))
    all_events.extend(_call_events(case_id))
    all_events.extend(_sim_events(case_id))
    all_events.extend(_device_events(case_id))
    all_events.extend(_account_events(case_id))
    all_events.extend(_case_events(case_id))
    all_events.extend(_evidence_events(case_id))

    # Sort by timestamp string (ISO-8601 lexicographic order works correctly)
    all_events.sort(key=lambda e: e["timestamp"])
    return all_events
