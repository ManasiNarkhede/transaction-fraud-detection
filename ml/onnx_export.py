"""Export trained fraud detection models to ONNX format.

This module provides functions to convert scikit-learn Isolation Forest
and XGBoost models into ONNX format for optimized inference with
ONNX Runtime.
"""

from __future__ import annotations

import json
import logging
import sys
from pathlib import Path
from typing import Any

import joblib
import numpy as np

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)

# --------------------------------------------------------------------------- #
# Paths
# --------------------------------------------------------------------------- #

ML_DIR = Path(__file__).parent.resolve()
MODELS_DIR = ML_DIR / "models"
ARTIFACTS_DIR = ML_DIR / "artifacts"

ISO_FOREST_MODEL_PATH = MODELS_DIR / "isolation_forest.pkl"
XGBOOST_MODEL_PATH = MODELS_DIR / "xgboost.pkl"
FEATURE_NAMES_PATH = ARTIFACTS_DIR / "feature_names.json"
SCALER_PATH = ARTIFACTS_DIR / "scaler.pkl"

ISO_FOREST_ONNX_PATH = MODELS_DIR / "isolation_forest.onnx"
XGBOOST_ONNX_PATH = MODELS_DIR / "xgboost.onnx"


def load_feature_names() -> list[str]:
    """Load feature names from the artifacts directory.

    Returns:
        List of feature column names in the expected order.
    """
    with open(FEATURE_NAMES_PATH) as f:
        data = json.load(f)
    return data.get("features", [])


def load_scaler() -> Any:
    """Load the fitted StandardScaler from disk.

    Returns:
        The scaler object or None if not found.
    """
    if not SCALER_PATH.exists():
        logger.warning("Scaler not found at %s", SCALER_PATH)
        return None
    return joblib.load(SCALER_PATH)


def generate_sample_data(n_samples: int = 10, n_features: int = 16) -> np.ndarray:
    """Generate random sample data for validation.

    Args:
        n_samples: Number of samples to generate.
        n_features: Number of features per sample.

    Returns:
        Random float32 array of shape (n_samples, n_features).
    """
    rng = np.random.default_rng(42)
    return rng.random((n_samples, n_features), dtype=np.float32)


def _create_inference_session(model_path: Path | str) -> Any:
    """Create an ONNX Runtime inference session.

    Args:
        model_path: Path to the ONNX model file.

    Returns:
        ONNX Runtime InferenceSession.
    """
    import onnxruntime as ort

    return ort.InferenceSession(str(model_path))


def export_isolation_forest(
    model_path: Path | str = ISO_FOREST_MODEL_PATH,
    output_path: Path | str = ISO_FOREST_ONNX_PATH,
) -> dict[str, Any]:
    """Export an Isolation Forest model to ONNX format.

    Args:
        model_path: Path to the pickled Isolation Forest model.
        output_path: Path where the ONNX model will be saved.

    Returns:
        Dictionary with export status, validation results, and comparison data.
    """
    model_path = Path(model_path)
    output_path = Path(output_path)

    if not model_path.exists():
        raise FileNotFoundError(f"Isolation Forest model not found: {model_path}")

    from skl2onnx import convert_sklearn
    from skl2onnx.common.data_types import FloatTensorType

    logger.info("Loading Isolation Forest from %s", model_path)
    model = joblib.load(model_path)

    n_features = model.n_features_in_
    logger.info("Model has %d features", n_features)

    # Convert to ONNX
    initial_type = [("float_input", FloatTensorType([None, n_features]))]
    onnx_model = convert_sklearn(
        model, initial_types=initial_type, target_opset={"": 15, "ai.onnx.ml": 3}
    )

    # Save ONNX model
    with open(output_path, "wb") as f:
        f.write(onnx_model.SerializeToString())
    logger.info("Saved Isolation Forest ONNX to %s", output_path)

    # Validate by running inference
    sample_data = generate_sample_data(n_samples=5, n_features=n_features)
    scaler = load_scaler()
    if scaler is not None:
        sample_data = scaler.transform(sample_data).astype(np.float32)

    # Original model prediction
    original_scores = model.decision_function(sample_data)

    # ONNX prediction
    session = _create_inference_session(output_path)
    input_name = session.get_inputs()[0].name
    onnx_scores = session.run(None, {input_name: sample_data})[0]

    # Compare outputs
    # Isolation Forest ONNX output may have different shape depending on version
    if onnx_scores.ndim > 1:
        onnx_scores_flat = onnx_scores[:, 0]
    else:
        onnx_scores_flat = onnx_scores

    comparison = {
        "original_scores": original_scores.tolist(),
        "onnx_scores": onnx_scores_flat.tolist(),
        "mean_absolute_difference": float(
            np.mean(np.abs(original_scores - onnx_scores_flat))
        ),
    }

    logger.info(
        "Isolation Forest validation - mean absolute difference: %.6f",
        comparison["mean_absolute_difference"],
    )

    return {
        "status": "success",
        "model_type": "isolation_forest",
        "output_path": str(output_path),
        "n_features": n_features,
        "validation": comparison,
    }


