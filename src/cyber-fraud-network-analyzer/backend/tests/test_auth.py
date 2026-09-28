"""
tests/test_auth.py
Tests for POST /api/auth/register, POST /api/auth/login, GET /api/auth/me
"""

import pytest
from .conftest import register, login, auth_header


# ═══════════════════════════════════════════════════════════════════════════════
# REGISTER
# ═══════════════════════════════════════════════════════════════════════════════

class TestRegister:

    def test_register_success(self, client):
        rv = register(client)
        assert rv.status_code == 201
        data = rv.get_json()
        assert data["user"]["username"] == "testuser"
        assert data["user"]["role"] == "INVESTIGATOR"
        assert "password_hash" not in data["user"]
        assert "token" in data

    def test_register_duplicate_username(self, client):
        register(client, username="dup_user", email="dup1@x.com")
        rv = register(client, username="dup_user", email="dup2@x.com")
        assert rv.status_code == 400
        assert "taken" in rv.get_json()["error"].lower()

    def test_register_duplicate_email(self, client):
        register(client, username="user_alpha", email="shared@x.com")
        rv = register(client, username="user_beta", email="shared@x.com")
        assert rv.status_code == 400
        assert "email" in rv.get_json()["error"].lower()

    def test_register_invalid_email(self, client):
        rv = register(client, username="u_bad_email", email="notanemail")
        assert rv.status_code == 400

    def test_register_weak_password_short(self, client):
        rv = register(client, username="u_short_pw", email="spw@x.com", password="Ab1")
        assert rv.status_code == 400
        assert "8 characters" in rv.get_json()["error"]

    def test_register_weak_password_no_upper(self, client):
        rv = register(client, username="u_no_upper", email="nu@x.com", password="alllower1")
        assert rv.status_code == 400
        assert "uppercase" in rv.get_json()["error"]

    def test_register_weak_password_no_digit(self, client):
        rv = register(client, username="u_no_digit", email="nd@x.com", password="NoDigitsHere")
        assert rv.status_code == 400
        assert "digit" in rv.get_json()["error"]

    def test_register_invalid_role(self, client):
        rv = register(client, username="u_bad_role", email="br@x.com", role="SUPERUSER")
        assert rv.status_code == 400
        assert "role" in rv.get_json()["error"].lower()

    def test_register_missing_username(self, client):
        rv = client.post("/api/auth/register", json={"email": "x@x.com", "password": "Test1234"})
        assert rv.status_code == 400

    def test_register_missing_password(self, client):
        rv = client.post("/api/auth/register", json={"username": "u", "email": "x@x.com"})
        assert rv.status_code == 400

    def test_register_all_roles_accepted(self, client):
        for i, role in enumerate(["ADMIN", "INVESTIGATOR", "ANALYST", "VIEWER"]):
            rv = register(client, username=f"role_user_{i}", email=f"role{i}@x.com", role=role)
            assert rv.status_code == 201, f"Role {role} rejected: {rv.get_json()}"

    def test_register_short_username(self, client):
        rv = register(client, username="ab", email="short@x.com")
        assert rv.status_code == 400


# ═══════════════════════════════════════════════════════════════════════════════
# LOGIN
# ═══════════════════════════════════════════════════════════════════════════════

class TestLogin:

    def test_login_success_by_username(self, client):
        register(client, username="luser", email="login@x.com")
        rv = login(client, "luser")
        assert rv.status_code == 200
        assert "token" in rv.get_json()

    def test_login_success_by_email(self, client):
        register(client, username="euser", email="email_login@x.com")
        rv = login(client, credential="email_login@x.com")
        assert rv.status_code == 200
        assert "token" in rv.get_json()

    def test_login_wrong_password(self, client):
        register(client, username="pw_user", email="pw@x.com")
        rv = client.post("/api/auth/login", json={"username": "pw_user", "password": "WrongPass9"})
        assert rv.status_code == 401
        assert "credentials" in rv.get_json()["error"].lower()

    def test_login_unknown_user(self, client):
        rv = login(client, credential="ghost_user")
        assert rv.status_code == 401

    def test_login_missing_password(self, client):
        rv = client.post("/api/auth/login", json={"username": "anyone"})
        assert rv.status_code == 400

    def test_login_missing_credential(self, client):
        rv = client.post("/api/auth/login", json={"password": "Test1234"})
        assert rv.status_code == 400

    def test_login_returns_user_without_hash(self, client):
        register(client, username="nohash", email="nohash@x.com")
        rv = login(client, "nohash")
        data = rv.get_json()
        assert "password_hash" not in data["user"]


# ═══════════════════════════════════════════════════════════════════════════════
# ME
# ═══════════════════════════════════════════════════════════════════════════════

class TestMe:

    def test_me_authenticated(self, client):
        register(client, username="meuser", email="me@x.com")
        token = login(client, "meuser").get_json()["token"]
        rv = client.get("/api/auth/me", headers=auth_header(token))
        assert rv.status_code == 200
        data = rv.get_json()
        assert data["user"]["username"] == "meuser"
        assert "permissions" in data
        assert isinstance(data["permissions"], list)

    def test_me_no_token(self, client):
        rv = client.get("/api/auth/me")
        assert rv.status_code == 401

    def test_me_invalid_token(self, client):
        rv = client.get("/api/auth/me", headers={"Authorization": "Bearer invalid.token.here"})
        assert rv.status_code == 401

    def test_viewer_permissions(self, client):
        register(client, username="viewer_u", email="viewer@x.com", role="VIEWER")
        token = login(client, "viewer_u").get_json()["token"]
        rv = client.get("/api/auth/me", headers=auth_header(token))
        perms = rv.get_json()["permissions"]
        assert "read" in perms
        assert "write" not in perms
        assert "delete" not in perms

    def test_admin_permissions(self, client):
        register(client, username="admin_u", email="admin@x.com", role="ADMIN")
        token = login(client, "admin_u").get_json()["token"]
        rv = client.get("/api/auth/me", headers=auth_header(token))
        perms = rv.get_json()["permissions"]
        assert "read" in perms
        assert "write" in perms
        assert "delete" in perms
        assert "manage_users" in perms
