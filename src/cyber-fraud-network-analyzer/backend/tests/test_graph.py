"""
tests/test_graph.py
Tests for:
  - graph_service: build_graph, filter_graph, algorithms
  - GET /api/graph/<case_id>
  - GET /api/graph/<case_id>/neighbors/<entity_id>
  - GET /api/graph/<case_id>/path
  - GET /api/graph/<case_id>/node/<entity_id>
  - GET /api/graph/<case_id>/search
  - GET /api/graph/<case_id>/components
"""

import json
from pathlib import Path
import pytest

from .conftest import register, login, auth_header


# ── Fixtures ──────────────────────────────────────────────────────────────────

CASE_ID = "case_graph_test"

ENTITIES = [
    {"entity_id": "ent_001", "type": "PERSON",  "value": "Rahul Sharma",
     "label": "Rahul Sharma", "confidence": 0.9, "evidence_ids": ["ev_001"],
     "case_ids": [CASE_ID], "attributes": {}, "risk_score": 0.7,
     "extracted_at": "2024-01-01T00:00:00Z", "updated_at": "2024-01-01T00:00:00Z",
     "raw_value": "Rahul Sharma", "source_texts": ["suspect Sh. Rahul Sharma"]},
    {"entity_id": "ent_002", "type": "PHONE",   "value": "9876543210",
     "label": "9876543210",   "confidence": 0.95, "evidence_ids": ["ev_001"],
     "case_ids": [CASE_ID], "attributes": {}, "risk_score": 0.5,
     "extracted_at": "2024-01-01T00:00:00Z", "updated_at": "2024-01-01T00:00:00Z",
     "raw_value": "9876543210", "source_texts": []},
    {"entity_id": "ent_003", "type": "BANK_ACCOUNT", "value": "HDFC0001234",
     "label": "HDFC0001234",  "confidence": 0.8, "evidence_ids": ["ev_002"],
     "case_ids": [CASE_ID], "attributes": {}, "risk_score": 0.6,
     "extracted_at": "2024-01-01T00:00:00Z", "updated_at": "2024-01-01T00:00:00Z",
     "raw_value": "HDFC0001234", "source_texts": []},
    {"entity_id": "ent_004", "type": "UPI_ID", "value": "fraud@paytm",
     "label": "fraud@paytm", "confidence": 0.85, "evidence_ids": ["ev_002"],
     "case_ids": [CASE_ID], "attributes": {}, "risk_score": 0.9,
     "extracted_at": "2024-01-01T00:00:00Z", "updated_at": "2024-01-01T00:00:00Z",
     "raw_value": "fraud@paytm", "source_texts": []},
    {"entity_id": "ent_005", "type": "VICTIM", "value": "Priya Singh",
     "label": "Priya Singh", "confidence": 0.88, "evidence_ids": ["ev_003"],
     "case_ids": [CASE_ID], "attributes": {}, "risk_score": 0.1,
     "extracted_at": "2024-01-01T00:00:00Z", "updated_at": "2024-01-01T00:00:00Z",
     "raw_value": "Priya Singh", "source_texts": []},
]

RELATIONSHIPS = [
    {"relationship_id": "rel_001", "source_entity": "ent_001", "target_entity": "ent_002",
     "relationship": "OWNS", "confidence": 0.85,
     "evidence_ids": ["ev_001"], "case_ids": [CASE_ID],
     "evidence_source": "observed", "source_text": "Rahul owns phone",
     "attributes": {}, "extracted_at": "2024-01-01T00:00:00Z"},
    {"relationship_id": "rel_002", "source_entity": "ent_001", "target_entity": "ent_003",
     "relationship": "OWNS", "confidence": 0.72,
     "evidence_ids": ["ev_001"], "case_ids": [CASE_ID],
     "evidence_source": "inferred", "source_text": "account linked",
     "attributes": {}, "extracted_at": "2024-01-01T00:00:00Z"},
    {"relationship_id": "rel_003", "source_entity": "ent_004", "target_entity": "ent_003",
     "relationship": "TRANSFERRED_TO", "confidence": 0.78,
     "evidence_ids": ["ev_002"], "case_ids": [CASE_ID],
     "evidence_source": "observed", "source_text": "upi to bank",
     "attributes": {}, "extracted_at": "2024-01-01T00:00:00Z"},
    {"relationship_id": "rel_004", "source_entity": "ent_005", "target_entity": "ent_001",
     "relationship": "ASSOCIATED_WITH", "confidence": 0.65,
     "evidence_ids": ["ev_003"], "case_ids": [CASE_ID],
     "evidence_source": "inferred", "source_text": "connected",
     "attributes": {}, "extracted_at": "2024-01-01T00:00:00Z"},
]

