"""
services/intelligence_service.py
Intelligence file ingestion + normalisation pipeline.

Supported formats: CSV, JSON, TXT, XLSX
Supported record types:
  transactions, calls, sims, devices, bank_accounts,
  upi_ids, complaints, phones, locations

All uploaded files are kept under data/raw/<case_id>/
Normalised records are written to data/processed/<case_id>/<type>.json
Evidence metadata is appended to data/evidence/evidence.json
"""

from __future__ import annotations

import csv
import io
import json
import re
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from config.settings import DATA_DIR
from storage.file_store import (
    read_json, write_json, append_json_record, generate_id, now_iso,
)

# ── Config ────────────────────────────────────────────────────────────────────
RAW_DIR       = DATA_DIR / "raw"
PROCESSED_DIR = DATA_DIR / "processed"
EVIDENCE_FILE = DATA_DIR / "evidence" / "evidence.json"

MAX_FILE_BYTES   = 50 * 1024 * 1024   # 50 MB
ALLOWED_EXT      = {".csv", ".json", ".txt", ".xlsx"}
ALLOWED_MIME     = {
    "text/csv", "application/json", "text/plain",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "application/vnd.ms-excel",
}

# Record types the API accepts as a hint
VALID_RECORD_TYPES = {
    "transactions", "calls", "sims", "devices",
    "bank_accounts", "upi_ids", "complaints", "phones", "locations",
}


# ── File validation ───────────────────────────────────────────────────────────

def _safe_filename(name: str) -> str:
    """
    Sanitise an uploaded filename:
    - Normalise unicode to ASCII
    - Keep only safe characters
    - Prevent path traversal
    """
    name = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    name = re.sub(r"[^\w.\-]", "_", name)
    name = re.sub(r"\.{2,}", ".", name)
    name = name.lstrip("._/\\")
    return name or "upload"


def validate_upload(filename: str, size_bytes: int, content: bytes) -> list[str]:
    """Return list of validation errors (empty = valid)."""
    errors: list[str] = []

    safe = _safe_filename(filename)
    ext  = Path(safe).suffix.lower()

    if not filename:
        errors.append("Filename is required")
    if ext not in ALLOWED_EXT:
        errors.append(f"Unsupported file type '{ext}'. Allowed: {', '.join(sorted(ALLOWED_EXT))}")
    if size_bytes > MAX_FILE_BYTES:
        errors.append(f"File too large ({size_bytes // 1024} KB). Maximum is {MAX_FILE_BYTES // 1024} KB")
    if size_bytes == 0:
        errors.append("File is empty")
    if len(filename) > 255:
        errors.append("Filename too long (max 255 characters)")

    # Basic content checks (only if extension checks passed)
    if not errors:
        if ext == ".json":
            try:
                json.loads(content)
            except json.JSONDecodeError as e:
                errors.append(f"Malformed JSON: {e}")
        elif ext == ".csv":
            try:
                text = content.decode("utf-8", errors="replace")
                reader = csv.reader(io.StringIO(text))
                rows = list(reader)
                if len(rows) < 2:
                    errors.append("CSV has no data rows (only a header or is empty)")
            except Exception as e:
                errors.append(f"Could not parse CSV: {e}")
        elif ext == ".xlsx":
            try:
                import openpyxl
                openpyxl.load_workbook(io.BytesIO(content), read_only=True)
            except Exception as e:
                errors.append(f"Could not parse XLSX: {e}")

    return errors


# ── Raw file storage ──────────────────────────────────────────────────────────

def _store_raw(case_id: str, safe_name: str, content: bytes) -> Path:
    dest_dir = RAW_DIR / case_id
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / safe_name
    dest.write_bytes(content)
    return dest


# ── Normalisation pipeline ───────────────────────────────────────────────────

def _coerce_timestamp(val: Any) -> str | None:
    """Try to parse any timestamp-ish value to ISO-8601 string."""
    if not val:
        return None
    s = str(val).strip()
    for fmt in (
        "%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%d %H:%M:%S", "%Y-%m-%d",
        "%d/%m/%Y %H:%M:%S", "%d/%m/%Y",
        "%d-%m-%Y %H:%M:%S", "%d-%m-%Y",
        "%m/%d/%Y %H:%M:%S", "%m/%d/%Y",
    ):
        try:
            return datetime.strptime(s, fmt).isoformat() + "Z"
        except ValueError:
            pass
    return s   # keep original if unparseable


