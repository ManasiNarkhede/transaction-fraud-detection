"""Tests for ONNX model export functionality."""

from __future__ import annotations

import json
import pickle
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from ml.onnx_export import (
    ISO_FOREST_MODEL_PATH,
    ISO_FOREST_ONNX_PATH,
    XGBOOST_MODEL_PATH,
    XGBOOST_ONNX_PATH,
    export_isolation_forest,
    export_xgboost,
    generate_sample_data,
    load_feature_names,
    load_scaler,
    main,
)


class MockIsolationForest:
    """Picklable mock for Isolation Forest."""

    def __init__(self, n_features: int = 4) -> None:
        self.n_features_in_ = n_features

    def decision_function(self, X: np.ndarray) -> np.ndarray:
        return np.array([0.1, 0.2, 0.3])


class MockXGBoost:
    """Picklable mock for XGBoost classifier."""

    def __init__(self, n_features: int = 4) -> None:
        self.n_features_in_ = n_features

    def predict_proba(self, X: np.ndarray) -> np.ndarray:
        return np.array([
            [0.7, 0.3],
            [0.4, 0.6],
            [0.8, 0.2],
        ])

    def get_booster(self) -> Any:
        raise Exception("not available")


class MockXGBoostNoFeatures:
    """Picklable mock for XGBoost without n_features_in_."""

    def predict_proba(self, X: np.ndarray) -> np.ndarray:
        return np.array([[0.5, 0.5]])

    def get_booster(self) -> Any:
        raise Exception("not available")


def _make_mock_module() -> MagicMock:
    """Create a mock module that supports nested attribute access."""
    return MagicMock()


# Pre-built mock modules for patching.
# Each sys.modules entry must be registered for every dot-separated subpath
# that the source code imports via `from pkg.sub.mod import X`.  Python's
# import machinery looks up each path segment in sys.modules independently;
# a MagicMock for the parent does NOT automatically populate the child paths.
_MOCK_SKL2ONNX = _make_mock_module()
_MOCK_SKL2ONNX_COMMON = _make_mock_module()
_MOCK_SKL2ONNX_COMMON_DATA_TYPES = _make_mock_module()
# convert_sklearn() returns an onnx model whose SerializeToString() must yield bytes
_MOCK_SKL2ONNX.convert_sklearn.return_value.SerializeToString.return_value = b""

_MOCK_ONNXMLTOOLS = _make_mock_module()
_MOCK_ONNXMLTOOLS_CONVERT = _make_mock_module()
_MOCK_ONNXMLTOOLS_CONVERT_COMMON = _make_mock_module()
_MOCK_ONNXMLTOOLS_CONVERT_COMMON_DATA_TYPES = _make_mock_module()
# convert_xgboost() also returns an onnx model whose SerializeToString() must yield bytes
_MOCK_ONNXMLTOOLS.convert_xgboost.return_value.SerializeToString.return_value = b""

# Full sys.modules patches for skl2onnx and onnxmltools.
# All intermediate subpackage paths must appear so Python's import machinery
# can resolve `from pkg.sub.mod import X` without hitting a real package.
_PATCH_SKL2ONNX = {
    "skl2onnx": _MOCK_SKL2ONNX,
    "skl2onnx.common": _MOCK_SKL2ONNX_COMMON,
    "skl2onnx.common.data_types": _MOCK_SKL2ONNX_COMMON_DATA_TYPES,
}
_PATCH_ONNXMLTOOLS = {
    "onnxmltools": _MOCK_ONNXMLTOOLS,
    "onnxmltools.convert": _MOCK_ONNXMLTOOLS_CONVERT,
    "onnxmltools.convert.common": _MOCK_ONNXMLTOOLS_CONVERT_COMMON,
    "onnxmltools.convert.common.data_types": _MOCK_ONNXMLTOOLS_CONVERT_COMMON_DATA_TYPES,
}


class TestGenerateSampleData:
    """Tests for sample data generation."""

    def test_shape(self) -> None:
        """Generated data should have the requested shape."""
        data = generate_sample_data(n_samples=5, n_features=10)
        assert data.shape == (5, 10)

    def test_dtype(self) -> None:
        """Generated data should be float32."""
        data = generate_sample_data()
        assert data.dtype == np.float32

    def test_reproducibility(self) -> None:
        """Same seed should produce same data."""
        # The function uses a fixed seed internally
        data1 = generate_sample_data(n_samples=3, n_features=2)
        data2 = generate_sample_data(n_samples=3, n_features=2)
        np.testing.assert_array_equal(data1, data2)


