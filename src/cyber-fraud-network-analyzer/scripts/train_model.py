"""
scripts/train_model.py

Full ML training pipeline for the Cyber Fraud Network Analyzer.

Steps
-----
1. Load & profile the 50K+ record dataset
2. Build account-level features (no target leakage)
3. Stratified 60/20/20 train/val/test split
4. Preprocessing pipeline (fit on train only)
5. Handle class imbalance via class_weight='balanced'
6. Train: Logistic Regression, Random Forest, XGBoost
7. Evaluate each on validation set; select best by PR-AUC (fraud-minority focus)
8. Final evaluation on held-out test set
9. Save all model artifacts under models/

Run from project root:
  python scripts/train_model.py
"""

from __future__ import annotations

import json
import sys
import warnings
from datetime import datetime, timezone
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.linear_model  import LogisticRegression
from sklearn.ensemble      import RandomForestClassifier
from sklearn.preprocessing import StandardScaler, LabelEncoder
from sklearn.pipeline      import Pipeline
from sklearn.compose       import ColumnTransformer
from sklearn.model_selection import train_test_split, StratifiedKFold
from sklearn.metrics       import (
    precision_score, recall_score, f1_score,
    roc_auc_score, average_precision_score,
    confusion_matrix, classification_report,
)
from xgboost import XGBClassifier

warnings.filterwarnings("ignore")

# ── Paths ─────────────────────────────────────────────────────────────────────
SCRIPT_DIR   = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
WORKSPACE    = PROJECT_ROOT.parent.parent
SRC_DATA_DIR = WORKSPACE / "src" / "data"
MODELS_DIR   = PROJECT_ROOT / "models"
MODELS_DIR.mkdir(parents=True, exist_ok=True)

sys.path.insert(0, str(PROJECT_ROOT / "backend"))
from ml.features import (
    load_transactions, load_fraud_labels, build_account_features,
    FEATURE_COLUMNS, TARGET_COLUMN,
)

RANDOM_STATE = 42
MODEL_VERSION = "fraud-model-v1"


# ── 1. Load data ──────────────────────────────────────────────────────────────

def load_dataset() -> pd.DataFrame:
    print("[1/8] Loading transaction dataset...")
    tx_df            = load_transactions()
    fraud_account_ids = load_fraud_labels()
    feat_df          = build_account_features(tx_df, fraud_account_ids)
    n_fraud  = feat_df[TARGET_COLUMN].sum()
    n_normal = len(feat_df) - n_fraud
    print(f"      Accounts: {len(feat_df):,} | Fraud: {n_fraud} | Normal: {n_normal}")
    print(f"      Class ratio fraud/(total): {n_fraud/len(feat_df):.4f}")
    return feat_df


# ── 2. Split ──────────────────────────────────────────────────────────────────

def split_data(feat_df: pd.DataFrame):
    print("[2/8] Splitting 60/20/20 stratified...")
    X = feat_df[FEATURE_COLUMNS].values
    y = feat_df[TARGET_COLUMN].values

    X_tv, X_test, y_tv, y_test = train_test_split(
        X, y, test_size=0.20, random_state=RANDOM_STATE, stratify=y
    )
    X_train, X_val, y_train, y_val = train_test_split(
        X_tv, y_tv, test_size=0.25, random_state=RANDOM_STATE, stratify=y_tv
    )
    print(f"      Train: {len(X_train):,} | Val: {len(X_val):,} | Test: {len(X_test):,}")
    return X_train, X_val, X_test, y_train, y_val, y_test


# ── 3. Preprocessing (fit on train only) ─────────────────────────────────────

def build_preprocessor(X_train: np.ndarray) -> StandardScaler:
    print("[3/8] Fitting scaler on training data only...")
    scaler = StandardScaler()
    scaler.fit(X_train)
    return scaler


# ── 4. Evaluate a model ───────────────────────────────────────────────────────

def evaluate(name: str, model, X: np.ndarray, y: np.ndarray, threshold: float = 0.5) -> dict:
    proba   = model.predict_proba(X)[:, 1]
    pred    = (proba >= threshold).astype(int)

    roc_auc = roc_auc_score(y, proba)
    pr_auc  = average_precision_score(y, proba)
    cm      = confusion_matrix(y, pred).tolist()
    report  = classification_report(y, pred, output_dict=True, zero_division=0)

    metrics = {
        "model":           name,
        "threshold":       threshold,
        "roc_auc":         round(roc_auc,  4),
        "pr_auc":          round(pr_auc,   4),
        "precision":       round(precision_score(y, pred, zero_division=0), 4),
        "recall":          round(recall_score(y, pred, zero_division=0),    4),
        "f1":              round(f1_score(y, pred, zero_division=0),        4),
        "confusion_matrix": cm,
        "class_report":    {
            str(k): {
                "precision": round(v.get("precision", 0), 4),
                "recall":    round(v.get("recall",    0), 4),
                "f1-score":  round(v.get("f1-score",  0), 4),
                "support":   int(v.get("support",     0)),
            }
            for k, v in report.items()
            if k not in ("accuracy", "macro avg", "weighted avg")
        },
        "macro_avg":    {k: round(v, 4) for k, v in report.get("macro avg", {}).items()
                         if k != "support"},
        "weighted_avg": {k: round(v, 4) for k, v in report.get("weighted avg", {}).items()
                         if k != "support"},
    }
    return metrics