def _normalise_amount(val: Any) -> float | None:
    if val is None or str(val).strip() == "":
        return None
    try:
        return float(str(val).replace(",", "").replace("₹", "").strip())
    except ValueError:
        return None


def _col(row: dict, *keys: str) -> Any:
    """Case-insensitive column lookup across a list of candidate keys."""
    lower_row = {k.lower().strip(): v for k, v in row.items()}
    for k in keys:
        v = lower_row.get(k.lower())
        if v is not None and str(v).strip() != "":
            return str(v).strip()
    return None


# ─── Per-type normalisers ─────────────────────────────────────────────────────

def _norm_transaction(raw: dict, src_meta: dict) -> dict:
    return {
        "id":               generate_id("txn"),
        "src_account":      _col(raw, "src_account","source","from_account","sender_account","src_id","from"),
        "dst_account":      _col(raw, "dst_account","destination","to_account","receiver_account","dst_id","to"),
        "amount":           _normalise_amount(_col(raw, "amount","txn_amount","transaction_amount","debit","value")),
        "currency":         _col(raw, "currency","ccy") or "INR",
        "method":           _col(raw, "method","mode","payment_mode","channel","type","txn_type"),
        "narration":        _col(raw, "narration","description","remarks","note","memo","desc"),
        "timestamp":        _coerce_timestamp(_col(raw, "timestamp","date","txn_date","datetime","time","created_at")),
        "risk_score":       None,
        "flagged":          False,
        **src_meta,
    }


def _norm_call(raw: dict, src_meta: dict) -> dict:
    dur_raw = _col(raw, "duration","duration_sec","dur","call_duration","seconds")
    try:
        duration = int(str(dur_raw).replace("s","").replace("sec","").strip()) if dur_raw else None
    except ValueError:
        duration = None
    return {
        "id":           generate_id("call"),
        "caller_id":    _col(raw, "caller","caller_id","from","calling_number","a_party","msisdn_a"),
        "receiver_id":  _col(raw, "receiver","receiver_id","to","called_number","b_party","msisdn_b"),
        "duration_sec": duration,
        "call_type":    _col(raw, "call_type","type","direction") or "unknown",
        "cell_tower":   _col(raw, "cell_tower","tower","cell_id","bts","site"),
        "timestamp":    _coerce_timestamp(_col(raw, "timestamp","date","call_date","datetime","start_time")),
        **src_meta,
    }


def _norm_sim(raw: dict, src_meta: dict) -> dict:
    swap_raw = _col(raw, "swap_count","swaps","sim_swaps","number_of_swaps")
    try:
        swap_count = int(swap_raw) if swap_raw is not None else 0
    except ValueError:
        swap_count = 0
    return {
        "id":             generate_id("sim"),
        "iccid":          _col(raw, "iccid","sim_id","sim_serial"),
        "imsi":           _col(raw, "imsi"),
        "operator":       _col(raw, "operator","telecom","service_provider","network"),
        "phone_number":   _col(raw, "phone","phone_number","msisdn","mobile"),
        "registered_to":  _col(raw, "registered_to","subscriber","owner","holder"),
        "kyc_verified":   str(_col(raw, "kyc","kyc_verified","kyc_status","verified") or "").lower() in ("true","yes","1","verified"),
        "swap_count":     swap_count,
        "issue_date":     _coerce_timestamp(_col(raw, "issue_date","activation_date","created_at","date")),
        "last_swap_date": _coerce_timestamp(_col(raw, "last_swap_date","swap_date","last_swap")),
        **src_meta,
    }


def _norm_device(raw: dict, src_meta: dict) -> dict:
    return {
        "id":            generate_id("dev"),
        "imei":          _col(raw, "imei","device_id","imei_number"),
        "brand":         _col(raw, "brand","make","manufacturer"),
        "model":         _col(raw, "model","device_model"),
        "os":            _col(raw, "os","operating_system","platform"),
        "registered_to": _col(raw, "registered_to","owner","user","holder"),
        "first_seen":    _coerce_timestamp(_col(raw, "first_seen","first_used","registered_date")),
        "last_seen":     _coerce_timestamp(_col(raw, "last_seen","last_used","last_active")),
        **src_meta,
    }


