"""
tests/test_ai_extraction.py
Tests for:
  - MockAIProvider entity + relationship extraction
  - Entity/relationship validation and normalisation
  - Deduplication (upsert_entities, upsert_relationships)
  - ExtractionRequest Pydantic schema validation
  - POST /api/ai/extract-entities  (route)
  - POST /api/ai/extract-relationships (route)
  - GET  /api/ai/entities
  - GET  /api/ai/relationships
"""

import sys
import json
from pathlib import Path
import pytest

from .conftest import register, login, auth_header

# ─────────────────────────────────────────────────────────────────────────────
# Synthetic text fixtures
# ─────────────────────────────────────────────────────────────────────────────

TEXT_PHONE_UPI = (
    "The victim Mr. Ramesh Kumar reported that he received a call from 9876543210. "
    "The accused transferred Rs.25000 via UPI ID fraud123@paytm to account HDFC0001234. "
    "IMEI 354321098765432 was found registered to the suspect."
)

TEXT_CASE_FIR = (
    "FIR/123/2024 was filed at Mumbai PS. Victim Smt. Priya Sharma lost Rs.50000. "
    "The accused suspect Sh. Rajesh Verma used phone 9123456789 and device IMEI 352001234567890. "
    "Transaction TXNIMPS12345678 was linked to FIR/123/2024."
)

TEXT_CALLS = (
    "Call records show 9000000001 called 9000000002 at 10:00 AM. "
    "Both numbers are registered to the same ICCID 8991400000000000001."
)

TEXT_UPI_CHAIN = (
    "Suspect Sh. Anil Gupta owns UPI ID anil99@ybl. "
    "Funds transferred from anil99@ybl to SBIN0001234. "
    "Located at Mumbai, Maharashtra."
)

TEXT_MINIMAL = "Call from 9111222333."

TEXT_EMPTY_ENTITIES = "This text contains no identifiable forensic entities."


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def get_token(client, role="INVESTIGATOR"):
    uname = f"ai_user_{role.lower()}"
    email = f"{uname}@x.com"
    register(client, username=uname, email=email, role=role)
    return login(client, uname).get_json()["token"]


def extract(client, token, text, case_id="case_ai_test", evidence_id="ev_001",
            min_confidence=0.0):
    return client.post("/api/ai/extract-entities", json={
        "text":           text,
        "case_id":        case_id,
        "evidence_id":    evidence_id,
        "min_confidence": min_confidence,
    }, headers=auth_header(token))


# ═══════════════════════════════════════════════════════════════════════════════
# UNIT — MockAIProvider
# ═══════════════════════════════════════════════════════════════════════════════

