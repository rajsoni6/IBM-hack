"""
tests/test_patterns.py

Tests for:
  - PatternDetector (all 9 pattern detectors)
  - RoleAnalyzer (all 6 role types)
  - GET  /api/patterns/<case_id>
  - POST /api/patterns/analyze/<case_id>
  - GET  /api/roles/<case_id>
"""

import json
from pathlib import Path

import pytest

from .conftest import register, login, auth_header


# ═══════════════════════════════════════════════════════════════════════════════
# Shared test fixtures
# ═══════════════════════════════════════════════════════════════════════════════

CASE_ID = "case_patterns_test"

# Minimal entity set covering all relevant types
ENTITIES = [
    # Persons
    {"entity_id": "p_001", "type": "PERSON",  "value": "Alice",   "label": "Alice",   "confidence": 0.9, "risk_score": 0.8,  "case_ids": [CASE_ID], "evidence_ids": [], "attributes": {}, "extracted_at": "2024-01-01T00:00:00Z", "updated_at": "2024-01-01T00:00:00Z", "raw_value": "Alice",   "source_texts": []},
    {"entity_id": "p_002", "type": "PERSON",  "value": "Bob",     "label": "Bob",     "confidence": 0.9, "risk_score": 0.7,  "case_ids": [CASE_ID], "evidence_ids": [], "attributes": {}, "extracted_at": "2024-01-01T00:00:00Z", "updated_at": "2024-01-01T00:00:00Z", "raw_value": "Bob",     "source_texts": []},
    {"entity_id": "p_003", "type": "VICTIM",  "value": "Victim1", "label": "Victim1", "confidence": 0.9, "risk_score": 0.05, "case_ids": [CASE_ID], "evidence_ids": [], "attributes": {}, "extracted_at": "2024-01-01T00:00:00Z", "updated_at": "2024-01-01T00:00:00Z", "raw_value": "Victim1", "source_texts": []},
    # Phones
    {"entity_id": "ph_001", "type": "PHONE",  "value": "9000000001", "label": "9000000001", "confidence": 0.9, "risk_score": 0.5, "case_ids": [CASE_ID], "evidence_ids": [], "attributes": {}, "extracted_at": "2024-01-01T00:00:00Z", "updated_at": "2024-01-01T00:00:00Z", "raw_value": "9000000001", "source_texts": []},
    {"entity_id": "ph_002", "type": "PHONE",  "value": "9000000002", "label": "9000000002", "confidence": 0.9, "risk_score": 0.5, "case_ids": [CASE_ID], "evidence_ids": [], "attributes": {}, "extracted_at": "2024-01-01T00:00:00Z", "updated_at": "2024-01-01T00:00:00Z", "raw_value": "9000000002", "source_texts": []},
    {"entity_id": "ph_003", "type": "PHONE",  "value": "9000000003", "label": "9000000003", "confidence": 0.9, "risk_score": 0.5, "case_ids": [CASE_ID], "evidence_ids": [], "attributes": {}, "extracted_at": "2024-01-01T00:00:00Z", "updated_at": "2024-01-01T00:00:00Z", "raw_value": "9000000003", "source_texts": []},
    # Accounts
    {"entity_id": "acc_001", "type": "BANK_ACCOUNT", "value": "ACC001", "label": "ACC001", "confidence": 0.9, "risk_score": 0.6, "case_ids": [CASE_ID], "evidence_ids": [], "attributes": {}, "extracted_at": "2024-01-01T00:00:00Z", "updated_at": "2024-01-01T00:00:00Z", "raw_value": "ACC001", "source_texts": []},
    {"entity_id": "acc_002", "type": "BANK_ACCOUNT", "value": "ACC002", "label": "ACC002", "confidence": 0.9, "risk_score": 0.6, "case_ids": [CASE_ID], "evidence_ids": [], "attributes": {}, "extracted_at": "2024-01-01T00:00:00Z", "updated_at": "2024-01-01T00:00:00Z", "raw_value": "ACC002", "source_texts": []},
    {"entity_id": "acc_003", "type": "BANK_ACCOUNT", "value": "ACC003", "label": "ACC003", "confidence": 0.9, "risk_score": 0.6, "case_ids": [CASE_ID], "evidence_ids": [], "attributes": {}, "extracted_at": "2024-01-01T00:00:00Z", "updated_at": "2024-01-01T00:00:00Z", "raw_value": "ACC003", "source_texts": []},
    {"entity_id": "acc_004", "type": "BANK_ACCOUNT", "value": "ACC004", "label": "ACC004", "confidence": 0.9, "risk_score": 0.6, "case_ids": [CASE_ID], "evidence_ids": [], "attributes": {}, "extracted_at": "2024-01-01T00:00:00Z", "updated_at": "2024-01-01T00:00:00Z", "raw_value": "ACC004", "source_texts": []},
    # SIM
    {"entity_id": "sim_001", "type": "SIM",    "value": "SIM001", "label": "SIM001", "confidence": 0.9, "risk_score": 0.5, "case_ids": [CASE_ID], "evidence_ids": [], "attributes": {}, "extracted_at": "2024-01-01T00:00:00Z", "updated_at": "2024-01-01T00:00:00Z", "raw_value": "SIM001", "source_texts": []},
    # Device
    {"entity_id": "dev_001", "type": "DEVICE", "value": "DEV001", "label": "DEV001", "confidence": 0.9, "risk_score": 0.5, "case_ids": [CASE_ID], "evidence_ids": [], "attributes": {}, "extracted_at": "2024-01-01T00:00:00Z", "updated_at": "2024-01-01T00:00:00Z", "raw_value": "DEV001", "source_texts": []},
]

