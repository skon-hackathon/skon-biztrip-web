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


def can_transition(current: TripStatus, target: TripStatus) -> bool:
    return target in ALLOWED_TRANSITIONS[current]


def assert_trip_transition(current: TripStatus, target: TripStatus) -> None:
    if not can_transition(current, target):
        raise ConflictError(
            "TRIP_INVALID_TRANSITION",
            f"{current} 상태에서 {target} 로 변경할 수 없습니다",
        )
