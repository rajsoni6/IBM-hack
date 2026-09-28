"""
tests/test_cases.py
Tests for POST /api/cases, GET /api/cases, GET /api/cases/<id>, PUT /api/cases/<id>
"""

import pytest
from .conftest import register, login, auth_header


def get_token(client, role="INVESTIGATOR"):
    uname = f"case_user_{role.lower()}"
    email = f"{uname}@x.com"
    register(client, username=uname, email=email, role=role)
    return login(client, uname).get_json()["token"]


VALID_CASE = {
    "title":         "Test fraud case",
    "description":   "A test description",
    "fraud_pattern": "sim_swap",
    "severity":      "high",
    "status":        "open",
    "jurisdiction":  "Mumbai",
    "assigned_to":   "IO-Test",
    "total_loss_inr": 50000,
}


# ═══════════════════════════════════════════════════════════════════════════════
# CREATE
# ═══════════════════════════════════════════════════════════════════════════════

class TestCreateCase:

    def test_create_success(self, client):
        token = get_token(client)
        rv = client.post("/api/cases/", json=VALID_CASE, headers=auth_header(token))
        assert rv.status_code == 201
        data = rv.get_json()
        assert "case" in data
        assert data["case"]["title"] == "Test fraud case"
        assert data["case"]["fraud_pattern"] == "sim_swap"
        assert data["case"]["id"].startswith("case_")
        assert "created_at" in data["case"]

    def test_create_requires_auth(self, client):
        rv = client.post("/api/cases/", json=VALID_CASE)
        assert rv.status_code == 401

    def test_create_viewer_forbidden(self, client):
        token = get_token(client, role="VIEWER")
        rv = client.post("/api/cases/", json=VALID_CASE, headers=auth_header(token))
        assert rv.status_code == 403

    def test_create_missing_title(self, client):
        token = get_token(client)
        rv = client.post("/api/cases/", json={"severity": "high"}, headers=auth_header(token))
        assert rv.status_code == 400
        assert "title" in rv.get_json()["error"].lower()

    def test_create_invalid_severity(self, client):
        token = get_token(client)
        body = {**VALID_CASE, "severity": "nuclear"}
        rv = client.post("/api/cases/", json=body, headers=auth_header(token))
        assert rv.status_code == 400
        assert "severity" in rv.get_json()["error"].lower()

    def test_create_invalid_status(self, client):
        token = get_token(client)
        body = {**VALID_CASE, "status": "pending"}
        rv = client.post("/api/cases/", json=body, headers=auth_header(token))
        assert rv.status_code == 400

    def test_create_invalid_fraud_pattern(self, client):
        token = get_token(client)
        body = {**VALID_CASE, "fraud_pattern": "alien_attack"}
        rv = client.post("/api/cases/", json=body, headers=auth_header(token))
        assert rv.status_code == 400

    def test_create_all_severities(self, client):
        token = get_token(client)
        for sev in ("critical", "high", "medium", "low"):
            body = {**VALID_CASE, "severity": sev, "title": f"Case {sev}"}
            rv = client.post("/api/cases/", json=body, headers=auth_header(token))
            assert rv.status_code == 201, f"severity={sev}: {rv.get_json()}"

    def test_create_stores_created_by(self, client):
        token = get_token(client)
        rv = client.post("/api/cases/", json=VALID_CASE, headers=auth_header(token))
        case = rv.get_json()["case"]
        assert "created_by" in case
        assert case["created_by"]  # non-empty user id


# ═══════════════════════════════════════════════════════════════════════════════
# LIST
# ═══════════════════════════════════════════════════════════════════════════════

class TestListCases:

    def _create_n(self, client, token, n: int):
        for i in range(n):
            client.post("/api/cases/", json={**VALID_CASE, "title": f"Case {i}"}, headers=auth_header(token))

    def test_list_empty(self, client):
        token = get_token(client)
        rv = client.get("/api/cases/", headers=auth_header(token))
        assert rv.status_code == 200
        data = rv.get_json()
        assert "cases" in data
        assert isinstance(data["cases"], list)

    def test_list_returns_created(self, client):
        token = get_token(client)
        self._create_n(client, token, 3)
        rv = client.get("/api/cases/", headers=auth_header(token))
        data = rv.get_json()
        assert data["total"] >= 3

    def test_list_filter_by_severity(self, client):
        token = get_token(client)
        client.post("/api/cases/", json={**VALID_CASE, "title": "Crit case", "severity": "critical"}, headers=auth_header(token))
        client.post("/api/cases/", json={**VALID_CASE, "title": "Low case", "severity": "low"}, headers=auth_header(token))
        rv = client.get("/api/cases/?severity=critical", headers=auth_header(token))
        cases = rv.get_json()["cases"]
        assert all(c["severity"] == "critical" for c in cases)

    def test_list_filter_by_status(self, client):
        token = get_token(client)
        client.post("/api/cases/", json={**VALID_CASE, "title": "Open case"}, headers=auth_header(token))
        rv = client.get("/api/cases/?status=open", headers=auth_header(token))
        cases = rv.get_json()["cases"]
        assert all(c["status"] == "open" for c in cases)

    def test_list_pagination(self, client):
        token = get_token(client)
        self._create_n(client, token, 5)
        rv = client.get("/api/cases/?limit=2&offset=0", headers=auth_header(token))
        data = rv.get_json()
        assert len(data["cases"]) <= 2
        assert data["limit"] == 2

    def test_list_requires_auth(self, client):
        rv = client.get("/api/cases/")
        assert rv.status_code == 401

    def test_list_invalid_limit(self, client):
        token = get_token(client)
        rv = client.get("/api/cases/?limit=abc", headers=auth_header(token))
        assert rv.status_code == 400


