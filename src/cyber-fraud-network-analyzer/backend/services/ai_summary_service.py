"""
services/ai_summary_service.py

Generates a structured FIR-ready investigation summary from graph data,
detected patterns, network roles, and the timeline.

PROVIDER: Mock (deterministic — derived entirely from real data records,
          no hallucination, no LLM calls).

All claims are sourced from actual data records and labelled by confidence:
  observed_evidence       — directly read from a data record
  inferred_relationship   — deduced from graph structure
  model_prediction        — output of the ML model
  investigator_conclusion — placeholder for investigator to fill in

Output is saved to data/reports/<case_id>_summary.json.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from config.settings import DATA_DIR
from storage.file_store import read_json, write_json, now_iso
from services.timeline_service import get_timeline
from services.evidence_service import list_evidence
from services.pattern_service import get_patterns, get_roles
from graph.graph_service import build_graph

# ── Paths ─────────────────────────────────────────────────────────────────────
REPORTS_DIR   = DATA_DIR / "reports"
CASES_FILE    = DATA_DIR / "cases" / "cases.json"
ENTITIES_FILE = DATA_DIR / "entities" / "entities.json"
SAMPLE_CASES  = DATA_DIR / "sample" / "cases.json"


def _load_case(case_id: str) -> Optional[dict]:
    for path in (CASES_FILE, SAMPLE_CASES):
        records = read_json(path) or []
        rec = next(
            (c for c in records if c.get("id") == case_id or c.get("case_id") == case_id),
            None,
        )
        if rec:
            return rec
    return None


def _load_entities_for_case(case_id: str) -> list[dict]:
    live = read_json(ENTITIES_FILE) or []
    case_ents = [
        e for e in live
        if case_id in (e.get("case_ids") or [e.get("case_id", "")])
    ]
    if case_ents:
        return case_ents
    # fallback sample
    sample = read_json(DATA_DIR / "sample" / "entities.json") or []
    return sample


# ── Section generators ────────────────────────────────────────────────────────

def _incident_summary(case: dict, patterns_data: Optional[dict]) -> dict:
    pattern = case.get("fraud_pattern") or case.get("pattern_code") or "unknown"
    severity = case.get("severity", "unknown")
    status   = case.get("status", "unknown")
    total    = case.get("total_loss_inr") or case.get("total_loss") or 0
    findings_count = len((patterns_data or {}).get("findings", []))
    return {
        "title":       case.get("title", case.get("id", "Unknown")),
        "case_id":     case.get("id", ""),
        "status":      status,
        "severity":    severity,
        "fraud_pattern": pattern,
        "jurisdiction":  case.get("jurisdiction", ""),
        "assigned_to":   case.get("assigned_to", ""),
        "total_loss_inr": float(total),
        "patterns_detected": findings_count,
        "confidence":  "observed_evidence",
        "note": (
            f"Investigation into {pattern.replace('_', ' ').title()} fraud. "
            f"Case severity: {severity}. Current status: {status}."
        ),
    }


def _victim_summary(case: dict, entities: list[dict]) -> dict:
    victim_ids = case.get("victim_ids") or []
    victim_entities = [
        e for e in entities
        if e.get("type") in ("VICTIM", "PERSON") and
        (e.get("entity_id") or e.get("id")) in victim_ids
    ]
    return {
        "victim_count": len(victim_ids),
        "victim_ids":   victim_ids,
        "victim_details": [
            {
                "entity_id":  e.get("entity_id") or e.get("id"),
                "value":      e.get("value") or e.get("label"),
                "risk_score": e.get("risk_score"),
            }
            for e in victim_entities
        ],
        "confidence": "observed_evidence",
    }


def _transaction_summary(patterns_data: Optional[dict], timeline: list[dict]) -> dict:
    tx_events = [e for e in timeline if e["event_type"] == "transaction"]
    findings  = (patterns_data or {}).get("findings") or []
    stats     = (patterns_data or {}).get("stats") or {}
    return {
        "transaction_event_count": len(tx_events),
        "graph_tx_count":          stats.get("tx_count", 0),
        "flagged_patterns":        len(findings),
        "pattern_names":           list({f.get("pattern_type", f.get("pattern")) for f in findings}),
        "confidence":              "observed_evidence",
        "note": (
            f"{len(tx_events)} transaction events found in the investigation timeline. "
            f"{len(findings)} suspicious pattern(s) detected."
        ),
    }


def _network_summary(G, roles_data: Optional[dict]) -> dict:
    roles = (roles_data or {}).get("roles") or []
    role_counts = (roles_data or {}).get("role_summary") or {}
    return {
        "node_count":   G.number_of_nodes(),
        "edge_count":   G.number_of_edges(),
        "entity_count": len(roles),
        "role_distribution": role_counts,
        "confidence":   "observed_evidence" if G.number_of_nodes() > 0 else "inferred_relationship",
    }


def _timeline_summary(timeline: list[dict]) -> dict:
    by_type: dict[str, int] = {}
    for ev in timeline:
        by_type[ev["event_type"]] = by_type.get(ev["event_type"], 0) + 1
    first_ts = timeline[0]["timestamp"] if timeline else None
    last_ts  = timeline[-1]["timestamp"] if timeline else None
    return {
        "total_events":        len(timeline),
        "event_type_counts":   by_type,
        "first_event":         first_ts,
        "last_event":          last_ts,
        "confidence":          "observed_evidence",
    }


def _detected_patterns(patterns_data: Optional[dict]) -> list[dict]:
    findings = (patterns_data or {}).get("findings") or []
    out = []
    for f in findings:
        out.append({
            "pattern_type":  f.get("pattern_type") or f.get("pattern"),
            "confidence":    f.get("confidence", 0),
            "affected_entities": f.get("entities") or f.get("affected_entities") or [],
            "indicators":    f.get("indicators") or [],
            "evidence_ids":  f.get("evidence_ids") or [],
            "source_label":  "observed_evidence",
        })
    return out


def _ml_analysis(case_id: str, entities: list[dict]) -> dict:
    """
    If there are ML prediction results for this case, summarise them.
    Does NOT run the model — only reads saved predictions.
    """
    predictions_file = DATA_DIR / "predictions" / "predictions.json"
    predictions = read_json(predictions_file) or []
    case_preds = [p for p in predictions if p.get("case_id") == case_id]
    high_risk = [p for p in case_preds if p.get("classification") in ("HIGH_RISK", "MEDIUM_RISK")]
    return {
        "predictions_run":    len(case_preds),
        "high_risk_entities": len(high_risk),
        "model_version":      case_preds[0].get("model_version") if case_preds else None,
        "confidence":         "model_prediction",
        "disclaimer": (
            "ML predictions are probabilistic estimates. "
            "They are NOT proof of criminal activity. "
            "All predictions require investigator review."
        ),
        "high_risk_list": [
            {"entity_id": p.get("entity_id"), "risk_score": p.get("risk_score"),
             "classification": p.get("classification")}
            for p in high_risk[:10]
        ],
    }


def _network_roles_section(roles_data: Optional[dict]) -> list[dict]:
    roles = (roles_data or {}).get("roles") or []
    top = sorted(roles, key=lambda r: r.get("risk_score", 0), reverse=True)[:20]
    return [
        {
            "entity_id":   r.get("entity_id"),
            "primary_role": r.get("primary_role"),
            "risk_score":  r.get("risk_score"),
            "confidence":  "inferred_relationship",
        }
        for r in top
    ]


def _key_evidence(evidence: list[dict], patterns_data: Optional[dict]) -> list[dict]:
    """
    Return up to 10 key evidence records — prioritise verified + cited in patterns.
    """
    cited_ids: set[str] = set()
    for f in (patterns_data or {}).get("findings", []):
        for eid in (f.get("evidence_ids") or []):
            cited_ids.add(eid)

    def _key(ev: dict) -> int:
        score = 0
        if ev.get("is_verified"):
            score += 10
        if (ev.get("evidence_id") or ev.get("id")) in cited_ids:
            score += 5
        return score

    ranked = sorted(evidence, key=_key, reverse=True)[:10]
    return [
        {
            "evidence_id":   e.get("evidence_id"),
            "type":          e.get("type"),
            "description":   e.get("description"),
            "timestamp":     e.get("timestamp"),
            "is_verified":   e.get("is_verified"),
            "confidence":    "observed_evidence",
        }
        for e in ranked
    ]


def _open_questions(case: dict, patterns_data: Optional[dict]) -> list[str]:
    questions = [
        "[INVESTIGATOR TO COMPLETE] Identify and record all victim financial accounts.",
        "[INVESTIGATOR TO COMPLETE] Obtain call detail records (CDR) from telecom operators.",
        "[INVESTIGATOR TO COMPLETE] Verify KYC documents for all flagged accounts.",
        "[INVESTIGATOR TO COMPLETE] Trace final destination of fraudulent funds.",
        "[INVESTIGATOR TO COMPLETE] Establish digital evidence chain of custody.",
    ]
    # Add pattern-specific questions
    pattern = case.get("fraud_pattern", "")
    if pattern == "sim_swap":
        questions.append("[INVESTIGATOR TO COMPLETE] Obtain SIM swap logs from telecom operator.")
    elif pattern == "mule_network":
        questions.append("[INVESTIGATOR TO COMPLETE] Map all mule accounts and recruiters.")
    elif pattern == "transaction_layering":
        questions.append("[INVESTIGATOR TO COMPLETE] Trace each layered hop to final beneficiary.")
    return questions


def _recommended_actions(case: dict, patterns_data: Optional[dict]) -> list[str]:
    actions = [
        "Freeze flagged accounts pending investigation per applicable banking regulations.",
        "Issue formal notice to account-holding banks for transaction details.",
        "File FIR with jurisdictional cybercrime cell with this report as annexure.",
        "Coordinate with CERT-In if digital infrastructure compromise is suspected.",
        "Submit to Financial Intelligence Unit (FIU-IND) if amount exceeds reporting threshold.",
    ]
    pattern = case.get("fraud_pattern", "")
    if pattern == "sim_swap":
        actions.append("Issue direction to telecom operator to block involved SIM cards.")
    elif pattern == "mule_network":
        actions.append("Identify and summon known mule account holders for questioning.")
    return actions


def _limitations() -> list[str]:
    return [
        "This summary is AI-generated from structured data and requires investigator verification.",
        "All ML predictions are probabilistic — not proof of criminal activity.",
        "Data is from the investigation system only; external records not consulted.",
        "Timestamp data may be incomplete; timeline may not reflect all events.",
        "Entity relationships marked 'inferred' require corroboration from primary sources.",
        "This document does NOT constitute a legally admissible statement.",
    ]


# ── Main public function ──────────────────────────────────────────────────────

def generate_summary(case_id: str) -> dict:
    """
    Generate and persist an investigation summary for *case_id*.

    Returns the summary dict.
    """
    case = _load_case(case_id)
    if not case:
        # Return a minimal stub rather than raising
        case = {"id": case_id, "title": f"Case {case_id}", "status": "unknown"}

    entities      = _load_entities_for_case(case_id)
    timeline      = get_timeline(case_id)
    evidence      = list_evidence(case_id)
    patterns_data = get_patterns(case_id)
    roles_data    = get_roles(case_id)

    try:
        G = build_graph(case_id)
    except Exception:
        import networkx as nx
        G = nx.DiGraph()

    summary = {
        "summary_id":     f"sum_{case_id}",
        "case_id":        case_id,
        "generated_at":   now_iso(),
        "provider":       "mock",
        "version":        "1.0",
        "disclaimer": (
            "AI-GENERATED DRAFT — REQUIRES INVESTIGATOR VERIFICATION. "
            "This document does not constitute a legally admissible statement. "
            "All claims labelled 'model_prediction' or 'inferred_relationship' "
            "must be corroborated by primary sources before inclusion in an FIR."
        ),
        "sections": {
            "incident_summary":    _incident_summary(case, patterns_data),
            "victim_summary":      _victim_summary(case, entities),
            "transaction_summary": _transaction_summary(patterns_data, timeline),
            "network_summary":     _network_summary(G, roles_data),
            "timeline_summary":    _timeline_summary(timeline),
            "detected_patterns":   _detected_patterns(patterns_data),
            "ml_analysis":         _ml_analysis(case_id, entities),
            "network_roles":       _network_roles_section(roles_data),
            "key_evidence":        _key_evidence(evidence, patterns_data),
            "open_questions":      _open_questions(case, patterns_data),
            "recommended_actions": _recommended_actions(case, patterns_data),
            "limitations":         _limitations(),
        },
    }

    # Persist
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    report_path = REPORTS_DIR / f"{case_id}_summary.json"
    write_json(report_path, summary)

    return summary


def get_summary(case_id: str) -> Optional[dict]:
    """Return a previously generated summary, or None."""
    path = REPORTS_DIR / f"{case_id}_summary.json"
    return read_json(path)
