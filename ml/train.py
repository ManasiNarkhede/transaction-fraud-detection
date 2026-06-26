"""Main training script for the fraud detection ML pipeline."""

from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import xgboost as xgb
from sklearn.ensemble import IsolationForest
from xgboost import XGBClassifier

from ml.config import (
    EVALUATION_REPORT_PATH,
    FEATURE_COLUMNS,
    FEATURE_NAMES_PATH,
    ISO_FOREST_CONTAMINATION,
    ISO_FOREST_MAX_SAMPLES,
    ISO_FOREST_MODEL_PATH,
    ISO_FOREST_N_ESTIMATORS,
    ISO_FOREST_RANDOM_STATE,
    MODEL_METADATA_PATH,
    RANDOM_SEED,
    SCALER_PATH,
    SYNTHETIC_DATA_PATH,
    SYNTHETIC_FRAUD_RATE,
    SYNTHETIC_N_SAMPLES,
    TEST_SIZE,
    VAL_SIZE,
    XGB_EARLY_STOPPING_ROUNDS,
    XGB_EVAL_METRIC,
    XGB_LEARNING_RATE,
    XGB_MAX_DEPTH,
    XGB_N_ESTIMATORS,
    XGB_RANDOM_STATE,
    XGBOOST_MODEL_PATH,
)
from ml.evaluate import evaluate_model
from ml.feature_engineering import compute_features, create_labels, scale_features
from ml.utils import load_data_from_postgres, save_artifact, save_json, split_data

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)


# --------------------------------------------------------------------------- #
# SQL queries
# --------------------------------------------------------------------------- #

TRANSACTIONS_QUERY = """
SELECT
    t.id,
    t.user_id,
    t.amount,
    t.currency,
    t.merchant_id,
    t.device_fingerprint AS device_id,
    t.status,
    t.created_at,
    fda.decision
FROM transactions t
LEFT JOIN fraud_decision_audits fda ON t.id = fda.transaction_id
ORDER BY t.created_at;
"""


# --------------------------------------------------------------------------- #
# Synthetic data generation
# --------------------------------------------------------------------------- #


def generate_synthetic_data(
    n_samples: int = SYNTHETIC_N_SAMPLES,
    fraud_rate: float = SYNTHETIC_FRAUD_RATE,
    random_state: int = RANDOM_SEED,
) -> pd.DataFrame:
    """Generate a synthetic transaction dataset with realistic distributions.

    Args:
        n_samples: Total number of transactions to generate.
        fraud_rate: Fraction of transactions that are fraudulent.
        random_state: Random seed for reproducibility.

    Returns:
        DataFrame with raw transaction columns.
    """
    rng = np.random.default_rng(random_state)
    n_fraud = int(n_samples * fraud_rate)
    n_legit = n_samples - n_fraud

    n_users = 500
    user_ids = [f"user_{i:04d}" for i in range(n_users)]
    merchant_ids = [f"merchant_{i:03d}" for i in range(100)]
    device_ids = [f"device_{i:03d}" for i in range(200)]
    currencies = ["USD", "EUR", "GBP", "CAD"]

    def _make_transactions(n: int, is_fraud: bool) -> pd.DataFrame:
        users = rng.choice(user_ids, size=n)
        base_amounts = rng.lognormal(mean=3.5, sigma=1.2, size=n)
        if is_fraud:
            # Fraudulent transactions tend to be larger or very small
            amounts = base_amounts * rng.choice([5.0, 0.1], size=n)
            decisions = ["block"] * n
        else:
            amounts = base_amounts
            decisions = ["approve"] * n

        # Generate timestamps over the last 60 days
        now = datetime.now(timezone.utc)
        deltas = rng.integers(0, 60 * 24 * 3600, size=n)
        timestamps = [now - pd.Timedelta(seconds=int(d)) for d in deltas]

        return pd.DataFrame(
            {
                "id": [f"tx_{i:08d}" for i in range(n)],
                "user_id": users,
                "amount": np.round(amounts, 2),
                "currency": rng.choice(currencies, size=n),
                "merchant_id": rng.choice(merchant_ids, size=n),
                "device_id": rng.choice(device_ids, size=n),
                "status": ["completed"] * n,
                "created_at": timestamps,
                "decision": decisions,
            }
        )

    legit_df = _make_transactions(n_legit, is_fraud=False)
    fraud_df = _make_transactions(n_fraud, is_fraud=True)
    df = pd.concat([legit_df, fraud_df], ignore_index=True)
    df = df.sample(frac=1, random_state=random_state).reset_index(drop=True)

    logger.info(
        "Generated synthetic data: %d rows (fraud=%d, legit=%d)",
        len(df),
        n_fraud,
        n_legit,
    )
    return df


