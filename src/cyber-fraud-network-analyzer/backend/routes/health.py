"""
routes/health.py
GET /api/health — liveness check.
"""

from flask import Blueprint, jsonify
from config.settings import FLASK_ENV, AI_PROVIDER, DATA_DIR, MODELS_DIR

health_bp = Blueprint("health", __name__)


@health_bp.get("/api/health")
def health():
    model_trained = (MODELS_DIR / "fraud_model.pkl").exists()
    return jsonify({
        "status":          "ok",
        "service":         "Cyber Fraud Network Analyzer",
        "version":         "1.0.0",
        "environment":     FLASK_ENV,
        "ai_provider":     AI_PROVIDER,
        "data_dir":        str(DATA_DIR),
        "model_trained":   model_trained,
        "phase":           10,
        "phases_complete": [
            "foundation",
            "data-ingestion",
            "entity-extraction",
            "graph-analysis",
            "ml-scoring",
            "ai-investigation",
            "fir-generation",
            "frontend-ui",
            "reporting",
            "integration",
        ],
        "phases_pending": [],
    }), 200
