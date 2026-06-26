"""Unit tests for the OTP service."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest

from app.services import otp_service


class TestGenerateOtp:
    """Tests for generate_otp function."""

    def test_generate_otp_returns_six_digit_string(self) -> None:
        """generate_otp should return a 6-digit numeric string."""
        otp = otp_service.generate_otp()
        assert isinstance(otp, str)
        assert len(otp) == 6
        assert otp.isdigit()

    def test_generate_otp_returns_different_values(self) -> None:
        """generate_otp should return different values on subsequent calls."""
        otp1 = otp_service.generate_otp()
        otp2 = otp_service.generate_otp()
        assert otp1 != otp2

    def test_generate_otp_zero_padded(self) -> None:
        """generate_otp should zero-pad values less than 6 digits."""
        with patch("app.services.otp_service.secrets.randbelow", return_value=42):
            otp = otp_service.generate_otp()
        assert otp == "000042"


class TestHashOtp:
    """Tests for hash_otp function."""

    def test_hash_otp_returns_string(self) -> None:
        """hash_otp should return a non-empty string."""
        hashed = otp_service.hash_otp("123456")
        assert isinstance(hashed, str)
        assert len(hashed) > 0

    def test_hash_otp_produces_different_hashes(self) -> None:
        """hash_otp should produce different hashes for the same OTP."""
        otp = "123456"
        hash1 = otp_service.hash_otp(otp)
        hash2 = otp_service.hash_otp(otp)
        assert hash1 != hash2


class TestVerifyOtp:
    """Tests for verify_otp function."""

    def test_verify_otp_correct(self) -> None:
        """verify_otp should return True for correct OTP."""
        otp = "123456"
        hashed = otp_service.hash_otp(otp)
        assert otp_service.verify_otp(otp, hashed) is True

    def test_verify_otp_incorrect(self) -> None:
        """verify_otp should return False for incorrect OTP."""
        otp = "123456"
        hashed = otp_service.hash_otp(otp)
        assert otp_service.verify_otp("654321", hashed) is False


class TestStoreOtp:
    """Tests for store_otp function."""

    @pytest.mark.asyncio
    async def test_store_otp_with_redis(self) -> None:
        """store_otp should store hashed OTP in Redis."""
        mock_redis = AsyncMock()
        mock_redis.set = AsyncMock()

        with patch("app.services.otp_service.get_redis", return_value=mock_redis):
            verification_id = uuid4()
            await otp_service.store_otp(verification_id, "123456", ttl=600)

        mock_redis.set.assert_called_once()
        call_args = mock_redis.set.call_args
        assert call_args[0][0] == f"verify:{verification_id}:otp"
        # orjson.dumps returns bytes, so decode before checking
        stored_data = call_args[0][1]
        if isinstance(stored_data, bytes):
            stored_data = stored_data.decode("utf-8")
        assert "hash" in stored_data
        assert call_args[1]["ex"] == 600

    @pytest.mark.asyncio
    async def test_store_otp_redis_unavailable(self) -> None:
        """store_otp should gracefully handle Redis being unavailable."""
        with patch("app.services.otp_service.get_redis", return_value=None):
            verification_id = uuid4()
            # Should not raise
            await otp_service.store_otp(verification_id, "123456")


class TestGetOtpData:
    """Tests for get_otp_data function."""

    @pytest.mark.asyncio
    async def test_get_otp_data_found(self) -> None:
        """get_otp_data should return OTP data when found in Redis."""
        mock_redis = AsyncMock()
        mock_redis.get = AsyncMock(return_value=b'{"hash":"abc123"}')

        with patch("app.services.otp_service.get_redis", return_value=mock_redis):
            verification_id = uuid4()
            result = await otp_service.get_otp_data(verification_id)

        assert result is not None
        assert result["hash"] == "abc123"

    @pytest.mark.asyncio
    async def test_get_otp_data_not_found(self) -> None:
        """get_otp_data should return None when OTP not found."""
        mock_redis = AsyncMock()
        mock_redis.get = AsyncMock(return_value=None)

        with patch("app.services.otp_service.get_redis", return_value=mock_redis):
            verification_id = uuid4()
            result = await otp_service.get_otp_data(verification_id)

        assert result is None

    @pytest.mark.asyncio
    async def test_get_otp_data_redis_unavailable(self) -> None:
        """get_otp_data should return None when Redis is unavailable."""
        with patch("app.services.otp_service.get_redis", return_value=None):
            verification_id = uuid4()
            result = await otp_service.get_otp_data(verification_id)

        assert result is None


class TestDeleteOtp:
    """Tests for delete_otp function."""

    @pytest.mark.asyncio
    async def test_delete_otp_with_redis(self) -> None:
        """delete_otp should remove OTP data from Redis."""
        mock_redis = AsyncMock()
        mock_redis.delete = AsyncMock()

        with patch("app.services.otp_service.get_redis", return_value=mock_redis):
            verification_id = uuid4()
            await otp_service.delete_otp(verification_id)

        mock_redis.delete.assert_called_once_with(f"verify:{verification_id}:otp")

    @pytest.mark.asyncio
    async def test_delete_otp_redis_unavailable(self) -> None:
        """delete_otp should gracefully handle Redis being unavailable."""
        with patch("app.services.otp_service.get_redis", return_value=None):
            verification_id = uuid4()
            # Should not raise
            await otp_service.delete_otp(verification_id)


class TestIsRateLimited:
    """Tests for is_rate_limited function."""

    @pytest.mark.asyncio
    async def test_is_rate_limited_first_request(self) -> None:
        """First request should not be rate limited."""
        mock_redis = AsyncMock()
        mock_redis.get = AsyncMock(return_value=None)
        mock_redis.set = AsyncMock()

        with patch("app.services.otp_service.get_redis", return_value=mock_redis):
            user_id = uuid4()
            result = await otp_service.is_rate_limited(user_id)

        assert result is False
        mock_redis.set.assert_called_once()

    @pytest.mark.asyncio
    async def test_is_rate_limited_under_limit(self) -> None:
        """Request under the limit should not be rate limited."""
        mock_redis = AsyncMock()
        mock_redis.get = AsyncMock(return_value=b"2")
        mock_redis.incr = AsyncMock()

        with patch("app.services.otp_service.get_redis", return_value=mock_redis):
            user_id = uuid4()
            result = await otp_service.is_rate_limited(user_id, max_requests=3)

        assert result is False
        mock_redis.incr.assert_called_once()

    @pytest.mark.asyncio
    async def test_is_rate_limited_at_limit(self) -> None:
        """Request at the limit should be rate limited."""
        mock_redis = AsyncMock()
        mock_redis.get = AsyncMock(return_value=b"3")

        with patch("app.services.otp_service.get_redis", return_value=mock_redis):
            user_id = uuid4()
            result = await otp_service.is_rate_limited(user_id, max_requests=3)

        assert result is True

    @pytest.mark.asyncio
    async def test_is_rate_limited_redis_unavailable(self) -> None:
        """is_rate_limited should return False when Redis is unavailable."""
        with patch("app.services.otp_service.get_redis", return_value=None):
            user_id = uuid4()
            result = await otp_service.is_rate_limited(user_id)

        assert result is False


class TestIncrementAttempts:
    """Tests for increment_attempts function."""

    @pytest.mark.asyncio
    async def test_increment_attempts_with_redis(self) -> None:
        """increment_attempts should return the new attempt count."""
        mock_redis = AsyncMock()
        mock_redis.incr = AsyncMock(return_value=3)

        with patch("app.services.otp_service.get_redis", return_value=mock_redis):
            verification_id = uuid4()
            result = await otp_service.increment_attempts(verification_id)

        assert result == 3
        mock_redis.incr.assert_called_once_with(f"verify:{verification_id}:attempts")

    @pytest.mark.asyncio
    async def test_increment_attempts_redis_unavailable(self) -> None:
        """increment_attempts should return 0 when Redis is unavailable."""
        with patch("app.services.otp_service.get_redis", return_value=None):
            verification_id = uuid4()
            result = await otp_service.increment_attempts(verification_id)

        assert result == 0


class TestGetAttempts:
    """Tests for get_attempts function."""

    @pytest.mark.asyncio
    async def test_get_attempts_with_redis(self) -> None:
        """get_attempts should return the current attempt count."""
        mock_redis = AsyncMock()
        mock_redis.get = AsyncMock(return_value=b"5")

        with patch("app.services.otp_service.get_redis", return_value=mock_redis):
            verification_id = uuid4()
            result = await otp_service.get_attempts(verification_id)

        assert result == 5

    @pytest.mark.asyncio
    async def test_get_attempts_not_found(self) -> None:
        """get_attempts should return 0 when key not found."""
        mock_redis = AsyncMock()
        mock_redis.get = AsyncMock(return_value=None)

        with patch("app.services.otp_service.get_redis", return_value=mock_redis):
            verification_id = uuid4()
            result = await otp_service.get_attempts(verification_id)

        assert result == 0

    @pytest.mark.asyncio
    async def test_get_attempts_redis_unavailable(self) -> None:
        """get_attempts should return 0 when Redis is unavailable."""
        with patch("app.services.otp_service.get_redis", return_value=None):
            verification_id = uuid4()
            result = await otp_service.get_attempts(verification_id)

        assert result == 0