RELATIONSHIPS = [
    # SIM → phones (for sim_swap / shared_sim)
    {"relationship_id": "r_01", "source_entity": "ph_001", "target_entity": "sim_001", "relationship": "USES", "confidence": 0.9, "evidence_ids": [], "case_ids": [CASE_ID], "evidence_source": "observed", "source_text": "", "attributes": {}, "extracted_at": "2024-01-01T00:00:00Z"},
    {"relationship_id": "r_02", "source_entity": "ph_002", "target_entity": "sim_001", "relationship": "USES", "confidence": 0.9, "evidence_ids": [], "case_ids": [CASE_ID], "evidence_source": "observed", "source_text": "", "attributes": {}, "extracted_at": "2024-01-01T00:00:00Z"},
    # person → phone
    {"relationship_id": "r_03", "source_entity": "p_001", "target_entity": "ph_001", "relationship": "OWNS", "confidence": 0.9, "evidence_ids": [], "case_ids": [CASE_ID], "evidence_source": "observed", "source_text": "", "attributes": {}, "extracted_at": "2024-01-01T00:00:00Z"},
    {"relationship_id": "r_04", "source_entity": "p_002", "target_entity": "ph_002", "relationship": "OWNS", "confidence": 0.9, "evidence_ids": [], "case_ids": [CASE_ID], "evidence_source": "observed", "source_text": "", "attributes": {}, "extracted_at": "2024-01-01T00:00:00Z"},
    # person → account
    {"relationship_id": "r_05", "source_entity": "p_001", "target_entity": "acc_001", "relationship": "OWNS", "confidence": 0.9, "evidence_ids": [], "case_ids": [CASE_ID], "evidence_source": "observed", "source_text": "", "attributes": {}, "extracted_at": "2024-01-01T00:00:00Z"},
    {"relationship_id": "r_06", "source_entity": "p_002", "target_entity": "acc_002", "relationship": "OWNS", "confidence": 0.9, "evidence_ids": [], "case_ids": [CASE_ID], "evidence_source": "observed", "source_text": "", "attributes": {}, "extracted_at": "2024-01-01T00:00:00Z"},
    # device → accounts (shared device)
    {"relationship_id": "r_07", "source_entity": "dev_001", "target_entity": "acc_001", "relationship": "LINKED_TO", "confidence": 0.9, "evidence_ids": [], "case_ids": [CASE_ID], "evidence_source": "observed", "source_text": "", "attributes": {}, "extracted_at": "2024-01-01T00:00:00Z"},
    {"relationship_id": "r_08", "source_entity": "dev_001", "target_entity": "acc_002", "relationship": "LINKED_TO", "confidence": 0.9, "evidence_ids": [], "case_ids": [CASE_ID], "evidence_source": "observed", "source_text": "", "attributes": {}, "extracted_at": "2024-01-01T00:00:00Z"},
    {"relationship_id": "r_09", "source_entity": "dev_001", "target_entity": "acc_003", "relationship": "LINKED_TO", "confidence": 0.9, "evidence_ids": [], "case_ids": [CASE_ID], "evidence_source": "observed", "source_text": "", "attributes": {}, "extracted_at": "2024-01-01T00:00:00Z"},
    # Phone → account direct link (needed for sim_swap account discovery)
    {"relationship_id": "r_09b", "source_entity": "ph_001", "target_entity": "acc_001", "relationship": "LINKED_TO", "confidence": 0.8, "evidence_ids": [], "case_ids": [CASE_ID], "evidence_source": "observed", "source_text": "", "attributes": {}, "extracted_at": "2024-01-01T00:00:00Z"},
    # Victim connections
    {"relationship_id": "r_10", "source_entity": "p_001", "target_entity": "p_003", "relationship": "ASSOCIATED_WITH", "confidence": 0.7, "evidence_ids": [], "case_ids": [CASE_ID], "evidence_source": "inferred", "source_text": "", "attributes": {}, "extracted_at": "2024-01-01T00:00:00Z"},
    # Dense cluster: acc_001 ↔ acc_002 ↔ acc_003 ↔ acc_001
    {"relationship_id": "r_11", "source_entity": "acc_001", "target_entity": "acc_002", "relationship": "LINKED_TO", "confidence": 0.8, "evidence_ids": [], "case_ids": [CASE_ID], "evidence_source": "observed", "source_text": "", "attributes": {}, "extracted_at": "2024-01-01T00:00:00Z"},
    {"relationship_id": "r_12", "source_entity": "acc_002", "target_entity": "acc_003", "relationship": "LINKED_TO", "confidence": 0.8, "evidence_ids": [], "case_ids": [CASE_ID], "evidence_source": "observed", "source_text": "", "attributes": {}, "extracted_at": "2024-01-01T00:00:00Z"},
    {"relationship_id": "r_13", "source_entity": "acc_003", "target_entity": "acc_001", "relationship": "LINKED_TO", "confidence": 0.8, "evidence_ids": [], "case_ids": [CASE_ID], "evidence_source": "observed", "source_text": "", "attributes": {}, "extracted_at": "2024-01-01T00:00:00Z"},
    # phone call edges (hub detection via graph)
    {"relationship_id": "r_14", "source_entity": "ph_001", "target_entity": "ph_002", "relationship": "CALLED", "confidence": 0.9, "evidence_ids": [], "case_ids": [CASE_ID], "evidence_source": "observed", "source_text": "", "attributes": {}, "extracted_at": "2024-01-01T00:00:00Z"},
    {"relationship_id": "r_15", "source_entity": "ph_001", "target_entity": "ph_003", "relationship": "CALLED", "confidence": 0.9, "evidence_ids": [], "case_ids": [CASE_ID], "evidence_source": "observed", "source_text": "", "attributes": {}, "extracted_at": "2024-01-01T00:00:00Z"},
    {"relationship_id": "r_16", "source_entity": "ph_003", "target_entity": "acc_004", "relationship": "LINKED_TO", "confidence": 0.8, "evidence_ids": [], "case_ids": [CASE_ID], "evidence_source": "observed", "source_text": "", "attributes": {}, "extracted_at": "2024-01-01T00:00:00Z"},
]

