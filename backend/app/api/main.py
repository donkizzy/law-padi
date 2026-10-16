from fastapi import APIRouter

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

api_router = APIRouter()
api_router.include_router(login.router)
api_router.include_router(users.router)
api_router.include_router(account.router)
api_router.include_router(utils.router)
api_router.include_router(admin.router)
api_router.include_router(search.router)
api_router.include_router(conversations.router)


if settings.FASTAPI_ENV == "development":
    api_router.include_router(private.router)