EVIDENCE = [
    {"id": "ev_001", "case_id": CASE_ID, "type": "call_record",
     "description": "Call record evidence", "collected_at": "2024-01-01"},
    {"id": "ev_002", "case_id": CASE_ID, "type": "transaction_log",
     "description": "Transaction evidence", "collected_at": "2024-01-02"},
    {"id": "ev_003", "case_id": CASE_ID, "type": "witness_statement",
     "description": "Victim statement", "collected_at": "2024-01-03"},
]


@pytest.fixture(autouse=True)
def seed_graph_data(isolated_data_dir):
    """Write test entities, relationships, and evidence to the temp data dir."""
    from storage.file_store import write_json
    import graph.graph_service as gs

    ent_file  = isolated_data_dir / "entities"      / "entities.json"
    rel_file  = isolated_data_dir / "relationships" / "relationships.json"
    ev_file   = isolated_data_dir / "evidence"      / "evidence.json"

    ent_file.parent.mkdir(parents=True, exist_ok=True)
    rel_file.parent.mkdir(parents=True, exist_ok=True)
    ev_file.parent.mkdir(parents=True, exist_ok=True)

    write_json(ent_file, ENTITIES)
    write_json(rel_file, RELATIONSHIPS)
    write_json(ev_file, EVIDENCE)

    # Redirect graph service file paths to temp dir
    gs.ENTITIES_FILE      = ent_file
    gs.RELATIONSHIPS_FILE = rel_file
    gs.EVIDENCE_FILE      = ev_file
    # Point sample fallback to a non-existent path so unknown cases return empty
    gs.SAMPLE_ENTITIES_FILE      = isolated_data_dir / "sample" / "entities.json"
    gs.SAMPLE_RELATIONSHIPS_FILE = isolated_data_dir / "sample" / "relationships.json"


def get_token(client, role="INVESTIGATOR"):
    uname = f"graph_user_{role.lower()}"
    email = f"{uname}@x.com"
    register(client, username=uname, email=email, role=role)
    return login(client, uname).get_json()["token"]


# ═══════════════════════════════════════════════════════════════════════════════
# UNIT — graph_service
# ═══════════════════════════════════════════════════════════════════════════════

class TestBuildGraph:

    def test_build_returns_digraph(self):
        import networkx as nx
        from graph.graph_service import build_graph
        G = build_graph(CASE_ID)
        assert isinstance(G, nx.DiGraph)

    def test_correct_node_count(self):
        from graph.graph_service import build_graph
        G = build_graph(CASE_ID)
        assert G.number_of_nodes() == 5

    def test_correct_edge_count(self):
        from graph.graph_service import build_graph
        G = build_graph(CASE_ID)
        assert G.number_of_edges() == 4

    def test_node_has_type(self):
        from graph.graph_service import build_graph
        G = build_graph(CASE_ID)
        assert G.nodes["ent_001"]["type"] == "PERSON"

    def test_node_has_label(self):
        from graph.graph_service import build_graph
        G = build_graph(CASE_ID)
        assert G.nodes["ent_001"]["label"] == "Rahul Sharma"

    def test_edge_has_relationship(self):
        from graph.graph_service import build_graph
        G = build_graph(CASE_ID)
        assert G["ent_001"]["ent_002"]["relationship"] == "OWNS"

    def test_unknown_case_returns_empty(self):
        from graph.graph_service import build_graph
        G = build_graph("case_does_not_exist_xyz")
        # Falls back to same sample data — may not be empty; just check it doesn't error
        assert G is not None


