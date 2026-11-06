"""Owned, release-pinned conversations and replayable generation events."""

import asyncio
import hashlib
import re
import secrets
import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Annotated
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, Response
from fastapi.sse import EventSourceResponse, ServerSentEvent
from sqlalchemy import and_, or_
from sqlmodel import Session, col, func, select, update

from app.api.deps import SessionDep, authenticated_user, get_current_active_superuser
from app.chat import EXPLANATION_PROMPT_VERSION
from app.chat.events import emit_event, subscribe, unsubscribe
from app.chat.schemas import (
    ChatCapabilities,
    ChatMetrics,
    ClaimResult,
    ConversationCreate,
    ConversationDetail,
    ConversationList,
    ConversationPublic,
    ConversationUpdate,
    FeedbackCreate,
    FeedbackPublic,
    MessageAccepted,
    MessageCreate,
    MessagePublic,
)
from app.core.config import settings
from app.core.db import engine
from app.deployment.chat_dispatch import dispatch_run, stage_dispatch
from app.ingestion.pgvector_repository import PgVectorRetrievalError, active_target
from app.languages.codes import DISPLAY_NAMES
from app.legal.enums import MessageRole, VectorIndexStatus
from app.legal.models import (
    Conversation,
    ConversationMessage,
    CorpusRelease,
    CorpusReleaseEntry,
    GenerationAdmission,
    GenerationCapacity,
    GenerationEvent,
    GenerationRun,
    MessageFeedback,
    Provision,
    ProvisionVersion,
    RetrievalIndexBuild,
    get_datetime_utc,
)
from app.legal.public_corpus import published_release
from app.legal.references import matches_reference, parse_section_reference
from app.models import User
from app.retention import maybe_purge_idle_guest_conversations

router = APIRouter(prefix="/conversations", tags=["conversations"])
_COOKIE = "law_padi_guest"
_COOKIE_RE = re.compile(r"^[A-Za-z0-9_-]{40,64}$")
_LAGOS = ZoneInfo("Africa/Lagos")


@dataclass(frozen=True)
class Owner:
    user_id: uuid.UUID | None = None
    guest_digest: str | None = None
    auth_version: int | None = None


