"""Centralized configuration management for YTCLFR."""

from functools import lru_cache
from pathlib import Path

from dotenv import find_dotenv, load_dotenv
from pydantic import AliasChoices, Field, PostgresDsn, RedisDsn, ValidationError, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from ytclfr_core.errors.exceptions import ConfigurationError

# Ensure .env values are loaded into process environment before settings resolution.
load_dotenv(find_dotenv(filename=".env", usecwd=True), override=False)


class Settings(BaseSettings):
    """Typed and validated application settings."""

    environment: str = Field(default="development", alias="ENVIRONMENT")
    service_name: str = Field(default="ytclfr", alias="SERVICE_NAME", min_length=1, max_length=64)
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    log_format: str = Field(default="json", alias="LOG_FORMAT")
    api_port: int = Field(default=8000, alias="API_PORT", ge=1, le=65535)
    metrics_enabled: bool = Field(default=True, alias="METRICS_ENABLED")
    metrics_namespace: str = Field(default="ytclfr", alias="METRICS_NAMESPACE", min_length=1)
    worker_metrics_port: int | None = Field(
        default=None,
        alias="WORKER_METRICS_PORT",
        ge=1,
        le=65535,
    )
    sentry_dsn: str | None = Field(default=None, alias="SENTRY_DSN")
    sentry_traces_sample_rate: float = Field(
        default=0.0,
        alias="SENTRY_TRACES_SAMPLE_RATE",
        ge=0.0,
        le=1.0,
    )
    cors_allowed_origins: list[str] = Field(
        default_factory=list,
        alias="CORS_ALLOWED_ORIGINS",
        description="Comma-separated list of allowed CORS origins.",
    )

    database_url: PostgresDsn = Field(
        validation_alias=AliasChoices("DATABASE_URL", "POSTGRES_DSN")
    )
    redis_url: RedisDsn = Field(validation_alias=AliasChoices("REDIS_URL"))
    openrouter_api_key: str = Field(alias="OPENROUTER_API_KEY", min_length=8)
    spotify_client_id: str = Field(alias="SPOTIFY_CLIENT_ID", min_length=2)
    spotify_client_secret: str = Field(alias="SPOTIFY_CLIENT_SECRET", min_length=8)
    storage_path: Path = Field(
        default=Path("./storage"),
        validation_alias=AliasChoices("STORAGE_PATH", "WORKING_DIRECTORY"),
    )
    max_video_duration: int = Field(alias="MAX_VIDEO_DURATION", default=3600, ge=60, le=43200)

    celery_broker_url: RedisDsn | None = Field(default=None, alias="CELERY_BROKER_URL")
    celery_result_backend: RedisDsn | None = Field(default=None, alias="CELERY_RESULT_BACKEND")
    celery_task_always_eager: bool = Field(default=False, alias="CELERY_TASK_ALWAYS_EAGER")

    yt_dlp_bin: str = Field(default="yt-dlp", alias="YT_DLP_BIN")
    yt_dlp_cookies_from_browser: str | None = Field(
        default="brave",
        alias="YT_DLP_COOKIES_FROM_BROWSER",
    )
    yt_dlp_cookie_file: Path | None = Field(default=None, alias="YT_DLP_COOKIE_FILE")
    yt_dlp_retry_without_cookies: bool = Field(
        default=True,
        alias="YT_DLP_RETRY_WITHOUT_COOKIES",
    )
    ffmpeg_bin: str = Field(default="ffmpeg", alias="FFMPEG_BIN")
    frame_extraction_fps: int = Field(default=1, alias="FRAME_EXTRACTION_FPS", ge=1, le=120)
    ocr_language: str = Field(default="en", alias="OCR_LANGUAGE", min_length=2, max_length=8)
    ocr_use_gpu: bool = Field(default=False, alias="OCR_USE_GPU")
    ocr_batch_size: int = Field(default=8, alias="OCR_BATCH_SIZE", ge=1, le=256)
    ocr_min_confidence: float = Field(default=0.5, alias="OCR_MIN_CONFIDENCE", ge=0.0, le=1.0)

    openrouter_base_url: str = Field(alias="OPENROUTER_BASE_URL")
    openrouter_model: str = Field(default="openai/gpt-4o-mini", alias="OPENROUTER_MODEL")
    openrouter_timeout_seconds: int = Field(
        default=60,
        alias="OPENROUTER_TIMEOUT_SECONDS",
        ge=5,
        le=600,
    )
    openrouter_parse_max_retries: int = Field(
        default=3,
        alias="OPENROUTER_PARSE_MAX_RETRIES",
        ge=1,
        le=10,
    )

    spotify_auth_url: str = Field(alias="SPOTIFY_AUTH_URL")
    spotify_api_base_url: str = Field(alias="SPOTIFY_API_BASE_URL")
    spotify_timeout_seconds: int = Field(default=30, alias="SPOTIFY_TIMEOUT_SECONDS", ge=5, le=300)
    spotify_user_id: str | None = Field(default=None, alias="SPOTIFY_USER_ID")
    spotify_user_access_token: str | None = Field(
        default=None,
        alias="SPOTIFY_USER_ACCESS_TOKEN",
    )

    tmdb_web_base_url: str = Field(default="https://www.themoviedb.org", alias="TMDB_WEB_BASE_URL")
    goodreads_web_base_url: str = Field(
        default="https://www.goodreads.com",
        alias="GOODREADS_WEB_BASE_URL",
    )

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="forbid",
        validate_default=True,
        case_sensitive=False,
        populate_by_name=True,
    )

    @field_validator("log_level")
    @classmethod
    def validate_log_level(cls, value: str) -> str:
        """Allow only known log levels."""
        normalized = value.upper().strip()
        allowed = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        if normalized not in allowed:
            raise ValueError(f"LOG_LEVEL must be one of: {sorted(allowed)}")
        return normalized

    @field_validator("log_format")
    @classmethod
    def validate_log_format(cls, value: str) -> str:
        """Allow only supported log output formats."""
        normalized = value.lower().strip()
        allowed = {"json", "text"}
        if normalized not in allowed:
            raise ValueError(f"LOG_FORMAT must be one of: {sorted(allowed)}")
        return normalized

    @field_validator("service_name")
    @classmethod
    def validate_service_name(cls, value: str) -> str:
        """Ensure service name is valid for logging/monitoring labels."""
        normalized = value.strip()
        if not normalized:
            raise ValueError("SERVICE_NAME cannot be empty.")
        return normalized

    @field_validator("metrics_namespace")
    @classmethod
    def validate_metrics_namespace(cls, value: str) -> str:
        """Ensure metrics namespace is non-empty and normalized."""
        normalized = value.strip().lower()
        if not normalized:
            raise ValueError("METRICS_NAMESPACE cannot be empty.")
        return normalized

    @field_validator("sentry_dsn")
    @classmethod
    def normalize_sentry_dsn(cls, value: str | None) -> str | None:
        """Treat blank SENTRY_DSN as unset."""
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None

    @field_validator("cors_allowed_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, value: str | list[str] | None) -> list[str]:
        """Parse CORS origins from comma-separated string or list."""
        if value is None:
            return []
        if isinstance(value, list):
            return [str(origin).strip() for origin in value if str(origin).strip()]
        return [origin.strip() for origin in str(value).split(",") if origin.strip()]

    @field_validator("storage_path")
    @classmethod
    def validate_storage_path(cls, value: Path) -> Path:
        """Ensure storage path is non-empty."""
        if not str(value).strip():
            raise ValueError("STORAGE_PATH cannot be empty.")
        return value

    @field_validator("yt_dlp_cookies_from_browser")
    @classmethod
    def normalize_yt_dlp_cookies_from_browser(cls, value: str | None) -> str | None:
        """Treat blank browser cookie source as disabled."""
        if value is None:
            return None
        normalized = value.strip().lower()
        return normalized or None

    @field_validator("yt_dlp_cookie_file")
    @classmethod
    def normalize_yt_dlp_cookie_file(cls, value: Path | None) -> Path | None:
        """Treat blank cookie file values as disabled."""
        if value is None:
            return None
        normalized = str(value).strip()
        if not normalized:
            return None
        return Path(normalized)

    @field_validator("ocr_language")
    @classmethod
    def validate_ocr_language(cls, value: str) -> str:
        """Normalize OCR language code."""
        normalized = value.strip().lower()
        if not normalized:
            raise ValueError("OCR_LANGUAGE cannot be empty.")
        return normalized

    @property
    def postgres_dsn(self) -> str:
        """Backward-compatible alias for legacy setting name."""
        return str(self.database_url)

    @property
    def working_directory(self) -> str:
        """Backward-compatible alias for legacy setting name."""
        return str(self.storage_path)

    @property
    def resolved_celery_broker_url(self) -> str:
        """Return configured broker URL or derive from REDIS_URL."""
        if self.celery_broker_url is not None:
            return str(self.celery_broker_url)
        return str(self.redis_url)

    @property
    def resolved_celery_result_backend(self) -> str:
        """Return configured result backend URL or derive from REDIS_URL."""
        if self.celery_result_backend is not None:
            return str(self.celery_result_backend)
        return str(self.redis_url)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Load validated settings once and reuse across the process."""
    try:
        return Settings()
    except ValidationError as exc:
        raise ConfigurationError("Invalid or missing environment configuration.") from exc
