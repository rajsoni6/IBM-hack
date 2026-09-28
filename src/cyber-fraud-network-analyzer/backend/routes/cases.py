"""
routes/cases.py
POST /api/cases
GET  /api/cases
GET  /api/cases/<case_id>
PUT  /api/cases/<case_id>
"""

from flask import Blueprint, g, jsonify, request

from services.cases_service import (
    create_case, list_cases, get_case, update_case,
)
from utils.auth_middleware import login_required, require_permission
from utils.audit import log_audit

cases_bp = Blueprint("cases", __name__, url_prefix="/api/cases")


# ── POST /api/cases ───────────────────────────────────────────────────────────

@cases_bp.post("/")
@require_permission("write")
def create():
    body = request.get_json(silent=True) or {}
    case, err = create_case(body, created_by=g.current_user["id"])
    if err:
        log_audit(
            action="case.create",
            user=g.current_user.get("username", ""),
            user_id=g.current_user.get("id", ""),
            status="failure",
            metadata={"error": err},
            ip_address=request.remote_addr,
        )
        return jsonify({"error": err}), 400
    log_audit(
        action="case.create",
        user=g.current_user.get("username", ""),
        user_id=g.current_user.get("id", ""),
        case_id=case["id"],
        status="success",
        metadata={"title": case.get("title"), "fraud_pattern": case.get("fraud_pattern")},
        ip_address=request.remote_addr,
    )
    return jsonify({"message": "Case created", "case": case}), 201


# ── GET /api/cases ────────────────────────────────────────────────────────────

@cases_bp.get("/")
@require_permission("read")
def list_all():
    status        = request.args.get("status")
    severity      = request.args.get("severity")
    fraud_pattern = request.args.get("fraud_pattern")
    assigned_to   = request.args.get("assigned_to")

    try:
        limit  = int(request.args.get("limit",  100))
        offset = int(request.args.get("offset", 0))
    except ValueError:
        return jsonify({"error": "limit and offset must be integers"}), 400

    limit  = min(max(limit,  1), 500)
    offset = max(offset, 0)

    result = list_cases(
        status=status,
        severity=severity,
        fraud_pattern=fraud_pattern,
        assigned_to=assigned_to,
        limit=limit,
        offset=offset,
    )
    return jsonify(result), 200


# ── GET /api/cases/<case_id> ──────────────────────────────────────────────────

@cases_bp.get("/<case_id>")
@require_permission("read")
def get_one(case_id: str):
    case = get_case(case_id)
    if case is None:
        return jsonify({"error": f"Case '{case_id}' not found"}), 404
    return jsonify({"case": case}), 200


# ── PUT /api/cases/<case_id> ──────────────────────────────────────────────────

@cases_bp.put("/<case_id>")
@require_permission("write")
def update(case_id: str):
    body = request.get_json(silent=True) or {}
    case, err = update_case(case_id, body, updated_by=g.current_user["id"])
    if err:
        status_code = 404 if "not found" in err.lower() else 400
        log_audit(
            action="case.update",
            user=g.current_user.get("username", ""),
            user_id=g.current_user.get("id", ""),
            case_id=case_id,
            status="failure",
            metadata={"error": err},
            ip_address=request.remote_addr,
        )
        return jsonify({"error": err}), status_code
    log_audit(
        action="case.update",
        user=g.current_user.get("username", ""),
        user_id=g.current_user.get("id", ""),
        case_id=case_id,
        status="success",
        metadata={"fields_updated": list(body.keys())},
        ip_address=request.remote_addr,
    )
    return jsonify({"message": "Case updated", "case": case}), 200
