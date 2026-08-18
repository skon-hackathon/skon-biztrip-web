"""출장 도메인의 순수 규칙. DB 접근이 없어 단위테스트로 전부 덮는다.

`trip_status.py`가 전이의 적법성만 판단하는 것과 짝을 이룬다. 여기서는 전이의 조건과
권한, 그리고 모델에 CheckConstraint를 걸지 않아 비어 있는 교차필드 제약을 담당한다.
모델이 막아줄 거라고 가정하지 말 것 — 막아주지 않는다.
"""

from datetime import date
from decimal import Decimal
from enum import StrEnum

from app.enums import TripStatus, UserRole
from app.errors import ConflictError, ForbiddenError, ValidationError
from app.services.trip_status import ALLOWED_TRANSITIONS, assert_trip_transition

#: 수정 가능한 상태. REJECTED에서 고쳐도 상태는 그대로 REJECTED로 남는다 — 곧바로
#: 다시 상신할 수는 없고, reopen_trip으로 DRAFT로 되돌린 뒤에야 상신할 수 있다.
#: 정상 경로는 수정 → reopen → 상신이다.
EDITABLE_STATUSES = frozenset({TripStatus.DRAFT, TripStatus.REJECTED})

#: 삭제 가능한 상태. assert_editable과 판단 방식을 맞추기 위해 `is not` 대신 멤버십으로
#: 검사한다 — 지금은 컬럼이 SAEnum(TripStatus)라 관측되지 않는 차이지만, 굳이 다르게
#: 둘 이유가 없다.
DELETABLE_STATUSES = frozenset({TripStatus.DRAFT})

#: Trip.estimated_cost는 Numeric(14, 2) — 정수부 12자리가 최대다. 넘으면 flush에서
#: Postgres numeric overflow가 나고 통일 핸들러의 catch-all에 걸려 500이 된다.
#: Agent는 5xx를 재시도하므로, 절대 성공할 수 없는 요청에 재시도 루프가 걸린다.
MAX_ESTIMATED_COST = Decimal("999999999999.99")


def assert_date_range(*, start_date: date, end_date: date) -> None:
    if end_date < start_date:
        raise ValidationError(
            "INVALID_DATE_RANGE", "종료일은 시작일보다 빠를 수 없습니다", field="end_date"
        )


def assert_estimated_cost(estimated_cost: Decimal) -> None:
    if estimated_cost < 0:
        raise ValidationError(
            "INVALID_AMOUNT", "예상 비용은 0 이상이어야 합니다", field="estimated_cost"
        )
    if estimated_cost > MAX_ESTIMATED_COST:
        raise ValidationError(
            "INVALID_AMOUNT",
            f"예상 비용은 {MAX_ESTIMATED_COST}를 넘을 수 없습니다",
            field="estimated_cost",
        )


def can_view_trip(*, user_id: int, role: UserRole, owner_id: int, approver_id: int | None) -> bool:
    """신청자·결재자·ADMIN만 출장을 볼 수 있다.

    이 판정이 False면 호출부는 403이 아니라 **404**를 낸다. 타인 리소스의 존재 자체를
    알려주지 않는 것이 이 프로젝트의 규칙이다.
    """
    if role == UserRole.ADMIN:
        return True
    return user_id == owner_id or (approver_id is not None and user_id == approver_id)


def assert_trip_owner(*, user_id: int, owner_id: int) -> None:
    if user_id != owner_id:
        raise ForbiddenError("NOT_TRIP_OWNER", "본인이 신청한 출장만 처리할 수 있습니다")


def assert_trip_approver(*, user_id: int, approver_id: int | None) -> None:
    if approver_id is None or user_id != approver_id:
        raise ForbiddenError("NOT_TRIP_APPROVER", "이 출장의 결재자가 아닙니다")


def assert_editable(status: TripStatus) -> None:
    if status not in EDITABLE_STATUSES:
        raise ConflictError("TRIP_NOT_EDITABLE", f"{status} 상태의 출장은 수정할 수 없습니다")


def assert_deletable(status: TripStatus) -> None:
    if status not in DELETABLE_STATUSES:
        raise ConflictError("TRIP_NOT_DELETABLE", "임시저장 상태의 출장만 삭제할 수 있습니다")


def assert_completable(end_date: date, *, today: date) -> None:
    """spec 5.4: APPROVED → COMPLETED는 end_date가 오늘 이전일 것.

    today를 인자로 받는 이유는 테스트를 결정적으로 만들기 위해서다. 호출부가
    date.today()를 넘긴다.
    """
    if end_date >= today:
        raise ConflictError("TRIP_NOT_ENDED", "종료일이 지난 출장만 완료 처리할 수 있습니다")


