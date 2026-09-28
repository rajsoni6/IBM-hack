"""
scripts/evaluate_model.py

Load a saved model and run full evaluation on the test set.
Prints a detailed report and writes evaluation_metrics.json.

Run from project root:
  python scripts/evaluate_model.py
"""

import json
import sys
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.metrics import (
    precision_score, recall_score, f1_score,
    roc_auc_score, average_precision_score,
    confusion_matrix, classification_report,
)

SCRIPT_DIR   = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
MODELS_DIR   = PROJECT_ROOT / "models"

sys.path.insert(0, str(PROJECT_ROOT / "backend"))
from ml.features import (
    load_transactions, load_fraud_labels, build_account_features,
    FEATURE_COLUMNS, TARGET_COLUMN,
)
from scripts.train_model import split_data


def main():
    model_pkl  = MODELS_DIR / "fraud_model.pkl"
    scaler_pkl = MODELS_DIR / "preprocessor.pkl"
    meta_path  = MODELS_DIR / "model_metadata.json"

    if not model_pkl.exists():
        print("ERROR: models/fraud_model.pkl not found. Run scripts/train_model.py first.")
        sys.exit(1)

    model  = joblib.load(model_pkl)
    scaler = joblib.load(scaler_pkl)
    meta   = json.loads(meta_path.read_text(encoding="utf-8"))
    threshold = meta.get("threshold", 0.5)

    print("Loading dataset...")
    tx_df             = load_transactions()
    fraud_account_ids = load_fraud_labels()
    feat_df           = build_account_features(tx_df, fraud_account_ids)

    _, _, X_test, _, _, y_test = split_data(feat_df)
    X_test_s = scaler.transform(X_test)

    proba = model.predict_proba(X_test_s)[:, 1]
    pred  = (proba >= threshold).astype(int)

    print(f"\nModel         : {meta.get('model_name')} ({meta.get('model_version')})")
    print(f"Threshold     : {threshold}")
    print(f"Test samples  : {len(y_test)} | Fraud: {y_test.sum()} | Normal: {(y_test==0).sum()}")
    print()

    cm = confusion_matrix(y_test, pred)
    print("Confusion Matrix:")
    print(f"  [[TN={cm[0][0]:4d}  FP={cm[0][1]:4d}]")
    print(f"   [FN={cm[1][0]:4d}  TP={cm[1][1]:4d}]]")
    print()

    print("Classification Report:")
    print(classification_report(y_test, pred, target_names=["normal", "fraud"], digits=4))

    roc_auc = roc_auc_score(y_test, proba)
    pr_auc  = average_precision_score(y_test, proba)
    print(f"ROC-AUC : {roc_auc:.4f}")
    print(f"PR-AUC  : {pr_auc:.4f}")


if __name__ == "__main__":
    main()
