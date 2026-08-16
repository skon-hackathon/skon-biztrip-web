import itertools

import pytest

from app.enums import TripStatus
from app.errors import ConflictError
from app.services.trip_status import assert_trip_transition, can_transition

# 리터럴로 직접 나열한다 — ALLOWED_TRANSITIONS에서 파생하면 항진명제(tautological)가 되어
# 표에 잘못된 엣지가 추가되어도 이 테스트가 잡아내지 못한다.
LEGAL_TRANSITIONS = frozenset(
    {
        (TripStatus.DRAFT, TripStatus.SUBMITTED),
        (TripStatus.SUBMITTED, TripStatus.APPROVED),
        (TripStatus.SUBMITTED, TripStatus.REJECTED),
        (TripStatus.REJECTED, TripStatus.DRAFT),
        (TripStatus.APPROVED, TripStatus.COMPLETED),
        (TripStatus.COMPLETED, TripStatus.SETTLED),
    }
)


@pytest.mark.parametrize(
    ("current", "target"),
    [
        (TripStatus.DRAFT, TripStatus.SUBMITTED),
        (TripStatus.SUBMITTED, TripStatus.APPROVED),
        (TripStatus.SUBMITTED, TripStatus.REJECTED),
        (TripStatus.REJECTED, TripStatus.DRAFT),
        (TripStatus.APPROVED, TripStatus.COMPLETED),
        (TripStatus.COMPLETED, TripStatus.SETTLED),
    ],
)
def test_allowed_transitions(current, target):
    assert can_transition(current, target) is True


@pytest.mark.parametrize(
    ("current", "target"),
    [
        (TripStatus.DRAFT, TripStatus.APPROVED),
        (TripStatus.SUBMITTED, TripStatus.SUBMITTED),
        (TripStatus.APPROVED, TripStatus.SETTLED),
        (TripStatus.SETTLED, TripStatus.DRAFT),
        (TripStatus.COMPLETED, TripStatus.APPROVED),
    ],
)
def test_forbidden_transitions(current, target):
    assert can_transition(current, target) is False


def test_assert_raises_conflict_with_domain_code():
    with pytest.raises(ConflictError) as exc_info:
        assert_trip_transition(TripStatus.SUBMITTED, TripStatus.SUBMITTED)

    error = exc_info.value
    assert error.status_code == 409
    assert error.code == "TRIP_INVALID_TRANSITION"
    assert "SUBMITTED" in error.message


def test_assert_passes_on_allowed():
    assert_trip_transition(TripStatus.DRAFT, TripStatus.SUBMITTED)


@pytest.mark.parametrize(("current", "target"), list(itertools.product(TripStatus, TripStatus)))
def test_full_transition_matrix(current, target):
    expected = (current, target) in LEGAL_TRANSITIONS
    assert can_transition(current, target) is expected
