from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, Field

from app.enums import ActivityAction, TripStatus


class TripCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    purpose_code: str = Field(min_length=1, max_length=40)
    purpose_detail: str = Field(min_length=1)
    destination_type_code: str = Field(min_length=1, max_length=40)
    country_code: str = Field(min_length=1, max_length=40)
    city: str = Field(min_length=1, max_length=80)
    start_date: date
    end_date: date
    transport_code: str = Field(min_length=1, max_length=40)
    accommodation_code: str = Field(min_length=1, max_length=40)
    cost_center_code: str = Field(min_length=1, max_length=20)
    # ge=0 이나 max_digits를 여기에 걸지 않는다. 금액·날짜 같은 교차/도메인 제약은
    # services/trip_rules.py가 400 + 도메인 코드로 돌려주기로 통일했다. Pydantic이 먼저
    # 잡으면 422 SCHEMA_INVALID가 나가 Agent가 보는 에러 코드가 필드마다 달라진다.
    estimated_cost: Decimal


class TripUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    purpose_code: str | None = Field(default=None, min_length=1, max_length=40)
    purpose_detail: str | None = Field(default=None, min_length=1)
    destination_type_code: str | None = Field(default=None, min_length=1, max_length=40)
    country_code: str | None = Field(default=None, min_length=1, max_length=40)
    city: str | None = Field(default=None, min_length=1, max_length=80)
    start_date: date | None = None
    end_date: date | None = None
    transport_code: str | None = Field(default=None, min_length=1, max_length=40)
    accommodation_code: str | None = Field(default=None, min_length=1, max_length=40)
    cost_center_code: str | None = Field(default=None, min_length=1, max_length=20)
    estimated_cost: Decimal | None = None


class TripListItem(BaseModel):
    id: int
    trip_no: str
    title: str
    city: str
    country_code: str
    destination_type_code: str
    purpose_code: str
    start_date: date
    end_date: date
    status: TripStatus
    estimated_cost: Decimal
    user_id: int
    user_name: str
    approver_id: int | None
    approver_name: str | None


class TripDetail(TripListItem):
    purpose_detail: str
    transport_code: str
    accommodation_code: str
    cost_center_code: str
    cost_center_name: str | None
    submitted_at: datetime | None
    approved_at: datetime | None
    reject_reason: str | None
    created_at: datetime
    updated_at: datetime


class TimelineEntry(BaseModel):
    id: int
    action: ActivityAction
    from_status: str | None
    to_status: str | None
    memo: str | None
    actor_id: int
    actor_name: str
    created_at: datetime


class RejectRequest(BaseModel):
    reason: str
