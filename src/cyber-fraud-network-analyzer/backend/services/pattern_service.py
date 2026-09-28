"""
services/pattern_service.py

Orchestrates fraud pattern detection and network role analysis.

Loads data from JSON files, builds the NetworkX graph, runs detectors,
persists findings to data/processed/patterns.json and
data/processed/network_roles.json.
"""

from __future__ import annotations

from pathlib import Path

from config.settings import DATA_DIR
from graph.graph_service import build_graph
from graph.pattern_detector import PatternDetector
from graph.role_analyzer import RoleAnalyzer
from storage.file_store import read_json, write_json, now_iso

# ── File paths (module-level so they can be patched in tests) ─────────────────
PATTERNS_FILE    = DATA_DIR / "processed" / "patterns.json"
ROLES_FILE       = DATA_DIR / "processed" / "network_roles.json"
TRANSACTIONS_FILE = DATA_DIR / "sample"  / "transactions.json"
CALL_RECORDS_FILE = DATA_DIR / "sample"  / "call_records.json"
SIMS_FILE         = DATA_DIR / "sample"  / "sims.json"


def _load_case_data(case_id: str) -> tuple[list, list, list]:
    """
    Load transactions, call records, and SIM records for a case.

    Tries data/processed/<case_id>/transactions.json first,
    then falls back to data/sample/ demo data.
    """
    processed_base = DATA_DIR / "processed" / case_id

    def _load(live_path: Path, sample_path: Path) -> list:
        live = read_json(live_path) or []
        if isinstance(live, list) and live:
            return live
        sample = read_json(sample_path) or []
        if isinstance(sample, list):
            return sample
        return []

    transactions = _load(
        processed_base / "transactions.json",
        TRANSACTIONS_FILE,
    )
    call_records = _load(
        processed_base / "calls.json",
        CALL_RECORDS_FILE,
    )
    sims = _load(
        processed_base / "sims.json",
        SIMS_FILE,
    )

    # Filter to this case if records carry a case_id field
    def _filter(records: list) -> list:
        tagged = [r for r in records if r.get("case_id") == case_id]
        return tagged if tagged else records   # fall back to all if no match

    return (
        _filter(transactions),
        _filter(call_records),
        _filter(sims),
    )


def run_pattern_analysis(case_id: str) -> dict:
    """
    Run full pattern detection for a case.
    Returns result dict and persists to PATTERNS_FILE.
    """
    G = build_graph(case_id)
    transactions, call_records, sims = _load_case_data(case_id)

    detector = PatternDetector(
        G            = G,
        transactions = transactions,
        call_records = call_records,
        sims         = sims,
        case_id      = case_id,
    )
    findings = detector.detect_all()

    result = {
        "case_id":      case_id,
        "analyzed_at":  now_iso(),
        "total_findings": len(findings),
        "findings":     findings,
        "stats": {
            "node_count":  G.number_of_nodes(),
            "edge_count":  G.number_of_edges(),
            "tx_count":    len(transactions),
            "call_count":  len(call_records),
        },
    }

    # Persist — keyed by case_id so multiple cases can coexist
    _upsert_case_result(PATTERNS_FILE, case_id, result)
    return result


def run_role_analysis(case_id: str) -> dict:
    """
    Run role analysis for all entities in a case.
    Returns result dict and persists to ROLES_FILE.
    """
    G = build_graph(case_id)
    transactions, call_records, _ = _load_case_data(case_id)

    analyzer = RoleAnalyzer(
        G            = G,
        transactions = transactions,
        call_records = call_records,
    )
    roles = analyzer.analyze()

    # Summary tallies
    role_counts: dict[str, int] = {}
    for r in roles:
        role = r.get("primary_role", "Unknown")
        role_counts[role] = role_counts.get(role, 0) + 1

    result = {
        "case_id":     case_id,
        "analyzed_at": now_iso(),
        "total_entities": len(roles),
        "role_summary":   role_counts,
        "roles":          roles,
    }

    _upsert_case_result(ROLES_FILE, case_id, result)
    return result


def get_patterns(case_id: str) -> dict | None:
    """Return stored pattern analysis for a case, or None if not yet run."""
    store = read_json(PATTERNS_FILE) or {}
    return store.get(case_id)


def get_roles(case_id: str) -> dict | None:
    """Return stored role analysis for a case, or None if not yet run."""
    store = read_json(ROLES_FILE) or {}
    return store.get(case_id)


# ── Persistence helpers ───────────────────────────────────────────────────────

def _upsert_case_result(filepath: Path, case_id: str, result: dict) -> None:
    """
    Store result under case_id key in a top-level dict JSON file.
    Creates the file if it doesn't exist.
    """
    store: dict = read_json(filepath) or {}
    store[case_id] = result
    write_json(filepath, store)
