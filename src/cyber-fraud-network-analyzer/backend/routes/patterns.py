"""
routes/patterns.py

GET  /api/patterns/<case_id>          — return stored pattern analysis
POST /api/patterns/analyze/<case_id>  — run (or re-run) pattern detection
GET  /api/roles/<case_id>             — return stored role analysis
"""

from flask import Blueprint, jsonify

from services.pattern_service import (
    run_pattern_analysis,
    run_role_analysis,
    get_patterns,
    get_roles,
)
from utils.auth_middleware import require_permission

patterns_bp = Blueprint("patterns", __name__)


# ── GET /api/patterns/<case_id> ───────────────────────────────────────────────

@patterns_bp.get("/api/patterns/<case_id>")
@require_permission("read")
def fetch_patterns(case_id: str):
    """
    Return the most recent pattern-analysis result for a case.
    404 if analysis has not been run yet.
    """
    result = get_patterns(case_id)
    if result is None:
        return jsonify({
            "error": (
                f"No pattern analysis found for case '{case_id}'. "
                f"POST /api/patterns/analyze/{case_id} to run it."
            )
        }), 404
    return jsonify(result), 200


# ── POST /api/patterns/analyze/<case_id> ──────────────────────────────────────

@patterns_bp.post("/api/patterns/analyze/<case_id>")
@require_permission("write")
def analyze_patterns(case_id: str):
    """
    Run (or re-run) fraud pattern detection for a case.
    Persists findings to data/processed/patterns.json.
    """
    try:
        result = run_pattern_analysis(case_id)
        return jsonify(result), 200
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


# ── GET /api/roles/<case_id> ──────────────────────────────────────────────────

@patterns_bp.get("/api/roles/<case_id>")
@require_permission("read")
def fetch_roles(case_id: str):
    """
    Return the most recent network-role analysis for a case.
    If no stored result exists, run analysis on-demand and return it.
    """
    result = get_roles(case_id)
    if result is None:
        # Run on-demand so the GET is useful even before an explicit POST
        try:
            result = run_role_analysis(case_id)
        except Exception as exc:
            return jsonify({"error": str(exc)}), 500
    return jsonify(result), 200
