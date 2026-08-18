"""정산 도메인의 순수 규칙. DB 접근이 없어 단위테스트로 전부 덮는다.

출장(`trip_rules.py`)과 같은 구조를 일부러 유지한다 — 전이표와 주체표를 따로 두되
임포트 시점에 두 표의 키가 정확히 일치하는지 검사한다. Phase 2에서 가장 컸던 결함이
"적법성과 권한을 따로 부를 수 있게 열어둔 것"이었고, 그 실패는 fail-open이었다.
"""

from collections.abc import Iterable
from decimal import Decimal

from app.enums import ExpenseReportStatus, TripStatus, UserRole
from app.errors import ConflictError, ForbiddenError, ValidationError

# TransitionActor를 출장 쪽에서 가져다 쓴다. 주체의 종류(신청자·결재자·시스템)는
# 도메인 중립이며, 두 벌로 두면 "OWNER"가 두 개 존재하는 상태가 된다.
from app.services.trip_rules import TransitionActor

#: 항목을 고칠 수 있는 리포트 상태. 반려된 리포트는 고쳐서 reopen 후 재상신한다.
EXPENSE_EDITABLE_STATUSES = frozenset(
    {ExpenseReportStatus.DRAFT, ExpenseReportStatus.REJECTED}
)

#: 정산서를 만들 수 있는 출장 상태 (spec 5.5).
REPORTABLE_TRIP_STATUSES = frozenset({TripStatus.APPROVED, TripStatus.COMPLETED})

#: expense_item.amount_krw는 Numeric(14, 2)다. 항목 하나가 컬럼을 넘지 못하게 하되,
#: 합계 상한보다 두 자리 낮게 잡아 항목 몇 개로 합계를 넘기는 일이 흔하지 않게 한다.
MAX_ITEM_AMOUNT = Decimal("9999999999.99")

#: expense_report.total_amount_krw도 Numeric(14, 2)다. 항목 상한만으로는 못 막는다.
MAX_REPORT_TOTAL = Decimal("999999999999.99")


def can_view_report(
    *, user_id: int, role: UserRole, owner_id: int, approver_id: int | None
) -> bool:
    """신청자·결재자·ADMIN만 정산서를 볼 수 있다. False면 호출부는 403이 아니라 404다."""
    if role == UserRole.ADMIN:
        return True
    return user_id == owner_id or (approver_id is not None and user_id == approver_id)


def assert_report_owner(*, user_id: int, owner_id: int) -> None:
    if user_id != owner_id:
        raise ForbiddenError("NOT_EXPENSE_OWNER", "본인의 정산서만 처리할 수 있습니다")


def assert_report_approver(*, user_id: int, approver_id: int | None) -> None:
    if approver_id is None or user_id != approver_id:
        raise ForbiddenError("NOT_EXPENSE_APPROVER", "이 정산서의 결재자가 아닙니다")


def assert_report_editable(status: ExpenseReportStatus) -> None:
    if status not in EXPENSE_EDITABLE_STATUSES:
        raise ConflictError(
            "EXPENSE_NOT_EDITABLE", f"{status} 상태의 정산서는 수정할 수 없습니다"
        )


def assert_report_creatable(trip_status: TripStatus) -> None:
    if trip_status not in REPORTABLE_TRIP_STATUSES:
        raise ConflictError(
            "TRIP_NOT_REPORTABLE",
            f"{trip_status} 상태의 출장에는 정산서를 만들 수 없습니다",
        )


def assert_trip_completed(trip_status: TripStatus) -> None:
    """제출은 출장이 완료된 뒤에만 가능하다.

    정산서 승인이 출장의 COMPLETED → SETTLED를 트리거하므로, 출장이 아직 APPROVED면
    승인 시점에 전이표에 없는 APPROVED → SETTLED가 필요해진다. 결재자가 승인을 누른
    뒤 409를 보는 것보다 신청자가 제출에서 막히는 편이 낫다.
    """
    if trip_status is not TripStatus.COMPLETED:
        raise ConflictError(
            "TRIP_NOT_COMPLETED", "출장을 완료 처리한 뒤에 정산서를 제출할 수 있습니다"
        )


def assert_item_amount(amount: Decimal) -> None:
    if amount < 0:
        raise ValidationError("INVALID_AMOUNT", "금액은 0 이상이어야 합니다", field="amount_krw")
    if amount > MAX_ITEM_AMOUNT:
        raise ValidationError(
            "INVALID_AMOUNT", f"금액은 {MAX_ITEM_AMOUNT}를 넘을 수 없습니다", field="amount_krw"
        )


def assert_report_total(total: Decimal) -> None:
    if total > MAX_REPORT_TOTAL:
        raise ValidationError(
            "TOTAL_AMOUNT_EXCEEDED",
            f"정산 합계는 {MAX_REPORT_TOTAL}를 넘을 수 없습니다",
            field="amount_krw",
        )


