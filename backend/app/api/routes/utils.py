from fastapi import APIRouter, Depends, HTTPException, status
from pydantic.networks import EmailStr
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.api.deps import SessionDep, get_current_active_superuser
from app.core.config import settings
from app.models import Message
from app.utils import generate_test_email, send_email

router = APIRouter(prefix="/utils", tags=["utils"])


@router.post(
    "/test-email/",
    dependencies=[Depends(get_current_active_superuser)],
    status_code=201,
)
def test_email(email_to: EmailStr) -> Message:
    """
    Test emails.
    """
    email_data = generate_test_email(email_to=email_to)
    send_email(
        email_to=email_to,
        subject=email_data.subject,
        html_content=email_data.html_content,
    )
    return Message(message="Test email sent")


@router.get("/health-check/")
def health_check(session: SessionDep) -> dict[str, bool]:
    """Verify the database and the configured retrieval backend are usable.

    The probe is public, so it reports readiness only, never versions.
    """
    try:
        session.connection().execute(text("SELECT 1"))
        if settings.RETRIEVAL_INDEX_BACKEND == "pgvector" and not (
            session.connection()
            .execute(text("SELECT 1 FROM pg_extension WHERE extname = 'vector'"))
            .scalar_one_or_none()
        ):
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Service is not ready",
            )
    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Service is not ready",
        ) from exc
    return {"ok": True}