def _norm_bank_account(raw: dict, src_meta: dict) -> dict:
    return {
        "id":             generate_id("acc"),
        "account_number": _col(raw, "account_number","acc_number","account_no","acno","account"),
        "bank":           _col(raw, "bank","bank_name","bank_code","ifsc_bank"),
        "ifsc":           _col(raw, "ifsc","ifsc_code"),
        "account_type":   _col(raw, "account_type","type","acct_type") or "savings",
        "holder_name":    _col(raw, "holder_name","account_holder","name","customer_name"),
        "holder_id":      _col(raw, "holder_id","person_id","customer_id"),
        "balance":        _normalise_amount(_col(raw, "balance","current_balance","avail_bal")),
        "opened_date":    _coerce_timestamp(_col(raw, "opened_date","opening_date","account_open_date")),
        "is_frozen":      str(_col(raw, "is_frozen","frozen","blocked","frozen_flag") or "").lower() in ("true","yes","1"),
        "kyc_status":     _col(raw, "kyc_status","kyc","kyc_verified") or "unknown",
        **src_meta,
    }


def _norm_upi(raw: dict, src_meta: dict) -> dict:
    return {
        "id":              generate_id("upi"),
        "vpa":             _col(raw, "vpa","upi_id","upi","virtual_payment_address"),
        "registered_to":   _col(raw, "registered_to","holder","person_id","customer_id"),
        "linked_account":  _col(raw, "linked_account","account_id","account_number"),
        "is_active":       str(_col(raw, "is_active","active","status") or "true").lower() in ("true","active","yes","1"),
        "txn_count":       int(_col(raw, "txn_count","transaction_count","total_txns") or 0),
        **src_meta,
    }


def _norm_complaint(raw: dict, src_meta: dict) -> dict:
    return {
        "id":              generate_id("cmp"),
        "complaint_number":_col(raw, "complaint_number","complaint_id","fir","fir_number","complaint_no"),
        "fraud_type":      _col(raw, "fraud_type","type","category","crime_type"),
        "narrative":       _col(raw, "narrative","description","complaint_text","details","text","body"),
        "loss_amount":     _normalise_amount(_col(raw, "loss_amount","amount","loss","claim_amount")),
        "currency":        _col(raw, "currency") or "INR",
        "incident_date":   _coerce_timestamp(_col(raw, "incident_date","date_of_incident","crime_date","date")),
        "reported_date":   _coerce_timestamp(_col(raw, "reported_date","report_date","filing_date")),
        "police_station":  _col(raw, "police_station","ps","station","ps_name"),
        **src_meta,
    }


def _norm_phone(raw: dict, src_meta: dict) -> dict:
    return {
        "id":             generate_id("ph"),
        "number":         _col(raw, "number","phone","phone_number","mobile","msisdn","contact"),
        "operator":       _col(raw, "operator","telecom","network","service_provider"),
        "circle":         _col(raw, "circle","state","region","telecom_circle"),
        "registered_to":  _col(raw, "registered_to","subscriber","owner","name"),
        "is_active":      str(_col(raw, "is_active","active","status") or "true").lower() in ("true","active","yes","1"),
        **src_meta,
    }


def _norm_location(raw: dict, src_meta: dict) -> dict:
    lat_raw = _col(raw, "lat","latitude","gps_lat")
    lon_raw = _col(raw, "lon","lng","longitude","gps_lon","gps_lng")
    try:
        lat = float(lat_raw) if lat_raw else None
        lon = float(lon_raw) if lon_raw else None
    except ValueError:
        lat = lon = None
    return {
        "id":      generate_id("loc"),
        "city":    _col(raw, "city","town","district"),
        "state":   _col(raw, "state","province","region"),
        "pincode": _col(raw, "pincode","pin","postal_code","zip"),
        "address": _col(raw, "address","addr","location","place"),
        "lat":     lat,
        "lon":     lon,
        **src_meta,
    }


# Dispatch table
_NORMALISERS = {
    "transactions":  _norm_transaction,
    "calls":         _norm_call,
    "sims":          _norm_sim,
    "devices":       _norm_device,
    "bank_accounts": _norm_bank_account,
    "upi_ids":       _norm_upi,
    "complaints":    _norm_complaint,
    "phones":        _norm_phone,
    "locations":     _norm_location,
}


