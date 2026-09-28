# 🔍 Cyber Fraud Network Analyzer
### Powered by IBM Bob AI

> A defensive cyber-fraud investigation platform that maps criminal networks, extracts entities, identifies fraud patterns, and generates FIR-ready case briefs — inspired by the real Jamtara SIM-swap ring case.

---

## 👥 Team

| Field | Details |
|---|---|
| **Team Name** | Maa Group |
| **Track** | Cyber FORENSICS |
| **Team Captain** | Kanjara Raj Bharatbhai — rajkanjara.1234@gmail.com |
| **Members** | Yash Tiwari, Dev Chauhan |

---

## 🎯 Problem Statement

> **Challenge #05 — Cyber Fraud Network Analyzer**

In FY2023, the Jamtara SIM-swap ring in Jharkhand was responsible for **95,000+ UPI fraud cases**, defrauding thousands of victims across India. Investigators had to **manually trace connections** between bank accounts, SIM cards, and devices — a process that took weeks and left most cases unsolved.

The core problem:
- No tools existed to **visualize the fraud network** in real time
- Investigators couldn't quickly identify **who the kingpin was** vs mules vs victims
- Generating an **FIR-ready brief** took days of manual documentation
- Patterns like SIM-swap, phishing, and mule networks were hard to distinguish from raw data

---

## 💡 Solution

We built a **Bob-powered investigation platform** that takes unstructured cyber fraud intelligence — transaction records, call logs, device IDs, accused names — and automatically:

1. **Extracts entities and relationships** (persons, accounts, phones, devices, IPs, wallets)
2. **Identifies the fraud pattern** (SIM Swap, Phishing, Mule Network, Vishing, Investment Scam, Insider Threat, Hybrid)
3. **Maps the organizational hierarchy** — Kingpin → Coordinator → Mule → Victim
4. **Generates an FIR-ready case brief** with applicable legal sections and recommended investigative actions
5. **Visualizes the fraud network** as an interactive graph

---

## ✨ Key Features

- **🧠 IBM Bob AI Entity Extraction** — Extracts persons, accounts, phones, devices, IPs, crypto wallets, and FIR references from raw unstructured text
- **🕸️ Interactive Network Graph** — Cytoscape.js powered visual map of the entire fraud network with color-coded roles
- **🏛️ Hierarchy Mapping** — Automatically classifies each actor as Kingpin / Coordinator / Mule / Victim
- **📄 FIR Draft Generator** — One-click generation of a structured FIR with IPC/IT Act sections and recommended actions
- **📊 Fraud Pattern Classifier** — ML + rule-based classifier supporting 7 fraud pattern types including Hybrid detection
- **🗂️ Multi-Case Support** — Load mock cases (Phishing, SIM Swap, Mule Network) or paste raw intelligence directly
- **📁 File-Based Storage** — All data stored locally as JSON/CSV — no database required

---

## 🛠️ Tech Stack

| Category | Technologies |
|---|---|
| **Languages** | Python 3.10+, TypeScript |
| **Frontend** | React 18, Vite, Tailwind CSS, React Router, Axios, Cytoscape.js, Recharts |
| **Backend** | Python, Flask, Flask Blueprints |
| **IBM Technologies** | IBM Bob (watsonx.ai — `ibm/granite-13b-instruct-v2`) |
| **ML / Data** | Pandas, NumPy, scikit-learn, XGBoost, NetworkX |
| **Storage** | JSON files, CSV files, Local filesystem (no database) |
| **Other** | python-dotenv, Pydantic, flask-cors |

---

## 📁 Repository Structure

```
cyber-fraud-network-analyzer/
├── src/
│   ├── cyber-fraud-network-analyzer/
│   │   ├── backend/
│   │   │   ├── app.py                  # Flask app factory
│   │   │   ├── requirements.txt
│   │   │   ├── config/                 # Settings & env config
│   │   │   ├── routes/                 # Flask Blueprints (health, cases, analyze)
│   │   │   ├── services/               # Business logic
│   │   │   ├── ai/                     # IBM Bob / watsonx provider abstraction
│   │   │   ├── ml/                     # Fraud classifier, risk scorer
│   │   │   ├── graph/                  # NetworkX graph builder
│   │   │   ├── storage/                # File-based JSON/CSV utilities
│   │   │   └── utils/                  # Logger, helpers
│   │   └── frontend/
│   │       ├── src/
│   │       │   ├── App.tsx
│   │       │   ├── pages/              # Dashboard, CaseView, GraphView, FIR
│   │       │   ├── components/         # NetworkGraph, HierarchyTree, StatCards
│   │       │   └── api/                # Axios API client
│   │       ├── package.json
│   │       └── vite.config.ts
│   ├── data/
│   │   ├── accounts/                   # accounts_0_0.csv, accounts_1_0.csv
│   │   ├── fraud/                      # fraud_cases.csv, transactions_fraud.csv
│   │   └── transactions/               # transactions_0_0.csv, transactions_1_0.csv
│   └── mock_data/
│       ├── case_001_phishing.json
│       ├── case_002_sim_swap.json
│       └── case_003_mule_network.json
├── data/
│   ├── cases/                          # Saved investigation cases
│   ├── entities/                       # Extracted entity graphs
│   ├── reports/                        # Generated FIR briefs
│   └── predictions/                    # ML fraud scores
├── docs/
│   ├── architecture.md
│   ├── setup-guide.md
│   └── solution-overview.md
├── demo/
│   ├── screenshots/
│   └── demo-video-link.txt
├── .env.example
├── .gitignore
├── docker-compose.yml
└── README.md
```

