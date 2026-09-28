"""
utils/auth_middleware.py
JWT helpers and Flask request decorators for authentication / authorisation.
"""

from __future__ import annotations

import functools
from datetime import datetime, timedelta, timezone
from typing import Optional

import jwt
from flask import current_app, g, jsonify, request

from services.auth_service import get_user_by_id

# ── Token helpers ─────────────────────────────────────────────────────────────

ACCESS_TOKEN_TTL_HOURS = 12


def _secret() -> str:
    return current_app.secret_key  # type: ignore[return-value]


def create_access_token(user_id: str, role: str) -> str:
    payload = {
        "sub":  user_id,
        "role": role,
        "iat":  datetime.now(timezone.utc),
        "exp":  datetime.now(timezone.utc) + timedelta(hours=ACCESS_TOKEN_TTL_HOURS),
    }
    return jwt.encode(payload, _secret(), algorithm="HS256")


def decode_access_token(token: str) -> Optional[dict]:
    try:
        return jwt.decode(token, _secret(), algorithms=["HS256"])
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None


def _extract_token() -> Optional[str]:
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        return auth_header[7:]
    return None


# ── Decorators ────────────────────────────────────────────────────────────────

def login_required(f):
    """Require a valid JWT. Injects current user into flask.g.current_user."""
    @functools.wraps(f)
    def wrapper(*args, **kwargs):
        token = _extract_token()
        if not token:
            return jsonify({"error": "Authentication required"}), 401

        payload = decode_access_token(token)
        if payload is None:
            return jsonify({"error": "Token is invalid or expired"}), 401

        user = get_user_by_id(payload["sub"])
        if user is None or not user.get("is_active", True):
            return jsonify({"error": "User not found or disabled"}), 401

        g.current_user = user
        return f(*args, **kwargs)

    return wrapper


def require_permission(permission: str):
    """Require login + specific permission. Must be used after @login_required."""
    def decorator(f):
        @functools.wraps(f)
        def wrapper(*args, **kwargs):
            token = _extract_token()
            if not token:
                return jsonify({"error": "Authentication required"}), 401

            payload = decode_access_token(token)
            if payload is None:
                return jsonify({"error": "Token is invalid or expired"}), 401

            user = get_user_by_id(payload["sub"])
            if user is None or not user.get("is_active", True):
                return jsonify({"error": "User not found or disabled"}), 401

            g.current_user = user

            from services.auth_service import has_permission, ROLE_PERMISSIONS
            if not has_permission(user, permission):
                return jsonify({
                    "error": "Insufficient permissions",
                    "required": permission,
                    "your_role": user.get("role"),
                }), 403

            return f(*args, **kwargs)
        return wrapper
    return decorator


def require_role(*roles: str):
    """Require login + one of the specified roles."""
    def decorator(f):
        @functools.wraps(f)
        def wrapper(*args, **kwargs):
            token = _extract_token()
            if not token:
                return jsonify({"error": "Authentication required"}), 401

            payload = decode_access_token(token)
            if payload is None:
                return jsonify({"error": "Token is invalid or expired"}), 401

            user = get_user_by_id(payload["sub"])
            if user is None or not user.get("is_active", True):
                return jsonify({"error": "User not found or disabled"}), 401

            g.current_user = user

            if user.get("role") not in roles:
                return jsonify({
                    "error": "Insufficient role",
                    "required_one_of": list(roles),
                    "your_role": user.get("role"),
                }), 403

            return f(*args, **kwargs)
        return wrapper
    return decorator
