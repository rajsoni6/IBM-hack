"""
ml/features.py

Account-level feature engineering from the 50K+ transaction dataset.

All features are derived only from information that would be available at
prediction time (no target leakage).  The `embedding` column (768-dim) and
`risk_score` from accounts (already a derived score) are intentionally
excluded to avoid leakage.

Feature groups
--------------
Transaction statistics   : counts, volumes, velocity, round amounts
Behavioural              : description mix, peer diversity, self-loop ratio
Graph (lightweight)      : degree in/out, unique peers
"""

from __future__ import annotations

import csv
from pathlib import Path
from collections import defaultdict
from typing import Optional

import numpy as np
import pandas as pd


# ── Dataset paths (overridable for tests) ─────────────────────────────────────
_HERE        = Path(__file__).resolve().parent                 # backend/ml/
_PROJECT     = _HERE.parent.parent                             # cyber-fraud-network-analyzer/
_WORKSPACE   = _PROJECT.parent.parent                          # repo root
SRC_DATA_DIR = _WORKSPACE / "src" / "data"

TRANSACTIONS_FILES = [
    SRC_DATA_DIR / "transactions" / "transactions_0_0.csv",
    SRC_DATA_DIR / "transactions" / "transactions_1_0.csv",
]
FRAUD_TX_FILE      = SRC_DATA_DIR / "fraud" / "transactions_fraud.csv"
FRAUD_CASES_FILE   = SRC_DATA_DIR / "fraud" / "fraud_cases.csv"
ACCOUNTS_FILES     = [
    SRC_DATA_DIR / "accounts" / "accounts_0_0.csv",
    SRC_DATA_DIR / "accounts" / "accounts_1_0.csv",
]

# Description groups (normal vs suspicious)
SUSPICIOUS_DESCRIPTIONS = {
    "dormant account sudden activity",
    "offshore transfer to tax haven",
    "layered transfer via intermediary",
    "high-value cross-border wire",
    "round-trip transaction",
    "shell company payment",
    "structuring deposit below threshold",
    "rapid movement of funds between accounts",
}


def load_transactions(
    tx_files: Optional[list[Path]] = None,
    fraud_tx_file: Optional[Path] = None,
    limit_per_file: Optional[int] = None,
) -> pd.DataFrame:
    """
    Load normal and fraud transactions into a single DataFrame.
    Adds  is_fraud_tx  column (0 = normal, 1 = fraud).
    Drops the `embedding` column (768-dim, not used in tabular ML).
    """
    tx_files     = tx_files     or TRANSACTIONS_FILES
    fraud_tx_file = fraud_tx_file or FRAUD_TX_FILE

    dfs: list[pd.DataFrame] = []
    for path in tx_files:
        df = pd.read_csv(path, nrows=limit_per_file)
        df["is_fraud_tx"] = 0
        dfs.append(df)

    fraud_df = pd.read_csv(fraud_tx_file)
    fraud_df["is_fraud_tx"] = 1
    dfs.append(fraud_df)

    combined = pd.concat(dfs, ignore_index=True)

    # Drop the embedding column — too wide and not needed for tabular features
    if "embedding" in combined.columns:
        combined = combined.drop(columns=["embedding"])

    # Parse timestamp; fill parse failures with NaT
    combined["timestamp"] = pd.to_datetime(combined["timestamp"], errors="coerce")
    combined["amount"]    = pd.to_numeric(combined["amount"], errors="coerce")
    return combined


def load_fraud_labels(
    fraud_cases_file: Optional[Path] = None,
    fraud_tx_file: Optional[Path] = None,
) -> set[str]:
    """
    Return the set of account_ids that are involved in any fraud.
    Union of: fraud_cases.csv involved_accounts + fraud transactions src/dst.
    """
    fraud_cases_file = fraud_cases_file or FRAUD_CASES_FILE
    fraud_tx_file    = fraud_tx_file    or FRAUD_TX_FILE

    fraud_accounts: set[str] = set()

    with open(fraud_cases_file, encoding="utf-8") as f:
        for row in csv.DictReader(f):
            for acc in row["involved_accounts"].split("|"):
                fraud_accounts.add(acc.strip())

    with open(fraud_tx_file, encoding="utf-8") as f:
        for row in csv.DictReader(f):
            fraud_accounts.add(row["src_id"].strip())
            fraud_accounts.add(row["dst_id"].strip())

    return fraud_accounts