class TestMockProviderEntities:

    def _provider(self):
        from ai.provider import MockAIProvider
        return MockAIProvider()

    def test_extracts_phone(self):
        p = self._provider()
        ents = p.extract_entities_raw("Call from 9876543210 was received.", {})
        phones = [e for e in ents if e["type"] == "PHONE"]
        assert len(phones) >= 1
        assert phones[0]["value"] == "9876543210"

    def test_phone_confidence_high(self):
        p = self._provider()
        ents = p.extract_entities_raw("9876543210 called.", {})
        phones = [e for e in ents if e["type"] == "PHONE"]
        assert phones[0]["confidence"] >= 0.85

    def test_extracts_upi(self):
        p = self._provider()
        ents = p.extract_entities_raw("Transfer via fraud123@paytm received.", {})
        upis = [e for e in ents if e["type"] == "UPI_ID"]
        assert len(upis) >= 1
        assert "paytm" in upis[0]["value"]

    def test_extracts_imei(self):
        p = self._provider()
        ents = p.extract_entities_raw("Device IMEI 354321098765432 found.", {})
        imeis = [e for e in ents if e["type"] == "IMEI"]
        assert len(imeis) >= 1
        assert imeis[0]["value"] == "354321098765432"

    def test_extracts_case_reference(self):
        p = self._provider()
        ents = p.extract_entities_raw("FIR/456/2024 was filed.", {})
        cases = [e for e in ents if e["type"] == "CASE"]
        assert len(cases) >= 1
        assert "FIR" in cases[0]["value"]

    def test_extracts_victim_person(self):
        p = self._provider()
        ents = p.extract_entities_raw("complainant Anita Singh lost money.", {})
        victims = [e for e in ents if e["type"] == "VICTIM"]
        assert len(victims) >= 1

    def test_extracts_suspect_person(self):
        p = self._provider()
        ents = p.extract_entities_raw("Accused Sh. Ramesh Kumar transferred money.", {})
        suspects = [e for e in ents if e["type"] in ("SUSPECT", "PERSON")]
        assert len(suspects) >= 1

    def test_extracts_ifsc_as_bank_account(self):
        p = self._provider()
        ents = p.extract_entities_raw("Transfer to HDFC0001234 was made.", {})
        accs = [e for e in ents if e["type"] == "BANK_ACCOUNT"]
        assert len(accs) >= 1

    def test_empty_text_returns_empty(self):
        p = self._provider()
        ents = p.extract_entities_raw("", {})
        assert ents == []

    def test_no_hallucination_plain_text(self):
        p = self._provider()
        ents = p.extract_entities_raw(TEXT_EMPTY_ENTITIES, {})
        assert len(ents) == 0

    def test_all_entities_have_required_fields(self):
        p = self._provider()
        ents = p.extract_entities_raw(TEXT_PHONE_UPI, {})
        for e in ents:
            assert "type"            in e
            assert "value"           in e
            assert "raw_value"       in e
            assert "confidence"      in e
            assert "evidence_source" in e
            assert "source_text"     in e
            assert 0.0 <= e["confidence"] <= 1.0

    def test_evidence_source_is_valid(self):
        p = self._provider()
        valid = {"observed", "inferred", "ai_generated"}
        ents = p.extract_entities_raw(TEXT_PHONE_UPI, {})
        for e in ents:
            assert e["evidence_source"] in valid


class TestMockProviderRelationships:

    def _provider(self):
        from ai.provider import MockAIProvider
        return MockAIProvider()

    def test_phone_called_phone(self):
        p = self._provider()
        ents = p.extract_entities_raw(TEXT_CALLS, {})
        rels = p.extract_relationships_raw(TEXT_CALLS, ents, {})
        called = [r for r in rels if r["relationship"] == "CALLED"]
        assert len(called) >= 1

    def test_person_owns_phone(self):
        p = self._provider()
        ents = p.extract_entities_raw(
            "Suspect Sh. Ravi Tiwari used phone 9876543210.", {}
        )
        rels = p.extract_relationships_raw(
            "Suspect Sh. Ravi Tiwari used phone 9876543210.", ents, {}
        )
        owns = [r for r in rels if r["relationship"] == "OWNS"]
        assert len(owns) >= 1

    def test_victim_of_relationship(self):
        p = self._provider()
        text = "complainant Leela Nair filed FIR/200/2024."
        ents = p.extract_entities_raw(text, {})
        rels = p.extract_relationships_raw(text, ents, {})
        victim_rels = [r for r in rels if r["relationship"] == "VICTIM_OF"]
        assert len(victim_rels) >= 1

    def test_all_rels_have_required_fields(self):
        p = self._provider()
        ents = p.extract_entities_raw(TEXT_CASE_FIR, {})
        rels = p.extract_relationships_raw(TEXT_CASE_FIR, ents, {})
        for r in rels:
            assert "source_value"    in r
            assert "source_type"     in r
            assert "relationship"    in r
            assert "target_value"    in r
            assert "target_type"     in r
            assert "confidence"      in r
            assert "evidence_source" in r
            assert 0.0 <= r["confidence"] <= 1.0

    def test_no_rels_without_entities(self):
        p = self._provider()
        rels = p.extract_relationships_raw("some text", [], {})
        assert rels == []


# ═══════════════════════════════════════════════════════════════════════════════
# UNIT — Normalisation
# ═══════════════════════════════════════════════════════════════════════════════