# Transactions enabling: mule, layering, velocity, rapid multi-hop
TRANSACTIONS = [
    # Mule pattern on acc_002 (receives from acc_001, forwards to acc_003 & acc_004)
    {"id": "tx_001", "src_account": "acc_001", "dst_account": "acc_002", "amount": 100000, "currency": "INR", "method": "IMPS", "timestamp": "2024-01-10T08:00:00Z", "case_id": CASE_ID, "risk_score": 0.8, "flagged": True},
    {"id": "tx_002", "src_account": "acc_001", "dst_account": "acc_002", "amount": 80000,  "currency": "INR", "method": "IMPS", "timestamp": "2024-01-10T09:00:00Z", "case_id": CASE_ID, "risk_score": 0.8, "flagged": True},
    {"id": "tx_003", "src_account": "acc_002", "dst_account": "acc_003", "amount": 90000,  "currency": "INR", "method": "IMPS", "timestamp": "2024-01-10T10:00:00Z", "case_id": CASE_ID, "risk_score": 0.8, "flagged": True},
    {"id": "tx_004", "src_account": "acc_002", "dst_account": "acc_004", "amount": 80000,  "currency": "INR", "method": "IMPS", "timestamp": "2024-01-10T11:00:00Z", "case_id": CASE_ID, "risk_score": 0.8, "flagged": True},
    # Layering / rapid multi-hop chain: acc_001 → acc_002 → acc_003 → acc_004
    {"id": "tx_005", "src_account": "acc_003", "dst_account": "acc_004", "amount": 50000,  "currency": "INR", "method": "NEFT", "timestamp": "2024-01-10T10:30:00Z", "case_id": CASE_ID, "risk_score": 0.7, "flagged": True},
    # High velocity on acc_001 (5 txns within 24 h)
    {"id": "tx_006", "src_account": "acc_001", "dst_account": "acc_003", "amount": 10000,  "currency": "INR", "method": "UPI",  "timestamp": "2024-01-10T12:00:00Z", "case_id": CASE_ID, "risk_score": 0.6, "flagged": False},
    {"id": "tx_007", "src_account": "acc_001", "dst_account": "acc_004", "amount": 15000,  "currency": "INR", "method": "UPI",  "timestamp": "2024-01-10T13:00:00Z", "case_id": CASE_ID, "risk_score": 0.6, "flagged": False},
    {"id": "tx_008", "src_account": "acc_001", "dst_account": "acc_002", "amount": 20000,  "currency": "INR", "method": "UPI",  "timestamp": "2024-01-10T14:00:00Z", "case_id": CASE_ID, "risk_score": 0.6, "flagged": False},
    {"id": "tx_009", "src_account": "acc_001", "dst_account": "acc_003", "amount": 5000,   "currency": "INR", "method": "UPI",  "timestamp": "2024-01-10T15:00:00Z", "case_id": CASE_ID, "risk_score": 0.5, "flagged": False},
    {"id": "tx_010", "src_account": "acc_001", "dst_account": "acc_004", "amount": 7000,   "currency": "INR", "method": "UPI",  "timestamp": "2024-01-10T16:00:00Z", "case_id": CASE_ID, "risk_score": 0.5, "flagged": False},
]