def export_xgboost(
    model_path: Path | str = XGBOOST_MODEL_PATH,
    output_path: Path | str = XGBOOST_ONNX_PATH,
) -> dict[str, Any]:
    """Export an XGBoost model to ONNX format.

    Args:
        model_path: Path to the pickled XGBoost model.
        output_path: Path where the ONNX model will be saved.

    Returns:
        Dictionary with export status, validation results, and comparison data.
    """
    model_path = Path(model_path)
    output_path = Path(output_path)

    if not model_path.exists():
        raise FileNotFoundError(f"XGBoost model not found: {model_path}")

    from onnxmltools import convert_xgboost
    from onnxmltools.convert.common.data_types import FloatTensorType as XGBFloatTensorType

    logger.info("Loading XGBoost from %s", model_path)
    model = joblib.load(model_path)

    # Try to get n_features from various model attributes
    n_features = getattr(model, "n_features_in_", None)
    if n_features is None:
        # Fallback for older XGBoost versions
        try:
            n_features = model.get_booster().num_features()
        except Exception:
            n_features = 16  # Default based on our feature set

    logger.info("Model has %d features", n_features)

    # Convert to ONNX
    initial_type = [("float_input", XGBFloatTensorType([None, n_features]))]
    onnx_model = convert_xgboost(model, initial_types=initial_type)

    # Save ONNX model
    with open(output_path, "wb") as f:
        f.write(onnx_model.SerializeToString())
    logger.info("Saved XGBoost ONNX to %s", output_path)

    # Validate by running inference
    sample_data = generate_sample_data(n_samples=5, n_features=n_features)
    scaler = load_scaler()
    if scaler is not None:
        sample_data = scaler.transform(sample_data).astype(np.float32)

    # Original model prediction (fraud class probability)
    original_proba = model.predict_proba(sample_data)[:, 1]

    # ONNX prediction
    session = _create_inference_session(output_path)
    input_name = session.get_inputs()[0].name
    onnx_output = session.run(None, {input_name: sample_data})[0]
    
    # Handle different ONNX output shapes
    if onnx_output.ndim == 2 and onnx_output.shape[1] == 2:
        onnx_proba = onnx_output[:, 1]
    else:
        onnx_proba = onnx_output.flatten()

    comparison = {
        "original_probabilities": original_proba.tolist(),
        "onnx_probabilities": onnx_proba.tolist(),
        "mean_absolute_difference": float(
            np.mean(np.abs(original_proba - onnx_proba))
        ),
    }

    logger.info(
        "XGBoost validation - mean absolute difference: %.6f",
        comparison["mean_absolute_difference"],
    )

    return {
        "status": "success",
        "model_type": "xgboost",
        "output_path": str(output_path),
        "n_features": n_features,
        "validation": comparison,
    }


def main() -> dict[str, Any]:
    """Export both models and print validation results.

    Returns:
        Dictionary containing results for both exports.
    """
    logger.info("=" * 60)
    logger.info("ONNX Model Export")
    logger.info("=" * 60)

    results = {}

    try:
        results["isolation_forest"] = export_isolation_forest()
    except Exception as exc:
        logger.exception("Failed to export Isolation Forest: %s", exc)
        results["isolation_forest"] = {
            "status": "error",
            "error": str(exc),
        }

    try:
        results["xgboost"] = export_xgboost()
    except Exception as exc:
        logger.exception("Failed to export XGBoost: %s", exc)
        results["xgboost"] = {
            "status": "error",
            "error": str(exc),
        }

    logger.info("=" * 60)
    logger.info("Export Summary")
    logger.info("=" * 60)

    for model_name, result in results.items():
        if result.get("status") == "success":
            logger.info(
                "%s: SUCCESS (MAE=%.6f)",
                model_name,
                result["validation"]["mean_absolute_difference"],
            )
        else:
            logger.error("%s: FAILED (%s)", model_name, result.get("error", "unknown"))

    return results


if __name__ == "__main__":
    main()
