"""
routes/evidence.py

GET /api/evidence/<case_id>
  Return all evidence records for a case.

GET /api/evidence/<case_id>/<evidence_id>
  Return a single evidence record with the full entity/relationship chain.
"""

from flask import Blueprint, jsonify
from utils.auth_middleware import require_permission

evidence_bp = Blueprint("evidence", __name__, url_prefix="/api")


@evidence_bp.get("/evidence/<case_id>")
@require_permission("read")
def list_evidence(case_id: str):
    from services.evidence_service import list_evidence as _list_evidence
    records = _list_evidence(case_id)
    return jsonify({"case_id": case_id, "evidence": records, "count": len(records)}), 200


@evidence_bp.get("/evidence/<case_id>/<evidence_id>")
@require_permission("read")
def get_evidence(case_id: str, evidence_id: str):
    from services.evidence_service import get_evidence as _get_evidence
    record = _get_evidence(case_id, evidence_id)
    if record is None:
        return jsonify({"error": f"Evidence '{evidence_id}' not found for case '{case_id}'"}), 404
    return jsonify(record), 200