# ── 5. Train all models ───────────────────────────────────────────────────────

def train_models(X_train_s: np.ndarray, y_train: np.ndarray):
    print("[4/8] Training models...")

    n_neg = int((y_train == 0).sum())
    n_pos = int((y_train == 1).sum())
    scale_pos = n_neg / max(n_pos, 1)

    models: dict[str, object] = {}

    # Logistic Regression
    print("      Training Logistic Regression...")
    lr = LogisticRegression(
        class_weight="balanced", max_iter=1000,
        solver="lbfgs", random_state=RANDOM_STATE,
    )
    lr.fit(X_train_s, y_train)
    models["logistic_regression"] = lr

    # Random Forest
    print("      Training Random Forest...")
    rf = RandomForestClassifier(
        n_estimators=200, max_depth=10,
        class_weight="balanced", n_jobs=-1,
        random_state=RANDOM_STATE,
    )
    rf.fit(X_train_s, y_train)
    models["random_forest"] = rf

    # XGBoost
    print("      Training XGBoost...")
    xgb = XGBClassifier(
        n_estimators=200, max_depth=6, learning_rate=0.1,
        scale_pos_weight=scale_pos,
        eval_metric="aucpr",
        random_state=RANDOM_STATE, verbosity=0,
    )
    xgb.fit(X_train_s, y_train)
    models["xgboost"] = xgb

    return models


# ── 6. Select best model ──────────────────────────────────────────────────────

def select_best(val_metrics: dict[str, dict]) -> str:
    """
    Selection criterion: highest PR-AUC on validation set.

    Rationale: the dataset is severely imbalanced (0.29 % fraud).
    ROC-AUC can be misleadingly high even for poor models.
    PR-AUC directly measures the trade-off between precision and recall
    on the minority (fraud) class, which is the operational objective:
    maximise fraud detection while keeping false-positive workload manageable.
    """
    best = max(val_metrics, key=lambda m: val_metrics[m]["pr_auc"])
    return best


# ── 7. Optimal threshold ──────────────────────────────────────────────────────

def find_best_threshold(model, X_val_s: np.ndarray, y_val: np.ndarray) -> float:
    """
    Find threshold that maximises F1 on the validation set.
    Evaluated over [0.05, 0.95] in steps of 0.05.
    """
    proba = model.predict_proba(X_val_s)[:, 1]
    best_f1, best_t = 0.0, 0.5
    for t in np.arange(0.05, 0.96, 0.05):
        pred = (proba >= t).astype(int)
        f1   = f1_score(y_val, pred, zero_division=0)
        if f1 > best_f1:
            best_f1 = f1
            best_t  = round(float(t), 2)
    return best_t


# ── 8. Feature importance ─────────────────────────────────────────────────────

def get_feature_importance(model, model_name: str) -> list[dict]:
    if model_name == "logistic_regression":
        coefs = np.abs(model.coef_[0])
        order = np.argsort(coefs)[::-1]
        return [
            {"feature": FEATURE_COLUMNS[i], "importance": round(float(coefs[i]), 6)}
            for i in order[:10]
        ]
    elif model_name == "random_forest":
        imp   = model.feature_importances_
        order = np.argsort(imp)[::-1]
        return [
            {"feature": FEATURE_COLUMNS[i], "importance": round(float(imp[i]), 6)}
            for i in order[:10]
        ]
    elif model_name == "xgboost":
        imp   = model.feature_importances_
        order = np.argsort(imp)[::-1]
        return [
            {"feature": FEATURE_COLUMNS[i], "importance": round(float(imp[i]), 6)}
            for i in order[:10]
        ]
    return []


# ── 9. Save artifacts ─────────────────────────────────────────────────────────