def assert_has_items(item_count: int) -> None:
    if item_count <= 0:
        raise ConflictError("EXPENSE_NO_ITEMS", "정산 항목이 없어 제출할 수 없습니다")


def assert_centers_present(*, fund_center_code: str | None, cost_center_code: str | None) -> None:
    """제출 시 FC/CC가 비어 있으면 검증 실패다 (spec 5.5)."""
    if not (fund_center_code or "").strip():
        raise ValidationError(
            "CENTER_REQUIRED", "펀드센터를 지정해야 제출할 수 있습니다", field="fund_center_code"
        )
    if not (cost_center_code or "").strip():
        raise ValidationError(
            "CENTER_REQUIRED", "코스트센터를 지정해야 제출할 수 있습니다", field="cost_center_code"
        )


def effective_center(item_code: str | None, report_code: str | None) -> str | None:
    """FC/CC 계층의 coalesce (spec 5.5). 항목 값이 비면 리포트 값을 쓴다."""
    return item_code if item_code is not None else report_code


def sum_included(amounts: Iterable[tuple[Decimal, bool]]) -> Decimal:
    """(금액, is_excluded) 쌍의 합. 제외된 항목은 합계에서 뺀다."""
    return sum((amount for amount, excluded in amounts if not excluded), Decimal("0"))


EXPENSE_ALLOWED_TRANSITIONS: dict[ExpenseReportStatus, frozenset[ExpenseReportStatus]] = {
    ExpenseReportStatus.DRAFT: frozenset({ExpenseReportStatus.SUBMITTED}),
    ExpenseReportStatus.SUBMITTED: frozenset(
        {ExpenseReportStatus.APPROVED, ExpenseReportStatus.REJECTED}
    ),
    ExpenseReportStatus.REJECTED: frozenset({ExpenseReportStatus.DRAFT}),
    ExpenseReportStatus.APPROVED: frozenset(),
}

_missing_statuses = set(ExpenseReportStatus) - set(EXPENSE_ALLOWED_TRANSITIONS)
if _missing_statuses:
    raise RuntimeError(f"EXPENSE_ALLOWED_TRANSITIONS missing entries for {_missing_statuses}")

#: 각 전이의 수행 주체. 아래 가드가 EXPENSE_ALLOWED_TRANSITIONS와의 일치를 임포트
#: 시점에 강제한다 — 전이를 추가하고 주체를 빠뜨리면 조용히 "아무나 가능"이 되는 게
#: 아니라 임포트가 깨진다.
EXPENSE_TRANSITION_ACTOR: dict[
    tuple[ExpenseReportStatus, ExpenseReportStatus], TransitionActor
] = {
    (ExpenseReportStatus.DRAFT, ExpenseReportStatus.SUBMITTED): TransitionActor.OWNER,
    (ExpenseReportStatus.SUBMITTED, ExpenseReportStatus.APPROVED): TransitionActor.APPROVER,
    (ExpenseReportStatus.SUBMITTED, ExpenseReportStatus.REJECTED): TransitionActor.APPROVER,
    (ExpenseReportStatus.REJECTED, ExpenseReportStatus.DRAFT): TransitionActor.OWNER,
}

_all_expense_transitions = {
    (current, target)
    for current, targets in EXPENSE_ALLOWED_TRANSITIONS.items()
    for target in targets
}
_missing_actors = _all_expense_transitions - set(EXPENSE_TRANSITION_ACTOR)
_extra_actors = set(EXPENSE_TRANSITION_ACTOR) - _all_expense_transitions
if _missing_actors or _extra_actors:
    raise RuntimeError(
        "EXPENSE_TRANSITION_ACTOR가 EXPENSE_ALLOWED_TRANSITIONS와 어긋납니다: "
        f"missing={_missing_actors} extra={_extra_actors}"
    )


def assert_expense_transition_allowed(
    current: ExpenseReportStatus,
    target: ExpenseReportStatus,
    *,
    user_id: int,
    owner_id: int,
    approver_id: int | None,
) -> None:
    """정산서 전이의 적법성과 수행 주체를 한 번에 검사한다. 호출부는 이것만 부른다."""
    if target not in EXPENSE_ALLOWED_TRANSITIONS[current]:
        raise ConflictError(
            "EXPENSE_INVALID_TRANSITION", f"{current} 상태에서 {target} 로 변경할 수 없습니다"
        )
    actor = EXPENSE_TRANSITION_ACTOR[(current, target)]
    if actor is TransitionActor.OWNER:
        assert_report_owner(user_id=user_id, owner_id=owner_id)
    elif actor is TransitionActor.APPROVER:
        assert_report_approver(user_id=user_id, approver_id=approver_id)
    else:  # pragma: no cover - 정산에는 시스템 전이가 없다
        raise ForbiddenError("SYSTEM_TRANSITION_ONLY", "이 전이는 시스템에 의해서만 수행됩니다")
