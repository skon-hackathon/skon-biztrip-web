from sqlalchemy import Boolean, Enum as SAEnum, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.enums import ActivityAction, EntityType, NotificationType
from app.models.base import Base, TimestampMixin


class Notification(Base, TimestampMixin):
    __tablename__ = "notification"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("user.id"), nullable=False, index=True)
    type: Mapped[NotificationType] = mapped_column(
        SAEnum(NotificationType, name="notification_type"), nullable=False
    )
    title: Mapped[str] = mapped_column(String(120), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    link_url: Mapped[str | None] = mapped_column(String(200))
    is_read: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)


class ActivityLog(Base, TimestampMixin):
    __tablename__ = "activity_log"
    __table_args__ = (
        # 타임라인 조회는 항상 entity_type + entity_id로 필터하고 created_at 순으로 읽으므로
        # 세 컬럼을 모두 포함하는 복합 인덱스 하나로 커버한다 (단일 컬럼 인덱스 두 개 대신).
        Index("ix_activity_log_entity", "entity_type", "entity_id", "created_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    entity_type: Mapped[EntityType] = mapped_column(
        SAEnum(EntityType, name="entity_type"), nullable=False
    )
    entity_id: Mapped[int] = mapped_column(Integer, nullable=False)
    actor_id: Mapped[int] = mapped_column(ForeignKey("user.id"), nullable=False)
    action: Mapped[ActivityAction] = mapped_column(
        SAEnum(ActivityAction, name="activity_action"), nullable=False
    )
    from_status: Mapped[str | None] = mapped_column(String(30))
    to_status: Mapped[str | None] = mapped_column(String(30))
    memo: Mapped[str | None] = mapped_column(Text)
