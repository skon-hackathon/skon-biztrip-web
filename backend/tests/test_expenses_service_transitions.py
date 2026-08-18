"""정산서 상태 전이. 출장의 전이 테스트와 같은 구조를 유지한다."""

from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
from sqlalchemy import select

from app.enums import (
    ActivityAction,
    EntityType,
    ExpenseReportStatus,
    NotificationType,
    TripStatus,
    UserRole,
)
from app.errors import ConflictError, ForbiddenError, ValidationError
from app.models import ActivityLog, Notification
from app.schemas.expense import ExpenseItemCreate, ExpenseReportUpdate
from app.schemas.trip import RejectRequest
from app.services.expenses import (
    add_item,
    approve_report,
    list_report_timeline,
    reject_report,
    reopen_report,
    submit_report,
    update_report,
)
from tests.factories import (
    make_card,
    make_card_transaction,
    make_expense_report,
    make_trip,
    make_trip_master_data,
    make_user,
)


async def _ready_report(db_session, *, trip_status=TripStatus.COMPLETED, with_centers=True):
    """제출 직전 상태의 정산서를 만든다 — 항목 1건 + FC/CC 지정."""
    await make_trip_master_data(db_session)
    manager = await make_user(db_session, role=UserRole.MANAGER, name="김결재")
    owner = await make_user(db_session, manager=manager, name="박신청")
    trip = await make_trip(db_session, user=owner, status=trip_status, approver_id=manager.id)
    report = await make_expense_report(
        db_session, trip=trip, approver=manager, fund_center_code=None
    )
    card = await make_card(db_session, user=owner)
    await make_card_transaction(
        db_session,
        card=card,
        approved_at=datetime.combine(trip.start_date, datetime.min.time(), tzinfo=timezone.utc)
        + timedelta(hours=3),
    )
    await add_item(
        db_session,
        user=owner,
        report_id=report.id,
        payload=ExpenseItemCreate(expense_category_code="MEAL", amount_krw=Decimal("30000")),
    )
    if with_centers:
        await update_report(
            db_session,
            user=owner,
            report_id=report.id,
            payload=ExpenseReportUpdate(fund_center_code="FC1010", cost_center_code="CC2030"),
        )
    return manager, owner, trip, report


async def test_submit_moves_to_submitted_and_notifies_the_approver(db_session):
    manager, owner, _, report = await _ready_report(db_session)

    detail = await submit_report(db_session, user=owner, report_id=report.id)

    assert detail.status is ExpenseReportStatus.SUBMITTED
    assert detail.submitted_at is not None
    assert detail.approver_id == manager.id

    notifications = (
        (
            await db_session.execute(
                select(Notification).where(Notification.user_id == manager.id)
            )
        )
        .scalars()
        .all()
    )
    assert [n.type for n in notifications] == [NotificationType.EXPENSE_SUBMITTED]


async def test_submit_requires_a_fund_center(db_session):
    _, owner, _, report = await _ready_report(db_session, with_centers=False)
    with pytest.raises(ValidationError) as excinfo:
        await submit_report(db_session, user=owner, report_id=report.id)
    assert excinfo.value.code == "CENTER_REQUIRED"
    assert excinfo.value.field == "fund_center_code"


async def test_submit_requires_a_completed_trip(db_session):
    _, owner, _, report = await _ready_report(db_session, trip_status=TripStatus.APPROVED)
    with pytest.raises(ConflictError) as excinfo:
        await submit_report(db_session, user=owner, report_id=report.id)
    assert excinfo.value.code == "TRIP_NOT_COMPLETED"


async def test_submit_requires_at_least_one_included_item(db_session):
    await make_trip_master_data(db_session)
    manager = await make_user(db_session, role=UserRole.MANAGER)
    owner = await make_user(db_session, manager=manager)
    trip = await make_trip(
        db_session, user=owner, status=TripStatus.COMPLETED, approver_id=manager.id
    )
    report = await make_expense_report(db_session, trip=trip, approver=manager)
    await update_report(
        db_session,
        user=owner,
        report_id=report.id,
        payload=ExpenseReportUpdate(fund_center_code="FC1010", cost_center_code="CC2030"),
    )
    with pytest.raises(ConflictError) as excinfo:
        await submit_report(db_session, user=owner, report_id=report.id)
    assert excinfo.value.code == "EXPENSE_NO_ITEMS"


async def test_the_approver_cannot_submit(db_session):
    manager, _, _, report = await _ready_report(db_session)
    with pytest.raises(ForbiddenError) as excinfo:
        await submit_report(db_session, user=manager, report_id=report.id)
    assert excinfo.value.code == "NOT_EXPENSE_OWNER"


