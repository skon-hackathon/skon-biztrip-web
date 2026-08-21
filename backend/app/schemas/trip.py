from datetime import date, datetime

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


class TripUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    purpose_code: str | None = Field(default=None, min_length=1, max_length=40)
    purpose_detail: str | None = Field(default=None, min_length=1)
    destination_type_code: str | None = Field(default=None, min_length=1, max_length=40)
    country_code: str | None = Field(default=None, min_length=1, max_length=40)
    city: str | None = Field(default=None, min_length=1, max_length=80)
    start_date: date | None = None
    end_date: date | None = None


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
    user_id: int
    user_name: str
    approver_id: int | None
    approver_name: str | None


class TripDetail(TripListItem):
    purpose_detail: str
    # 출장 신청에서 받지 않는 값이다. 시드 데이터에만 들어 있고 새 출장은 비어 있다.
    cost_center_code: str | None
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