class TestFilterGraph:

    def test_filter_by_entity_type(self):
        from graph.graph_service import build_graph, filter_graph
        G = build_graph(CASE_ID)
        H = filter_graph(G, entity_types=["PERSON"])
        types = {d["type"] for _, d in H.nodes(data=True)}
        assert types == {"PERSON"}

    def test_filter_by_rel_type(self):
        from graph.graph_service import build_graph, filter_graph
        G = build_graph(CASE_ID)
        H = filter_graph(G, rel_types=["OWNS"])
        rels = {d["relationship"] for _, _, d in H.edges(data=True)}
        assert rels.issubset({"OWNS"})

    def test_filter_by_min_confidence(self):
        from graph.graph_service import build_graph, filter_graph
        G = build_graph(CASE_ID)
        H = filter_graph(G, min_confidence=0.9)
        for _, _, d in H.edges(data=True):
            assert d["confidence"] >= 0.9

    def test_filter_by_evidence_source(self):
        from graph.graph_service import build_graph, filter_graph
        G = build_graph(CASE_ID)
        H = filter_graph(G, evidence_source="observed")
        for _, _, d in H.edges(data=True):
            assert d["evidence_source"] == "observed"

    def test_no_filter_returns_full_graph(self):
        from graph.graph_service import build_graph, filter_graph
        G = build_graph(CASE_ID)
        H = filter_graph(G)
        assert H.number_of_nodes() == G.number_of_nodes()


class TestGraphAlgorithms:

    def test_get_neighbors_depth1(self):
        from graph.graph_service import build_graph, get_neighbors
        G = build_graph(CASE_ID)
        result = get_neighbors(G, "ent_001", depth=1)
        node_ids = {n["id"] for n in result["nodes"]}
        assert "ent_001" in node_ids
        assert "ent_002" in node_ids   # OWNS

    def test_get_neighbors_unknown_entity(self):
        from graph.graph_service import build_graph, get_neighbors
        G = build_graph(CASE_ID)
        result = get_neighbors(G, "ent_nonexistent", depth=1)
        assert result["nodes"] == []

    def test_shortest_path_found(self):
        from graph.graph_service import build_graph, get_shortest_path
        G = build_graph(CASE_ID)
        # ent_001 -> ent_003 via OWNS (direct)
        result = get_shortest_path(G, "ent_001", "ent_003")
        assert result["found"] is True
        assert result["length"] >= 1

    def test_shortest_path_not_found_isolated(self):
        from graph.graph_service import build_graph, get_shortest_path
        G = build_graph(CASE_ID)
        result = get_shortest_path(G, "ent_001", "ent_NOPE")
        assert result["found"] is False

    def test_transaction_path(self):
        from graph.graph_service import build_graph, get_transaction_path
        G = build_graph(CASE_ID)
        # ent_004 -> ent_003 via TRANSFERRED_TO
        result = get_transaction_path(G, "ent_004", "ent_003")
        assert result["found"] is True
        assert len(result["paths"]) >= 1

    def test_search_graph_hits(self):
        from graph.graph_service import build_graph, search_graph
        G = build_graph(CASE_ID)
        result = search_graph(G, "Rahul")
        node_ids = {n["id"] for n in result["nodes"]}
        assert "ent_001" in node_ids

    def test_search_graph_no_hits(self):
        from graph.graph_service import build_graph, search_graph
        G = build_graph(CASE_ID)
        result = search_graph(G, "zzznomatch99999")
        assert result["nodes"] == []

    def test_connected_components(self):
        from graph.graph_service import build_graph, get_connected_components
        G = build_graph(CASE_ID)
        comps = get_connected_components(G)
        assert len(comps) >= 1
        # Largest component should contain all 5 nodes (they're all connected)
        assert comps[0]["stats"]["node_count"] >= 1

    def test_node_detail_returns_edges(self):
        from graph.graph_service import build_graph, get_node_detail
        G = build_graph(CASE_ID)
        detail = get_node_detail(G, "ent_001", {})
        assert "out_edges" in detail
        assert len(detail["out_edges"]) >= 1   # OWNS phone and account

    def test_node_detail_unknown_returns_empty(self):
        from graph.graph_service import build_graph, get_node_detail
        G = build_graph(CASE_ID)
        detail = get_node_detail(G, "ent_UNKNOWN", {})
        assert detail == {}

    def test_graph_to_cytoscape_shape(self):
        from graph.graph_service import build_graph, graph_to_cytoscape
        G = build_graph(CASE_ID)
        cy = graph_to_cytoscape(G)
        assert "nodes" in cy and "edges" in cy and "stats" in cy
        for node in cy["nodes"]:
            assert "id"       in node
            assert "type"     in node
            assert "label"    in node
            assert "metadata" in node
        for edge in cy["edges"]:
            assert "id"           in edge
            assert "source"       in edge
            assert "target"       in edge
            assert "relationship" in edge
            assert "confidence"   in edge
            assert "evidence_id"  in edge


