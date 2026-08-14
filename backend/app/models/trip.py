from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Date, DateTime, Enum as SAEnum, ForeignKey, Numeric, String, Text
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
    transport_code: Mapped[str] = mapped_column(String(40), nullable=False)
    accommodation_code: Mapped[str] = mapped_column(String(40), nullable=False)
    cost_center_code: Mapped[str] = mapped_column(String(20), nullable=False)
    estimated_cost: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    status: Mapped[TripStatus] = mapped_column(
        SAEnum(TripStatus, name="trip_status"), default=TripStatus.DRAFT, nullable=False, index=True
    )
    approver_id: Mapped[int | None] = mapped_column(ForeignKey("user.id"))
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    reject_reason: Mapped[str | None] = mapped_column(Text)
