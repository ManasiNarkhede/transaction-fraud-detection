"""Unit tests for the authentication service."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from jose import jwt
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.user import User
from app.services.auth_service import (
    authenticate_user,
    create_access_token_for_user,
    create_refresh_token_for_user,
    hash_password,
    verify_jwt_token,
    verify_password,
)


class TestHashPassword:
    """Tests for hash_password function."""

    def test_hash_password_returns_string(self) -> None:
        """hash_password should return a non-empty string."""
        hashed = hash_password("mysecret")
        assert isinstance(hashed, str)
        assert len(hashed) > 0

    def test_hash_password_produces_different_hashes(self) -> None:
        """hash_password should produce different hashes for the same password."""
        password = "mysecret"
        hash1 = hash_password(password)
        hash2 = hash_password(password)
        assert hash1 != hash2


class TestVerifyPassword:
    """Tests for verify_password function."""

    def test_verify_password_correct(self) -> None:
        """verify_password should return True for correct password."""
        password = "mysecret"
        hashed = hash_password(password)
        assert verify_password(password, hashed) is True

    def test_verify_password_incorrect(self) -> None:
        """verify_password should return False for incorrect password."""
        password = "mysecret"
        hashed = hash_password(password)
        assert verify_password("wrongpassword", hashed) is False


class TestCreateAccessToken:
    """Tests for create_access_token_for_user function."""

    def test_create_access_token_returns_string(self) -> None:
        """create_access_token_for_user should return a JWT string."""
        user_id = uuid4()
        token = create_access_token_for_user(user_id, "admin")
        assert isinstance(token, str)
        assert len(token) > 0

    def test_create_access_token_payload(self) -> None:
        """create_access_token_for_user payload should contain correct claims."""
        user_id = uuid4()
        token = create_access_token_for_user(user_id, "analyst")
        payload = jwt.decode(
            token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm]
        )
        assert payload["sub"] == str(user_id)
        assert payload["role"] == "analyst"
        assert payload["type"] == "access"
        assert "exp" in payload
        assert "iat" in payload


class TestCreateRefreshToken:
    """Tests for create_refresh_token_for_user function."""

    def test_create_refresh_token_returns_string(self) -> None:
        """create_refresh_token_for_user should return a JWT string."""
        user_id = uuid4()
        token = create_refresh_token_for_user(user_id)
        assert isinstance(token, str)
        assert len(token) > 0

    def test_create_refresh_token_payload(self) -> None:
        """create_refresh_token_for_user payload should contain correct claims."""
        user_id = uuid4()
        token = create_refresh_token_for_user(user_id)
        payload = jwt.decode(
            token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm]
        )
        assert payload["sub"] == str(user_id)
        assert payload["type"] == "refresh"
        assert "exp" in payload
        assert "iat" in payload
        assert "role" not in payload


class TestVerifyJwtToken:
    """Tests for verify_jwt_token function."""

    def test_verify_valid_access_token(self) -> None:
        """verify_jwt_token should return payload for a valid token."""
        user_id = uuid4()
        token = create_access_token_for_user(user_id, "admin")
        payload = verify_jwt_token(token)
        assert payload is not None
        assert payload["sub"] == str(user_id)
        assert payload["role"] == "admin"

    def test_verify_valid_refresh_token(self) -> None:
        """verify_jwt_token should return payload for a valid refresh token."""
        user_id = uuid4()
        token = create_refresh_token_for_user(user_id)
        payload = verify_jwt_token(token)
        assert payload is not None
        assert payload["sub"] == str(user_id)
        assert payload["type"] == "refresh"

    def test_verify_invalid_token(self) -> None:
        """verify_jwt_token should return None for an invalid token."""
        payload = verify_jwt_token("not.a.valid.token")
        assert payload is None

    def test_verify_tampered_token(self) -> None:
        """verify_jwt_token should return None for a tampered token."""
        user_id = uuid4()
        token = create_access_token_for_user(user_id, "admin")
        tampered = token[:-5] + "xxxxx"
        payload = verify_jwt_token(tampered)
        assert payload is None


class TestAuthenticateUser:
    """Tests for authenticate_user function."""

    @pytest.fixture
    def mock_session(self) -> AsyncMock:
        """Return a mocked async session."""
        return AsyncMock(spec=AsyncSession)

    @pytest.fixture
    def mock_user(self) -> User:
        """Return a test user with hashed password."""
        user = User(
            id=uuid4(),
            email="test@example.com",
            hashed_password=hash_password("correctpassword"),
            full_name="Test User",
            role="analyst",
            is_active=True,
        )
        return user

    async def test_authenticate_user_success(
        self, mock_session: AsyncMock, mock_user: User
    ) -> None:
        """authenticate_user should return user for valid credentials."""
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = mock_user
        mock_session.execute.return_value = result_mock

        user = await authenticate_user(
            mock_session, "test@example.com", "correctpassword"
        )
        assert user is not None
        assert user.email == "test@example.com"

    async def test_authenticate_user_wrong_password(
        self, mock_session: AsyncMock, mock_user: User
    ) -> None:
        """authenticate_user should return None for wrong password."""
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = mock_user
        mock_session.execute.return_value = result_mock

        user = await authenticate_user(
            mock_session, "test@example.com", "wrongpassword"
        )
        assert user is None

    async def test_authenticate_user_not_found(self, mock_session: AsyncMock) -> None:
        """authenticate_user should return None if user not found."""
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = result_mock

        user = await authenticate_user(
            mock_session, "missing@example.com", "anypassword"
        )
        assert user is None

    async def test_authenticate_user_inactive(
        self, mock_session: AsyncMock, mock_user: User
    ) -> None:
        """authenticate_user should return None if user is inactive."""
        mock_user.is_active = False
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = mock_user
        mock_session.execute.return_value = result_mock

        user = await authenticate_user(
            mock_session, "test@example.com", "correctpassword"
        )
        assert user is None