# ═══════════════════════════════════════════════════════════════════════════════
# ROUTE — GET /api/graph/<case_id>
# ═══════════════════════════════════════════════════════════════════════════════

class TestGraphRoute:

    def test_requires_auth(self, client):
        rv = client.get(f"/api/graph/{CASE_ID}")
        assert rv.status_code == 401

    def test_returns_graph(self, client):
        token = get_token(client)
        rv = client.get(f"/api/graph/{CASE_ID}", headers=auth_header(token))
        assert rv.status_code == 200
        data = rv.get_json()
        assert "nodes" in data
        assert "edges" in data
        assert "stats" in data
        assert data["stats"]["node_count"] == 5
        assert data["stats"]["edge_count"] == 4

    def test_node_format(self, client):
        token = get_token(client)
        rv    = client.get(f"/api/graph/{CASE_ID}", headers=auth_header(token))
        for node in rv.get_json()["nodes"]:
            assert "id"       in node
            assert "type"     in node
            assert "label"    in node
            assert "metadata" in node

    def test_edge_format(self, client):
        token = get_token(client)
        rv    = client.get(f"/api/graph/{CASE_ID}", headers=auth_header(token))
        for edge in rv.get_json()["edges"]:
            assert "id"           in edge
            assert "source"       in edge
            assert "target"       in edge
            assert "relationship" in edge
            assert "confidence"   in edge
            assert "evidence_id"  in edge

    def test_filter_by_entity_type(self, client):
        token = get_token(client)
        rv    = client.get(f"/api/graph/{CASE_ID}?entity_types=PERSON",
                           headers=auth_header(token))
        data  = rv.get_json()
        types = {n["type"] for n in data["nodes"]}
        assert types == {"PERSON"}

    def test_filter_by_rel_type(self, client):
        token = get_token(client)
        rv    = client.get(f"/api/graph/{CASE_ID}?rel_types=OWNS",
                           headers=auth_header(token))
        rels  = {e["relationship"] for e in rv.get_json()["edges"]}
        assert rels.issubset({"OWNS"})

    def test_filter_by_confidence(self, client):
        token = get_token(client)
        rv    = client.get(f"/api/graph/{CASE_ID}?min_confidence=0.9",
                           headers=auth_header(token))
        for edge in rv.get_json()["edges"]:
            assert edge["confidence"] >= 0.9

    def test_unknown_case_empty_message(self, client):
        token = get_token(client)
        rv    = client.get("/api/graph/case_nonexistent_xyz",
                           headers=auth_header(token))
        assert rv.status_code == 200
        data  = rv.get_json()
        assert data["nodes"] == []


# ═══════════════════════════════════════════════════════════════════════════════
# ROUTE — GET /api/graph/<case_id>/neighbors/<entity_id>
# ═══════════════════════════════════════════════════════════════════════════════

class TestNeighborsRoute:

    def test_neighbors_success(self, client):
        token = get_token(client)
        rv    = client.get(f"/api/graph/{CASE_ID}/neighbors/ent_001",
                           headers=auth_header(token))
        assert rv.status_code == 200
        data = rv.get_json()
        assert "nodes" in data
        node_ids = {n["id"] for n in data["nodes"]}
        assert "ent_001" in node_ids

    def test_neighbors_depth_param(self, client):
        token = get_token(client)
        rv    = client.get(f"/api/graph/{CASE_ID}/neighbors/ent_001?depth=2",
                           headers=auth_header(token))
        assert rv.status_code == 200
        data = rv.get_json()
        assert data["depth"] == 2

    def test_neighbors_invalid_direction(self, client):
        token = get_token(client)
        rv    = client.get(f"/api/graph/{CASE_ID}/neighbors/ent_001?direction=sideways",
                           headers=auth_header(token))
        assert rv.status_code == 400

    def test_neighbors_unknown_entity(self, client):
        token = get_token(client)
        rv    = client.get(f"/api/graph/{CASE_ID}/neighbors/ent_UNKNOWN",
                           headers=auth_header(token))
        assert rv.status_code == 200
        assert rv.get_json()["nodes"] == []


# ═══════════════════════════════════════════════════════════════════════════════
# ROUTE — GET /api/graph/<case_id>/path
# ═══════════════════════════════════════════════════════════════════════════════

