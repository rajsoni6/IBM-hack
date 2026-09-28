"""
services/evidence_service.py

Load and query evidence records.

Each evidence record follows the schema:
  {
    evidence_id   : str
    source_file   : str
    source_record : dict | str
    timestamp     : str
    entities      : list[str]
    relationships : list[str]
    description   : str
    # additional fields from the raw record
  }

Chain maintained:
  Finding → Evidence → Source Record → Entities → Relationships
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from config.settings import DATA_DIR
from storage.file_store import read_json

# ── File paths ────────────────────────────────────────────────────────────────
EVIDENCE_FILE        = DATA_DIR / "evidence" / "evidence.json"
SAMPLE_EVIDENCE_FILE = DATA_DIR / "sample"   / "evidence.json"
ENTITIES_FILE        = DATA_DIR / "entities" / "entities.json"
RELATIONSHIPS_FILE   = DATA_DIR / "relationships" / "relationships.json"


def _load_evidence_raw() -> list[dict]:
    """Load evidence from live store, falling back to sample data."""
    live = read_json(EVIDENCE_FILE) or []
    if isinstance(live, list) and live:
        return live
    sample = read_json(SAMPLE_EVIDENCE_FILE) or []
    return sample if isinstance(sample, list) else []


def _normalise(record: dict) -> dict:
    """
    Normalise a raw evidence record to the canonical schema.
    Handles both the live intelligence_service format and the sample format.
    """
    eid = record.get("evidence_id") or record.get("id") or ""
    ts  = (
        record.get("timestamp")
        or record.get("collected_at")
        or record.get("created_at")
        or ""
    )
    entities      = record.get("entities")      or record.get("entity_ids")      or []
    relationships = record.get("relationships") or record.get("relationship_ids") or []
    source_file   = (
        record.get("source_file")
        or record.get("file_path")
        or record.get("type")
        or ""
    )
    source_record = record.get("source_record") or record.get("raw") or {}

    return {
        "evidence_id":    eid,
        "case_id":        record.get("case_id", ""),
        "source_file":    source_file,
        "source_record":  source_record,
        "timestamp":      ts,
        "entities":       entities if isinstance(entities, list) else [entities],
        "relationships":  relationships if isinstance(relationships, list) else [relationships],
        "description":    record.get("description", ""),
        "type":           record.get("type", ""),
        "collected_by":   record.get("collected_by", ""),
        "is_verified":    record.get("is_verified", False),
        "hash_sha256":    record.get("hash_sha256", ""),
        # Keep all original fields too
        **{k: v for k, v in record.items() if k not in {
            "evidence_id", "id", "case_id", "source_file", "source_record",
            "timestamp", "entities", "relationships", "description", "type",
            "collected_by", "is_verified", "hash_sha256",
        }},
    }


def _build_chain(ev: dict) -> dict:
    """
    Enrich an evidence record with entity + relationship detail for the chain view.

    Chain:
      evidence → entity records → relationship records
    """
    entities_raw = read_json(ENTITIES_FILE) or []
    rels_raw     = read_json(RELATIONSHIPS_FILE) or []

    entity_index = {e.get("entity_id") or e.get("id"): e for e in entities_raw}
    rel_index    = {r.get("relationship_id") or r.get("id"): r for r in rels_raw}

    entity_ids = ev.get("entities", [])
    rel_ids    = ev.get("relationships", [])

    chain = {
        **ev,
        "chain": {
            "evidence":      ev,
            "entities":      [entity_index[eid] for eid in entity_ids if eid in entity_index],
            "relationships": [rel_index[rid] for rid in rel_ids if rid in rel_index],
        },
    }
    return chain


# ── Public API ────────────────────────────────────────────────────────────────

def list_evidence(case_id: str) -> list[dict]:
    """Return all evidence records for a case, normalised."""
    raw = _load_evidence_raw()
    return [
        _normalise(r) for r in raw
        if r.get("case_id") == case_id
    ]


def get_evidence(case_id: str, evidence_id: str) -> Optional[dict]:
    """
    Return a single evidence record with the full entity/relationship chain.
    Returns None if not found.
    """
    raw = _load_evidence_raw()
    record = next(
        (r for r in raw
         if (r.get("evidence_id") or r.get("id")) == evidence_id
         and r.get("case_id") == case_id),
        None,
    )
    if record is None:
        return None
    return _build_chain(_normalise(record))