def _auto_detect_record_type(rows: list[dict]) -> str:
    """
    Heuristic: look at column names to guess record type.
    Returns best-guess type name or 'unknown'.
    """
    if not rows:
        return "unknown"
    cols = {k.lower().strip() for k in rows[0].keys()}

    if any(c in cols for c in ("imei", "device_id", "device_model")):
        return "devices"
    if any(c in cols for c in ("iccid", "imsi", "sim_serial", "sim_swaps")):
        return "sims"
    if any(c in cols for c in ("vpa", "upi_id", "virtual_payment_address")):
        return "upi_ids"
    if any(c in cols for c in ("caller", "caller_id", "msisdn_a", "a_party", "b_party", "call_duration")):
        return "calls"
    if any(c in cols for c in ("account_number", "acc_number", "ifsc", "account_holder")):
        return "bank_accounts"
    if any(c in cols for c in ("complaint_number","fir","narrative","complaint_text","crime_type")):
        return "complaints"
    if any(c in cols for c in ("lat","latitude","longitude","gps_lat")):
        return "locations"
    if any(c in cols for c in ("msisdn","phone_number","mobile","telecom","circle")):
        return "phones"
    if any(c in cols for c in ("amount","txn_amount","src_account","dst_account","sender_account","debit")):
        return "transactions"
    return "unknown"


def _parse_file_to_rows(filename: str, content: bytes) -> tuple[list[dict], str | None]:
    """
    Parse file content into a list of row dicts.
    Returns (rows, error).
    """
    ext = Path(filename).suffix.lower()

    if ext == ".json":
        try:
            data = json.loads(content)
            if isinstance(data, list):
                return data, None
            if isinstance(data, dict):
                # Unwrap common wrappers: {"records": [...]} / {"data": [...]} / {"items": [...]}
                for key in ("records","data","items","results","rows","transactions","calls",
                            "sims","devices","bank_accounts","upi_ids","complaints","phones","locations"):
                    if isinstance(data.get(key), list):
                        return data[key], None
                return [data], None   # single-object file
            return [], "JSON root must be an array or an object with a records/data/items key"
        except json.JSONDecodeError as e:
            return [], f"Malformed JSON: {e}"

    if ext == ".csv":
        try:
            text   = content.decode("utf-8", errors="replace")
            reader = csv.DictReader(io.StringIO(text))
            return list(reader), None
        except Exception as e:
            return [], f"CSV parse error: {e}"

    if ext == ".txt":
        # Try CSV with various delimiters
        text = content.decode("utf-8", errors="replace")
        for delim in (",", "\t", "|", ";"):
            try:
                reader = csv.DictReader(io.StringIO(text), delimiter=delim)
                rows = list(reader)
                if rows and len(rows[0]) > 1:
                    return rows, None
            except Exception:
                pass
        # Fall back: each line is a "text" complaint
        lines = [l.strip() for l in text.splitlines() if l.strip()]
        return [{"text": line} for line in lines], None

    if ext == ".xlsx":
        try:
            import openpyxl
            wb = openpyxl.load_workbook(io.BytesIO(content), read_only=True, data_only=True)
            ws = wb.active
            rows_iter = iter(ws.rows)
            header = [str(cell.value).strip() if cell.value is not None else f"col_{i}"
                      for i, cell in enumerate(next(rows_iter))]
            result = []
            for row in rows_iter:
                result.append({header[i]: (cell.value if cell.value is not None else "")
                                for i, cell in enumerate(row) if i < len(header)})
            return result, None
        except ImportError:
            return [], "openpyxl is not installed; XLSX support unavailable"
        except Exception as e:
            return [], f"XLSX parse error: {e}"

    return [], f"Unsupported extension: {ext}"


def _store_processed(case_id: str, record_type: str, records: list[dict]) -> Path:
    dest_dir = PROCESSED_DIR / case_id
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / f"{record_type}.json"
    existing = read_json(dest) or []
    existing.extend(records)
    write_json(dest, existing)
    return dest


