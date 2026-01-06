"""Configuration management using pydantic-settings."""

from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class NATSSettings(BaseSettings):
    """NATS JetStream configuration."""

    model_config = SettingsConfigDict(env_prefix="NATS_")

    servers: list[str] = Field(default=["nats://localhost:4222"])
    user: str | None = None
    password: SecretStr | None = None
    token: SecretStr | None = None
    connect_timeout: float = Field(default=5.0, ge=0.1)
    max_reconnect_attempts: int = Field(default=10, ge=-1)

    @field_validator("servers", mode="before")
    @classmethod
    def parse_servers(cls, v: str | list[str]) -> list[str]:
        if isinstance(v, str):
            return [s.strip() for s in v.split(",")]
        return v


class DatabaseSettings(BaseSettings):
    """PostgreSQL database configuration."""

    model_config = SettingsConfigDict(env_prefix="DATABASE_")

    host: str = "localhost"
    port: int = 5432
    user: str = "orchestrator"
    password: SecretStr = SecretStr("orchestrator_dev")
    name: str = "agent_orchestrator"
    pool_size: int = Field(default=10, ge=1)
    max_overflow: int = Field(default=20, ge=0)
    echo: bool = False

    @property
    def url(self) -> str:
        """Build async database URL."""
        password = self.password.get_secret_value()
        return f"postgresql+asyncpg://{self.user}:{password}@{self.host}:{self.port}/{self.name}"


class RedisSettings(BaseSettings):
    """Redis configuration."""

    model_config = SettingsConfigDict(env_prefix="REDIS_")

    host: str = "localhost"
    port: int = 6379
    password: SecretStr | None = None
    db: int = Field(default=0, ge=0)
    ssl: bool = False
    max_connections: int = Field(default=50, ge=1)

    @property
    def url(self) -> str:
        """Build Redis URL."""
        auth = ""
        if self.password:
            auth = f":{self.password.get_secret_value()}@"
        protocol = "rediss" if self.ssl else "redis"
        return f"{protocol}://{auth}{self.host}:{self.port}/{self.db}"


class S3Settings(BaseSettings):
    """S3-compatible object storage configuration."""

    model_config = SettingsConfigDict(env_prefix="S3_")

    endpoint_url: str = "http://localhost:9000"
    access_key_id: str = "minioadmin"
    secret_access_key: SecretStr = SecretStr("minioadmin")
    bucket: str = "agent-orchestrator"
    region: str = "us-east-1"


class LLMSettings(BaseSettings):
    """LLM provider configuration."""

    model_config = SettingsConfigDict(env_prefix="LLM_")

    default_provider: Literal["anthropic", "openai", "openrouter"] = "anthropic"
    anthropic_api_key: SecretStr | None = None
    openai_api_key: SecretStr | None = None
    default_model: str = "claude-sonnet-4-20250514"
    default_temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    default_max_tokens: int = Field(default=4096, ge=1)
    timeout: float = Field(default=120.0, ge=1.0)
    max_retries: int = Field(default=3, ge=0)


class TelemetrySettings(BaseSettings):
    """OpenTelemetry configuration."""

    model_config = SettingsConfigDict(env_prefix="OTEL_")

    enabled: bool = True
    service_name: str = "agent-orchestrator"
    exporter_otlp_endpoint: str = "http://localhost:4317"
    exporter_otlp_insecure: bool = True
    log_level: str = "INFO"


class APISettings(BaseSettings):
    """API server configuration."""

    model_config = SettingsConfigDict(env_prefix="API_")

    host: str = "0.0.0.0"
    port: int = 8000
    debug: bool = False
    cors_origins: list[str] = Field(default=["*"])
    rate_limit_requests: int = Field(default=100, ge=1)
    rate_limit_window_seconds: int = Field(default=60, ge=1)

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, v: str | list[str]) -> list[str]:
        if isinstance(v, str):
            return [s.strip() for s in v.split(",")]
        return v


class Settings(BaseSettings):
    """Main application settings."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    environment: Literal["development", "staging", "production"] = "development"

    # Sub-settings
    nats: NATSSettings = Field(default_factory=NATSSettings)
    database: DatabaseSettings = Field(default_factory=DatabaseSettings)
    redis: RedisSettings = Field(default_factory=RedisSettings)
    s3: S3Settings = Field(default_factory=S3Settings)
    llm: LLMSettings = Field(default_factory=LLMSettings)
    telemetry: TelemetrySettings = Field(default_factory=TelemetrySettings)
    api: APISettings = Field(default_factory=APISettings)

    @property
    def is_development(self) -> bool:
        return self.environment == "development"

    @property
    def is_production(self) -> bool:
        return self.environment == "production"


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