def save_artifacts(
    best_name: str,
    best_model,
    scaler: StandardScaler,
    threshold: float,
    train_metrics: dict,
    val_metrics: dict,
    test_metrics: dict,
    feat_df: pd.DataFrame,
    all_val_metrics: dict,
) -> None:
    print("[8/8] Saving artifacts...")

    # Model
    joblib.dump(best_model, MODELS_DIR / "fraud_model.pkl")
    # Preprocessor
    joblib.dump(scaler, MODELS_DIR / "preprocessor.pkl")

    # Feature columns
    (MODELS_DIR / "feature_columns.json").write_text(
        json.dumps(FEATURE_COLUMNS, indent=2), encoding="utf-8"
    )

    # Class distribution in full dataset
    n_fraud  = int(feat_df[TARGET_COLUMN].sum())
    n_normal = int(len(feat_df) - n_fraud)

    # Evaluation metrics
    eval_out = {
        "model_name":       best_name,
        "threshold":        threshold,
        "validation":       val_metrics,
        "test":             test_metrics,
        "all_models_val":   all_val_metrics,
        "selection_reason": (
            "PR-AUC was used as the primary selection criterion because "
            "the dataset is severely imbalanced (fraud ≈ 0.29 %). "
            "PR-AUC measures precision-recall trade-off on the minority "
            "class and is more informative than ROC-AUC in this setting."
        ),
    }
    (MODELS_DIR / "evaluation_metrics.json").write_text(
        json.dumps(eval_out, indent=2), encoding="utf-8"
    )

    # Feature importances
    importance = get_feature_importance(best_model, best_name)

    # Model metadata
    metadata = {
        "model_version":   MODEL_VERSION,
        "model_name":      best_name,
        "target_column":   TARGET_COLUMN,
        "class_mapping":   {"0": "normal", "1": "fraud"},
        "threshold":       threshold,
        "feature_columns": FEATURE_COLUMNS,
        "feature_count":   len(FEATURE_COLUMNS),
        "top_features":    importance,
        "dataset": {
            "total_accounts": n_fraud + n_normal,
            "fraud_accounts": n_fraud,
            "normal_accounts": n_normal,
            "fraud_ratio": round(n_fraud / (n_fraud + n_normal), 6),
            "source_files": [
                "src/data/transactions/transactions_0_0.csv",
                "src/data/transactions/transactions_1_0.csv",
                "src/data/fraud/transactions_fraud.csv",
                "src/data/fraud/fraud_cases.csv",
                "src/data/accounts/accounts_0_0.csv",
                "src/data/accounts/accounts_1_0.csv",
            ],
        },
        "training_config": {
            "random_state": RANDOM_STATE,
            "split": "60/20/20 stratified",
            "imbalance_strategy": "class_weight='balanced' / scale_pos_weight",
            "val_metric": "PR-AUC",
        },
        "trained_at": datetime.now(timezone.utc).isoformat(),
        "known_limitations": [
            "All transactions share the same date (2024-01-01); no temporal features are possible.",
            "Fraud transaction amounts are all exactly 9999.0; near_threshold_ratio is a near-perfect discriminator and may be brittle in production.",
            "Dataset is synthetically generated; real-world distributions will differ.",
            "No network/graph features (betweenness, PageRank) used — requires NetworkX at training time.",
            "SMOTE not applied; class_weight used instead to avoid synthetic oversampling artifacts.",
        ],
    }
    (MODELS_DIR / "model_metadata.json").write_text(
        json.dumps(metadata, indent=2), encoding="utf-8"
    )

    print(f"      Artifacts saved to: {MODELS_DIR}")
    print(f"      Model version: {MODEL_VERSION}")
    print(f"      Best model: {best_name}")
    print(f"      Threshold: {threshold}")
    print(f"      Val  PR-AUC={val_metrics['pr_auc']}  ROC-AUC={val_metrics['roc_auc']}")
    print(f"      Test PR-AUC={test_metrics['pr_auc']} ROC-AUC={test_metrics['roc_auc']}")


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> dict:
    print("=" * 60)
    print(" Cyber Fraud Network Analyzer — ML Training Pipeline")
    print("=" * 60)

    feat_df = load_dataset()

    X_train, X_val, X_test, y_train, y_val, y_test = split_data(feat_df)

    scaler = build_preprocessor(X_train)
    X_train_s = scaler.transform(X_train)
    X_val_s   = scaler.transform(X_val)
    X_test_s  = scaler.transform(X_test)

    models = train_models(X_train_s, y_train)

    print("[5/8] Evaluating on validation set...")
    all_val_metrics: dict[str, dict] = {}
    for name, model in models.items():
        m = evaluate(name, model, X_val_s, y_val)
        all_val_metrics[name] = m
        print(f"      {name}: PR-AUC={m['pr_auc']} ROC-AUC={m['roc_auc']} F1={m['f1']}")

    print("[6/8] Selecting best model (by PR-AUC)...")
    best_name  = select_best(all_val_metrics)
    best_model = models[best_name]
    print(f"      Selected: {best_name}")

    print("[7/8] Tuning classification threshold on val set...")
    threshold = find_best_threshold(best_model, X_val_s, y_val)
    print(f"      Optimal threshold: {threshold}")

    val_metrics  = evaluate(best_name, best_model, X_val_s,  y_val,  threshold)
    test_metrics = evaluate(best_name, best_model, X_test_s, y_test, threshold)

    save_artifacts(
        best_name, best_model, scaler, threshold,
        all_val_metrics[best_name], val_metrics, test_metrics,
        feat_df, all_val_metrics,
    )

    print("\nDone.")
    return {
        "best_model":    best_name,
        "threshold":     threshold,
        "val_metrics":   val_metrics,
        "test_metrics":  test_metrics,
    }


if __name__ == "__main__":
    main()
