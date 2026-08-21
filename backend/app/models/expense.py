from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum as SAEnum,
    ForeignKey,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.enums import ExpenseReportStatus
from app.models.base import USER_FK, Base, TimestampMixin


class CorporateCard(Base, TimestampMixin):
    __tablename__ = "corporate_card"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey(USER_FK), nullable=False, index=True)
    card_no_masked: Mapped[str] = mapped_column(String(30), nullable=False)
    brand: Mapped[str] = mapped_column(String(30), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class CardTransaction(Base, TimestampMixin):
    __tablename__ = "card_transaction"

    id: Mapped[int] = mapped_column(primary_key=True)
    card_id: Mapped[int] = mapped_column(ForeignKey("corporate_card.id"), nullable=False, index=True)
    approved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    merchant_name: Mapped[str] = mapped_column(String(120), nullable=False)
    merchant_category_code: Mapped[str] = mapped_column(String(40), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    currency_code: Mapped[str] = mapped_column(String(10), nullable=False)
    amount_krw: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    is_cancelled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)


class ExpenseReport(Base, TimestampMixin):
    __tablename__ = "expense_report"

    id: Mapped[int] = mapped_column(primary_key=True)
    report_no: Mapped[str] = mapped_column(String(20), unique=True, nullable=False, index=True)
    trip_id: Mapped[int] = mapped_column(ForeignKey("trip.id"), unique=True, nullable=False)
    user_id: Mapped[int] = mapped_column(ForeignKey(USER_FK), nullable=False, index=True)
    status: Mapped[ExpenseReportStatus] = mapped_column(
        SAEnum(ExpenseReportStatus, name="expense_report_status"),
        default=ExpenseReportStatus.DRAFT,
        nullable=False,
        index=True,
    )
    fund_center_code: Mapped[str | None] = mapped_column(String(20))
    cost_center_code: Mapped[str | None] = mapped_column(String(20))
    # 비정규화 값: expense_item.amount_krw 합계와 항상 일치해야 한다.
    # 서비스 레이어(Task 9 / Phase 3)가 항목 추가·수정·삭제 시마다 재계산해서 갱신할 책임을 진다.
    total_amount_krw: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=Decimal("0"), nullable=False)
    approver_id: Mapped[int | None] = mapped_column(ForeignKey(USER_FK))
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    reject_reason: Mapped[str | None] = mapped_column(Text)


class ExpenseItem(Base, TimestampMixin):
    __tablename__ = "expense_item"
    __table_args__ = (
        UniqueConstraint("report_id", "card_transaction_id", name="uq_expense_item_report_txn"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    report_id: Mapped[int] = mapped_column(ForeignKey("expense_report.id"), nullable=False, index=True)
    card_transaction_id: Mapped[int | None] = mapped_column(ForeignKey("card_transaction.id"))
    expense_category_code: Mapped[str] = mapped_column(String(40), nullable=False)
    amount_krw: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    memo: Mapped[str | None] = mapped_column(String(255))
    is_excluded: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    fund_center_code: Mapped[str | None] = mapped_column(String(20))
    cost_center_code: Mapped[str | None] = mapped_column(String(20))
