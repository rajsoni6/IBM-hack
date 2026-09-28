"""
services/auth_service.py
User authentication and authorisation — file-based (data/users/users.json).
No database. Passwords hashed with bcrypt.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Optional

import bcrypt

from config.settings import DATA_DIR
from storage.file_store import (
    read_json, write_json, append_json_record,
    search_json_records, generate_id, now_iso,
)

USERS_FILE = DATA_DIR / "users" / "users.json"

# ── Role definitions ──────────────────────────────────────────────────────────
ROLES = {"ADMIN", "INVESTIGATOR", "ANALYST", "VIEWER"}

ROLE_PERMISSIONS: dict[str, set[str]] = {
    "ADMIN":        {"read", "write", "delete", "manage_users", "upload"},
    "INVESTIGATOR": {"read", "write", "upload"},
    "ANALYST":      {"read", "upload"},
    "VIEWER":       {"read"},
}


# ── Helpers ───────────────────────────────────────────────────────────────────

def _ensure_users_file() -> None:
    USERS_FILE.parent.mkdir(parents=True, exist_ok=True)
    if not USERS_FILE.exists():
        write_json(USERS_FILE, [])


def _validate_email(email: str) -> bool:
    return bool(re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email))


def _validate_password_strength(password: str) -> list[str]:
    """Return list of unmet password requirements (empty = valid)."""
    errors = []
    if len(password) < 8:
        errors.append("Password must be at least 8 characters")
    if not re.search(r"[A-Z]", password):
        errors.append("Password must contain at least one uppercase letter")
    if not re.search(r"[0-9]", password):
        errors.append("Password must contain at least one digit")
    return errors


def _hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def _check_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))


def _sanitise_user(user: dict) -> dict:
    """Return user dict without the password hash."""
    return {k: v for k, v in user.items() if k != "password_hash"}


# ── Public API ────────────────────────────────────────────────────────────────

def register_user(
    username: str,
    email: str,
    password: str,
    role: str = "VIEWER",
    full_name: str = "",
) -> tuple[dict, str | None]:
    """
    Register a new user.
    Returns (user_dict_without_hash, error_message).
    error_message is None on success.
    """
    _ensure_users_file()

    # Validate inputs
    username = username.strip()
    email    = email.strip().lower()
    role     = role.upper()

    if not username or len(username) < 3:
        return {}, "username must be at least 3 characters"
    if not re.match(r"^[a-zA-Z0-9_.-]+$", username):
        return {}, "username may only contain letters, digits, _, -, ."
    if not _validate_email(email):
        return {}, "Invalid email address"
    if role not in ROLES:
        return {}, f"Invalid role. Must be one of: {', '.join(sorted(ROLES))}"
    pw_errors = _validate_password_strength(password)
    if pw_errors:
        return {}, "; ".join(pw_errors)

    # Check uniqueness
    users: list[dict] = read_json(USERS_FILE) or []
    for u in users:
        if u["username"].lower() == username.lower():
            return {}, "Username already taken"
        if u["email"] == email:
            return {}, "Email already registered"

    user = {
        "id":            generate_id("usr"),
        "username":      username,
        "email":         email,
        "full_name":     full_name.strip(),
        "role":          role,
        "password_hash": _hash_password(password),
        "is_active":     True,
        "created_at":    now_iso(),
        "updated_at":    now_iso(),
        "last_login":    None,
    }
    users.append(user)
    write_json(USERS_FILE, users)
    return _sanitise_user(user), None


def login_user(
    username_or_email: str,
    password: str,
) -> tuple[dict, str | None]:
    """
    Authenticate a user.
    Returns (user_dict_without_hash, error_message).
    """
    _ensure_users_file()
    users: list[dict] = read_json(USERS_FILE) or []
    query = username_or_email.strip().lower()

    user = next(
        (u for u in users
         if u["username"].lower() == query or u["email"] == query),
        None,
    )
    if user is None:
        return {}, "Invalid credentials"
    if not user.get("is_active", True):
        return {}, "Account is disabled"
    if not _check_password(password, user["password_hash"]):
        return {}, "Invalid credentials"

    # Update last_login
    user["last_login"] = now_iso()
    write_json(USERS_FILE, users)
    return _sanitise_user(user), None


def get_user_by_id(user_id: str) -> Optional[dict]:
    _ensure_users_file()
    users: list[dict] = read_json(USERS_FILE) or []
    u = next((u for u in users if u["id"] == user_id), None)
    return _sanitise_user(u) if u else None


def get_user_by_username(username: str) -> Optional[dict]:
    _ensure_users_file()
    users: list[dict] = read_json(USERS_FILE) or []
    u = next((u for u in users if u["username"].lower() == username.lower()), None)
    return _sanitise_user(u) if u else None


def has_permission(user: dict, permission: str) -> bool:
    role = user.get("role", "VIEWER")
    return permission in ROLE_PERMISSIONS.get(role, set())
