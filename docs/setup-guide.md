# Setup Guide — Cyber Fraud Network Analyzer

## Prerequisites

- Python 3.10+
- Node.js 18+ and npm
- Git

## 1. Clone the Repository

```bash
git clone 
cd cyber-fraud-network-analyzer
```

## 2. Backend Setup (Flask API)

```bash
cd backend

# Create and activate virtual environment
python -m venv venv

# Windows
venv\Scripts\activate
# macOS/Linux
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env if you want to connect IBM watsonx.ai (optional)
```

## 3. Start the Backend

```bash
# From the backend/ directory (with venv active)
python app.py
```

Backend runs at: `http://localhost:5000`

Verify: `curl http://localhost:5000/api/health` → `{"status": "ok"}`

## 4. Frontend Setup (React)

```bash
# In a new terminal, from project root
cd frontend
npm install
npm start
```

Frontend runs at: `http://localhost:3000`

## 5. Using the Application

1. Open `http://localhost:3000`
2. Click any mock case in the left sidebar (CASE-001 Phishing, CASE-002 SIM Swap, CASE-003 Mule Network)
3. IBM Bob analyzes the intelligence and renders:
   - **Overview** — fraud pattern, stats, legal sections, recommended actions
   - **Network Graph** — interactive vis-network entity relationship map
   - **Hierarchy** — Kingpin → Coordinator → Mule → Victim tree
   - **FIR Draft** — copy/download the FIR-ready case brief
4. Or paste your own raw intelligence text in the sidebar and click **Analyze with Bob**

## 6. Running the CLI (without frontend)

```bash
cd src

# Single case
python run.py --case mock_data/case_001_phishing.json

# All mock cases
python run.py --all

# Raw text
python run.py --raw "Accused Rajan Kumar called victim Priya at 9876543210..."
```

## 7. Running on CSV Dataset (50 fraud patterns)

```bash
cd src
python run_csv_dataset.py --dataset /path/to/extracted/output --all
python run_csv_dataset.py --dataset /path/to/extracted/output --master-only
python run_csv_dataset.py --dataset /path/to/extracted/output --pattern pat_0
```

## Environment Variables

| Variable | Description | Required |
|---|---|---|
| `PORT` | Flask port (default: 5000) | No |
| `WATSONX_API_KEY` | IBM watsonx.ai API key | No (optional enrichment) |
| `WATSONX_PROJECT_ID` | watsonx.ai project ID | No |
| `WATSONX_URL` | watsonx.ai endpoint URL | No |

## Troubleshooting

| Issue | Solution |
|---|---|
| `ModuleNotFoundError: flask` | Run `pip install -r requirements.txt` inside `backend/` with venv active |
| `ModuleNotFoundError: src.parser` | Ensure you run `python app.py` from the `backend/` directory |
| CORS error in browser | Confirm Flask is running on port 5000 and `proxy` in `frontend/package.json` is set |
| `npm install` fails | Ensure Node.js 18+ is installed: `node --version` |
| Graph not rendering | vis-network requires a DOM container — ensure browser JS is enabled |
