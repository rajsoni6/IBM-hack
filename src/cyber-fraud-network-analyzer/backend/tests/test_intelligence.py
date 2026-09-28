"""
tests/test_intelligence.py
Tests for POST /api/intelligence/upload
"""

import io
import json
import csv

import pytest
from .conftest import register, login, auth_header


# ── Helpers ───────────────────────────────────────────────────────────────────

def get_token(client, role="INVESTIGATOR"):
    uname = f"intel_user_{role.lower()}"
    email = f"{uname}@x.com"
    register(client, username=uname, email=email, role=role)
    return login(client, uname).get_json()["token"]


def make_csv_bytes(rows: list[dict]) -> bytes:
    buf = io.StringIO()
    if not rows:
        return b""
    w = csv.DictWriter(buf, fieldnames=list(rows[0].keys()))
    w.writeheader()
    w.writerows(rows)
    return buf.getvalue().encode("utf-8")


def make_json_bytes(data) -> bytes:
    return json.dumps(data).encode("utf-8")


def upload(client, token, content, filename, case_id="case_test_001",
           record_type=None, content_type="text/csv"):
    data = {
        "file":    (io.BytesIO(content), filename),
        "case_id": case_id,
    }
    if record_type:
        data["record_type"] = record_type
    return client.post(
        "/api/intelligence/upload",
        data=data,
        content_type="multipart/form-data",
        headers=auth_header(token),
    )


# ═══════════════════════════════════════════════════════════════════════════════
# AUTH GUARD
# ═══════════════════════════════════════════════════════════════════════════════

class TestUploadAuth:

    def test_upload_requires_auth(self, client):
        content = make_csv_bytes([{"col": "val"}])
        rv = client.post(
            "/api/intelligence/upload",
            data={"file": (io.BytesIO(content), "test.csv"), "case_id": "c001"},
            content_type="multipart/form-data",
        )
        assert rv.status_code == 401

    def test_viewer_cannot_upload(self, client):
        token   = get_token(client, role="VIEWER")
        content = make_csv_bytes([{"amount": "100", "src_account": "a", "dst_account": "b"}])
        rv = upload(client, token, content, "txn.csv")
        assert rv.status_code == 403


# ═══════════════════════════════════════════════════════════════════════════════
# VALIDATION
# ═══════════════════════════════════════════════════════════════════════════════

class TestUploadValidation:

    def test_no_file_key(self, client):
        token = get_token(client)
        rv = client.post(
            "/api/intelligence/upload",
            data={"case_id": "c001"},
            content_type="multipart/form-data",
            headers=auth_header(token),
        )
        assert rv.status_code == 400
        assert "file" in rv.get_json()["error"].lower()

    def test_missing_case_id(self, client):
        token   = get_token(client)
        content = make_csv_bytes([{"a": "1"}])
        rv = client.post(
            "/api/intelligence/upload",
            data={"file": (io.BytesIO(content), "f.csv")},
            content_type="multipart/form-data",
            headers=auth_header(token),
        )
        assert rv.status_code == 400
        assert "case_id" in rv.get_json()["error"].lower()

    def test_unsupported_extension(self, client):
        token   = get_token(client)
        content = b"some content"
        rv = upload(client, token, content, "data.exe")
        assert rv.status_code == 422

    def test_empty_file(self, client):
        token = get_token(client)
        rv = upload(client, token, b"", "empty.csv")
        assert rv.status_code == 422

    def test_malformed_json(self, client):
        token = get_token(client)
        rv = upload(client, token, b"{not valid json", "bad.json")
        assert rv.status_code == 422

    def test_csv_header_only(self, client):
        token = get_token(client)
        content = b"col1,col2\n"    # header row only, no data
        rv = upload(client, token, content, "header_only.csv")
        assert rv.status_code == 422

    def test_unknown_record_type_rejected(self, client):
        token   = get_token(client)
        content = make_csv_bytes([{"a": "1"}])
        rv = upload(client, token, content, "f.csv", record_type="spaceship")
        assert rv.status_code == 400


# ═══════════════════════════════════════════════════════════════════════════════
# SUCCESSFUL INGESTION — CSV
# ═══════════════════════════════════════════════════════════════════════════════

