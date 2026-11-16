from fastapi.testclient import TestClient
from sqlmodel import Session, func, select

from app import crud
from app.core.config import settings
from app.models import User, UserCreate
from tests.utils.utils import random_email, random_lower_string

API = settings.API_V1_STR


def test_email_case_does_not_create_or_hide_an_account(
    client: TestClient, db: Session
) -> None:
    email = random_email()
    password = random_lower_string()
    crud.create_user(session=db, user_create=UserCreate(email=email, password=password))
    shouted = email.upper()

    signed_in = client.post(
        f"{API}/login/access-token", data={"username": shouted, "password": password}
    )
    assert signed_in.status_code == 200

    signup = client.post(
        f"{API}/users/signup",
        json={"email": shouted, "password": random_lower_string()},
    )
    assert signup.status_code == 200
    count = db.exec(
        select(func.count()).select_from(User).where(func.lower(User.email) == email)
    ).one()
    assert count == 1