def assert_reject_reason(reason: str | None) -> str:
    text = (reason or "").strip()
    if not text:
        raise ValidationError("REJECT_REASON_REQUIRED", "반려 사유를 입력해야 합니다", field="reason")
    return text


def assert_has_approver(manager_id: int | None) -> int:
    """결재자는 신청자의 manager_id로 자동 결정된다 (spec 5.1). 없으면 상신할 수 없다."""
    if manager_id is None:
        raise ConflictError("NO_APPROVER", "결재자가 지정되지 않아 상신할 수 없습니다")
    return manager_id


class TransitionActor(StrEnum):
    OWNER = "OWNER"
    APPROVER = "APPROVER"
    SYSTEM = "SYSTEM"


#: 각 전이를 수행할 수 있는 주체. ALLOWED_TRANSITIONS(trip_status.py)의 (현재, 목표) 쌍과
#: 키가 정확히 일치해야 한다 — 아래 가드가 그 일치를 임포트 시점에 강제한다. 전이를
#: 추가하면서 여기 엔트리를 빠뜨리면, 조용히 통과하는 대신 임포트 자체가 깨진다.
TRANSITION_ACTOR: dict[tuple[TripStatus, TripStatus], TransitionActor] = {
    (TripStatus.DRAFT, TripStatus.SUBMITTED): TransitionActor.OWNER,
    (TripStatus.SUBMITTED, TripStatus.APPROVED): TransitionActor.APPROVER,
    (TripStatus.SUBMITTED, TripStatus.REJECTED): TransitionActor.APPROVER,
    (TripStatus.REJECTED, TripStatus.DRAFT): TransitionActor.OWNER,
    (TripStatus.APPROVED, TripStatus.COMPLETED): TransitionActor.OWNER,
    (TripStatus.COMPLETED, TripStatus.SETTLED): TransitionActor.SYSTEM,
}

_all_transitions = {
    (current, target) for current, targets in ALLOWED_TRANSITIONS.items() for target in targets
}
_missing_actors = _all_transitions - set(TRANSITION_ACTOR)
_extra_actors = set(TRANSITION_ACTOR) - _all_transitions
if _missing_actors or _extra_actors:
    raise RuntimeError(
        "TRANSITION_ACTOR가 ALLOWED_TRANSITIONS와 어긋납니다: "
        f"missing={_missing_actors} extra={_extra_actors}"
    )


def assert_transition_allowed(
    current: TripStatus,
    target: TripStatus,
    *,
    user_id: int,
    owner_id: int,
    approver_id: int | None,
) -> None:
    """전이의 적법성과 수행 주체를 한 번에 검사한다.

    호출부가 두 검사를 따로 부르면 언젠가 한쪽을 빠뜨리고, 그 실패는 조용하다 —
    load_visible_trip을 이미 통과한 결재자가 신청자만 할 수 있는 전이를 수행하게 된다.

    적법성을 권한보다 먼저 검사한다: 결재자가 DRAFT 상태의 출장에 승인을 시도하면
    TRIP_INVALID_TRANSITION(409)이 권한 오류보다 더 실질적인 답이다 — 그 결재자는
    어차피 이 출장을 볼 수 있으므로 상태를 감출 이유가 없다.
    """
    assert_trip_transition(current, target)
    actor = TRANSITION_ACTOR[(current, target)]
    if actor is TransitionActor.OWNER:
        assert_trip_owner(user_id=user_id, owner_id=owner_id)
    elif actor is TransitionActor.APPROVER:
        assert_trip_approver(user_id=user_id, approver_id=approver_id)
    else:
        raise ForbiddenError("SYSTEM_TRANSITION_ONLY", "이 전이는 시스템에 의해서만 수행됩니다")


def assert_system_transition(current: TripStatus, target: TripStatus) -> None:
    """시스템만 수행하는 전이를 검사한다 (지금은 COMPLETED → SETTLED 하나뿐).

    `assert_transition_allowed`와 **같은 표**를 읽는 것이 요점이다. 정산 서비스가
    표를 건너뛰고 `trip.status = SETTLED`를 직접 대입하면 적법성 검사도, 이력도
    없이 상태가 바뀐다. 그래서 시스템 경로에도 통로를 하나 만들어 주고, 그 통로가
    사용자 주체 전이는 거부하게 한다 — 두 방향 모두 fail-closed다.
    """
    assert_trip_transition(current, target)
    actor = TRANSITION_ACTOR[(current, target)]
    if actor is not TransitionActor.SYSTEM:
        raise ForbiddenError("USER_TRANSITION_ONLY", "이 전이는 사용자가 수행해야 합니다")