# ═══════════════════════════════════════════════════════════════════════════════
# GET ONE
# ═══════════════════════════════════════════════════════════════════════════════

class TestGetCase:

    def test_get_existing(self, client):
        token = get_token(client)
        case_id = client.post("/api/cases/", json=VALID_CASE, headers=auth_header(token)).get_json()["case"]["id"]
        rv = client.get(f"/api/cases/{case_id}", headers=auth_header(token))
        assert rv.status_code == 200
        assert rv.get_json()["case"]["id"] == case_id

    def test_get_not_found(self, client):
        token = get_token(client)
        rv = client.get("/api/cases/case_nonexistent", headers=auth_header(token))
        assert rv.status_code == 404

    def test_get_requires_auth(self, client):
        rv = client.get("/api/cases/case_anything")
        assert rv.status_code == 401


# ═══════════════════════════════════════════════════════════════════════════════
# UPDATE
# ═══════════════════════════════════════════════════════════════════════════════

class TestUpdateCase:

    def test_update_title(self, client):
        token = get_token(client)
        case_id = client.post("/api/cases/", json=VALID_CASE, headers=auth_header(token)).get_json()["case"]["id"]
        rv = client.put(f"/api/cases/{case_id}", json={"title": "Updated title"}, headers=auth_header(token))
        assert rv.status_code == 200
        assert rv.get_json()["case"]["title"] == "Updated title"

    def test_update_status_to_closed(self, client):
        token = get_token(client)
        case_id = client.post("/api/cases/", json=VALID_CASE, headers=auth_header(token)).get_json()["case"]["id"]
        rv = client.put(f"/api/cases/{case_id}", json={"status": "closed"}, headers=auth_header(token))
        case = rv.get_json()["case"]
        assert case["status"] == "closed"
        assert case["closed_at"] is not None

    def test_update_sets_updated_by(self, client):
        token = get_token(client)
        case_id = client.post("/api/cases/", json=VALID_CASE, headers=auth_header(token)).get_json()["case"]["id"]
        rv = client.put(f"/api/cases/{case_id}", json={"title": "New"}, headers=auth_header(token))
        assert "updated_by" in rv.get_json()["case"]

    def test_update_invalid_severity(self, client):
        token = get_token(client)
        case_id = client.post("/api/cases/", json=VALID_CASE, headers=auth_header(token)).get_json()["case"]["id"]
        rv = client.put(f"/api/cases/{case_id}", json={"severity": "extreme"}, headers=auth_header(token))
        assert rv.status_code == 400

    def test_update_not_found(self, client):
        token = get_token(client)
        rv = client.put("/api/cases/case_nonexistent", json={"title": "x"}, headers=auth_header(token))
        assert rv.status_code == 404

    def test_update_no_fields_provided(self, client):
        token = get_token(client)
        case_id = client.post("/api/cases/", json=VALID_CASE, headers=auth_header(token)).get_json()["case"]["id"]
        rv = client.put(f"/api/cases/{case_id}", json={}, headers=auth_header(token))
        assert rv.status_code == 400

    def test_update_requires_auth(self, client):
        rv = client.put("/api/cases/case_anything", json={"title": "x"})
        assert rv.status_code == 401

    def test_update_viewer_forbidden(self, client):
        inv_token  = get_token(client, role="INVESTIGATOR")
        viewer_token = get_token(client, role="VIEWER")
        case_id = client.post("/api/cases/", json=VALID_CASE, headers=auth_header(inv_token)).get_json()["case"]["id"]
        rv = client.put(f"/api/cases/{case_id}", json={"title": "x"}, headers=auth_header(viewer_token))
        assert rv.status_code == 403
