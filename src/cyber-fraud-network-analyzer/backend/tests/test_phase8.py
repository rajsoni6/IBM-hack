"""
tests/test_phase8.py

Tests for Phase 8 endpoints:
  - GET  /api/timeline/<case_id>
  - GET  /api/evidence/<case_id>
  - GET  /api/evidence/<case_id>/<evidence_id>
  - POST /api/summary/generate/<case_id>
  - GET  /api/summary/<case_id>
"""

import json
from pathlib import Path

import pytest

from .conftest import register, login, auth_header


CASE_ID = "case_ph8_test"

# ── Sample data fixtures ──────────────────────────────────────────────────────

SAMPLE_TRANSACTIONS = [
    {
        "id": "txn_ph8_001",
        "src_account": "acc_001",
        "dst_account": "acc_002",
        "amount": 50000.0,
        "currency": "INR",
        "method": "IMPS",
        "narration": "Fund transfer",
        "timestamp": "2024-01-10T09:00:00Z",
        "case_id": CASE_ID,
        "risk_score": 0.8,
        "flagged": True,
    }
]

SAMPLE_CALLS = [
    {
        "id": "call_ph8_001",
        "caller_id": "ph_001",
        "receiver_id": "ph_002",
        "duration_sec": 120,
        "call_type": "outgoing",
        "timestamp": "2024-01-10T10:00:00Z",
        "case_id": CASE_ID,
    }
]

SAMPLE_CASES = [
    {
        "id": CASE_ID,
        "title": "Phase 8 Test Case",
        "fraud_pattern": "mule_network",
        "severity": "high",
        "status": "open",
        "total_loss_inr": 150000.0,
        "victim_ids": ["vic_001"],
        "assigned_to": "IO-Test",
        "jurisdiction": "Mumbai",
        "created_at": "2024-01-01T00:00:00Z",
    }
]

SAMPLE_EVIDENCE = [
    {
        "id": "ev_ph8_001",
        "case_id": CASE_ID,
        "type": "bank_statement",
        "description": "Bank statement for account ACC001 showing suspicious transfers",
        "file_path": "raw/statement.pdf",
        "collected_by": "IO-Test",
        "collected_at": "2024-01-11T08:00:00Z",
        "hash_sha256": "abc123",
        "is_verified": True,
        "created_at": "2024-01-11T08:00:00Z",
    }
]


@pytest.fixture(autouse=True)
def seed_phase8_data(isolated_data_dir):
    """Write minimal test data to the temp directory."""
    tmp = isolated_data_dir

    def _write(path: Path, data):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    _write(tmp / "sample" / "transactions.json", SAMPLE_TRANSACTIONS)
    _write(tmp / "sample" / "call_records.json", SAMPLE_CALLS)
    _write(tmp / "sample" / "sims.json", [])
    _write(tmp / "sample" / "devices.json", [])
    _write(tmp / "sample" / "evidence.json", SAMPLE_EVIDENCE)
    _write(tmp / "cases" / "cases.json", SAMPLE_CASES)
    _write(tmp / "evidence" / "evidence.json", SAMPLE_EVIDENCE)
    _write(tmp / "entities" / "entities.json", [])
    _write(tmp / "relationships" / "relationships.json", [])
    (tmp / "reports").mkdir(parents=True, exist_ok=True)


def _get_token(client, username="ph8_user"):
    email = f"{username}@example.com"
    register(client, username=username, email=email)
    r = login(client, credential=username)
    data = r.get_json()
    return data.get("token") or data.get("access_token")


# ═══════════════════════════════════════════════════════════════════════════════
# Timeline
# ═══════════════════════════════════════════════════════════════════════════════

