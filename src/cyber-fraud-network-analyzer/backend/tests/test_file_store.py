"""
tests/test_file_store.py
Unit tests for storage/file_store.py utilities.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import pytest
import tempfile
import json
from pathlib import Path
from storage.file_store import (
    read_json, write_json, append_json_record, update_json_record,
    search_json_records, read_csv, write_csv, append_csv_row,
    search_csv_rows, generate_id,
)


@pytest.fixture
def tmp(tmp_path):
    return tmp_path


# ── JSON ──────────────────────────────────────────────────────────────────────

def test_write_and_read_json(tmp):
    path = tmp / "data.json"
    write_json(path, {"hello": "world"})
    result = read_json(path)
    assert result == {"hello": "world"}


def test_read_json_missing_returns_none(tmp):
    assert read_json(tmp / "nonexistent.json") is None


def test_append_json_record_assigns_id(tmp):
    path = tmp / "records.json"
    rec = append_json_record(path, {"name": "Alice"})
    assert "id" in rec
    assert "created_at" in rec


def test_append_json_record_accumulates(tmp):
    path = tmp / "records.json"
    append_json_record(path, {"name": "Alice"})
    append_json_record(path, {"name": "Bob"})
    records = read_json(path)
    assert len(records) == 2


def test_update_json_record(tmp):
    path = tmp / "records.json"
    rec = append_json_record(path, {"name": "Alice"})
    updated = update_json_record(path, rec["id"], {"name": "Alicia"})
    assert updated is not None
    assert updated["name"] == "Alicia"
    assert "updated_at" in updated


def test_update_json_record_not_found(tmp):
    path = tmp / "records.json"
    append_json_record(path, {"name": "Alice"})
    result = update_json_record(path, "nonexistent-id", {"name": "X"})
    assert result is None


def test_search_json_records(tmp):
    path = tmp / "records.json"
    append_json_record(path, {"name": "Alice", "type": "person"})
    append_json_record(path, {"name": "Bob",   "type": "account"})
    results = search_json_records(path, lambda r: r["type"] == "person")
    assert len(results) == 1
    assert results[0]["name"] == "Alice"


# ── CSV ───────────────────────────────────────────────────────────────────────

def test_write_and_read_csv(tmp):
    path = tmp / "data.csv"
    rows = [{"id": "1", "amount": "100"}, {"id": "2", "amount": "200"}]
    write_csv(path, rows)
    result = read_csv(path)
    assert len(result) == 2
    assert result[0]["id"] == "1"


def test_read_csv_missing_returns_empty(tmp):
    assert read_csv(tmp / "nonexistent.csv") == []


def test_append_csv_row_creates_header(tmp):
    path = tmp / "rows.csv"
    append_csv_row(path, {"id": "1", "val": "a"})
    rows = read_csv(path)
    assert len(rows) == 1
    append_csv_row(path, {"id": "2", "val": "b"})
    rows = read_csv(path)
    assert len(rows) == 2


def test_search_csv_rows(tmp):
    path = tmp / "rows.csv"
    write_csv(path, [{"id": "1", "risk": "high"}, {"id": "2", "risk": "low"}])
    results = search_csv_rows(path, lambda r: r["risk"] == "high")
    assert len(results) == 1
    assert results[0]["id"] == "1"


# ── generate_id ───────────────────────────────────────────────────────────────

def test_generate_id_with_prefix():
    uid = generate_id("case")
    assert uid.startswith("case_")
    assert len(uid) > 5


def test_generate_id_unique():
    ids = {generate_id() for _ in range(100)}
    assert len(ids) == 100
