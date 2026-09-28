"""
graph/role_analyzer.py

Network role analysis for each entity in the fraud graph.

Roles are assigned probabilistically from graph metrics — not by LLM.
Every role assignment carries an evidence list and a human-readable
explanation. No entity is labelled definitively criminal.

Roles
-----
Potential Coordinator     — high betweenness + high out-degree + high PageRank
Potential Intermediary    — moderate betweenness, significant in+out flow
Potential Mule Account    — high in-tx volume, high forwarding ratio, low degree
Technical/Device Node     — DEVICE/SIM/IMEI type with many linked identities
Victim                    — VICTIM type or very low risk_score + high in-degree
Unknown                   — insufficient signal to classify
"""

from __future__ import annotations

import math
from collections import defaultdict
from typing import Any

import networkx as nx

from storage.file_store import now_iso


# ── Sigmoid normaliser ────────────────────────────────────────────────────────

def _sigmoid(x: float, midpoint: float, steepness: float = 0.5) -> float:
    return 1.0 / (1.0 + math.exp(-steepness * (x - midpoint)))


# ── Score weights ─────────────────────────────────────────────────────────────

ROLE_DEFINITIONS = {
    "Potential Coordinator": (
        "This entity shows high betweenness centrality and PageRank, suggesting "
        "it may act as a central organiser or coordinator of the network's activity."
    ),
    "Potential Intermediary": (
        "This entity has significant in-flow and out-flow connections with moderate "
        "betweenness, indicating a pass-through role between parts of the network."
    ),
    "Potential Mule Account": (
        "This account receives funds then forwards most of them onward with limited "
        "legitimate transaction patterns, consistent with money-mule behaviour."
    ),
    "Technical/Device Node": (
        "This entity is a device, SIM, or IP address linked to multiple identities, "
        "suggesting it is used as shared technical infrastructure."
    ),
    "Victim": (
        "This entity is flagged as a victim — it receives funds or communication "
        "abnormally and shows low risk indicators of active participation."
    ),
    "Unknown": (
        "Insufficient graph signal to assign a specific role. "
        "Further investigation is recommended."
    ),
}


