from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.errors import NotFoundError
from app.models import Notification, User
from app.schemas.notification import NotificationOut, NotificationPage


async def list_notifications(
    session: AsyncSession, *, user: User, unread_only: bool = False, page: int = 1, size: int = 20
) -> NotificationPage:
    conditions = [Notification.user_id == user.id]
    if unread_only:
        conditions.append(Notification.is_read.is_(False))

    total = (
        await session.execute(select(func.count()).select_from(Notification).where(*conditions))
    ).scalar_one()
    # unread는 필터와 무관하게 전체를 센다 — 헤더 뱃지가 목록 조건에 따라 달라지면 안 된다.
    unread = (
        await session.execute(
            select(func.count())
            .select_from(Notification)
            .where(Notification.user_id == user.id, Notification.is_read.is_(False))
        )
    ).scalar_one()
    rows = (
        (
            await session.execute(
                select(Notification)
                .where(*conditions)
                .order_by(Notification.created_at.desc(), Notification.id.desc())
                .offset((page - 1) * size)
                .limit(size)
            )
        )
        .scalars()
        .all()
    )
    return NotificationPage(
        items=[NotificationOut.model_validate(row) for row in rows],
        total=total,
        unread=unread,
        page=page,
        size=size,
    )


async def mark_read(session: AsyncSession, *, user: User, notification_id: int) -> NotificationOut:
    notification = await session.get(Notification, notification_id)
    # 타인의 알림은 존재 자체를 알리지 않는다.
    if notification is None or notification.user_id != user.id:
        raise NotFoundError("NOTIFICATION_NOT_FOUND", "알림을 찾을 수 없습니다")
    notification.is_read = True
    await session.commit()
    return NotificationOut.model_validate(notification)
