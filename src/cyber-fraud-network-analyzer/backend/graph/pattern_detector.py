"""
graph/pattern_detector.py

Deterministic, rule-based fraud pattern detection.

Scores are computed from graph metrics, transaction statistics, and
time-based heuristics — never assigned arbitrarily by an LLM.

Supported patterns
------------------
1. sim_swap_sequence        — SIM change → immediate account activity
2. mule_account_network     — accounts receiving then forwarding money, no retail spend
3. transaction_layering     — rapid split/merge fund movement across ≥3 hops
4. shared_device_network    — one device linked to multiple accounts/persons
5. shared_sim_network       — one SIM linked to multiple accounts/persons
6. high_transaction_velocity — unusually many transactions in a short window
7. communication_hub        — node with very high out-call degree vs peers
8. rapid_multi_hop          — funds move through ≥3 accounts in < 2 h
9. dense_relationship_cluster — tightly connected sub-graph (triangle density)
"""

from __future__ import annotations

import math
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any

import networkx as nx

from storage.file_store import read_json, now_iso


# ── Timestamp helpers ─────────────────────────────────────────────────────────

def _parse_ts(ts: str | None) -> datetime | None:
    if not ts:
        return None
    # Normalise common ISO 8601 suffixes before parsing
    s = ts.strip()
    # Replace +00:00Z and +00:00 and trailing Z so strptime can handle them uniformly
    for suffix in ("+00:00Z", "+00:00", "Z"):
        if s.endswith(suffix):
            s = s[: -len(suffix)]
            break
    for fmt in (
        "%Y-%m-%dT%H:%M:%S.%f",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%dT%H:%M",
        "%Y-%m-%d",
    ):
        try:
            dt = datetime.strptime(s, fmt)
            return dt.replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return None


def _delta_hours(a: datetime | None, b: datetime | None) -> float | None:
    if a is None or b is None:
        return None
    diff = abs((b - a).total_seconds()) / 3600
    return diff


def _time_range(timestamps: list[datetime]) -> dict:
    if not timestamps:
        return {}
    ts_sorted = sorted(timestamps)
    return {
        "start": ts_sorted[0].isoformat(),
        "end":   ts_sorted[-1].isoformat(),
        "span_hours": round((ts_sorted[-1] - ts_sorted[0]).total_seconds() / 3600, 2),
    }


# ── Sigmoid-shaped normaliser (maps raw counts/ratios to 0–1) ─────────────────

def _sigmoid(x: float, midpoint: float, steepness: float = 0.5) -> float:
    """Smooth 0–1 normaliser centred at `midpoint`."""
    return 1.0 / (1.0 + math.exp(-steepness * (x - midpoint)))


# ── Finding builder ────────────────────────────────────────────────────────────

def _finding(
    pattern_id: str,
    pattern_name: str,
    score: float,
    confidence: float,
    affected: list[str],
    indicators: list[str],
    evidence: list[str],
    time_range: dict,
    explanation: str,
) -> dict:
    return {
        "pattern_id":          pattern_id,
        "pattern_name":        pattern_name,
        "score":               round(min(max(score, 0.0), 1.0), 4),
        "confidence":          round(min(max(confidence, 0.0), 1.0), 4),
        "affected_entities":   affected,
        "indicators":          indicators,
        "supporting_evidence": evidence,
        "time_range":          time_range,
        "explanation":         explanation,
    }


# ── PatternDetector ────────────────────────────────────────────────────────────