class TestCSVIngestion:

    def test_csv_transactions(self, client):
        token = get_token(client)
        rows = [
            {"src_account": "acc_001", "dst_account": "acc_002",
             "amount": "15000", "method": "IMPS",
             "narration": "transfer", "timestamp": "2024-01-15"},
            {"src_account": "acc_003", "dst_account": "acc_004",
             "amount": "8500", "method": "UPI",
             "narration": "payment", "timestamp": "2024-01-16"},
        ]
        rv = upload(client, token, make_csv_bytes(rows), "txn.csv",
                    record_type="transactions")
        assert rv.status_code == 201
        data = rv.get_json()
        assert data["normalised"] == 2
        assert data["record_type"] == "transactions"
        assert data["evidence_id"]

    def test_csv_calls(self, client):
        token = get_token(client)
        rows = [
            {"caller": "9876543210", "receiver": "9123456789",
             "duration": "120", "call_type": "outgoing",
             "timestamp": "2024-02-01 10:00:00"},
        ]
        rv = upload(client, token, make_csv_bytes(rows), "calls.csv",
                    record_type="calls")
        assert rv.status_code == 201
        assert rv.get_json()["normalised"] == 1
        assert rv.get_json()["record_type"] == "calls"

    def test_csv_bank_accounts(self, client):
        token = get_token(client)
        rows = [
            {"account_number": "123456789012", "bank": "SBI",
             "ifsc": "SBIN0001234", "holder_name": "Test Person",
             "balance": "50000", "kyc_status": "verified"},
        ]
        rv = upload(client, token, make_csv_bytes(rows), "accounts.csv",
                    record_type="bank_accounts")
        assert rv.status_code == 201

    def test_csv_sims(self, client):
        token = get_token(client)
        rows = [
            {"iccid": "89914000000000001", "imsi": "404100000000001",
             "operator": "Jio", "phone_number": "9000000001",
             "swap_count": "2", "kyc": "true"},
        ]
        rv = upload(client, token, make_csv_bytes(rows), "sims.csv",
                    record_type="sims")
        assert rv.status_code == 201

    def test_csv_devices(self, client):
        token = get_token(client)
        rows = [
            {"imei": "354321000000001", "brand": "Samsung",
             "model": "Galaxy A52", "os": "Android 12"},
        ]
        rv = upload(client, token, make_csv_bytes(rows), "devices.csv",
                    record_type="devices")
        assert rv.status_code == 201

    def test_csv_upi_ids(self, client):
        token = get_token(client)
        rows = [{"vpa": "user@okaxis", "is_active": "true", "txn_count": "100"}]
        rv = upload(client, token, make_csv_bytes(rows), "upi.csv", record_type="upi_ids")
        assert rv.status_code == 201

    def test_csv_phones(self, client):
        token = get_token(client)
        rows = [{"number": "9876543210", "operator": "Airtel", "circle": "Mumbai"}]
        rv = upload(client, token, make_csv_bytes(rows), "phones.csv", record_type="phones")
        assert rv.status_code == 201

    def test_csv_locations(self, client):
        token = get_token(client)
        rows = [{"city": "Mumbai", "state": "Maharashtra", "lat": "19.076", "lon": "72.877"}]
        rv = upload(client, token, make_csv_bytes(rows), "loc.csv", record_type="locations")
        assert rv.status_code == 201

    def test_csv_complaints(self, client):
        token = get_token(client)
        rows = [{"complaint_number": "CMP001", "fraud_type": "UPI fraud",
                 "narrative": "Victim lost money", "loss_amount": "25000"}]
        rv = upload(client, token, make_csv_bytes(rows), "cmp.csv", record_type="complaints")
        assert rv.status_code == 201

    def test_auto_detect_transactions(self, client):
        token = get_token(client)
        rows = [{"src_account": "a1", "dst_account": "a2", "amount": "500", "debit": "100"}]
        rv = upload(client, token, make_csv_bytes(rows), "auto.csv")   # no hint
        assert rv.status_code == 201
        assert rv.get_json()["record_type"] == "transactions"

    def test_response_contains_provenance(self, client):
        token = get_token(client)
        rows = [{"src_account": "a", "dst_account": "b", "amount": "100"}]
        rv = upload(client, token, make_csv_bytes(rows), "prov.csv",
                    case_id="case_prov_test", record_type="transactions")
        data = rv.get_json()
        assert data["case_id"] == "case_prov_test"
        assert data["filename"] == "prov.csv"
        assert "raw_path" in data
        assert "processed_path" in data
        assert "uploaded_at" in data