class TestNormalisation:

    def test_phone_stripped_of_prefix(self):
        from services.extraction_service import normalise_entity_value
        assert normalise_entity_value("PHONE", "+91 9876543210") == "9876543210"

    def test_phone_stripped_of_country_code(self):
        from services.extraction_service import normalise_entity_value
        assert normalise_entity_value("PHONE", "919876543210") == "9876543210"

    def test_upi_lowercased(self):
        from services.extraction_service import normalise_entity_value
        assert normalise_entity_value("UPI_ID", "User123@PAYTM") == "user123@paytm"

    def test_name_title_cased(self):
        from services.extraction_service import normalise_entity_value
        assert normalise_entity_value("PERSON", "RAMESH KUMAR") == "Ramesh Kumar"

    def test_imei_whitespace_stripped(self):
        from services.extraction_service import normalise_entity_value
        assert normalise_entity_value("IMEI", "354 321 098 765 432") == "354321098765432"


# ═══════════════════════════════════════════════════════════════════════════════
# UNIT — Validation
# ═══════════════════════════════════════════════════════════════════════════════

class TestValidation:

    def test_valid_entity_passes(self):
        from services.extraction_service import _validate_raw_entity
        raw = {"type": "PHONE", "value": "9876543210", "raw_value": "9876543210",
               "confidence": 0.9, "source_text": "...", "evidence_source": "observed"}
        warnings = []
        result = _validate_raw_entity(raw, warnings)
        assert result is not None
        assert result["type"] == "PHONE"
        assert len(warnings) == 0

    def test_unknown_entity_type_rejected(self):
        from services.extraction_service import _validate_raw_entity
        raw = {"type": "SPACESHIP", "value": "X", "raw_value": "X",
               "confidence": 0.9, "source_text": "...", "evidence_source": "observed"}
        warnings = []
        result = _validate_raw_entity(raw, warnings)
        assert result is None
        assert len(warnings) == 1

    def test_empty_value_rejected(self):
        from services.extraction_service import _validate_raw_entity
        raw = {"type": "PHONE", "value": "", "raw_value": "",
               "confidence": 0.9, "source_text": "", "evidence_source": "observed"}
        warnings = []
        result = _validate_raw_entity(raw, warnings)
        assert result is None

    def test_confidence_clamped(self):
        from services.extraction_service import _validate_raw_entity
        raw = {"type": "PHONE", "value": "9876543210", "raw_value": "9876543210",
               "confidence": 99.0, "source_text": "", "evidence_source": "observed"}
        warnings = []
        result = _validate_raw_entity(raw, warnings)
        assert result is not None
        assert result["confidence"] == 1.0

    def test_invalid_evidence_source_coerced(self):
        from services.extraction_service import _validate_raw_entity
        raw = {"type": "PHONE", "value": "9876543210", "raw_value": "9876543210",
               "confidence": 0.8, "source_text": "", "evidence_source": "UNKNOWN"}
        warnings = []
        result = _validate_raw_entity(raw, warnings)
        assert result is not None
        assert result["evidence_source"] == "observed"

    def test_valid_relationship_passes(self):
        from services.extraction_service import _validate_raw_relationship
        raw = {
            "source_value": "9876543210", "source_type": "PHONE",
            "relationship": "CALLED",
            "target_value": "9123456789", "target_type": "PHONE",
            "confidence": 0.85, "source_text": "", "evidence_source": "observed",
        }
        warnings = []
        result = _validate_raw_relationship(raw, warnings)
        assert result is not None

    def test_unknown_relationship_rejected(self):
        from services.extraction_service import _validate_raw_relationship
        raw = {
            "source_value": "A", "source_type": "PHONE",
            "relationship": "HACKED",
            "target_value": "B", "target_type": "PHONE",
            "confidence": 0.8, "source_text": "", "evidence_source": "observed",
        }
        warnings = []
        result = _validate_raw_relationship(raw, warnings)
        assert result is None

    def test_empty_source_value_rejected(self):
        from services.extraction_service import _validate_raw_relationship
        raw = {
            "source_value": "", "source_type": "PHONE",
            "relationship": "CALLED",
            "target_value": "9123456789", "target_type": "PHONE",
            "confidence": 0.8, "source_text": "", "evidence_source": "observed",
        }
        warnings = []
        result = _validate_raw_relationship(raw, warnings)
        assert result is None


