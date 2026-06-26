"""Unit tests for feature engineering service, FeatureVector model, and KeyBuilder."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

import pytest
from pydantic import ValidationError
from pytest_mock import MockerFixture

from app.models import FeatureVector
from app.services.feature_engineering import FeatureEngineeringService
from app.services.key_builder import KeyBuilder

# --------------------------------------------------------------------------- #
# FeatureVector model creation
# --------------------------------------------------------------------------- #


def test_feature_vector_model_creation() -> None:
    """Test FeatureVector instantiation with valid data."""
    fv = FeatureVector(
        amount=Decimal("100.00"),
        amount_zscore=0.5,
        time_since_last_tx=24.0,
        tx_count_1h=0,
        tx_count_24h=1,
        tx_count_7d=5,
        avg_amount_30d=Decimal("50.00"),
        max_amount_30d=Decimal("200.00"),
        unique_merchants_24h=1,
        unique_countries_24h=1,
        device_trust_score=0.8,
        is_new_device=False,
        hour_of_day=14,
        day_of_week=2,
        is_weekend=False,
    )
    assert fv.amount == Decimal("100.00")
    assert fv.amount_zscore == 0.5
    assert fv.time_since_last_tx == 24.0
    assert fv.tx_count_1h == 0
    assert fv.tx_count_24h == 1
    assert fv.tx_count_7d == 5
    assert fv.avg_amount_30d == Decimal("50.00")
    assert fv.max_amount_30d == Decimal("200.00")
    assert fv.unique_merchants_24h == 1
    assert fv.unique_countries_24h == 1
    assert fv.device_trust_score == 0.8
    assert fv.is_new_device is False
    assert fv.hour_of_day == 14
    assert fv.day_of_week == 2
    assert fv.is_weekend is False


# --------------------------------------------------------------------------- #
# FeatureVector validation
# --------------------------------------------------------------------------- #


def test_feature_vector_validation_hour_of_day_bounds() -> None:
    """Test hour_of_day must be between 0 and 23."""
    with pytest.raises(ValidationError):
        FeatureVector(
            amount=Decimal("100.00"),
            amount_zscore=0.0,
            time_since_last_tx=1.0,
            tx_count_1h=0,
            tx_count_24h=0,
            tx_count_7d=0,
            avg_amount_30d=Decimal("50.00"),
            max_amount_30d=Decimal("50.00"),
            unique_merchants_24h=1,
            unique_countries_24h=1,
            device_trust_score=0.5,
            is_new_device=False,
            hour_of_day=24,
            day_of_week=0,
            is_weekend=False,
        )

    with pytest.raises(ValidationError):
        FeatureVector(
            amount=Decimal("100.00"),
            amount_zscore=0.0,
            time_since_last_tx=1.0,
            tx_count_1h=0,
            tx_count_24h=0,
            tx_count_7d=0,
            avg_amount_30d=Decimal("50.00"),
            max_amount_30d=Decimal("50.00"),
            unique_merchants_24h=1,
            unique_countries_24h=1,
            device_trust_score=0.5,
            is_new_device=False,
            hour_of_day=-1,
            day_of_week=0,
            is_weekend=False,
        )


def test_feature_vector_validation_day_of_week_bounds() -> None:
    """Test day_of_week must be between 0 and 6."""
    with pytest.raises(ValidationError):
        FeatureVector(
            amount=Decimal("100.00"),
            amount_zscore=0.0,
            time_since_last_tx=1.0,
            tx_count_1h=0,
            tx_count_24h=0,
            tx_count_7d=0,
            avg_amount_30d=Decimal("50.00"),
            max_amount_30d=Decimal("50.00"),
            unique_merchants_24h=1,
            unique_countries_24h=1,
            device_trust_score=0.5,
            is_new_device=False,
            hour_of_day=12,
            day_of_week=7,
            is_weekend=False,
        )

    with pytest.raises(ValidationError):
        FeatureVector(
            amount=Decimal("100.00"),
            amount_zscore=0.0,
            time_since_last_tx=1.0,
            tx_count_1h=0,
            tx_count_24h=0,
            tx_count_7d=0,
            avg_amount_30d=Decimal("50.00"),
            max_amount_30d=Decimal("50.00"),
            unique_merchants_24h=1,
            unique_countries_24h=1,
            device_trust_score=0.5,
            is_new_device=False,
            hour_of_day=12,
            day_of_week=-1,
            is_weekend=False,
        )


def test_feature_vector_validation_device_trust_score_bounds() -> None:
    """Test device_trust_score must be between 0.0 and 1.0."""
    with pytest.raises(ValidationError):
        FeatureVector(
            amount=Decimal("100.00"),
            amount_zscore=0.0,
            time_since_last_tx=1.0,
            tx_count_1h=0,
            tx_count_24h=0,
            tx_count_7d=0,
            avg_amount_30d=Decimal("50.00"),
            max_amount_30d=Decimal("50.00"),
            unique_merchants_24h=1,
            unique_countries_24h=1,
            device_trust_score=1.1,
            is_new_device=False,
            hour_of_day=12,
            day_of_week=3,
            is_weekend=False,
        )

    with pytest.raises(ValidationError):
        FeatureVector(
            amount=Decimal("100.00"),
            amount_zscore=0.0,
            time_since_last_tx=1.0,
            tx_count_1h=0,
            tx_count_24h=0,
            tx_count_7d=0,
            avg_amount_30d=Decimal("50.00"),
            max_amount_30d=Decimal("50.00"),
            unique_merchants_24h=1,
            unique_countries_24h=1,
            device_trust_score=-0.1,
            is_new_device=False,
            hour_of_day=12,
            day_of_week=3,
            is_weekend=False,
        )


def test_feature_vector_validation_tx_counts_non_negative() -> None:
    """Test transaction counts must be non-negative."""
    with pytest.raises(ValidationError):
        FeatureVector(
            amount=Decimal("100.00"),
            amount_zscore=0.0,
            time_since_last_tx=1.0,
            tx_count_1h=-1,
            tx_count_24h=0,
            tx_count_7d=0,
            avg_amount_30d=Decimal("50.00"),
            max_amount_30d=Decimal("50.00"),
            unique_merchants_24h=1,
            unique_countries_24h=1,
            device_trust_score=0.5,
            is_new_device=False,
            hour_of_day=12,
            day_of_week=3,
            is_weekend=False,
        )

    with pytest.raises(ValidationError):
        FeatureVector(
            amount=Decimal("100.00"),
            amount_zscore=0.0,
            time_since_last_tx=1.0,
            tx_count_1h=0,
            tx_count_24h=-1,
            tx_count_7d=0,
            avg_amount_30d=Decimal("50.00"),
            max_amount_30d=Decimal("50.00"),
            unique_merchants_24h=1,
            unique_countries_24h=1,
            device_trust_score=0.5,
            is_new_device=False,
            hour_of_day=12,
            day_of_week=3,
            is_weekend=False,
        )

    with pytest.raises(ValidationError):
        FeatureVector(
            amount=Decimal("100.00"),
            amount_zscore=0.0,
            time_since_last_tx=1.0,
            tx_count_1h=0,
            tx_count_24h=0,
            tx_count_7d=-1,
            avg_amount_30d=Decimal("50.00"),
            max_amount_30d=Decimal("50.00"),
            unique_merchants_24h=1,
            unique_countries_24h=1,
            device_trust_score=0.5,
            is_new_device=False,
            hour_of_day=12,
            day_of_week=3,
            is_weekend=False,
        )


def test_feature_vector_validation_unique_counts_non_negative() -> None:
    """Test unique merchant/country counts must be non-negative."""
    with pytest.raises(ValidationError):
        FeatureVector(
            amount=Decimal("100.00"),
            amount_zscore=0.0,
            time_since_last_tx=1.0,
            tx_count_1h=0,
            tx_count_24h=0,
            tx_count_7d=0,
            avg_amount_30d=Decimal("50.00"),
            max_amount_30d=Decimal("50.00"),
            unique_merchants_24h=-1,
            unique_countries_24h=1,
            device_trust_score=0.5,
            is_new_device=False,
            hour_of_day=12,
            day_of_week=3,
            is_weekend=False,
        )

    with pytest.raises(ValidationError):
        FeatureVector(
            amount=Decimal("100.00"),
            amount_zscore=0.0,
            time_since_last_tx=1.0,
            tx_count_1h=0,
            tx_count_24h=0,
            tx_count_7d=0,
            avg_amount_30d=Decimal("50.00"),
            max_amount_30d=Decimal("50.00"),
            unique_merchants_24h=1,
            unique_countries_24h=-1,
            device_trust_score=0.5,
            is_new_device=False,
            hour_of_day=12,
            day_of_week=3,
            is_weekend=False,
        )


def test_feature_vector_validation_boundary_values() -> None:
    """Test FeatureVector accepts boundary values."""
    fv = FeatureVector(
        amount=Decimal("0.00"),
        amount_zscore=0.0,
        time_since_last_tx=0.0,
        tx_count_1h=0,
        tx_count_24h=0,
        tx_count_7d=0,
        avg_amount_30d=Decimal("0.00"),
        max_amount_30d=Decimal("0.00"),
        unique_merchants_24h=0,
        unique_countries_24h=0,
        device_trust_score=0.0,
        is_new_device=True,
        hour_of_day=0,
        day_of_week=0,
        is_weekend=False,
    )
    assert fv.hour_of_day == 0
    assert fv.day_of_week == 0
    assert fv.device_trust_score == 0.0

    fv_max = FeatureVector(
        amount=Decimal("999999.99"),
        amount_zscore=10.0,
        time_since_last_tx=999.0,
        tx_count_1h=100,
        tx_count_24h=1000,
        tx_count_7d=7000,
        avg_amount_30d=Decimal("999999.99"),
        max_amount_30d=Decimal("999999.99"),
        unique_merchants_24h=100,
        unique_countries_24h=50,
        device_trust_score=1.0,
        is_new_device=False,
        hour_of_day=23,
        day_of_week=6,
        is_weekend=True,
    )
    assert fv_max.hour_of_day == 23
    assert fv_max.day_of_week == 6
    assert fv_max.device_trust_score == 1.0


# --------------------------------------------------------------------------- #
# Cold-start features
# --------------------------------------------------------------------------- #


def test_cold_start_features() -> None:
    """Test cold-start default feature values."""
    service = FeatureEngineeringService()
    amount = Decimal("150.00")
    fingerprint = "abc123"
    timestamp = datetime(2024, 6, 15, 14, 30, 0)

    features = service.get_cold_start_features(amount, fingerprint, timestamp)

    assert features.amount == amount
    assert features.amount_zscore == 0.0
    assert features.time_since_last_tx == 999.0
    assert features.tx_count_1h == 0
    assert features.tx_count_24h == 0
    assert features.tx_count_7d == 0
    assert features.avg_amount_30d == amount
    assert features.max_amount_30d == amount
    assert features.unique_merchants_24h == 1
    assert features.unique_countries_24h == 1
    assert features.device_trust_score == 0.5
    assert features.is_new_device is True
    assert features.hour_of_day == 14
    assert features.day_of_week == 5  # Saturday
    assert features.is_weekend is True


def test_cold_start_features_weekday() -> None:
    """Test cold-start features on a weekday."""
    service = FeatureEngineeringService()
    amount = Decimal("50.00")
    fingerprint = "def456"
    timestamp = datetime(2024, 6, 10, 9, 0, 0)  # Monday

    features = service.get_cold_start_features(amount, fingerprint, timestamp)

    assert features.hour_of_day == 9
    assert features.day_of_week == 0
    assert features.is_weekend is False


# --------------------------------------------------------------------------- #
# FeatureVector serialization
# --------------------------------------------------------------------------- #


def test_feature_vector_serialization() -> None:
    """Test JSON serialization and deserialization of FeatureVector."""
    fv = FeatureVector(
        amount=Decimal("100.00"),
        amount_zscore=0.5,
        time_since_last_tx=24.0,
        tx_count_1h=0,
        tx_count_24h=1,
        tx_count_7d=5,
        avg_amount_30d=Decimal("50.00"),
        max_amount_30d=Decimal("200.00"),
        unique_merchants_24h=1,
        unique_countries_24h=1,
        device_trust_score=0.8,
        is_new_device=False,
        hour_of_day=14,
        day_of_week=2,
        is_weekend=False,
    )

    # Serialize to dict
    data = fv.model_dump()
    assert data["amount"] == Decimal("100.00")
    assert data["hour_of_day"] == 14
    assert data["is_new_device"] is False

    # Deserialize from dict
    fv2 = FeatureVector(**data)
    assert fv2.amount == Decimal("100.00")
    assert fv2.hour_of_day == 14
    assert fv2.is_new_device is False


def test_feature_vector_serialization_json() -> None:
    """Test JSON string serialization of FeatureVector."""
    fv = FeatureVector(
        amount=Decimal("100.00"),
        amount_zscore=0.5,
        time_since_last_tx=24.0,
        tx_count_1h=0,
        tx_count_24h=1,
        tx_count_7d=5,
        avg_amount_30d=Decimal("50.00"),
        max_amount_30d=Decimal("200.00"),
        unique_merchants_24h=1,
        unique_countries_24h=1,
        device_trust_score=0.8,
        is_new_device=False,
        hour_of_day=14,
        day_of_week=2,
        is_weekend=False,
    )

    json_str = fv.model_dump_json()
    assert '"amount":' in json_str
    assert '"hour_of_day":14' in json_str
    assert '"is_new_device":false' in json_str


# --------------------------------------------------------------------------- #
# KeyBuilder patterns
# --------------------------------------------------------------------------- #


def test_key_builder_patterns() -> None:
    """Test all KeyBuilder key patterns."""
    user_id = "user-123"
    ip = "192.168.1.1"
    fingerprint = "fp-abc"
    entity = "login"
    window = "1m"

    assert KeyBuilder.user_profile(user_id) == f"fraudguard:user:profile:{user_id}"
    assert KeyBuilder.user_history(user_id) == f"fraudguard:user:history:{user_id}"
    assert KeyBuilder.fraud_rules(user_id) == f"fraudguard:fraud:rules:{user_id}"
    assert KeyBuilder.blacklist_ip(ip) == f"fraudguard:blacklist:ip:{ip}"
    assert (
        KeyBuilder.blacklist_device(fingerprint)
        == f"fraudguard:blacklist:device:{fingerprint}"
    )
    assert (
        KeyBuilder.rate_limit(entity, window)
        == f"fraudguard:ratelimit:{entity}:{window}"
    )
    assert KeyBuilder.feature_vector(user_id) == f"fraudguard:ml:features:{user_id}"


def test_key_builder_prefix_consistency() -> None:
    """Test that all keys share the same prefix."""
    keys = [
        KeyBuilder.user_profile("u1"),
        KeyBuilder.user_history("u1"),
        KeyBuilder.fraud_rules("u1"),
        KeyBuilder.blacklist_ip("1.1.1.1"),
        KeyBuilder.blacklist_device("fp"),
        KeyBuilder.rate_limit("e", "w"),
        KeyBuilder.feature_vector("u1"),
    ]
    for key in keys:
        assert key.startswith("fraudguard:")


# --------------------------------------------------------------------------- #
# FeatureEngineeringService helpers
# --------------------------------------------------------------------------- #


def test_calculate_zscore_no_history() -> None:
    """Test z-score returns 0.0 when no history exists."""
    service = FeatureEngineeringService()
    stats = {"count": 0, "avg_amount": Decimal("0"), "std_amount": Decimal("0")}
    assert service._calculate_zscore(Decimal("100.00"), stats) == 0.0


def test_calculate_zscore_zero_std() -> None:
    """Test z-score returns 0.0 when std is zero with multiple priors."""
    service = FeatureEngineeringService()
    stats = {
        "count": 5,
        "avg_amount": Decimal("100.00"),
        "std_amount": Decimal("0"),
    }
    assert service._calculate_zscore(Decimal("100.00"), stats) == 0.0


def test_calculate_zscore_single_prior_relative_deviation() -> None:
    """With one prior tx, use relative deviation when population std is zero."""
    service = FeatureEngineeringService()
    stats = {
        "count": 1,
        "avg_amount": Decimal("10000.00"),
        "std_amount": Decimal("0"),
    }
    zscore = service._calculate_zscore(Decimal("10.00"), stats)
    assert zscore == pytest.approx(-0.999)


def test_calculate_zscore_normal() -> None:
    """Test z-score calculation with normal stats."""
    service = FeatureEngineeringService()
    stats = {
        "count": 10,
        "avg_amount": Decimal("100.00"),
        "std_amount": Decimal("20.00"),
    }
    zscore = service._calculate_zscore(Decimal("140.00"), stats)
    assert zscore == 2.0


def test_hours_since_no_last_tx() -> None:
    """Test _hours_since returns 999.0 when no last transaction."""
    service = FeatureEngineeringService()
    current = datetime(2024, 6, 15, 12, 0, 0)
    assert service._hours_since(None, current) == 999.0


def test_hours_since_with_last_tx() -> None:
    """Test _hours_since calculates correct hours."""
    service = FeatureEngineeringService()
    current = datetime(2024, 6, 15, 12, 0, 0)
    last_tx = datetime(2024, 6, 15, 10, 0, 0)
    assert service._hours_since(last_tx, current) == 2.0


def test_hours_since_clamps_negative_delta() -> None:
    """Clock skew must not produce negative hours-since values."""
    service = FeatureEngineeringService()
    current = datetime(2024, 6, 15, 12, 0, 0)
    last_tx = datetime(2024, 6, 15, 12, 0, 1)
    assert service._hours_since(last_tx, current) == 0.0


# --------------------------------------------------------------------------- #
# FeatureEngineeringService async methods (with mocking)
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_get_cached_features_hit(mocker: MockerFixture) -> None:
    """Test retrieving cached features when cache has data."""
    service = FeatureEngineeringService()
    user_id = uuid4()
    cached_data = {
        "amount": "100.00",
        "amount_zscore": 0.5,
        "time_since_last_tx": 24.0,
        "tx_count_1h": 0,
        "tx_count_24h": 1,
        "tx_count_7d": 5,
        "avg_amount_30d": "50.00",
        "max_amount_30d": "200.00",
        "unique_merchants_24h": 1,
        "unique_countries_24h": 1,
        "device_trust_score": 0.8,
        "is_new_device": False,
        "hour_of_day": 14,
        "day_of_week": 2,
        "is_weekend": False,
    }
    mocker.patch.object(service.cache, "get", return_value=cached_data)

    result = await service.get_cached_features(user_id)

    assert result is not None
    assert result.amount == Decimal("100.00")
    assert result.hour_of_day == 14


@pytest.mark.asyncio
async def test_get_cached_features_miss(mocker: MockerFixture) -> None:
    """Test retrieving cached features when cache is empty."""
    service = FeatureEngineeringService()
    user_id = uuid4()
    mocker.patch.object(service.cache, "get", return_value=None)

    result = await service.get_cached_features(user_id)

    assert result is None


@pytest.mark.asyncio
async def test_get_cached_features_parse_error(
    mocker: MockerFixture,
) -> None:
    """Test retrieving cached features with invalid data returns None."""
    service = FeatureEngineeringService()
    user_id = uuid4()
    mocker.patch.object(service.cache, "get", return_value={"invalid": "data"})

    result = await service.get_cached_features(user_id)

    assert result is None


@pytest.mark.asyncio
async def test_cache_features(mocker: MockerFixture) -> None:
    """Test caching features stores them correctly."""
    service = FeatureEngineeringService()
    user_id = uuid4()
    fv = FeatureVector(
        amount=Decimal("100.00"),
        amount_zscore=0.5,
        time_since_last_tx=24.0,
        tx_count_1h=0,
        tx_count_24h=1,
        tx_count_7d=5,
        avg_amount_30d=Decimal("50.00"),
        max_amount_30d=Decimal("200.00"),
        unique_merchants_24h=1,
        unique_countries_24h=1,
        device_trust_score=0.8,
        is_new_device=False,
        hour_of_day=14,
        day_of_week=2,
        is_weekend=False,
    )
    mock_set = mocker.patch.object(service.cache, "set", return_value=True)

    result = await service.cache_features(user_id, fv, ttl=300)

    assert result is True
    mock_set.assert_called_once()
    call_args = mock_set.call_args
    assert call_args[1]["ttl"] == 300


# --------------------------------------------------------------------------- #
# _hours_since timezone handling (regression: naive DB datetime vs aware now)
# --------------------------------------------------------------------------- #


def test_hours_since_naive_last_tx_aware_current() -> None:
    """Postgres returns naive datetimes; current is tz-aware. Must not raise."""
    svc = FeatureEngineeringService()
    naive_last = datetime(2026, 6, 24, 10, 0, 0)  # naive (as from DB)
    aware_now = datetime(2026, 6, 24, 16, 0, 0, tzinfo=UTC)
    result = svc._hours_since(naive_last, aware_now)
    assert result == pytest.approx(6.0)


def test_hours_since_aware_last_tx_naive_current() -> None:
    """Reverse mix is also handled."""
    svc = FeatureEngineeringService()
    aware_last = datetime(2026, 6, 24, 10, 0, 0, tzinfo=UTC)
    naive_now = datetime(2026, 6, 24, 13, 0, 0)
    result = svc._hours_since(aware_last, naive_now)
    assert result == pytest.approx(3.0)


def test_hours_since_none_returns_sentinel() -> None:
    svc = FeatureEngineeringService()
    assert svc._hours_since(None, datetime.now(UTC)) == 999.0


def test_money_quantizes_high_precision_avg() -> None:
    """DB AVG() yields >2dp Decimals; _money must quantize to 2 places."""
    svc = FeatureEngineeringService()
    assert svc._money(Decimal("4309.9957142857142857")) == Decimal("4310.00")
    assert svc._money(Decimal("12.005")) == Decimal("12.01")


def test_feature_vector_accepts_quantized_money() -> None:
    """A high-precision avg, once quantized, builds a valid FeatureVector."""
    svc = FeatureEngineeringService()
    fv = FeatureVector(
        amount=Decimal("42.50"),
        amount_zscore=0.0,
        time_since_last_tx=1.0,
        tx_count_1h=0,
        tx_count_24h=1,
        tx_count_7d=1,
        avg_amount_30d=svc._money(Decimal("4309.9957142857142857")),
        max_amount_30d=svc._money(Decimal("9999.99")),
        unique_merchants_24h=1,
        unique_countries_24h=1,
        device_trust_score=0.5,
        is_new_device=True,
        hour_of_day=12,
        day_of_week=2,
        is_weekend=False,
    )
    assert fv.avg_amount_30d == Decimal("4310.00")


def test_feature_vector_json_dump_is_serializable() -> None:
    """features.model_dump(mode='json') must be json.dumps-able (no Decimal).

    Regression: audit log + stream publish used model_dump() (python mode),
    leaving Decimal values that broke JSONB persistence / json.dumps.
    """
    import json

    fv = FeatureVector(
        amount=Decimal("4309.99"),
        amount_zscore=0.0,
        time_since_last_tx=1.0,
        tx_count_1h=0,
        tx_count_24h=1,
        tx_count_7d=1,
        avg_amount_30d=Decimal("4310.00"),
        max_amount_30d=Decimal("9999.99"),
        unique_merchants_24h=1,
        unique_countries_24h=1,
        device_trust_score=0.5,
        is_new_device=True,
        hour_of_day=12,
        day_of_week=2,
        is_weekend=False,
    )
    # python mode keeps Decimal -> NOT json-serializable
    with pytest.raises(TypeError):
        json.dumps(fv.model_dump())
    # json mode -> serializable
    json.dumps(fv.model_dump(mode="json"))