# ═══════════════════════════════════════════════════════════════════════════════
# SUCCESSFUL INGESTION — JSON
# ═══════════════════════════════════════════════════════════════════════════════

class TestJSONIngestion:

    def test_json_array(self, client):
        token = get_token(client)
        data  = [{"src_account": "a", "dst_account": "b", "amount": "200"}]
        rv = upload(client, token, make_json_bytes(data), "txn.json",
                    record_type="transactions")
        assert rv.status_code == 201
        assert rv.get_json()["normalised"] == 1

    def test_json_wrapped_records_key(self, client):
        token = get_token(client)
        data  = {"records": [{"src_account": "a", "dst_account": "b", "amount": "50"}]}
        rv = upload(client, token, make_json_bytes(data), "wrapped.json",
                    record_type="transactions")
        assert rv.status_code == 201
        assert rv.get_json()["normalised"] == 1

    def test_json_wrapped_data_key(self, client):
        token = get_token(client)
        data  = {"data": [{"caller": "9111111111", "receiver": "9222222222", "duration": "60"}]}
        rv = upload(client, token, make_json_bytes(data), "wrapped2.json",
                    record_type="calls")
        assert rv.status_code == 201

    def test_json_single_object(self, client):
        token = get_token(client)
        data  = {"src_account": "a", "dst_account": "b", "amount": "999"}
        rv = upload(client, token, make_json_bytes(data), "single.json",
                    record_type="transactions")
        assert rv.status_code == 201
        assert rv.get_json()["normalised"] == 1


# ═══════════════════════════════════════════════════════════════════════════════
# SUCCESSFUL INGESTION — TXT
# ═══════════════════════════════════════════════════════════════════════════════

class TestTXTIngestion:

    def test_txt_csv_like(self, client):
        token   = get_token(client)
        content = b"caller,receiver,duration\n9000000001,9000000002,120\n9000000003,9000000004,60\n"
        rv = upload(client, token, content, "calls.txt", record_type="calls")
        assert rv.status_code == 201
        assert rv.get_json()["normalised"] >= 1

    def test_txt_complaints_freeform(self, client):
        token   = get_token(client)
        content = b"I lost money via UPI fraud.\nThe caller claimed to be from my bank.\n"
        rv = upload(client, token, content, "complaint.txt", record_type="complaints")
        assert rv.status_code == 201


# ═══════════════════════════════════════════════════════════════════════════════
# IDEMPOTENCY — uploading twice appends, doesn't overwrite
# ═══════════════════════════════════════════════════════════════════════════════

class TestIdempotency:

    def test_upload_twice_appends(self, client):
        token = get_token(client)
        rows  = [{"src_account": "a", "dst_account": "b", "amount": "1"}]
        upload(client, token, make_csv_bytes(rows), "txn1.csv",
               case_id="case_idem", record_type="transactions")
        upload(client, token, make_csv_bytes(rows), "txn2.csv",
               case_id="case_idem", record_type="transactions")

        # Both uploads created separate evidence records
        from services.intelligence_service import EVIDENCE_FILE
        from storage.file_store import read_json
        evidence = read_json(EVIDENCE_FILE) or []
        idem_ev = [e for e in evidence if e["case_id"] == "case_idem"]
        assert len(idem_ev) >= 2


# ═══════════════════════════════════════════════════════════════════════════════
# NORMALISER — provenance fields
# ═══════════════════════════════════════════════════════════════════════════════

class TestProvenance:

    def test_normalised_records_have_provenance(self, client):
        token = get_token(client)
        rows  = [{"src_account": "x", "dst_account": "y", "amount": "777"}]
        rv = upload(client, token, make_csv_bytes(rows), "prov2.csv",
                    case_id="case_provenance", record_type="transactions")
        result = rv.get_json()
        evidence_id = result["evidence_id"]

        from services.intelligence_service import PROCESSED_DIR
        import json as _json
        from pathlib import Path
        pf = PROCESSED_DIR / "case_provenance" / "transactions.json"
        assert pf.exists(), "Processed file should exist"
        records = _json.loads(pf.read_text())
        assert len(records) >= 1
        r = records[0]
        assert r["source_file"] == "prov2.csv"
        assert r["case_id"] == "case_provenance"
        assert r["evidence_id"] == evidence_id
        assert "ingested_at" in r
