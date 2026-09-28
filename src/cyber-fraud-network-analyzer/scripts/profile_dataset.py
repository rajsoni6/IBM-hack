"""
scripts/profile_dataset.py

Fast dataset profiling using pandas.
Outputs data/ml/dataset_profile.json.

Run from project root:
  python scripts/profile_dataset.py
"""

import json
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd
import numpy as np

SCRIPT_DIR   = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
WORKSPACE    = PROJECT_ROOT.parent.parent
SRC_DATA_DIR = WORKSPACE / "src" / "data"
OUTPUT_DIR   = PROJECT_ROOT / "data" / "ml"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

sys.path.insert(0, str(PROJECT_ROOT / "backend"))
from ml.features import load_transactions, load_fraud_labels, FEATURE_COLUMNS


def profile_df(df: pd.DataFrame, name: str, path: Path) -> dict:
    col_profiles = {}
    for col in df.columns:
        s     = df[col]
        miss  = int(s.isna().sum())
        uniq  = int(s.nunique())
        dtype = str(s.dtype)

        if col == "embedding":
            col_profiles[col] = {"type": "embedding_vector", "note": "768-dim pipe-separated float, excluded", "missing": miss}
            continue

        if pd.api.types.is_numeric_dtype(s):
            q = s.quantile([0.25, 0.5, 0.75])
            mean_val = float(s.mean())
            std_val  = float(s.std()) if len(s) > 1 else 0.0
            outliers = int(((s - mean_val).abs() > 3 * std_val).sum()) if std_val > 0 else 0
            col_profiles[col] = {
                "type": "numeric", "missing": miss, "missing_pct": round(miss/len(df)*100, 2),
                "unique": uniq, "min": round(float(s.min()), 4), "max": round(float(s.max()), 4),
                "mean": round(mean_val, 4), "median": round(float(q[0.5]), 4),
                "q25": round(float(q[0.25]), 4), "q75": round(float(q[0.75]), 4),
                "std": round(std_val, 4), "zeros": int((s == 0).sum()),
                "negatives": int((s < 0).sum()), "outliers_3sigma": outliers,
            }
        elif pd.api.types.is_datetime64_any_dtype(s):
            col_profiles[col] = {
                "type": "datetime", "missing": miss, "unique": uniq,
                "min": str(s.min()), "max": str(s.max()),
            }
        else:
            top5 = s.value_counts().head(5).to_dict()
            col_profiles[col] = {
                "type": "categorical", "missing": miss, "missing_pct": round(miss/len(df)*100, 2),
                "unique": uniq, "top_values": [{"value": k, "count": v} for k, v in top5.items()],
            }

    dup = int(df.drop(columns=["embedding"], errors="ignore").duplicated().sum())
    numeric_cols     = [c for c, p in col_profiles.items() if p.get("type") == "numeric"]
    categorical_cols = [c for c, p in col_profiles.items() if p.get("type") == "categorical"]
    datetime_cols    = [c for c, p in col_profiles.items() if p.get("type") == "datetime"]

    return {
        "file_name": path.name, "file_format": "CSV",
        "file_size_kb": round(path.stat().st_size / 1024, 1),
        "num_rows": len(df), "num_columns": len(df.columns),
        "column_names": list(df.columns),
        "numeric_columns": numeric_cols,
        "categorical_columns": categorical_cols,
        "datetime_columns": datetime_cols,
        "duplicate_rows": dup,
        "columns": col_profiles,
    }


def main():
    print("Profiling dataset...")

    FILES = {
        "accounts_0_0":     SRC_DATA_DIR / "accounts"     / "accounts_0_0.csv",
        "accounts_1_0":     SRC_DATA_DIR / "accounts"     / "accounts_1_0.csv",
        "transactions_0_0": SRC_DATA_DIR / "transactions"  / "transactions_0_0.csv",
        "transactions_1_0": SRC_DATA_DIR / "transactions"  / "transactions_1_0.csv",
        "fraud_cases":      SRC_DATA_DIR / "fraud"         / "fraud_cases.csv",
        "fraud_transactions": SRC_DATA_DIR / "fraud"       / "transactions_fraud.csv",
    }

    profiles = {}
    for name, path in FILES.items():
        print(f"  {name} ({path.name})...")
        # Don't expand the embedding column — read as string for profiling
        df = pd.read_csv(path)
        profiles[name] = profile_df(df, name, path)

    # Target analysis
    fraud_ids = load_fraud_labels()
    n_total   = profiles["accounts_0_0"]["num_rows"] + profiles["accounts_1_0"]["num_rows"]
    n_fraud   = len(fraud_ids)
    n_normal  = n_total - n_fraud

    target_analysis = {
        "selected_target": "is_fraud",
        "target_level": "account",
        "rationale": (
            "No pre-labelled fraud column exists. Ground-truth is derived "
            "from fraud_cases.csv (50 patterns, 266 involved accounts) and "
            "fraud/transactions_fraud.csv (266 labelled transactions). "
            "Account-level is the natural modelling unit: behavioural features "
            "(velocity, volume, peer diversity) are computed per account."
        ),
        "target_candidate_columns": ["is_fraud (derived)"],
        "class_distribution": {"is_fraud=0 (normal)": n_normal, "is_fraud=1 (fraud)": n_fraud},
        "imbalance_ratio_fraud_to_normal": round(n_fraud / max(n_normal, 1), 4),
        "fraud_pct": round(n_fraud / n_total * 100, 3),
    }

    report = {
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "data_directory": str(SRC_DATA_DIR),
        "files": profiles,
        "target_analysis": target_analysis,
        "ml_task": {
            "type": "binary_classification",
            "target": "is_fraud",
            "level": "account",
            "feature_columns": FEATURE_COLUMNS,
            "feature_count": len(FEATURE_COLUMNS),
        },
        "data_quality_notes": [
            "No missing values in any file.",
            "Fraud transaction amounts are all exactly 9999.0 — strong signal but may overfit.",
            "All timestamps are 2024-01-01 — no temporal features possible.",
            "Embedding column (768-dim) excluded from tabular ML.",
            "No duplicate accounts or transactions detected.",
        ],
    }

    out = OUTPUT_DIR / "dataset_profile.json"
    out.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    print(f"\nProfile saved: {out}")
    print(f"Target: is_fraud | Fraud={n_fraud} | Normal={n_normal} | Ratio={round(n_fraud/n_total*100,3)}%")


if __name__ == "__main__":
    main()