def _account(request: Request, session: Session) -> User | None:
    authorization = request.headers.get("authorization")
    if not authorization:
        return None
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise HTTPException(
            status_code=401,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    try:
        return authenticated_user(session, token)
    except HTTPException as exc:
        if exc.status_code == 401:
            raise
        raise HTTPException(
            status_code=403, detail="Could not validate credentials"
        ) from exc


def _owner(request: Request, response: Response, session: Session) -> Owner:
    user = _account(request, session)
    if user:
        return Owner(user_id=user.id, auth_version=user.auth_version)
    token = request.cookies.get(_COOKIE)
    if token is None or not _COOKIE_RE.fullmatch(token):
        token = secrets.token_urlsafe(32)
        response.set_cookie(
            _COOKIE,
            token,
            max_age=settings.GUEST_CONVERSATION_RETENTION_DAYS * 24 * 60 * 60,
            httponly=True,
            secure=settings.FASTAPI_ENV != "development",
            samesite="lax" if settings.FASTAPI_ENV == "development" else "none",
            path=f"{settings.API_V1_STR}/conversations",
        )
    return Owner(guest_digest=hashlib.sha256(token.encode()).hexdigest())


def _owned_conversation(
    session: Session, conversation_id: uuid.UUID, owner: Owner, *, lock: bool = False
) -> Conversation:
    statement = select(Conversation).where(Conversation.id == conversation_id)
    if lock:
        statement = statement.with_for_update()
    conversation = session.exec(statement).first()
    valid = bool(
        conversation
        and (
            owner.user_id is not None
            and conversation.user_id == owner.user_id
            or owner.guest_digest is not None
            and conversation.user_id is None
            and conversation.anonymous_session_id == owner.guest_digest
            and conversation.updated_at
            >= get_datetime_utc()
            - timedelta(days=settings.GUEST_CONVERSATION_RETENTION_DAYS)
        )
    )
    if not valid:
        raise HTTPException(status_code=404, detail="Conversation was not found")
    assert conversation is not None
    return conversation


def _edition_label(release: CorpusRelease) -> str:
    report = release.validation_report or {}
    review = report.get("source_edition_review", {})
    if isinstance(review, dict) and isinstance(review.get("edition"), str):
        return str(review["edition"])
    return "Published source edition"


def _public(session: Session, conversation: Conversation) -> ConversationPublic:
    release = session.get(CorpusRelease, conversation.pinned_release_id)
    if release is None:
        raise HTTPException(status_code=503, detail="Pinned edition is unavailable")
    return ConversationPublic(
        id=conversation.id,
        title=conversation.title,
        release_version=release.version,
        edition_label=_edition_label(release),
        preferred_language=conversation.preferred_language,
        created_at=conversation.created_at,
        updated_at=conversation.updated_at,
    )


def _ensure_chat_enabled() -> None:
    if not settings.CHAT_ENABLED:
        raise HTTPException(status_code=503, detail="Conversations are not enabled")


@router.get("/capabilities")
def read_chat_capabilities() -> ChatCapabilities:
    """Report product availability independently of conversation history."""
    return ChatCapabilities(
        conversations_enabled=settings.CHAT_ENABLED,
        explanations_enabled=settings.explanations_enabled,
        supported_languages=[
            DISPLAY_NAMES[language] for language in settings.CHAT_LANGUAGES_ENABLED
        ],
        answer_languages=list(settings.CHAT_LANGUAGES_ENABLED),
        build_revision=settings.BUILD_REVISION,
        prompt_version=EXPLANATION_PROMPT_VERSION,
    )


@router.get("/metrics", dependencies=[Depends(get_current_active_superuser)])
def read_chat_metrics(session: SessionDep) -> ChatMetrics:
    """Aggregate quality signals without exposing questions or answer text."""
    since = get_datetime_utc() - timedelta(hours=24)
    rows = session.exec(
        select(GenerationRun.outcome, func.count())
        .where(GenerationRun.created_at >= since)
        .group_by(GenerationRun.outcome)
    ).all()
    outcomes = {outcome or "in_progress": count for outcome, count in rows}
    average = session.exec(
        select(
            func.avg(
                func.extract(
                    "epoch",
                    col(GenerationRun.updated_at) - col(GenerationRun.created_at),
                )
                * 1000
            )
        ).where(
            GenerationRun.created_at >= since, col(GenerationRun.outcome).is_not(None)
        )
    ).one()
    ratings = dict(
        session.exec(
            select(MessageFeedback.helpful, func.count())
            .where(MessageFeedback.updated_at >= since)
            .group_by(col(MessageFeedback.helpful))
        ).all()
    )
    return ChatMetrics(
        accepted_questions=sum(outcomes.values()),
        finished_answers=sum(
            count for outcome, count in outcomes.items() if outcome != "in_progress"
        ),
        explained_answers=outcomes.get("completed", 0)
        + outcomes.get("partial_evidence", 0),
        average_finish_ms=float(average) if average is not None else None,
        outcomes=outcomes,
        helpful_ratings=ratings.get(True, 0),
        unhelpful_ratings=ratings.get(False, 0),
    )


@router.post("", response_model=ConversationPublic, status_code=201)
def create_conversation(
    body: ConversationCreate,
    request: Request,
    response: Response,
    session: SessionDep,
) -> ConversationPublic:
    _ensure_chat_enabled()
    maybe_purge_idle_guest_conversations(session)
    owner = _owner(request, response, session)
    release = published_release(session, release_version=body.release_version)
    if body.release_version:
        build = session.exec(
            select(RetrievalIndexBuild)
            .where(
                RetrievalIndexBuild.release_id == release.id,
                RetrievalIndexBuild.index_kind == "enacted",
                RetrievalIndexBuild.status == VectorIndexStatus.READY,
            )
            .order_by(col(RetrievalIndexBuild.created_at).desc())
        ).first()
        if build is None:
            raise HTTPException(
                status_code=503, detail="Pinned edition has no ready search index"
            )
        build_id = build.id
    else:
        target = active_target(session)
        if target.release_id != release.id:
            raise PgVectorRetrievalError(
                "Active release changed during conversation creation"
            )
        build_id = target.retrieval_index_build_id
    conversation = Conversation(
        user_id=owner.user_id,
        anonymous_session_id=owner.guest_digest,
        title=body.title.strip() if body.title else None,
        pinned_release_id=release.id,
        pinned_index_build_id=build_id,
        preferred_language=body.preferred_language,
    )
    session.add(conversation)
    public = ConversationPublic(
        id=conversation.id,
        title=conversation.title,
        release_version=release.version,
        edition_label=_edition_label(release),
        preferred_language=conversation.preferred_language,
        created_at=conversation.created_at,
        updated_at=conversation.updated_at,
    )
    session.commit()
    return public


@router.get("", response_model=ConversationList)
def list_conversations(
    request: Request,
    response: Response,
    session: SessionDep,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 30,
    q: Annotated[str | None, Query(max_length=200)] = None,
) -> ConversationList:
    _ensure_chat_enabled()
    owner = _owner(request, response, session)
    if owner.user_id:
        predicate = col(Conversation.user_id) == owner.user_id
    else:
        predicate = and_(
            col(Conversation.anonymous_session_id) == owner.guest_digest,
            col(Conversation.user_id).is_(None),
            col(Conversation.updated_at)
            >= get_datetime_utc()
            - timedelta(days=settings.GUEST_CONVERSATION_RETENTION_DAYS),
        )
    if q and q.strip():
        escaped = (
            q.strip().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        )
        predicate = and_(
            predicate, col(Conversation.title).ilike(f"%{escaped}%", escape="\\")
        )
    count = session.exec(
        select(func.count()).select_from(Conversation).where(predicate)
    ).one()
    rows = session.exec(
        select(Conversation)
        .where(predicate)
        .order_by(col(Conversation.updated_at).desc(), col(Conversation.id))
        .offset(offset)
        .limit(limit)
    ).all()
    return ConversationList(data=[_public(session, row) for row in rows], count=count)


@router.get("/{conversation_id}", response_model=ConversationDetail)
def read_conversation(
    conversation_id: uuid.UUID,
    request: Request,
    response: Response,
    session: SessionDep,
    before: Annotated[uuid.UUID | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> ConversationDetail:
    _ensure_chat_enabled()
    conversation = _owned_conversation(
        session, conversation_id, _owner(request, response, session)
    )
    message_query = select(ConversationMessage).where(
        ConversationMessage.conversation_id == conversation.id
    )
    if before is not None:
        cursor = session.get(ConversationMessage, before)
        if cursor is None or cursor.conversation_id != conversation.id:
            raise HTTPException(status_code=404, detail="Message cursor was not found")
        message_query = message_query.where(
            or_(
                col(ConversationMessage.created_at) < cursor.created_at,
                and_(
                    col(ConversationMessage.created_at) == cursor.created_at,
                    col(ConversationMessage.id) < cursor.id,
                ),
            )
        )
    descending = session.exec(
        message_query.order_by(
            col(ConversationMessage.created_at).desc(),
            col(ConversationMessage.id).desc(),
        ).limit(limit + 1)
    ).all()
    has_more = len(descending) > limit
    messages = list(reversed(descending[:limit]))
    feedback = (
        {
            row.message_id: row.helpful
            for row in session.exec(
                select(MessageFeedback).where(
                    col(MessageFeedback.message_id).in_(
                        [message.id for message in messages]
                    )
                )
            ).all()
        }
        if messages
        else {}
    )
    active_run = session.exec(
        select(GenerationRun.id).where(
            GenerationRun.conversation_id == conversation.id,
            col(GenerationRun.status).in_(["pending", "running"]),
        )
    ).first()
    detail = ConversationDetail(
        **_public(session, conversation).model_dump(),
        active_run_id=active_run,
        has_more_messages=has_more,
        next_before=messages[0].id if has_more and messages else None,
        messages=[
            MessagePublic(
                id=message.id,
                role=str(message.role),
                content=message.content,
                answer_status=str(message.answer_status)
                if message.answer_status
                else None,
                answer_content=message.answer_content,
                evidence_snapshot=message.evidence_snapshot,
                created_at=message.created_at,
                helpful=feedback.get(message.id),
            )
            for message in messages
        ],
    )
    # A user returning after a lost enqueue should not wait for the hourly scan.
    # Release the read transaction before Cloud Tasks publication.
    session.commit()
    if active_run is not None:
        dispatch_run(active_run)
    return detail


@router.patch("/{conversation_id}", response_model=ConversationPublic)
def rename_conversation(
    conversation_id: uuid.UUID,
    body: ConversationUpdate,
    request: Request,
    response: Response,
    session: SessionDep,
) -> ConversationPublic:
    _ensure_chat_enabled()
    conversation = _owned_conversation(
        session, conversation_id, _owner(request, response, session)
    )
    title = body.title.strip()
    if not title:
        raise HTTPException(status_code=422, detail="Enter a title")
    conversation.title = title
    conversation.updated_at = get_datetime_utc()
    session.add(conversation)
    public = _public(session, conversation)
    session.commit()
    return public


@router.delete("/{conversation_id}", status_code=204)
def delete_conversation(
    conversation_id: uuid.UUID,
    request: Request,
    response: Response,
    session: SessionDep,
) -> None:
    _ensure_chat_enabled()
    conversation = _owned_conversation(
        session, conversation_id, _owner(request, response, session), lock=True
    )
    active = session.exec(
        select(GenerationRun).where(
            GenerationRun.conversation_id == conversation.id,
            col(GenerationRun.status).in_(["pending", "running"]),
        )
    ).first()
    if active:
        capacity = session.exec(
            select(GenerationCapacity)
            .where(GenerationCapacity.id == 1)
            .with_for_update()
        ).one()
        capacity.active_count = max(0, capacity.active_count - 1)
        session.add(capacity)
    session.delete(conversation)
    session.commit()


@router.post("/{conversation_id}/messages/{message_id}/feedback")
def submit_message_feedback(
    conversation_id: uuid.UUID,
    message_id: uuid.UUID,
    body: FeedbackCreate,
    request: Request,
    response: Response,
    session: SessionDep,
) -> FeedbackPublic:
    _ensure_chat_enabled()
    owner = _owner(request, response, session)
    _owned_conversation(session, conversation_id, owner, lock=True)
    message = session.get(ConversationMessage, message_id)
    if (
        message is None
        or message.conversation_id != conversation_id
        or message.role != MessageRole.ASSISTANT
    ):
        raise HTTPException(status_code=404, detail="Answer was not found")
    feedback = session.get(MessageFeedback, message_id)
    if feedback is None:
        feedback = MessageFeedback(message_id=message_id, helpful=body.helpful)
    else:
        feedback.helpful = body.helpful
        feedback.updated_at = get_datetime_utc()
    session.add(feedback)
    session.commit()
    session.refresh(feedback)
    return FeedbackPublic.model_validate(feedback)


@router.post("/claim", response_model=ClaimResult)
def claim_guest_conversations(
    request: Request, response: Response, session: SessionDep
) -> ClaimResult:
    _ensure_chat_enabled()
    user = _account(request, session)
    if user is None:
        raise HTTPException(status_code=401, detail="Sign in to claim conversations")
    if user.email_verified_at is None:
        raise HTTPException(
            status_code=403,
            detail="Confirm your email address to keep your research in your account.",
        )
    token = request.cookies.get(_COOKIE)
    if token is None or not _COOKIE_RE.fullmatch(token):
        return ClaimResult(claimed_count=0)
    digest = hashlib.sha256(token.encode()).hexdigest()
    rows = session.exec(
        select(Conversation)
        .where(
            Conversation.anonymous_session_id == digest,
            col(Conversation.user_id).is_(None),
            Conversation.updated_at
            >= get_datetime_utc()
            - timedelta(days=settings.GUEST_CONVERSATION_RETENTION_DAYS),
        )
        .with_for_update()
    ).all()
    for conversation in rows:
        conversation.user_id = user.id
        conversation.anonymous_session_id = None
        session.add(conversation)
    if rows:
        session.flush()
        _lock_generation_capacity(session)
        # Keep original guest attribution so replay of that cookie still uses
        # its allowance. The claimed runs also count against the account.
        session.exec(
            update(GenerationAdmission)
            .where(
                col(GenerationAdmission.guest_digest) == digest,
                col(GenerationAdmission.user_id).is_(None),
                col(GenerationAdmission.run_id).in_(
                    select(GenerationRun.id)
                    .join(Conversation)
                    .where(Conversation.user_id == user.id)
                ),
            )
            .values(user_id=user.id)
        )
    session.commit()
    response.delete_cookie(_COOKIE, path=f"{settings.API_V1_STR}/conversations")
    return ClaimResult(claimed_count=len(rows))


def _lock_generation_capacity(session: Session) -> GenerationCapacity:
    return session.exec(
        select(GenerationCapacity).where(GenerationCapacity.id == 1).with_for_update()
    ).one()


def _admission_counts(session: Session, owner: Owner, now: datetime) -> tuple[int, int]:
    today = now.astimezone(_LAGOS).date()
    day_start = datetime.combine(today, datetime.min.time(), _LAGOS).astimezone(UTC)
    day_end = day_start + timedelta(days=1)
    minute_start = now - timedelta(minutes=1)
    owner_filter = (
        GenerationAdmission.user_id == owner.user_id
        if owner.user_id
        else GenerationAdmission.guest_digest == owner.guest_digest
    )
    created_at = col(GenerationAdmission.created_at)
    daily, recent = session.exec(
        select(
            func.count().filter(created_at >= day_start, created_at < day_end),
            func.count().filter(created_at >= minute_start),
        )
        .select_from(GenerationAdmission)
        .where(owner_filter, created_at >= min(day_start, minute_start))
    ).one()
    return daily, recent


def _validate_selected_version(
    session: Session,
    conversation: Conversation,
    question: str,
    version_id: uuid.UUID | None,
) -> None:
    if version_id is None:
        return
    version = session.get(ProvisionVersion, version_id)
    provision = session.get(Provision, version.provision_id) if version else None
    entry = session.exec(
        select(CorpusReleaseEntry).where(
            CorpusReleaseEntry.release_id == conversation.pinned_release_id,
            CorpusReleaseEntry.provision_version_id == version_id,
        )
    ).first()
    if (
        version is None
        or provision is None
        or entry is None
        or (str(version.legal_status) == "proposed")
        != (conversation.index_kind == "proposals")
    ):
        raise HTTPException(
            status_code=422, detail="Selected provision is not in this edition"
        )
    parsed = parse_section_reference(question)
    if parsed.error or (
        parsed.references
        and not any(
            matches_reference(provision.canonical_path, reference)
            for reference in parsed.references
        )
    ):
        raise HTTPException(
            status_code=422, detail="Selected provision does not match the question"
        )


@router.post(
    "/{conversation_id}/messages", response_model=MessageAccepted, status_code=202
)
def submit_message(
    conversation_id: uuid.UUID,
    body: MessageCreate,
    request: Request,
    response: Response,
    session: SessionDep,
) -> MessageAccepted:
    _ensure_chat_enabled()
    if not settings.explanations_enabled:
        raise HTTPException(
            status_code=503, detail="Explanations are temporarily unavailable"
        )
    owner = _owner(request, response, session)
    conversation = _owned_conversation(session, conversation_id, owner, lock=True)
    question = body.question.strip()
    if not question:
        raise HTTPException(status_code=422, detail="Enter a question")
    existing = session.exec(
        select(GenerationRun).where(
            GenerationRun.conversation_id == conversation.id,
            GenerationRun.idempotency_key == body.idempotency_key,
        )
    ).first()
    if existing:
        prior = session.get(ConversationMessage, existing.user_message_id)
        if (
            prior is None
            or prior.content != question
            or existing.selected_provision_version_id
            != body.selected_provision_version_id
        ):
            raise HTTPException(
                status_code=409,
                detail="Submission key was used for a different question",
            )
        accepted = MessageAccepted(
            run_id=existing.id,
            user_message_id=existing.user_message_id,
            status=existing.status,
        )
        session.commit()
        dispatch_run(accepted.run_id)
        return accepted
    _validate_selected_version(
        session, conversation, question, body.selected_provision_version_id
    )
    active = session.exec(
        select(GenerationRun).where(
            GenerationRun.conversation_id == conversation.id,
            col(GenerationRun.status).in_(["pending", "running"]),
        )
    ).first()
    if active:
        raise HTTPException(
            status_code=409,
            detail="An explanation is already active in this conversation",
        )
    # The shared row lock also serializes daily allowance checks across this
    # owner's different conversations before a new run is committed.
    capacity = _lock_generation_capacity(session)
    now = get_datetime_utc()
    daily_count, recent_count = _admission_counts(session, owner, now)
    limit = (
        settings.CHAT_ACCOUNT_DAILY_LIMIT
        if owner.user_id
        else settings.CHAT_GUEST_DAILY_LIMIT
    )
    if daily_count >= limit:
        raise HTTPException(
            status_code=429, detail="Daily explanation allowance reached"
        )
    burst_limit = (
        settings.CHAT_ACCOUNT_BURST_LIMIT
        if owner.user_id
        else settings.CHAT_GUEST_BURST_LIMIT
    )
    if recent_count >= burst_limit:
        raise HTTPException(
            status_code=429, detail="Too many explanations in one minute"
        )
    # Use live rows because account deletion can cascade runs without touching
    # the cached counter. The lock prevents two admissions from overbooking.
    active_count = session.exec(
        select(func.count())
        .select_from(GenerationRun)
        .where(col(GenerationRun.status).in_(["pending", "running"]))
    ).one()
    if active_count >= settings.CHAT_MAX_ACTIVE_GENERATIONS:
        raise HTTPException(status_code=429, detail="Generation capacity is full")
    capacity.active_count = active_count + 1
    message = ConversationMessage(
        conversation_id=conversation.id, role=MessageRole.USER, content=question
    )
    session.add(message)
    session.flush()
    run = GenerationRun(
        conversation_id=conversation.id,
        user_message_id=message.id,
        idempotency_key=body.idempotency_key,
        selected_provision_version_id=body.selected_provision_version_id,
        answer_language=body.answer_language,
        created_at=now,
    )
    session.add(run)
    session.add(
        GenerationAdmission(
            run_id=run.id,
            user_id=owner.user_id,
            guest_digest=owner.guest_digest,
            created_at=now,
        )
    )
    session.flush()
    stage_dispatch(session, run)
    emit_event(
        session,
        run,
        "message.started",
        {"run_id": str(run.id), "message_id": str(message.id)},
    )
    conversation.updated_at = now
    if conversation.title is None:
        conversation.title = question[:120]
    session.add(conversation)
    session.add(capacity)
    accepted = MessageAccepted(
        run_id=run.id, user_message_id=message.id, status=run.status
    )
    session.commit()
    dispatch_run(accepted.run_id)
    return accepted


@router.post("/{conversation_id}/runs/{run_id}/cancel", response_model=MessageAccepted)
def cancel_run(
    conversation_id: uuid.UUID,
    run_id: uuid.UUID,
    request: Request,
    response: Response,
    session: SessionDep,
) -> MessageAccepted:
    _ensure_chat_enabled()
    _owned_conversation(
        session, conversation_id, _owner(request, response, session), lock=True
    )
    run = session.exec(
        select(GenerationRun)
        .where(
            GenerationRun.id == run_id, GenerationRun.conversation_id == conversation_id
        )
        .with_for_update()
    ).first()
    if run is None:
        raise HTTPException(status_code=404, detail="Generation run was not found")
    if run.status == "pending":
        run.status = "cancelled"
        run.outcome = "cancelled"
        capacity = session.exec(
            select(GenerationCapacity)
            .where(GenerationCapacity.id == 1)
            .with_for_update()
        ).one()
        capacity.active_count = max(0, capacity.active_count - 1)
        session.add(capacity)
        emit_event(session, run, "answer.complete", {"outcome": "cancelled"})
    elif run.status == "running":
        run.cancellation_requested = True
    session.add(run)
    result = MessageAccepted(
        run_id=run.id, user_message_id=run.user_message_id, status=run.status
    )
    session.commit()
    return result


def _read_events(
    conversation_id: uuid.UUID,
    owner: Owner,
    after_id: int,
    run_id: uuid.UUID | None = None,
) -> tuple[list[GenerationEvent], bool]:
    with Session(engine) as session:
        if owner.user_id is not None:
            user = session.get(User, owner.user_id)
            if (
                user is None
                or not user.is_active
                or user.auth_version != owner.auth_version
            ):
                return [], False
        try:
            _owned_conversation(session, conversation_id, owner)
        except HTTPException:
            return [], False
        event_query = select(GenerationEvent).where(
            GenerationEvent.conversation_id == conversation_id,
            col(GenerationEvent.id) > after_id,
        )
        if run_id is not None:
            event_query = event_query.where(GenerationEvent.run_id == run_id)
        events = session.exec(
            event_query.order_by(col(GenerationEvent.id)).limit(100)
        ).all()
        active_query = select(GenerationRun.id).where(
            GenerationRun.conversation_id == conversation_id,
            col(GenerationRun.status).in_(["pending", "running"]),
        )
        if run_id is not None:
            active_query = active_query.where(GenerationRun.id == run_id)
        active = session.exec(active_query).first() is not None
        return list(events), active


@dataclass(frozen=True)
class EventAccess:
    owner: Owner
    cursor: int


def _event_access(
    conversation_id: uuid.UUID,
    request: Request,
    response: Response,
    session: SessionDep,
    last_event_id: Annotated[str | None, Header(alias="Last-Event-ID")] = None,
    run_id: Annotated[uuid.UUID | None, Query()] = None,
) -> EventAccess:
    _ensure_chat_enabled()
    try:
        cursor = int(last_event_id) if last_event_id else 0
        if cursor < 0:
            raise ValueError
    except ValueError:
        raise HTTPException(status_code=422, detail="Invalid Last-Event-ID")
    # Streaming connections may stay open for minutes. Close the ownership
    # transaction before yielding, then use short catch-up reads per wakeup.
    owner = _owner(request, response, session)
    _owned_conversation(session, conversation_id, owner)
    if run_id is not None:
        run = session.get(GenerationRun, run_id)
        if run is None or run.conversation_id != conversation_id:
            raise HTTPException(status_code=404, detail="Generation run was not found")
    else:
        run_id = session.exec(
            select(GenerationRun.id).where(
                GenerationRun.conversation_id == conversation_id,
                col(GenerationRun.status).in_(["pending", "running"]),
            )
        ).first()
    session.commit()
    if run_id is not None:
        dispatch_run(run_id)
    return EventAccess(owner=owner, cursor=cursor)


@router.get("/{conversation_id}/events", response_class=EventSourceResponse)
async def conversation_events(
    conversation_id: uuid.UUID,
    request: Request,
    access: Annotated[EventAccess, Depends(_event_access)],
    run_id: Annotated[uuid.UUID | None, Query()] = None,
) -> AsyncIterator[ServerSentEvent]:
    cursor = access.cursor
    wake = subscribe(conversation_id)
    try:
        while not await request.is_disconnected():
            wake.clear()
            events, active = await asyncio.to_thread(
                _read_events, conversation_id, access.owner, cursor, run_id
            )
            for event in events:
                if event.id is None:
                    continue
                cursor = event.id
                yield ServerSentEvent(
                    data=event.payload, event=event.event_type, id=str(event.id)
                )
            if not active:
                break
            try:
                await asyncio.wait_for(wake.wait(), timeout=15)
            except TimeoutError:
                pass
    finally:
        unsubscribe(conversation_id, wake)
