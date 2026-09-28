"""
routes/ai_extraction.py

POST /api/ai/extract-entities
  — full pipeline: entities + relationships in one call

POST /api/ai/extract-relationships
  — relationships only (entities already extracted / supplied in body)

GET  /api/ai/entities?case_id=<id>
GET  /api/ai/relationships?case_id=<id>
"""

from flask import Blueprint, g, jsonify, request

from ai.schemas import ExtractionRequest
from services.extraction_service import (
    run_extraction,
    run_relationship_extraction,
    get_entities_for_case,
    get_relationships_for_case,
)
from utils.auth_middleware import require_permission
from pydantic import ValidationError

ai_bp = Blueprint("ai", __name__, url_prefix="/api/ai")


# ── POST /api/ai/extract-entities ────────────────────────────────────────────

@ai_bp.post("/extract-entities")
@require_permission("upload")
def extract_entities():
    body = request.get_json(silent=True) or {}

    text = (body.get("text") or "").strip()
    if not text:
        return jsonify({"error": "text is required"}), 400

    try:
        req = ExtractionRequest(
            text               = text,
            case_id            = body.get("case_id"),
            evidence_id        = body.get("evidence_id"),
            source_hint        = body.get("source_hint"),
            max_entities       = int(body.get("max_entities",       100)),
            max_relationships  = int(body.get("max_relationships",  200)),
            min_confidence     = float(body.get("min_confidence",   0.3)),
        )
    except (ValidationError, ValueError) as e:
        return jsonify({"error": str(e)}), 400

    result = run_extraction(req)

    # Serialise Pydantic models to plain dicts
    return jsonify({
        "request_id":            result.request_id,
        "case_id":               result.case_id,
        "evidence_id":           result.evidence_id,
        "provider":              result.provider,
        "model":                 result.model,
        "extracted_at":          result.extracted_at,
        "entities": [
            {
                "entity_id":      e.entity_id,
                "type":           e.type.value,
                "value":          e.value,
                "confidence":     e.confidence,
                "evidence_source": e.evidence_source.value,
                "evidence_id":    e.evidence_id,
                "source_text":    e.source_text,
                "attributes":     e.attributes,
            }
            for e in result.entities
        ],
        "relationships": [
            {
                "relationship_id": r.relationship_id,
                "source_entity":   r.source_entity,
                "relationship":    r.relationship.value,
                "target_entity":   r.target_entity,
                "confidence":      r.confidence,
                "evidence_source": r.evidence_source.value,
                "evidence_id":     r.evidence_id,
                "source_text":     r.source_text,
                "attributes":      r.attributes,
            }
            for r in result.relationships
        ],
        "stats": {
            "new_entities":          result.new_entities,
            "merged_entities":       result.merged_entities,
            "new_relationships":     result.new_relationships,
            "merged_relationships":  result.merged_relationships,
        },
        "warnings": result.warnings,
    }), 201


# ── POST /api/ai/extract-relationships ───────────────────────────────────────

@ai_bp.post("/extract-relationships")
@require_permission("upload")
def extract_relationships():
    body = request.get_json(silent=True) or {}

    text = (body.get("text") or "").strip()
    if not text:
        return jsonify({"error": "text is required"}), 400

    entities = body.get("entities")
    if not isinstance(entities, list) or not entities:
        return jsonify({"error": "entities must be a non-empty list"}), 400

    case_id     = body.get("case_id")
    evidence_id = body.get("evidence_id")
    try:
        min_confidence = float(body.get("min_confidence", 0.3))
    except (TypeError, ValueError):
        return jsonify({"error": "min_confidence must be a float"}), 400

    upserted, new_c, merged_c, warnings = run_relationship_extraction(
        text        = text,
        entities    = entities,
        case_id     = case_id,
        evidence_id = evidence_id,
        min_confidence = min_confidence,
    )

    return jsonify({
        "relationships": [
            {
                "relationship_id": r["relationship_id"],
                "source_entity":   r["source_entity"],
                "relationship":    r["relationship"],
                "target_entity":   r["target_entity"],
                "confidence":      r["confidence"],
                "evidence_source": r["evidence_source"],
                "evidence_id":     r.get("evidence_id"),
            }
            for r in upserted
        ],
        "stats": {
            "new_relationships":    new_c,
            "merged_relationships": merged_c,
        },
        "warnings": warnings,
    }), 201


# ── GET /api/ai/entities ──────────────────────────────────────────────────────

@ai_bp.get("/entities")
@require_permission("read")
def list_entities():
    case_id = request.args.get("case_id", "").strip()
    if not case_id:
        return jsonify({"error": "case_id query parameter is required"}), 400
    entities = get_entities_for_case(case_id)
    return jsonify({"entities": entities, "total": len(entities)}), 200


# ── GET /api/ai/relationships ─────────────────────────────────────────────────

@ai_bp.get("/relationships")
@require_permission("read")
def list_relationships():
    case_id = request.args.get("case_id", "").strip()
    if not case_id:
        return jsonify({"error": "case_id query parameter is required"}), 400
    rels = get_relationships_for_case(case_id)
    return jsonify({"relationships": rels, "total": len(rels)}), 200
