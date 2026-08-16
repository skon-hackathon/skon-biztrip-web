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
