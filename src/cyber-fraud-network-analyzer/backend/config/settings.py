"""
config/settings.py
All configuration loaded from environment / .env file.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# ── Paths ─────────────────────────────────────────────────────────────────────
BASE_DIR   = Path(__file__).resolve().parents[2]          # project root
DATA_DIR   = BASE_DIR / "data"
MODELS_DIR = BASE_DIR / "models"

# Sub-directories (created on startup)
DATA_SUBDIRS = [
    "raw", "processed", "cases", "entities",
    "relationships", "transactions", "evidence",
    "predictions", "reports", "sample", "users",
]

# Upload limits
MAX_UPLOAD_BYTES = int(os.getenv("MAX_UPLOAD_BYTES", str(50 * 1024 * 1024)))   # 50 MB

# ── Flask ─────────────────────────────────────────────────────────────────────
FLASK_ENV   = os.getenv("FLASK_ENV", "development")
FLASK_DEBUG = FLASK_ENV == "development"
PORT        = int(os.getenv("PORT", 5000))
SECRET_KEY  = os.getenv("SECRET_KEY", "dev-secret-change-in-prod")

# ── CORS ──────────────────────────────────────────────────────────────────────
CORS_ORIGINS = os.getenv("CORS_ORIGINS", "http://localhost:5173,http://localhost:3000").split(",")

# ── AI Provider ───────────────────────────────────────────────────────────────
AI_PROVIDER        = os.getenv("AI_PROVIDER", "mock")   # mock | watsonx
WATSONX_API_KEY    = os.getenv("WATSONX_API_KEY", "")
WATSONX_PROJECT_ID = os.getenv("WATSONX_PROJECT_ID", "")
WATSONX_URL        = os.getenv("WATSONX_URL", "https://us-south.ml.cloud.ibm.com")
WATSONX_MODEL_ID   = os.getenv("WATSONX_MODEL_ID", "ibm/granite-13b-instruct-v2")

# ── Source data (training CSVs) ───────────────────────────────────────────────
SRC_DATA_DIR = BASE_DIR.parent / "data"   # src/data/ — the 3 CSV datasets
