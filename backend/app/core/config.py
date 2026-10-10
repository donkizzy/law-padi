import warnings
from typing import Literal, Self

from pydantic import (
    EmailStr,
    Field,
    HttpUrl,
    PostgresDsn,
    computed_field,
    field_validator,
    model_validator,
)
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        # Use top level .env file (one level above ./backend/)
        env_file="../.env",
        env_ignore_empty=True,
        extra="ignore",
    )
    API_V1_STR: str = "/api/v1"
    SECRET_KEY: str
    # 60 minutes * 24 hours * 8 days = 8 days
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 8
    FRONTEND_HOST: str = "http://localhost:5173"
    FASTAPI_ENV: Literal["development"] | None = None

    PROJECT_NAME: str
    SENTRY_DSN: HttpUrl | None = None
    DATABASE_URL: PostgresDsn
    INGESTION_STORAGE_BACKEND: Literal["local", "r2"] = "local"
    INGESTION_STORAGE_DIR: str = "storage/source-documents"
    INGESTION_STAGE_CONCURRENCY_LIMITS: dict[str, int] = Field(default_factory=dict)
    MALWARE_SCANNER_BACKEND: Literal["static_pdf", "clamav"] = "static_pdf"
    CLAMAV_HOST: str = "127.0.0.1"
    CLAMAV_PORT: int = 3310
    CLAMAV_TIMEOUT_SECONDS: float = 15.0
    R2_ENDPOINT_URL: str | None = None
    R2_BUCKET_NAME: str | None = None
    R2_ACCESS_KEY_ID: str | None = None
    R2_SECRET_ACCESS_KEY: str | None = None
    OPENAI_API_KEY: str | None = None
    HUGGINGFACE_TEI_ENDPOINT_URL: str | None = None
    HUGGINGFACE_API_TOKEN: str | None = None
    RETRIEVAL_INDEX_BACKEND: Literal["pgvector", "qdrant"] = "pgvector"
    RETRIEVAL_VECTOR_DIMENSIONS: int = Field(default=1024, ge=1)
    RETRIEVAL_DENSE_CANDIDATE_LIMIT: int = Field(default=50, ge=1)
    RETRIEVAL_LEXICAL_CANDIDATE_LIMIT: int = Field(default=50, ge=1)
    RETRIEVAL_RRF_K: int = Field(default=60, ge=1)
    RETRIEVAL_LEXICAL_PROFILE_VERSION: str = "postgres-simple-v1"
    CITATION_LOOKUP_ENABLED: bool = True
    CHAT_ENABLED: bool = False
    CHAT_GENERATION_ENABLED: bool = False
    CHAT_GENERATION_KILL_SWITCH: bool = False
    CHAT_MAX_ACTIVE_GENERATIONS: int = Field(default=100, ge=1, le=1000)
    CHAT_WORKER_CONCURRENCY: int = Field(default=16, ge=1, le=1000)
    CHAT_PROVIDER_CAPACITY_APPROVED: bool = False
    CHAT_GUEST_DAILY_LIMIT: int = Field(default=20, ge=0)
    CHAT_ACCOUNT_DAILY_LIMIT: int = Field(default=200, ge=0)
    CHAT_GUEST_BURST_LIMIT: int = Field(default=3, ge=0)
    CHAT_ACCOUNT_BURST_LIMIT: int = Field(default=10, ge=0)
    DATABASE_POOL_SIZE: int = Field(default=40, ge=1, le=100)
    CHAT_DAILY_BUDGET_USD: float = Field(default=100.0, ge=0)
    CHAT_EVIDENCE_MAX_CHARS: int = Field(default=24000, ge=1000)
    DEEPSEEK_API_KEY: str | None = None
    DEEPSEEK_BASE_URL: str = "https://api.deepseek.com"
    DEEPSEEK_MODEL: str = "deepseek-v4-pro"
    DEEPSEEK_INPUT_USD_PER_MILLION: float = Field(default=1.32, ge=0)
    DEEPSEEK_OUTPUT_USD_PER_MILLION: float = Field(default=3.96, ge=0)
    DEEPSEEK_MAX_OUTPUT_TOKENS: int = Field(default=2000, ge=1)
    INGESTION_WORKER_LEASE_SECONDS: int = Field(default=900, ge=1)
    QDRANT_URL: str | None = None
    QDRANT_API_KEY: str | None = None
    MANAGED_OCR_PROVIDER: Literal[
        "disabled", "google_document_ai", "azure_document_intelligence"
    ] = "disabled"
    GOOGLE_DOCUMENT_AI_PROCESSOR_NAME: str | None = None
    GOOGLE_DOCUMENT_AI_ACCESS_TOKEN: str | None = None
    AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT: str | None = None
    AZURE_DOCUMENT_INTELLIGENCE_KEY: str | None = None
    AZURE_DOCUMENT_INTELLIGENCE_MODEL_ID: str = "prebuilt-layout"
    AZURE_DOCUMENT_INTELLIGENCE_API_VERSION: str = "2024-11-30"

    @field_validator("DATABASE_URL", mode="before")
    @classmethod
    def _use_psycopg_driver(cls, value: str | PostgresDsn) -> str:
        database_url = str(value)
        for scheme in ("postgres://", "postgresql://"):
            if database_url.startswith(scheme):
                return database_url.replace(scheme, "postgresql+psycopg://", 1)
        return database_url

    SMTP_TLS: bool = True
    SMTP_SSL: bool = False
    SMTP_PORT: int = 587
    SMTP_HOST: str | None = None
    SMTP_USER: str | None = None
    SMTP_PASSWORD: str | None = None
    EMAILS_FROM_EMAIL: EmailStr | None = None
    EMAILS_FROM_NAME: str | None = None

    @model_validator(mode="after")
    def _set_default_emails_from(self) -> Self:
        if not self.EMAILS_FROM_NAME:
            self.EMAILS_FROM_NAME = self.PROJECT_NAME
        return self

    EMAIL_RESET_TOKEN_EXPIRE_HOURS: int = 48

    @computed_field  # type: ignore[prop-decorator]
    @property
    def emails_enabled(self) -> bool:
        return bool(self.SMTP_HOST and self.EMAILS_FROM_EMAIL)

    EMAIL_TEST_USER: EmailStr = "test@example.com"
    FIRST_SUPERUSER: EmailStr
    FIRST_SUPERUSER_PASSWORD: str

    def _check_default_secret(self, var_name: str, value: str | None) -> None:
        if value == "changethis":
            message = (
                f'The value of {var_name} is "changethis", '
                "for security, please change it, at least for deployments."
            )
            if self.FASTAPI_ENV == "development":
                warnings.warn(message, stacklevel=1)
            else:
                raise ValueError(message)

    @model_validator(mode="after")
    def _enforce_non_default_secrets(self) -> Self:
        self._check_default_secret("SECRET_KEY", self.SECRET_KEY)
        for host in self.DATABASE_URL.hosts():
            self._check_default_secret("DATABASE_URL password", host["password"])
        self._check_default_secret(
            "FIRST_SUPERUSER_PASSWORD", self.FIRST_SUPERUSER_PASSWORD
        )
        if (
            self.CHAT_MAX_ACTIVE_GENERATIONS > 500
            and not self.CHAT_PROVIDER_CAPACITY_APPROVED
        ):
            raise ValueError(
                "CHAT_PROVIDER_CAPACITY_APPROVED is required above the documented DeepSeek Pro limit"
            )

        return self


settings = Settings()  # type: ignore
