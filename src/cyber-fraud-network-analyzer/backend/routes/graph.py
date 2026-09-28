"""
routes/graph.py

GET  /api/graph/<case_id>                         — full graph (filtered)
GET  /api/graph/<case_id>/neighbors/<entity_id>   — ego-graph
GET  /api/graph/<case_id>/path                    — shortest / transaction path
GET  /api/graph/<case_id>/node/<entity_id>        — full node detail
GET  /api/graph/<case_id>/search                  — search nodes by label/value
GET  /api/graph/<case_id>/components              — connected components
"""

from flask import Blueprint, g, jsonify, request

from graph.graph_service import (
    build_graph, filter_graph, graph_to_cytoscape,
    get_neighbors, get_shortest_path, get_transaction_path,
    get_connected_components, search_graph, get_node_detail,
    _load_evidence,
)
from utils.auth_middleware import require_permission

graph_bp = Blueprint("graph", __name__, url_prefix="/api/graph")


def _parse_list(param: str | None) -> list[str] | None:
    """Parse comma-separated query param into a list, or None if absent."""
    if not param:
        return None
    return [v.strip() for v in param.split(",") if v.strip()]


def _safe_float(val: str | None, default: float) -> float:
    try:
        return float(val) if val is not None else default
    except (TypeError, ValueError):
        return default


def _safe_int(val: str | None, default: int) -> int:
    try:
        return max(1, min(int(val), 5)) if val is not None else default
    except (TypeError, ValueError):
        return default


# ── GET /api/graph/<case_id> ─────────────────────────────────────────────────

@graph_bp.get("/<case_id>")
@require_permission("read")
def get_graph(case_id: str):
    """
    Return the full graph for a case, with optional filters:
      ?entity_types=PERSON,PHONE
      ?rel_types=OWNS,CALLED
      ?min_confidence=0.5
      ?evidence_source=observed|inferred|ai_generated
      ?pattern=sim_swap|mule_network|…
    """
    entity_types    = _parse_list(request.args.get("entity_types"))
    rel_types       = _parse_list(request.args.get("rel_types"))
    min_confidence  = _safe_float(request.args.get("min_confidence"), 0.0)
    evidence_source = request.args.get("evidence_source") or None
    pattern         = request.args.get("pattern") or None

    G = build_graph(case_id)
    if not G.number_of_nodes():
        return jsonify({
            "case_id": case_id,
            "nodes": [], "edges": [],
            "stats": {"node_count": 0, "edge_count": 0},
            "message": "No entities found for this case. Run AI extraction first.",
        }), 200

    if any([entity_types, rel_types, min_confidence > 0.0, evidence_source, pattern]):
        G = filter_graph(G, entity_types, rel_types, min_confidence, evidence_source, pattern)

    result = graph_to_cytoscape(G)
    result["case_id"] = case_id
    return jsonify(result), 200


# ── GET /api/graph/<case_id>/neighbors/<entity_id> ───────────────────────────

@graph_bp.get("/<case_id>/neighbors/<path:entity_id>")
@require_permission("read")
def get_neighbor_graph(case_id: str, entity_id: str):
    """
    Return ego-graph for an entity (all nodes within `depth` hops).
      ?depth=1     (1–5)
      ?direction=both|in|out
    """
    depth     = _safe_int(request.args.get("depth"), 1)
    direction = request.args.get("direction", "both")
    if direction not in ("in", "out", "both"):
        return jsonify({"error": "direction must be 'in', 'out', or 'both'"}), 400

    G      = build_graph(case_id)
    result = get_neighbors(G, entity_id, depth=depth, direction=direction)
    result["case_id"]   = case_id
    result["entity_id"] = entity_id
    result["depth"]     = depth
    result["direction"] = direction
    return jsonify(result), 200


# ── GET /api/graph/<case_id>/path ─────────────────────────────────────────────

@graph_bp.get("/<case_id>/path")
@require_permission("read")
def get_path(case_id: str):
    """
    Find a path between two entities.
      ?source=<entity_id>   (required)
      ?target=<entity_id>   (required)
      ?mode=shortest|transaction   (default: shortest)
    """
    source = (request.args.get("source") or "").strip()
    target = (request.args.get("target") or "").strip()
    mode   = request.args.get("mode", "shortest").lower()

    if not source:
        return jsonify({"error": "source query parameter is required"}), 400
    if not target:
        return jsonify({"error": "target query parameter is required"}), 400
    if mode not in ("shortest", "transaction"):
        return jsonify({"error": "mode must be 'shortest' or 'transaction'"}), 400

    G = build_graph(case_id)

    if mode == "transaction":
        result = get_transaction_path(G, source, target)
    else:
        result = get_shortest_path(G, source, target)

    result["case_id"] = case_id
    result["source"]  = source
    result["target"]  = target
    result["mode"]    = mode
    return jsonify(result), 200


# ── GET /api/graph/<case_id>/node/<entity_id> ─────────────────────────────────

@graph_bp.get("/<case_id>/node/<path:entity_id>")
@require_permission("read")
def get_node(case_id: str, entity_id: str):
    """Return full detail for a single node including connections and evidence."""
    G            = build_graph(case_id)
    evidence_map = _load_evidence()
    detail       = get_node_detail(G, entity_id, evidence_map)

    if not detail:
        return jsonify({"error": f"Entity '{entity_id}' not found in graph for case '{case_id}'"}), 404

    detail["case_id"] = case_id
    return jsonify(detail), 200


# ── GET /api/graph/<case_id>/search ──────────────────────────────────────────

@graph_bp.get("/<case_id>/search")
@require_permission("read")
def search(case_id: str):
    """
    Search nodes by label / value.
      ?q=<query string>
    """
    query = (request.args.get("q") or "").strip()
    if not query:
        return jsonify({"error": "q query parameter is required"}), 400

    G      = build_graph(case_id)
    result = search_graph(G, query)
    result["case_id"] = case_id
    result["query"]   = query
    return jsonify(result), 200


# ── GET /api/graph/<case_id>/components ───────────────────────────────────────

@graph_bp.get("/<case_id>/components")
@require_permission("read")
def components(case_id: str):
    """Return weakly connected components, largest first."""
    G      = build_graph(case_id)
    comps  = get_connected_components(G)
    return jsonify({
        "case_id":    case_id,
        "components": comps,
        "total":      len(comps),
    }), 200
