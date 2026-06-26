"""API response schemas for the fraud dashboard endpoint.

Contracts for ``GET /api/v1/dashboard/metrics``. Kept separate from ORM models
and from the dashboard service so the router stays thin.
"""

from __future__ import annotations

from datetime import date as date_type

from pydantic import BaseModel, ConfigDict, Field


class FraudTrendPoint(BaseModel):
    """A single day in the fraud trend time series."""

    model_config = ConfigDict(from_attributes=True)

    date: date_type = Field(..., description="Calendar day (UTC)")
    total: int = Field(..., ge=0, description="Total transactions that day")
    blocked: int = Field(..., ge=0, description="Blocked transactions that day")


class DecisionLatencyKPI(BaseModel):
    """Per-transaction decision latency summary."""

    model_config = ConfigDict(from_attributes=True)

    avg_ms: float | None = Field(
        None,
        description="Average decision latency in milliseconds over all recorded decisions.",
    )
    p95_ms: float | None = Field(
        None,
        description=(
            "95th-percentile decision latency in milliseconds. "
            "Null until at least one latency value is persisted."
        ),
    )


class DashboardKPIs(BaseModel):
    """Key Performance Metrics for the fraud detection system.

    These fields are additive — existing response fields are unchanged.

    Notes on accuracy / false-negative rate
    ----------------------------------------
    ``fraud_detection_accuracy`` and ``false_negative_rate`` require ground-truth
    fraud labels (a confirmed-fraud outcome feedback loop) that this system does
    not yet have.  They are intentionally returned as ``null``; see ``*_note``
    fields for context.
    """

    model_config = ConfigDict(from_attributes=True)

    # --- computable from persisted data ---

    block_success_rate: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description=(
            "Fraction of all fraud decisions that resulted in a block. "
            "Formula: blocked_transactions / total_decisions (fraud_scores rows). "
            "Returns 0.0 when no decisions have been recorded."
        ),
    )
    verification_success_rate: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description=(
            "Fraction of terminal verification challenges that the user passed. "
            "Formula: VERIFIED / (VERIFIED + FAILED + EXPIRED). "
            "Returns 0.0 when no terminal verifications exist. "
            "Note: this re-uses the same computation as ``false_positive_rate`` "
            "because a challenged user who proves legitimate is counted as "
            "both a successful verification and a false-positive signal."
        ),
    )
    decision_latency: DecisionLatencyKPI = Field(
        ...,
        description=(
            "Avg and p95 decision latency in milliseconds, computed from "
            "``fraud_scores.decision_latency_ms`` (nullable column added in "
            "migration e5f6a7b8c9d0). Both values are null until at least one "
            "transaction is ingested after that migration runs."
        ),
    )

    # --- requires labeled outcomes (not yet available) ---

    fraud_detection_accuracy: None = Field(
        None,
        description="Requires ground-truth fraud labels / feedback loop.",
    )
    fraud_detection_accuracy_note: str = Field(
        "requires labeled outcomes — no confirmed-fraud feedback loop exists yet",
        description="Explains why accuracy is null.",
    )
    false_negative_rate: None = Field(
        None,
        description="Requires ground-truth fraud labels / feedback loop.",
    )
    false_negative_rate_note: str = Field(
        "requires labeled outcomes — no confirmed-fraud feedback loop exists yet",
        description="Explains why false-negative rate is null.",
    )


class DashboardMetricsResponse(BaseModel):
    """Aggregate fraud metrics for the dashboard."""

    model_config = ConfigDict(from_attributes=True)

    total_transactions: int = Field(..., ge=0)
    blocked_transactions: int = Field(..., ge=0)
    high_risk_users: int = Field(
        ..., ge=0, description="Distinct users with a fraud score above threshold"
    )
    false_positive_rate: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description=(
            "Successful verifications / total terminal verifications "
            "(VERIFIED / (VERIFIED + FAILED + EXPIRED)). A challenged user who "
            "then proves legitimate is treated as a false positive."
        ),
    )
    fraud_trends: list[FraudTrendPoint] = Field(
        default_factory=list,
        description="Daily total vs blocked transaction counts",
    )
    kpis: DashboardKPIs = Field(
        ...,
        description="Key Performance Indicators — additive extension to the base metrics.",
    )
