"""정산 순수 규칙 단위테스트. DB를 쓰지 않는다.

파생 데이터를 검사 대상 상수에서 만들지 않는다 — `set(ExpenseReportStatus) -
EXPENSE_EDITABLE_STATUSES` 같은 식으로 쓰면 상수를 넓히는 버그와 테스트가 함께 움직여
조용히 통과한다 (Phase 2 결함 #6). 리터럴로 적는다.
"""

from decimal import Decimal

import pytest

from app.enums import ExpenseReportStatus, TripStatus, UserRole
from app.errors import ConflictError, ForbiddenError, ValidationError
from app.services.expense_rules import (
    MAX_ITEM_AMOUNT,
    MAX_REPORT_TOTAL,
    assert_centers_present,
    assert_expense_transition_allowed,
    assert_has_items,
    assert_item_amount,
    assert_report_creatable,
    assert_report_editable,
    assert_report_total,
    assert_trip_completed,
    can_view_report,
    effective_center,
    sum_included,
)


@pytest.mark.parametrize("status", [ExpenseReportStatus.DRAFT, ExpenseReportStatus.REJECTED])
def test_editable_statuses(status):
    assert_report_editable(status)


@pytest.mark.parametrize("status", [ExpenseReportStatus.SUBMITTED, ExpenseReportStatus.APPROVED])
def test_non_editable_statuses(status):
    with pytest.raises(ConflictError) as excinfo:
        assert_report_editable(status)
    assert excinfo.value.code == "EXPENSE_NOT_EDITABLE"


@pytest.mark.parametrize("status", [TripStatus.APPROVED, TripStatus.COMPLETED])
def test_report_can_be_created_for_approved_and_completed_trips(status):
    assert_report_creatable(status)


@pytest.mark.parametrize(
    "status",
    [TripStatus.DRAFT, TripStatus.SUBMITTED, TripStatus.REJECTED, TripStatus.SETTLED],
)
def test_report_cannot_be_created_for_other_trip_statuses(status):
    with pytest.raises(ConflictError) as excinfo:
        assert_report_creatable(status)
    assert excinfo.value.code == "TRIP_NOT_REPORTABLE"


def test_submit_requires_a_completed_trip():
    """승인 시 COMPLETED → SETTLED가 성립해야 하므로 제출 단계에서 막는다."""
    assert_trip_completed(TripStatus.COMPLETED)
    with pytest.raises(ConflictError) as excinfo:
        assert_trip_completed(TripStatus.APPROVED)
    assert excinfo.value.code == "TRIP_NOT_COMPLETED"


def test_item_amount_bounds():
    assert_item_amount(Decimal("0"))
    assert_item_amount(MAX_ITEM_AMOUNT)
    with pytest.raises(ValidationError) as negative:
        assert_item_amount(Decimal("-1"))
    assert negative.value.code == "INVALID_AMOUNT"
    assert negative.value.field == "amount_krw"
    with pytest.raises(ValidationError) as too_big:
        assert_item_amount(MAX_ITEM_AMOUNT + Decimal("0.01"))
    assert too_big.value.code == "INVALID_AMOUNT"


def test_report_total_bound():
    """항목 상한만 두면 항목 여러 개로 합계를 넘길 수 있다. 그 오버플로는 flush에서
    500이 되고 Agent가 무한 재시도한다 (Phase 2 결함 #2와 같은 형태)."""
    assert_report_total(MAX_REPORT_TOTAL)
    with pytest.raises(ValidationError) as excinfo:
        assert_report_total(MAX_REPORT_TOTAL + Decimal("0.01"))
    assert excinfo.value.code == "TOTAL_AMOUNT_EXCEEDED"
    assert excinfo.value.field == "amount_krw"


def test_item_limit_is_lower_than_the_report_limit():
    """항목 하나로 리포트 상한을 채워버리면 합계 가드가 사실상 죽는다."""
    assert MAX_ITEM_AMOUNT < MAX_REPORT_TOTAL


def test_submit_requires_items():
    assert_has_items(1)
    with pytest.raises(ConflictError) as excinfo:
        assert_has_items(0)
    assert excinfo.value.code == "EXPENSE_NO_ITEMS"


def test_submit_requires_both_centers():
    assert_centers_present(fund_center_code="FC1010", cost_center_code="CC2030")
    with pytest.raises(ValidationError) as no_fund:
        assert_centers_present(fund_center_code=None, cost_center_code="CC2030")
    assert no_fund.value.code == "CENTER_REQUIRED"
    assert no_fund.value.field == "fund_center_code"
    with pytest.raises(ValidationError) as no_cost:
        assert_centers_present(fund_center_code="FC1010", cost_center_code="  ")
    assert no_cost.value.field == "cost_center_code"