# ═══════════════════════════════════════════════════════════════════════════════
# UNIT — Deduplication
# ═══════════════════════════════════════════════════════════════════════════════

class TestDeduplication:

    def test_same_entity_not_duplicated(self, isolated_data_dir):
        from services.extraction_service import upsert_entities, ENTITIES_FILE
        from storage.file_store import write_json
        write_json(ENTITIES_FILE, [])   # reset

        now = "2024-01-01T00:00:00Z"
        validated = [
            {"type": "PHONE", "value": "9876543210", "raw_value": "9876543210",
             "confidence": 0.9, "source_text": "s1", "evidence_source": "observed", "attributes": {}},
        ]
        upsert_entities(validated, "ev_001", "case_001", now)
        upsert_entities(validated, "ev_002", "case_001", now)  # second time same entity

        from storage.file_store import read_json
        stored = read_json(ENTITIES_FILE)
        phones = [e for e in stored if e["type"] == "PHONE" and e["value"] == "9876543210"]
        assert len(phones) == 1   # deduped

    def test_dedup_bumps_confidence(self, isolated_data_dir):
        from services.extraction_service import upsert_entities, ENTITIES_FILE
        from storage.file_store import write_json
        write_json(ENTITIES_FILE, [])

        now = "2024-01-01T00:00:00Z"
        low  = [{"type": "PHONE", "value": "9000000001", "raw_value": "9000000001",
                 "confidence": 0.5, "source_text": "", "evidence_source": "observed", "attributes": {}}]
        high = [{"type": "PHONE", "value": "9000000001", "raw_value": "9000000001",
                 "confidence": 0.95, "source_text": "", "evidence_source": "observed", "attributes": {}}]

        upsert_entities(low,  "ev_001", "case_001", now)
        upsert_entities(high, "ev_002", "case_001", now)

        from storage.file_store import read_json
        stored = read_json(ENTITIES_FILE)
        p = next(e for e in stored if e["value"] == "9000000001")
        assert p["confidence"] == 0.95

    def test_dedup_accumulates_evidence_ids(self, isolated_data_dir):
        from services.extraction_service import upsert_entities, ENTITIES_FILE
        from storage.file_store import write_json
        write_json(ENTITIES_FILE, [])

        now = "2024-01-01T00:00:00Z"
        validated = [{"type": "UPI_ID", "value": "test@paytm", "raw_value": "test@paytm",
                      "confidence": 0.8, "source_text": "", "evidence_source": "observed", "attributes": {}}]
        upsert_entities(validated, "ev_A", "case_001", now)
        upsert_entities(validated, "ev_B", "case_001", now)

        from storage.file_store import read_json
        stored = read_json(ENTITIES_FILE)
        u = next(e for e in stored if e["value"] == "test@paytm")
        assert "ev_A" in u["evidence_ids"]
        assert "ev_B" in u["evidence_ids"]

    def test_different_entities_both_stored(self, isolated_data_dir):
        from services.extraction_service import upsert_entities, ENTITIES_FILE
        from storage.file_store import write_json
        write_json(ENTITIES_FILE, [])

        now = "2024-01-01T00:00:00Z"
        validated = [
            {"type": "PHONE", "value": "9111111111", "raw_value": "9111111111",
             "confidence": 0.9, "source_text": "", "evidence_source": "observed", "attributes": {}},
            {"type": "PHONE", "value": "9222222222", "raw_value": "9222222222",
             "confidence": 0.9, "source_text": "", "evidence_source": "observed", "attributes": {}},
        ]
        upsert_entities(validated, "ev_1", "case_001", now)

        from storage.file_store import read_json
        stored = read_json(ENTITIES_FILE)
        vals = {e["value"] for e in stored if e["type"] == "PHONE"}
        assert "9111111111" in vals
        assert "9222222222" in vals


# ═══════════════════════════════════════════════════════════════════════════════
# UNIT — ExtractionRequest Pydantic schema
# ═══════════════════════════════════════════════════════════════════════════════

