"""
storage/file_store.py
File-based storage utilities — JSON and CSV operations.
No database. All data lives on the local filesystem.
"""

import csv
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional


# ── Helpers ──────────────────────────────────────────────────────────────────

def _ensure(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def generate_id(prefix: str = "") -> str:
    """Create a unique ID like 'case_a1b2c3d4'."""
    uid = uuid.uuid4().hex[:12]
    return f"{prefix}_{uid}" if prefix else uid


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


# ── JSON operations ───────────────────────────────────────────────────────────

def read_json(path: str | Path) -> Any:
    """Read and return parsed JSON from a file. Returns None if file missing."""
    p = Path(path)
    if not p.exists():
        return None
    return json.loads(p.read_text(encoding="utf-8"))


def write_json(path: str | Path, data: Any, indent: int = 2) -> None:
    """Write data as pretty-printed JSON, creating parent dirs as needed."""
    p = _ensure(Path(path))
    p.write_text(json.dumps(data, indent=indent, default=str), encoding="utf-8")


def append_json_record(path: str | Path, record: Dict) -> Dict:
    """
    Append a single record to a JSON array file.
    Creates the file with an empty array if it doesn't exist.
    Returns the record with auto-assigned id/created_at if missing.
    """
    p = Path(path)
    records: List[Dict] = read_json(p) or []

    if "id" not in record:
        record["id"] = generate_id()
    if "created_at" not in record:
        record["created_at"] = now_iso()

    records.append(record)
    write_json(p, records)
    return record


def update_json_record(
    path: str | Path,
    record_id: str,
    updates: Dict,
    id_field: str = "id",
) -> Optional[Dict]:
    """
    Find a record by id_field and merge updates into it.
    Returns the updated record, or None if not found.
    """
    p = Path(path)
    records: List[Dict] = read_json(p) or []
    updated = None
    for rec in records:
        if rec.get(id_field) == record_id:
            rec.update(updates)
            rec["updated_at"] = now_iso()
            updated = rec
            break
    if updated:
        write_json(p, records)
    return updated


def search_json_records(
    path: str | Path,
    predicate: Callable[[Dict], bool],
) -> List[Dict]:
    """Return all records from a JSON array file that satisfy predicate."""
    records: List[Dict] = read_json(path) or []
    return [r for r in records if predicate(r)]


# ── CSV operations ────────────────────────────────────────────────────────────

def read_csv(path: str | Path) -> List[Dict]:
    """Read a CSV file and return list of row dicts."""
    p = Path(path)
    if not p.exists():
        return []
    with p.open(encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def write_csv(path: str | Path, rows: List[Dict], fieldnames: Optional[List[str]] = None) -> None:
    """Write list of dicts to CSV, creating parent dirs as needed."""
    if not rows:
        return
    p = _ensure(Path(path))
    fields = fieldnames or list(rows[0].keys())
    with p.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def append_csv_row(path: str | Path, row: Dict, fieldnames: Optional[List[str]] = None) -> None:
    """Append a single row to a CSV file. Creates with header if new."""
    p = Path(path)
    fields = fieldnames or list(row.keys())
    write_header = not p.exists()
    _ensure(p)
    with p.open("a", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields, extrasaction="ignore")
        if write_header:
            writer.writeheader()
        writer.writerow(row)


def search_csv_rows(
    path: str | Path,
    predicate: Callable[[Dict], bool],
) -> List[Dict]:
    """Return all CSV rows that satisfy predicate."""
    return [r for r in read_csv(path) if predicate(r)]
