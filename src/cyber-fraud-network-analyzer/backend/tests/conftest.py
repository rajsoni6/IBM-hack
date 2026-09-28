"""
tests/conftest.py
Shared pytest fixtures for all backend tests.
"""

import sys
from pathlib import Path

import pytest

# Ensure backend root is on the path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

# Point DATA_DIR at a temp dir so tests never touch real data
@pytest.fixture(scope="session", autouse=True)
def isolated_data_dir(tmp_path_factory):
    """
    Create a throw-away data directory for the entire test session
    and patch config.settings.DATA_DIR before any imports that use it.
    """
    tmp = tmp_path_factory.mktemp("cfna_data")
    # Patch at the module level BEFORE importing settings-dependent modules
    import config.settings as _cfg
    _cfg.DATA_DIR = tmp

    # Re-point service constants that were already imported at module load
    import services.auth_service as _auth
    _auth.USERS_FILE = tmp / "users" / "users.json"

    import services.cases_service as _cases
    _cases.CASES_FILE = tmp / "cases" / "cases.json"

    import services.intelligence_service as _intel
    _intel.RAW_DIR       = tmp / "raw"
    _intel.PROCESSED_DIR = tmp / "processed"
    _intel.EVIDENCE_FILE = tmp / "evidence" / "evidence.json"

    import services.extraction_service as _extract
    _extract.ENTITIES_FILE      = tmp / "entities"      / "entities.json"
    _extract.RELATIONSHIPS_FILE = tmp / "relationships" / "relationships.json"

    import graph.graph_service as _graph
    _graph.ENTITIES_FILE             = tmp / "entities"      / "entities.json"
    _graph.RELATIONSHIPS_FILE        = tmp / "relationships" / "relationships.json"
    _graph.EVIDENCE_FILE             = tmp / "evidence"      / "evidence.json"
    _graph.SAMPLE_ENTITIES_FILE      = tmp / "sample"        / "entities.json"
    _graph.SAMPLE_RELATIONSHIPS_FILE = tmp / "sample"        / "relationships.json"

    import services.pattern_service as _pat
    _pat.PATTERNS_FILE     = tmp / "processed" / "patterns.json"
    _pat.ROLES_FILE        = tmp / "processed" / "network_roles.json"
    _pat.TRANSACTIONS_FILE = tmp / "sample"    / "transactions.json"
    _pat.CALL_RECORDS_FILE = tmp / "sample"    / "call_records.json"
    _pat.SIMS_FILE         = tmp / "sample"    / "sims.json"

    import ml.predictor as _predictor
    _predictor.PREDICTIONS_FILE = tmp / "predictions" / "predictions.json"

    import services.timeline_service as _timeline
    _timeline.TRANSACTIONS_FILE   = tmp / "sample" / "transactions.json"
    _timeline.CALL_RECORDS_FILE   = tmp / "sample" / "call_records.json"
    _timeline.SIMS_FILE           = tmp / "sample" / "sims.json"
    _timeline.DEVICES_FILE        = tmp / "sample" / "devices.json"
    _timeline.ENTITIES_FILE       = tmp / "entities" / "entities.json"
    _timeline.EVIDENCE_FILE       = tmp / "evidence" / "evidence.json"
    _timeline.CASES_FILE          = tmp / "cases"    / "cases.json"
    _timeline.SAMPLE_EVIDENCE_FILE= tmp / "sample"   / "evidence.json"

    import services.evidence_service as _evidence
    _evidence.EVIDENCE_FILE        = tmp / "evidence"      / "evidence.json"
    _evidence.SAMPLE_EVIDENCE_FILE = tmp / "sample"        / "evidence.json"
    _evidence.ENTITIES_FILE        = tmp / "entities"      / "entities.json"
    _evidence.RELATIONSHIPS_FILE   = tmp / "relationships" / "relationships.json"

    import services.ai_summary_service as _summary
    _summary.REPORTS_DIR   = tmp / "reports"
    _summary.CASES_FILE    = tmp / "cases"    / "cases.json"
    _summary.ENTITIES_FILE = tmp / "entities" / "entities.json"

    # Patch audit module to use isolated dir
    import utils.audit as _audit
    _audit.AUDIT_DIR  = tmp / "audit"
    _audit.AUDIT_FILE = tmp / "audit" / "audit_logs.json"

    return tmp


@pytest.fixture
def app(isolated_data_dir):
    from app import create_app
    application = create_app()
    application.config["TESTING"] = True
    application.config["SECRET_KEY"] = "test-secret-key"
    # Disable rate limiting in tests
    application.config["RATELIMIT_ENABLED"] = False
    return application


@pytest.fixture
def client(app):
    with app.test_client() as c:
        yield c


# Class-scoped fixtures for E2E tests
@pytest.fixture(scope="class")
def app_class(isolated_data_dir):
    from app import create_app
    application = create_app()
    application.config["TESTING"] = True
    application.config["SECRET_KEY"] = "test-secret-key"
    application.config["RATELIMIT_ENABLED"] = False
    return application


# ── Reusable helpers ──────────────────────────────────────────────────────────

def register(client, username="testuser", email="test@example.com",
             password="Test1234", role="INVESTIGATOR"):
    return client.post("/api/auth/register", json={
        "username":  username,
        "email":     email,
        "password":  password,
        "role":      role,
        "full_name": "Test User",
    })


def login(client, credential="testuser", password="Test1234"):
    return client.post("/api/auth/login", json={
        "username": credential,
        "password": password,
    })


def auth_header(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}
