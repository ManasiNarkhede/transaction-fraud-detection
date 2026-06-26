"""Unit tests for ML model training and evaluation."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from sklearn.ensemble import IsolationForest
from xgboost import XGBClassifier

from ml.config import RANDOM_SEED
from ml.evaluate import evaluate_model, find_optimal_threshold
from ml.train import generate_synthetic_data, train_isolation_forest, train_xgboost
from ml.utils import load_artifact, save_artifact


# --------------------------------------------------------------------------- #
# Fixtures
# --------------------------------------------------------------------------- #


@pytest.fixture
def small_dataset() -> tuple[pd.DataFrame, pd.Series]:
    """Small synthetic dataset for fast tests."""
    rng = np.random.default_rng(RANDOM_SEED)
    n = 200
    n_fraud = 20

    df = pd.DataFrame(
        {
            "amount": np.concatenate([
                rng.lognormal(3.5, 1.0, n - n_fraud),
                rng.lognormal(3.5, 1.0, n_fraud) * 5,
            ]),
            "tx_count_24h": rng.integers(0, 10, size=n),
            "device_trust_score": rng.random(n),
            "hour_of_day": rng.integers(0, 24, size=n),
            "is_weekend": rng.integers(0, 2, size=n),
        }
    )
    y = pd.Series([0] * (n - n_fraud) + [1] * n_fraud)
    # Shuffle
    idx = rng.permutation(n)
    return df.iloc[idx].reset_index(drop=True), y.iloc[idx].reset_index(drop=True)


@pytest.fixture
def trained_models(
    small_dataset: tuple[pd.DataFrame, pd.Series],
) -> tuple[Any, Any, np.ndarray, np.ndarray]:
    """Train both models on the small dataset."""
    X, y = small_dataset
    X_vals = X.values
    y_vals = y.values

    iso = train_isolation_forest(X_vals, contamination=0.1)
    xgb = train_xgboost(X_vals, y_vals, X_vals, y_vals)
    return iso, xgb, X_vals, y_vals


# --------------------------------------------------------------------------- #
# Synthetic data generation
# --------------------------------------------------------------------------- #


def test_generate_synthetic_data_shape() -> None:
    """Synthetic data should have the expected number of rows."""
    df = generate_synthetic_data(n_samples=500, fraud_rate=0.05)
    assert len(df) == 500
    assert "decision" in df.columns
    assert "amount" in df.columns


def test_generate_synthetic_data_fraud_rate() -> None:
    """Synthetic data should have approximately the requested fraud rate."""
    df = generate_synthetic_data(n_samples=1000, fraud_rate=0.10)
    fraud_rate = (df["decision"] == "block").mean()
    assert 0.05 <= fraud_rate <= 0.15


# --------------------------------------------------------------------------- #
# Model training
# --------------------------------------------------------------------------- #


def test_train_isolation_forest(small_dataset: tuple[pd.DataFrame, pd.Series]) -> None:
    """Isolation Forest should train and have decision_function."""
    X, _ = small_dataset
    model = train_isolation_forest(X.values, contamination=0.1)
    assert isinstance(model, IsolationForest)
    assert hasattr(model, "decision_function")
    scores = model.decision_function(X.values)
    assert len(scores) == len(X)


def test_train_xgboost(small_dataset: tuple[pd.DataFrame, pd.Series]) -> None:
    """XGBoost should train and have predict_proba."""
    X, y = small_dataset
    model = train_xgboost(X.values, y.values, X.values, y.values)
    assert isinstance(model, XGBClassifier)
    assert hasattr(model, "predict_proba")
    probs = model.predict_proba(X.values)
    assert probs.shape == (len(X), 2)


# --------------------------------------------------------------------------- #
# Model saving / loading
# --------------------------------------------------------------------------- #


def test_save_and_load_artifact(tmp_path: Path) -> None:
    """Artifacts should round-trip through save/load."""
    path = tmp_path / "test_model.pkl"
    model = IsolationForest(n_estimators=10, random_state=42)
    model.fit(np.random.randn(50, 5))

    save_artifact(model, path)
    loaded = load_artifact(path)

    assert isinstance(loaded, IsolationForest)
    assert loaded.n_estimators == 10


# --------------------------------------------------------------------------- #
# Threshold optimization
# --------------------------------------------------------------------------- #


def test_find_optimal_threshold_basic() -> None:
    """Optimal threshold should be between 0 and 1."""
    y_true = np.array([0, 0, 0, 0, 1, 1, 1, 1])
    y_scores = np.array([0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8])
    threshold = find_optimal_threshold(y_true, y_scores)
    assert 0.0 < threshold < 1.0


def test_find_optimal_threshold_perfect_separation() -> None:
    """With perfect separation, threshold should separate classes."""
    y_true = np.array([0, 0, 1, 1])
    y_scores = np.array([0.1, 0.2, 0.8, 0.9])
    threshold = find_optimal_threshold(y_true, y_scores)
    assert 0.2 < threshold <= 0.8


# --------------------------------------------------------------------------- #
# Evaluation
# --------------------------------------------------------------------------- #


def test_evaluate_model_xgboost(trained_models: tuple) -> None:
    """XGBoost evaluation should return expected metrics."""
    _, xgb, X_test, y_test = trained_models
    metrics = evaluate_model(xgb, X_test, y_test, "XGBoost Test")

    assert "auc_roc" in metrics
    assert "auc_pr" in metrics
    assert "precision" in metrics
    assert "recall" in metrics
    assert "f1_score" in metrics
    assert "confusion_matrix" in metrics
    assert 0.0 <= metrics["auc_roc"] <= 1.0


def test_evaluate_model_isolation_forest(trained_models: tuple) -> None:
    """Isolation Forest evaluation should return expected metrics."""
    iso, _, X_test, y_test = trained_models
    metrics = evaluate_model(iso, X_test, y_test, "Isolation Forest Test")

    assert "auc_roc" in metrics
    assert "auc_pr" in metrics
    assert "f1_score" in metrics
    assert 0.0 <= metrics["auc_roc"] <= 1.0


def test_evaluate_model_saves_plots(trained_models: tuple, tmp_path: Path) -> None:
    """Evaluation should save plot files."""
    _, xgb, X_test, y_test = trained_models
    reports_dir = tmp_path / "reports"
    evaluate_model(xgb, X_test, y_test, "TestModel", reports_dir=reports_dir)

    assert (reports_dir / "roc_curve_testmodel.png").exists()
    assert (reports_dir / "precision_recall_curve_testmodel.png").exists()
    assert (reports_dir / "confusion_matrix_testmodel.png").exists()


# --------------------------------------------------------------------------- #
# Integration: full pipeline on tiny data
# --------------------------------------------------------------------------- #


def test_full_pipeline_integration(tmp_path: Path) -> None:
    """End-to-end pipeline should run without errors on synthetic data."""
    from ml.feature_engineering import compute_features, create_labels, scale_features
    from ml.utils import split_data

    df = generate_synthetic_data(n_samples=500, fraud_rate=0.05)
    df = compute_features(df)
    df["is_fraud"] = create_labels(df)

    train_df, val_df, test_df = split_data(df, test_size=0.2, val_size=0.15)
    feature_cols = [c for c in df.columns if c not in {"id", "user_id", "decision", "is_fraud", "created_at", "status", "currency", "merchant_id", "device_id"}]

    X_train = train_df[feature_cols]
    X_val = val_df[feature_cols]
    X_test = test_df[feature_cols]
    y_train = train_df["is_fraud"].values
    y_val = val_df["is_fraud"].values
    y_test = test_df["is_fraud"].values

    X_train_s, X_val_s, X_test_s, scaler = scale_features(X_train, X_val, X_test)

    iso = train_isolation_forest(X_train_s, contamination=0.05)
    xgb = train_xgboost(X_train_s, y_train, X_val_s, y_val)

    iso_metrics = evaluate_model(iso, X_test_s, y_test, "ISO", reports_dir=tmp_path)
    xgb_metrics = evaluate_model(xgb, X_test_s, y_test, "XGB", reports_dir=tmp_path)

    assert iso_metrics["auc_roc"] >= 0.0
    assert xgb_metrics["auc_roc"] >= 0.0
