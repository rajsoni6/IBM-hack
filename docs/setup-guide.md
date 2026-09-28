# Setup Guide — Cyber Fraud Network Analyzer

> **Team:** Maa Group | **Captain:** Kanjara Raj Bharatbhai | rajkanjara.1234@gmail.com

---

## Prerequisites

Make sure the following are installed before you begin:

| Tool | Version | Check |
|---|---|---|
| Python | 3.10+ | `python --version` |
| Node.js | 18+ | `node --version` |
| npm | 9+ | `npm --version` |
| Git | any | `git --version` |

---

## 1. Clone the Repository

```bash
git clone https://github.com/rajsoni6/IBM-hack.git
cd IBM-hack
```

---

## 2. Environment Configuration

Copy the example env file and configure it:

```bash
cp .env.example .env
```

Open `.env` and set the values:

```env
# Required for Phase 1 (no API key needed)
AI_PROVIDER=mock
PORT=5000
FLASK_ENV=development

# Optional — only needed for IBM Bob / watsonx.ai (Phase 8)
WATSONX_API_KEY=your_api_key_here
WATSONX_PROJECT_ID=your_project_id_here
WATSONX_URL=https://us-south.ml.cloud.ibm.com
WATSONX_MODEL_ID=ibm/granite-13b-instruct-v2
```

> **Note:** Set `AI_PROVIDER=mock` to run without any IBM API key. The full pipeline works in mock mode.

---

## 3. Backend Setup (Flask API)

```bash
# Navigate to backend
cd src/cyber-fraud-network-analyzer/backend

# Create virtual environment
python -m venv venv

# Activate — Windows
venv\Scripts\activate

# Activate — macOS / Linux
source venv/bin/activate

# Install all dependencies
pip install -r requirements.txt
```

### Start the backend server

```bash
python app.py
```

Backend runs at: **`http://localhost:5000`**

### Verify it's working

```bash
curl http://localhost:5000/api/health
```

Expected response:
```json
{
  "status": "ok",
  "service": "Cyber Fraud Network Analyzer",
  "version": "1.0.0-phase1",
  "ai_provider": "mock"
}
```

---

## 4. Frontend Setup (React + Vite)

Open a **new terminal** (keep backend running):

```bash
# Navigate to frontend
cd src/cyber-fraud-network-analyzer/frontend

# Install dependencies
npm install

# Start development server
npm run dev
```

Frontend runs at: **`http://localhost:5173`**

Open your browser and go to `http://localhost:5173`

---

## 5. Using the Application

### Option A — Load a Mock Case

1. Open `http://localhost:5173`
2. Click any case in the left sidebar:
   - **CASE-001** — Mass Phishing & OTP Fraud
   - **CASE-002** — SIM Swap Attack (Jamtara-style)
   - **CASE-003** — Organised Mule Network
3. IBM Bob analyzes the intelligence and shows:
   - **📊 Overview** — fraud pattern, financial impact, entity counts
   - **🕸️ Network Graph** — interactive Cytoscape.js entity map
   - **🏛️ Hierarchy** — Kingpin → Coordinator → Mule → Victim tree
   - **📄 FIR Draft** — copy or download the structured case brief

### Option B — Paste Raw Intelligence

1. Paste any unstructured text in the sidebar input box
2. Click **Analyze with Bob**
3. Example input:
```
Accused Rajan Kumar called victim Priya Sharma at 9876543210 on 14-Mar-2024.
Transaction TXN8821 of INR 1,45,000 debited from account AC-3391 to AC-9902.
Device IMEI 354823091234567 registered to SIM 9876543210.
AC-9902 held by Anil Yadav (suspected mule). Prior FIR/456/2022.
```

---

## 6. CLI Mode (No Frontend Required)

```bash
cd src

# Analyze a single mock case
python run.py --case mock_data/case_001_phishing.json
python run.py --case mock_data/case_002_sim_swap.json
python run.py --case mock_data/case_003_mule_network.json

# Run all 3 mock cases at once
python run.py --all

# Analyze raw text directly
python run.py --raw "Accused Rajan Kumar called victim Priya at 9876543210..."
```

Output files are saved to `src/output/`:
- `CASE-001_brief.txt` — FIR draft
- `CASE-001_graph.json` — entity graph JSON

---

## 7. CSV Dataset Mode (50 Fraud Patterns)

The project includes a real CSV dataset with 10,000+ accounts and 50 fraud patterns:

```bash
cd src

# Run all 50 fraud patterns
python run_csv_dataset.py --dataset data --all

# Run only the master aggregated case
python run_csv_dataset.py --dataset data --master-only

# Run a specific pattern
python run_csv_dataset.py --dataset data --pattern pat_0

# Run top 10 patterns only
python run_csv_dataset.py --dataset data --top 10
```

Dataset location:
```
src/data/
├── accounts/
│   ├── accounts_0_0.csv      # 5,000 accounts
│   └── accounts_1_0.csv      # 5,000 accounts
├── fraud/
│   ├── fraud_cases.csv       # 50 fraud cycle patterns
│   └── transactions_fraud.csv # flagged transactions with embeddings
└── transactions/
    ├── transactions_0_0.csv
    └── transactions_1_0.csv
```

