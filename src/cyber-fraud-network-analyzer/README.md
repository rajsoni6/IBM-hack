# Cyber Fraud Network Analyzer

A full-stack application for detecting and investigating cyber fraud networks using AI-powered entity extraction, graph analysis, and ML-based risk scoring.

**No database required** — all data is stored in local JSON/CSV files.

---

## Table of Contents

1. [Project Overview](#1-project-overview)
2. [Architecture](#2-architecture)
3. [Prerequisites](#3-prerequisites)
4. [Installation](#4-installation)
5. [Running the Backend](#5-running-the-backend)
6. [Running the Frontend](#6-running-the-frontend)
7. [How to Input Data](#7-how-to-input-data)
8. [Running Tests](#8-running-tests)
9. [Data Storage Structure](#9-data-storage-structure)
10. [API Documentation](#10-api-documentation)
11. [AI Configuration](#11-ai-configuration)
12. [ML Model](#12-ml-model)
13. [Security](#13-security)
14. [Demo Workflow](#14-demo-workflow)
15. [Limitations](#15-limitations)

---

## 1. Project Overview

| Layer     | Technologies |
|-----------|-------------|
| Frontend  | React 18 · TypeScript · Vite · Tailwind CSS · Cytoscape.js · Recharts |
| Backend   | Python 3.11+ · Flask · Flask-CORS · Flask-Limiter · PyJWT · bcrypt |
| AI        | Mock provider (regex-based) · watsonx.ai (optional) |
| ML        | scikit-learn · XGBoost · NetworkX · pandas · numpy |
| Storage   | JSON files + CSV files — **no database** |

---

## 2. Architecture

```
cyber-fraud-network-analyzer/
├── backend/                  ← Flask REST API (port 5000)
│   ├── app.py                ← Application factory (CORS, rate limiting, blueprints)
│   ├── config/settings.py    ← All config loaded from .env
│   ├── routes/               ← Flask Blueprints
│   │   ├── health.py         ← GET  /api/health
│   │   ├── auth.py           ← POST /api/auth/register|login, GET /api/auth/me
│   │   ├── cases.py          ← CRUD /api/cases/
│   │   ├── intelligence.py   ← POST /api/intelligence/upload
│   │   ├── ai_extraction.py  ← POST /api/ai/extract-entities|extract-relationships
│   │   ├── graph.py          ← GET  /api/graph/<case_id>
│   │   ├── patterns.py       ← GET/POST /api/patterns/<case_id>
│   │   ├── predict.py        ← POST /api/predict
│   │   ├── timeline.py       ← GET  /api/timeline/<case_id>
│   │   ├── evidence.py       ← GET  /api/evidence/<case_id>
│   │   └── summary.py        ← POST /api/summary/generate/<case_id>
│   ├── services/             ← Business logic
│   ├── ai/                   ← AI provider abstraction (mock / watsonx)
│   ├── ml/                   ← ML feature engineering + predictor
│   ├── graph/                ← NetworkX graph builder + pattern detector
│   ├── storage/file_store.py ← JSON/CSV file utilities
│   └── utils/
│       ├── auth_middleware.py ← JWT helpers + decorators
│       └── audit.py           ← Audit log writer → data/audit/audit_logs.json
│
├── frontend/                 ← React + TypeScript + Vite (port 5173)
│   └── src/
│       ├── pages/            ← Dashboard, Cases, Graph, ML, Timeline, Evidence, AI Brief …
│       ├── components/       ← Layout, StatCard, WorkflowStepper …
│       └── api/              ← Axios client wrappers
│
├── data/                     ← All persistent data (JSON/CSV, no DB)
│   ├── audit/audit_logs.json ← Security audit trail
│   ├── cases/cases.json
│   ├── entities/entities.json
│   ├── relationships/relationships.json
│   ├── evidence/evidence.json
│   ├── predictions/predictions.json
│   ├── reports/<case_id>_summary.json
│   ├── raw/<case_id>/        ← Uploaded raw files
│   ├── processed/<case_id>/  ← Normalised JSON per record type
│   └── sample/               ← Synthetic demo dataset
│
├── models/                   ← Trained ML artifacts (.pkl)
├── scripts/                  ← train_model.py, seed_demo.py
└── tests/                    ← pytest test suite
```

---

## 3. Prerequisites

| Tool | Minimum version | Check |
|------|----------------|-------|
| Python | 3.11 | `python --version` |
| pip | 23+ | `pip --version` |
| Node.js | 18 LTS | `node --version` |
| npm | 9+ | `npm --version` |

---

## 4. Installation

### Clone and configure

```bash
# 1 — navigate to the project
cd src/cyber-fraud-network-analyzer

# 2 — copy environment file
copy .env.example .env          # Windows
# cp .env.example .env          # macOS / Linux
```

Edit `.env` if needed. The defaults work for local development.

### Backend dependencies

```bash
cd backend

# Create virtual environment
python -m venv .venv

# Activate (Windows PowerShell)
.venv\Scripts\Activate.ps1

# Activate (Windows CMD)
.venv\Scripts\activate.bat

# Activate (macOS / Linux)
source .venv/bin/activate

# Install all packages
pip install -r requirements.txt
```

### Frontend dependencies

```bash
cd frontend
npm install
```

---

## 5. Running the Backend

```bash
cd backend

# Make sure virtual env is active
.venv\Scripts\Activate.ps1     # Windows
source .venv/bin/activate       # macOS/Linux

# Start the Flask server
python app.py
```

**Output:**
```
 * Running on http://0.0.0.0:5000
 * Debug mode: on
```

**Verify it works:**
```bash
curl http://localhost:5000/api/health
```

Expected response:
```json
{
  "status": "ok",
  "service": "Cyber Fraud Network Analyzer",
  "version": "1.0.0",
  "phase": 10,
  "ai_provider": "mock"
}
```

---

## 6. Running the Frontend

Open a **second terminal**:

```bash
cd frontend
npm run dev
```

**Output:**
```
  VITE v5.x  ready in 400ms
  ➜  Local:   http://localhost:5173/
```

Open **http://localhost:5173** in your browser.

> The Vite dev server proxies `/api/*` requests to `http://localhost:5000` automatically — no CORS issues.

---

## 7. How to Input Data

### Step 1 — Register a user (API or UI)

**Via API:**
```bash
curl -X POST http://localhost:5000/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "username": "investigator1",
    "email": "io1@agency.gov",
    "password": "SecurePass1",
    "role": "INVESTIGATOR",
    "full_name": "Investigator One"
  }'
```

**Roles available:** `ADMIN` · `INVESTIGATOR` · `ANALYST` · `VIEWER`

Save the `token` from the response — all subsequent calls need it.

---

### Step 2 — Login

```bash
curl -X POST http://localhost:5000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "investigator1", "password": "SecurePass1"}'
```

---

### Step 3 — Create a Case

```bash
TOKEN="<paste your token here>"

curl -X POST http://localhost:5000/api/cases/ \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "title": "UPI Fraud — Mule Network",
    "description": "Victim lost Rs.49000 via UPI. Multiple mule accounts identified.",
    "fraud_pattern": "mule_network",
    "severity": "high",
    "status": "open",
    "jurisdiction": "Mumbai",
    "assigned_to": "IO-Singh",
    "total_loss_inr": 49000
  }'
```

Save the `case.id` from the response (e.g. `case_abc123def456`).

**Valid fraud patterns:** `sim_swap` · `mule_network` · `transaction_layering` · `shared_device` · `shared_sim` · `communication_hub` · `rapid_multi_hop` · `legitimate` · `unknown`

**Valid severities:** `critical` · `high` · `medium` · `low`

---

### Step 4 — Upload Intelligence Files

Upload a **CSV transaction file:**

```bash
CASE_ID="case_abc123def456"

curl -X POST http://localhost:5000/api/intelligence/upload \
  -H "Authorization: Bearer $TOKEN" \
  -F "case_id=$CASE_ID" \
  -F "record_type=transactions" \
  -F "file=@transactions.csv"
```

**Supported file formats:** `.csv` · `.json` · `.txt` · `.xlsx`

**Supported record types:**

| record_type | Required columns |
|-------------|-----------------|
| `transactions` | `src_account`, `dst_account`, `amount`, `timestamp` |
| `calls` | `caller`, `receiver`, `duration`, `timestamp` |
| `sims` | `iccid`, `operator`, `phone_number` |
| `devices` | `imei`, `brand`, `model` |
| `bank_accounts` | `account_number`, `bank`, `ifsc` |
| `upi_ids` | `vpa` |
| `complaints` | `complaint_number`, `fraud_type`, `narrative` |
| `phones` | `number`, `operator` |
| `locations` | `city`, `state`, `lat`, `lon` |

**Example `transactions.csv`:**
```csv
src_account,dst_account,amount,method,narration,timestamp
acc_001,acc_002,49000,IMPS,Fund transfer,2024-01-10T09:00:00Z
acc_002,acc_003,48000,NEFT,Payment,2024-01-10T10:00:00Z
acc_003,acc_004,47000,UPI,UPI transfer,2024-01-10T11:00:00Z
```

**Example `complaint.json`:**
```json
[{
  "complaint_number": "CMP/2024/001",
  "fraud_type": "UPI fraud",
  "narrative": "Victim Mr. Ramesh Kumar received a call from 9876543210. Rs.49000 transferred to ACC001.",
  "loss_amount": "49000",
  "incident_date": "2024-01-10"
}]
```

---

### Step 5 — AI Entity Extraction

```bash
curl -X POST http://localhost:5000/api/ai/extract-entities \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "text": "Victim Mr. Ramesh Kumar reported a call from 9876543210. Rs.49000 was transferred to account HDFC0001234 by suspect Sh. Rahul Sharma. Device IMEI 354321098765432.",
    "case_id": "case_abc123def456"
  }'
```

---

### Step 6 — Build Network Graph

```bash
curl -H "Authorization: Bearer $TOKEN" \
  http://localhost:5000/api/graph/case_abc123def456
```

---

### Step 7 — Detect Fraud Patterns

```bash
curl -X POST http://localhost:5000/api/patterns/analyze/case_abc123def456 \
  -H "Authorization: Bearer $TOKEN"
```

---

### Step 8 — ML Prediction

```bash
curl -X POST http://localhost:5000/api/predict \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "features": {
      "tx_count": 10,
      "tx_out_count": 7,
      "tx_in_count": 3,
      "total_volume": 345000,
      "out_volume": 249000,
      "in_volume": 96000,
      "avg_tx_amount": 34500,
      "max_tx_amount": 49000,
      "min_tx_amount": 9999,
      "std_tx_amount": 15000,
      "fwd_ratio": 2.6,
      "unique_peers": 4,
      "unique_out_peers": 4,
      "unique_in_peers": 3,
      "round_amount_ratio_out": 0.3,
      "near_threshold_ratio": 0.7,
      "suspicious_desc_ratio": 0.4,
      "self_loop_count": 0,
      "out_max_amount": 49000
    },
    "case_id": "case_abc123def456",
    "entity_id": "acc_001"
  }'
```

> **Note:** If the model is not trained yet, the API returns `503`. Run `python scripts/train_model.py` first.

---

### Step 9 — Generate AI Case Brief

```bash
curl -X POST http://localhost:5000/api/summary/generate/case_abc123def456 \
  -H "Authorization: Bearer $TOKEN"
```

---

## 8. Running Tests

All tests live in `backend/tests/`. Run from the `backend/` directory.

```bash
cd backend

# Activate virtual environment first
.venv\Scripts\Activate.ps1     # Windows
source .venv/bin/activate       # macOS/Linux

# Run all tests
python -m pytest tests/ -v

# Run specific test file
python -m pytest tests/test_auth.py -v
python -m pytest tests/test_cases.py -v
python -m pytest tests/test_intelligence.py -v
python -m pytest tests/test_graph.py -v
python -m pytest tests/test_patterns.py -v
python -m pytest tests/test_ml.py -v
python -m pytest tests/test_phase8.py -v
python -m pytest tests/test_security.py -v
python -m pytest tests/test_end_to_end.py -v

# Run only fast tests (skip ML model tests that need training)
python -m pytest tests/ -v -k "not predictor_loads"

# Run with coverage
python -m pytest tests/ --tb=short -q
```

### Test files and what they cover

| Test File | Coverage |
|-----------|----------|
| `test_auth.py` | Register, Login, /me, RBAC roles, password validation |
| `test_cases.py` | Create, List, Get, Update cases; auth guards; validation |
| `test_intelligence.py` | CSV/JSON/TXT upload; file validation; normalisation; provenance |
| `test_graph.py` | NetworkX graph build; filter; search; path finding; components |
| `test_patterns.py` | All 9 pattern detectors; role analyzer; pattern route |
| `test_ml.py` | Feature engineering; dataset loading; prediction output format |
| `test_phase8.py` | Timeline; Evidence; AI Case Brief / Summary |
| `test_security.py` | Auth on every endpoint; RBAC; password hashing; path traversal; XSS; audit logs |
| `test_end_to_end.py` | Full 12-step pipeline; invalid inputs at each stage; synthetic dataset |
| `test_file_store.py` | JSON/CSV file store utilities |
| `test_health.py` | /api/health endpoint |

### Expected test output (passing)

```
tests/test_auth.py          ............... [PASSED]
tests/test_cases.py         ............... [PASSED]
tests/test_intelligence.py  ............... [PASSED]
tests/test_graph.py         ............... [PASSED]
tests/test_patterns.py      ............... [PASSED]
tests/test_ml.py            ......sssss.... [PASSED]  (s = skipped, model not trained)
tests/test_phase8.py        ............... [PASSED]
tests/test_security.py      ............... [PASSED]
tests/test_end_to_end.py    ............... [PASSED]
```

> ML predictor tests are skipped automatically if `models/fraud_model.pkl` does not exist. Run `python scripts/train_model.py` to train first.

---

## 9. Data Storage Structure

All data is stored as plain JSON or CSV files. **No database.**

```
data/
├── audit/
│   └── audit_logs.json          ← Security audit trail (every login, upload, create)
├── cases/
│   └── cases.json               ← Array of all fraud cases
├── entities/
│   └── entities.json            ← Extracted entities (persons, phones, accounts, …)
├── relationships/
│   └── relationships.json       ← Entity relationships
├── evidence/
│   └── evidence.json            ← Uploaded file metadata + chain of custody
├── predictions/
│   └── predictions.json         ← ML risk score predictions
├── reports/
│   └── <case_id>_summary.json   ← AI-generated case brief per case
├── raw/
│   └── <case_id>/               ← Original uploaded files (immutable)
├── processed/
│   └── <case_id>/
│       ├── transactions.json
│       ├── calls.json
│       ├── sims.json
│       └── …                    ← Normalised records per type
├── users/
│   └── users.json               ← User accounts (passwords bcrypt-hashed)
└── sample/
    ├── transactions.json
    ├── call_records.json
    ├── entities.json
    ├── relationships.json
    └── …                        ← Synthetic demo dataset
```

### Audit log record format

```json
{
  "id": "aud_a1b2c3d4e5f6",
  "timestamp": "2024-01-10T09:00:00Z",
  "user": "investigator1",
  "user_id": "usr_abc123",
  "action": "case.create",
  "case_id": "case_xyz789",
  "entity_id": null,
  "status": "success",
  "metadata": {"title": "UPI Fraud", "fraud_pattern": "mule_network"},
  "ip_address": "127.0.0.1"
}
```

**Tracked actions:** `user.register` · `user.login` · `case.create` · `case.update` · `file.upload`

---

## 10. API Documentation

All endpoints require `Authorization: Bearer <token>` except `/api/health`, `/api/auth/register`, `/api/auth/login`.

### Authentication

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/auth/register` | Register new user |
| `POST` | `/api/auth/login` | Login, receive JWT |
| `GET`  | `/api/auth/me` | Current user + permissions |

### Cases

| Method | Path | Permission | Description |
|--------|------|-----------|-------------|
| `POST` | `/api/cases/` | write | Create fraud case |
| `GET`  | `/api/cases/` | read | List cases (filter by status/severity) |
| `GET`  | `/api/cases/<id>` | read | Get single case |
| `PUT`  | `/api/cases/<id>` | write | Update case fields |

### Intelligence Upload

| Method | Path | Permission | Description |
|--------|------|-----------|-------------|
| `POST` | `/api/intelligence/upload` | upload | Upload CSV/JSON/TXT/XLSX file |

Form fields: `file` (multipart), `case_id` (string), `record_type` (optional hint)

### AI Extraction

| Method | Path | Permission | Description |
|--------|------|-----------|-------------|
| `POST` | `/api/ai/extract-entities` | upload | Extract entities from text |
| `POST` | `/api/ai/extract-relationships` | upload | Extract relationships from text |
| `GET`  | `/api/ai/entities` | read | List all extracted entities |
| `GET`  | `/api/ai/relationships` | read | List all extracted relationships |

### Graph

| Method | Path | Permission | Description |
|--------|------|-----------|-------------|
| `GET`  | `/api/graph/<case_id>` | read | Get graph (nodes + edges) |
| `GET`  | `/api/graph/<case_id>/neighbors/<entity_id>` | read | Neighbours of entity |
| `POST` | `/api/graph/<case_id>/path` | read | Shortest path between entities |
| `GET`  | `/api/graph/<case_id>/node/<entity_id>` | read | Node detail |
| `GET`  | `/api/graph/<case_id>/search?q=...` | read | Text search in graph |
| `GET`  | `/api/graph/<case_id>/components` | read | Connected components |

### Patterns & Roles

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/patterns/analyze/<case_id>` | Run pattern detection |
| `GET`  | `/api/patterns/<case_id>` | Get detected patterns |
| `GET`  | `/api/roles/<case_id>` | Get network role assignments |

### ML Prediction

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/predict` | Predict fraud risk for an entity |

Body: `{ "features": {...19 keys...}, "case_id": "...", "entity_id": "..." }`

### Timeline & Evidence

| Method | Path | Description |
|--------|------|-------------|
| `GET`  | `/api/timeline/<case_id>` | Chronological event timeline |
| `GET`  | `/api/evidence/<case_id>` | List evidence for case |
| `GET`  | `/api/evidence/<case_id>/<evidence_id>` | Single evidence item + chain |

### Summary (AI Case Brief)

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/summary/generate/<case_id>` | Generate and save AI case brief |
| `GET`  | `/api/summary/<case_id>` | Retrieve saved brief |

---

## 11. AI Configuration

Set `AI_PROVIDER` in `.env`:

| Value | Description | API Key Required |
|-------|-------------|-----------------|
| `mock` | Regex-based extraction — works offline, deterministic | No |
| `watsonx` | IBM watsonx.ai Granite model | Yes — `WATSONX_API_KEY` + `WATSONX_PROJECT_ID` |

**To use watsonx.ai:**
```bash
# In .env
AI_PROVIDER=watsonx
WATSONX_API_KEY=your-api-key-here
WATSONX_PROJECT_ID=your-project-id
WATSONX_URL=https://us-south.ml.cloud.ibm.com
WATSONX_MODEL_ID=ibm/granite-13b-instruct-v2
```

---

## 12. ML Model

### Training

```bash
cd backend
python ../scripts/train_model.py
```

This trains an XGBoost fraud classifier on the synthetic transaction dataset and saves:
- `models/fraud_model.pkl` — trained model
- `models/scaler.pkl` — feature scaler
- `models/model_metadata.json` — version, metrics, feature names

### Features (19 total)

| Feature | Description |
|---------|-------------|
| `tx_count` | Total transactions |
| `tx_out_count` | Outgoing transactions |
| `tx_in_count` | Incoming transactions |
| `total_volume` | Total transaction volume |
| `out_volume` | Total outgoing volume |
| `in_volume` | Total incoming volume |
| `avg_tx_amount` | Average transaction amount |
| `max_tx_amount` | Maximum single transaction |
| `min_tx_amount` | Minimum transaction |
| `std_tx_amount` | Standard deviation of amounts |
| `fwd_ratio` | Out/in volume ratio |
| `unique_peers` | Unique counterparties |
| `unique_out_peers` | Unique destinations |
| `unique_in_peers` | Unique sources |
| `round_amount_ratio_out` | Fraction of round-number outgoing amounts |
| `near_threshold_ratio` | Fraction near ₹10,000 (structuring) |
| `suspicious_desc_ratio` | Fraction with suspicious narrations |
| `self_loop_count` | Transactions to own account |
| `out_max_amount` | Max outgoing single transaction |

### Risk Classifications

| Score | Classification |
|-------|---------------|
| ≥ 0.75 | HIGH_RISK |
| ≥ 0.40 | MEDIUM_RISK |
| ≥ 0.15 | LOW_RISK |
| < 0.15 | VERY_LOW_RISK |

---

## 13. Security

| Control | Implementation |
|---------|---------------|
| Authentication | JWT (HS256, 12-hour expiry) via PyJWT |
| Password hashing | bcrypt with salt rounds |
| RBAC | 4 roles: ADMIN, INVESTIGATOR, ANALYST, VIEWER |
| Rate limiting | Flask-Limiter — 200 req/min global, 20 req/min on auth |
| CORS | Restricted to configured origins only |
| Input validation | Pydantic schemas + manual checks on all endpoints |
| File validation | Extension whitelist, size limit (50 MB), content inspection |
| Secure filenames | Unicode normalised, path traversal stripped |
| Audit logging | Every login/upload/case event → `data/audit/audit_logs.json` |
| No hardcoded secrets | All credentials via `.env` variables |
| Safe JSON parsing | Malformed input returns 422, never 500 |
| Path safety | All file paths resolved from `DATA_DIR` — no traversal |

**Password requirements:** ≥ 8 characters · 1 uppercase letter · 1 digit

---

## 14. Demo Workflow

Complete 12-step pipeline using the synthetic dataset:

```
1.  Register investigator account
2.  Login → get JWT token
3.  Create Case (mule_network, high severity)
4.  Upload transactions.csv  →  10 transactions normalised
5.  Upload calls.csv         →  3 call records normalised
6.  Upload complaint.json    →  FIR complaint normalised
7.  POST /api/ai/extract-entities    →  persons, phones, accounts extracted
8.  POST /api/ai/extract-relationships  →  OWNS, CALLS, USES relationships
9.  GET  /api/graph/<case_id>        →  NetworkX graph → Cytoscape.js
10. POST /api/patterns/analyze/<id>  →  rapid_multi_hop, structuring detected
11. POST /api/predict                →  HIGH_RISK score for acc_001
12. GET  /api/timeline/<case_id>     →  chronological event list
13. GET  /api/evidence/<case_id>     →  3 evidence items with chain
14. POST /api/summary/generate/<id>  →  full AI case brief generated
```

---

## 15. Limitations

- **Mock AI provider** produces deterministic regex-based extraction — not LLM-quality. Use `AI_PROVIDER=watsonx` for real analysis.
- **ML model** must be trained before `/api/predict` returns results. Run `scripts/train_model.py` once.
- **File storage** is single-process only — concurrent writes to JSON files are not safe under high load. This is a local investigation tool, not a multi-user production system.
- **No real-time updates** — the frontend polls on page load; there is no WebSocket push.
- All data is stored unencrypted on the local filesystem. Apply OS-level disk encryption for sensitive case data.
