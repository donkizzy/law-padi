"""Research that follows a signed-in person between devices.

Every route needs a confirmed email address: syncing is what verification
unlocks.
"""

from datetime import datetime
from typing import Annotated, Any

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import JSONResponse
from sqlalchemy.dialects.postgresql import insert
from sqlmodel import Session, col, delete, func, select

from app.api.deps import CurrentUser, SessionDep, VerifiedUser
from app.legal.models import Conversation, ConversationMessage
from app.models import (
    Message,
    PreferencesBase,
    PreferencesPublic,
    SavedProvision,
    SavedProvisionIn,
    SavedProvisionPublic,
    SavedProvisionsMerge,
    User,
    UserPreferences,
    get_datetime_utc,
)

router = APIRouter(prefix="/account", tags=["account"])

MAX_SAVED_PROVISIONS = 2000


def _saved(session: Session, user: User) -> list[SavedProvisionPublic]:
    rows = session.exec(
        select(SavedProvision)
        .where(SavedProvision.user_id == user.id)
        .order_by(col(SavedProvision.saved_at))
    ).all()
    return [SavedProvisionPublic.model_validate(row) for row in rows]


def _add(session: Session, user: User, items: list[SavedProvisionIn]) -> None:
    if not items:
        return
    count = session.exec(
        select(func.count()).where(SavedProvision.user_id == user.id)
    ).one()
    if count + len(items) > MAX_SAVED_PROVISIONS:
        raise HTTPException(
            status_code=409,
            detail=f"You can keep up to {MAX_SAVED_PROVISIONS} saved sections.",
        )
    now = get_datetime_utc()
    session.exec(
        insert(SavedProvision)
        .values(
            [
                {
                    "user_id": user.id,
                    "canonical_path": item.canonical_path,
                    "release_version": item.release_version,
                    "saved_at": item.saved_at or now,
                }
                for item in items
            ]
        )
        .on_conflict_do_nothing(
            index_elements=["user_id", "canonical_path", "release_version"]
        )
    )
    session.commit()


@router.get("/saved-provisions", response_model=list[SavedProvisionPublic])
def read_saved_provisions(
    session: SessionDep, user: VerifiedUser
) -> list[SavedProvisionPublic]:
    """Sections saved to this account, oldest first."""
    return _saved(session, user)


@router.put("/saved-provisions", response_model=Message)
def save_provision(
    session: SessionDep, user: VerifiedUser, body: SavedProvisionIn
) -> Message:
    """Save one section. Saving it again changes nothing."""
    _add(session, user, [body])
    return Message(message="Saved")


@router.delete("/saved-provisions", response_model=Message)
def remove_saved_provision(
    session: SessionDep,
    user: VerifiedUser,
    canonical_path: Annotated[str, Query(min_length=1, max_length=512)],
    release_version: Annotated[str, Query(min_length=1, max_length=128)],
) -> Message:
    """Remove one saved section. Removing one that isn't saved is fine."""
    session.exec(
        delete(SavedProvision).where(
            col(SavedProvision.user_id) == user.id,
            col(SavedProvision.canonical_path) == canonical_path,
            col(SavedProvision.release_version) == release_version,
        )
    )
    session.commit()
    return Message(message="Removed")


@router.post("/saved-provisions/merge", response_model=list[SavedProvisionPublic])
def merge_saved_provisions(
    session: SessionDep, user: VerifiedUser, body: SavedProvisionsMerge
) -> list[SavedProvisionPublic]:
    """
    Add sections saved on this browser before signing in, then return the
    account's full list. Sections already saved keep their original date.
    """
    _add(session, user, body.items)
    return _saved(session, user)


def _iso(value: datetime | None) -> str | None:
    return value.isoformat() if value else None


@router.get("/export")
def export_account_data(session: SessionDep, user: CurrentUser) -> JSONResponse:
    """
    Everything this account holds, as a JSON download: profile, saved sections,
    preferences and conversations with their messages.
    """
    conversations: list[dict[str, Any]] = []
    for conversation in session.exec(
        select(Conversation)
        .where(Conversation.user_id == user.id)
        .order_by(col(Conversation.created_at))
    ).all():
        messages = session.exec(
            select(ConversationMessage)
            .where(ConversationMessage.conversation_id == conversation.id)
            .order_by(col(ConversationMessage.created_at))
        ).all()
        conversations.append(
            {
                "id": str(conversation.id),
                "title": conversation.title,
                "created_at": _iso(conversation.created_at),
                "updated_at": _iso(conversation.updated_at),
                "messages": [
                    {
                        "role": str(message.role),
                        "content": message.content,
                        "created_at": _iso(message.created_at),
                    }
                    for message in messages
                ],
            }
        )
    preferences = session.get(UserPreferences, user.id)
    data = {
        "exported_at": _iso(get_datetime_utc()),
        "account": {
            "email": user.email,
            "full_name": user.full_name,
            "created_at": _iso(user.created_at),
            "email_verified_at": _iso(user.email_verified_at),
        },
        "preferences": (
            PreferencesPublic.model_validate(preferences).model_dump()
            if preferences
            else None
        ),
        "saved_sections": [
            item.model_dump(mode="json") for item in _saved(session, user)
        ],
        "conversations": conversations,
    }
    return JSONResponse(
        data,
        headers={
            "Content-Disposition": 'attachment; filename="constitution-ng-account.json"',
            "Cache-Control": "no-store",
        },
    )


@router.get("/preferences", response_model=PreferencesPublic | None)
def read_preferences(session: SessionDep, user: VerifiedUser) -> UserPreferences | None:
    """This account's preferences, or null if none have been saved yet."""
    return session.get(UserPreferences, user.id)


@router.put("/preferences", response_model=PreferencesPublic)
def save_preferences(
    session: SessionDep, user: VerifiedUser, body: PreferencesBase
) -> UserPreferences:
    preferences = session.get(UserPreferences, user.id) or UserPreferences(
        user_id=user.id
    )
    preferences.sqlmodel_update(body.model_dump())
    preferences.updated_at = get_datetime_utc()
    session.add(preferences)
    session.commit()
    session.refresh(preferences)
    return preferences