async def test_double_submit_is_a_409(db_session):
    _, owner, _, report = await _ready_report(db_session)
    await submit_report(db_session, user=owner, report_id=report.id)
    with pytest.raises(ConflictError) as excinfo:
        await submit_report(db_session, user=owner, report_id=report.id)
    assert excinfo.value.code == "EXPENSE_INVALID_TRANSITION"


async def test_approve_settles_the_trip_and_notifies_the_owner(db_session):
    manager, owner, trip, report = await _ready_report(db_session)
    await submit_report(db_session, user=owner, report_id=report.id)

    detail = await approve_report(db_session, user=manager, report_id=report.id)

    assert detail.status is ExpenseReportStatus.APPROVED
    assert detail.approved_at is not None

    await db_session.refresh(trip)
    assert trip.status is TripStatus.SETTLED

    notifications = (
        (
            await db_session.execute(
                select(Notification).where(Notification.user_id == owner.id)
            )
        )
        .scalars()
        .all()
    )
    assert [n.type for n in notifications] == [NotificationType.EXPENSE_APPROVED]

    trip_log = (
        (
            await db_session.execute(
                select(ActivityLog).where(
                    ActivityLog.entity_type == EntityType.TRIP,
                    ActivityLog.entity_id == trip.id,
                    ActivityLog.action == ActivityAction.SETTLED,
                )
            )
        )
        .scalars()
        .all()
    )
    assert len(trip_log) == 1


async def test_the_owner_cannot_approve(db_session):
    _, owner, _, report = await _ready_report(db_session)
    await submit_report(db_session, user=owner, report_id=report.id)
    with pytest.raises(ForbiddenError) as excinfo:
        await approve_report(db_session, user=owner, report_id=report.id)
    assert excinfo.value.code == "NOT_EXPENSE_APPROVER"


async def test_reject_requires_a_reason_and_notifies_the_owner(db_session):
    manager, owner, _, report = await _ready_report(db_session)
    await submit_report(db_session, user=owner, report_id=report.id)

    with pytest.raises(ValidationError) as excinfo:
        await reject_report(
            db_session, user=manager, report_id=report.id, payload=RejectRequest(reason="  ")
        )
    assert excinfo.value.code == "REJECT_REASON_REQUIRED"

    detail = await reject_report(
        db_session,
        user=manager,
        report_id=report.id,
        payload=RejectRequest(reason="영수증 누락"),
    )
    assert detail.status is ExpenseReportStatus.REJECTED
    assert detail.reject_reason == "영수증 누락"

    notifications = (
        (
            await db_session.execute(
                select(Notification).where(
                    Notification.user_id == owner.id,
                    Notification.type == NotificationType.EXPENSE_REJECTED,
                )
            )
        )
        .scalars()
        .all()
    )
    assert len(notifications) == 1


async def test_rejecting_does_not_settle_the_trip(db_session):
    manager, owner, trip, report = await _ready_report(db_session)
    await submit_report(db_session, user=owner, report_id=report.id)
    await reject_report(
        db_session, user=manager, report_id=report.id, payload=RejectRequest(reason="보완")
    )
    await db_session.refresh(trip)
    assert trip.status is TripStatus.COMPLETED


async def test_rejected_report_can_be_reopened_and_resubmitted(db_session):
    manager, owner, _, report = await _ready_report(db_session)
    await submit_report(db_session, user=owner, report_id=report.id)
    await reject_report(
        db_session, user=manager, report_id=report.id, payload=RejectRequest(reason="보완")
    )

    detail = await reopen_report(db_session, user=owner, report_id=report.id)
    assert detail.status is ExpenseReportStatus.DRAFT
    assert detail.submitted_at is None
    # 무엇을 고쳐야 하는지 화면에 계속 보여야 하므로 반려 사유는 남긴다.
    assert detail.reject_reason == "보완"

    detail = await submit_report(db_session, user=owner, report_id=report.id)
    assert detail.status is ExpenseReportStatus.SUBMITTED
    assert detail.reject_reason is None


async def test_an_approved_report_is_terminal(db_session):
    manager, owner, _, report = await _ready_report(db_session)
    await submit_report(db_session, user=owner, report_id=report.id)
    await approve_report(db_session, user=manager, report_id=report.id)
    with pytest.raises(ConflictError):
        await reopen_report(db_session, user=owner, report_id=report.id)


async def test_timeline_lists_the_report_history_in_order(db_session):
    manager, owner, _, report = await _ready_report(db_session)
    await submit_report(db_session, user=owner, report_id=report.id)
    await approve_report(db_session, user=manager, report_id=report.id)

    entries = await list_report_timeline(db_session, user=owner, report_id=report.id)
    actions = [entry.action for entry in entries]
    assert ActivityAction.SUBMITTED in actions
    assert ActivityAction.APPROVED in actions
    assert actions.index(ActivityAction.SUBMITTED) < actions.index(ActivityAction.APPROVED)
    assert all(entry.actor_name for entry in entries)
