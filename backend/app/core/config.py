import os
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

from app.languages.codes import Language


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        # Use top level .env file (one level above ./backend/)
        env_file="../.env",
        env_ignore_empty=True,
        extra="ignore",
    )
    API_V1_STR: str = "/api/v1"
    SECRET_KEY: str
    # Access tokens live in browser memory only; the refresh cookie renews them.
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30
    # A rotated refresh token presented again within this window is treated as a
    # benign race (two tabs, a lost response) rather than token theft.
    REFRESH_TOKEN_REUSE_GRACE_SECONDS: int = 10
    FRONTEND_HOST: str = "http://localhost:5173"
    FASTAPI_ENV: Literal["development"] | None = None

    PROJECT_NAME: str
    BUILD_REVISION: str = "development"
    SERVE_FRONTEND: bool = True
    ORIGIN_PROXY_SECRET: str | None = None
    APP_RUNTIME_ROLE: Literal["api"] | None = None
    SENTRY_DSN: HttpUrl | None = None
    SENTRY_TRACES_SAMPLE_RATE: float = Field(default=0.05, ge=0, le=1)
    DATABASE_URL: PostgresDsn
    DATABASE_LISTENER_URL: PostgresDsn | None = None
    DATABASE_CONNECT_TIMEOUT_SECONDS: int = Field(default=15, ge=1, le=60)
    DATABASE_STATEMENT_TIMEOUT_MS: int = Field(default=0, ge=0)
    DATABASE_LOCK_TIMEOUT_MS: int = Field(default=0, ge=0)
    INGESTION_STORAGE_BACKEND: Literal["local", "r2"] = "local"
    INGESTION_STORAGE_DIR: str = "storage/source-documents"
    INGESTION_ALLOWED_INSTRUMENT_TYPES: list[Literal["constitution", "act"]] = [
        "constitution"
    ]
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
    EMBEDDING_QUERY_ENABLED: bool = True
    # Paid query embeddings per UTC day across the deployment. Past it, search
    # uses keyword ranking until the next day.
    QUERY_EMBEDDING_DAILY_LIMIT: int = Field(default=5000, ge=0)
    RETRIEVAL_INDEX_BACKEND: Literal["pgvector"] = "pgvector"
    RETRIEVAL_VECTOR_DIMENSIONS: int = Field(default=1024, ge=1)
    RETRIEVAL_DENSE_CANDIDATE_LIMIT: int = Field(default=50, ge=1)
    RETRIEVAL_LEXICAL_CANDIDATE_LIMIT: int = Field(default=50, ge=1)
    RETRIEVAL_RRF_K: int = Field(default=60, ge=1)
    # Keyword ranking is far weaker than dense ranking on everyday questions;
    # at full weight it pushed correct dense matches out of first place, and
    # without dense ranking it overrode the topic guide's curated order.
    # Measured with scripts/retrieval_benchmark.py.
    RETRIEVAL_LEXICAL_WEIGHT: float = Field(default=0.15, ge=0)
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
    # Guest cookies are free to replace, so guest-tier explanations (guests and
    # unconfirmed accounts) are also counted per client IP. Mobile carriers
    # share addresses, so these sit well above the per-guest limits.
    CHAT_GUEST_IP_DAILY_LIMIT: int = Field(default=30, ge=0)
    CHAT_GUEST_IP_BURST_LIMIT: int = Field(default=3, ge=0)
    DATABASE_POOL_SIZE: int = Field(default=40, ge=1, le=100)
    DATABASE_GATE_WAIT_SECONDS: float = Field(default=10, gt=0)
    CHAT_DAILY_BUDGET_USD: float = Field(default=100.0, ge=0)
    CHAT_MONTHLY_BUDGET_USD: float = Field(default=4.0, ge=0)
    AI_MONTHLY_BUDGET_USD: float = Field(default=5.0, ge=0)
    CHAT_DISPATCH_MODE: Literal["poll"] = "poll"
    CHAT_EVIDENCE_MAX_CHARS: int = Field(default=36000, ge=1000)
    DEEPSEEK_API_KEY: str | None = None
    DEEPSEEK_BASE_URL: str = "https://api.deepseek.com"
    DEEPSEEK_MODEL: str = "deepseek-flash"
    # Flash peak-hour rates; off-peak is half, so budgets never under-count.
    DEEPSEEK_INPUT_USD_PER_MILLION: float = Field(default=0.30, ge=0)
    DEEPSEEK_OUTPUT_USD_PER_MILLION: float = Field(default=1.20, ge=0)
    DEEPSEEK_MAX_OUTPUT_TOKENS: int = Field(default=2000, ge=1)
    # Thinking tokens count toward the output limit, so each stage has its own.
    # The verifier reasons in its JSON instead: with thinking it used its whole
    # budget before answering.
    DEEPSEEK_GENERATION_THINKING: bool = True
    DEEPSEEK_VERIFIER_THINKING: bool = False
    DEEPSEEK_GENERATION_MAX_OUTPUT_TOKENS: int = Field(default=8000, ge=1)
    DEEPSEEK_VERIFIER_MAX_OUTPUT_TOKENS: int = Field(default=4000, ge=1)
    DEEPSEEK_TIMEOUT_SECONDS: float = Field(default=120.0, gt=0)
    CHAT_RUN_TIMEOUT_SECONDS: int = Field(default=270, ge=60)
    # Reader languages whose answers are enabled. English answers are always
    # produced; other languages are translated from the verified English answer.
    # Translations stay labelled as beta until native-speaker review.
    CHAT_LANGUAGES_ENABLED: list[Language] = list(Language)
    # Search queries longer than this are searched as typed, untranslated.
    SEARCH_TRANSLATION_MAX_CHARS: int = Field(default=300, ge=1, le=2000)
    SEARCH_TRANSLATION_MAX_OUTPUT_TOKENS: int = Field(default=600, ge=1)
    # Search is anonymous, so its paid query understanding draws on its own
    # slice of the daily budget and can never starve chat explanations.
    SEARCH_TRANSLATION_DAILY_BUDGET_USD: float = Field(default=0.5, ge=0)
    TRANSLATION_PROVIDER: Literal["deepseek"] = "deepseek"
    # Yorùbá and Igbo tone marks use far more tokens than the English answer.
    TRANSLATION_MAX_OUTPUT_TOKENS: int = Field(default=6000, ge=1)
    INGESTION_WORKER_LEASE_SECONDS: int = Field(default=900, ge=1)
    MANAGED_OCR_PROVIDER: Literal[
        "disabled", "google_document_ai", "azure_document_intelligence"
    ] = "disabled"
    GOOGLE_DOCUMENT_AI_PROCESSOR_NAME: str | None = None
    GOOGLE_DOCUMENT_AI_ACCESS_TOKEN: str | None = None
    AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT: str | None = None
    AZURE_DOCUMENT_INTELLIGENCE_KEY: str | None = None
    AZURE_DOCUMENT_INTELLIGENCE_MODEL_ID: str = "prebuilt-layout"
    AZURE_DOCUMENT_INTELLIGENCE_API_VERSION: str = "2024-11-30"

    @property
    def explanations_enabled(self) -> bool:
        return (
            self.CHAT_ENABLED
            and self.CHAT_GENERATION_ENABLED
            and not self.CHAT_GENERATION_KILL_SWITCH
        )

    @field_validator("CHAT_LANGUAGES_ENABLED")
    @classmethod
    def _english_always_enabled(cls, value: list[Language]) -> list[Language]:
        return [Language.ENGLISH, *(lang for lang in value if lang != Language.ENGLISH)]

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
    EMAIL_VERIFICATION_TOKEN_EXPIRE_HOURS: int = 48
    # Guest conversations idle this long are hidden, then deleted.
    GUEST_CONVERSATION_RETENTION_DAYS: int = 30
    # Postgres-backed request limits on sign-in, sign-up and recovery routes.
    RATE_LIMIT_ENABLED: bool = True

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
        if self.APP_RUNTIME_ROLE == "api" and len(self.ORIGIN_PROXY_SECRET or "") < 32:
            raise ValueError(
                "The hosted API requires an ORIGIN_PROXY_SECRET of at least 32 characters"
            )
        if self.APP_RUNTIME_ROLE is not None and self.FASTAPI_ENV == "development":
            raise ValueError("Hosted runtimes cannot use FASTAPI_ENV=development")
        if (
            self.CHAT_MAX_ACTIVE_GENERATIONS > 500
            and not self.CHAT_PROVIDER_CAPACITY_APPROVED
        ):
            raise ValueError(
                "CHAT_PROVIDER_CAPACITY_APPROVED is required above the documented DeepSeek concurrency limit"
            )
        return self


settings = Settings(_env_file=os.environ.get("APP_RUNTIME_ENV_FILE", "../.env"))  # type: ignore
