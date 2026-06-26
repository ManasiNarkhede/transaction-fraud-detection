"""Batch feature engineering for the fraud detection ML pipeline."""

from __future__ import annotations

import logging
from typing import Any

import numpy as np
import pandas as pd
from sklearn.preprocessing import StandardScaler

from ml.config import FEATURE_COLUMNS, RANDOM_SEED

logger = logging.getLogger(__name__)


# --------------------------------------------------------------------------- #
# Feature computation
# --------------------------------------------------------------------------- #


def compute_features(df: pd.DataFrame) -> pd.DataFrame:
    """Compute all engineered features from raw transaction data.

    Expects the input DataFrame to contain at minimum:
        - ``user_id``
        - ``amount``
        - ``created_at`` (datetime)
        - ``merchant_id``
        - ``device_id`` or ``device_fingerprint``
        - ``currency`` (optional)

    Args:
        df: Raw transaction DataFrame.

    Returns:
        DataFrame with all engineered features.
    """
    df = df.copy()
    df["created_at"] = pd.to_datetime(df["created_at"])
    df = df.sort_values(["user_id", "created_at"]).reset_index(drop=True)

    # Amount features
    df["log_amount"] = np.log1p(df["amount"].astype(float))
    df["amount_zscore"] = _compute_amount_zscore(df)

    # Temporal features
    df["time_since_last_tx"] = _compute_time_since_last_tx(df)
    df["hour_of_day"] = df["created_at"].dt.hour
    df["day_of_week"] = df["created_at"].dt.weekday
    df["is_weekend"] = df["day_of_week"] >= 5

    # Velocity features
    df["tx_count_1h"] = _compute_rolling_count(df, hours=1)
    df["tx_count_24h"] = _compute_rolling_count(df, hours=24)
    df["tx_count_7d"] = _compute_rolling_count(df, hours=168)

    # Historical amount aggregations
    df["avg_amount_30d"] = _compute_rolling_amount_agg(df, days=30, agg="mean")
    df["max_amount_30d"] = _compute_rolling_amount_agg(df, days=30, agg="max")

    # Merchant / location diversity
    df["unique_merchants_24h"] = _compute_unique_entities(df, hours=24, col="merchant_id")
    df["unique_countries_24h"] = _compute_unique_entities(df, hours=24, col="currency")

    # Device features
    df["device_trust_score"] = _compute_device_trust_score(df)
    df["is_new_device"] = _compute_is_new_device(df)

    # Spec-named behavioral risk signals (mirror backend feature_queries.py).
    # failed_attempt_count: user's recent (24h) blocked attempts, excluding
    # the current transaction. merchant_risk_score: merchant's historical
    # block rate from PRIOR transactions only (current row excluded to avoid
    # leaking the current label into the feature).
    df["failed_attempt_count"] = _compute_failed_attempt_count(df, hours=24)
    df["merchant_risk_score"] = _compute_merchant_risk_score(df)

    # Ensure all expected feature columns exist, fill missing with 0
    for col in FEATURE_COLUMNS:
        if col not in df.columns:
            df[col] = 0

    # Convert boolean to int for ML models
    df["is_new_device"] = df["is_new_device"].astype(int)
    df["is_weekend"] = df["is_weekend"].astype(int)

    logger.info("Computed %d features for %d rows", len(FEATURE_COLUMNS), len(df))
    return df


# --------------------------------------------------------------------------- #
# Label creation
# --------------------------------------------------------------------------- #


def create_labels(df: pd.DataFrame, decision_col: str = "decision") -> pd.Series:
    """Create binary fraud labels from a decision column.

    Treats ``block`` and ``rejected`` as fraud (1), everything else as
    legitimate (0).

    Args:
        df: DataFrame containing the decision column.
        decision_col: Name of the decision column.

    Returns:
        Binary Series (0 = legitimate, 1 = fraud).
    """
    if decision_col not in df.columns:
        logger.warning("Decision column '%s' not found; returning all zeros", decision_col)
        return pd.Series(0, index=df.index)

    labels = df[decision_col].str.lower().isin(["block", "rejected"]).astype(int)
    labels.name = "is_fraud"
    fraud_rate = labels.mean()
    logger.info("Created labels: fraud_rate=%.4f", fraud_rate)
    return labels


