"""정산서 생성·수정 서비스."""

import pytest
from sqlalchemy import event

from app.enums import ExpenseReportStatus, TripStatus, UserRole
from app.errors import ConflictError, ForbiddenError, NotFoundError, ValidationError
from app.schemas.expense import ExpenseReportCreate, ExpenseReportUpdate
from app.services.expenses import (
    ExpenseFilters,
    create_report,
    get_report,
    list_reports,
    update_report,
)
from tests.factories import (
    make_expense_report,
    make_trip,
    make_trip_master_data,
    make_user,
)


async def _org(session):
    await make_trip_master_data(session)
    manager = await make_user(session, role=UserRole.MANAGER, name="김결재")
    owner = await make_user(session, manager=manager, name="박신청")
    return manager, owner


async def test_create_report_inherits_cost_center_and_approver(db_session):
    manager, owner = await _org(db_session)
    trip = await make_trip(
        db_session, user=owner, status=TripStatus.COMPLETED, approver_id=manager.id
    )

    detail = await create_report(
        db_session, user=owner, payload=ExpenseReportCreate(trip_id=trip.id)
    )

    assert detail.status is ExpenseReportStatus.DRAFT
    assert detail.cost_center_code == trip.cost_center_code
    assert detail.fund_center_code is None
    assert detail.approver_id == manager.id
    assert detail.trip_no == trip.trip_no
    assert detail.report_no.startswith("EX-")
    assert detail.items == []


async def test_create_report_is_rejected_for_a_draft_trip(db_session):
    _, owner = await _org(db_session)
    trip = await make_trip(db_session, user=owner, status=TripStatus.DRAFT)
    with pytest.raises(ConflictError) as excinfo:
        await create_report(db_session, user=owner, payload=ExpenseReportCreate(trip_id=trip.id))
    assert excinfo.value.code == "TRIP_NOT_REPORTABLE"


async def test_only_one_report_per_trip(db_session):
    manager, owner = await _org(db_session)
    trip = await make_trip(
        db_session, user=owner, status=TripStatus.COMPLETED, approver_id=manager.id
    )
    await create_report(db_session, user=owner, payload=ExpenseReportCreate(trip_id=trip.id))
    with pytest.raises(ConflictError) as excinfo:
        await create_report(db_session, user=owner, payload=ExpenseReportCreate(trip_id=trip.id))
    assert excinfo.value.code == "EXPENSE_ALREADY_EXISTS"


async def test_approver_cannot_create_the_report(db_session):
    manager, owner = await _org(db_session)
    trip = await make_trip(
        db_session, user=owner, status=TripStatus.COMPLETED, approver_id=manager.id
    )
    with pytest.raises(ForbiddenError) as excinfo:
        await create_report(db_session, user=manager, payload=ExpenseReportCreate(trip_id=trip.id))
    assert excinfo.value.code == "NOT_TRIP_OWNER"


async def test_creating_a_report_for_someone_elses_trip_is_a_404(db_session):
    _, owner = await _org(db_session)
    stranger = await make_user(db_session, name="남의사람")
    trip = await make_trip(db_session, user=owner, status=TripStatus.COMPLETED)
    with pytest.raises(NotFoundError) as excinfo:
        await create_report(
            db_session, user=stranger, payload=ExpenseReportCreate(trip_id=trip.id)
        )
    assert excinfo.value.code == "TRIP_NOT_FOUND"


async def test_update_sets_the_header_centers(db_session):
    manager, owner = await _org(db_session)
    trip = await make_trip(
        db_session, user=owner, status=TripStatus.COMPLETED, approver_id=manager.id
    )
    report = await make_expense_report(db_session, trip=trip, approver=manager)

    detail = await update_report(
        db_session,
        user=owner,
        report_id=report.id,
        payload=ExpenseReportUpdate(fund_center_code="FC1010", cost_center_code="CC2030"),
    )
    assert detail.fund_center_code == "FC1010"
    assert detail.cost_center_code == "CC2030"


