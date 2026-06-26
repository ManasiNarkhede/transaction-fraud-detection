"""Training configuration for the fraud detection ML pipeline."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

# Load environment variables from .env file if present
load_dotenv()

# --------------------------------------------------------------------------- #
# Paths
# --------------------------------------------------------------------------- #

ML_DIR = Path(__file__).parent.resolve()
MODELS_DIR = ML_DIR / "models"
ARTIFACTS_DIR = ML_DIR / "artifacts"
REPORTS_DIR = ML_DIR / "reports"
DATA_DIR = ML_DIR / "data"

# Ensure directories exist
for _dir in (MODELS_DIR, ARTIFACTS_DIR, REPORTS_DIR, DATA_DIR):
    _dir.mkdir(parents=True, exist_ok=True)

# --------------------------------------------------------------------------- #
# Database
# --------------------------------------------------------------------------- #

DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = int(os.getenv("DB_PORT", "5432"))
DB_NAME = os.getenv("DB_NAME", "fraudguard")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD", "postgres")

DATABASE_URL = (
    f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
)

# --------------------------------------------------------------------------- #
# Training settings
# --------------------------------------------------------------------------- #

TEST_SIZE = 0.20
VAL_SIZE = 0.15  # of training data
RANDOM_SEED = 42

# --------------------------------------------------------------------------- #
# Model hyperparameters
# --------------------------------------------------------------------------- #

# Isolation Forest
ISO_FOREST_N_ESTIMATORS = 100
ISO_FOREST_MAX_SAMPLES = "auto"
ISO_FOREST_CONTAMINATION = "auto"  # or float based on fraud rate
ISO_FOREST_RANDOM_STATE = RANDOM_SEED

# XGBoost
XGB_MAX_DEPTH = 6
XGB_LEARNING_RATE = 0.1
XGB_N_ESTIMATORS = 1000
XGB_EARLY_STOPPING_ROUNDS = 50
XGB_EVAL_METRIC = "auc"
XGB_RANDOM_STATE = RANDOM_SEED

# --------------------------------------------------------------------------- #
# Features
# --------------------------------------------------------------------------- #

FEATURE_COLUMNS = [
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
    # Spec-named behavioral risk signals (positions 17-18). Order MUST match
    # the backend FeatureVector (app/models/feature_vector.py) so the ONNX
    # feature_names.json contract aligns by name AND position.
    "failed_attempt_count",
    "merchant_risk_score",
]

# --------------------------------------------------------------------------- #
# Synthetic data generation
# --------------------------------------------------------------------------- #

SYNTHETIC_N_SAMPLES = 10_000
SYNTHETIC_FRAUD_RATE = 0.05

# --------------------------------------------------------------------------- #
# Artifacts
# --------------------------------------------------------------------------- #

SCALER_PATH = ARTIFACTS_DIR / "scaler.pkl"
FEATURE_NAMES_PATH = ARTIFACTS_DIR / "feature_names.json"
MODEL_METADATA_PATH = ARTIFACTS_DIR / "model_metadata.json"

ISO_FOREST_MODEL_PATH = MODELS_DIR / "isolation_forest.pkl"
XGBOOST_MODEL_PATH = MODELS_DIR / "xgboost.pkl"

EVALUATION_REPORT_PATH = REPORTS_DIR / "evaluation.json"
ROC_CURVE_PATH = REPORTS_DIR / "roc_curve.png"
PR_CURVE_PATH = REPORTS_DIR / "precision_recall_curve.png"
CONFUSION_MATRIX_PATH = REPORTS_DIR / "confusion_matrix.png"

SYNTHETIC_DATA_PATH = DATA_DIR / "synthetic.csv"
