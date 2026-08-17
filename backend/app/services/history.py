"""상태 전이 이력과 알림을 함께 남기는 단일 지점 (spec 5.8).

전이를 수행하는 서비스 함수는 반드시 이 함수를 호출한다. 두 테이블에 따로 쓰게 두면
언젠가 한쪽을 빠뜨리고, 그러면 "웹으로 하면 알림이 오는데 API로 하면 안 온다" 같은
경로별 불일치가 생긴다.
"""

from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from app.enums import ActivityAction, EntityType, NotificationType
from app.models import ActivityLog, Notification


@dataclass(frozen=True)
class NotifySpec:
    user_id: int
    type: NotificationType
    title: str
    body: str
    link_url: str | None = None


async def record_transition(
    session: AsyncSession,
    *,
    entity_type: EntityType,
    entity_id: int,
    actor_id: int,
    action: ActivityAction,
    from_status: str | None = None,
    to_status: str | None = None,
    memo: str | None = None,
    notify: NotifySpec | None = None,
) -> None:
    session.add(
        ActivityLog(
            entity_type=entity_type,
            entity_id=entity_id,
            actor_id=actor_id,
            action=action,
            from_status=from_status,
            to_status=to_status,
            memo=memo,
        )
    )
    # 자기가 한 일을 자기에게 알리지 않는다. ADMIN이 자기 출장을 스스로 결재하는
    # 데모 시나리오에서 실제로 발생한다.
    if notify is not None and notify.user_id != actor_id:
        session.add(
            Notification(
                user_id=notify.user_id,
                type=notify.type,
                title=notify.title,
                body=notify.body,
                link_url=notify.link_url,
            )
        )
    await session.flush()