async def test_update_rejects_an_unknown_fund_center(db_session):
    manager, owner = await _org(db_session)
    trip = await make_trip(
        db_session, user=owner, status=TripStatus.COMPLETED, approver_id=manager.id
    )
    report = await make_expense_report(db_session, trip=trip, approver=manager)
    with pytest.raises(ValidationError) as excinfo:
        await update_report(
            db_session,
            user=owner,
            report_id=report.id,
            payload=ExpenseReportUpdate(fund_center_code="FC9999"),
        )
    assert excinfo.value.code == "INVALID_FUND_CENTER"
    assert excinfo.value.field == "fund_center_code"


async def test_update_is_rejected_once_submitted(db_session):
    manager, owner = await _org(db_session)
    trip = await make_trip(
        db_session, user=owner, status=TripStatus.COMPLETED, approver_id=manager.id
    )
    report = await make_expense_report(
        db_session, trip=trip, approver=manager, status=ExpenseReportStatus.SUBMITTED
    )
    with pytest.raises(ConflictError) as excinfo:
        await update_report(
            db_session,
            user=owner,
            report_id=report.id,
            payload=ExpenseReportUpdate(fund_center_code="FC1010"),
        )
    assert excinfo.value.code == "EXPENSE_NOT_EDITABLE"


async def test_get_report_hides_other_peoples_reports(db_session):
    manager, owner = await _org(db_session)
    stranger = await make_user(db_session, name="남의사람")
    trip = await make_trip(
        db_session, user=owner, status=TripStatus.COMPLETED, approver_id=manager.id
    )
    report = await make_expense_report(db_session, trip=trip, approver=manager)
    with pytest.raises(NotFoundError) as excinfo:
        await get_report(db_session, user=stranger, report_id=report.id)
    assert excinfo.value.code == "EXPENSE_NOT_FOUND"

    # 결재자는 볼 수 있다.
    assert (await get_report(db_session, user=manager, report_id=report.id)).id == report.id


async def test_list_scopes(db_session):
    manager, owner = await _org(db_session)
    trip = await make_trip(
        db_session, user=owner, status=TripStatus.COMPLETED, approver_id=manager.id
    )
    await make_expense_report(
        db_session, trip=trip, approver=manager, status=ExpenseReportStatus.SUBMITTED
    )

    mine = await list_reports(db_session, user=owner, filters=ExpenseFilters(scope="mine"))
    assert mine.total == 1

    inbox = await list_reports(db_session, user=manager, filters=ExpenseFilters(scope="approvals"))
    assert inbox.total == 1

    with pytest.raises(ForbiddenError) as excinfo:
        await list_reports(db_session, user=owner, filters=ExpenseFilters(scope="all"))
    assert excinfo.value.code == "FORBIDDEN_SCOPE"


async def test_list_filters_by_status_and_text(db_session):
    manager, owner = await _org(db_session)
    trip = await make_trip(
        db_session,
        user=owner,
        status=TripStatus.COMPLETED,
        approver_id=manager.id,
        title="울산공장 품질점검",
    )
    await make_expense_report(db_session, trip=trip, approver=manager)

    hit = await list_reports(
        db_session, user=owner, filters=ExpenseFilters(status=[ExpenseReportStatus.DRAFT])
    )
    assert hit.total == 1

    miss = await list_reports(
        db_session, user=owner, filters=ExpenseFilters(status=[ExpenseReportStatus.APPROVED])
    )
    assert miss.total == 0

    by_text = await list_reports(db_session, user=owner, filters=ExpenseFilters(q="울산공장"))
    assert by_text.total == 1


async def test_list_does_not_issue_a_query_per_row(db_session):
    """목록에서 행마다 헬퍼를 부르면 N+1이 된다. 출장 목록과 같은 규칙을 정산에도 건다."""
    manager, owner = await _org(db_session)
    for _ in range(5):
        trip = await make_trip(
            db_session, user=owner, status=TripStatus.COMPLETED, approver_id=manager.id
        )
        await make_expense_report(db_session, trip=trip, approver=manager)

    counter = {"n": 0}

    @event.listens_for(db_session.sync_session, "do_orm_execute")
    def _count(_context) -> None:
        counter["n"] += 1

    page = await list_reports(db_session, user=owner, filters=ExpenseFilters())

    assert page.total == 5
    # count + rows + trips + names. 행 수가 늘어도 이 값은 변하지 않아야 한다.
    assert counter["n"] == 4
