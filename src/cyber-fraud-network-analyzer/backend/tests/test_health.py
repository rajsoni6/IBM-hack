"""
tests/test_health.py
Simple smoke test for the /api/health endpoint.
Run: pytest tests/
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import pytest
from app import create_app


@pytest.fixture
def client():
    app = create_app()
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


def test_health_returns_200(client):
    resp = client.get("/api/health")
    assert resp.status_code == 200


def test_health_status_ok(client):
    data = resp = client.get("/api/health").get_json()
    assert data["status"] == "ok"


def test_health_has_required_keys(client):
    data = client.get("/api/health").get_json()
    for key in ("status", "service", "version", "environment", "ai_provider",
                "data_dir", "phase", "phases_complete", "phases_pending"):
        assert key in data, f"Missing key: {key}"