class TestExtractionRequestSchema:

    def test_valid_request(self):
        from ai.schemas import ExtractionRequest
        req = ExtractionRequest(text="some text", case_id="c1")
        assert req.text == "some text"
        assert req.min_confidence == 0.3   # default

    def test_empty_text_rejected(self):
        from ai.schemas import ExtractionRequest
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            ExtractionRequest(text="")

    def test_whitespace_only_text_rejected(self):
        from ai.schemas import ExtractionRequest
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            ExtractionRequest(text="   ")

    def test_confidence_bounds(self):
        from ai.schemas import ExtractionRequest
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            ExtractionRequest(text="x", min_confidence=1.5)


# ═══════════════════════════════════════════════════════════════════════════════
# INTEGRATION — Extraction pipeline
# ═══════════════════════════════════════════════════════════════════════════════

class TestExtractionPipeline:

    def test_run_extraction_returns_result(self, isolated_data_dir):
        from ai.schemas import ExtractionRequest
        from services.extraction_service import run_extraction, ENTITIES_FILE
        from storage.file_store import write_json
        write_json(ENTITIES_FILE, [])

        req = ExtractionRequest(
            text=TEXT_PHONE_UPI,
            case_id="case_pipeline_01",
            evidence_id="ev_pipe_01",
            min_confidence=0.0,
        )
        result = run_extraction(req)
        assert result.provider == "mock"
        assert len(result.entities) >= 1
        assert result.new_entities >= 1

    def test_entities_persisted_to_file(self, isolated_data_dir):
        from ai.schemas import ExtractionRequest
        from services.extraction_service import run_extraction, ENTITIES_FILE
        from storage.file_store import write_json, read_json
        write_json(ENTITIES_FILE, [])

        req = ExtractionRequest(text=TEXT_PHONE_UPI, case_id="case_persist",
                                evidence_id="ev_p1", min_confidence=0.0)
        run_extraction(req)

        stored = read_json(ENTITIES_FILE) or []
        assert len(stored) >= 1
        assert all("entity_id" in e for e in stored)

    def test_case_id_on_entities(self, isolated_data_dir):
        from ai.schemas import ExtractionRequest
        from services.extraction_service import run_extraction, ENTITIES_FILE
        from storage.file_store import write_json, read_json
        write_json(ENTITIES_FILE, [])

        req = ExtractionRequest(text=TEXT_MINIMAL, case_id="case_id_check",
                                evidence_id="ev_1", min_confidence=0.0)
        run_extraction(req)
        stored = read_json(ENTITIES_FILE) or []
        for e in stored:
            assert "case_id_check" in (e.get("case_ids") or [])

    def test_evidence_id_on_entities(self, isolated_data_dir):
        from ai.schemas import ExtractionRequest
        from services.extraction_service import run_extraction, ENTITIES_FILE
        from storage.file_store import write_json, read_json
        write_json(ENTITIES_FILE, [])

        req = ExtractionRequest(text=TEXT_MINIMAL, case_id="cx",
                                evidence_id="ev_link_test", min_confidence=0.0)
        run_extraction(req)
        stored = read_json(ENTITIES_FILE) or []
        for e in stored:
            assert "ev_link_test" in (e.get("evidence_ids") or [])

    def test_min_confidence_filters(self, isolated_data_dir):
        from ai.schemas import ExtractionRequest
        from services.extraction_service import run_extraction, ENTITIES_FILE
        from storage.file_store import write_json
        write_json(ENTITIES_FILE, [])

        req_low  = ExtractionRequest(text=TEXT_PHONE_UPI, case_id="c1",
                                     evidence_id="e1", min_confidence=0.0)
        req_high = ExtractionRequest(text=TEXT_PHONE_UPI, case_id="c2",
                                     evidence_id="e2", min_confidence=0.99)

        res_low  = run_extraction(req_low)
        write_json(ENTITIES_FILE, [])
        res_high = run_extraction(req_high)

        assert len(res_low.entities) >= len(res_high.entities)

    def test_relationships_persisted(self, isolated_data_dir):
        from ai.schemas import ExtractionRequest
        from services.extraction_service import (
            run_extraction, ENTITIES_FILE, RELATIONSHIPS_FILE,
        )
        from storage.file_store import write_json, read_json
        write_json(ENTITIES_FILE, [])
        write_json(RELATIONSHIPS_FILE, [])

        req = ExtractionRequest(text=TEXT_CALLS, case_id="c_rel",
                                evidence_id="ev_rel", min_confidence=0.0)
        result = run_extraction(req)

        if result.new_relationships > 0:
            stored = read_json(RELATIONSHIPS_FILE) or []
            assert len(stored) >= 1
            assert all("relationship_id" in r for r in stored)

    def test_no_duplicate_entities_across_calls(self, isolated_data_dir):
        from ai.schemas import ExtractionRequest
        from services.extraction_service import run_extraction, ENTITIES_FILE
        from storage.file_store import write_json, read_json
        write_json(ENTITIES_FILE, [])

        req = ExtractionRequest(text=TEXT_MINIMAL, case_id="c_dedup",
                                evidence_id="ev_dedup", min_confidence=0.0)
        run_extraction(req)
        run_extraction(req)   # second call — should dedup

        stored = read_json(ENTITIES_FILE) or []
        entity_ids = [e["entity_id"] for e in stored]
        assert len(entity_ids) == len(set(entity_ids))   # no duplicate IDs


