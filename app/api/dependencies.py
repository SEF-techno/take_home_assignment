from typing import Annotated
from uuid import UUID

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import webhook_settings
from app.core.security import oauth2_scheme_user
from app.db.models import User
from app.db.redis import is_jti_blacklisted
from app.db.session import get_session
from app.services.campaign import CampaignService
from app.services.teacher import TeacherService
from app.services.user import UserService
from app.services.webhook import WebhookService
from app.utils import decode_access_token

# Reusable FastAPI dependency: gets the actual AsyncSession yielded by get_session() for each request and handles its lifecycle automatically.
SessionDep = Annotated[AsyncSession, Depends(get_session)]



### Reusable Campaign Service Dependency
async def get_campaign_service(
    session: SessionDep,
):
    return CampaignService(session)

CampaignServiceDep = Annotated[
    CampaignService,
    Depends(get_campaign_service),
]


async def get_teacher_service(session: SessionDep) -> TeacherService:
    return TeacherService(session)


TeacherServiceDep = Annotated[TeacherService, Depends(get_teacher_service)]

### Reusable User Service Dependency
async def get_user_service(
        session: SessionDep
):
    return UserService(session)

UserServiceDep = Annotated[
    UserService,
    Depends(get_user_service),
]


### User access token related - User Auth Dependency

# Access token data dependency
async def _get_access_token(token: str) -> dict:
    data = decode_access_token(token)

    # validate the token
    if data is None or await is_jti_blacklisted(data["jti"]):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Bad credentials"
        )

    return data

# user access token data
async def get_user_access_token(token: Annotated[str, Depends(oauth2_scheme_user)]):
    return await _get_access_token(token)


# Logged in user
async def get_current_user(
    token_data: Annotated[dict, Depends(get_user_access_token)], session: SessionDep
):
    user = await session.get(User, UUID(token_data["user"]["id"]))

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Bad credentials"
        )

    return user

# Reusable FastAPI dependency: provides a UserDep with its database session already injected.
UserAuthDep = Annotated[
    User,
    Depends(get_current_user),
]


### Webhook related

async def get_webhook_service(
    session: SessionDep,
) -> WebhookService:
    return WebhookService(session)


WebhookServiceDep = Annotated[
    WebhookService,
    Depends(get_webhook_service),
]


async def verify_webhook_secret(
    x_webhook_secret: Annotated[str, Header()],
):
    if x_webhook_secret != webhook_settings.WEBHOOK_SECRET:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid webhook secret",
        )
