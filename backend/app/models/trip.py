from datetime import date, datetime

from sqlalchemy import Date, DateTime, Enum as SAEnum, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.enums import TripStatus
from app.models.base import Base, TimestampMixin


class Trip(Base, TimestampMixin):
    __tablename__ = "trip"

    id: Mapped[int] = mapped_column(primary_key=True)
    trip_no: Mapped[str] = mapped_column(String(20), unique=True, nullable=False, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("user.id"), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    purpose_code: Mapped[str] = mapped_column(String(40), nullable=False)
    purpose_detail: Mapped[str] = mapped_column(Text, nullable=False)
    destination_type_code: Mapped[str] = mapped_column(String(40), nullable=False)
    country_code: Mapped[str] = mapped_column(String(40), nullable=False)
    city: Mapped[str] = mapped_column(String(80), nullable=False)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    # 출장 신청 화면에서 코스트센터를 받지 않으므로 nullable이다. 정산서가 이 값을
    # 승계하며(services/expenses.py), 비어 있으면 사용자가 정산 화면에서 고른다 —
    # 제출 시 assert_centers_present가 빈 CC를 거부하므로 검증이 빠지지는 않는다.
    cost_center_code: Mapped[str | None] = mapped_column(String(20))
    status: Mapped[TripStatus] = mapped_column(
        SAEnum(TripStatus, name="trip_status"), default=TripStatus.DRAFT, nullable=False, index=True
    )
    approver_id: Mapped[int | None] = mapped_column(ForeignKey("user.id"))
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    reject_reason: Mapped[str | None] = mapped_column(Text)
