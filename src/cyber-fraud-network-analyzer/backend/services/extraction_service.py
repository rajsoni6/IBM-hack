"""
services/extraction_service.py
Full entity + relationship extraction pipeline.

Flow:
  1. Receive text + context (case_id, evidence_id, …)
  2. Call AI provider → raw entity dicts
  3. Validate + normalise each entity (Pydantic)
  4. Deduplicate against existing stored entities
  5. Persist new / merged entities to data/entities/entities.json
  6. Call AI provider → raw relationship dicts
  7. Resolve source/target to entity_ids
  8. Validate + deduplicate relationships
  9. Persist to data/relationships/relationships.json
 10. Return ExtractionResult

Saves:
  data/entities/entities.json        (canonical entity store)
  data/relationships/relationships.json  (canonical relationship store)
"""

from __future__ import annotations

import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from pydantic import ValidationError

from ai.schemas import (
    EntityType, RelationshipType, EvidenceSource,
    ExtractedEntity, ExtractedRelationship, ExtractionRequest, ExtractionResult,
)
from config.settings import DATA_DIR
from storage.file_store import read_json, write_json

ENTITIES_FILE      = DATA_DIR / "entities"      / "entities.json"
RELATIONSHIPS_FILE = DATA_DIR / "relationships" / "relationships.json"


# ── Normalisation helpers ────────────────────────────────────────────────────

def _clean_phone(v: str) -> str:
    """Normalise phone number to 10-digit string."""
    v = re.sub(r"[\s\-\(\)\+]", "", v)
    if v.startswith("91") and len(v) == 12:
        v = v[2:]
    return v


def _clean_account(v: str) -> str:
    return re.sub(r"\s", "", v)


def _clean_upi(v: str) -> str:
    return v.strip().lower()


def _clean_ip(v: str) -> str:
    return v.strip()


def _clean_name(v: str) -> str:
    return " ".join(v.title().split())


_NORMALISERS: dict[str, Any] = {
    "PHONE":        _clean_phone,
    "BANK_ACCOUNT": _clean_account,
    "UPI_ID":       _clean_upi,
    "IP_ADDRESS":   _clean_ip,
    "PERSON":       _clean_name,
    "VICTIM":       _clean_name,
    "SUSPECT":      _clean_name,
    "IMEI":         lambda v: re.sub(r"\s", "", v),
    "SIM":          lambda v: re.sub(r"\s", "", v),
}


def normalise_entity_value(entity_type: str, raw_value: str) -> str:
    fn = _NORMALISERS.get(entity_type)
    return fn(raw_value) if fn else raw_value.strip()


# ── File I/O helpers ──────────────────────────────────────────────────────────