class TestTimeline:
    def test_get_timeline_200(self, client):
        token = _get_token(client, "timeline_user1")
        r = client.get(f"/api/timeline/{CASE_ID}", headers=auth_header(token))
        assert r.status_code == 200

    def test_get_timeline_response_structure(self, client):
        token = _get_token(client, "timeline_user2")
        r = client.get(f"/api/timeline/{CASE_ID}", headers=auth_header(token))
        data = r.get_json()
        assert "case_id" in data
        assert "events" in data
        assert "count" in data
        assert isinstance(data["events"], list)

    def test_get_timeline_has_transactions(self, client):
        token = _get_token(client, "timeline_user3")
        r = client.get(f"/api/timeline/{CASE_ID}", headers=auth_header(token))
        data = r.get_json()
        tx_events = [e for e in data["events"] if e["event_type"] == "transaction"]
        assert len(tx_events) >= 1

    def test_get_timeline_has_call_events(self, client):
        token = _get_token(client, "timeline_user4")
        r = client.get(f"/api/timeline/{CASE_ID}", headers=auth_header(token))
        data = r.get_json()
        call_events = [e for e in data["events"] if e["event_type"] == "call"]
        assert len(call_events) >= 1

    def test_get_timeline_events_sorted(self, client):
        token = _get_token(client, "timeline_user5")
        r = client.get(f"/api/timeline/{CASE_ID}", headers=auth_header(token))
        events = r.get_json()["events"]
        timestamps = [e["timestamp"] for e in events]
        assert timestamps == sorted(timestamps)

    def test_get_timeline_event_schema(self, client):
        token = _get_token(client, "timeline_user6")
        r = client.get(f"/api/timeline/{CASE_ID}", headers=auth_header(token))
        for ev in r.get_json()["events"]:
            assert "event_id"   in ev
            assert "timestamp"  in ev
            assert "event_type" in ev
            assert "entity_ids" in ev
            assert "description" in ev
            assert "source" in ev

    def test_get_timeline_unknown_case_returns_200(self, client):
        """An unknown case returns 200 with a list (may have global SIM/device events)."""
        token = _get_token(client, "timeline_user7")
        r = client.get("/api/timeline/no_such_case_xyz", headers=auth_header(token))
        assert r.status_code == 200
        data = r.get_json()
        assert "events" in data
        assert isinstance(data["events"], list)

    def test_get_timeline_requires_auth(self, client):
        r = client.get(f"/api/timeline/{CASE_ID}")
        assert r.status_code == 401


# ═══════════════════════════════════════════════════════════════════════════════
# Evidence
# ═══════════════════════════════════════════════════════════════════════════════

class TestEvidence:
    def test_list_evidence_200(self, client):
        token = _get_token(client, "ev_user1")
        r = client.get(f"/api/evidence/{CASE_ID}", headers=auth_header(token))
        assert r.status_code == 200

    def test_list_evidence_structure(self, client):
        token = _get_token(client, "ev_user2")
        r = client.get(f"/api/evidence/{CASE_ID}", headers=auth_header(token))
        data = r.get_json()
        assert "case_id"  in data
        assert "evidence" in data
        assert "count"    in data
        assert isinstance(data["evidence"], list)

    def test_list_evidence_returns_records(self, client):
        token = _get_token(client, "ev_user3")
        r = client.get(f"/api/evidence/{CASE_ID}", headers=auth_header(token))
        data = r.get_json()
        assert data["count"] >= 1

    def test_list_evidence_record_schema(self, client):
        token = _get_token(client, "ev_user4")
        r = client.get(f"/api/evidence/{CASE_ID}", headers=auth_header(token))
        for ev in r.get_json()["evidence"]:
            assert "evidence_id"  in ev
            assert "description"  in ev

    def test_get_single_evidence_200(self, client):
        token = _get_token(client, "ev_user5")
        r = client.get(f"/api/evidence/{CASE_ID}/ev_ph8_001", headers=auth_header(token))
        assert r.status_code == 200

    def test_get_single_evidence_has_chain(self, client):
        token = _get_token(client, "ev_user6")
        r = client.get(f"/api/evidence/{CASE_ID}/ev_ph8_001", headers=auth_header(token))
        data = r.get_json()
        assert "chain" in data

    def test_get_evidence_not_found_404(self, client):
        token = _get_token(client, "ev_user7")
        r = client.get(f"/api/evidence/{CASE_ID}/nonexistent_ev_xyz", headers=auth_header(token))
        assert r.status_code == 404

    def test_list_evidence_empty_case_200(self, client):
        token = _get_token(client, "ev_user8")
        r = client.get("/api/evidence/no_such_case_xyz", headers=auth_header(token))
        assert r.status_code == 200
        assert r.get_json()["count"] == 0

    def test_evidence_requires_auth(self, client):
        r = client.get(f"/api/evidence/{CASE_ID}")
        assert r.status_code == 401


