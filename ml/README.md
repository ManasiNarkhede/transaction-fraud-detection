# Machine Learning Pipeline

This directory contains the machine learning components of the FraudGuard system.

## Overview

The ML pipeline is responsible for:

1. **Feature Engineering** — Extracting features from transaction data
2. **Model Training** — Training a fraud detection model on labeled data
3. **Model Evaluation** — Validating model performance with classification metrics
4. **Model Export** — Exporting the trained model to ONNX for inference

## Directory Layout

```
ml/
├── config.py                  # Pipeline configuration
├── feature_engineering.py     # Feature extraction and transforms
├── train.py                   # Model training entry point
├── evaluate.py                # Model evaluation and metrics
├── onnx_export.py             # Export trained model to ONNX
├── utils.py                   # Shared helpers
├── requirements.txt           # Python dependencies
├── data/
│   └── synthetic.csv          # Synthetic training dataset
└── tests/
    ├── test_feature_engineering.py
    ├── test_training.py
    └── test_onnx_export.py
```

## Technology Stack

| Component      | Technology         |
|----------------|--------------------|
| Model Training | scikit-learn, XGBoost |
| Model Export   | ONNX               |
| Inference      | ONNX Runtime (served via the backend) |

## Model Performance Targets

| Metric | Target |
|--------|--------|
| Precision | > 0.85 |
| Recall | > 0.80 |
| F1 Score | > 0.82 |
| AUC-ROC | > 0.90 |

## Usage

```bash
cd ml
pip install -r requirements.txt

# Train a model
python train.py

# Evaluate the trained model
python evaluate.py

# Export to ONNX
python onnx_export.py

# Run tests
pytest
```

## See Also

- [Architecture Documentation](../docs/architecture/)
- [API Documentation](../docs/api/)
