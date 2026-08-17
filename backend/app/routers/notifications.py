from typing import Annotated

from fastapi import APIRouter, Query

from app.deps import CurrentUser, DbSession
from app.schemas.notification import NotificationOut, NotificationPage
from app.services import notifications as notification_service

router = APIRouter(prefix="/api/v1/notifications", tags=["notifications"])


@router.get("", response_model=NotificationPage)
async def list_notifications(
    user: CurrentUser,
    session: DbSession,
    unread_only: bool = False,
    page: Annotated[int, Query(ge=1)] = 1,
    size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> NotificationPage:
    return await notification_service.list_notifications(
        session, user=user, unread_only=unread_only, page=page, size=size
    )


@router.post("/{notification_id}/read", response_model=NotificationOut)
async def mark_read(notification_id: int, user: CurrentUser, session: DbSession) -> NotificationOut:
    return await notification_service.mark_read(
        session, user=user, notification_id=notification_id
    )
