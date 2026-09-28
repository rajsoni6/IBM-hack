"""
routes/summary.py

POST /api/summary/generate/<case_id>
  Generate (or regenerate) an AI investigation summary for the case.

GET /api/summary/<case_id>
  Return the stored summary for the case (404 if not yet generated).
"""

from flask import Blueprint, jsonify
from utils.auth_middleware import require_permission

summary_bp = Blueprint("summary", __name__, url_prefix="/api")


@summary_bp.post("/summary/generate/<case_id>")
@require_permission("write")
def generate_summary(case_id: str):
    from services.ai_summary_service import generate_summary as _generate
    summary = _generate(case_id)
    return jsonify(summary), 200


@summary_bp.get("/summary/<case_id>")
@require_permission("read")
def get_summary(case_id: str):
    from services.ai_summary_service import get_summary as _get_summary
    summary = _get_summary(case_id)
    if summary is None:
        return jsonify({
            "error": f"No summary found for case '{case_id}'. "
                     "POST /api/summary/generate/<case_id> to generate one."
        }), 404
    return jsonify(summary), 200