# --------------------------------------------------------------------------- #
# Model training
# --------------------------------------------------------------------------- #


def train_isolation_forest(
    X_train: np.ndarray,
    contamination: float | str = ISO_FOREST_CONTAMINATION,
) -> IsolationForest:
    """Train an Isolation Forest for unsupervised anomaly detection.

    Args:
        X_train: Training feature matrix.
        contamination: Expected proportion of anomalies. Can be ``"auto"``
            or a float.

    Returns:
        Trained IsolationForest model.
    """
    model = IsolationForest(
        n_estimators=ISO_FOREST_N_ESTIMATORS,
        max_samples=ISO_FOREST_MAX_SAMPLES,
        contamination=contamination,
        random_state=ISO_FOREST_RANDOM_STATE,
        n_jobs=-1,
    )
    model.fit(X_train)
    logger.info("Trained Isolation Forest (contamination=%s)", contamination)
    return model


def train_xgboost(
    X_train: np.ndarray,
    y_train: np.ndarray,
    X_val: np.ndarray,
    y_val: np.ndarray,
    scale_pos_weight: float | None = None,
) -> XGBClassifier:
    """Train an XGBoost classifier with early stopping.

    Automatically computes ``scale_pos_weight`` based on class imbalance
    if not provided.

    Args:
        X_train: Training feature matrix.
        y_train: Training binary labels.
        X_val: Validation feature matrix.
        y_val: Validation binary labels.
        scale_pos_weight: Weight for positive class. If ``None``, computed
            from training data.

    Returns:
        Trained XGBClassifier.
    """
    if scale_pos_weight is None:
        fraud_count = int(y_train.sum())
        legit_count = int(len(y_train) - fraud_count)
        scale_pos_weight = legit_count / max(fraud_count, 1)

    model = XGBClassifier(
        max_depth=XGB_MAX_DEPTH,
        learning_rate=XGB_LEARNING_RATE,
        n_estimators=XGB_N_ESTIMATORS,
        eval_metric=XGB_EVAL_METRIC,
        scale_pos_weight=scale_pos_weight,
        random_state=XGB_RANDOM_STATE,
        n_jobs=-1,
        callbacks=[
            xgb.callback.EarlyStopping(
                rounds=XGB_EARLY_STOPPING_ROUNDS,
                save_best=True,
            )
        ],
    )

    model.fit(
        X_train,
        y_train,
        eval_set=[(X_val, y_val)],
        verbose=False,
    )

    best_iteration = model.best_iteration if hasattr(model, "best_iteration") else XGB_N_ESTIMATORS
    logger.info(
        "Trained XGBoost (best_iteration=%d, scale_pos_weight=%.2f)",
        best_iteration,
        scale_pos_weight,
    )
    return model


# --------------------------------------------------------------------------- #
# Orchestration
# --------------------------------------------------------------------------- #