# --------------------------------------------------------------------------- #
# Scaling
# --------------------------------------------------------------------------- #


def scale_features(
    X_train: pd.DataFrame,
    X_val: pd.DataFrame,
    X_test: pd.DataFrame,
    feature_cols: list[str] | None = None,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, StandardScaler]:
    """Fit a ``StandardScaler`` on training data and transform all splits.

    Args:
        X_train: Training features.
        X_val: Validation features.
        X_test: Test features.
        feature_cols: Subset of columns to scale. If ``None``, scales all
            numeric columns present in all three DataFrames.

    Returns:
        Scaled train, val, test arrays and the fitted scaler.
    """
    if feature_cols is None:
        feature_cols = list(
            set(X_train.columns) & set(X_val.columns) & set(X_test.columns)
        )

    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train[feature_cols])
    X_val_scaled = scaler.transform(X_val[feature_cols])
    X_test_scaled = scaler.transform(X_test[feature_cols])

    logger.info("Scaled %d features", len(feature_cols))
    return X_train_scaled, X_val_scaled, X_test_scaled, scaler


# --------------------------------------------------------------------------- #
# Internal helpers
# --------------------------------------------------------------------------- #


def _compute_amount_zscore(df: pd.DataFrame) -> pd.Series:
    """Z-score of amount within each user's history."""

    def zscore(group: pd.DataFrame) -> pd.Series:
        mean = group["amount"].expanding().mean().shift(1)
        std = group["amount"].expanding().std().shift(1)
        return (group["amount"] - mean) / std.replace(0, np.nan)

    return df.groupby("user_id", group_keys=False).apply(zscore).fillna(0.0)


def _compute_time_since_last_tx(df: pd.DataFrame) -> pd.Series:
    """Hours since the user's previous transaction."""
    return (
        df.groupby("user_id")["created_at"]
        .diff()
        .dt.total_seconds()
        .div(3600)
        .fillna(999.0)
    )


def _compute_rolling_count(df: pd.DataFrame, hours: int) -> pd.Series:
    """Count of transactions in the last *hours* per user (excluding current)."""
    counts = (
        df.groupby("user_id")
        .rolling(
            window=pd.Timedelta(hours=hours),
            on="created_at",
            closed="left",
        )
        .count()
        .iloc[:, 0]
        .fillna(0)
        .values
    )
    return pd.Series(counts, index=df.index, dtype=int)


def _compute_rolling_amount_agg(
    df: pd.DataFrame, days: int, agg: str
) -> pd.Series:
    """Rolling aggregation (mean or max) of amount over *days* per user."""
    window = pd.Timedelta(days=days)
    grouped = df.groupby("user_id").rolling(
        window=window,
        on="created_at",
        closed="left",
    )["amount"]

    if agg == "mean":
        result = grouped.mean()
    elif agg == "max":
        result = grouped.max()
    else:
        raise ValueError(f"Unsupported aggregation: {agg}")

    return pd.Series(result.fillna(0).values, index=df.index)


def _compute_unique_entities(
    df: pd.DataFrame, hours: int, col: str
) -> pd.Series:
    """Count of unique values in *col* over the last *hours* per user."""
    if col not in df.columns:
        return pd.Series(1, index=df.index)

    def unique_count(group: pd.DataFrame) -> pd.Series:
        counts = []
        for i in range(len(group)):
            current_time = group.iloc[i]["created_at"]
            window_start = current_time - pd.Timedelta(hours=hours)
            past = group.iloc[:i]
            in_window = past[past["created_at"] > window_start]
            counts.append(in_window[col].nunique())
        return pd.Series(counts, index=group.index)

    return (
        df.groupby("user_id", group_keys=False)
        .apply(unique_count)
        .fillna(0)
        .astype(int)
    )