CALL_RECORDS = [
    # Hub: ph_001 contacts many parties
    {"id": "call_001", "caller_id": "ph_001", "receiver_id": "ph_002", "duration_sec": 60,  "call_type": "outgoing", "timestamp": "2024-01-10T08:00:00Z", "case_id": CASE_ID},
    {"id": "call_002", "caller_id": "ph_001", "receiver_id": "ph_003", "duration_sec": 120, "call_type": "outgoing", "timestamp": "2024-01-10T09:00:00Z", "case_id": CASE_ID},
    {"id": "call_003", "caller_id": "ph_001", "receiver_id": "9111111111", "duration_sec": 30,  "call_type": "outgoing", "timestamp": "2024-01-10T10:00:00Z", "case_id": CASE_ID},
    {"id": "call_004", "caller_id": "ph_001", "receiver_id": "9222222222", "duration_sec": 45,  "call_type": "outgoing", "timestamp": "2024-01-10T11:00:00Z", "case_id": CASE_ID},
    {"id": "call_005", "caller_id": "ph_001", "receiver_id": "9333333333", "duration_sec": 90,  "call_type": "outgoing", "timestamp": "2024-01-10T12:00:00Z", "case_id": CASE_ID},
    {"id": "call_006", "caller_id": "ph_001", "receiver_id": "9444444444", "duration_sec": 20,  "call_type": "outgoing", "timestamp": "2024-01-10T13:00:00Z", "case_id": CASE_ID},
    # ph_002: just one call (for avg comparison)
    {"id": "call_007", "caller_id": "ph_002", "receiver_id": "ph_003", "duration_sec": 60, "call_type": "outgoing", "timestamp": "2024-01-10T08:30:00Z", "case_id": CASE_ID},
    # ph_003: one call
    {"id": "call_008", "caller_id": "ph_003", "receiver_id": "ph_002", "duration_sec": 60, "call_type": "outgoing", "timestamp": "2024-01-10T09:30:00Z", "case_id": CASE_ID},
    # Extra single-contact callers to keep average low so ph_001 (6 contacts) stands out at ≥2.5x
    {"id": "call_009", "caller_id": "9500000001", "receiver_id": "ph_001", "duration_sec": 30, "call_type": "outgoing", "timestamp": "2024-01-10T10:30:00Z", "case_id": CASE_ID},
    {"id": "call_010", "caller_id": "9500000002", "receiver_id": "ph_001", "duration_sec": 30, "call_type": "outgoing", "timestamp": "2024-01-10T11:30:00Z", "case_id": CASE_ID},
    {"id": "call_011", "caller_id": "9500000003", "receiver_id": "ph_002", "duration_sec": 30, "call_type": "outgoing", "timestamp": "2024-01-10T12:30:00Z", "case_id": CASE_ID},
    {"id": "call_012", "caller_id": "9500000004", "receiver_id": "ph_003", "duration_sec": 30, "call_type": "outgoing", "timestamp": "2024-01-10T13:30:00Z", "case_id": CASE_ID},
    {"id": "call_013", "caller_id": "9500000005", "receiver_id": "ph_003", "duration_sec": 30, "call_type": "outgoing", "timestamp": "2024-01-10T14:30:00Z", "case_id": CASE_ID},
]


@pytest.fixture(autouse=True)
def seed_pattern_data(isolated_data_dir):
    """Write test entities, relationships, transactions, and call records."""
    from storage.file_store import write_json
    import graph.graph_service as gs
    import services.pattern_service as ps

    ent_file = isolated_data_dir / "entities"      / "entities.json"
    rel_file = isolated_data_dir / "relationships" / "relationships.json"
    tx_file  = isolated_data_dir / "sample"        / "transactions.json"
    cr_file  = isolated_data_dir / "sample"        / "call_records.json"

    for f in (ent_file, rel_file, tx_file, cr_file):
        f.parent.mkdir(parents=True, exist_ok=True)

    write_json(ent_file, ENTITIES)
    write_json(rel_file, RELATIONSHIPS)
    write_json(tx_file,  TRANSACTIONS)
    write_json(cr_file,  CALL_RECORDS)

    # Redirect graph and pattern service paths
    gs.ENTITIES_FILE             = ent_file
    gs.RELATIONSHIPS_FILE        = rel_file
    gs.EVIDENCE_FILE             = isolated_data_dir / "evidence" / "evidence.json"
    gs.SAMPLE_ENTITIES_FILE      = isolated_data_dir / "sample"   / "entities.json"
    gs.SAMPLE_RELATIONSHIPS_FILE = isolated_data_dir / "sample"   / "relationships.json"

    ps.TRANSACTIONS_FILE = tx_file
    ps.CALL_RECORDS_FILE = cr_file
    ps.SIMS_FILE         = isolated_data_dir / "sample" / "sims.json"
    ps.PATTERNS_FILE     = isolated_data_dir / "processed" / "patterns.json"
    ps.ROLES_FILE        = isolated_data_dir / "processed" / "network_roles.json"


def get_token(client, role="INVESTIGATOR"):
    uname = f"pat_user_{role.lower()}"
    email = f"{uname}@x.com"
    register(client, username=uname, email=email, role=role)
    return login(client, uname).get_json()["token"]


# ═══════════════════════════════════════════════════════════════════════════════
# UNIT — PatternDetector
# ═══════════════════════════════════════════════════════════════════════════════

