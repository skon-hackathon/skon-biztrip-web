"""출장 도메인의 순수 규칙. DB 접근이 없어 단위테스트로 전부 덮는다.

`trip_status.py`가 전이의 적법성만 판단하는 것과 짝을 이룬다. 여기서는 전이의 조건과
권한, 그리고 모델에 CheckConstraint를 걸지 않아 비어 있는 교차필드 제약을 담당한다.
모델이 막아줄 거라고 가정하지 말 것 — 막아주지 않는다.
"""

from datetime import date
from decimal import Decimal

from app.enums import TripStatus, UserRole
from app.errors import ConflictError, ForbiddenError, ValidationError

#: 신청자가 내용을 고칠 수 있는 상태. 반려된 출장은 고쳐서 다시 상신하는 것이 정상 경로다.
EDITABLE_STATUSES = frozenset({TripStatus.DRAFT, TripStatus.REJECTED})


def assert_date_range(start_date: date, end_date: date) -> None:
    if end_date < start_date:
        raise ValidationError(
            "INVALID_DATE_RANGE", "종료일은 시작일보다 빠를 수 없습니다", field="end_date"
        )


def assert_estimated_cost(estimated_cost: Decimal) -> None:
    if estimated_cost < 0:
        raise ValidationError(
            "INVALID_AMOUNT", "예상 비용은 0 이상이어야 합니다", field="estimated_cost"
        )


def can_view(*, user_id: int, role: UserRole, owner_id: int, approver_id: int | None) -> bool:
    """신청자·결재자·ADMIN만 출장을 볼 수 있다.

    이 판정이 False면 호출부는 403이 아니라 **404**를 낸다. 타인 리소스의 존재 자체를
    알려주지 않는 것이 이 프로젝트의 규칙이다.
    """
    if role == UserRole.ADMIN:
        return True
    return user_id == owner_id or (approver_id is not None and user_id == approver_id)


def assert_owner(*, user_id: int, owner_id: int) -> None:
    if user_id != owner_id:
        raise ForbiddenError("NOT_TRIP_OWNER", "본인이 신청한 출장만 처리할 수 있습니다")


def assert_trip_approver(*, user_id: int, approver_id: int | None) -> None:
    if approver_id is None or user_id != approver_id:
        raise ForbiddenError("NOT_TRIP_APPROVER", "이 출장의 결재자가 아닙니다")


def assert_editable(status: TripStatus) -> None:
    if status not in EDITABLE_STATUSES:
        raise ConflictError("TRIP_NOT_EDITABLE", f"{status} 상태의 출장은 수정할 수 없습니다")


def assert_deletable(status: TripStatus) -> None:
    if status is not TripStatus.DRAFT:
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