class TestLoadFeatureNames:
    """Tests for feature name loading."""

    def test_load_existing(self, tmp_path: Path) -> None:
        """Should load feature names from existing JSON file."""
        feature_file = tmp_path / "feature_names.json"
        feature_file.write_text(json.dumps({"features": ["a", "b", "c"]}))

        with patch("ml.onnx_export.FEATURE_NAMES_PATH", feature_file):
            names = load_feature_names()
            assert names == ["a", "b", "c"]

    def test_load_empty(self, tmp_path: Path) -> None:
        """Should return empty list for empty features."""
        feature_file = tmp_path / "feature_names.json"
        feature_file.write_text(json.dumps({"features": []}))

        with patch("ml.onnx_export.FEATURE_NAMES_PATH", feature_file):
            names = load_feature_names()
            assert names == []

    def test_load_missing_key(self, tmp_path: Path) -> None:
        """Should return empty list when 'features' key is missing."""
        feature_file = tmp_path / "feature_names.json"
        feature_file.write_text(json.dumps({"other": "data"}))

        with patch("ml.onnx_export.FEATURE_NAMES_PATH", feature_file):
            names = load_feature_names()
            assert names == []


class TestLoadScaler:
    """Tests for scaler loading."""

    def test_load_existing(self, tmp_path: Path) -> None:
        """Should load scaler from existing pickle file."""
        scaler_file = tmp_path / "scaler.pkl"
        mock_scaler = {"mean": 0.0, "std": 1.0}
        scaler_file.write_bytes(pickle.dumps(mock_scaler))

        with patch("ml.onnx_export.SCALER_PATH", scaler_file):
            scaler = load_scaler()
            assert scaler == mock_scaler

    def test_missing_file(self, tmp_path: Path) -> None:
        """Should return None when scaler file is missing."""
        with patch("ml.onnx_export.SCALER_PATH", tmp_path / "missing.pkl"):
            scaler = load_scaler()
            assert scaler is None


