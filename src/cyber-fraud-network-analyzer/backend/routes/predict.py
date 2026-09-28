"""
routes/predict.py

POST /api/predict  — score an account/entity for fraud risk

The endpoint loads the saved model + preprocessor from models/.
It does NOT retrain at request time.

Request body
------------
{
  "features": {
    "tx_count": 12,
    "tx_out_count": 8,
    ...
  },
  "case_id":   "case_abc",   (optional)
  "entity_id": "acc_001"     (optional)
}

Response
--------
{
  "prediction_id": "pred_...",
  "case_id": "...",
  "entity_id": "...",
  "model_version": "fraud-model-v1",
  "timestamp": "...",
  "risk_score": 0.87,
  "classification": "HIGH_RISK",
  "top_features": [...],
  "explanation": "..."
}
"""

from flask import Blueprint, jsonify, request
from utils.auth_middleware import require_permission

predict_bp = Blueprint("predict", __name__, url_prefix="/api")


@predict_bp.post("/predict")
@require_permission("read")
def predict():
    body = request.get_json(silent=True) or {}

    features = body.get("features")
    if not isinstance(features, dict) or not features:
        return jsonify({
            "error": (
                "Request body must include a non-empty 'features' object. "
                "Keys should be feature names, values should be numeric."
            )
        }), 400

    case_id   = str(body.get("case_id",   ""))
    entity_id = str(body.get("entity_id", ""))

    # Lazy-load predictor (no retraining)
    try:
        from ml.predictor import FraudPredictor
        predictor = FraudPredictor.get()
        result    = predictor.predict(features, case_id=case_id, entity_id=entity_id)
        return jsonify(result), 200
    except FileNotFoundError as exc:
        return jsonify({
            "error": str(exc),
            "hint": "Run scripts/train_model.py to train and save the model first."
        }), 503
    except Exception as exc:
        return jsonify({"error": f"Prediction failed: {exc}"}), 500
