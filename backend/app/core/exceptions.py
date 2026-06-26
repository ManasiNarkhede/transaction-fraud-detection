"""FraudDetectionError hierarchy."""


class FraudDetectionError(Exception):
    """Base exception for all fraud detection domain errors."""

    error_code: str = "INTERNAL_ERROR"

    def __init__(self, message: str = "Fraud detection error") -> None:
        """Initialize with message."""
        self.message = message
        super().__init__(self.message)


class ConfigurationError(FraudDetectionError):
    """Raised when application configuration is invalid or missing."""

    error_code: str = "CONFIGURATION_ERROR"

    def __init__(self, message: str = "Invalid configuration") -> None:
        """Initialize with message."""
        super().__init__(message)


class DatabaseConnectionError(FraudDetectionError):
    """Raised when database connectivity fails."""

    error_code: str = "DATABASE_CONNECTION_ERROR"

    def __init__(self, message: str = "Database connection failed") -> None:
        """Initialize with message."""
        super().__init__(message)


class RedisConnectionError(FraudDetectionError):
    """Raised when Redis connectivity fails."""

    error_code: str = "REDIS_CONNECTION_ERROR"

    def __init__(self, message: str = "Redis connection failed") -> None:
        """Initialize with message."""
        super().__init__(message)


class ValidationError(FraudDetectionError):
    """Raised when request data fails validation."""

    error_code: str = "VALIDATION_ERROR"

    def __init__(self, message: str = "Validation failed") -> None:
        """Initialize with message."""
        super().__init__(message)


class NotFoundError(FraudDetectionError):
    """Raised when a requested resource is not found."""

    error_code: str = "NOT_FOUND"

    def __init__(self, message: str = "Resource not found") -> None:
        """Initialize with message."""
        super().__init__(message)


class AuthenticationError(FraudDetectionError):
    """Raised when authentication fails."""

    error_code: str = "AUTHENTICATION_ERROR"

    def __init__(self, message: str = "Authentication failed") -> None:
        """Initialize with message."""
        super().__init__(message)


class AuthorizationError(FraudDetectionError):
    """Raised when the user is not authorized to perform an action."""

    error_code: str = "AUTHORIZATION_ERROR"

    def __init__(self, message: str = "Authorization failed") -> None:
        """Initialize with message."""
        super().__init__(message)
