"""Pydantic Settings class loading from .env."""

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_DEV_JWT_DEFAULT = "dev-only-do-not-use-in-production-generate-new-key"


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "FraudDetectionGuard"
    debug: bool = False
    version: str = "0.1.0"
    environment: str = "development"
    api_v1_prefix: str = "/api/v1"
    project_name: str = "Fraud Detection API"

    database_url: str = (
        "postgresql+asyncpg://fraud_user:fraud_password@localhost:5432/fraud_detection"
    )
    db_pool_size: int = 20

    redis_url: str = "redis://:redis_password@localhost:6379/0"

    jwt_secret_key: str = _DEV_JWT_DEFAULT
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 15
    refresh_token_expire_days: int = 7
    bcrypt_rounds: int = 12

    cors_origins: str = "http://localhost:5173,http://localhost:3000"

    log_level: str = "INFO"
    log_format: str = "json"

    rate_limit_per_minute: int = 60

    # When True, stream workers run as in-process asyncio background tasks
    # inside the App Service process (set to True via Azure App Settings).
    # When False (default), workers run as a separate process via run.py.
    workers_in_process: bool = False

    model_path: str = "./models"
    model_dir: str = "ml/models"
    ml_enabled: bool = True
    ml_rule_weight: float = 0.4
    ml_model_weight: float = 0.6
    onnx_threads: int = 2

    # Decision engine thresholds
    approve_threshold: int = 40
    verify_threshold: int = 70
    block_threshold: int = 100

    # SMTP email (OTP codes + fraud alerts)
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: str = ""
    smtp_use_tls: bool = True
    notification_from_email: str = "alerts@fraudguard.com"

    # Twilio SMS (OTP + critical block alerts)
    twilio_account_sid: str = ""
    twilio_auth_token: str = ""
    twilio_from_number: str = ""

    @model_validator(mode="after")
    def _validate_jwt_secret_in_production(self) -> "Settings":
        """Refuse to start in production with a missing or known-insecure JWT secret."""
        if self.environment == "production":
            secret = self.jwt_secret_key
            if not secret or secret == _DEV_JWT_DEFAULT:
                raise ValueError(
                    "JWT_SECRET_KEY must be set to a strong, unique value in production. "
                    "The application will not start with the dev default or an empty secret."
                )
        return self

    @property
    def cors_origins_list(self) -> list[str]:
        """Return CORS origins as a list."""
        return [origin.strip() for origin in self.cors_origins.split(",")]


settings = Settings()
