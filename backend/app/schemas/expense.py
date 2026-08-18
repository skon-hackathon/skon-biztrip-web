from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, Field

from app.enums import ExpenseReportStatus


class ExpenseReportCreate(BaseModel):
    trip_id: int


class ExpenseReportUpdate(BaseModel):
    """헤더 FC/CC 수정. spec 5.5의 "승계되며 수정 가능하다"를 만족시키는 유일한 경로다."""

    fund_center_code: str | None = Field(default=None, min_length=1, max_length=20)
    cost_center_code: str | None = Field(default=None, min_length=1, max_length=20)


class ExpenseItemCreate(BaseModel):
    # 카드거래를 연결하면 amount_krw를 생략할 수 있다 — 거래 금액을 그대로 쓴다.
    # 수기 항목(card_transaction_id=None)은 금액이 필수이며 서비스가 400으로 막는다.
    card_transaction_id: int | None = None
    expense_category_code: str = Field(min_length=1, max_length=40)
    amount_krw: Decimal | None = None
    memo: str | None = Field(default=None, max_length=255)
    fund_center_code: str | None = Field(default=None, min_length=1, max_length=20)
    cost_center_code: str | None = Field(default=None, min_length=1, max_length=20)


class ExpenseItemUpdate(BaseModel):
    expense_category_code: str | None = Field(default=None, min_length=1, max_length=40)
    amount_krw: Decimal | None = None
    memo: str | None = Field(default=None, max_length=255)
    is_excluded: bool | None = None
    fund_center_code: str | None = Field(default=None, min_length=1, max_length=20)
    cost_center_code: str | None = Field(default=None, min_length=1, max_length=20)


class ExpenseItemOut(BaseModel):
    id: int
    card_transaction_id: int | None
    expense_category_code: str
    amount_krw: Decimal
    memo: str | None
    is_excluded: bool
    #: null이면 "리포트 값 상속". 화면의 "부서 지정" 컬럼이 이 두 필드를 본다.
    fund_center_code: str | None
    cost_center_code: str | None
    #: coalesce 결과. Agent가 상속 규칙을 다시 구현하지 않아도 되게 함께 내려준다.
    effective_fund_center_code: str | None
    effective_cost_center_code: str | None
    merchant_name: str | None
    approved_at: datetime | None


class ExpenseReportListItem(BaseModel):
    id: int
    report_no: str
    status: ExpenseReportStatus
    trip_id: int
    trip_no: str
    trip_title: str
    trip_start_date: date
    trip_end_date: date
    user_id: int
    user_name: str
    approver_id: int | None
    approver_name: str | None
    fund_center_code: str | None
    cost_center_code: str | None
    total_amount_krw: Decimal
    submitted_at: datetime | None
    approved_at: datetime | None


class ExpenseReportDetail(ExpenseReportListItem):
    reject_reason: str | None
    created_at: datetime
    updated_at: datetime
    items: list[ExpenseItemOut]


class MatchCandidateOut(BaseModel):
    transaction_id: int
    approved_at: datetime
    merchant_name: str
    merchant_category_code: str
    amount_krw: Decimal
    suggested_category_code: str
    reasons: list[str]
    #: 이미 이 리포트의 항목으로 담긴 거래. 화면이 "담기" 버튼을 비활성화한다.
    already_added: bool