class TestExportIsolationForest:
    """Tests for Isolation Forest ONNX export."""

    def test_model_not_found(self, tmp_path: Path) -> None:
        """Should raise FileNotFoundError when model is missing."""
        with pytest.raises(FileNotFoundError, match="Isolation Forest model not found"):
            export_isolation_forest(
                model_path=tmp_path / "missing.pkl",
                output_path=tmp_path / "out.onnx",
            )

    @patch.dict(sys.modules, _PATCH_SKL2ONNX)
    @patch("ml.onnx_export.load_scaler", return_value=None)
    @patch("ml.onnx_export._create_inference_session")
    def test_successful_export(
        self,
        mock_session_cls: MagicMock,
        _mock_load_scaler: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Should export model and validate inference."""
        model_path = tmp_path / "iso_forest.pkl"
        output_path = tmp_path / "iso_forest.onnx"

        # Create mock model
        mock_model = MockIsolationForest(n_features=4)
        model_path.write_bytes(pickle.dumps(mock_model))

        # Mock ONNX session
        mock_session = MagicMock()
        mock_input = MagicMock()
        mock_input.name = "float_input"
        mock_session.get_inputs.return_value = [mock_input]
        mock_session.run.return_value = [np.array([0.1, 0.2, 0.3])]
        mock_session_cls.return_value = mock_session

        result = export_isolation_forest(
            model_path=model_path,
            output_path=output_path,
        )

        assert result["status"] == "success"
        assert result["model_type"] == "isolation_forest"
        assert result["n_features"] == 4
        assert output_path.exists()

    @patch.dict(sys.modules, _PATCH_SKL2ONNX)
    @patch("ml.onnx_export.load_scaler", return_value=None)
    @patch("ml.onnx_export._create_inference_session")
    def test_validation_comparison(
        self,
        mock_session_cls: MagicMock,
        _mock_load_scaler: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Should compare original and ONNX outputs."""
        model_path = tmp_path / "iso_forest.pkl"
        output_path = tmp_path / "iso_forest.onnx"

        mock_model = MockIsolationForest(n_features=2)
        model_path.write_bytes(pickle.dumps(mock_model))

        mock_session = MagicMock()
        mock_input = MagicMock()
        mock_input.name = "float_input"
        mock_session.get_inputs.return_value = [mock_input]
        onnx_scores = np.array([[0.1], [0.2], [0.3]])
        mock_session.run.return_value = [onnx_scores]
        mock_session_cls.return_value = mock_session

        result = export_isolation_forest(
            model_path=model_path,
            output_path=output_path,
        )

        validation = result["validation"]
        assert "original_scores" in validation
        assert "onnx_scores" in validation
        assert "mean_absolute_difference" in validation
        assert validation["mean_absolute_difference"] == pytest.approx(0.0, abs=1e-6)


class TestExportXGBoost:
    """Tests for XGBoost ONNX export."""

    def test_model_not_found(self, tmp_path: Path) -> None:
        """Should raise FileNotFoundError when model is missing."""
        with pytest.raises(FileNotFoundError, match="XGBoost model not found"):
            export_xgboost(
                model_path=tmp_path / "missing.pkl",
                output_path=tmp_path / "out.onnx",
            )

    @patch.dict(sys.modules, _PATCH_ONNXMLTOOLS)
    @patch("ml.onnx_export.load_scaler", return_value=None)
    @patch("ml.onnx_export._create_inference_session")
    def test_successful_export(
        self,
        mock_session_cls: MagicMock,
        _mock_load_scaler: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Should export model and validate inference."""
        model_path = tmp_path / "xgboost.pkl"
        output_path = tmp_path / "xgboost.onnx"

        # Create mock model
        mock_model = MockXGBoost(n_features=4)
        model_path.write_bytes(pickle.dumps(mock_model))

        # Mock ONNX session
        mock_session = MagicMock()
        mock_input = MagicMock()
        mock_input.name = "float_input"
        mock_session.get_inputs.return_value = [mock_input]
        mock_session.run.return_value = [
            np.array([[0.7, 0.3], [0.4, 0.6], [0.8, 0.2]])
        ]
        mock_session_cls.return_value = mock_session

        result = export_xgboost(
            model_path=model_path,
            output_path=output_path,
        )

        assert result["status"] == "success"
        assert result["model_type"] == "xgboost"
        assert result["n_features"] == 4
        assert output_path.exists()

    @patch.dict(sys.modules, _PATCH_ONNXMLTOOLS)
    @patch("ml.onnx_export.load_scaler", return_value=None)
    @patch("ml.onnx_export._create_inference_session")
    def test_fallback_n_features(
        self,
        mock_session_cls: MagicMock,
        _mock_load_scaler: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Should fallback to default n_features when model attribute is missing."""
        model_path = tmp_path / "xgboost.pkl"
        output_path = tmp_path / "xgboost.onnx"

        mock_model = MockXGBoostNoFeatures()
        model_path.write_bytes(pickle.dumps(mock_model))

        mock_session = MagicMock()
        mock_input = MagicMock()
        mock_input.name = "float_input"
        mock_session.get_inputs.return_value = [mock_input]
        mock_session.run.return_value = [np.array([[0.5, 0.5]])]
        mock_session_cls.return_value = mock_session

        result = export_xgboost(
            model_path=model_path,
            output_path=output_path,
        )

        assert result["status"] == "success"
        assert result["n_features"] == 16  # Default fallback


class TestMain:
    """Tests for the main export orchestration function."""

    @patch("ml.onnx_export.export_isolation_forest")
    @patch("ml.onnx_export.export_xgboost")
    def test_main_success(
        self,
        mock_export_xgb: MagicMock,
        mock_export_iso: MagicMock,
    ) -> None:
        """Main should call both export functions and return results."""
        mock_export_iso.return_value = {
            "status": "success",
            "validation": {"mean_absolute_difference": 0.001},
        }
        mock_export_xgb.return_value = {
            "status": "success",
            "validation": {"mean_absolute_difference": 0.002},
        }

        results = main()

        assert results["isolation_forest"]["status"] == "success"
        assert results["xgboost"]["status"] == "success"
        mock_export_iso.assert_called_once()
        mock_export_xgb.assert_called_once()

    @patch("ml.onnx_export.export_isolation_forest")
    @patch("ml.onnx_export.export_xgboost")
    def test_main_partial_failure(
        self,
        mock_export_xgb: MagicMock,
        mock_export_iso: MagicMock,
    ) -> None:
        """Main should handle one export failing gracefully."""
        mock_export_iso.side_effect = Exception("ISO export failed")
        mock_export_xgb.return_value = {
            "status": "success",
            "validation": {"mean_absolute_difference": 0.002},
        }

        results = main()

        assert results["isolation_forest"]["status"] == "error"
        assert results["xgboost"]["status"] == "success"
