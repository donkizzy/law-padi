from fastapi import APIRouter

from app.api.errors import ErrorResponse, ValidationErrorResponse
from app.api.routes import (
    account,
    admin,
    conversations,
    login,
    private,
    search,
    users,
    utils,
)
from app.core.config import settings

api_router = APIRouter(
    responses={
        **{
            status: {"model": ErrorResponse}
            for status in (400, 401, 403, 404, 409, 429, 503)
        },
        422: {"model": ErrorResponse | ValidationErrorResponse},
    }
)
api_router.include_router(login.router)
api_router.include_router(users.router)
api_router.include_router(account.router)
api_router.include_router(utils.router)
api_router.include_router(admin.router)
api_router.include_router(search.router)
api_router.include_router(conversations.router)


if settings.FASTAPI_ENV == "development":
    api_router.include_router(private.router)
