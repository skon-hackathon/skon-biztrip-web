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