---

## ⚡ How to Run

### Backend (Flask API)

```bash
# 1. Navigate to backend
cd src/cyber-fraud-network-analyzer/backend

# 2. Create virtual environment
python -m venv venv

# Windows
venv\Scripts\activate

# macOS/Linux
source venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure environment
cp .env.example .env
# Edit .env — set AI_PROVIDER=mock for Phase 1 (no API key needed)

# 5. Run the server
python app.py
```

Backend runs at: `http://localhost:5000`

Verify: `curl http://localhost:5000/api/health`

---

### Frontend (React + Vite)

```bash
# 1. Navigate to frontend
cd src/cyber-fraud-network-analyzer/frontend

# 2. Install dependencies
npm install

# 3. Start dev server
npm run dev
```

Frontend runs at: `http://localhost:5173`

---

### Quick Demo (CLI — no frontend needed)

```bash
cd src

# Analyze SIM Swap case
python run.py --case mock_data/case_002_sim_swap.json

# Analyze all 3 mock cases
python run.py --all

# Paste raw intelligence
python run.py --raw "Accused Rajan Kumar called victim Priya at 9876543210..."
```

---

## 🗺️ Real Case Reference

| Detail | Info |
|---|---|
| **Case** | Jamtara SIM-Swap Ring, Jharkhand |
| **Scale** | 95,000+ UPI fraud cases in FY2023 |
| **Method** | SIM re-issue with forged Aadhaar → OTP interception → account takeover |
| **Problem** | Manual investigation took weeks; most cases unsolved |
| **Our Tool** | Automates entity extraction, network mapping, and FIR generation in seconds |

---

## 🔬 Fraud Patterns Detected

| Pattern | Description |
|---|---|
| `SIM_SWAP` | Illegal SIM re-issue to intercept OTPs |
| `PHISHING` | Fake SMS/email luring victims to spoofed sites |
| `MULE_NETWORK` | Recruited accounts used to layer stolen funds |
| `VISHING` | Voice call impersonation of bank/govt officials |
| `INVESTMENT_SCAM` | Fake returns via WhatsApp/Telegram groups |
| `INSIDER_THREAT` | Telecom/bank employee collusion |
| `HYBRID` | Two or more patterns active simultaneously |

---

## 📋 10-Phase Development Plan

| Phase | Title | Status |
|---|---|---|
| **Phase 1** | Foundation — Flask API, file storage, React scaffold | ✅ Complete |
| **Phase 2** | Data Ingestion — CSV adapter, mock case loader | ✅ Complete |
| **Phase 3** | Entity Extraction — IBM Bob NER pipeline | ✅ Complete |
| **Phase 4** | ML Fraud Classifier — XGBoost + rule-based scoring | ✅ Complete |
| **Phase 5** | Graph Analysis — NetworkX hierarchy builder | ✅ Complete |
| **Phase 6** | FIR Generator — structured brief with legal sections | ✅ Complete |
| **Phase 7** | React Frontend — network graph, hierarchy, FIR viewer | 🔄 In Progress |
| **Phase 8** | IBM Bob Integration — watsonx.ai LLM enrichment | 🔄 In Progress |
| **Phase 9** | Reporting & Export — PDF/TXT FIR download | ⏳ Pending |
| **Phase 10** | Integration & Polish — end-to-end testing, demo | ⏳ Pending |

---

## 🖥️ Demo

| Artifact | Link |
|---|---|
| 📹 Demo Video | [See demo/demo-video-link.txt](demo/demo-video-link.txt) |
| 🖼️ Screenshots | [See demo/screenshots/](demo/screenshots/) |
| 📊 Presentation | [See presentation/](presentation/) |

---

## ⚖️ Applicable Legal Sections

The tool automatically maps fraud patterns to relevant Indian law:

- **IT Act §66C** — Identity theft
- **IT Act §66D** — Cheating by personation using computer resource
- **IPC §419** — Cheating by personation
- **IPC §420** — Cheating and dishonestly inducing delivery of property
- **IPC §468** — Forgery for purpose of cheating
- **IPC §120B** — Criminal conspiracy
- **PMLA §3/§4** — Money laundering offences
- **TRAI Regulations** — Telecom violations

---

## ⚠️ Known Limitations

- Authentication is mocked — not production-ready
- AI entity extraction uses rule-based regex in Phase 1; IBM Bob LLM integration is Phase 8
- Only tested with the 3 provided mock cases and the CSV dataset
- Network graph performance may degrade beyond 500 nodes
- FIR draft requires manual review before official submission

---

## 🏅 What We're Most Proud Of

The **end-to-end pipeline** — from pasting raw unstructured intelligence text to getting a fully structured, FIR-ready case brief with a visual network graph in under 3 seconds. The hierarchy builder that automatically identifies the **Kingpin → Coordinator → Mule → Victim** chain from unstructured data is the core innovation, directly addressing the Jamtara investigators' biggest pain point.

---

## 📄 License

This project was built for the IBM Hackathon using only authorized mock/synthetic data. All case data is fictional and for demonstration purposes only.