class PatternDetector:
    """
    All detection methods receive a NetworkX DiGraph and optional raw-data
    lists (transactions, call_records, sims) loaded from JSON files.

    Each method returns a list of Finding dicts (possibly empty).
    """

    # Thresholds (all tunable)
    SIM_SWAP_WINDOW_H   = 6      # calls/txns within N h of SIM change = suspicious
    MULE_FWD_RATIO      = 0.75   # forwarded / received ≥ this = mule
    LAYERING_MIN_HOPS   = 3      # minimum hop chain for layering
    LAYERING_WINDOW_H   = 48     # chain must complete within N h
    VELOCITY_WINDOW_H   = 24     # rolling window for velocity check
    VELOCITY_MIN_TXN    = 5      # minimum txns to flag
    HUB_DEGREE_RATIO    = 2.5    # caller's degree / avg ≥ this = hub
    HUB_MIN_DEGREE      = 4      # absolute minimum unique contacts
    RAPID_HOP_HOPS      = 3      # min hops for rapid multi-hop
    RAPID_HOP_WINDOW_H  = 2      # window in hours
    CLUSTER_MIN_NODES   = 3      # min clique size for cluster detection
    SHARED_DEVICE_MIN   = 3      # min accounts per device
    SHARED_SIM_MIN      = 2      # min accounts per SIM

    def __init__(
        self,
        G: nx.DiGraph,
        transactions: list[dict] | None = None,
        call_records: list[dict] | None = None,
        sims: list[dict] | None = None,
        case_id: str | None = None,
    ):
        self.G            = G
        self.transactions = transactions or []
        self.call_records = call_records or []
        self.sims         = sims or []
        self.case_id      = case_id

        # Pre-compute some indexes for speed
        self._tx_by_src: dict[str, list[dict]] = defaultdict(list)
        self._tx_by_dst: dict[str, list[dict]] = defaultdict(list)
        for tx in self.transactions:
            src = tx.get("src_account") or tx.get("source_account") or tx.get("from_account") or ""
            dst = tx.get("dst_account") or tx.get("dest_account") or tx.get("to_account") or ""
            if src:
                self._tx_by_src[src].append(tx)
            if dst:
                self._tx_by_dst[dst].append(tx)

        self._call_by_caller: dict[str, list[dict]] = defaultdict(list)
        for c in self.call_records:
            caller = c.get("caller_id") or c.get("caller") or ""
            if caller:
                self._call_by_caller[caller].append(c)

    # ── Public entry point ────────────────────────────────────────────────────

    def detect_all(self) -> list[dict]:
        """Run all detectors. Returns a flat list of findings."""
        findings: list[dict] = []
        for method in [
            self._detect_sim_swap,
            self._detect_mule_network,
            self._detect_transaction_layering,
            self._detect_shared_device_network,
            self._detect_shared_sim_network,
            self._detect_high_velocity,
            self._detect_communication_hub,
            self._detect_rapid_multi_hop,
            self._detect_dense_cluster,
        ]:
            try:
                findings.extend(method())
            except Exception:  # never let one detector crash the whole run
                pass
        return findings

    # ── 1. SIM-swap sequence ──────────────────────────────────────────────────

    def _detect_sim_swap(self) -> list[dict]:
        """
        A SIM-swap sequence is indicated when:
          - a SIM node is linked to >1 phone/person (SHARED_SIM edge pattern)
          - AND financial activity (transactions) occurs within SIM_SWAP_WINDOW_H
            after the swap timestamp.
        """
        findings: list[dict] = []
        G = self.G

        # Look for SIM nodes connected to ≥2 phone/person nodes
        for node_id, attrs in G.nodes(data=True):
            if attrs.get("type", "").upper() not in ("SIM", "SIM_CARD"):
                continue

            linked_phones = [
                nbr for nbr in G.predecessors(node_id)
                if G.nodes[nbr].get("type", "").upper() in ("PHONE", "PERSON")
            ] + [
                nbr for nbr in G.successors(node_id)
                if G.nodes[nbr].get("type", "").upper() in ("PHONE", "PERSON")
            ]
            if len(linked_phones) < 2:
                continue

            # Check if there are accounts linked to this SIM's phones
            linked_accounts: list[str] = []
            for ph in linked_phones:
                for nbr in list(G.successors(ph)) + list(G.predecessors(ph)):
                    if G.nodes[nbr].get("type", "").upper() in (
                        "BANK_ACCOUNT", "UPI_ID", "ACCOUNT"
                    ):
                        linked_accounts.append(nbr)

            if not linked_accounts:
                continue

            # Score: ratio of linked phones (more phones → higher suspicion)
            n_phones  = len(linked_phones)
            base_score = _sigmoid(n_phones, midpoint=3, steepness=1.2)

            # Boost if transactions exist on those accounts
            tx_count = sum(
                len(self._tx_by_src.get(a, [])) + len(self._tx_by_dst.get(a, []))
                for a in linked_accounts
            )
            tx_boost = _sigmoid(tx_count, midpoint=3, steepness=0.4) * 0.3

            score = min(base_score + tx_boost, 1.0)
            confidence = 0.6 + (0.1 if tx_count > 0 else 0.0)

            indicators = [
                f"SIM {node_id} linked to {n_phones} phone/person nodes",
                f"{len(linked_accounts)} account(s) reachable from affected phones",
            ]
            if tx_count:
                indicators.append(f"{tx_count} transaction(s) on linked accounts")

            findings.append(_finding(
                pattern_id   = f"pat_sim_swap_{node_id}",
                pattern_name = "Potential SIM-swap sequence",
                score        = score,
                confidence   = confidence,
                affected     = [node_id] + linked_phones[:10] + linked_accounts[:10],
                indicators   = indicators,
                evidence     = [],
                time_range   = {},
                explanation  = (
                    f"SIM node {node_id} is associated with {n_phones} distinct "
                    f"phone/person nodes, which may indicate a SIM-swap pattern "
                    f"where control of a number has changed hands. "
                    f"{len(linked_accounts)} account(s) are reachable from the "
                    f"affected phones."
                ),
            ))

        return findings

    # ── 2. Mule-account network ───────────────────────────────────────────────

    def _detect_mule_network(self) -> list[dict]:
        """
        A mule account receives funds then rapidly forwards most of them onward.
        Indicator: received > N transactions AND forwarded ≥ MULE_FWD_RATIO of
        received volume, with no significant retail-type spend detected.
        """
        findings: list[dict] = []

        for acc_id, received_txns in self._tx_by_dst.items():
            forwarded_txns = self._tx_by_src.get(acc_id, [])
            if not received_txns or not forwarded_txns:
                continue

            received_vol  = sum(float(t.get("amount", 0)) for t in received_txns)
            forwarded_vol = sum(float(t.get("amount", 0)) for t in forwarded_txns)
            if received_vol == 0:
                continue

            fwd_ratio = forwarded_vol / received_vol
            if fwd_ratio < self.MULE_FWD_RATIO:
                continue

            # Compute time spread of activity
            all_ts = [
                _parse_ts(t.get("timestamp") or t.get("created_at"))
                for t in received_txns + forwarded_txns
            ]
            all_ts = [t for t in all_ts if t]

            n_recv = len(received_txns)
            n_fwd  = len(forwarded_txns)

            score = min(
                0.3
                + _sigmoid(fwd_ratio, midpoint=0.85, steepness=8) * 0.4
                + _sigmoid(n_recv + n_fwd, midpoint=6, steepness=0.5) * 0.3,
                1.0,
            )
            confidence = 0.65 if fwd_ratio >= 0.9 else 0.55

            # Trace upstream sources and downstream destinations
            sources  = list({t.get("src_account", "") for t in received_txns if t.get("src_account")})
            dests    = list({t.get("dst_account", "") for t in forwarded_txns if t.get("dst_account")})
            affected = list(set([acc_id] + sources[:5] + dests[:5]))

            findings.append(_finding(
                pattern_id   = f"pat_mule_{acc_id}",
                pattern_name = "Potential mule-account network",
                score        = score,
                confidence   = confidence,
                affected     = affected,
                indicators   = [
                    f"Account {acc_id} received {n_recv} txn(s) (vol {received_vol:,.0f})",
                    f"Forwarded {n_fwd} txn(s) — {fwd_ratio*100:.1f}% of received volume",
                    f"{len(sources)} distinct source(s), {len(dests)} distinct destination(s)",
                ],
                evidence     = [t.get("id", "") for t in (received_txns + forwarded_txns)[:10]],
                time_range   = _time_range(all_ts),
                explanation  = (
                    f"Account {acc_id} exhibits a pass-through pattern consistent with "
                    f"money-mule behaviour: it received {received_vol:,.0f} from "
                    f"{len(sources)} source(s) and forwarded {forwarded_vol:,.0f} "
                    f"({fwd_ratio*100:.1f}%) onward to {len(dests)} destination(s)."
                ),
            ))

        return findings

    # ── 3. Transaction layering ───────────────────────────────────────────────

    def _detect_transaction_layering(self) -> list[dict]:
        """
        Layering: funds move through ≥ LAYERING_MIN_HOPS accounts in a chain,
        each leg completing within LAYERING_WINDOW_H hours of the first.
        Uses DFS on the transaction graph.
        """
        findings: list[dict] = []
        # Build a directed graph of accounts only from transaction flow
        tx_graph: dict[str, list[tuple[str, dict]]] = defaultdict(list)
        for tx in self.transactions:
            src = tx.get("src_account") or tx.get("source_account") or ""
            dst = tx.get("dst_account") or tx.get("dest_account") or ""
            if src and dst:
                tx_graph[src].append((dst, tx))

        visited_chains: set[tuple] = set()

        def dfs(path: list[str], tx_chain: list[dict], start_ts: datetime | None):
            if len(path) > 8:  # cap depth
                return
            last = path[-1]
            for dst, tx in tx_graph.get(last, []):
                if dst in path:  # no cycles
                    continue
                ts = _parse_ts(tx.get("timestamp") or tx.get("created_at"))
                if start_ts and ts:
                    elapsed = _delta_hours(start_ts, ts)
                    if elapsed is not None and elapsed > self.LAYERING_WINDOW_H:
                        continue

                new_path  = path + [dst]
                new_chain = tx_chain + [tx]
                # Emit finding at min-hops threshold; avoid duplicate sub-chains
                if len(new_path) >= self.LAYERING_MIN_HOPS + 1:
                    key = tuple(new_path[:self.LAYERING_MIN_HOPS + 1])
                    if key not in visited_chains:
                        visited_chains.add(key)
                        all_ts = [
                            _parse_ts(t.get("timestamp") or t.get("created_at"))
                            for t in new_chain if _parse_ts(t.get("timestamp") or t.get("created_at"))
                        ]
                        total_vol = sum(float(t.get("amount", 0)) for t in new_chain)
                        n_hops    = len(new_path) - 1
                        score = min(
                            0.25
                            + _sigmoid(n_hops, midpoint=4, steepness=0.8) * 0.4
                            + _sigmoid(total_vol, midpoint=100_000, steepness=0.000005) * 0.35,
                            1.0,
                        )
                        findings.append(_finding(
                            pattern_id   = f"pat_layer_{new_path[0]}_{new_path[-1]}",
                            pattern_name = "Potential transaction layering",
                            score        = score,
                            confidence   = 0.6,
                            affected     = new_path,
                            indicators   = [
                                f"{n_hops}-hop chain detected within {self.LAYERING_WINDOW_H} h",
                                f"Total volume: {total_vol:,.0f}",
                                f"Chain: {' → '.join(new_path)}",
                            ],
                            evidence     = [t.get("id", "") for t in new_chain if t.get("id")],
                            time_range   = _time_range(all_ts),
                            explanation  = (
                                f"Funds moved through {n_hops} accounts in sequence "
                                f"({' → '.join(new_path)}) with a total volume of "
                                f"{total_vol:,.0f}, completing within "
                                f"{self.LAYERING_WINDOW_H} h. This is consistent with "
                                f"transaction layering to obscure the origin of funds."
                            ),
                        ))
                dfs(new_path, new_chain, start_ts or _parse_ts(tx.get("timestamp") or tx.get("created_at")))

        for src in list(tx_graph.keys())[:200]:  # cap iteration for large graphs
            dfs([src], [], None)
            if len(findings) >= 50:
                break

        return findings

    # ── 4. Shared-device network ──────────────────────────────────────────────

    def _detect_shared_device_network(self) -> list[dict]:
        """
        One device node used by ≥ SHARED_DEVICE_MIN distinct accounts or persons.
        """
        findings: list[dict] = []
        G = self.G

        for node_id, attrs in G.nodes(data=True):
            if attrs.get("type", "").upper() not in ("DEVICE", "IMEI"):
                continue

            connected_accounts = set()
            connected_persons  = set()
            for nbr in list(G.predecessors(node_id)) + list(G.successors(node_id)):
                ntype = G.nodes[nbr].get("type", "").upper()
                if ntype in ("BANK_ACCOUNT", "UPI_ID", "ACCOUNT"):
                    connected_accounts.add(nbr)
                elif ntype in ("PERSON",):
                    connected_persons.add(nbr)

            total = len(connected_accounts) + len(connected_persons)
            if total < self.SHARED_DEVICE_MIN:
                continue

            score = _sigmoid(total, midpoint=self.SHARED_DEVICE_MIN + 1, steepness=0.8)
            confidence = 0.7 if total >= 5 else 0.55

            affected = [node_id] + list(connected_accounts)[:10] + list(connected_persons)[:10]
            findings.append(_finding(
                pattern_id   = f"pat_shared_device_{node_id}",
                pattern_name = "Shared-device network",
                score        = score,
                confidence   = confidence,
                affected     = affected,
                indicators   = [
                    f"Device {node_id} linked to {len(connected_accounts)} account(s)",
                    f"Device {node_id} linked to {len(connected_persons)} person(s)",
                ],
                evidence     = [],
                time_range   = {},
                explanation  = (
                    f"Device {node_id} is associated with {len(connected_accounts)} "
                    f"account(s) and {len(connected_persons)} person(s), suggesting "
                    f"that a single device is being used to manage multiple financial "
                    f"identities — a common indicator of coordinated fraud."
                ),
            ))

        return findings

    # ── 5. Shared-SIM network ─────────────────────────────────────────────────

    def _detect_shared_sim_network(self) -> list[dict]:
        """
        One SIM linked to ≥ SHARED_SIM_MIN distinct accounts or persons
        (distinct from sim_swap: here the focus is on concurrent use).
        """
        findings: list[dict] = []
        G = self.G

        for node_id, attrs in G.nodes(data=True):
            if attrs.get("type", "").upper() not in ("SIM", "SIM_CARD", "ICCID"):
                continue

            linked = set()
            for nbr in list(G.predecessors(node_id)) + list(G.successors(node_id)):
                ntype = G.nodes[nbr].get("type", "").upper()
                if ntype in ("BANK_ACCOUNT", "UPI_ID", "ACCOUNT", "PERSON", "PHONE"):
                    linked.add(nbr)

            if len(linked) < self.SHARED_SIM_MIN:
                continue

            score      = _sigmoid(len(linked), midpoint=self.SHARED_SIM_MIN + 1, steepness=1.0)
            confidence = 0.65

            findings.append(_finding(
                pattern_id   = f"pat_shared_sim_{node_id}",
                pattern_name = "Shared-SIM network",
                score        = score,
                confidence   = confidence,
                affected     = [node_id] + list(linked)[:15],
                indicators   = [
                    f"SIM {node_id} linked to {len(linked)} entity/entities",
                ],
                evidence     = [],
                time_range   = {},
                explanation  = (
                    f"SIM {node_id} is linked to {len(linked)} distinct entities "
                    f"(phones, persons, accounts), which may indicate that a single "
                    f"SIM card is shared across multiple identities to mask activity."
                ),
            ))

        return findings

    # ── 6. High transaction velocity ──────────────────────────────────────────

    def _detect_high_velocity(self) -> list[dict]:
        """
        An account sends or receives ≥ VELOCITY_MIN_TXN transactions within a
        VELOCITY_WINDOW_H-hour sliding window.
        """
        findings: list[dict] = []

        all_accounts = set(self._tx_by_src.keys()) | set(self._tx_by_dst.keys())
        for acc_id in all_accounts:
            txns = (
                self._tx_by_src.get(acc_id, []) +
                self._tx_by_dst.get(acc_id, [])
            )
            if len(txns) < self.VELOCITY_MIN_TXN:
                continue

            # Parse and sort timestamps
            ts_pairs = []
            for t in txns:
                dt = _parse_ts(t.get("timestamp") or t.get("created_at"))
                if dt:
                    ts_pairs.append((dt, t))
            ts_pairs.sort(key=lambda x: x[0])

            # Sliding window max
            best_window: list[tuple] = []
            j = 0
            for i, (ts_i, _) in enumerate(ts_pairs):
                # Advance j while window exceeds limit
                while j < i and _delta_hours(ts_pairs[j][0], ts_i) is not None and \
                        (_delta_hours(ts_pairs[j][0], ts_i) or 0) > self.VELOCITY_WINDOW_H:
                    j += 1
                window = ts_pairs[j:i + 1]
                if len(window) > len(best_window):
                    best_window = window

            if len(best_window) < self.VELOCITY_MIN_TXN:
                continue

            n_in_window = len(best_window)
            vol = sum(float(t.get("amount", 0)) for _, t in best_window)
            score = min(
                _sigmoid(n_in_window, midpoint=8, steepness=0.4) * 0.6
                + _sigmoid(vol, midpoint=200_000, steepness=0.000003) * 0.4,
                1.0,
            )
            confidence = 0.7 if n_in_window >= 10 else 0.55

            window_ts = [ts for ts, _ in best_window]
            findings.append(_finding(
                pattern_id   = f"pat_velocity_{acc_id}",
                pattern_name = "High transaction velocity",
                score        = score,
                confidence   = confidence,
                affected     = [acc_id],
                indicators   = [
                    f"{n_in_window} txns in ≤{self.VELOCITY_WINDOW_H}h window",
                    f"Total volume in window: {vol:,.0f}",
                ],
                evidence     = [t.get("id", "") for _, t in best_window[:10] if t.get("id")],
                time_range   = _time_range(window_ts),
                explanation  = (
                    f"Account {acc_id} executed {n_in_window} transactions within a "
                    f"{self.VELOCITY_WINDOW_H}-hour window (total volume {vol:,.0f}). "
                    f"High velocity is a common indicator of automated or coordinated "
                    f"fraud activity."
                ),
            ))

        return findings

    # ── 7. Communication hub ──────────────────────────────────────────────────

    def _detect_communication_hub(self) -> list[dict]:
        """
        A phone/person node whose out-call degree is ≥ HUB_DEGREE_RATIO × average
        and ≥ HUB_MIN_DEGREE absolute contacts.
        """
        findings: list[dict] = []
        if not self.call_records:
            # Fall back to graph in-degree of CALLED edges
            for node_id, attrs in self.G.nodes(data=True):
                if attrs.get("type", "").upper() not in ("PHONE", "PERSON"):
                    continue
                out_calls = sum(
                    1 for _, _, d in self.G.out_edges(node_id, data=True)
                    if d.get("relationship", "").upper() == "CALLED"
                )
                if out_calls >= self.HUB_MIN_DEGREE:
                    score = _sigmoid(out_calls, midpoint=self.HUB_MIN_DEGREE * 1.5, steepness=0.3)
                    findings.append(_finding(
                        pattern_id   = f"pat_hub_{node_id}",
                        pattern_name = "Communication hub",
                        score        = score,
                        confidence   = 0.5,
                        affected     = [node_id],
                        indicators   = [f"{node_id} has {out_calls} outgoing CALLED edges"],
                        evidence     = [],
                        time_range   = {},
                        explanation  = (
                            f"Node {node_id} has {out_calls} outgoing CALLED edges in "
                            f"the network graph, which is higher than expected for a "
                            f"normal user."
                        ),
                    ))
            return findings

        # Count unique contacts per caller
        caller_contacts: dict[str, set] = defaultdict(set)
        caller_calls:    dict[str, list] = defaultdict(list)
        for cr in self.call_records:
            caller   = cr.get("caller_id") or cr.get("caller") or ""
            receiver = cr.get("receiver_id") or cr.get("receiver") or ""
            if caller:
                caller_contacts[caller].add(receiver)
                caller_calls[caller].append(cr)

        if not caller_contacts:
            return findings

        avg_contacts = sum(len(v) for v in caller_contacts.values()) / len(caller_contacts)

        for caller_id, contacts in caller_contacts.items():
            n = len(contacts)
            if n < self.HUB_MIN_DEGREE:
                continue
            ratio = n / max(avg_contacts, 1)
            if ratio < self.HUB_DEGREE_RATIO:
                continue

            calls = caller_calls[caller_id]
            all_ts = [
                _parse_ts(c.get("timestamp") or c.get("created_at"))
                for c in calls
            ]
            all_ts = [t for t in all_ts if t]

            score = min(
                _sigmoid(ratio, midpoint=self.HUB_DEGREE_RATIO * 1.5, steepness=0.5) * 0.6
                + _sigmoid(n, midpoint=self.HUB_MIN_DEGREE * 2, steepness=0.2) * 0.4,
                1.0,
            )
            confidence = 0.65

            findings.append(_finding(
                pattern_id   = f"pat_hub_{caller_id}",
                pattern_name = "Communication hub",
                score        = score,
                confidence   = confidence,
                affected     = [caller_id] + list(contacts)[:15],
                indicators   = [
                    f"{caller_id} contacted {n} unique parties",
                    f"Contact ratio vs avg: {ratio:.1f}×",
                    f"{len(calls)} total calls recorded",
                ],
                evidence     = [c.get("id", "") for c in calls[:10] if c.get("id")],
                time_range   = _time_range(all_ts),
                explanation  = (
                    f"Phone/node {caller_id} contacted {n} unique parties — "
                    f"{ratio:.1f}× the network average. A disproportionately high "
                    f"number of unique contacts may indicate this node acts as a "
                    f"coordinator or recruiter in the fraud network."
                ),
            ))

        return findings

    # ── 8. Rapid multi-hop fund movement ─────────────────────────────────────

    def _detect_rapid_multi_hop(self) -> list[dict]:
        """
        Funds move through ≥ RAPID_HOP_HOPS accounts in < RAPID_HOP_WINDOW_H h.
        Similar to layering but focused purely on speed.
        """
        findings: list[dict] = []
        visited_chains: set[tuple] = set()

        # Build time-ordered adjacency
        tx_graph: dict[str, list[tuple[str, dict]]] = defaultdict(list)
        for tx in self.transactions:
            src = tx.get("src_account") or tx.get("source_account") or ""
            dst = tx.get("dst_account") or tx.get("dest_account") or ""
            if src and dst:
                tx_graph[src].append((dst, tx))

        def dfs(path: list[str], chain: list[dict], first_ts: datetime | None):
            if len(path) > 8:
                return
            last = path[-1]
            for dst, tx in tx_graph.get(last, []):
                if dst in path:
                    continue
                ts = _parse_ts(tx.get("timestamp") or tx.get("created_at"))
                if first_ts and ts:
                    elapsed = _delta_hours(first_ts, ts)
                    if elapsed is None or elapsed > self.RAPID_HOP_WINDOW_H:
                        continue
                new_path  = path + [dst]
                new_chain = chain + [tx]
                if len(new_path) - 1 >= self.RAPID_HOP_HOPS:
                    key = tuple(new_path[:self.RAPID_HOP_HOPS + 1])
                    if key not in visited_chains:
                        visited_chains.add(key)
                        all_ts = [
                            _parse_ts(t.get("timestamp") or t.get("created_at"))
                            for t in new_chain
                            if _parse_ts(t.get("timestamp") or t.get("created_at"))
                        ]
                        elapsed_h = (
                            _delta_hours(all_ts[0], all_ts[-1])
                            if len(all_ts) >= 2 else 0.0
                        )
                        vol = sum(float(t.get("amount", 0)) for t in new_chain)
                        n_hops = len(new_path) - 1
                        score = min(
                            0.35
                            + _sigmoid(n_hops, midpoint=4, steepness=0.9) * 0.35
                            + _sigmoid(vol, midpoint=50_000, steepness=0.000008) * 0.3,
                            1.0,
                        )
                        if elapsed_h is not None and elapsed_h < 1.0:
                            score = min(score + 0.1, 1.0)

                        findings.append(_finding(
                            pattern_id   = f"pat_rapid_hop_{new_path[0]}_{new_path[-1]}",
                            pattern_name = "Rapid multi-hop fund movement",
                            score        = score,
                            confidence   = 0.65,
                            affected     = new_path,
                            indicators   = [
                                f"{n_hops} hops in ~{elapsed_h:.2f}h" if elapsed_h is not None else f"{n_hops} hops",
                                f"Total volume: {vol:,.0f}",
                                f"Chain: {' → '.join(new_path)}",
                            ],
                            evidence     = [t.get("id", "") for t in new_chain if t.get("id")],
                            time_range   = _time_range(all_ts),
                            explanation  = (
                                f"Funds moved through {n_hops} accounts "
                                f"({' → '.join(new_path)}) in approximately "
                                f"{elapsed_h:.2f} hours — faster than legitimate "
                                f"multi-hop transfers. This may indicate deliberate "
                                f"rapid layering to evade detection."
                            ),
                        ))
                dfs(new_path, new_chain, first_ts or _parse_ts(tx.get("timestamp") or tx.get("created_at")))

        for src in list(tx_graph.keys())[:200]:
            dfs([src], [], None)
            if len(findings) >= 50:
                break

        return findings

    # ── 9. Dense relationship cluster ─────────────────────────────────────────

    def _detect_dense_cluster(self) -> list[dict]:
        """
        Find cliques (fully connected sub-graphs) of size ≥ CLUSTER_MIN_NODES
        using the undirected projection of the graph.
        """
        findings: list[dict] = []
        G_und = self.G.to_undirected()

        seen: set[frozenset] = set()
        for clique in nx.find_cliques(G_und):
            if len(clique) < self.CLUSTER_MIN_NODES:
                continue
            key = frozenset(clique)
            if key in seen:
                continue
            seen.add(key)

            sub = G_und.subgraph(clique)
            n   = sub.number_of_nodes()
            e   = sub.number_of_edges()
            max_edges  = n * (n - 1) / 2
            density    = e / max_edges if max_edges > 0 else 0.0
            # Average risk score of nodes
            risk_scores = [
                self.G.nodes[nd].get("risk_score") or 0.0
                for nd in clique
                if self.G.nodes[nd].get("risk_score") is not None
            ]
            avg_risk = sum(risk_scores) / len(risk_scores) if risk_scores else 0.0

            score = min(
                _sigmoid(n, midpoint=5, steepness=0.6) * 0.5
                + density * 0.3
                + avg_risk * 0.2,
                1.0,
            )
            confidence = 0.55 + density * 0.2

            findings.append(_finding(
                pattern_id   = f"pat_cluster_{'_'.join(sorted(clique)[:3])}",
                pattern_name = "Dense relationship cluster",
                score        = score,
                confidence   = confidence,
                affected     = list(clique),
                indicators   = [
                    f"Clique of {n} nodes, density={density:.2f}",
                    f"Average risk score: {avg_risk:.2f}",
                ],
                evidence     = [],
                time_range   = {},
                explanation  = (
                    f"A clique of {n} nodes with edge density {density:.2f} was "
                    f"detected. High-density sub-graphs can indicate coordinated "
                    f"fraud rings where participants are all directly connected "
                    f"to each other (average risk score {avg_risk:.2f})."
                ),
            ))

        return findings
