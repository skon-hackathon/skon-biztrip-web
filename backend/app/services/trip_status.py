"""출장 상태전이의 적법성(legality)만 판단한다.

누가 전이를 수행할 수 있는지(권한)와 전이에 필요한 부가 조건(예: APPROVED → COMPLETED는
end_date가 과거여야 하고, 승인은 지정된 승인자만 할 수 있음)은 이 모듈의 책임이 아니다.
그런 규칙들은 Phase 2의 서비스 함수에서 처리한다.
"""

from app.enums import TripStatus
from app.errors import ConflictError

ALLOWED_TRANSITIONS: dict[TripStatus, frozenset[TripStatus]] = {
    TripStatus.DRAFT: frozenset({TripStatus.SUBMITTED}),
    TripStatus.SUBMITTED: frozenset({TripStatus.APPROVED, TripStatus.REJECTED}),
    TripStatus.REJECTED: frozenset({TripStatus.DRAFT}),
    TripStatus.APPROVED: frozenset({TripStatus.COMPLETED}),
    TripStatus.COMPLETED: frozenset({TripStatus.SETTLED}),
    TripStatus.SETTLED: frozenset(),
}

_missing = set(TripStatus) - set(ALLOWED_TRANSITIONS)
if _missing:
    raise RuntimeError(f"ALLOWED_TRANSITIONS missing entries for {_missing}")


def can_transition(current: TripStatus, target: TripStatus) -> bool:
    return target in ALLOWED_TRANSITIONS[current]


def assert_trip_transition(current: TripStatus, target: TripStatus) -> None:
    if not can_transition(current, target):
        raise ConflictError(
            "TRIP_INVALID_TRANSITION",
            f"{current} 상태에서 {target} 로 변경할 수 없습니다",
        )