def build_account_features(
    tx_df: pd.DataFrame,
    fraud_account_ids: set[str],
    accounts_files: Optional[list[Path]] = None,
) -> pd.DataFrame:
    """
    Aggregate transaction-level data to account-level features.
    Returns a DataFrame with one row per account and target column `is_fraud`.

    Features derived (no target leakage):
    - tx_count              total transaction count (sent + received)
    - tx_out_count          sent transactions
    - tx_in_count           received transactions
    - total_volume          sum of amounts sent + received
    - out_volume            sum of amounts sent
    - in_volume             sum of amounts received
    - avg_tx_amount         mean transaction amount
    - max_tx_amount         maximum transaction amount
    - min_tx_amount         minimum transaction amount
    - std_tx_amount         std dev of transaction amounts
    - fwd_ratio             out_volume / (in_volume + 1)
    - unique_peers          unique accounts transacted with
    - unique_out_peers      unique destination accounts
    - unique_in_peers       unique source accounts
    - round_amount_ratio    fraction of txns with integer amounts
    - near_threshold_ratio  fraction of txns with amount in [9000, 10000]
    - suspicious_desc_ratio fraction of txns with suspicious description
    - self_loop_count       transactions where src == dst
    """
    accounts_files = accounts_files or ACCOUNTS_FILES

    # All known account IDs
    all_accounts: set[str] = set()
    for path in accounts_files:
        df_acc = pd.read_csv(path, usecols=["account_id"])
        all_accounts.update(df_acc["account_id"].tolist())

    # Also add any account seen in transactions
    all_accounts.update(tx_df["src_id"].dropna().tolist())
    all_accounts.update(tx_df["dst_id"].dropna().tolist())

    # --- per-account aggregations ---
    out_tx = tx_df.groupby("src_id")
    in_tx  = tx_df.groupby("dst_id")

    out_stats = out_tx["amount"].agg(
        out_volume="sum",
        tx_out_count="count",
        out_max_amount="max",
        out_std_amount="std",
    ).fillna(0)

    in_stats = in_tx["amount"].agg(
        in_volume="sum",
        tx_in_count="count",
    ).fillna(0)

    out_peers = out_tx["dst_id"].nunique().rename("unique_out_peers")
    in_peers  = in_tx["src_id"].nunique().rename("unique_in_peers")

    # Round-amount ratio
    tx_df_copy = tx_df.copy()
    tx_df_copy["is_round"] = (tx_df_copy["amount"] % 1 == 0).astype(int)
    tx_df_copy["is_near_threshold"] = (
        (tx_df_copy["amount"] >= 9000) & (tx_df_copy["amount"] <= 10000)
    ).astype(int)
    tx_df_copy["is_suspicious_desc"] = tx_df_copy["description"].str.lower().isin(
        SUSPICIOUS_DESCRIPTIONS
    ).astype(int)
    tx_df_copy["is_self_loop"] = (tx_df_copy["src_id"] == tx_df_copy["dst_id"]).astype(int)

    round_out  = tx_df_copy.groupby("src_id")["is_round"].mean().rename("round_amount_ratio_out")
    thresh_out = tx_df_copy.groupby("src_id")["is_near_threshold"].mean().rename("near_threshold_ratio")
    susp_out   = tx_df_copy.groupby("src_id")["is_suspicious_desc"].mean().rename("suspicious_desc_ratio")
    self_loop  = tx_df_copy.groupby("src_id")["is_self_loop"].sum().rename("self_loop_count")

    avg_amount = tx_df.groupby("src_id")["amount"].mean().rename("avg_tx_amount")
    min_amount = tx_df.groupby("src_id")["amount"].min().rename("min_tx_amount")
    max_amount = tx_df.groupby("src_id")["amount"].max().rename("max_tx_amount")

    # Combine
    feat = (
        pd.DataFrame(index=sorted(all_accounts))
        .join(out_stats, how="left")
        .join(in_stats, how="left")
        .join(out_peers, how="left")
        .join(in_peers, how="left")
        .join(round_out, how="left")
        .join(thresh_out, how="left")
        .join(susp_out, how="left")
        .join(self_loop, how="left")
        .join(avg_amount, how="left")
        .join(min_amount, how="left")
        .join(max_amount, how="left")
        .fillna(0)
    )
    feat.index.name = "account_id"
    feat = feat.reset_index()

    # Derived features
    feat["tx_count"]       = feat["tx_out_count"] + feat["tx_in_count"]
    feat["total_volume"]   = feat["out_volume"]   + feat["in_volume"]
    feat["fwd_ratio"]      = feat["out_volume"] / (feat["in_volume"] + 1.0)
    feat["unique_peers"]   = feat["unique_out_peers"] + feat["unique_in_peers"]

    # Combine std (missing for accounts with only 1 tx → fill 0)
    feat["std_tx_amount"]  = feat["out_std_amount"].fillna(0)
    feat = feat.drop(columns=["out_std_amount"], errors="ignore")

    # Target label
    feat["is_fraud"] = feat["account_id"].isin(fraud_account_ids).astype(int)

    return feat


FEATURE_COLUMNS = [
    "tx_count", "tx_out_count", "tx_in_count",
    "total_volume", "out_volume", "in_volume",
    "avg_tx_amount", "max_tx_amount", "min_tx_amount", "std_tx_amount",
    "fwd_ratio",
    "unique_peers", "unique_out_peers", "unique_in_peers",
    "round_amount_ratio_out", "near_threshold_ratio",
    "suspicious_desc_ratio", "self_loop_count",
    "out_max_amount",
]
TARGET_COLUMN = "is_fraud"