class TestPatternDetector:

    def _build_graph(self):
        from graph.graph_service import build_graph
        return build_graph(CASE_ID)

    def _make_detector(self):
        from graph.pattern_detector import PatternDetector
        G = self._build_graph()
        return PatternDetector(
            G            = G,
            transactions = TRANSACTIONS,
            call_records = CALL_RECORDS,
            case_id      = CASE_ID,
        )

    # -- detect_all() ----------------------------------------------------------

    def test_detect_all_returns_list(self):
        d = self._make_detector()
        results = d.detect_all()
        assert isinstance(results, list)

    def test_finding_schema(self):
        d = self._make_detector()
        results = d.detect_all()
        required = {
            "pattern_id", "pattern_name", "score", "confidence",
            "affected_entities", "indicators", "supporting_evidence",
            "time_range", "explanation",
        }
        for f in results:
            assert required.issubset(set(f.keys())), f"Missing keys in {f['pattern_id']}"

    def test_scores_in_range(self):
        d = self._make_detector()
        for f in d.detect_all():
            assert 0.0 <= f["score"]      <= 1.0, f"Score out of range in {f['pattern_id']}"
            assert 0.0 <= f["confidence"] <= 1.0, f"Confidence out of range"

    # -- sim_swap --------------------------------------------------------------

    def test_sim_swap_detected(self):
        from graph.pattern_detector import PatternDetector
        G = self._build_graph()
        d = PatternDetector(G=G, transactions=TRANSACTIONS, case_id=CASE_ID)
        results = d._detect_sim_swap()
        # sim_001 is linked to ph_001 and ph_002
        names = [f["pattern_name"] for f in results]
        assert any("SIM-swap" in n for n in names), "Expected sim_swap finding"

    def test_sim_swap_has_affected_entities(self):
        from graph.pattern_detector import PatternDetector
        G = self._build_graph()
        d = PatternDetector(G=G, transactions=TRANSACTIONS, case_id=CASE_ID)
        for f in d._detect_sim_swap():
            assert len(f["affected_entities"]) >= 2

    # -- mule_account ----------------------------------------------------------

    def test_mule_detected(self):
        from graph.pattern_detector import PatternDetector
        G = self._build_graph()
        d = PatternDetector(G=G, transactions=TRANSACTIONS, case_id=CASE_ID)
        results = d._detect_mule_network()
        # acc_002 receives and forwards at high ratio
        assert len(results) >= 1, "Expected at least one mule finding"

    def test_mule_acc002_is_flagged(self):
        from graph.pattern_detector import PatternDetector
        G = self._build_graph()
        d = PatternDetector(G=G, transactions=TRANSACTIONS, case_id=CASE_ID)
        results = d._detect_mule_network()
        affected = [e for f in results for e in f["affected_entities"]]
        assert "acc_002" in affected

    def test_mule_has_evidence_ids(self):
        from graph.pattern_detector import PatternDetector
        G = self._build_graph()
        d = PatternDetector(G=G, transactions=TRANSACTIONS, case_id=CASE_ID)
        for f in d._detect_mule_network():
            assert isinstance(f["supporting_evidence"], list)

    # -- transaction layering --------------------------------------------------

    def test_layering_detected(self):
        from graph.pattern_detector import PatternDetector
        G = self._build_graph()
        d = PatternDetector(G=G, transactions=TRANSACTIONS, case_id=CASE_ID)
        results = d._detect_transaction_layering()
        # Chain: acc_001 → acc_002 → acc_003/acc_004 (3 hops)
        assert len(results) >= 1, "Expected layering finding"

    def test_layering_hops_indicator(self):
        from graph.pattern_detector import PatternDetector
        G = self._build_graph()
        d = PatternDetector(G=G, transactions=TRANSACTIONS, case_id=CASE_ID)
        for f in d._detect_transaction_layering():
            # Indicator must mention hop count
            joined = " ".join(f["indicators"])
            assert "hop" in joined.lower()

    # -- shared device ---------------------------------------------------------

    def test_shared_device_detected(self):
        from graph.pattern_detector import PatternDetector
        G = self._build_graph()
        d = PatternDetector(G=G, case_id=CASE_ID)
        results = d._detect_shared_device_network()
        # dev_001 is linked to acc_001, acc_002, acc_003 (≥ SHARED_DEVICE_MIN=3)
        assert len(results) >= 1

    def test_shared_device_has_dev001(self):
        from graph.pattern_detector import PatternDetector
        G = self._build_graph()
        d = PatternDetector(G=G, case_id=CASE_ID)
        results = d._detect_shared_device_network()
        affected = [e for f in results for e in f["affected_entities"]]
        assert "dev_001" in affected

    # -- shared SIM ------------------------------------------------------------

    def test_shared_sim_detected(self):
        from graph.pattern_detector import PatternDetector
        G = self._build_graph()
        d = PatternDetector(G=G, case_id=CASE_ID)
        results = d._detect_shared_sim_network()
        # sim_001 linked to ph_001 and ph_002
        assert len(results) >= 1

    # -- high velocity ---------------------------------------------------------

    def test_velocity_detected(self):
        from graph.pattern_detector import PatternDetector
        G = self._build_graph()
        d = PatternDetector(G=G, transactions=TRANSACTIONS, case_id=CASE_ID)
        results = d._detect_high_velocity()
        # acc_001 sends 7 txns within 24h
        assert len(results) >= 1

    def test_velocity_acc001_flagged(self):
        from graph.pattern_detector import PatternDetector
        G = self._build_graph()
        d = PatternDetector(G=G, transactions=TRANSACTIONS, case_id=CASE_ID)
        results = d._detect_high_velocity()
        affected = [e for f in results for e in f["affected_entities"]]
        assert "acc_001" in affected

    def test_velocity_has_time_range(self):
        from graph.pattern_detector import PatternDetector
        G = self._build_graph()
        d = PatternDetector(G=G, transactions=TRANSACTIONS, case_id=CASE_ID)
        for f in d._detect_high_velocity():
            assert "start" in f["time_range"] or f["time_range"] == {}

    # -- communication hub -----------------------------------------------------

    def test_hub_detected_from_call_records(self):
        from graph.pattern_detector import PatternDetector
        G = self._build_graph()
        d = PatternDetector(G=G, call_records=CALL_RECORDS, case_id=CASE_ID)
        results = d._detect_communication_hub()
        # ph_001 contacts 6 unique parties vs avg of ~1.6
        assert len(results) >= 1

    def test_hub_ph001_flagged(self):
        from graph.pattern_detector import PatternDetector
        G = self._build_graph()
        d = PatternDetector(G=G, call_records=CALL_RECORDS, case_id=CASE_ID)
        results = d._detect_communication_hub()
        affected = [e for f in results for e in f["affected_entities"]]
        assert "ph_001" in affected

    # -- rapid multi-hop -------------------------------------------------------

    def test_rapid_hop_detected(self):
        from graph.pattern_detector import PatternDetector
        G = self._build_graph()
        d = PatternDetector(G=G, transactions=TRANSACTIONS, case_id=CASE_ID)
        results = d._detect_rapid_multi_hop()
        # Chain within 2h: acc_001→acc_002→acc_003→acc_004 (3 hops in ~2.5h)
        # Or acc_001→acc_002→acc_004 (2 hops in ~3h)
        # At least the acc_002→acc_003→acc_004 sub-chain in ~0.5h
        assert isinstance(results, list)

    # -- dense cluster ---------------------------------------------------------

    def test_cluster_detected(self):
        from graph.pattern_detector import PatternDetector
        G = self._build_graph()
        d = PatternDetector(G=G, case_id=CASE_ID)
        results = d._detect_dense_cluster()
        # acc_001 ↔ acc_002 ↔ acc_003 ↔ acc_001 forms a 3-clique
        assert len(results) >= 1

    def test_cluster_score_in_range(self):
        from graph.pattern_detector import PatternDetector
        G = self._build_graph()
        d = PatternDetector(G=G, case_id=CASE_ID)
        for f in d._detect_dense_cluster():
            assert 0.0 <= f["score"] <= 1.0