def main(use_synthetic: bool = False) -> dict[str, Any]:
    """Run the full training pipeline.

    Args:
        use_synthetic: If ``True``, generate and use synthetic data instead
            of querying PostgreSQL.

    Returns:
        Dictionary containing evaluation metrics for both models.
    """
    logger.info("=" * 60)
    logger.info("Fraud Detection ML Training Pipeline")
    logger.info("=" * 60)

    # ------------------------------------------------------------------ #
    # 1. Load data
    # ------------------------------------------------------------------ #

    if use_synthetic:
        logger.info("Using synthetic data")
        df = generate_synthetic_data()
        df.to_csv(SYNTHETIC_DATA_PATH, index=False)
    else:
        try:
            logger.info("Loading data from PostgreSQL")
            df = load_data_from_postgres(TRANSACTIONS_QUERY)
            if df.empty:
                logger.warning("No data returned from PostgreSQL; falling back to synthetic")
                df = generate_synthetic_data()
                df.to_csv(SYNTHETIC_DATA_PATH, index=False)
        except Exception as exc:
            logger.error("Failed to load from PostgreSQL: %s", exc)
            logger.info("Falling back to synthetic data")
            df = generate_synthetic_data()
            df.to_csv(SYNTHETIC_DATA_PATH, index=False)

    logger.info("Loaded %d transactions", len(df))

    # ------------------------------------------------------------------ #
    # 2. Engineer features
    # ------------------------------------------------------------------ #

    df = compute_features(df)

    # ------------------------------------------------------------------ #
    # 3. Create labels
    # ------------------------------------------------------------------ #

    df["is_fraud"] = create_labels(df, decision_col="decision")

    # ------------------------------------------------------------------ #
    # 4. Split data
    # ------------------------------------------------------------------ #

    train_df, val_df, test_df = split_data(
        df,
        test_size=TEST_SIZE,
        val_size=VAL_SIZE,
        random_state=RANDOM_SEED,
        stratify_col="is_fraud",
    )

    feature_cols = [c for c in FEATURE_COLUMNS if c in train_df.columns]
    X_train = train_df[feature_cols]
    X_val = val_df[feature_cols]
    X_test = test_df[feature_cols]
    y_train = train_df["is_fraud"].values
    y_val = val_df["is_fraud"].values
    y_test = test_df["is_fraud"].values

    logger.info(
        "Features: %s",
        ", ".join(feature_cols),
    )

    # ------------------------------------------------------------------ #
    # 5. Scale features
    # ------------------------------------------------------------------ #

    X_train_s, X_val_s, X_test_s, scaler = scale_features(X_train, X_val, X_test, feature_cols)
    save_artifact(scaler, SCALER_PATH)
    save_json({"features": feature_cols}, FEATURE_NAMES_PATH)

    # ------------------------------------------------------------------ #
    # 6. Train Isolation Forest
    # ------------------------------------------------------------------ #

    fraud_rate = float(y_train.mean())
    contamination = fraud_rate if fraud_rate > 0 else "auto"
    iso_forest = train_isolation_forest(X_train_s, contamination=contamination)
    save_artifact(iso_forest, ISO_FOREST_MODEL_PATH)

    # ------------------------------------------------------------------ #
    # 7. Train XGBoost
    # ------------------------------------------------------------------ #

    fraud_count = int(y_train.sum())
    legit_count = int(len(y_train) - fraud_count)
    scale_pos_weight = legit_count / max(fraud_count, 1)
    xgb_model = train_xgboost(
        X_train_s, y_train, X_val_s, y_val, scale_pos_weight=scale_pos_weight
    )
    save_artifact(xgb_model, XGBOOST_MODEL_PATH)

    # ------------------------------------------------------------------ #
    # 8. Evaluate models
    # ------------------------------------------------------------------ #

    iso_metrics = evaluate_model(iso_forest, X_test_s, y_test, "Isolation Forest")
    xgb_metrics = evaluate_model(xgb_model, X_test_s, y_test, "XGBoost")

    report = {
        "training_date": datetime.now(timezone.utc).isoformat(),
        "n_train": int(len(y_train)),
        "n_val": int(len(y_val)),
        "n_test": int(len(y_test)),
        "fraud_rate": round(float(y_test.mean()), 4),
        "features": feature_cols,
        "models": {
            "isolation_forest": iso_metrics,
            "xgboost": xgb_metrics,
        },
    }

    save_json(report, EVALUATION_REPORT_PATH)
    logger.info("Evaluation report saved to %s", EVALUATION_REPORT_PATH)

    # ------------------------------------------------------------------ #
    # 9. Save metadata
    # ------------------------------------------------------------------ #

    metadata = {
        "training_date": datetime.now(timezone.utc).isoformat(),
        "random_seed": RANDOM_SEED,
        "n_samples": int(len(df)),
        "n_features": len(feature_cols),
        "feature_columns": feature_cols,
        "test_size": TEST_SIZE,
        "val_size": VAL_SIZE,
        "isolation_forest": {
            "n_estimators": ISO_FOREST_N_ESTIMATORS,
            "contamination": contamination if isinstance(contamination, str) else round(contamination, 4),
            "path": str(ISO_FOREST_MODEL_PATH),
        },
        "xgboost": {
            "max_depth": XGB_MAX_DEPTH,
            "learning_rate": XGB_LEARNING_RATE,
            "n_estimators": XGB_N_ESTIMATORS,
            "early_stopping_rounds": XGB_EARLY_STOPPING_ROUNDS,
            "scale_pos_weight": round(float(legit_count / max(fraud_count, 1)), 4),
            "path": str(XGBOOST_MODEL_PATH),
        },
    }
    save_json(metadata, MODEL_METADATA_PATH)
    logger.info("Model metadata saved to %s", MODEL_METADATA_PATH)

    logger.info("=" * 60)
    logger.info("Training complete!")
    logger.info("Isolation Forest AUC-ROC: %.4f", iso_metrics["auc_roc"])
    logger.info("XGBoost AUC-ROC: %.4f", xgb_metrics["auc_roc"])
    logger.info("=" * 60)

    return report


# --------------------------------------------------------------------------- #
# CLI entry point
# --------------------------------------------------------------------------- #


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Fraud Detection ML Training Pipeline")
    parser.add_argument(
        "--synthetic",
        action="store_true",
        help="Use synthetic data instead of PostgreSQL",
    )
    args = parser.parse_args()
    main(use_synthetic=args.synthetic)