def _compute_device_trust_score(df: pd.DataFrame) -> pd.Series:
    """Compute a simple device trust score (0-1) based on device history."""
    device_col = "device_id" if "device_id" in df.columns else "device_fingerprint"
    if device_col not in df.columns:
        return pd.Series(0.5, index=df.index)

    def trust_score(group: pd.DataFrame) -> pd.Series:
        device_col_local = "device_id" if "device_id" in group.columns else "device_fingerprint"
        seen = set()
        scores = []
        for _, row in group.iterrows():
            device = row[device_col_local]
            if device in seen:
                scores.append(1.0)
            else:
                scores.append(0.5)
                seen.add(device)
        return pd.Series(scores, index=group.index)

    return df.groupby("user_id", group_keys=False).apply(trust_score)


def _compute_is_new_device(df: pd.DataFrame) -> pd.Series:
    """Boolean: is this the first time we've seen this device for the user?"""
    device_col = "device_id" if "device_id" in df.columns else "device_fingerprint"
    if device_col not in df.columns:
        return pd.Series(True, index=df.index)

    def is_new(group: pd.DataFrame) -> pd.Series:
        device_col_local = "device_id" if "device_id" in group.columns else "device_fingerprint"
        seen = set()
        results = []
        for _, row in group.iterrows():
            device = row[device_col_local]
            results.append(device not in seen)
            seen.add(device)
        return pd.Series(results, index=group.index)

    return df.groupby("user_id", group_keys=False).apply(is_new)


def _blocked_indicator(df: pd.DataFrame) -> pd.Series:
    """Boolean Series marking transactions that were blocked attempts.

    Mirrors the backend's notion of a "failed/blocked attempt". The backend
    keys off ``status == "block"`` (the decision engine sets it). The training
    data marks blocks via the ``decision`` column (synthetic generator emits
    decision="block"; the Postgres export joins fraud_decision_audits.decision).
    We treat either signal as a block so the feature matches the backend whether
    the source is live transactions or the training export.
    """
    blocked = pd.Series(False, index=df.index)
    if "status" in df.columns:
        blocked = blocked | df["status"].astype(str).str.lower().eq("block")
    if "decision" in df.columns:
        blocked = blocked | df["decision"].astype(str).str.lower().isin(["block", "rejected"])
    return blocked


def _compute_failed_attempt_count(df: pd.DataFrame, hours: int = 24) -> pd.Series:
    """Count of the user's blocked attempts in the last *hours* (excl. current).

    Mirrors backend ``get_failed_attempt_count`` (count of the user's blocked
    transactions in a rolling window). Uses a left-closed window so the current
    transaction is excluded — at scoring time the backend counts only PRIOR
    attempts, so this avoids leaking the current label.
    """
    blocked = _blocked_indicator(df)
    work = pd.DataFrame(
        {"user_id": df["user_id"], "created_at": df["created_at"], "blocked": blocked.astype(float)}
    )
    counts = (
        work.groupby("user_id")
        .rolling(window=pd.Timedelta(hours=hours), on="created_at", closed="left")["blocked"]
        .sum()
        .fillna(0.0)
        .values
    )
    return pd.Series(counts, index=df.index).astype(int)


def _compute_merchant_risk_score(df: pd.DataFrame) -> pd.Series:
    """Merchant's historical block rate from PRIOR transactions only.

    Mirrors backend ``get_merchant_risk_score`` = blocked_count / total_count
    for the merchant, clamped to [0, 1]. Computed as an expanding mean of the
    blocked indicator per merchant, shifted by one so the current transaction
    is excluded (neutral 0.0 for the merchant's first-ever transaction). The
    shift prevents the current row's own block status — which determines the
    fraud label — from leaking into its feature.
    """
    if "merchant_id" not in df.columns:
        return pd.Series(0.0, index=df.index)

    blocked = _blocked_indicator(df).astype(float)
    work = pd.DataFrame(
        {"merchant_id": df["merchant_id"], "created_at": df["created_at"], "blocked": blocked}
    ).sort_values(["merchant_id", "created_at"])

    rate = (
        work.groupby("merchant_id")["blocked"]
        .apply(lambda s: s.expanding().mean().shift(1))
        .reset_index(level=0, drop=True)
    )
    rate = rate.reindex(df.index).fillna(0.0).clip(0.0, 1.0)
    return rate