# ═══════════════════════════════════════════════════════════════════════════════
# ROUTE — POST /api/ai/extract-entities
# ═══════════════════════════════════════════════════════════════════════════════

class TestExtractEntitiesRoute:

    def test_requires_auth(self, client):
        rv = client.post("/api/ai/extract-entities", json={"text": "hello"})
        assert rv.status_code == 401

    def test_viewer_forbidden(self, client):
        token = get_token(client, role="VIEWER")
        rv = client.post("/api/ai/extract-entities",
                         json={"text": "some text"},
                         headers=auth_header(token))
        assert rv.status_code == 403

    def test_missing_text(self, client):
        token = get_token(client)
        rv = client.post("/api/ai/extract-entities", json={}, headers=auth_header(token))
        assert rv.status_code == 400
        assert "text" in rv.get_json()["error"]

    def test_empty_text(self, client):
        token = get_token(client)
        rv = client.post("/api/ai/extract-entities",
                         json={"text": ""},
                         headers=auth_header(token))
        assert rv.status_code == 400

    def test_successful_extraction(self, client):
        token = get_token(client)
        rv = client.post("/api/ai/extract-entities", json={
            "text":        TEXT_PHONE_UPI,
            "case_id":     "case_route_01",
            "evidence_id": "ev_route_01",
            "min_confidence": 0.0,
        }, headers=auth_header(token))
        assert rv.status_code == 201
        data = rv.get_json()
        assert "entities" in data
        assert "relationships" in data
        assert "stats" in data
        assert "provider" in data
        assert data["provider"] == "mock"

    def test_entity_format(self, client):
        token = get_token(client)
        rv = client.post("/api/ai/extract-entities", json={
            "text": TEXT_PHONE_UPI, "case_id": "c_fmt", "min_confidence": 0.0,
        }, headers=auth_header(token))
        data = rv.get_json()
        for e in data["entities"]:
            assert "entity_id"      in e
            assert "type"           in e
            assert "value"          in e
            assert "confidence"     in e
            assert "evidence_source" in e

    def test_relationship_format(self, client):
        token = get_token(client)
        rv = client.post("/api/ai/extract-entities", json={
            "text": TEXT_CALLS, "case_id": "c_relfmt", "min_confidence": 0.0,
        }, headers=auth_header(token))
        data = rv.get_json()
        for r in data.get("relationships", []):
            assert "relationship_id" in r
            assert "source_entity"   in r
            assert "relationship"    in r
            assert "target_entity"   in r
            assert "confidence"      in r

    def test_stats_present(self, client):
        token = get_token(client)
        rv = client.post("/api/ai/extract-entities", json={
            "text": TEXT_PHONE_UPI, "case_id": "c_stats", "min_confidence": 0.0,
        }, headers=auth_header(token))
        data = rv.get_json()
        stats = data["stats"]
        assert "new_entities"    in stats
        assert "merged_entities" in stats
        assert stats["new_entities"] >= 0

    def test_empty_entities_text_returns_empty_list(self, client):
        token = get_token(client)
        rv = client.post("/api/ai/extract-entities", json={
            "text": TEXT_EMPTY_ENTITIES, "case_id": "c_empty",
        }, headers=auth_header(token))
        assert rv.status_code == 201
        assert rv.get_json()["entities"] == []