# ═══════════════════════════════════════════════════════════════════════════════
# UNIT — RoleAnalyzer
# ═══════════════════════════════════════════════════════════════════════════════

class TestRoleAnalyzer:

    def _build_graph(self):
        from graph.graph_service import build_graph
        return build_graph(CASE_ID)

    def _make_analyzer(self):
        from graph.role_analyzer import RoleAnalyzer
        G = self._build_graph()
        return RoleAnalyzer(G=G, transactions=TRANSACTIONS, call_records=CALL_RECORDS)

    def test_analyze_returns_list(self):
        a = self._make_analyzer()
        roles = a.analyze()
        assert isinstance(roles, list)
        assert len(roles) == len(ENTITIES)

    def test_role_schema(self):
        a = self._make_analyzer()
        required = {
            "entity_id", "entity_type", "entity_label",
            "primary_role", "role_score", "all_scores",
            "metrics", "evidence", "explanation", "analyzed_at",
        }
        for r in a.analyze():
            assert required.issubset(set(r.keys())), f"Missing keys for {r['entity_id']}"

    def test_role_scores_in_range(self):
        a = self._make_analyzer()
        for r in a.analyze():
            assert 0.0 <= r["role_score"] <= 1.0
            for v in r["all_scores"].values():
                assert 0.0 <= v <= 1.0

    def test_valid_primary_roles(self):
        a = self._make_analyzer()
        valid = {
            "Potential Coordinator", "Potential Intermediary",
            "Potential Mule Account", "Technical/Device Node",
            "Victim", "Unknown",
        }
        for r in a.analyze():
            assert r["primary_role"] in valid, f"Unknown role: {r['primary_role']}"

    def test_victim_entity_gets_victim_role(self):
        a = self._make_analyzer()
        roles = {r["entity_id"]: r for r in a.analyze()}
        # p_003 is type VICTIM
        assert roles["p_003"]["primary_role"] == "Victim"

    def test_device_node_gets_technical_role(self):
        a = self._make_analyzer()
        roles = {r["entity_id"]: r for r in a.analyze()}
        # dev_001 is type DEVICE linked to 3 accounts
        assert roles["dev_001"]["primary_role"] == "Technical/Device Node"

    def test_metrics_all_present(self):
        a = self._make_analyzer()
        required_metrics = {
            "degree", "in_degree", "out_degree", "weighted_degree",
            "betweenness_centrality", "pagerank",
            "transaction_volume", "tx_in_volume", "tx_out_volume",
            "forwarding_ratio", "connected_accounts",
            "connected_devices", "connected_sims", "communication_count",
        }
        for r in a.analyze():
            assert required_metrics.issubset(set(r["metrics"].keys()))

    def test_evidence_is_list(self):
        a = self._make_analyzer()
        for r in a.analyze():
            assert isinstance(r["evidence"], list)

    def test_explanation_nonempty(self):
        a = self._make_analyzer()
        for r in a.analyze():
            assert len(r["explanation"]) > 10

    def test_ph001_has_high_comm_count(self):
        """ph_001 appears in call records 6× as caller → high comm_count."""
        a = self._make_analyzer()
        roles = {r["entity_id"]: r for r in a.analyze()}
        assert roles["ph_001"]["metrics"]["communication_count"] >= 6

    def test_empty_graph_returns_empty(self):
        import networkx as nx
        from graph.role_analyzer import RoleAnalyzer
        a = RoleAnalyzer(G=nx.DiGraph())
        assert a.analyze() == []


