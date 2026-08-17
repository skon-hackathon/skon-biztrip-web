from datetime import date
from decimal import Decimal

import pytest

from app.enums import TripStatus, UserRole
from app.errors import ConflictError, ForbiddenError, ValidationError
from app.services.trip_rules import (
    EDITABLE_STATUSES,
    MAX_ESTIMATED_COST,
    assert_completable,
    assert_date_range,
    assert_deletable,
    assert_editable,
    assert_estimated_cost,
    assert_has_approver,
    assert_reject_reason,
    assert_trip_approver,
    assert_trip_owner,
    can_view_trip,
)


def test_date_range_accepts_same_day():
    assert_date_range(start_date=date(2026, 9, 1), end_date=date(2026, 9, 1))


def test_date_range_rejects_end_before_start():
    with pytest.raises(ValidationError) as exc_info:
        assert_date_range(start_date=date(2026, 9, 3), end_date=date(2026, 9, 1))

    error = exc_info.value
    assert error.status_code == 400
    assert error.code == "INVALID_DATE_RANGE"
    assert error.field == "end_date"


def test_estimated_cost_accepts_zero():
    assert_estimated_cost(Decimal("0"))


def test_estimated_cost_rejects_negative():
    with pytest.raises(ValidationError) as exc_info:
        assert_estimated_cost(Decimal("-1"))

    assert exc_info.value.code == "INVALID_AMOUNT"
    assert exc_info.value.field == "estimated_cost"


def test_estimated_cost_accepts_max():
    assert_estimated_cost(MAX_ESTIMATED_COST)


def test_estimated_cost_rejects_over_max():
    with pytest.raises(ValidationError) as exc_info:
        assert_estimated_cost(MAX_ESTIMATED_COST + Decimal("0.01"))

    assert exc_info.value.code == "INVALID_AMOUNT"
    assert exc_info.value.field == "estimated_cost"


@pytest.mark.parametrize("role", [UserRole.EMPLOYEE, UserRole.MANAGER])
def test_owner_and_approver_can_view(role):
    assert can_view_trip(user_id=1, role=role, owner_id=1, approver_id=9) is True
    assert can_view_trip(user_id=9, role=role, owner_id=1, approver_id=9) is True
    assert can_view_trip(user_id=5, role=role, owner_id=1, approver_id=9) is False


def test_admin_can_view_anything():
    assert can_view_trip(user_id=5, role=UserRole.ADMIN, owner_id=1, approver_id=9) is True


def test_can_view_handles_missing_approver():
    assert can_view_trip(user_id=1, role=UserRole.EMPLOYEE, owner_id=1, approver_id=None) is True
    assert can_view_trip(user_id=2, role=UserRole.EMPLOYEE, owner_id=1, approver_id=None) is False


def test_assert_trip_owner_allows_owner():
    assert_trip_owner(user_id=1, owner_id=1)


def test_assert_trip_owner_rejects_other_user():
    with pytest.raises(ForbiddenError) as exc_info:
        assert_trip_owner(user_id=2, owner_id=1)

    assert exc_info.value.status_code == 403
    assert exc_info.value.code == "NOT_TRIP_OWNER"


def test_assert_trip_approver_allows_approver():
    assert_trip_approver(user_id=9, approver_id=9)


def test_assert_trip_approver_rejects_other_user():
    with pytest.raises(ForbiddenError) as exc_info:
        assert_trip_approver(user_id=2, approver_id=9)

    assert exc_info.value.code == "NOT_TRIP_APPROVER"


def test_assert_trip_approver_rejects_unassigned_trip():
    with pytest.raises(ForbiddenError):
        assert_trip_approver(user_id=2, approver_id=None)


@pytest.mark.parametrize("status", [TripStatus.DRAFT, TripStatus.REJECTED])
def test_editable_statuses(status):
    assert_editable(status)


@pytest.mark.parametrize("status", sorted(set(TripStatus) - EDITABLE_STATUSES))
def test_non_editable_statuses(status):
    with pytest.raises(ConflictError) as exc_info:
        assert_editable(status)

    assert exc_info.value.status_code == 409
    assert exc_info.value.code == "TRIP_NOT_EDITABLE"


def test_deletable_status():
    assert_deletable(TripStatus.DRAFT)


@pytest.mark.parametrize("status", sorted(set(TripStatus) - {TripStatus.DRAFT}))
def test_non_deletable_statuses(status):
    with pytest.raises(ConflictError) as exc_info:
        assert_deletable(status)

    assert exc_info.value.code == "TRIP_NOT_DELETABLE"


def test_completable_requires_end_date_in_the_past():
    assert_completable(date(2026, 8, 16), today=date(2026, 8, 17))


@pytest.mark.parametrize("end_date", [date(2026, 8, 17), date(2026, 8, 18)])
def test_not_completable_before_end_date_passes(end_date):
    with pytest.raises(ConflictError) as exc_info:
        assert_completable(end_date, today=date(2026, 8, 17))

    assert exc_info.value.code == "TRIP_NOT_ENDED"


def test_reject_reason_is_trimmed_and_returned():
    assert assert_reject_reason("  예산 초과  ") == "예산 초과"


@pytest.mark.parametrize("reason", [None, "", "   "])
def test_reject_reason_is_required(reason):
    with pytest.raises(ValidationError) as exc_info:
        assert_reject_reason(reason)

    assert exc_info.value.code == "REJECT_REASON_REQUIRED"
    assert exc_info.value.field == "reason"


def test_assert_has_approver_returns_manager_id():
    assert assert_has_approver(7) == 7


def test_assert_has_approver_rejects_none():
    with pytest.raises(ConflictError) as exc_info:
        assert_has_approver(None)

    assert exc_info.value.status_code == 409
    assert exc_info.value.code == "NO_APPROVER"
