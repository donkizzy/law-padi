import uuid
from datetime import UTC, datetime

from pydantic import BaseModel, ConfigDict, EmailStr, field_validator
from sqlalchemy import DateTime, Index, UniqueConstraint, column, func
from sqlmodel import Field, SQLModel


def get_datetime_utc() -> datetime:
    return datetime.now(UTC)


# Shared properties
class UserBase(SQLModel):
    email: EmailStr = Field(max_length=255)
    is_active: bool = True
    is_superuser: bool = False
    full_name: str | None = Field(default=None, max_length=255)


# Properties to receive via API on creation
class UserCreate(UserBase):
    password: str = Field(min_length=8, max_length=128)


class UserRegister(SQLModel):
    email: EmailStr = Field(max_length=255)
    password: str = Field(min_length=8, max_length=128)
    full_name: str | None = Field(default=None, max_length=255)


# Properties to receive via API on update, all are optional
class UserUpdate(SQLModel):
    email: EmailStr | None = Field(default=None, max_length=255)
    is_active: bool | None = None
    is_superuser: bool | None = None
    full_name: str | None = Field(default=None, max_length=255)
    password: str | None = Field(default=None, min_length=8, max_length=128)


class UserUpdateMe(BaseModel):
    model_config = ConfigDict(extra="forbid")

    full_name: str | None = Field(default=None, max_length=255)


class EmailChangeRequest(SQLModel):
    email: EmailStr = Field(max_length=255)
    current_password: str = Field(min_length=8, max_length=128)


class AccountDeletion(SQLModel):
    current_password: str = Field(min_length=8, max_length=128)


class UpdatePassword(SQLModel):
    current_password: str = Field(min_length=8, max_length=128)
    new_password: str = Field(min_length=8, max_length=128)


# Database model, database table inferred from class name
class User(UserBase, table=True):
    __table_args__ = (
        Index("ux_user_email_lower", func.lower(column("email")), unique=True),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    hashed_password: str
    auth_version: int = Field(default=0)
    created_at: datetime | None = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
    )
    # Set once the person follows the link sent to ``email``. Cleared when the
    # address changes. Account syncing waits for it.
    email_verified_at: datetime | None = Field(
        default=None,
        sa_type=DateTime(timezone=True),  # type: ignore
    )


# Properties to return via API, id is always required
class UserPublic(UserBase):
    id: uuid.UUID
    created_at: datetime | None = None
    email_verified_at: datetime | None = None


class UsersPublic(SQLModel):
    data: list[UserPublic]
    count: int


# Generic message
class Message(SQLModel):
    message: str


# JSON payload containing access token
class Token(SQLModel):
    access_token: str
    token_type: str = "bearer"


# Contents of JWT token
class TokenPayload(SQLModel):
    sub: uuid.UUID
    auth_version: int = Field(ge=0)


class RefreshToken(SQLModel, table=True):
    """One rotating refresh token. Only a SHA-256 digest of the token is stored.

    Tokens issued from the same sign-in share a ``family_id``; presenting a
    token that was already rotated revokes the whole family.
    """

    __tablename__ = "refresh_token"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    user_id: uuid.UUID = Field(foreign_key="user.id", index=True, ondelete="CASCADE")
    family_id: uuid.UUID = Field(index=True)
    token_hash: str = Field(unique=True, max_length=64)
    auth_version: int = Field(default=0)
    created_at: datetime = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
    )
    expires_at: datetime = Field(sa_type=DateTime(timezone=True))  # type: ignore
    revoked_at: datetime | None = Field(
        default=None,
        sa_type=DateTime(timezone=True),  # type: ignore
    )


class SavedProvisionBase(SQLModel):
    canonical_path: str = Field(min_length=1, max_length=512)
    release_version: str = Field(min_length=1, max_length=128)


class SavedProvisionIn(SavedProvisionBase):
    saved_at: datetime | None = None


class SavedProvisionPublic(SavedProvisionBase):
    saved_at: datetime


class SavedProvisionsMerge(SQLModel):
    items: list[SavedProvisionIn] = Field(max_length=500)


class SavedProvision(SavedProvisionBase, table=True):
    """A section a signed-in person saved, kept in their account."""

    __tablename__ = "saved_provision"
    __table_args__ = (UniqueConstraint("user_id", "canonical_path", "release_version"),)

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    user_id: uuid.UUID = Field(foreign_key="user.id", index=True, ondelete="CASCADE")
    saved_at: datetime = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
    )


PREFERENCE_LANGUAGES = frozenset(
    {"auto", "english", "pidgin", "yoruba", "igbo", "hausa"}
)


class PreferencesBase(SQLModel):
    enter_to_send: bool = True
    follow_latest: bool = True
    open_sources: bool = False
    # The interface and answer language; None means the account has not saved
    # one, so each browser keeps its own.
    language: str | None = Field(default=None, max_length=16)

    @field_validator("language")
    @classmethod
    def _known_language(cls, value: str | None) -> str | None:
        if value is not None and value not in PREFERENCE_LANGUAGES:
            raise ValueError("Unsupported language")
        return value


class PreferencesPublic(PreferencesBase):
    pass


class UserPreferences(PreferencesBase, table=True):
    """Reading and composing preferences that follow a person between devices."""

    __tablename__ = "user_preferences"

    user_id: uuid.UUID = Field(
        foreign_key="user.id", primary_key=True, ondelete="CASCADE"
    )
    updated_at: datetime = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
    )


class EmailVerification(SQLModel):
    token: str = Field(max_length=2048)


class RateLimitCounter(SQLModel, table=True):
    """Requests seen for one rate-limit key in one fixed time window."""

    __tablename__ = "rate_limit_counter"

    key: str = Field(primary_key=True, max_length=255)
    window_start: datetime = Field(
        primary_key=True,
        sa_type=DateTime(timezone=True),  # type: ignore
    )
    count: int = 0


class NewPassword(SQLModel):
    token: str
    new_password: str = Field(min_length=8, max_length=128)


from app.legal.models import (  # noqa: E402,F401
    ActiveRetrievalTarget,
    AdminRoleAssignment,
    Amendment,
    AmendmentOperation,
    AuditEvent,
    CandidateRevision,
    ConstitutionalBill,
    Conversation,
    ConversationMessage,
    CorpusRelease,
    CorpusReleaseEntry,
    EmbeddingProfile,
    EmbeddingRun,
    EvaluationDataset,
    EvaluationItem,
    ExtractionCandidate,
    IngestionArtifact,
    IngestionEvent,
    IngestionRun,
    IngestionStep,
    IngestionTask,
    LegalConcept,
    LegalConceptAlias,
    LegalInstrument,
    LegislativeEvent,
    MessageEvidence,
    Provision,
    ProvisionVersion,
    ReleasePromotionAttempt,
    RetrievalEmbedding,
    RetrievalIndexBuild,
    RetrievalSegment,
    ReviewDecisionRecord,
    ReviewIssue,
    SourceDocument,
    SourcePage,
    SourceUpload,
    TransactionalOutbox,
)