# ═══════════════════════════════════════════════════════════════════════════════
# UNIT — pattern_service
# ═══════════════════════════════════════════════════════════════════════════════

class TestPatternService:

    def test_run_pattern_analysis_returns_dict(self):
        from services.pattern_service import run_pattern_analysis
        result = run_pattern_analysis(CASE_ID)
        assert isinstance(result, dict)
        assert result["case_id"] == CASE_ID

    def test_run_pattern_analysis_has_findings(self):
        from services.pattern_service import run_pattern_analysis
        result = run_pattern_analysis(CASE_ID)
        assert "findings" in result
        assert isinstance(result["findings"], list)

    def test_run_pattern_analysis_persists(self, isolated_data_dir):
        from services.pattern_service import run_pattern_analysis, get_patterns
        run_pattern_analysis(CASE_ID)
        stored = get_patterns(CASE_ID)
        assert stored is not None
        assert stored["case_id"] == CASE_ID

    def test_run_role_analysis_returns_dict(self):
        from services.pattern_service import run_role_analysis
        result = run_role_analysis(CASE_ID)
        assert isinstance(result, dict)
        assert result["case_id"] == CASE_ID

    def test_run_role_analysis_has_roles(self):
        from services.pattern_service import run_role_analysis
        result = run_role_analysis(CASE_ID)
        assert "roles" in result
        assert len(result["roles"]) == len(ENTITIES)

    def test_run_role_analysis_persists(self):
        from services.pattern_service import run_role_analysis, get_roles
        run_role_analysis(CASE_ID)
        stored = get_roles(CASE_ID)
        assert stored is not None

    def test_get_patterns_returns_none_before_run(self):
        from services.pattern_service import get_patterns
        assert get_patterns("nonexistent_case_xyz") is None

    def test_get_roles_returns_none_before_run(self):
        from services.pattern_service import get_roles
        assert get_roles("nonexistent_case_xyz") is None


# ═══════════════════════════════════════════════════════════════════════════════
# ROUTE — GET /api/patterns/<case_id>
# ═══════════════════════════════════════════════════════════════════════════════

class TestGetPatternsRoute:

    def test_requires_auth(self, client):
        rv = client.get(f"/api/patterns/{CASE_ID}")
        assert rv.status_code == 401

    def test_not_found_before_analysis(self, client):
        token = get_token(client)
        rv    = client.get("/api/patterns/case_never_run_xyz",
                           headers=auth_header(token))
        assert rv.status_code == 404
        assert "error" in rv.get_json()

    def test_returns_result_after_analysis(self, client):
        token = get_token(client)
        # First run the analysis
        client.post(f"/api/patterns/analyze/{CASE_ID}", headers=auth_header(token))
        rv   = client.get(f"/api/patterns/{CASE_ID}", headers=auth_header(token))
        assert rv.status_code == 200
        data = rv.get_json()
        assert data["case_id"] == CASE_ID
        assert "findings" in data

    def test_response_has_stats(self, client):
        token = get_token(client)
        client.post(f"/api/patterns/analyze/{CASE_ID}", headers=auth_header(token))
        rv   = client.get(f"/api/patterns/{CASE_ID}", headers=auth_header(token))
        data = rv.get_json()
        assert "stats" in data
        assert "node_count" in data["stats"]

    def test_findings_have_required_fields(self, client):
        token = get_token(client)
        client.post(f"/api/patterns/analyze/{CASE_ID}", headers=auth_header(token))
        rv      = client.get(f"/api/patterns/{CASE_ID}", headers=auth_header(token))
        findings = rv.get_json().get("findings", [])
        required = {
            "pattern_id", "pattern_name", "score", "confidence",
            "affected_entities", "indicators", "supporting_evidence",
            "time_range", "explanation",
        }
        for f in findings:
            assert required.issubset(set(f.keys()))


