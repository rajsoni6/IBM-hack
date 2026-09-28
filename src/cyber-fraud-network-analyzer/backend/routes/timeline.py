"""
routes/timeline.py

GET /api/timeline/<case_id>
  Return all timeline events for a case, sorted chronologically.
"""

from flask import Blueprint, jsonify
from utils.auth_middleware import require_permission

timeline_bp = Blueprint("timeline", __name__, url_prefix="/api")


@timeline_bp.get("/timeline/<case_id>")
@require_permission("read")
def get_timeline(case_id: str):
    from services.timeline_service import get_timeline as _get_timeline
    events = _get_timeline(case_id)
    return jsonify({"case_id": case_id, "events": events, "count": len(events)}), 200
