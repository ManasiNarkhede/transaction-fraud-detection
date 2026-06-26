"""ONNX inference service for fraud detection models.

Loads exported ONNX models and provides a unified interface for
scoring transactions using both Isolation Forest and XGBoost models.
"""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import Any

import numpy as np

logger = logging.getLogger(__name__)

# ONNX Runtime is imported lazily to allow the module to load even when
# the dependency is not installed (e.g. in minimal test environments).
_ort = None


def _get_ort() -> Any:
    """Lazy-load onnxruntime module.

    Returns:
        The onnxruntime module.

    Raises:
        ImportError: If onnxruntime is not installed.
    """
    global _ort
    if _ort is None:
        import onnxruntime as ort

        _ort = ort
    return _ort


class ONNXInferenceService:
    """Service for running fraud detection inference with ONNX models.

    Loads Isolation Forest and XGBoost ONNX models from disk and provides
    a ``predict`` method that returns ensemble scores.
    """

    def __init__(self, model_dir: str = "ml/models") -> None:
        """Initialize the inference service and load models.

        Args:
            model_dir: Directory containing the ONNX model files. A relative
                path is anchored to the backend package root (the directory
                containing ``app/``) so resolution is independent of the
                process CWD — on Azure App Service gunicorn's CWD is not
                guaranteed to be the deploy/extract root.
        """
        base = Path(model_dir)
        if not base.is_absolute():
            base = Path(__file__).resolve().parents[2] / base
        self.model_dir = base
        self.iso_session: Any | None = None
        self.xgb_session: Any | None = None
        self.feature_names: list[str] = []
        self._load_models()

    def _load_models(self) -> None:
        """Load ONNX models and feature names from disk.

        Models are loaded gracefully — missing files result in ``None``
        sessions rather than hard failures.
        """
        try:
            ort = _get_ort()
        except ImportError:
            logger.warning("onnxruntime not installed; ONNX inference disabled")
            return

        # Load Isolation Forest ONNX
        iso_path = self.model_dir / "isolation_forest.onnx"
        if iso_path.exists():
            try:
                self.iso_session = ort.InferenceSession(str(iso_path))
                logger.info("Loaded Isolation Forest ONNX from %s", iso_path)
            except Exception as exc:
                logger.warning(
                    "Failed to load Isolation Forest ONNX: %s",
                    exc,
                )
        else:
            logger.warning("Isolation Forest ONNX not found at %s", iso_path)

        # Load XGBoost ONNX
        xgb_path = self.model_dir / "xgboost.onnx"
        if xgb_path.exists():
            try:
                self.xgb_session = ort.InferenceSession(str(xgb_path))
                logger.info("Loaded XGBoost ONNX from %s", xgb_path)
            except Exception as exc:
                logger.warning(
                    "Failed to load XGBoost ONNX: %s",
                    exc,
                )
        else:
            logger.warning("XGBoost ONNX not found at %s", xgb_path)

        # Load feature names
        feature_names_path = self.model_dir / "../artifacts/feature_names.json"
        if feature_names_path.exists():
            try:
                with open(feature_names_path) as f:
                    data = json.load(f)
                    self.feature_names = data.get("features", [])
                logger.info("Loaded %d feature names", len(self.feature_names))
            except Exception as exc:
                logger.warning("Failed to load feature names: %s", exc)
        else:
            logger.warning("Feature names not found at %s", feature_names_path)

    def is_ready(self) -> bool:
        """Check if both models are loaded and ready for inference.

        Returns:
            True if both Isolation Forest and XGBoost sessions are available.
        """
        return self.iso_session is not None and self.xgb_session is not None

    def predict(self, features: dict[str, float]) -> dict[str, float]:
        """Run inference on a single feature vector.

        Args:
            features: Dictionary mapping feature names to float values.

        Returns:
            Dictionary with raw and normalized scores from each model
            plus an ensemble score.

        Raises:
            RuntimeError: If models are not loaded.
        """
        if not self.is_ready():
            raise RuntimeError("ONNX models are not loaded")

        start_time = time.perf_counter()

        # Convert features to numpy array in the correct order
        feature_vector = np.array(
            [[features.get(name, 0.0) for name in self.feature_names]],
            dtype=np.float32,
        )

        # Isolation Forest prediction
        iso_input_name = self.iso_session.get_inputs()[0].name  # type: ignore[union-attr]
        iso_output = self.iso_session.run(None, {iso_input_name: feature_vector})  # type: ignore[union-attr]
        iso_score = float(np.asarray(iso_output[0]).flatten()[0])

        # XGBoost prediction
        xgb_input_name = self.xgb_session.get_inputs()[0].name  # type: ignore[union-attr]
        xgb_output = self.xgb_session.run(None, {xgb_input_name: feature_vector})  # type: ignore[union-attr]
        xgb_prob = xgb_output[0]

        # Normalize Isolation Forest score to [0, 1]
        # Isolation Forest returns anomaly_score where -0.5 is normal, +0.5 is anomalous
        iso_normalized = 1.0 - (iso_score + 0.5)
        iso_normalized = max(0.0, min(1.0, iso_normalized))

        # XGBoost returns probability of fraud (class 1)
        xgb_prob_arr = np.asarray(xgb_prob).flatten()
        if len(xgb_prob_arr) > 1:
            xgb_fraud_prob = float(xgb_prob_arr[1])
        else:
            xgb_fraud_prob = float(xgb_prob_arr[0])

        # Ensemble score (weighted average)
        ensemble_score = 0.3 * iso_normalized + 0.7 * xgb_fraud_prob

        inference_time = time.perf_counter() - start_time
        logger.info(
            "ONNX inference completed in %.4fs (ensemble_score=%.4f)",
            inference_time,
            ensemble_score,
        )

        return {
            "isolation_forest_score": iso_score,
            "isolation_forest_normalized": iso_normalized,
            "xgboost_probability": xgb_fraud_prob,
            "ensemble_score": ensemble_score,
        }

    def get_model_info(self) -> dict[str, Any]:
        """Return metadata about loaded models.

        Returns:
            Dictionary with model load status and feature information.
        """
        return {
            "isolation_forest_loaded": self.iso_session is not None,
            "xgboost_loaded": self.xgb_session is not None,
            "feature_count": len(self.feature_names),
            "features": self.feature_names,
        }