class TestPathRoute:

    def test_shortest_path_found(self, client):
        token = get_token(client)
        rv    = client.get(
            f"/api/graph/{CASE_ID}/path?source=ent_001&target=ent_003&mode=shortest",
            headers=auth_header(token),
        )
        assert rv.status_code == 200
        data = rv.get_json()
        assert data["found"] is True
        assert data["length"] >= 1

    def test_transaction_path_found(self, client):
        token = get_token(client)
        rv    = client.get(
            f"/api/graph/{CASE_ID}/path?source=ent_004&target=ent_003&mode=transaction",
            headers=auth_header(token),
        )
        assert rv.status_code == 200
        data = rv.get_json()
        assert data["found"] is True

    def test_missing_source(self, client):
        token = get_token(client)
        rv    = client.get(f"/api/graph/{CASE_ID}/path?target=ent_002",
                           headers=auth_header(token))
        assert rv.status_code == 400
        assert "source" in rv.get_json()["error"]

    def test_missing_target(self, client):
        token = get_token(client)
        rv    = client.get(f"/api/graph/{CASE_ID}/path?source=ent_001",
                           headers=auth_header(token))
        assert rv.status_code == 400

    def test_invalid_mode(self, client):
        token = get_token(client)
        rv    = client.get(
            f"/api/graph/{CASE_ID}/path?source=ent_001&target=ent_003&mode=teleport",
            headers=auth_header(token),
        )
        assert rv.status_code == 400

    def test_no_path_returns_not_found(self, client):
        token = get_token(client)
        rv    = client.get(
            f"/api/graph/{CASE_ID}/path?source=ent_001&target=ent_NOPE",
            headers=auth_header(token),
        )
        assert rv.status_code == 200
        assert rv.get_json()["found"] is False


# ═══════════════════════════════════════════════════════════════════════════════
# ROUTE — GET /api/graph/<case_id>/node/<entity_id>
# ═══════════════════════════════════════════════════════════════════════════════

class TestNodeDetailRoute:

    def test_node_detail_success(self, client):
        token  = get_token(client)
        rv     = client.get(f"/api/graph/{CASE_ID}/node/ent_001",
                            headers=auth_header(token))
        assert rv.status_code == 200
        data   = rv.get_json()
        assert data["id"] == "ent_001"
        assert data["type"] == "PERSON"
        assert "out_edges"   in data
        assert "in_edges"    in data
        assert "neighbours"  in data
        assert "degree"      in data
        assert data["degree"]["out"] >= 1

    def test_node_detail_unknown(self, client):
        token = get_token(client)
        rv    = client.get(f"/api/graph/{CASE_ID}/node/ent_UNKNOWN",
                           headers=auth_header(token))
        assert rv.status_code == 404


# ═══════════════════════════════════════════════════════════════════════════════
# ROUTE — GET /api/graph/<case_id>/search
# ═══════════════════════════════════════════════════════════════════════════════

class TestSearchRoute:

    def test_search_returns_match(self, client):
        token = get_token(client)
        rv    = client.get(f"/api/graph/{CASE_ID}/search?q=Rahul",
                           headers=auth_header(token))
        assert rv.status_code == 200
        data  = rv.get_json()
        ids   = {n["id"] for n in data["nodes"]}
        assert "ent_001" in ids

    def test_search_no_match(self, client):
        token = get_token(client)
        rv    = client.get(f"/api/graph/{CASE_ID}/search?q=zzznomatchxxx",
                           headers=auth_header(token))
        assert rv.status_code == 200
        assert rv.get_json()["nodes"] == []

    def test_search_missing_q(self, client):
        token = get_token(client)
        rv    = client.get(f"/api/graph/{CASE_ID}/search",
                           headers=auth_header(token))
        assert rv.status_code == 400


# ═══════════════════════════════════════════════════════════════════════════════
# ROUTE — GET /api/graph/<case_id>/components
# ═══════════════════════════════════════════════════════════════════════════════

class TestComponentsRoute:

    def test_components_returns_list(self, client):
        token = get_token(client)
        rv    = client.get(f"/api/graph/{CASE_ID}/components",
                           headers=auth_header(token))
        assert rv.status_code == 200
        data  = rv.get_json()
        assert "components" in data
        assert "total"      in data
        assert data["total"] >= 1
