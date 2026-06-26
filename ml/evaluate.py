"""Model evaluation utilities for the fraud detection ML pipeline."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")  # Non-interactive backend
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
from sklearn.metrics import (
    auc,
    confusion_matrix,
    f1_score,
    precision_recall_curve,
    precision_score,
    recall_score,
    roc_auc_score,
    roc_curve,
)

from ml.config import (
    CONFUSION_MATRIX_PATH,
    EVALUATION_REPORT_PATH,
    PR_CURVE_PATH,
    ROC_CURVE_PATH,
)
from ml.utils import save_json

logger = logging.getLogger(__name__)


# --------------------------------------------------------------------------- #
# Threshold optimization
# --------------------------------------------------------------------------- #


def find_optimal_threshold(y_true: np.ndarray, y_scores: np.ndarray) -> float:
    """Find the classification threshold that maximizes F1 score.

    Args:
        y_true: Ground-truth binary labels.
        y_scores: Predicted scores or probabilities.

    Returns:
        Threshold value (float).
    """
    thresholds = np.linspace(0.01, 0.99, 99)
    best_f1 = 0.0
    best_threshold = 0.5

    for t in thresholds:
        preds = (y_scores >= t).astype(int)
        if preds.sum() == 0:
            continue
        f1 = f1_score(y_true, preds, zero_division=0)
        if f1 > best_f1:
            best_f1 = f1
            best_threshold = t

    logger.info("Optimal threshold: %.3f (F1=%.4f)", best_threshold, best_f1)
    return float(best_threshold)


# --------------------------------------------------------------------------- #
# Evaluation
# --------------------------------------------------------------------------- #


def evaluate_model(
    model: Any,
    X_test: np.ndarray,
    y_test: np.ndarray,
    model_name: str,
    reports_dir: Path | None = None,
) -> dict[str, Any]:
    """Evaluate a trained model and generate metrics + plots.

    Supports both scikit-learn classifiers (``predict_proba``) and
    anomaly detectors like IsolationForest (``decision_function``).

    Args:
        model: Trained model instance.
        X_test: Test feature matrix.
        y_test: Test binary labels.
        model_name: Human-readable model name for report keys.
        reports_dir: Directory to save plots and JSON. Defaults to
            ``ml/reports/``.

    Returns:
        Dictionary of evaluation metrics.
    """
    if reports_dir is None:
        reports_dir = EVALUATION_REPORT_PATH.parent

    # ------------------------------------------------------------------ #
    # Predict scores
    # ------------------------------------------------------------------ #

    if hasattr(model, "predict_proba"):
        # For classifiers: use probability of positive class
        y_scores = model.predict_proba(X_test)[:, 1]
    elif hasattr(model, "decision_function"):
        # For anomaly detectors: normalize decision function to [0, 1]
        raw_scores = model.decision_function(X_test)
        # IsolationForest: lower = more anomalous, so invert
        y_scores = 1.0 - _min_max_scale(-raw_scores)
    else:
        raise ValueError("Model must implement predict_proba or decision_function")

    # ------------------------------------------------------------------ #
    # Metrics
    # ------------------------------------------------------------------ #

    auc_roc = float(roc_auc_score(y_test, y_scores))

    precision_vals, recall_vals, pr_thresholds = precision_recall_curve(y_test, y_scores)
    auc_pr = float(auc(recall_vals, precision_vals))

    threshold = find_optimal_threshold(y_test, y_scores)
    y_pred = (y_scores >= threshold).astype(int)

    prec = float(precision_score(y_test, y_pred, zero_division=0))
    rec = float(recall_score(y_test, y_pred, zero_division=0))
    f1 = float(f1_score(y_test, y_pred, zero_division=0))

    cm = confusion_matrix(y_test, y_pred)
    tn, fp, fn, tp = cm.ravel()

    metrics = {
        "model_name": model_name,
        "auc_roc": round(auc_roc, 4),
        "auc_pr": round(auc_pr, 4),
        "optimal_threshold": round(threshold, 4),
        "precision": round(prec, 4),
        "recall": round(rec, 4),
        "f1_score": round(f1, 4),
        "confusion_matrix": {
            "true_negatives": int(tn),
            "false_positives": int(fp),
            "false_negatives": int(fn),
            "true_positives": int(tp),
        },
        "support": {
            "n_total": int(len(y_test)),
            "n_fraud": int(y_test.sum()),
            "n_legitimate": int(len(y_test) - y_test.sum()),
        },
    }

    logger.info(
        "%s — AUC-ROC: %.4f | AUC-PR: %.4f | F1: %.4f | Precision: %.4f | Recall: %.4f",
        model_name,
        auc_roc,
        auc_pr,
        f1,
        prec,
        rec,
    )

    # ------------------------------------------------------------------ #
    # Plots
    # ------------------------------------------------------------------ #

    reports_dir.mkdir(parents=True, exist_ok=True)
    _plot_roc_curve(y_test, y_scores, model_name, reports_dir)
    _plot_precision_recall_curve(y_test, y_scores, model_name, reports_dir)
    _plot_confusion_matrix(cm, model_name, reports_dir)

    return metrics


# --------------------------------------------------------------------------- #
# Plotting helpers
# --------------------------------------------------------------------------- #


def _plot_roc_curve(
    y_true: np.ndarray,
    y_scores: np.ndarray,
    model_name: str,
    reports_dir: Path,
) -> None:
    """Plot and save the ROC curve."""
    fpr, tpr, _ = roc_curve(y_true, y_scores)
    roc_auc = roc_auc_score(y_true, y_scores)

    plt.figure(figsize=(8, 6))
    plt.plot(fpr, tpr, label=f"{model_name} (AUC = {roc_auc:.4f})")
    plt.plot([0, 1], [0, 1], "k--", label="Random")
    plt.xlim([0.0, 1.0])
    plt.ylim([0.0, 1.05])
    plt.xlabel("False Positive Rate")
    plt.ylabel("True Positive Rate")
    plt.title(f"ROC Curve — {model_name}")
    plt.legend(loc="lower right")
    plt.tight_layout()
    path = reports_dir / f"roc_curve_{_safe_name(model_name)}.png"
    plt.savefig(path, dpi=150)
    plt.close()
    logger.info("Saved ROC curve to %s", path)


def _plot_precision_recall_curve(
    y_true: np.ndarray,
    y_scores: np.ndarray,
    model_name: str,
    reports_dir: Path,
) -> None:
    """Plot and save the precision-recall curve."""
    precision_vals, recall_vals, _ = precision_recall_curve(y_true, y_scores)
    auc_pr = auc(recall_vals, precision_vals)

    plt.figure(figsize=(8, 6))
    plt.plot(recall_vals, precision_vals, label=f"{model_name} (AUC-PR = {auc_pr:.4f})")
    plt.xlabel("Recall")
    plt.ylabel("Precision")
    plt.title(f"Precision-Recall Curve — {model_name}")
    plt.legend(loc="lower left")
    plt.xlim([0.0, 1.0])
    plt.ylim([0.0, 1.05])
    plt.tight_layout()
    path = reports_dir / f"precision_recall_curve_{_safe_name(model_name)}.png"
    plt.savefig(path, dpi=150)
    plt.close()
    logger.info("Saved PR curve to %s", path)


def _plot_confusion_matrix(
    cm: np.ndarray,
    model_name: str,
    reports_dir: Path,
) -> None:
    """Plot and save the confusion matrix as a heatmap."""
    plt.figure(figsize=(6, 5))
    sns.heatmap(
        cm,
        annot=True,
        fmt="d",
        cmap="Blues",
        xticklabels=["Legitimate", "Fraud"],
        yticklabels=["Legitimate", "Fraud"],
    )
    plt.ylabel("True Label")
    plt.xlabel("Predicted Label")
    plt.title(f"Confusion Matrix — {model_name}")
    plt.tight_layout()
    path = reports_dir / f"confusion_matrix_{_safe_name(model_name)}.png"
    plt.savefig(path, dpi=150)
    plt.close()
    logger.info("Saved confusion matrix to %s", path)


# --------------------------------------------------------------------------- #
# Utilities
# --------------------------------------------------------------------------- #


def _min_max_scale(arr: np.ndarray) -> np.ndarray:
    """Min-max scale an array to [0, 1]."""
    min_val = arr.min()
    max_val = arr.max()
    if max_val - min_val == 0:
        return np.zeros_like(arr)
    return (arr - min_val) / (max_val - min_val)


def _safe_name(name: str) -> str:
    """Convert a model name to a filesystem-safe string."""
    return name.lower().replace(" ", "_").replace("-", "_")
