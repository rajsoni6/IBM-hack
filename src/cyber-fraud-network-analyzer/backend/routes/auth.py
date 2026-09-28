"""
routes/auth.py
POST /api/auth/register
POST /api/auth/login
GET  /api/auth/me
"""

from flask import Blueprint, g, jsonify, request

from services.auth_service import register_user, login_user, ROLES, ROLE_PERMISSIONS
from utils.auth_middleware import create_access_token, login_required
from utils.audit import log_audit

auth_bp = Blueprint("auth", __name__, url_prefix="/api/auth")


def _ip() -> str:
    return request.remote_addr or "unknown"


# ── POST /api/auth/register ───────────────────────────────────────────────────

@auth_bp.post("/register")
def register():
    body = request.get_json(silent=True) or {}

    username  = body.get("username", "").strip()
    email     = body.get("email", "").strip()
    password  = body.get("password", "")
    role      = body.get("role", "VIEWER").upper()
    full_name = body.get("full_name", "").strip()

    if not username:
        return jsonify({"error": "username is required"}), 400
    if not email:
        return jsonify({"error": "email is required"}), 400
    if not password:
        return jsonify({"error": "password is required"}), 400

    user, err = register_user(username, email, password, role, full_name)
    if err:
        log_audit(
            action="user.register",
            user=username,
            status="failure",
            metadata={"error": err, "email": email},
            ip_address=_ip(),
        )
        return jsonify({"error": err}), 400

    log_audit(
        action="user.register",
        user=user["username"],
        user_id=user["id"],
        status="success",
        metadata={"role": user["role"], "email": email},
        ip_address=_ip(),
    )
    token = create_access_token(user["id"], user["role"])
    return jsonify({
        "message": "User registered successfully",
        "user":    user,
        "token":   token,
    }), 201


# ── POST /api/auth/login ──────────────────────────────────────────────────────

@auth_bp.post("/login")
def login():
    body = request.get_json(silent=True) or {}

    credential = body.get("username") or body.get("email") or ""
    password   = body.get("password", "")

    if not credential:
        return jsonify({"error": "username or email is required"}), 400
    if not password:
        return jsonify({"error": "password is required"}), 400

    user, err = login_user(credential, password)
    if err:
        log_audit(
            action="user.login",
            user=credential,
            status="failure",
            metadata={"error": err},
            ip_address=_ip(),
        )
        return jsonify({"error": err}), 401

    log_audit(
        action="user.login",
        user=user["username"],
        user_id=user["id"],
        status="success",
        metadata={"role": user["role"]},
        ip_address=_ip(),
    )
    token = create_access_token(user["id"], user["role"])
    return jsonify({
        "message": "Login successful",
        "user":    user,
        "token":   token,
    }), 200


# ── GET /api/auth/me ──────────────────────────────────────────────────────────

@auth_bp.get("/me")
@login_required
def me():
    user = g.current_user
    return jsonify({
        "user":        user,
        "permissions": sorted(ROLE_PERMISSIONS.get(user.get("role", "VIEWER"), set())),
    }), 200