class RoleAnalyzer:
    """
    Compute a role score vector for every node in the NetworkX DiGraph.

    Metrics used
    ------------
    degree, weighted_degree, betweenness_centrality, pagerank,
    transaction_volume (from raw tx list), connected_accounts,
    connected_devices, connected_sims, communication_count (from call list)
    """

    def __init__(
        self,
        G: nx.DiGraph,
        transactions: list[dict] | None = None,
        call_records: list[dict] | None = None,
    ):
        self.G            = G
        self.transactions = transactions or []
        self.call_records = call_records or []

        # Pre-index transactions
        self._tx_in:  dict[str, list[dict]] = defaultdict(list)
        self._tx_out: dict[str, list[dict]] = defaultdict(list)
        for tx in self.transactions:
            src = tx.get("src_account") or tx.get("source_account") or ""
            dst = tx.get("dst_account") or tx.get("dest_account") or ""
            if src:
                self._tx_out[src].append(tx)
            if dst:
                self._tx_in[dst].append(tx)

        # Pre-index calls
        self._calls_out: dict[str, list[dict]] = defaultdict(list)
        self._calls_in:  dict[str, list[dict]] = defaultdict(list)
        for cr in self.call_records:
            caller   = cr.get("caller_id") or cr.get("caller") or ""
            receiver = cr.get("receiver_id") or cr.get("receiver") or ""
            if caller:
                self._calls_out[caller].append(cr)
            if receiver:
                self._calls_in[receiver].append(cr)

    # ── Pure-Python PageRank (avoids scipy dependency issue) ──────────────────

    @staticmethod
    def _pagerank_pure(G: nx.DiGraph, alpha: float = 0.85, max_iter: int = 200,
                       tol: float = 1e-6) -> dict[str, float]:
        """
        Power-iteration PageRank that works without scipy.
        Falls back to uniform distribution if the graph has no edges.
        """
        nodes = list(G.nodes())
        N = len(nodes)
        if N == 0:
            return {}

        idx = {n: i for i, n in enumerate(nodes)}
        rank = {n: 1.0 / N for n in nodes}

        # Build out-degree map
        out_deg = {n: G.out_degree(n) for n in nodes}
        dangling = [n for n in nodes if out_deg[n] == 0]

        for _ in range(max_iter):
            rank_new: dict[str, float] = {}
            dangling_sum = alpha * sum(rank[n] for n in dangling) / N

            for n in nodes:
                s = dangling_sum
                for pred in G.predecessors(n):
                    od = out_deg[pred]
                    if od > 0:
                        s += alpha * rank[pred] / od
                rank_new[n] = s + (1.0 - alpha) / N

            # Normalise
            total = sum(rank_new.values())
            if total > 0:
                rank_new = {n: v / total for n, v in rank_new.items()}

            # Convergence check
            err = sum(abs(rank_new[n] - rank[n]) for n in nodes)
            rank = rank_new
            if err < N * tol:
                break

        return rank

    # ── Public entry point ────────────────────────────────────────────────────

    def analyze(self) -> list[dict]:
        """Return a role-record for every node in the graph."""
        if self.G.number_of_nodes() == 0:
            return []

        # Compute graph-level metrics (expensive, do once)
        G_und = self.G.to_undirected()
        betweenness = nx.betweenness_centrality(G_und, normalized=True)
        pagerank    = self._pagerank_pure(self.G, alpha=0.85, max_iter=200)

        # Normalise degree to [0, 1] across all nodes
        max_degree = max((self.G.degree(n) for n in self.G.nodes()), default=1)

        results: list[dict] = []
        for node_id in self.G.nodes():
            record = self._analyze_node(
                node_id,
                betweenness.get(node_id, 0.0),
                pagerank.get(node_id, 0.0),
                max_degree,
            )
            results.append(record)

        return results

    # ── Per-node analysis ─────────────────────────────────────────────────────

    def _analyze_node(
        self,
        node_id: str,
        betweenness: float,
        pagerank:    float,
        max_degree:  int,
    ) -> dict:
        G    = self.G
        attrs = G.nodes[node_id]
        ntype = attrs.get("type", "UNKNOWN").upper()

        # ── Raw metrics ───────────────────────────────────────────────────────
        in_degree  = G.in_degree(node_id)
        out_degree = G.out_degree(node_id)
        degree     = in_degree + out_degree

        # Weighted degree (by edge confidence)
        w_in  = sum(d.get("confidence", 1.0) for _, _, d in G.in_edges(node_id, data=True))
        w_out = sum(d.get("confidence", 1.0) for _, _, d in G.out_edges(node_id, data=True))
        weighted_degree = w_in + w_out

        # Transaction volume
        tx_in_vol  = sum(float(t.get("amount", 0)) for t in self._tx_in.get(node_id, []))
        tx_out_vol = sum(float(t.get("amount", 0)) for t in self._tx_out.get(node_id, []))
        tx_volume  = tx_in_vol + tx_out_vol

        # Connected entity type counts
        connected_accounts = sum(
            1 for nbr in list(G.predecessors(node_id)) + list(G.successors(node_id))
            if G.nodes[nbr].get("type", "").upper() in ("BANK_ACCOUNT", "UPI_ID", "ACCOUNT")
        )
        connected_devices = sum(
            1 for nbr in list(G.predecessors(node_id)) + list(G.successors(node_id))
            if G.nodes[nbr].get("type", "").upper() in ("DEVICE", "IMEI")
        )
        connected_sims = sum(
            1 for nbr in list(G.predecessors(node_id)) + list(G.successors(node_id))
            if G.nodes[nbr].get("type", "").upper() in ("SIM", "SIM_CARD", "ICCID")
        )

        # Communication count
        comm_out = len(self._calls_out.get(node_id, []))
        comm_in  = len(self._calls_in.get(node_id, []))
        comm_count = comm_out + comm_in

        # Forwarding ratio (for mule detection)
        fwd_ratio = 0.0
        if tx_in_vol > 0 and tx_out_vol > 0:
            fwd_ratio = tx_out_vol / tx_in_vol

        # ── Role scoring ──────────────────────────────────────────────────────
        scores: dict[str, float] = {}

        # 1. Potential Coordinator
        scores["Potential Coordinator"] = min(
            _sigmoid(betweenness, midpoint=0.1, steepness=15) * 0.35
            + _sigmoid(pagerank,  midpoint=0.05, steepness=20) * 0.30
            + _sigmoid(out_degree, midpoint=5,  steepness=0.4) * 0.20
            + _sigmoid(comm_out,  midpoint=5,  steepness=0.3) * 0.15,
            1.0,
        )

        # 2. Potential Intermediary
        scores["Potential Intermediary"] = min(
            _sigmoid(betweenness, midpoint=0.05, steepness=12) * 0.30
            + _sigmoid(in_degree + out_degree, midpoint=4, steepness=0.5) * 0.30
            + (min(in_degree, out_degree) / max(max(in_degree, out_degree), 1)) * 0.25
            + _sigmoid(fwd_ratio, midpoint=0.5, steepness=4) * 0.15,
            1.0,
        )

        # 3. Potential Mule Account
        scores["Potential Mule Account"] = 0.0
        if ntype in ("BANK_ACCOUNT", "UPI_ID", "ACCOUNT") or (tx_in_vol > 0 and tx_out_vol > 0):
            scores["Potential Mule Account"] = min(
                _sigmoid(fwd_ratio, midpoint=0.8, steepness=8) * 0.50
                + _sigmoid(len(self._tx_in.get(node_id, [])), midpoint=3, steepness=0.8) * 0.30
                + (1.0 - _sigmoid(degree, midpoint=6, steepness=0.5)) * 0.20,
                1.0,
            )

        # 4. Technical/Device Node
        scores["Technical/Device Node"] = 0.0
        if ntype in ("DEVICE", "IMEI", "SIM", "SIM_CARD", "ICCID", "IP_ADDRESS"):
            linked_ids = connected_accounts + connected_devices + connected_sims + degree
            scores["Technical/Device Node"] = min(
                _sigmoid(linked_ids, midpoint=3, steepness=0.7) * 0.7
                + _sigmoid(degree, midpoint=4, steepness=0.5) * 0.3,
                1.0,
            )

        # 5. Victim
        scores["Victim"] = 0.0
        if ntype == "VICTIM":
            scores["Victim"] = 0.85
        else:
            victim_score = 0.0
            risk_score   = attrs.get("risk_score") or 0.0
            if risk_score < 0.3:
                victim_score += 0.3
            if in_degree > 0 and out_degree == 0:
                victim_score += 0.3
            if tx_in_vol > 0 and tx_out_vol == 0:
                victim_score += 0.2
            scores["Victim"] = min(victim_score, 0.8)

        # 6. Unknown — residual (all scores low)
        max_other = max(
            scores.get("Potential Coordinator", 0),
            scores.get("Potential Intermediary", 0),
            scores.get("Potential Mule Account", 0),
            scores.get("Technical/Device Node", 0),
            scores.get("Victim", 0),
        )
        scores["Unknown"] = max(0.0, 0.4 - max_other * 0.4)

        # ── Assign primary role (highest score) ───────────────────────────────
        primary_role = max(scores, key=lambda k: scores[k])
        primary_score = scores[primary_role]

        # Build evidence list
        evidence: list[str] = []
        if betweenness > 0.05:
            evidence.append(f"betweenness_centrality={betweenness:.3f}")
        if pagerank > 0.01:
            evidence.append(f"pagerank={pagerank:.4f}")
        if tx_volume > 0:
            evidence.append(f"transaction_volume={tx_volume:,.0f}")
        if fwd_ratio > 0:
            evidence.append(f"forwarding_ratio={fwd_ratio:.2f}")
        if connected_accounts:
            evidence.append(f"connected_accounts={connected_accounts}")
        if connected_devices:
            evidence.append(f"connected_devices={connected_devices}")
        if connected_sims:
            evidence.append(f"connected_sims={connected_sims}")
        if comm_count:
            evidence.append(f"communication_count={comm_count}")

        explanation = ROLE_DEFINITIONS.get(primary_role, ROLE_DEFINITIONS["Unknown"])

        return {
            "entity_id":      node_id,
            "entity_type":    ntype,
            "entity_label":   attrs.get("label", node_id),
            "primary_role":   primary_role,
            "role_score":     round(primary_score, 4),
            "all_scores":     {k: round(v, 4) for k, v in scores.items()},
            "metrics": {
                "degree":                  degree,
                "in_degree":               in_degree,
                "out_degree":              out_degree,
                "weighted_degree":         round(weighted_degree, 4),
                "betweenness_centrality":  round(betweenness, 6),
                "pagerank":                round(pagerank, 6),
                "transaction_volume":      round(tx_volume, 2),
                "tx_in_volume":            round(tx_in_vol, 2),
                "tx_out_volume":           round(tx_out_vol, 2),
                "forwarding_ratio":        round(fwd_ratio, 4),
                "connected_accounts":      connected_accounts,
                "connected_devices":       connected_devices,
                "connected_sims":          connected_sims,
                "communication_count":     comm_count,
            },
            "evidence":    evidence,
            "explanation": explanation,
            "analyzed_at": now_iso(),
        }
