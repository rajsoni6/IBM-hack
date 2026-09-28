"""
routes/intelligence.py
POST /api/intelligence/upload
"""

from flask import Blueprint, g, jsonify, request

from services.intelligence_service import ingest_file, VALID_RECORD_TYPES
from utils.auth_middleware import require_permission
from utils.audit import log_audit

intelligence_bp = Blueprint("intelligence", __name__, url_prefix="/api/intelligence")


@intelligence_bp.post("/upload")
@require_permission("upload")
def upload():
    # ── Validate request structure ────────────────────────────────────────
    if "file" not in request.files:
        return jsonify({"error": "No file part in request. Send as multipart/form-data with key 'file'"}), 400

    file = request.files["file"]
    if not file or not file.filename:
        return jsonify({"error": "No file selected"}), 400

    case_id = (request.form.get("case_id") or "").strip()
    if not case_id:
        return jsonify({"error": "case_id is required as a form field"}), 400

    record_type_hint = (request.form.get("record_type") or "").strip().lower() or None
    if record_type_hint and record_type_hint not in VALID_RECORD_TYPES:
        return jsonify({
            "error":   f"Unknown record_type '{record_type_hint}'",
            "allowed": sorted(VALID_RECORD_TYPES),
        }), 400

    # ── Read content ──────────────────────────────────────────────────────
    content = file.read()

    # ── Delegate to service ───────────────────────────────────────────────
    result = ingest_file(
        filename         = file.filename,
        content          = content,
        case_id          = case_id,
        uploaded_by      = g.current_user["id"],
        record_type_hint = record_type_hint,
    )

    if not result.get("success"):
        log_audit(
            action="file.upload",
            user=g.current_user.get("username", ""),
            user_id=g.current_user.get("id", ""),
            case_id=case_id,
            status="failure",
            metadata={
                "filename": result.get("filename"),
                "errors": result.get("errors", []),
            },
            ip_address=request.remote_addr,
        )
        return jsonify({
            "error":    "Upload failed",
            "details":  result.get("errors", []),
            "filename": result.get("filename"),
        }), 422

    log_audit(
        action="file.upload",
        user=g.current_user.get("username", ""),
        user_id=g.current_user.get("id", ""),
        case_id=case_id,
        entity_id=result.get("evidence_id"),
        status="success",
        metadata={
            "filename":    result.get("filename"),
            "record_type": result.get("record_type"),
            "normalised":  result.get("normalised"),
            "total_rows":  result.get("total_rows"),
        },
        ip_address=request.remote_addr,
    )
    return jsonify({
        "message":      "File ingested successfully",
        **{k: v for k, v in result.items() if k != "success"},
    }), 201