---

## 8. Environment Variables Reference

| Variable | Description | Default | Required |
|---|---|---|---|
| `AI_PROVIDER` | AI backend: `mock` or `watsonx` | `mock` | No |
| `PORT` | Flask server port | `5000` | No |
| `FLASK_ENV` | `development` or `production` | `development` | No |
| `SECRET_KEY` | Flask secret key | `dev-secret` | No |
| `CORS_ORIGINS` | Allowed frontend origins | `http://localhost:5173` | No |
| `WATSONX_API_KEY` | IBM watsonx.ai API key | — | Phase 8 only |
| `WATSONX_PROJECT_ID` | watsonx.ai project ID | — | Phase 8 only |
| `WATSONX_URL` | watsonx.ai endpoint | `https://us-south.ml.cloud.ibm.com` | Phase 8 only |
| `WATSONX_MODEL_ID` | Model ID | `ibm/granite-13b-instruct-v2` | Phase 8 only |

---

## 9. Project Structure

```
IBM-hack/
├── src/
│   ├── cyber-fraud-network-analyzer/
│   │   ├── backend/
│   │   │   ├── app.py              # Flask app factory
│   │   │   ├── requirements.txt
│   │   │   ├── config/             # Settings loaded from .env
│   │   │   ├── routes/             # Flask Blueprints
│   │   │   ├── services/           # Business logic (Phase 2+)
│   │   │   ├── ai/                 # IBM Bob provider abstraction
│   │   │   ├── ml/                 # Fraud classifier (Phase 4+)
│   │   │   ├── graph/              # NetworkX builder (Phase 5+)
│   │   │   ├── storage/            # JSON/CSV file utilities
│   │   │   └── utils/              # Logger, helpers
│   │   └── frontend/
│   │       ├── src/
│   │       │   ├── App.tsx
│   │       │   ├── pages/
│   │       │   └── components/
│   │       └── package.json
│   ├── data/                       # Training CSV datasets
│   ├── mock_data/                  # 3 mock case JSON files
│   ├── output/                     # Generated FIR briefs + graphs
│   ├── run.py                      # CLI entry point
│   └── run_csv_dataset.py          # CSV dataset runner
├── docs/
├── demo/
├── .env.example
├── submission.yaml
└── README.md
```

---

## 10. Troubleshooting

| Issue | Cause | Fix |
|---|---|---|
| `ModuleNotFoundError: flask` | venv not active or deps not installed | Run `pip install -r requirements.txt` with venv active |
| `ModuleNotFoundError: src.parser` | Wrong working directory | Run `python app.py` from inside `backend/` folder |
| `CORS error` in browser | Backend not running or wrong port | Confirm Flask is on port 5000 |
| `npm install` fails | Old Node.js version | Upgrade to Node.js 18+: `node --version` |
| `git push` rejected | Branch name mismatch | Run `git branch -M main` then push again |
| `AI_PROVIDER` error | Wrong value in `.env` | Set `AI_PROVIDER=mock` for Phase 1 |
| Port 5000 already in use | Another process using port | Change `PORT=5001` in `.env` |
| Graph not rendering | JavaScript disabled | Enable JS in browser settings |

---

## 11. IBM Bob AI Prompts (Phase 8 Reference)

These are the prompts used when `AI_PROVIDER=watsonx`:

### Entity Extraction Prompt
```
You are a cyber fraud investigator. Extract all named entities from the following intelligence text.
Return a JSON object with keys: persons, accounts, phones, devices, transactions, ip_addresses, urls, crypto_wallets.
Each entity should have: value, role (KINGPIN/COORDINATOR/MULE/VICTIM/UNKNOWN), confidence.

Intelligence text:
{text}
```

### Relationship Extraction Prompt
```
Given these entities from a cyber fraud case, identify all relationships between them.
Return a JSON array of objects with: from_entity, relationship_type, to_entity, confidence.
Relationship types: CONTROLS_ACCOUNT, USES_PHONE, TRANSFERRED_TO, LINKED_TO, VICTIM_OF.

Entities: {entities}
Intelligence text: {text}
```

### Investigation Summary Prompt
```
You are an experienced cyber crime investigator. Based on the following case data,
write a concise 3-paragraph investigation summary suitable for a senior officer.
Include: fraud pattern identified, key accused persons, estimated financial loss, and top 3 recommended actions.

Case data: {case_data}
```

### Fraud Pattern Classification Prompt
```
Classify the following cyber fraud case into one of these patterns:
SIM_SWAP, PHISHING, MULE_NETWORK, VISHING, INVESTMENT_SCAM, INSIDER_THREAT, HYBRID.
Return JSON: { "pattern": "...", "confidence": 0.0-1.0, "reasoning": "..." }

Case summary: {summary}
```

---

*Built for IBM Hackathon by Team Maa Group. All case data is fictional and for demonstration only.*
