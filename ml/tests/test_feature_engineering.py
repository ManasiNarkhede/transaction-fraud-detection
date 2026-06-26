"""Unit tests for ML feature engineering module."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
from sklearn.preprocessing import StandardScaler

from ml.feature_engineering import (
    compute_features,
    create_labels,
    scale_features,
)


# --------------------------------------------------------------------------- #
# Fixtures
# --------------------------------------------------------------------------- #


@pytest.fixture
def sample_raw_df() -> pd.DataFrame:
    """Minimal raw transaction DataFrame."""
    return pd.DataFrame(
        {
            "id": ["tx_1", "tx_2", "tx_3", "tx_4"],
            "user_id": ["u1", "u1", "u2", "u2"],
            "amount": [100.0, 200.0, 50.0, 75.0],
            "currency": ["USD", "USD", "EUR", "EUR"],
            "merchant_id": ["m1", "m2", "m1", "m3"],
            "device_id": ["d1", "d1", "d2", "d2"],
            "status": ["completed"] * 4,
            "created_at": pd.to_datetime(
                [
                    "2024-01-01 10:00:00",
                    "2024-01-01 11:00:00",
                    "2024-01-01 09:00:00",
                    "2024-01-01 12:00:00",
                ]
            ),
            "decision": ["approve", "block", "approve", "approve"],
        }
    )


# --------------------------------------------------------------------------- #
# Feature computation
# --------------------------------------------------------------------------- #


def test_compute_features_returns_expected_columns(sample_raw_df: pd.DataFrame) -> None:
    """All expected feature columns should be present after computation."""
    df = compute_features(sample_raw_df)
    expected = [
        "amount",
        "log_amount",
        "amount_zscore",
        "time_since_last_tx",
        "tx_count_1h",
        "tx_count_24h",
        "tx_count_7d",
        "avg_amount_30d",
        "max_amount_30d",
        "unique_merchants_24h",
        "unique_countries_24h",
        "device_trust_score",
        "is_new_device",
        "hour_of_day",
        "day_of_week",
        "is_weekend",
        "failed_attempt_count",
        "merchant_risk_score",
    ]
    for col in expected:
        assert col in df.columns, f"Missing column: {col}"


def test_compute_features_log_amount(sample_raw_df: pd.DataFrame) -> None:
    """log_amount should be log1p of amount."""
    df = compute_features(sample_raw_df)
    expected = np.log1p(sample_raw_df["amount"])
    pd.testing.assert_series_equal(
        df["log_amount"].reset_index(drop=True),
        expected.reset_index(drop=True),
        check_names=False,
    )


def test_compute_features_hour_of_day(sample_raw_df: pd.DataFrame) -> None:
    """hour_of_day should match transaction timestamps."""
    df = compute_features(sample_raw_df)
    expected = sample_raw_df["created_at"].dt.hour.values
    np.testing.assert_array_equal(df["hour_of_day"].values, expected)


def test_compute_features_day_of_week(sample_raw_df: pd.DataFrame) -> None:
    """day_of_week should match transaction timestamps."""
    df = compute_features(sample_raw_df)
    expected = sample_raw_df["created_at"].dt.weekday.values
    np.testing.assert_array_equal(df["day_of_week"].values, expected)


def test_compute_features_is_weekend(sample_raw_df: pd.DataFrame) -> None:
    """is_weekend should be 1 for Saturday/Sunday, 0 otherwise."""
    df = compute_features(sample_raw_df)
    # 2024-01-01 is Monday (weekday 0)
    assert df["is_weekend"].sum() == 0


def test_compute_features_time_since_last_tx(sample_raw_df: pd.DataFrame) -> None:
    """First transaction per user should have time_since_last_tx = 999.0."""
    df = compute_features(sample_raw_df)
    # u1 first tx at 10:00, second at 11:00 -> 1 hour
    u1_first = df[(df["user_id"] == "u1")].iloc[0]
    assert u1_first["time_since_last_tx"] == 999.0

    u1_second = df[(df["user_id"] == "u1")].iloc[1]
    assert u1_second["time_since_last_tx"] == 1.0


def test_compute_features_device_trust_score(sample_raw_df: pd.DataFrame) -> None:
    """device_trust_score should be 0.5 for first device, 1.0 for repeat."""
    df = compute_features(sample_raw_df)
    u1_scores = df[df["user_id"] == "u1"]["device_trust_score"].tolist()
    assert u1_scores == [0.5, 1.0]


def test_compute_features_is_new_device(sample_raw_df: pd.DataFrame) -> None:
    """is_new_device should be 1 for first device, 0 for repeat."""
    df = compute_features(sample_raw_df)
    u1_new = df[df["user_id"] == "u1"]["is_new_device"].tolist()
    assert u1_new == [1, 0]


def test_compute_features_no_missing_columns() -> None:
    """Missing optional columns should not raise errors."""
    df = pd.DataFrame(
        {
            "user_id": ["u1"],
            "amount": [100.0],
            "created_at": pd.to_datetime(["2024-01-01 10:00:00"]),
            "merchant_id": ["m1"],
        }
    )
    result = compute_features(df)
    assert "device_trust_score" in result.columns
    assert "is_new_device" in result.columns
    assert "unique_countries_24h" in result.columns


# --------------------------------------------------------------------------- #
# Label creation
# --------------------------------------------------------------------------- #


def test_create_labels_block_is_fraud() -> None:
    """'block' decisions should map to fraud (1)."""
    df = pd.DataFrame({"decision": ["approve", "block", "BLOCK", "rejected", "approve"]})
    labels = create_labels(df)
    expected = pd.Series([0, 1, 1, 1, 0], name="is_fraud")
    pd.testing.assert_series_equal(labels.reset_index(drop=True), expected)


def test_create_labels_missing_column() -> None:
    """Missing decision column should return all zeros."""
    df = pd.DataFrame({"amount": [100, 200]})
    labels = create_labels(df)
    assert labels.tolist() == [0, 0]


# --------------------------------------------------------------------------- #
# Scaling
# --------------------------------------------------------------------------- #


def test_scale_features_shapes() -> None:
    """Scaled outputs should have the same shape as inputs."""
    train = pd.DataFrame({"a": [1.0, 2.0, 3.0], "b": [10.0, 20.0, 30.0]})
    val = pd.DataFrame({"a": [4.0], "b": [40.0]})
    test = pd.DataFrame({"a": [5.0], "b": [50.0]})

    X_train_s, X_val_s, X_test_s, scaler = scale_features(train, val, test)

    assert X_train_s.shape == (3, 2)
    assert X_val_s.shape == (1, 2)
    assert X_test_s.shape == (1, 2)
    assert isinstance(scaler, StandardScaler)


def test_scale_features_zero_mean_on_train() -> None:
    """Training data should have approximately zero mean after scaling."""
    train = pd.DataFrame({"a": [1.0, 2.0, 3.0, 4.0, 5.0]})
    val = pd.DataFrame({"a": [6.0]})
    test = pd.DataFrame({"a": [7.0]})

    X_train_s, _, _, _ = scale_features(train, val, test)
    np.testing.assert_allclose(X_train_s.mean(), 0.0, atol=1e-10)
