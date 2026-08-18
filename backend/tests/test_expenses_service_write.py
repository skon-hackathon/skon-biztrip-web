"""정산서 생성·수정 서비스."""

from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
from sqlalchemy import event

from app.enums import ExpenseReportStatus, TripStatus, UserRole
from app.errors import ConflictError, ForbiddenError, NotFoundError, ValidationError
from app.schemas.expense import (
    ExpenseItemCreate,
    ExpenseItemUpdate,
    ExpenseReportCreate,
    ExpenseReportUpdate,
)
from app.services.expense_rules import MAX_ITEM_AMOUNT
from app.services.expenses import (
    ExpenseFilters,
    add_item,
    create_report,
    delete_item,
    update_item,
    get_report,
    list_reports,
    update_report,
)
from tests.factories import (
    make_card,
    make_cost_center,
    make_card_transaction,
    make_expense_item,
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


async def _report_with_card(db_session):
    manager, owner = await _org(db_session)
    trip = await make_trip(
        db_session, user=owner, status=TripStatus.COMPLETED, approver_id=manager.id
    )
    report = await make_expense_report(db_session, trip=trip, approver=manager)
    card = await make_card(db_session, user=owner)
    return manager, owner, trip, report, card


def _during(trip, day_offset: int = 0) -> datetime:
    """출장 기간 안의 KST 정오(=UTC 03시)."""
    return datetime.combine(
        trip.start_date + timedelta(days=day_offset), datetime.min.time(), tzinfo=timezone.utc
    ) + timedelta(hours=3)


async def test_add_item_from_a_card_transaction_uses_its_amount(db_session):
    _, owner, trip, report, card = await _report_with_card(db_session)
    transaction = await make_card_transaction(
        db_session, card=card, approved_at=_during(trip), amount=Decimal("45000")
    )

    detail = await add_item(
        db_session,
        user=owner,
        report_id=report.id,
        payload=ExpenseItemCreate(
            card_transaction_id=transaction.id, expense_category_code="MEAL"
        ),
    )

    assert len(detail.items) == 1
    assert detail.items[0].amount_krw == Decimal("45000")
    assert detail.items[0].merchant_name == "한밭식당"
    assert detail.total_amount_krw == Decimal("45000")


async def test_manual_item_requires_an_amount(db_session):
    _, owner, _, report, _ = await _report_with_card(db_session)
    with pytest.raises(ValidationError) as excinfo:
        await add_item(
            db_session,
            user=owner,
            report_id=report.id,
            payload=ExpenseItemCreate(expense_category_code="MEAL"),
        )
    assert excinfo.value.code == "AMOUNT_REQUIRED"
    assert excinfo.value.field == "amount_krw"


async def test_add_item_rejects_an_unknown_category(db_session):
    _, owner, _, report, _ = await _report_with_card(db_session)
    with pytest.raises(ValidationError) as excinfo:
        await add_item(
            db_session,
            user=owner,
            report_id=report.id,
            payload=ExpenseItemCreate(expense_category_code="NOPE", amount_krw=Decimal("1000")),
        )
    assert excinfo.value.code == "INVALID_CODE"
    assert excinfo.value.field == "expense_category_code"


async def test_add_item_rejects_someone_elses_transaction(db_session):
    _, owner, trip, report, _ = await _report_with_card(db_session)
    stranger = await make_user(db_session, name="남의사람")
    stranger_card = await make_card(db_session, user=stranger)
    transaction = await make_card_transaction(
        db_session, card=stranger_card, approved_at=_during(trip)
    )
    with pytest.raises(ValidationError) as excinfo:
        await add_item(
            db_session,
            user=owner,
            report_id=report.id,
            payload=ExpenseItemCreate(
                card_transaction_id=transaction.id, expense_category_code="MEAL"
            ),
        )
    assert excinfo.value.code == "INVALID_TRANSACTION"
    assert excinfo.value.field == "card_transaction_id"


async def test_add_item_rejects_a_cancelled_transaction(db_session):
    _, owner, trip, report, card = await _report_with_card(db_session)
    transaction = await make_card_transaction(
        db_session, card=card, approved_at=_during(trip), is_cancelled=True
    )
    with pytest.raises(ValidationError) as excinfo:
        await add_item(
            db_session,
            user=owner,
            report_id=report.id,
            payload=ExpenseItemCreate(
                card_transaction_id=transaction.id, expense_category_code="MEAL"
            ),
        )
    assert excinfo.value.code == "INVALID_TRANSACTION"


async def test_the_same_transaction_cannot_be_added_twice(db_session):
    _, owner, trip, report, card = await _report_with_card(db_session)
    transaction = await make_card_transaction(db_session, card=card, approved_at=_during(trip))
    payload = ExpenseItemCreate(card_transaction_id=transaction.id, expense_category_code="MEAL")
    await add_item(db_session, user=owner, report_id=report.id, payload=payload)
    with pytest.raises(ConflictError) as excinfo:
        await add_item(db_session, user=owner, report_id=report.id, payload=payload)
    assert excinfo.value.code == "EXPENSE_ITEM_DUPLICATE"


async def test_item_amount_above_the_column_limit_is_a_400_not_a_500(db_session):
    """Numeric(14,2) 오버플로가 flush에서 터지면 500이 되고 Agent가 무한 재시도한다."""
    _, owner, _, report, _ = await _report_with_card(db_session)
    with pytest.raises(ValidationError) as excinfo:
        await add_item(
            db_session,
            user=owner,
            report_id=report.id,
            payload=ExpenseItemCreate(
                expense_category_code="MEAL", amount_krw=MAX_ITEM_AMOUNT + Decimal("1")
            ),
        )
    assert excinfo.value.code == "INVALID_AMOUNT"


async def test_excluded_items_drop_out_of_the_total(db_session):
    _, owner, _, report, _ = await _report_with_card(db_session)
    detail = await add_item(
        db_session,
        user=owner,
        report_id=report.id,
        payload=ExpenseItemCreate(expense_category_code="MEAL", amount_krw=Decimal("10000")),
    )
    item_id = detail.items[0].id
    detail = await add_item(
        db_session,
        user=owner,
        report_id=report.id,
        payload=ExpenseItemCreate(expense_category_code="MEAL", amount_krw=Decimal("5000")),
    )
    assert detail.total_amount_krw == Decimal("15000")

    detail = await update_item(
        db_session, user=owner, item_id=item_id, payload=ExpenseItemUpdate(is_excluded=True)
    )
    assert detail.total_amount_krw == Decimal("5000")


async def test_item_center_override_shows_up_as_effective_value(db_session):
    _, owner, _, report, _ = await _report_with_card(db_session)
    await make_cost_center(db_session, "CC2040")
    await update_report(
        db_session,
        user=owner,
        report_id=report.id,
        payload=ExpenseReportUpdate(fund_center_code="FC1010", cost_center_code="CC2030"),
    )
    detail = await add_item(
        db_session,
        user=owner,
        report_id=report.id,
        payload=ExpenseItemCreate(expense_category_code="MEAL", amount_krw=Decimal("1000")),
    )
    item = detail.items[0]
    assert item.cost_center_code is None
    assert item.effective_cost_center_code == "CC2030"

    detail = await update_item(
        db_session,
        user=owner,
        item_id=item.id,
        payload=ExpenseItemUpdate(cost_center_code="CC2040"),
    )
    assert detail.items[0].cost_center_code == "CC2040"
    assert detail.items[0].effective_cost_center_code == "CC2040"


async def test_delete_item_recomputes_the_total(db_session):
    _, owner, _, report, _ = await _report_with_card(db_session)
    detail = await add_item(
        db_session,
        user=owner,
        report_id=report.id,
        payload=ExpenseItemCreate(expense_category_code="MEAL", amount_krw=Decimal("7000")),
    )
    detail = await delete_item(db_session, user=owner, item_id=detail.items[0].id)
    assert detail.items == []
    assert detail.total_amount_krw == Decimal("0")


async def test_items_cannot_be_touched_once_submitted(db_session):
    manager, owner = await _org(db_session)
    trip = await make_trip(
        db_session, user=owner, status=TripStatus.COMPLETED, approver_id=manager.id
    )
    report = await make_expense_report(
        db_session, trip=trip, approver=manager, status=ExpenseReportStatus.SUBMITTED
    )
    with pytest.raises(ConflictError) as excinfo:
        await add_item(
            db_session,
            user=owner,
            report_id=report.id,
            payload=ExpenseItemCreate(expense_category_code="MEAL", amount_krw=Decimal("1000")),
        )
    assert excinfo.value.code == "EXPENSE_NOT_EDITABLE"


async def test_updating_someone_elses_item_is_a_404(db_session):
    _, owner, _, report, _ = await _report_with_card(db_session)
    stranger = await make_user(db_session, name="남의사람")
    detail = await add_item(
        db_session,
        user=owner,
        report_id=report.id,
        payload=ExpenseItemCreate(expense_category_code="MEAL", amount_krw=Decimal("1000")),
    )
    with pytest.raises(NotFoundError) as excinfo:
        await update_item(
            db_session,
            user=stranger,
            item_id=detail.items[0].id,
            payload=ExpenseItemUpdate(memo="여기 손대지 마"),
        )
    assert excinfo.value.code == "EXPENSE_NOT_FOUND"


async def test_clearing_an_override_returns_to_inheritance(db_session):
    _, owner, _, report, _ = await _report_with_card(db_session)
    await make_cost_center(db_session, "CC2040")
    await update_report(
        db_session,
        user=owner,
        report_id=report.id,
        payload=ExpenseReportUpdate(fund_center_code="FC1010", cost_center_code="CC2030"),
    )
    detail = await add_item(
        db_session,
        user=owner,
        report_id=report.id,
        payload=ExpenseItemCreate(
            expense_category_code="MEAL", amount_krw=Decimal("1000"), cost_center_code="CC2040"
        ),
    )
    detail = await update_item(
        db_session,
        user=owner,
        item_id=detail.items[0].id,
        payload=ExpenseItemUpdate(cost_center_code=None),
    )
    assert detail.items[0].cost_center_code is None
    assert detail.items[0].effective_cost_center_code == "CC2030"
