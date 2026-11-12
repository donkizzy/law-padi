from datetime import timedelta
from unittest.mock import patch

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.core import security
from app.core.config import settings
from app.models import (
    SavedProvision,
    User,
    UserPreferences,
    get_datetime_utc,
)
from tests.utils.user import create_random_user

SAVED = f"{settings.API_V1_STR}/account/saved-provisions"
PREFERENCES = f"{settings.API_V1_STR}/account/preferences"


def _headers(db: Session, *, verified: bool = True) -> tuple[User, dict[str, str]]:
    user = create_random_user(db)
    if verified:
        user.email_verified_at = get_datetime_utc()
        db.add(user)
        db.commit()
    token = security.create_access_token(user.id, timedelta(minutes=5))
    return user, {"Authorization": f"Bearer {token}"}


def _item(path: str, release: str = "2024") -> dict[str, str]:
    return {"canonical_path": path, "release_version": release}


def test_sync_needs_a_confirmed_email(client: TestClient, db: Session) -> None:
    _, headers = _headers(db, verified=False)
    for response in (
        client.get(SAVED, headers=headers),
        client.put(SAVED, headers=headers, json=_item("s/1")),
        client.get(PREFERENCES, headers=headers),
    ):
        assert response.status_code == 403
        assert response.json()["detail"].startswith("Confirm your email address")


def test_sync_needs_sign_in(client: TestClient) -> None:
    assert client.get(SAVED).status_code == 401


def test_save_list_and_remove(client: TestClient, db: Session) -> None:
    _, headers = _headers(db)
    assert client.get(SAVED, headers=headers).json() == []

    assert client.put(SAVED, headers=headers, json=_item("s/37")).status_code == 200
    # Saving twice is harmless.
    assert client.put(SAVED, headers=headers, json=_item("s/37")).status_code == 200
    saved = client.get(SAVED, headers=headers).json()
    assert [(row["canonical_path"], row["release_version"]) for row in saved] == [
        ("s/37", "2024")
    ]

    r = client.delete(SAVED, headers=headers, params=_item("s/37"))
    assert r.status_code == 200
    assert client.get(SAVED, headers=headers).json() == []
    # Removing again is harmless too.
    assert (
        client.delete(SAVED, headers=headers, params=_item("s/37")).status_code == 200
    )


def test_merge_adds_browser_bookmarks_and_keeps_existing_dates(
    client: TestClient, db: Session
) -> None:
    _, headers = _headers(db)
    client.put(
        SAVED,
        headers=headers,
        json={**_item("s/33"), "saved_at": "2026-01-01T00:00:00Z"},
    )
    r = client.post(
        f"{SAVED}/merge",
        headers=headers,
        json={
            "items": [
                {**_item("s/33"), "saved_at": "2026-09-01T00:00:00Z"},
                {**_item("s/35"), "saved_at": "2026-05-01T00:00:00Z"},
            ]
        },
    )
    assert r.status_code == 200
    rows = r.json()
    assert [row["canonical_path"] for row in rows] == ["s/33", "s/35"]
    assert rows[0]["saved_at"].startswith("2026-01-01")


def test_accounts_only_see_their_own_saved_sections(
    client: TestClient, db: Session
) -> None:
    _, first = _headers(db)
    _, second = _headers(db)
    client.put(SAVED, headers=first, json=_item("s/40"))
    assert client.get(SAVED, headers=second).json() == []
    client.delete(SAVED, headers=second, params=_item("s/40"))
    assert len(client.get(SAVED, headers=first).json()) == 1


def test_saved_sections_are_capped(client: TestClient, db: Session) -> None:
    _, headers = _headers(db)
    with patch("app.api.routes.account.MAX_SAVED_PROVISIONS", 2):
        client.put(SAVED, headers=headers, json=_item("s/1"))
        client.put(SAVED, headers=headers, json=_item("s/2"))
        r = client.put(SAVED, headers=headers, json=_item("s/3"))
    assert r.status_code == 409


def test_preferences_start_empty_then_round_trip(
    client: TestClient, db: Session
) -> None:
    _, headers = _headers(db)
    assert client.get(PREFERENCES, headers=headers).json() is None
    body = {
        "enter_to_send": False,
        "follow_latest": True,
        "open_sources": True,
        "language": "yoruba",
    }
    r = client.put(PREFERENCES, headers=headers, json=body)
    assert r.status_code == 200
    assert r.json() == body
    assert client.get(PREFERENCES, headers=headers).json() == body


def test_saving_without_a_language_keeps_the_saved_language(
    client: TestClient, db: Session
) -> None:
    _, headers = _headers(db)
    client.put(
        PREFERENCES,
        headers=headers,
        json={
            "enter_to_send": True,
            "follow_latest": True,
            "open_sources": False,
            "language": "hausa",
        },
    )
    older_client = {
        "enter_to_send": False,
        "follow_latest": True,
        "open_sources": False,
    }
    r = client.put(PREFERENCES, headers=headers, json=older_client)
    assert r.status_code == 200
    assert r.json() == {**older_client, "language": "hausa"}


def test_unknown_preference_language_is_rejected(
    client: TestClient, db: Session
) -> None:
    _, headers = _headers(db)
    r = client.put(
        PREFERENCES,
        headers=headers,
        json={
            "enter_to_send": True,
            "follow_latest": True,
            "open_sources": False,
            "language": "french",
        },
    )
    assert r.status_code == 422


def test_deleting_an_account_deletes_its_research(
    client: TestClient, db: Session
) -> None:
    user, headers = _headers(db)
    user_id = user.id
    client.put(SAVED, headers=headers, json=_item("s/1"))
    client.put(
        PREFERENCES,
        headers=headers,
        json={"enter_to_send": True, "follow_latest": True, "open_sources": False},
    )
    user.hashed_password = security.get_password_hash("account-password")
    db.add(user)
    db.commit()
    r = client.request(
        "DELETE",
        f"{settings.API_V1_STR}/users/me",
        headers=headers,
        json={"current_password": "account-password"},
    )
    assert r.status_code == 200
    db.expire_all()
    assert db.get(User, user_id) is None
    remaining = db.exec(
        select(SavedProvision).where(SavedProvision.user_id == user_id)
    ).all()
    assert remaining == []
    assert db.get(UserPreferences, user_id) is None
