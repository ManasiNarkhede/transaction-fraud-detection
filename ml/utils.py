"""Utility helpers for the ML training pipeline."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

import joblib
import pandas as pd
import psycopg2
from psycopg2.extensions import connection

from ml.config import DATABASE_URL

logger = logging.getLogger(__name__)


# --------------------------------------------------------------------------- #
# Database
# --------------------------------------------------------------------------- #


def get_db_connection() -> connection:
    """Create and return a PostgreSQL database connection."""
    return psycopg2.connect(DATABASE_URL)


def load_data_from_postgres(query: str) -> pd.DataFrame:
    """Execute a SQL query and return the result as a pandas DataFrame.

    Args:
        query: SQL query string to execute.

    Returns:
        DataFrame containing query results.
    """
    conn = get_db_connection()
    try:
        df = pd.read_sql_query(query, conn)
        logger.info("Loaded %d rows from PostgreSQL", len(df))
        return df
    finally:
        conn.close()


# --------------------------------------------------------------------------- #
# Data splitting
# --------------------------------------------------------------------------- #


def split_data(
    df: pd.DataFrame,
    test_size: float = 0.20,
    val_size: float = 0.15,
    random_state: int = 42,
    stratify_col: str | None = "is_fraud",
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Split a DataFrame into train/validation/test sets.

    The split is performed in two stages:
        1. Separate test set (``test_size`` fraction).
        2. Separate validation set from remaining train data
           (``val_size`` fraction of the *original* data).

    Args:
        df: Input DataFrame.
        test_size: Fraction of data to reserve for testing.
        val_size: Fraction of *original* data to reserve for validation.
        random_state: Random seed for reproducibility.
        stratify_col: Column name to stratify on (default ``is_fraud``).

    Returns:
        Three DataFrames: (train, val, test).
    """
    from sklearn.model_selection import train_test_split

    stratify = df[stratify_col] if stratify_col and stratify_col in df.columns else None

    # First split: train+val vs test
    train_val, test = train_test_split(
        df,
        test_size=test_size,
        random_state=random_state,
        stratify=stratify,
    )

    # Second split: train vs val
    # val_size is relative to original, so compute relative to train_val
    relative_val_size = val_size / (1 - test_size)
    stratify_train_val = (
        train_val[stratify_col]
        if stratify_col and stratify_col in train_val.columns
        else None
    )

    train, val = train_test_split(
        train_val,
        test_size=relative_val_size,
        random_state=random_state,
        stratify=stratify_train_val,
    )

    logger.info(
        "Data split: train=%d, val=%d, test=%d",
        len(train),
        len(val),
        len(test),
    )
    return train, val, test


# --------------------------------------------------------------------------- #
# Artifact I/O
# --------------------------------------------------------------------------- #


def save_artifact(obj: Any, path: Path) -> None:
    """Save a Python object to disk using ``joblib``.

    Args:
        obj: Object to serialize.
        path: Destination file path.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(obj, path)
    logger.info("Saved artifact to %s", path)


def load_artifact(path: Path) -> Any:
    """Load a Python object from disk using ``joblib``.

    Args:
        path: Source file path.

    Returns:
        Deserialized object.
    """
    obj = joblib.load(path)
    logger.info("Loaded artifact from %s", path)
    return obj


# --------------------------------------------------------------------------- #
# JSON helpers
# --------------------------------------------------------------------------- #


def save_json(data: dict[str, Any], path: Path) -> None:
    """Save a dictionary as a JSON file.

    Args:
        data: Dictionary to serialize.
        path: Destination file path.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, default=str)
    logger.info("Saved JSON to %s", path)


def load_json(path: Path) -> dict[str, Any]:
    """Load a JSON file into a dictionary.

    Args:
        path: Source file path.

    Returns:
        Deserialized dictionary.
    """
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)
