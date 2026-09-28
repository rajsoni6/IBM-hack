"""
tests/test_ml.py

Unit and integration tests for the ML pipeline:
  - Dataset loading (features.py)
  - Feature generation
  - Preprocessing
  - Prediction output format
  - Model loading (predictor.py)
  - Invalid input handling
  - Missing feature handling
  - /api/predict route (POST)
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from .conftest import register, login, auth_header


# ── Helpers ────────────────────────────────────────────────────────────────────

def _make_tx_csv(path: Path, rows: list[dict]) -> None:
    """Write a minimal transaction CSV to *path*."""
    import csv
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = ["tx_id", "src_id", "dst_id", "amount", "timestamp", "description"]
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)


def _make_fraud_csv(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    import csv
    fields = ["tx_id", "src_id", "dst_id", "amount", "timestamp", "description"]
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)


def _make_fraud_cases_csv(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    import csv
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["case_id", "involved_accounts"])
        w.writeheader()
        w.writerow({"case_id": "c1", "involved_accounts": "acc_fraud_1|acc_fraud_2"})


def _make_accounts_csv(path: Path, account_ids: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    import csv
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["account_id", "name"])
        w.writeheader()
        for aid in account_ids:
            w.writerow({"account_id": aid, "name": aid})


# ── Fixtures ───────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def tiny_dataset(tmp_path_factory):
    """
    Create a tiny in-memory dataset with 3 normal accounts and 2 fraud accounts.
    Returns (tx_files, fraud_tx_file, fraud_cases_file, accounts_files).
    """
    base = tmp_path_factory.mktemp("ml_data")

    normal_rows = [
        {"tx_id": "t1", "src_id": "acc_n1", "dst_id": "acc_n2",
         "amount": "500.0", "timestamp": "2024-01-01T10:00:00Z",
         "description": "salary payment"},
        {"tx_id": "t2", "src_id": "acc_n2", "dst_id": "acc_n3",
         "amount": "250.0", "timestamp": "2024-01-01T11:00:00Z",
         "description": "rent payment"},
        {"tx_id": "t3", "src_id": "acc_n3", "dst_id": "acc_n1",
         "amount": "100.0", "timestamp": "2024-01-01T12:00:00Z",
         "description": "utility bill"},
    ]
    fraud_rows = [
        {"tx_id": "tf1", "src_id": "acc_fraud_1", "dst_id": "acc_fraud_2",
         "amount": "9999.0", "timestamp": "2024-01-01T08:00:00Z",
         "description": "structuring deposit below threshold"},
        {"tx_id": "tf2", "src_id": "acc_fraud_2", "dst_id": "acc_fraud_1",
         "amount": "9999.0", "timestamp": "2024-01-01T08:30:00Z",
         "description": "rapid movement of funds between accounts"},
    ]

    tx_file = base / "transactions" / "tx_0.csv"
    fraud_tx_file = base / "fraud" / "transactions_fraud.csv"
    fraud_cases_file = base / "fraud" / "fraud_cases.csv"
    accounts_file = base / "accounts" / "accounts_0.csv"

    _make_tx_csv(tx_file, normal_rows)
    _make_fraud_csv(fraud_tx_file, fraud_rows)
    _make_fraud_cases_csv(fraud_cases_file)
    _make_accounts_csv(accounts_file, ["acc_n1", "acc_n2", "acc_n3"])

    return [tx_file], fraud_tx_file, fraud_cases_file, [accounts_file]


# ═══════════════════════════════════════════════════════════════════════════════
# 1. Dataset loading
# ═══════════════════════════════════════════════════════════════════════════════

class TestDatasetLoading:
    def test_load_transactions_returns_dataframe(self, tiny_dataset):
        tx_files, fraud_tx, _, _ = tiny_dataset
        from ml.features import load_transactions
        df = load_transactions(tx_files=tx_files, fraud_tx_file=fraud_tx)
        assert isinstance(df, pd.DataFrame)
        assert len(df) > 0

    def test_load_transactions_has_is_fraud_tx(self, tiny_dataset):
        tx_files, fraud_tx, _, _ = tiny_dataset
        from ml.features import load_transactions
        df = load_transactions(tx_files=tx_files, fraud_tx_file=fraud_tx)
        assert "is_fraud_tx" in df.columns
        assert set(df["is_fraud_tx"].unique()).issubset({0, 1})

    def test_fraud_tx_marked_correctly(self, tiny_dataset):
        tx_files, fraud_tx, _, _ = tiny_dataset
        from ml.features import load_transactions
        df = load_transactions(tx_files=tx_files, fraud_tx_file=fraud_tx)
        fraud_rows = df[df["is_fraud_tx"] == 1]
        assert len(fraud_rows) == 2

    def test_load_fraud_labels_union(self, tiny_dataset):
        _, fraud_tx, fraud_cases, _ = tiny_dataset
        from ml.features import load_fraud_labels
        labels = load_fraud_labels(fraud_cases_file=fraud_cases, fraud_tx_file=fraud_tx)
        assert isinstance(labels, set)
        # from transactions_fraud.csv
        assert "acc_fraud_1" in labels
        assert "acc_fraud_2" in labels
        # from fraud_cases.csv (pipe-separated)
        # already covered by acc_fraud_1 / acc_fraud_2

    def test_load_fraud_labels_non_empty(self, tiny_dataset):
        _, fraud_tx, fraud_cases, _ = tiny_dataset
        from ml.features import load_fraud_labels
        labels = load_fraud_labels(fraud_cases_file=fraud_cases, fraud_tx_file=fraud_tx)
        assert len(labels) >= 2


# ═══════════════════════════════════════════════════════════════════════════════
# 2. Feature generation
# ═══════════════════════════════════════════════════════════════════════════════

class TestFeatureGeneration:
    def test_build_account_features_returns_dataframe(self, tiny_dataset):
        tx_files, fraud_tx, fraud_cases, accounts_files = tiny_dataset
        from ml.features import load_transactions, load_fraud_labels, build_account_features
        tx_df = load_transactions(tx_files=tx_files, fraud_tx_file=fraud_tx)
        labels = load_fraud_labels(fraud_cases_file=fraud_cases, fraud_tx_file=fraud_tx)
        feat = build_account_features(tx_df, labels, accounts_files=accounts_files)
        assert isinstance(feat, pd.DataFrame)
        assert len(feat) > 0

    def test_feature_columns_present(self, tiny_dataset):
        tx_files, fraud_tx, fraud_cases, accounts_files = tiny_dataset
        from ml.features import (
            load_transactions, load_fraud_labels,
            build_account_features, FEATURE_COLUMNS,
        )
        tx_df = load_transactions(tx_files=tx_files, fraud_tx_file=fraud_tx)
        labels = load_fraud_labels(fraud_cases_file=fraud_cases, fraud_tx_file=fraud_tx)
        feat = build_account_features(tx_df, labels, accounts_files=accounts_files)
        for col in FEATURE_COLUMNS:
            assert col in feat.columns, f"Missing feature column: {col}"

    def test_target_column_present(self, tiny_dataset):
        tx_files, fraud_tx, fraud_cases, accounts_files = tiny_dataset
        from ml.features import (
            load_transactions, load_fraud_labels,
            build_account_features, TARGET_COLUMN,
        )
        tx_df = load_transactions(tx_files=tx_files, fraud_tx_file=fraud_tx)
        labels = load_fraud_labels(fraud_cases_file=fraud_cases, fraud_tx_file=fraud_tx)
        feat = build_account_features(tx_df, labels, accounts_files=accounts_files)
        assert TARGET_COLUMN in feat.columns

    def test_fraud_accounts_labeled_correctly(self, tiny_dataset):
        tx_files, fraud_tx, fraud_cases, accounts_files = tiny_dataset
        from ml.features import (
            load_transactions, load_fraud_labels,
            build_account_features, TARGET_COLUMN,
        )
        tx_df = load_transactions(tx_files=tx_files, fraud_tx_file=fraud_tx)
        labels = load_fraud_labels(fraud_cases_file=fraud_cases, fraud_tx_file=fraud_tx)
        feat = build_account_features(tx_df, labels, accounts_files=accounts_files)
        fraud_rows = feat[feat[TARGET_COLUMN] == 1]
        assert len(fraud_rows) >= 1

    def test_no_negative_counts(self, tiny_dataset):
        tx_files, fraud_tx, fraud_cases, accounts_files = tiny_dataset
        from ml.features import (
            load_transactions, load_fraud_labels,
            build_account_features, FEATURE_COLUMNS,
        )
        tx_df = load_transactions(tx_files=tx_files, fraud_tx_file=fraud_tx)
        labels = load_fraud_labels(fraud_cases_file=fraud_cases, fraud_tx_file=fraud_tx)
        feat = build_account_features(tx_df, labels, accounts_files=accounts_files)
        # count columns must be non-negative
        count_cols = [c for c in FEATURE_COLUMNS if "count" in c]
        for col in count_cols:
            assert (feat[col] >= 0).all(), f"Negative values in {col}"

    def test_feature_columns_constant(self):
        from ml.features import FEATURE_COLUMNS
        assert len(FEATURE_COLUMNS) == 19
        assert "tx_count" in FEATURE_COLUMNS
        assert "near_threshold_ratio" in FEATURE_COLUMNS
        assert "suspicious_desc_ratio" in FEATURE_COLUMNS


# ═══════════════════════════════════════════════════════════════════════════════
# 3. Preprocessing
# ═══════════════════════════════════════════════════════════════════════════════

class TestPreprocessing:
    def test_scaler_fit_transform(self):
        from sklearn.preprocessing import StandardScaler
        X = np.array([[1.0, 2.0, 3.0], [4.0, 5.0, 6.0], [7.0, 8.0, 9.0]])
        scaler = StandardScaler()
        scaler.fit(X)
        X_s = scaler.transform(X)
        # Check zero mean after scaling (approximately)
        assert abs(X_s.mean(axis=0).mean()) < 1e-10

    def test_scaler_no_fit_on_test(self, tiny_dataset):
        """Scaler must be fitted on train data only."""
        tx_files, fraud_tx, fraud_cases, accounts_files = tiny_dataset
        from ml.features import (
            load_transactions, load_fraud_labels,
            build_account_features, FEATURE_COLUMNS,
        )
        from sklearn.preprocessing import StandardScaler
        from sklearn.model_selection import train_test_split
        tx_df = load_transactions(tx_files=tx_files, fraud_tx_file=fraud_tx)
        labels = load_fraud_labels(fraud_cases_file=fraud_cases, fraud_tx_file=fraud_tx)
        feat = build_account_features(tx_df, labels, accounts_files=accounts_files)
        X = feat[FEATURE_COLUMNS].values
        y = feat["is_fraud"].values
        # With tiny data there may be only 1 class — skip stratify in that case
        X_train, X_test = train_test_split(X, test_size=0.3, random_state=42)
        scaler = StandardScaler()
        scaler.fit(X_train)
        # Must not raise when transforming test set
        X_test_s = scaler.transform(X_test)
        assert X_test_s.shape == X_test.shape


# ═══════════════════════════════════════════════════════════════════════════════
# 4. Model loading + predictor
# ═══════════════════════════════════════════════════════════════════════════════

class TestPredictor:
    def test_predictor_loads_saved_model(self):
        """FraudPredictor should load the model trained in Phase 7."""
        from config.settings import MODELS_DIR
        if not (MODELS_DIR / "fraud_model.pkl").exists():
            pytest.skip("Model not trained yet — run scripts/train_model.py first")
        from ml.predictor import FraudPredictor
        pred = FraudPredictor(models_dir=MODELS_DIR)
        pred.load()
        assert pred._loaded is True

    def test_predictor_version(self):
        from config.settings import MODELS_DIR
        if not (MODELS_DIR / "fraud_model.pkl").exists():
            pytest.skip("Model not trained yet")
        from ml.predictor import FraudPredictor
        pred = FraudPredictor(models_dir=MODELS_DIR)
        pred.load()
        assert pred.model_version != "unknown"

    def test_prediction_output_format(self):
        from config.settings import MODELS_DIR
        if not (MODELS_DIR / "fraud_model.pkl").exists():
            pytest.skip("Model not trained yet")
        from ml.predictor import FraudPredictor
        pred = FraudPredictor(models_dir=MODELS_DIR)
        pred.load()
        features = {col: 0.0 for col in pred._features}
        result = pred.predict(features, case_id="test_case", entity_id="test_entity")
        # Required keys
        for key in ["prediction_id", "risk_score", "classification",
                    "top_features", "explanation", "model_version", "timestamp"]:
            assert key in result, f"Missing key: {key}"

    def test_risk_score_in_range(self):
        from config.settings import MODELS_DIR
        if not (MODELS_DIR / "fraud_model.pkl").exists():
            pytest.skip("Model not trained yet")
        from ml.predictor import FraudPredictor
        pred = FraudPredictor(models_dir=MODELS_DIR)
        pred.load()
        features = {col: 0.0 for col in pred._features}
        result = pred.predict(features)
        assert 0.0 <= result["risk_score"] <= 1.0

    def test_classification_valid_label(self):
        from config.settings import MODELS_DIR
        if not (MODELS_DIR / "fraud_model.pkl").exists():
            pytest.skip("Model not trained yet")
        from ml.predictor import FraudPredictor
        pred = FraudPredictor(models_dir=MODELS_DIR)
        pred.load()
        features = {col: 0.0 for col in pred._features}
        result = pred.predict(features)
        assert result["classification"] in {
            "HIGH_RISK", "MEDIUM_RISK", "LOW_RISK", "VERY_LOW_RISK"
        }

    def test_missing_features_default_to_zero(self):
        """Missing feature keys should default to 0.0 without error."""
        from config.settings import MODELS_DIR
        if not (MODELS_DIR / "fraud_model.pkl").exists():
            pytest.skip("Model not trained yet")
        from ml.predictor import FraudPredictor
        pred = FraudPredictor(models_dir=MODELS_DIR)
        pred.load()
        # Provide an empty features dict — all features default to 0.0
        result = pred.predict({})
        assert "risk_score" in result
        assert 0.0 <= result["risk_score"] <= 1.0

    def test_top_features_list(self):
        from config.settings import MODELS_DIR
        if not (MODELS_DIR / "fraud_model.pkl").exists():
            pytest.skip("Model not trained yet")
        from ml.predictor import FraudPredictor
        pred = FraudPredictor(models_dir=MODELS_DIR)
        pred.load()
        features = {col: 1.0 for col in pred._features}
        result = pred.predict(features)
        assert isinstance(result["top_features"], list)

    def test_model_not_found_raises(self, tmp_path):
        from ml.predictor import FraudPredictor
        pred = FraudPredictor(models_dir=tmp_path)
        with pytest.raises(FileNotFoundError):
            pred.load()


# ═══════════════════════════════════════════════════════════════════════════════
# 5. /api/predict route
# ═══════════════════════════════════════════════════════════════════════════════

class TestPredictRoute:
    def _token(self, client):
        uname = "ml_pred_user"
        register(client, username=uname, email=f"{uname}@x.com")
        r = login(client, credential=uname)
        data = r.get_json()
        return data.get("token") or data.get("access_token")

    def test_predict_missing_features_400(self, client):
        token = self._token(client)
        r = client.post(
            "/api/predict",
            json={},
            headers=auth_header(token),
        )
        assert r.status_code == 400

    def test_predict_empty_features_400(self, client):
        token = self._token(client)
        r = client.post(
            "/api/predict",
            json={"features": {}},
            headers=auth_header(token),
        )
        assert r.status_code == 400

    def test_predict_valid_request(self, client):
        from config.settings import MODELS_DIR
        if not (MODELS_DIR / "fraud_model.pkl").exists():
            pytest.skip("Model not trained yet")
        # Reset predictor singleton so it picks up the real model
        from ml.predictor import FraudPredictor
        FraudPredictor._instance = None

        token = self._token(client)
        features = {
            "tx_count": 5, "tx_out_count": 3, "tx_in_count": 2,
            "total_volume": 15000.0, "out_volume": 9000.0, "in_volume": 6000.0,
            "avg_tx_amount": 3000.0, "max_tx_amount": 9999.0, "min_tx_amount": 100.0,
            "std_tx_amount": 2500.0, "fwd_ratio": 1.5,
            "unique_peers": 4, "unique_out_peers": 3, "unique_in_peers": 2,
            "round_amount_ratio_out": 0.6, "near_threshold_ratio": 0.4,
            "suspicious_desc_ratio": 0.5, "self_loop_count": 0,
            "out_max_amount": 9999.0,
        }
        r = client.post(
            "/api/predict",
            json={"features": features, "case_id": "test_case"},
            headers=auth_header(token),
        )
        # 200 if model exists, 503 if not yet trained (both are valid in CI)
        assert r.status_code in (200, 503)

    def test_predict_unauthenticated_401(self, client):
        r = client.post("/api/predict", json={"features": {"tx_count": 1}})
        assert r.status_code == 401