# ═══════════════════════════════════════════════════════════════════════════════
# Summary
# ═══════════════════════════════════════════════════════════════════════════════

class TestSummary:
    def test_generate_summary_200(self, client):
        token = _get_token(client, "sum_user1")
        r = client.post(f"/api/summary/generate/{CASE_ID}", headers=auth_header(token))
        assert r.status_code == 200

    def test_generate_summary_has_sections(self, client):
        token = _get_token(client, "sum_user2")
        r = client.post(f"/api/summary/generate/{CASE_ID}", headers=auth_header(token))
        data = r.get_json()
        assert "sections" in data
        sections = data["sections"]
        for key in [
            "incident_summary", "victim_summary", "transaction_summary",
            "network_summary", "timeline_summary", "detected_patterns",
            "ml_analysis", "network_roles", "key_evidence",
            "open_questions", "recommended_actions", "limitations",
        ]:
            assert key in sections, f"Missing section: {key}"

    def test_generate_summary_has_disclaimer(self, client):
        token = _get_token(client, "sum_user3")
        r = client.post(f"/api/summary/generate/{CASE_ID}", headers=auth_header(token))
        data = r.get_json()
        assert "disclaimer" in data
        assert "REQUIRES INVESTIGATOR VERIFICATION" in data["disclaimer"]

    def test_generate_summary_incident_section(self, client):
        token = _get_token(client, "sum_user4")
        r = client.post(f"/api/summary/generate/{CASE_ID}", headers=auth_header(token))
        inc = r.get_json()["sections"]["incident_summary"]
        assert inc["case_id"] == CASE_ID
        assert "fraud_pattern" in inc

    def test_generate_summary_persisted(self, client, isolated_data_dir):
        token = _get_token(client, "sum_user5")
        client.post(f"/api/summary/generate/{CASE_ID}", headers=auth_header(token))
        report_path = isolated_data_dir / "reports" / f"{CASE_ID}_summary.json"
        assert report_path.exists()

    def test_get_summary_404_before_generate(self, client):
        token = _get_token(client, "sum_user6")
        r = client.get(f"/api/summary/no_such_case_xyz", headers=auth_header(token))
        assert r.status_code == 404

    def test_get_summary_200_after_generate(self, client):
        token = _get_token(client, "sum_user7")
        client.post(f"/api/summary/generate/{CASE_ID}", headers=auth_header(token))
        r = client.get(f"/api/summary/{CASE_ID}", headers=auth_header(token))
        assert r.status_code == 200

    def test_get_summary_has_case_id(self, client):
        token = _get_token(client, "sum_user8")
        client.post(f"/api/summary/generate/{CASE_ID}", headers=auth_header(token))
        r = client.get(f"/api/summary/{CASE_ID}", headers=auth_header(token))
        assert r.get_json()["case_id"] == CASE_ID

    def test_generate_requires_auth(self, client):
        r = client.post(f"/api/summary/generate/{CASE_ID}")
        assert r.status_code == 401

    def test_get_summary_requires_auth(self, client):
        r = client.get(f"/api/summary/{CASE_ID}")
        assert r.status_code == 401

    def test_generate_unknown_case_still_succeeds(self, client):
        """Summary for an unknown case returns a minimal stub, not an error."""
        token = _get_token(client, "sum_user9")
        r = client.post("/api/summary/generate/unknown_case_xyz", headers=auth_header(token))
        assert r.status_code == 200
        data = r.get_json()
        assert "sections" in data
