from enum import StrEnum


class TripStatus(StrEnum):
    DRAFT = "DRAFT"
    SUBMITTED = "SUBMITTED"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    COMPLETED = "COMPLETED"
    SETTLED = "SETTLED"


class ExpenseReportStatus(StrEnum):
    DRAFT = "DRAFT"
    SUBMITTED = "SUBMITTED"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class UserRole(StrEnum):
    EMPLOYEE = "EMPLOYEE"
    MANAGER = "MANAGER"
    ADMIN = "ADMIN"


class UserStatus(StrEnum):
    """가입 신청의 생애주기.

    `is_active`(로그인 가능 여부)와 의미가 겹치지 않는다. 불변식은 단방향이다 —
    `status != ACTIVE`이면 반드시 `is_active = false`이지만, 역은 성립하지 않는다.
    승인된 뒤 관리자가 정지시킨 사용자가 `status=ACTIVE` + `is_active=false`이며,
    그것이 "승인 대기"와 구분되어야 하는 경우다.

    공통코드 테이블이 아니라 Python Enum인 이유는 role과 같다 — 가입·승인·로그인
    분기에 박히는 값이므로 관리자가 편집할 수 있으면 안 된다.
    """

    PENDING = "PENDING"
    ACTIVE = "ACTIVE"
    REJECTED = "REJECTED"


# 값이 멤버명과 다르다 (TRIPS_READ -> "trips:read"). API 스코프 문자열 그대로를 쓰기 때문.
# 저장은 ARRAY(String)으로 한다 — SAEnum으로 매핑하면 값 대신 멤버명이 저장되어 깨진다.
class ApiKeyScope(StrEnum):
    TRIPS_READ = "trips:read"
    TRIPS_WRITE = "trips:write"
    EXPENSES_READ = "expenses:read"
    EXPENSES_WRITE = "expenses:write"
    CARDS_READ = "cards:read"
    ADMIN = "admin"


class NotificationType(StrEnum):
    TRIP_SUBMITTED = "TRIP_SUBMITTED"
    TRIP_APPROVED = "TRIP_APPROVED"
    TRIP_REJECTED = "TRIP_REJECTED"
    EXPENSE_SUBMITTED = "EXPENSE_SUBMITTED"
    EXPENSE_APPROVED = "EXPENSE_APPROVED"
    EXPENSE_REJECTED = "EXPENSE_REJECTED"


class ActivityAction(StrEnum):
    CREATED = "CREATED"
    UPDATED = "UPDATED"
    SUBMITTED = "SUBMITTED"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    COMPLETED = "COMPLETED"
    SETTLED = "SETTLED"


class EntityType(StrEnum):
    TRIP = "TRIP"
    EXPENSE_REPORT = "EXPENSE_REPORT"
