from sqlalchemy import Boolean, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class FundCenter(Base, TimestampMixin):
    """비용처리 부서."""

    __tablename__ = "fund_center"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(20), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    department_id: Mapped[int | None] = mapped_column(ForeignKey("department.id"))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class CostCenter(Base, TimestampMixin):
    """비용사용 부서."""

    __tablename__ = "cost_center"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(20), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    department_id: Mapped[int | None] = mapped_column(ForeignKey("department.id"))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
