"""
graph/graph_service.py
NetworkX-based graph service.

Loads entities + relationships from JSON files, builds a directed graph,
and exposes graph-analysis functions used by the API routes.

Data sources (read-only):
  data/entities/entities.json
  data/relationships/relationships.json
  data/evidence/evidence.json          (for evidence linking)
  data/sample/entities.json            (fallback demo data)
  data/sample/relationships.json       (fallback demo data)

No database. Graph is rebuilt on each API call from JSON on disk.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

import networkx as nx

from config.settings import DATA_DIR
from storage.file_store import read_json

# ── Data file paths ──────────────────────────────────────────────────────────
ENTITIES_FILE       = DATA_DIR / "entities"      / "entities.json"
RELATIONSHIPS_FILE  = DATA_DIR / "relationships" / "relationships.json"
EVIDENCE_FILE       = DATA_DIR / "evidence"      / "evidence.json"
# Demo / sample data fallbacks (used when live extraction store is empty)
SAMPLE_ENTITIES_FILE      = DATA_DIR / "sample" / "entities.json"
SAMPLE_RELATIONSHIPS_FILE = DATA_DIR / "sample" / "relationships.json"


# ── Loading helpers ──────────────────────────────────────────────────────────

def _load_entities(case_id: str) -> list[dict]:
    """
    Load all entities for a given case.
    Tries the live extraction store first; falls back to sample data.
    """
    live = read_json(ENTITIES_FILE) or []
    case_entities = [
        e for e in live
        if case_id in (e.get("case_ids") or [e.get("case_id", "")])
    ]
    if case_entities:
        return case_entities

    # Fallback: sample data — every sample entity is treated as belonging
    # to the requested case (demo mode)
    sample = read_json(SAMPLE_ENTITIES_FILE) or []
    return sample


def _load_relationships(case_id: str) -> list[dict]:
    live = read_json(RELATIONSHIPS_FILE) or []
    case_rels = [
        r for r in live
        if case_id in (r.get("case_ids") or [r.get("case_id", "")])
    ]
    if case_rels:
        return case_rels

    sample = read_json(SAMPLE_RELATIONSHIPS_FILE) or []
    return sample


def _load_evidence() -> dict[str, dict]:
    """Return evidence records indexed by evidence_id."""
    records = read_json(EVIDENCE_FILE) or []
    return {e["id"]: e for e in records if "id" in e}


# ── Graph construction ───────────────────────────────────────────────────────

def _entity_to_node(e: dict) -> tuple[str, dict]:
    """Convert a raw entity record to a (node_id, attrs) tuple."""
    node_id = e.get("entity_id") or e.get("id") or ""
    label   = e.get("value") or e.get("label") or node_id

    attrs = {
        "type":          e.get("type", "UNKNOWN"),
        "label":         label,
        "value":         e.get("value", label),
        "confidence":    e.get("confidence", 1.0),
        "evidence_ids":  e.get("evidence_ids") or ([e["evidence_id"]] if e.get("evidence_id") else []),
        "case_ids":      e.get("case_ids") or ([e["case_id"]] if e.get("case_id") else []),
        "attributes":    e.get("attributes") or {},
        "extracted_at":  e.get("extracted_at") or e.get("created_at"),
        "updated_at":    e.get("updated_at"),
        "risk_score":    e.get("risk_score"),
        # Extra fields present in sample data
        "raw_value":     e.get("raw_value", label),
        "source_texts":  e.get("source_texts", []),
    }
    return node_id, attrs


def _rel_to_edge(r: dict) -> tuple[str, str, dict]:
    """Convert a raw relationship record to a (src_id, tgt_id, attrs) tuple."""
    src = r.get("source_entity") or r.get("src_id") or ""
    tgt = r.get("target_entity") or r.get("dst_id") or ""

    rel_id = r.get("relationship_id") or r.get("id") or f"{src}__{r.get('relationship','')}__{tgt}"
    attrs = {
        "id":             rel_id,
        "relationship":   r.get("relationship", ""),
        "confidence":     r.get("confidence", 1.0),
        "evidence_ids":   r.get("evidence_ids") or ([r["evidence_id"]] if r.get("evidence_id") else []),
        "case_ids":       r.get("case_ids") or ([r["case_id"]] if r.get("case_id") else []),
        "evidence_source":r.get("evidence_source", "observed"),
        "source_text":    r.get("source_text", ""),
        "attributes":     r.get("attributes") or {},
        "extracted_at":   r.get("extracted_at") or r.get("created_at"),
        # Extra fields from sample data
        "source_value":   r.get("source_value"),
        "target_value":   r.get("target_value"),
        "pattern":        r.get("pattern"),
    }
    return src, tgt, attrs


def build_graph(case_id: str) -> nx.DiGraph:
    """
    Build a directed NetworkX graph for the given case.
    Nodes = entities, edges = relationships.
    """
    G = nx.DiGraph()
    entities      = _load_entities(case_id)
    relationships = _load_relationships(case_id)

    # Add nodes
    for e in entities:
        node_id, attrs = _entity_to_node(e)
        if node_id:
            G.add_node(node_id, **attrs)

    # Add edges (only between nodes already in the graph)
    for r in relationships:
        src, tgt, attrs = _rel_to_edge(r)
        if src and tgt and G.has_node(src) and G.has_node(tgt):
            G.add_edge(src, tgt, **attrs)

    return G


# ── Serialisation helpers ─────────────────────────────────────────────────────

def _node_to_dict(G: nx.DiGraph, node_id: str) -> dict:
    attrs = G.nodes[node_id]
    return {
        "id":         node_id,
        "type":       attrs.get("type", "UNKNOWN"),
        "label":      attrs.get("label", node_id),
        "metadata": {
            "value":        attrs.get("value"),
            "confidence":   attrs.get("confidence"),
            "risk_score":   attrs.get("risk_score"),
            "evidence_ids": attrs.get("evidence_ids", []),
            "case_ids":     attrs.get("case_ids", []),
            "extracted_at": attrs.get("extracted_at"),
            "updated_at":   attrs.get("updated_at"),
            "attributes":   attrs.get("attributes", {}),
            "source_texts": attrs.get("source_texts", []),
            "pattern":      attrs.get("attributes", {}).get("pattern"),
        },
    }


def _edge_to_dict(G: nx.DiGraph, src: str, tgt: str, data: dict) -> dict:
    return {
        "id":           data.get("id", f"{src}__{data.get('relationship','')}__{tgt}"),
        "source":       src,
        "target":       tgt,
        "relationship": data.get("relationship", ""),
        "confidence":   data.get("confidence", 1.0),
        "evidence_id":  (data.get("evidence_ids") or [None])[0],
        "evidence_ids": data.get("evidence_ids", []),
        "evidence_source": data.get("evidence_source", "observed"),
        "source_text":  data.get("source_text", ""),
        "pattern":      data.get("pattern"),
        "attributes":   data.get("attributes", {}),
    }


def graph_to_cytoscape(G: nx.DiGraph) -> dict:
    """Serialise graph to the node/edge format expected by the frontend."""
    nodes = [_node_to_dict(G, n) for n in G.nodes()]
    edges = [
        _edge_to_dict(G, u, v, d)
        for u, v, d in G.edges(data=True)
    ]
    return {
        "nodes": nodes,
        "edges": edges,
        "stats": {
            "node_count": G.number_of_nodes(),
            "edge_count": G.number_of_edges(),
        },
    }


# ── Filter helpers ────────────────────────────────────────────────────────────

def filter_graph(
    G: nx.DiGraph,
    entity_types:    Optional[list[str]] = None,
    rel_types:       Optional[list[str]] = None,
    min_confidence:  float = 0.0,
    evidence_source: Optional[str] = None,
    pattern:         Optional[str] = None,
) -> nx.DiGraph:
    """Return a subgraph matching the given filters."""
    # Filter nodes by type
    if entity_types:
        types_upper = {t.upper() for t in entity_types}
        keep_nodes = [
            n for n, d in G.nodes(data=True)
            if d.get("type", "").upper() in types_upper
        ]
        G = G.subgraph(keep_nodes).copy()

    # Filter edges
    remove_edges = []
    for u, v, d in G.edges(data=True):
        if rel_types and d.get("relationship", "").upper() not in {r.upper() for r in rel_types}:
            remove_edges.append((u, v))
            continue
        if d.get("confidence", 1.0) < min_confidence:
            remove_edges.append((u, v))
            continue
        if evidence_source and d.get("evidence_source") != evidence_source:
            remove_edges.append((u, v))
            continue
        if pattern and d.get("pattern") != pattern:
            remove_edges.append((u, v))
            continue

    H = G.copy()
    H.remove_edges_from(remove_edges)
    return H


# ── Graph algorithms ──────────────────────────────────────────────────────────

def get_neighbors(
    G: nx.DiGraph,
    entity_id: str,
    depth: int = 1,
    direction: str = "both",   # "in" | "out" | "both"
) -> dict:
    """
    Return nodes within `depth` hops of `entity_id`.
    direction controls traversal: incoming, outgoing, or both.
    """
    if entity_id not in G:
        return {"nodes": [], "edges": [], "stats": {"node_count": 0, "edge_count": 0}}

    if direction == "out":
        neighbors_func = nx.ego_graph
    elif direction == "in":
        neighbors_func = lambda g, n, r: nx.ego_graph(g.reverse(copy=False), n, r)
    else:
        # undirected traversal
        neighbors_func = lambda g, n, r: nx.ego_graph(g.to_undirected(as_view=True), n, r)

    sub = neighbors_func(G, entity_id, depth)

    # Always return as a DiGraph view
    if not isinstance(sub, nx.DiGraph):
        sub = G.subgraph(sub.nodes()).copy()

    return graph_to_cytoscape(sub)


def get_shortest_path(
    G: nx.DiGraph,
    source_id: str,
    target_id: str,
) -> dict:
    """
    Find the shortest directed path between two entity nodes.
    Falls back to undirected if no directed path exists.
    """
    for use_directed in (True, False):
        graph = G if use_directed else G.to_undirected()
        try:
            path_nodes = nx.shortest_path(graph, source=source_id, target=target_id)
            break
        except (nx.NetworkXNoPath, nx.NodeNotFound):
            path_nodes = []

    if not path_nodes:
        return {
            "found":  False,
            "path":   [],
            "nodes":  [],
            "edges":  [],
            "length": 0,
        }

    # Build subgraph from path
    path_set = set(path_nodes)
    sub = G.subgraph(path_set).copy()
    cy  = graph_to_cytoscape(sub)
    return {
        "found":  True,
        "path":   path_nodes,
        "nodes":  cy["nodes"],
        "edges":  cy["edges"],
        "length": len(path_nodes) - 1,
    }


def get_transaction_path(
    G: nx.DiGraph,
    source_id: str,
    target_id: str,
) -> dict:
    """
    Find all simple paths between two nodes limited to TRANSFERRED_TO /
    PAID_TO edge types. Returns up to 10 paths.
    """
    # Build a view restricted to financial edges
    financial_rels = {"TRANSFERRED_TO", "PAID_TO"}
    tx_edges = [
        (u, v) for u, v, d in G.edges(data=True)
        if d.get("relationship", "").upper() in financial_rels
    ]
    tx_graph = nx.DiGraph()
    tx_graph.add_nodes_from(G.nodes(data=True))
    for u, v in tx_edges:
        tx_graph.add_edge(u, v, **G[u][v])

    paths: list[list[str]] = []
    try:
        for p in nx.all_simple_paths(tx_graph, source=source_id, target=target_id, cutoff=8):
            paths.append(p)
            if len(paths) >= 10:
                break
    except (nx.NodeNotFound, nx.NetworkXError):
        pass

    if not paths:
        return {"found": False, "paths": [], "nodes": [], "edges": []}

    # Union of all path nodes/edges
    all_nodes: set[str] = set()
    for p in paths:
        all_nodes.update(p)

    sub = G.subgraph(all_nodes).copy()
    cy  = graph_to_cytoscape(sub)
    return {
        "found": True,
        "paths": paths,
        "nodes": cy["nodes"],
        "edges": cy["edges"],
    }


def get_connected_components(G: nx.DiGraph) -> list[dict]:
    """Return weakly connected components as serialised sub-graphs."""
    undirected = G.to_undirected()
    components = []
    for i, component in enumerate(
        sorted(nx.connected_components(undirected), key=len, reverse=True)
    ):
        sub = G.subgraph(component).copy()
        cy  = graph_to_cytoscape(sub)
        cy["component_index"] = i
        cy["size"] = len(component)
        components.append(cy)
    return components


def search_graph(G: nx.DiGraph, query: str) -> dict:
    """
    Return nodes whose label or value matches the query string (case-insensitive).
    """
    q = query.strip().lower()
    if not q:
        return {"nodes": [], "edges": [], "stats": {"node_count": 0, "edge_count": 0}}

    matches = [
        n for n, d in G.nodes(data=True)
        if q in str(d.get("label", "")).lower()
        or q in str(d.get("value", "")).lower()
        or q in n.lower()
    ]

    if not matches:
        return {"nodes": [], "edges": [], "stats": {"node_count": 0, "edge_count": 0}}

    sub = G.subgraph(matches).copy()
    return graph_to_cytoscape(sub)


def get_node_detail(G: nx.DiGraph, entity_id: str, evidence_map: dict) -> dict:
    """
    Return full detail for a single node including its connections and evidence.
    """
    if entity_id not in G:
        return {}

    node = _node_to_dict(G, entity_id)

    in_edges  = [_edge_to_dict(G, u, v, d) for u, v, d in G.in_edges(entity_id,  data=True)]
    out_edges = [_edge_to_dict(G, u, v, d) for u, v, d in G.out_edges(entity_id, data=True)]

    # Neighbour nodes
    neighbour_ids = set()
    for u, v, _ in G.in_edges(entity_id, data=True):
        neighbour_ids.add(u)
    for u, v, _ in G.out_edges(entity_id, data=True):
        neighbour_ids.add(v)

    neighbours = [_node_to_dict(G, n) for n in neighbour_ids if n != entity_id]

    # Evidence records
    ev_ids = node["metadata"].get("evidence_ids", [])
    evidence_records = [evidence_map[eid] for eid in ev_ids if eid in evidence_map]

    # Transaction edges (TRANSFERRED_TO / PAID_TO)
    tx_rels = {"TRANSFERRED_TO", "PAID_TO"}
    related_transactions = [
        e for e in (in_edges + out_edges)
        if e.get("relationship", "").upper() in tx_rels
    ]

    return {
        **node,
        "in_edges":   in_edges,
        "out_edges":  out_edges,
        "neighbours": neighbours,
        "evidence":   evidence_records,
        "related_transactions": related_transactions,
        "degree": {
            "in":    G.in_degree(entity_id),
            "out":   G.out_degree(entity_id),
            "total": G.degree(entity_id),
        },
    }