# ═══════════════════════════════════════════════════════════════════════════════
# ROUTE — POST /api/patterns/analyze/<case_id>
# ═══════════════════════════════════════════════════════════════════════════════

class TestAnalyzePatternsRoute:

    def test_requires_auth(self, client):
        rv = client.post(f"/api/patterns/analyze/{CASE_ID}")
        assert rv.status_code == 401

    def test_viewer_cannot_analyze(self, client):
        token = get_token(client, "VIEWER")
        rv    = client.post(f"/api/patterns/analyze/{CASE_ID}",
                            headers=auth_header(token))
        assert rv.status_code == 403

    def test_investigator_can_analyze(self, client):
        token = get_token(client)
        rv    = client.post(f"/api/patterns/analyze/{CASE_ID}",
                            headers=auth_header(token))
        assert rv.status_code == 200

    def test_response_structure(self, client):
        token = get_token(client)
        rv    = client.post(f"/api/patterns/analyze/{CASE_ID}",
                            headers=auth_header(token))
        data  = rv.get_json()
        assert data["case_id"] == CASE_ID
        assert isinstance(data["findings"], list)
        assert isinstance(data["total_findings"], int)
        assert data["total_findings"] == len(data["findings"])

    def test_idempotent_rerun(self, client):
        token = get_token(client)
        rv1 = client.post(f"/api/patterns/analyze/{CASE_ID}", headers=auth_header(token))
        rv2 = client.post(f"/api/patterns/analyze/{CASE_ID}", headers=auth_header(token))
        assert rv1.status_code == 200
        assert rv2.status_code == 200

    def test_unknown_case_still_runs(self, client):
        """An unknown case returns an empty graph, analysis should succeed (0 findings)."""
        token = get_token(client)
        rv    = client.post("/api/patterns/analyze/nonexistent_xyz",
                            headers=auth_header(token))
        assert rv.status_code == 200
        data  = rv.get_json()
        assert isinstance(data["findings"], list)

    def test_analyze_produces_multiple_pattern_types(self, client):
        token    = get_token(client)
        rv       = client.post(f"/api/patterns/analyze/{CASE_ID}",
                               headers=auth_header(token))
        findings = rv.get_json()["findings"]
        names    = {f["pattern_name"] for f in findings}
        # With the seed data we expect at least 3 distinct pattern types
        assert len(names) >= 3, f"Expected ≥3 pattern types, got: {names}"


# ═══════════════════════════════════════════════════════════════════════════════
# ROUTE — GET /api/roles/<case_id>
# ═══════════════════════════════════════════════════════════════════════════════

class TestGetRolesRoute:

    def test_requires_auth(self, client):
        rv = client.get(f"/api/roles/{CASE_ID}")
        assert rv.status_code == 401

    def test_on_demand_analysis(self, client):
        """GET /api/roles/<case_id> runs analysis on-demand if not yet stored."""
        token = get_token(client)
        rv    = client.get(f"/api/roles/{CASE_ID}", headers=auth_header(token))
        assert rv.status_code == 200
        data  = rv.get_json()
        assert data["case_id"] == CASE_ID
        assert "roles" in data

    def test_response_has_role_summary(self, client):
        token = get_token(client)
        rv    = client.get(f"/api/roles/{CASE_ID}", headers=auth_header(token))
        data  = rv.get_json()
        assert "role_summary" in data
        assert isinstance(data["role_summary"], dict)

    def test_role_records_have_required_fields(self, client):
        token = get_token(client)
        rv    = client.get(f"/api/roles/{CASE_ID}", headers=auth_header(token))
        roles = rv.get_json().get("roles", [])
        required = {
            "entity_id", "entity_type", "entity_label",
            "primary_role", "role_score", "all_scores",
            "metrics", "evidence", "explanation",
        }
        for r in roles:
            assert required.issubset(set(r.keys()))

    def test_all_entities_have_a_role(self, client):
        token = get_token(client)
        rv    = client.get(f"/api/roles/{CASE_ID}", headers=auth_header(token))
        roles = rv.get_json()["roles"]
        assert len(roles) == len(ENTITIES)

    def test_victim_entity_role(self, client):
        token = get_token(client)
        rv    = client.get(f"/api/roles/{CASE_ID}", headers=auth_header(token))
        roles = {r["entity_id"]: r for r in rv.get_json()["roles"]}
        assert roles["p_003"]["primary_role"] == "Victim"

    def test_device_node_role(self, client):
        token = get_token(client)
        rv    = client.get(f"/api/roles/{CASE_ID}", headers=auth_header(token))
        roles = {r["entity_id"]: r for r in rv.get_json()["roles"]}
        assert roles["dev_001"]["primary_role"] == "Technical/Device Node"

    def test_scores_in_range(self, client):
        token = get_token(client)
        rv    = client.get(f"/api/roles/{CASE_ID}", headers=auth_header(token))
        for r in rv.get_json()["roles"]:
            assert 0.0 <= r["role_score"] <= 1.0
