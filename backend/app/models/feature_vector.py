"""Feature vector Pydantic model for fraud detection."""

from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class FeatureVector(BaseModel):
    """Feature vector containing engineered features for fraud scoring.

    Features describe user behavior, transaction patterns, and risk signals
    derived from historical transaction data.

    Canonical order (must match ml/config.py FEATURE_COLUMNS for the ONNX
    inference contract). Positions 1-16 mirror ml/config exactly; the final
    two (failed_attempt_count, merchant_risk_score) are appended for the
    spec's risk signals and must be appended to ml/config when Phase 3
    retrains. New fields carry defaults so historical callers stay valid.
    """

    model_config = ConfigDict(from_attributes=True)

    # Transaction amount features
    amount: Decimal = Field(..., description="Transaction amount", decimal_places=2)
    log_amount: float = Field(
        default=0.0, description="Natural log of (1 + amount); log1p(amount)"
    )
    amount_zscore: float = Field(
        ..., description="Z-score of amount relative to user history"
    )

    # Temporal features
    time_since_last_tx: float = Field(
        ..., description="Hours since user's last transaction"
    )
    tx_count_1h: int = Field(
        ..., description="Transaction count in the last hour", ge=0
    )
    tx_count_24h: int = Field(
        ..., description="Transaction count in the last 24 hours", ge=0
    )
    tx_count_7d: int = Field(
        ..., description="Transaction count in the last 7 days", ge=0
    )

    # Historical amount aggregations
    avg_amount_30d: Decimal = Field(
        ..., description="Average transaction amount over 30 days", decimal_places=2
    )
    max_amount_30d: Decimal = Field(
        ..., description="Maximum transaction amount over 30 days", decimal_places=2
    )

    # Merchant and location diversity
    unique_merchants_24h: int = Field(
        ..., description="Unique merchants in the last 24 hours", ge=0
    )
    unique_countries_24h: int = Field(
        ..., description="Unique countries in the last 24 hours", ge=0
    )

    # Device risk features
    device_trust_score: float = Field(
        ..., description="Trust score of the device (0.0 to 1.0)", ge=0.0, le=1.0
    )
    is_new_device: bool = Field(
        ..., description="Whether the device is new for this user"
    )

    # Time-based cyclical features
    hour_of_day: int = Field(
        ..., description="Hour of the transaction (0-23)", ge=0, le=23
    )
    day_of_week: int = Field(
        ..., description="Day of the week (0=Monday, 6=Sunday)", ge=0, le=6
    )
    is_weekend: bool = Field(
        ..., description="Whether the transaction occurred on a weekend"
    )

    # Spec-named behavioral risk signals (appended to the ML contract)
    failed_attempt_count: int = Field(
        default=0,
        description="Recent failed/blocked transaction attempts for the user (24h)",
        ge=0,
    )
    merchant_risk_score: float = Field(
        default=0.0,
        description="Historical fraud-block rate for the merchant (0.0 to 1.0)",
        ge=0.0,
        le=1.0,
    )
