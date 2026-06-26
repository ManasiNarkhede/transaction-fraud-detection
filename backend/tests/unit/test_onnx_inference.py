"""Unit tests for the ONNXInferenceService."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from app.services.onnx_inference import ONNXInferenceService


class TestONNXInferenceService:
    """Tests for ONNXInferenceService without requiring real ONNX models."""

    def test_init_without_models(self, tmp_path: Path) -> None:
        """Service should initialize gracefully when models are missing."""
        service = ONNXInferenceService(model_dir=str(tmp_path))
        assert service.iso_session is None
        assert service.xgb_session is None
        assert service.is_ready() is False

    def test_get_model_info_without_models(self, tmp_path: Path) -> None:
        """Model info should report models as not loaded."""
        service = ONNXInferenceService(model_dir=str(tmp_path))
        info = service.get_model_info()
        assert info["isolation_forest_loaded"] is False
        assert info["xgboost_loaded"] is False
        assert info["feature_count"] == 0

    def test_predict_raises_when_not_ready(self, tmp_path: Path) -> None:
        """Predict should raise RuntimeError when models are not loaded."""
        service = ONNXInferenceService(model_dir=str(tmp_path))
        with pytest.raises(RuntimeError, match="ONNX models are not loaded"):
            service.predict({})

    def test_predict_with_mocked_sessions(self) -> None:
        """Predict should return expected scores with mocked sessions."""
        service = ONNXInferenceService(model_dir="ml/models")

        # Mock feature names
        service.feature_names = [
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
        ]

        # Mock Isolation Forest session
        iso_session = MagicMock()
        iso_input = MagicMock()
        iso_input.name = "float_input"
        iso_session.get_inputs.return_value = [iso_input]
        iso_session.run.return_value = [np.array([[0.2]], dtype=np.float32)]
        service.iso_session = iso_session

        # Mock XGBoost session
        xgb_session = MagicMock()
        xgb_input = MagicMock()
        xgb_input.name = "float_input"
        xgb_session.get_inputs.return_value = [xgb_input]
        xgb_session.run.return_value = [np.array([[0.3, 0.7]], dtype=np.float32)]
        service.xgb_session = xgb_session

        features = dict.fromkeys(service.feature_names, 1.0)
        result = service.predict(features)

        assert "isolation_forest_score" in result
        assert "isolation_forest_normalized" in result
        assert "xgboost_probability" in result
        assert "ensemble_score" in result

        # Check normalization: 1.0 - (0.2 + 0.5) = 0.3
        assert result["isolation_forest_normalized"] == pytest.approx(0.3, abs=1e-6)
        # XGBoost fraud prob = 0.7
        assert result["xgboost_probability"] == pytest.approx(0.7, abs=1e-6)
        # Ensemble = 0.3 * 0.3 + 0.7 * 0.7 = 0.09 + 0.49 = 0.58
        assert result["ensemble_score"] == pytest.approx(0.58, abs=1e-6)

    def test_predict_with_single_class_xgboost(self) -> None:
        """Predict should handle single-class XGBoost output."""
        service = ONNXInferenceService(model_dir="ml/models")

        service.feature_names = ["feature_a", "feature_b"]

        iso_session = MagicMock()
        iso_input = MagicMock()
        iso_input.name = "input"
        iso_session.get_inputs.return_value = [iso_input]
        iso_session.run.return_value = [np.array([[-0.5]], dtype=np.float32)]
        service.iso_session = iso_session

        xgb_session = MagicMock()
        xgb_input = MagicMock()
        xgb_input.name = "input"
        xgb_session.get_inputs.return_value = [xgb_input]
        # Single value output (some XGBoost ONNX configs)
        xgb_session.run.return_value = [np.array([[0.8]], dtype=np.float32)]
        service.xgb_session = xgb_session

        result = service.predict({"feature_a": 1.0, "feature_b": 2.0})

        # iso_normalized = 1.0 - (-0.5 + 0.5) = 1.0
        assert result["isolation_forest_normalized"] == pytest.approx(1.0, abs=1e-6)
        assert result["xgboost_probability"] == pytest.approx(0.8, abs=1e-6)

    def test_is_ready_with_both_sessions(self) -> None:
        """is_ready should return True only when both sessions are loaded."""
        service = ONNXInferenceService(model_dir="ml/models")

        assert service.is_ready() is False

        service.iso_session = MagicMock()
        assert service.is_ready() is False

        service.xgb_session = MagicMock()
        assert service.is_ready() is True

    def test_feature_ordering(self) -> None:
        """Features should be passed to ONNX in the correct order."""
        service = ONNXInferenceService(model_dir="ml/models")
        service.feature_names = ["a", "b", "c"]

        iso_session = MagicMock()
        iso_input = MagicMock()
        iso_input.name = "input"
        iso_session.get_inputs.return_value = [iso_input]
        iso_session.run.return_value = [np.array([[0.0]], dtype=np.float32)]
        service.iso_session = iso_session

        xgb_session = MagicMock()
        xgb_input = MagicMock()
        xgb_input.name = "input"
        xgb_session.get_inputs.return_value = [xgb_input]
        xgb_session.run.return_value = [np.array([[0.0, 0.5]], dtype=np.float32)]
        service.xgb_session = xgb_session

        service.predict({"a": 1.0, "b": 2.0, "c": 3.0})

        # Verify the numpy array was constructed in the right order
        call_args = iso_session.run.call_args
        input_array = call_args[0][1]["input"]
        expected = np.array([[1.0, 2.0, 3.0]], dtype=np.float32)
        np.testing.assert_array_equal(input_array, expected)

    def test_missing_features_default_to_zero(self) -> None:
        """Missing features should default to 0.0."""
        service = ONNXInferenceService(model_dir="ml/models")
        service.feature_names = ["a", "b", "c"]

        iso_session = MagicMock()
        iso_input = MagicMock()
        iso_input.name = "input"
        iso_session.get_inputs.return_value = [iso_input]
        iso_session.run.return_value = [np.array([[0.0]], dtype=np.float32)]
        service.iso_session = iso_session

        xgb_session = MagicMock()
        xgb_input = MagicMock()
        xgb_input.name = "input"
        xgb_session.get_inputs.return_value = [xgb_input]
        xgb_session.run.return_value = [np.array([[0.0, 0.5]], dtype=np.float32)]
        service.xgb_session = xgb_session

        service.predict({"a": 1.0})  # b and c missing

        call_args = iso_session.run.call_args
        input_array = call_args[0][1]["input"]
        expected = np.array([[1.0, 0.0, 0.0]], dtype=np.float32)
        np.testing.assert_array_equal(input_array, expected)

    @patch("app.services.onnx_inference._get_ort")
    def test_import_error_handling(self, mock_get_ort: MagicMock) -> None:
        """Service should handle missing onnxruntime gracefully."""
        mock_get_ort.side_effect = ImportError("onnxruntime not installed")
        service = ONNXInferenceService(model_dir="ml/models")
        assert service.iso_session is None
        assert service.xgb_session is None