def _ensure_file(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        write_json(path, [])


def _load_entities() -> list[dict]:
    _ensure_file(ENTITIES_FILE)
    return read_json(ENTITIES_FILE) or []


def _load_relationships() -> list[dict]:
    _ensure_file(RELATIONSHIPS_FILE)
    return read_json(RELATIONSHIPS_FILE) or []


def _save_entities(records: list[dict]) -> None:
    write_json(ENTITIES_FILE, records)


def _save_relationships(records: list[dict]) -> None:
    write_json(RELATIONSHIPS_FILE, records)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _new_entity_id() -> str:
    return "ent_" + uuid.uuid4().hex[:12]


def _new_rel_id() -> str:
    return "rel_" + uuid.uuid4().hex[:12]


# ── Validation ───────────────────────────────────────────────────────────────

VALID_ENTITY_TYPES = {e.value for e in EntityType}
VALID_REL_TYPES    = {r.value for r in RelationshipType}


def _validate_raw_entity(raw: dict, warnings: list[str]) -> Optional[dict]:
    """
    Check and coerce a raw entity dict from the provider.
    Returns cleaned dict or None (invalid / rejected).
    """
    entity_type = str(raw.get("type", "")).upper()
    if entity_type not in VALID_ENTITY_TYPES:
        warnings.append(f"Skipped unknown entity type: {raw.get('type')!r}")
        return None

    raw_value = str(raw.get("raw_value") or raw.get("value") or "").strip()
    if not raw_value:
        warnings.append(f"Skipped entity with empty value (type={entity_type})")
        return None

    value = normalise_entity_value(entity_type, raw_value)
    if not value:
        warnings.append(f"Skipped entity — normalised value is empty (type={entity_type})")
        return None

    try:
        conf = float(raw.get("confidence", 0.5))
        conf = max(0.0, min(1.0, conf))
    except (TypeError, ValueError):
        conf = 0.5

    ev_src = str(raw.get("evidence_source", "observed")).lower()
    if ev_src not in {s.value for s in EvidenceSource}:
        ev_src = "observed"

    return {
        "type":            entity_type,
        "value":           value,
        "raw_value":       raw_value,
        "confidence":      round(conf, 4),
        "source_text":     (raw.get("source_text") or "")[:500],
        "evidence_source": ev_src,
        "attributes":      raw.get("attributes") or {},
    }


def _validate_raw_relationship(raw: dict, warnings: list[str]) -> Optional[dict]:
    rel_type = str(raw.get("relationship", "")).upper()
    if rel_type not in VALID_REL_TYPES:
        warnings.append(f"Skipped unknown relationship type: {raw.get('relationship')!r}")
        return None

    src_val  = str(raw.get("source_value") or "").strip()
    src_type = str(raw.get("source_type")  or "").upper()
    tgt_val  = str(raw.get("target_value") or "").strip()
    tgt_type = str(raw.get("target_type")  or "").upper()

    if not src_val or not tgt_val:
        warnings.append(f"Skipped relationship with empty source/target (rel={rel_type})")
        return None

    if src_type not in VALID_ENTITY_TYPES:
        warnings.append(f"Skipped relationship — unknown source type: {src_type!r}")
        return None
    if tgt_type not in VALID_ENTITY_TYPES:
        warnings.append(f"Skipped relationship — unknown target type: {tgt_type!r}")
        return None

    try:
        conf = float(raw.get("confidence", 0.5))
        conf = max(0.0, min(1.0, conf))
    except (TypeError, ValueError):
        conf = 0.5

    ev_src = str(raw.get("evidence_source", "inferred")).lower()
    if ev_src not in {s.value for s in EvidenceSource}:
        ev_src = "inferred"

    # Normalise source/target values for matching
    src_val_norm = normalise_entity_value(src_type, src_val)
    tgt_val_norm = normalise_entity_value(tgt_type, tgt_val)

    return {
        "relationship":    rel_type,
        "source_value":    src_val_norm,
        "source_type":     src_type,
        "target_value":    tgt_val_norm,
        "target_type":     tgt_type,
        "confidence":      round(conf, 4),
        "source_text":     (raw.get("source_text") or "")[:500],
        "evidence_source": ev_src,
        "attributes":      raw.get("attributes") or {},
    }


# ── Deduplication + persistence ───────────────────────────────────────────────

def upsert_entities(
    validated: list[dict],
    evidence_id: Optional[str],
    case_id: Optional[str],
    now: str,
) -> tuple[list[dict], int, int]:
    """
    Merge validated entities into the entity store.
    Returns (all_upserted, new_count, merged_count).
    Dedup key: (TYPE, normalised_VALUE.upper())
    On collision — keep highest confidence; append new evidence_ids.
    """
    existing = _load_entities()
    index: dict[str, dict] = {
        f"{r['type']}::{r['value'].upper()}": r for r in existing
    }

    upserted: list[dict]  = []
    new_count    = 0
    merged_count = 0

    for v in validated:
        key = f"{v['type']}::{v['value'].upper()}"
        if key in index:
            # Merge: bump confidence if higher, add evidence_id
            existing_rec = index[key]
            merged_count += 1
            if v["confidence"] > existing_rec["confidence"]:
                existing_rec["confidence"] = v["confidence"]
            existing_ids = set(existing_rec.get("evidence_ids") or [])
            if evidence_id:
                existing_ids.add(evidence_id)
            existing_rec["evidence_ids"] = sorted(existing_ids)
            case_ids = set(existing_rec.get("case_ids") or [])
            if case_id:
                case_ids.add(case_id)
            existing_rec["case_ids"] = sorted(case_ids)
            existing_rec["updated_at"] = now
            # Merge source_texts (keep up to 3)
            texts = list(existing_rec.get("source_texts") or [])
            st = v.get("source_text", "")
            if st and st not in texts:
                texts.append(st)
            existing_rec["source_texts"] = texts[:3]
            upserted.append(existing_rec)
        else:
            # New entity
            entity_id = _new_entity_id()
            new_rec = {
                "entity_id":      entity_id,
                "type":           v["type"],
                "value":          v["value"],
                "raw_value":      v["raw_value"],
                "confidence":     v["confidence"],
                "evidence_source": v["evidence_source"],
                "evidence_id":    evidence_id,
                "evidence_ids":   [evidence_id] if evidence_id else [],
                "case_id":        case_id,
                "case_ids":       [case_id] if case_id else [],
                "source_texts":   [v["source_text"]] if v.get("source_text") else [],
                "attributes":     v["attributes"],
                "extracted_at":   now,
                "updated_at":     now,
            }
            index[key] = new_rec
            new_count += 1
            upserted.append(new_rec)

    # Rebuild full list preserving unrelated existing entities
    merged_existing_keys = {
        f"{r['type']}::{r['value'].upper()}"
        for r in upserted if f"{r['type']}::{r['value'].upper()}" in
        {f"{r['type']}::{r['value'].upper()}" for r in existing}
    }
    untouched = [r for r in existing
                 if f"{r['type']}::{r['value'].upper()}" not in
                 {f"{v['type']}::{v['value'].upper()}" for v in validated}]
    _save_entities(untouched + list(index.values()))
    return upserted, new_count, merged_count


def upsert_relationships(
    validated_rels: list[dict],
    entity_index: dict[str, str],   # "TYPE::VALUE" -> entity_id
    evidence_id: Optional[str],
    case_id: Optional[str],
    now: str,
) -> tuple[list[dict], int, int]:
    """
    Merge relationships into the relationship store.
    Returns (all_upserted, new_count, merged_count).
    Dedup key: (source_entity_id, RELATIONSHIP, target_entity_id)
    """
    existing = _load_relationships()
    index: dict[str, dict] = {
        f"{r['source_entity']}::{r['relationship']}::{r['target_entity']}": r
        for r in existing
    }

    upserted:    list[dict] = []
    new_count    = 0
    merged_count = 0
    skipped      = 0

    for v in validated_rels:
        src_key = f"{v['source_type']}::{v['source_value'].upper()}"
        tgt_key = f"{v['target_type']}::{v['target_value'].upper()}"
        src_id  = entity_index.get(src_key)
        tgt_id  = entity_index.get(tgt_key)

        if not src_id or not tgt_id:
            skipped += 1
            continue   # both endpoints must exist

        dedup_key = f"{src_id}::{v['relationship']}::{tgt_id}"

        if dedup_key in index:
            existing_rec = index[dedup_key]
            merged_count += 1
            if v["confidence"] > existing_rec["confidence"]:
                existing_rec["confidence"] = v["confidence"]
            evidence_ids = set(existing_rec.get("evidence_ids") or [])
            if evidence_id:
                evidence_ids.add(evidence_id)
            existing_rec["evidence_ids"] = sorted(evidence_ids)
            case_ids = set(existing_rec.get("case_ids") or [])
            if case_id:
                case_ids.add(case_id)
            existing_rec["case_ids"] = sorted(case_ids)
            existing_rec["updated_at"] = now
            upserted.append(existing_rec)
        else:
            rel_id = _new_rel_id()
            new_rec = {
                "relationship_id":  rel_id,
                "source_entity":    src_id,
                "source_type":      v["source_type"],
                "source_value":     v["source_value"],
                "relationship":     v["relationship"],
                "target_entity":    tgt_id,
                "target_type":      v["target_type"],
                "target_value":     v["target_value"],
                "confidence":       v["confidence"],
                "evidence_source":  v["evidence_source"],
                "evidence_id":      evidence_id,
                "evidence_ids":     [evidence_id] if evidence_id else [],
                "case_id":          case_id,
                "case_ids":         [case_id] if case_id else [],
                "source_text":      v.get("source_text", ""),
                "attributes":       v["attributes"],
                "extracted_at":     now,
                "updated_at":       now,
            }
            index[dedup_key] = new_rec
            new_count += 1
            upserted.append(new_rec)

    untouched = [r for r in existing
                 if f"{r['source_entity']}::{r['relationship']}::{r['target_entity']}"
                 not in {f"{u['source_entity']}::{u['relationship']}::{u['target_entity']}"
                         for u in upserted}]
    _save_relationships(untouched + list(index.values()))
    return upserted, new_count, merged_count


# ── Public pipeline ───────────────────────────────────────────────────────────

def run_extraction(req: ExtractionRequest) -> ExtractionResult:
    """
    Full extraction pipeline. Returns an ExtractionResult.
    Never raises on provider errors — they go into result.warnings.
    """
    from ai.provider import get_provider
    now          = _now_iso()
    request_id   = "req_" + uuid.uuid4().hex[:12]
    provider     = get_provider()
    warnings:    list[str] = []

    context = {
        "case_id":     req.case_id,
        "evidence_id": req.evidence_id,
        "source_hint": req.source_hint,
    }

    # ── 1. Extract entities ───────────────────────────────────────────────
    try:
        raw_entities = provider.extract_entities_raw(req.text, context)
    except Exception as e:
        warnings.append(f"Entity extraction failed: {e}")
        raw_entities = []

    # ── 2. Validate + normalise entities ─────────────────────────────────
    validated_entities: list[dict] = []
    for raw in raw_entities[:req.max_entities]:
        clean = _validate_raw_entity(raw, warnings)
        if clean and clean["confidence"] >= req.min_confidence:
            validated_entities.append(clean)

    # ── 3. Persist entities (dedup + merge) ───────────────────────────────
    upserted_entities, new_ents, merged_ents = upsert_entities(
        validated_entities, req.evidence_id, req.case_id, now
    )

    # ── 4. Build entity index for relationship resolution ─────────────────
    entity_index: dict[str, str] = {
        f"{e['type']}::{e['value'].upper()}": e["entity_id"]
        for e in upserted_entities
    }

    # ── 5. Extract relationships ──────────────────────────────────────────
    try:
        raw_rels = provider.extract_relationships_raw(
            req.text,
            [{"type": e["type"], "value": e["value"], "raw_value": e["raw_value"]}
             for e in upserted_entities],
            context,
        )
    except Exception as e:
        warnings.append(f"Relationship extraction failed: {e}")
        raw_rels = []

    # ── 6. Validate + normalise relationships ─────────────────────────────
    validated_rels: list[dict] = []
    for raw in raw_rels[:req.max_relationships]:
        clean = _validate_raw_relationship(raw, warnings)
        if clean and clean["confidence"] >= req.min_confidence:
            validated_rels.append(clean)

    # ── 7. Persist relationships ──────────────────────────────────────────
    upserted_rels, new_rels, merged_rels = upsert_relationships(
        validated_rels, entity_index, req.evidence_id, req.case_id, now
    )

    # ── 8. Build result ───────────────────────────────────────────────────
    result_entities = []
    for e in upserted_entities:
        result_entities.append(ExtractedEntity(
            entity_id       = e["entity_id"],
            type            = EntityType(e["type"]),
            value           = e["value"],
            raw_value       = e["raw_value"],
            confidence      = e["confidence"],
            evidence_id     = e.get("evidence_id"),
            case_id         = e.get("case_id"),
            source_text     = (e.get("source_texts") or [""])[0],
            evidence_source = EvidenceSource(e["evidence_source"]),
            attributes      = e.get("attributes", {}),
            extracted_at    = e.get("extracted_at"),
        ))

    result_rels = []
    for r in upserted_rels:
        result_rels.append(ExtractedRelationship(
            relationship_id  = r["relationship_id"],
            source_entity    = r["source_entity"],
            relationship     = RelationshipType(r["relationship"]),
            target_entity    = r["target_entity"],
            confidence       = r["confidence"],
            evidence_id      = r.get("evidence_id"),
            case_id          = r.get("case_id"),
            source_text      = r.get("source_text"),
            evidence_source  = EvidenceSource(r["evidence_source"]),
            attributes       = r.get("attributes", {}),
            extracted_at     = r.get("extracted_at"),
        ))

    return ExtractionResult(
        request_id            = request_id,
        case_id               = req.case_id,
        evidence_id           = req.evidence_id,
        entities              = result_entities,
        relationships         = result_rels,
        new_entities          = new_ents,
        merged_entities       = merged_ents,
        new_relationships     = new_rels,
        merged_relationships  = merged_rels,
        provider              = provider.name,
        model                 = provider.model_id,
        extracted_at          = now,
        warnings              = warnings,
    )


# ── Standalone relationship extraction (called from separate endpoint) ────────

def run_relationship_extraction(
    text: str,
    entities: list[dict],
    case_id: Optional[str] = None,
    evidence_id: Optional[str] = None,
    min_confidence: float = 0.3,
) -> tuple[list[dict], int, int, list[str]]:
    """
    Extract and persist relationships for an already-known entity list.
    Returns (upserted_rels, new_count, merged_count, warnings).
    """
    from ai.provider import get_provider
    now      = _now_iso()
    provider = get_provider()
    warnings: list[str] = []

    context = {"case_id": case_id, "evidence_id": evidence_id}
    try:
        raw_rels = provider.extract_relationships_raw(text, entities, context)
    except Exception as e:
        warnings.append(f"Relationship extraction error: {e}")
        return [], 0, 0, warnings

    validated: list[dict] = []
    for raw in raw_rels:
        clean = _validate_raw_relationship(raw, warnings)
        if clean and clean["confidence"] >= min_confidence:
            validated.append(clean)

    # Load existing entities to build index
    existing_entities = _load_entities()
    entity_index = {
        f"{e['type']}::{e['value'].upper()}": e["entity_id"]
        for e in existing_entities
    }

    upserted, new_c, merged_c = upsert_relationships(
        validated, entity_index, evidence_id, case_id, now
    )
    return upserted, new_c, merged_c, warnings


# ── Query helpers ─────────────────────────────────────────────────────────────

def get_entities_for_case(case_id: str) -> list[dict]:
    return [e for e in _load_entities() if case_id in (e.get("case_ids") or [])]


def get_relationships_for_case(case_id: str) -> list[dict]:
    return [r for r in _load_relationships() if case_id in (r.get("case_ids") or [])]


def get_entity_by_id(entity_id: str) -> Optional[dict]:
    return next((e for e in _load_entities() if e["entity_id"] == entity_id), None)