def test_effective_center_falls_back_to_the_report_value():
    assert effective_center("CC2040", "CC2030") == "CC2040"
    assert effective_center(None, "CC2030") == "CC2030"
    assert effective_center(None, None) is None


def test_sum_included_skips_excluded_items():
    assert sum_included([(Decimal("100"), False), (Decimal("50"), True)]) == Decimal("100")
    assert sum_included([]) == Decimal("0")


def test_owner_and_approver_and_admin_can_view():
    assert can_view_report(user_id=1, role=UserRole.EMPLOYEE, owner_id=1, approver_id=2)
    assert can_view_report(user_id=2, role=UserRole.MANAGER, owner_id=1, approver_id=2)
    assert can_view_report(user_id=9, role=UserRole.ADMIN, owner_id=1, approver_id=2)
    assert not can_view_report(user_id=3, role=UserRole.EMPLOYEE, owner_id=1, approver_id=2)


def test_submit_is_owner_only():
    assert_expense_transition_allowed(
        ExpenseReportStatus.DRAFT,
        ExpenseReportStatus.SUBMITTED,
        user_id=1,
        owner_id=1,
        approver_id=2,
    )
    with pytest.raises(ForbiddenError) as excinfo:
        assert_expense_transition_allowed(
            ExpenseReportStatus.DRAFT,
            ExpenseReportStatus.SUBMITTED,
            user_id=2,
            owner_id=1,
            approver_id=2,
        )
    assert excinfo.value.code == "NOT_EXPENSE_OWNER"


def test_approve_is_approver_only():
    assert_expense_transition_allowed(
        ExpenseReportStatus.SUBMITTED,
        ExpenseReportStatus.APPROVED,
        user_id=2,
        owner_id=1,
        approver_id=2,
    )
    with pytest.raises(ForbiddenError) as excinfo:
        assert_expense_transition_allowed(
            ExpenseReportStatus.SUBMITTED,
            ExpenseReportStatus.APPROVED,
            user_id=1,
            owner_id=1,
            approver_id=2,
        )
    assert excinfo.value.code == "NOT_EXPENSE_APPROVER"


def test_reject_is_approver_only():
    assert_expense_transition_allowed(
        ExpenseReportStatus.SUBMITTED,
        ExpenseReportStatus.REJECTED,
        user_id=2,
        owner_id=1,
        approver_id=2,
    )
    with pytest.raises(ForbiddenError):
        assert_expense_transition_allowed(
            ExpenseReportStatus.SUBMITTED,
            ExpenseReportStatus.REJECTED,
            user_id=1,
            owner_id=1,
            approver_id=2,
        )


def test_illegal_transition_is_reported_before_the_actor_check():
    """결재자가 DRAFT 리포트를 승인하려 하면 409가 403보다 실질적인 답이다 —
    출장 쪽 assert_transition_allowed와 같은 순서다."""
    with pytest.raises(ConflictError) as excinfo:
        assert_expense_transition_allowed(
            ExpenseReportStatus.DRAFT,
            ExpenseReportStatus.APPROVED,
            user_id=2,
            owner_id=1,
            approver_id=2,
        )
    assert excinfo.value.code == "EXPENSE_INVALID_TRANSITION"


def test_reopen_is_owner_only():
    assert_expense_transition_allowed(
        ExpenseReportStatus.REJECTED,
        ExpenseReportStatus.DRAFT,
        user_id=1,
        owner_id=1,
        approver_id=2,
    )
    with pytest.raises(ForbiddenError):
        assert_expense_transition_allowed(
            ExpenseReportStatus.REJECTED,
            ExpenseReportStatus.DRAFT,
            user_id=2,
            owner_id=1,
            approver_id=2,
        )


def test_approved_report_is_terminal():
    with pytest.raises(ConflictError):
        assert_expense_transition_allowed(
            ExpenseReportStatus.APPROVED,
            ExpenseReportStatus.DRAFT,
            user_id=1,
            owner_id=1,
            approver_id=2,
        )


def test_missing_approver_is_rejected_not_treated_as_wildcard():
    with pytest.raises(ForbiddenError) as excinfo:
        assert_expense_transition_allowed(
            ExpenseReportStatus.SUBMITTED,
            ExpenseReportStatus.APPROVED,
            user_id=2,
            owner_id=1,
            approver_id=None,
        )
    assert excinfo.value.code == "NOT_EXPENSE_APPROVER"
