from datetime import datetime

from sqlalchemy import DateTime, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from app.config import get_settings

#: `user` 테이블만 다른 스키마(기본 `public`)에 산다. 다른 프로젝트와 계정을 공유하기
#: 때문이다. 나머지 테이블은 스키마를 붙이지 않고 search_path(`DB_SCHEMA`)로 해석된다.
USER_SCHEMA = get_settings().user_db_schema

#: user를 참조하는 FK는 반드시 이 상수를 쓴다. 문자열 "user.id"로 적으면 메타데이터 키가
#: `USER_SCHEMA.user`라서 해석되지 않고 임포트 시점에 NoReferencedTableError로 죽는다.
USER_FK = f"{USER_SCHEMA}.user.id"


class Base(DeclarativeBase):
    __mapper_args__ = {"eager_defaults": True}


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
