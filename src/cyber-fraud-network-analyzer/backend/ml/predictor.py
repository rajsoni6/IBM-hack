"""
ml/predictor.py

Loads the saved model + preprocessor and runs inference.
Does NOT retrain. Called by the /api/predict route.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

import joblib
import numpy as np

from storage.file_store import generate_id, now_iso, write_json, read_json
from config.settings import DATA_DIR, MODELS_DIR

PREDICTIONS_FILE = DATA_DIR / "predictions" / "predictions.json"

# ── Classification label mapping ──────────────────────────────────────────────
# Derived from the actual model targets (0 = normal, 1 = fraud)
RISK_BANDS = [
    (0.80, "HIGH_RISK"),
    (0.50, "MEDIUM_RISK"),
    (0.20, "LOW_RISK"),
    (0.00, "VERY_LOW_RISK"),
]


def _risk_label(score: float) -> str:
    for threshold, label in RISK_BANDS:
        if score >= threshold:
            return label
    return "VERY_LOW_RISK"


class FraudPredictor:
    """
    Singleton-style predictor.  Loads artifacts on first call; reuses them
    for subsequent predictions (no model re-training at inference time).
    """

    _instance: Optional["FraudPredictor"] = None

    def __init__(self, models_dir: Optional[Path] = None) -> None:
        base = Path(models_dir) if models_dir else MODELS_DIR
        self.model_path  = base / "fraud_model.pkl"
        self.scaler_path = base / "preprocessor.pkl"
        self.meta_path   = base / "model_metadata.json"
        self.feat_path   = base / "feature_columns.json"

        self._model    = None
        self._scaler   = None
        self._meta: dict = {}
        self._features: list[str] = []
        self._threshold: float = 0.5
        self._loaded = False

    @classmethod
    def get(cls, models_dir: Optional[Path] = None) -> "FraudPredictor":
        if cls._instance is None or not cls._instance._loaded:
            cls._instance = cls(models_dir)
        return cls._instance

    def load(self) -> None:
        if self._loaded:
            return
        if not self.model_path.exists():
            raise FileNotFoundError(
                f"Model not found at {self.model_path}. "
                "Run scripts/train_model.py first."
            )
        self._model    = joblib.load(self.model_path)
        self._scaler   = joblib.load(self.scaler_path)
        self._meta     = json.loads(self.meta_path.read_text(encoding="utf-8"))
        self._features = json.loads(self.feat_path.read_text(encoding="utf-8"))
        self._threshold = float(self._meta.get("threshold", 0.5))
        self._loaded = True

    @property
    def model_version(self) -> str:
        return self._meta.get("model_version", "unknown")

    def predict(
        self,
        features: dict,
        case_id: str = "",
        entity_id: str = "",
    ) -> dict:
        """
        Run a single prediction.

        Parameters
        ----------
        features : dict mapping feature_name → numeric value
        case_id  : optional investigation case reference
        entity_id: optional entity (account) reference

        Returns
        -------
        Prediction dict with risk_score, classification, top_features, explanation
        """
        self.load()

        # Build feature vector in the correct column order
        vec = np.array(
            [float(features.get(f, 0.0)) for f in self._features],
            dtype=np.float64,
        ).reshape(1, -1)

        # Scale
        vec_s = self._scaler.transform(vec)

        # Predict
        proba = float(self._model.predict_proba(vec_s)[0, 1])
        classification = _risk_label(proba)

        # Top contributing features (absolute coefficient / importance weighted by input value)
        top_features = self._top_features(vec[0])

        explanation = self._build_explanation(proba, classification, top_features)

        result: dict = {
            "prediction_id":  generate_id("pred"),
            "case_id":        case_id,
            "entity_id":      entity_id,
            "model_version":  self.model_version,
            "timestamp":      now_iso(),
            "risk_score":     round(proba, 6),
            "classification": classification,
            "top_features":   top_features,
            "explanation":    explanation,
        }

        # Persist
        _append_prediction(result)
        return result

    def _top_features(self, raw_vec: np.ndarray, top_n: int = 5) -> list[dict]:
        """Return top N feature contributions (magnitude of scaled input × weight)."""
        try:
            # Get model importances / coefficients
            if hasattr(self._model, "feature_importances_"):
                weights = self._model.feature_importances_
            elif hasattr(self._model, "coef_"):
                weights = np.abs(self._model.coef_[0])
            else:
                return []

            # Scale the raw input the same way
            vec_s = self._scaler.transform(raw_vec.reshape(1, -1))[0]
            contrib = np.abs(vec_s * weights)
            order   = np.argsort(contrib)[::-1][:top_n]

            return [
                {
                    "feature":    self._features[i],
                    "value":      round(float(raw_vec[i]), 4),
                    "importance": round(float(weights[i]), 6),
                }
                for i in order
            ]
        except Exception:
            return []

    def _build_explanation(
        self, score: float, classification: str, top: list[dict]
    ) -> str:
        top_names = ", ".join(f["feature"] for f in top[:3]) if top else "unknown"
        return (
            f"The model assigned a fraud probability of {score:.1%}. "
            f"Classification: {classification}. "
            f"Top contributing features: {top_names}. "
            "This is a model prediction and NOT proof of criminal activity. "
            "Human review is required before taking any action."
        )


def _append_prediction(record: dict) -> None:
    PREDICTIONS_FILE.parent.mkdir(parents=True, exist_ok=True)
    existing: list = read_json(PREDICTIONS_FILE) or []
    existing.append(record)
    write_json(PREDICTIONS_FILE, existing)
