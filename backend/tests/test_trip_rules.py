from datetime import date
from pathlib import Path

import pytest

import app.services.trip_rules as trip_rules_module
from app.enums import TripStatus, UserRole
from app.errors import ConflictError, ForbiddenError, ValidationError
from app.services.trip_rules import (
    assert_completable,
    assert_date_range,
    assert_deletable,
    assert_editable,
    assert_has_approver,
    assert_reject_reason,
    assert_system_transition,
    assert_transition_allowed,
    assert_trip_approver,
    assert_trip_owner,
    can_view_trip,
)

#: assert_transition_allowed 테스트에서 쓰는 고정 신청자/결재자 id.
OWNER_ID = 1
APPROVER_ID = 9


def test_date_range_accepts_same_day():
    assert_date_range(start_date=date(2026, 9, 1), end_date=date(2026, 9, 1))


def test_date_range_rejects_end_before_start():
    with pytest.raises(ValidationError) as exc_info:
        assert_date_range(start_date=date(2026, 9, 3), end_date=date(2026, 9, 1))

    error = exc_info.value
    assert error.status_code == 400
    assert error.code == "INVALID_DATE_RANGE"
    assert error.field == "end_date"


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


@pytest.mark.parametrize(
    "status", sorted(set(TripStatus) - {TripStatus.DRAFT, TripStatus.REJECTED})
)
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


def test_transition_actor_guard_fires_on_missing_entry():
    """TRANSITION_ACTOR에서 엔트리 하나를 지운 변형 소스를 exec하면 임포트 시점 가드가
    RuntimeError를 던져야 한다. 실제 파일은 건드리지 않는다 — 소스 텍스트를 메모리에서
    수정해 재실행할 뿐이다."""
    module_path = Path(trip_rules_module.__file__)
    source = module_path.read_text()
    target_line = "    (TripStatus.COMPLETED, TripStatus.SETTLED): TransitionActor.SYSTEM,\n"
    assert target_line in source, "TRANSITION_ACTOR 엔트리 텍스트가 바뀌어 이 테스트를 갱신해야 합니다"
    broken_source = source.replace(target_line, "", 1)

    with pytest.raises(RuntimeError, match="TRANSITION_ACTOR"):
        exec(  # noqa: S102 - 의도된 동적 실행: 임포트 시점 가드를 재현하기 위함
            compile(broken_source, str(module_path), "exec"),
            {"__name__": "trip_rules_broken_for_test"},
        )


@pytest.mark.parametrize(
    ("current", "target", "actor_user_id", "wrong_user_id", "wrong_code"),
    [
        (TripStatus.DRAFT, TripStatus.SUBMITTED, OWNER_ID, APPROVER_ID, "NOT_TRIP_OWNER"),
        (TripStatus.SUBMITTED, TripStatus.APPROVED, APPROVER_ID, OWNER_ID, "NOT_TRIP_APPROVER"),
        (TripStatus.SUBMITTED, TripStatus.REJECTED, APPROVER_ID, OWNER_ID, "NOT_TRIP_APPROVER"),
        (TripStatus.REJECTED, TripStatus.DRAFT, OWNER_ID, APPROVER_ID, "NOT_TRIP_OWNER"),
        (TripStatus.APPROVED, TripStatus.COMPLETED, OWNER_ID, APPROVER_ID, "NOT_TRIP_OWNER"),
    ],
)
def test_assert_transition_allowed_gates_on_actor(
    current, target, actor_user_id, wrong_user_id, wrong_code
):
    assert_transition_allowed(
        current, target, user_id=actor_user_id, owner_id=OWNER_ID, approver_id=APPROVER_ID
    )

    with pytest.raises(ForbiddenError) as exc_info:
        assert_transition_allowed(
            current, target, user_id=wrong_user_id, owner_id=OWNER_ID, approver_id=APPROVER_ID
        )

    assert exc_info.value.code == wrong_code


@pytest.mark.parametrize("user_id", [OWNER_ID, APPROVER_ID])
def test_assert_transition_allowed_rejects_settled_for_any_user(user_id):
    with pytest.raises(ForbiddenError) as exc_info:
        assert_transition_allowed(
            TripStatus.COMPLETED,
            TripStatus.SETTLED,
            user_id=user_id,
            owner_id=OWNER_ID,
            approver_id=APPROVER_ID,
        )

    assert exc_info.value.code == "SYSTEM_TRANSITION_ONLY"


def test_assert_transition_allowed_rejects_illegal_transition_for_correct_actor():
    with pytest.raises(ConflictError) as exc_info:
        assert_transition_allowed(
            TripStatus.DRAFT,
            TripStatus.APPROVED,
            user_id=OWNER_ID,
            owner_id=OWNER_ID,
            approver_id=APPROVER_ID,
        )

    assert exc_info.value.status_code == 409
    assert exc_info.value.code == "TRIP_INVALID_TRANSITION"


def test_assert_system_transition_allows_completed_to_settled():
    assert_system_transition(TripStatus.COMPLETED, TripStatus.SETTLED)


def test_assert_system_transition_rejects_owner_transition():
    """사용자 주체 전이를 시스템 통로로 우회할 수 없다.

    이 가드가 없으면 정산 서비스가 실수로 submit·complete를 호출자 검증 없이
    수행할 수 있는 통로가 열린다 — 그게 fail-open이다.
    """
    with pytest.raises(ForbiddenError) as exc_info:
        assert_system_transition(TripStatus.DRAFT, TripStatus.SUBMITTED)
    assert exc_info.value.code == "USER_TRANSITION_ONLY"


def test_assert_system_transition_rejects_approver_transition():
    with pytest.raises(ForbiddenError) as exc_info:
        assert_system_transition(TripStatus.SUBMITTED, TripStatus.APPROVED)
    assert exc_info.value.code == "USER_TRANSITION_ONLY"


def test_assert_system_transition_rejects_illegal_transition():
    """적법성을 권한보다 먼저 본다 — assert_transition_allowed와 순서를 맞춘다."""
    with pytest.raises(ConflictError) as exc_info:
        assert_system_transition(TripStatus.DRAFT, TripStatus.SETTLED)
    assert exc_info.value.code == "TRIP_INVALID_TRANSITION"


def test_user_path_still_rejects_the_system_transition():
    with pytest.raises(ForbiddenError) as exc_info:
        assert_transition_allowed(
            TripStatus.COMPLETED,
            TripStatus.SETTLED,
            user_id=OWNER_ID,
            owner_id=OWNER_ID,
            approver_id=APPROVER_ID,
        )
    assert exc_info.value.code == "SYSTEM_TRANSITION_ONLY"