# ═══════════════════════════════════════════════════════════════════════════════
# ROUTE — POST /api/ai/extract-relationships
# ═══════════════════════════════════════════════════════════════════════════════

class TestExtractRelationshipsRoute:

    def _seed_entities(self, client, token, text, case_id):
        """Run extract-entities first so entities exist in the store."""
        return client.post("/api/ai/extract-entities", json={
            "text": text, "case_id": case_id, "min_confidence": 0.0,
        }, headers=auth_header(token)).get_json()["entities"]

    def test_requires_auth(self, client):
        rv = client.post("/api/ai/extract-relationships",
                         json={"text": "x", "entities": [{"type": "PHONE", "value": "9111111111"}]})
        assert rv.status_code == 401

    def test_missing_text(self, client):
        token = get_token(client)
        rv = client.post("/api/ai/extract-relationships",
                         json={"entities": [{"type": "PHONE", "value": "9111111111"}]},
                         headers=auth_header(token))
        assert rv.status_code == 400

    def test_missing_entities(self, client):
        token = get_token(client)
        rv = client.post("/api/ai/extract-relationships",
                         json={"text": "some text"},
                         headers=auth_header(token))
        assert rv.status_code == 400

    def test_empty_entities_list(self, client):
        token = get_token(client)
        rv = client.post("/api/ai/extract-relationships",
                         json={"text": "some text", "entities": []},
                         headers=auth_header(token))
        assert rv.status_code == 400

    def test_successful_rel_extraction(self, client):
        token = get_token(client)
        entities = self._seed_entities(client, token, TEXT_CALLS, "c_relroute")
        rv = client.post("/api/ai/extract-relationships", json={
            "text":     TEXT_CALLS,
            "entities": entities,
            "case_id":  "c_relroute",
            "min_confidence": 0.0,
        }, headers=auth_header(token))
        assert rv.status_code == 201
        data = rv.get_json()
        assert "relationships" in data
        assert "stats" in data


# ═══════════════════════════════════════════════════════════════════════════════
# ROUTE — GET /api/ai/entities  and  GET /api/ai/relationships
# ═══════════════════════════════════════════════════════════════════════════════

class TestGetEntitiesRoute:

    def test_entities_missing_case_id(self, client):
        token = get_token(client)
        rv = client.get("/api/ai/entities", headers=auth_header(token))
        assert rv.status_code == 400

    def test_entities_returns_list(self, client):
        token = get_token(client)
        # Seed
        client.post("/api/ai/extract-entities", json={
            "text": TEXT_PHONE_UPI, "case_id": "c_get_ent", "min_confidence": 0.0,
        }, headers=auth_header(token))
        rv = client.get("/api/ai/entities?case_id=c_get_ent", headers=auth_header(token))
        assert rv.status_code == 200
        data = rv.get_json()
        assert "entities" in data
        assert data["total"] == len(data["entities"])
        assert data["total"] >= 1

    def test_relationships_missing_case_id(self, client):
        token = get_token(client)
        rv = client.get("/api/ai/relationships", headers=auth_header(token))
        assert rv.status_code == 400

    def test_relationships_returns_list(self, client):
        token = get_token(client)
        client.post("/api/ai/extract-entities", json={
            "text": TEXT_CALLS, "case_id": "c_get_rel", "min_confidence": 0.0,
        }, headers=auth_header(token))
        rv = client.get("/api/ai/relationships?case_id=c_get_rel", headers=auth_header(token))
        assert rv.status_code == 200
        data = rv.get_json()
        assert "relationships" in data
        assert isinstance(data["relationships"], list)