def _store_evidence(evidence: dict) -> None:
    EVIDENCE_FILE.parent.mkdir(parents=True, exist_ok=True)
    if not EVIDENCE_FILE.exists():
        write_json(EVIDENCE_FILE, [])
    existing = read_json(EVIDENCE_FILE) or []
    existing.append(evidence)
    write_json(EVIDENCE_FILE, existing)


# ── Public entry point ────────────────────────────────────────────────────────

def ingest_file(
    filename:    str,
    content:     bytes,
    case_id:     str,
    uploaded_by: str,
    record_type_hint: str | None = None,
) -> dict:
    """
    Main ingestion pipeline.
    1. Validate
    2. Store raw
    3. Parse to rows
    4. Detect / confirm record type
    5. Normalise each row
    6. Store processed JSON
    7. Record evidence metadata
    Returns a result summary dict (never raises on parse/norm errors; they go in the summary).
    """
    now = now_iso()
    safe_name   = _safe_filename(filename)
    evidence_id = generate_id("ev")

    # ── 1. Validate ─────────────────────────────────────────────────────────
    errors = validate_upload(filename, len(content), content)
    if errors:
        return {
            "success":   False,
            "errors":    errors,
            "filename":  safe_name,
            "case_id":   case_id,
        }

    # ── 2. Store raw ─────────────────────────────────────────────────────────
    raw_path = _store_raw(case_id, safe_name, content)

    # ── 3. Parse ─────────────────────────────────────────────────────────────
    rows, parse_err = _parse_file_to_rows(safe_name, content)
    if parse_err:
        return {
            "success":    False,
            "errors":     [parse_err],
            "filename":   safe_name,
            "raw_path":   str(raw_path),
            "case_id":    case_id,
            "evidence_id": evidence_id,
        }

    # ── 4. Detect record type ─────────────────────────────────────────────
    if record_type_hint and record_type_hint in VALID_RECORD_TYPES:
        record_type = record_type_hint
    else:
        record_type = _auto_detect_record_type(rows)

    # ── 5. Normalise ──────────────────────────────────────────────────────
    normaliser = _NORMALISERS.get(record_type)
    norm_records:   list[dict] = []
    skipped:        list[int]  = []
    norm_errors:    list[str]  = []

    src_meta = {
        "source_file":      safe_name,
        "source_record_id": None,   # set per row below
        "case_id":          case_id,
        "evidence_id":      evidence_id,
        "ingested_at":      now,
    }

    if normaliser is None:
        # unknown type — store rows as-is with provenance
        for i, row in enumerate(rows):
            rec = dict(row)
            rec["id"]               = generate_id("raw")
            rec["source_file"]      = safe_name
            rec["source_record_id"] = str(i)
            rec["case_id"]          = case_id
            rec["evidence_id"]      = evidence_id
            rec["ingested_at"]      = now
            norm_records.append(rec)
        record_type = "unknown"
    else:
        for i, row in enumerate(rows):
            try:
                meta = {**src_meta, "source_record_id": str(i)}
                rec  = normaliser(row, meta)
                norm_records.append(rec)
            except Exception as e:
                skipped.append(i)
                norm_errors.append(f"Row {i}: {e}")

    # ── 6. Store processed ────────────────────────────────────────────────
    processed_path = _store_processed(case_id, record_type, norm_records)

    # ── 7. Evidence metadata ──────────────────────────────────────────────
    evidence = {
        "id":              evidence_id,
        "case_id":         case_id,
        "type":            "uploaded_file",
        "record_type":     record_type,
        "filename":        safe_name,
        "raw_path":        str(raw_path),
        "processed_path":  str(processed_path),
        "total_rows":      len(rows),
        "normalised":      len(norm_records),
        "skipped":         len(skipped),
        "uploaded_by":     uploaded_by,
        "uploaded_at":     now,
    }
    _store_evidence(evidence)

    return {
        "success":           True,
        "evidence_id":       evidence_id,
        "filename":          safe_name,
        "case_id":           case_id,
        "record_type":       record_type,
        "total_rows":        len(rows),
        "normalised":        len(norm_records),
        "skipped":           len(skipped),
        "norm_errors":       norm_errors[:20],  # first 20 row errors
        "raw_path":          str(raw_path),
        "processed_path":    str(processed_path),
        "uploaded_at":       now,
    }
