from datetime import datetime

from pydantic import BaseModel, Field

from app.enums import ApiKeyScope

#: 만료 최대치. 무제한 키를 허용하되(만료 없음), 숫자를 넣을 거면 상식적인 범위로 막는다.
MAX_EXPIRES_DAYS = 365


class ApiKeyCreate(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    # 스코프는 문자열로 받고 서비스가 검증한다. 여기서 Enum으로 강제하면 오타가
    # 422 SCHEMA_INVALID로 떨어져 "어떤 값이 유효한지"를 알려주지 못한다.
    scopes: list[str]
    expires_in_days: int | None = Field(default=None, ge=1, le=MAX_EXPIRES_DAYS)


class ApiKeyOut(BaseModel):
    id: int
    name: str
    key_prefix: str
    scopes: list[str]
    state: str
    last_used_at: datetime | None
    expires_at: datetime | None
    revoked_at: datetime | None
    created_at: datetime


class ApiKeyCreated(ApiKeyOut):
    """발급 직후에만 존재하는 응답. `key`는 이 응답 이후 어디에도 남지 않는다."""

    key: str


class ScopeInfo(BaseModel):
    scope: ApiKeyScope
    description: str
    endpoints: list[str]
