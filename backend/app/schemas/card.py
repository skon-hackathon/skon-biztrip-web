from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict


class CardOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    card_no_masked: str
    brand: str
    is_active: bool


class CardTransactionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    card_id: int
    approved_at: datetime
    merchant_name: str
    merchant_category_code: str
    amount: Decimal
    currency_code: str
    amount_krw: Decimal
    is_cancelled: bool
    # 업종에서 추천한 정산 비목. 서비스가 services/matching.suggest_expense_category로
    # 채운다 — 화면이 업종→비목 매핑을 따로 가지면 자동매칭이 추천하는 비목과 카드내역
    # 피커가 추천하는 비목이 갈라진다.
    suggested_expense_category_code: str
