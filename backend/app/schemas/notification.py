from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.enums import NotificationType
from app.schemas.common import Page


class NotificationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    type: NotificationType
    title: str
    body: str
    link_url: str | None
    is_read: bool
    created_at: datetime


class NotificationPage(Page[NotificationOut]):
    #: 읽지 않은 **전체** 개수. 헤더의 뱃지가 목록을 다시 세지 않게 하려고 봉투에 싣는다.
    unread: int
