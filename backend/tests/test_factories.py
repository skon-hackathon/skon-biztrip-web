from datetime import date, datetime, timezone
from decimal import Decimal

from app.enums import ExpenseReportStatus, TripStatus, UserRole
from tests.factories import (
    make_card,
    make_card_transaction,
    make_expense_item,
    make_expense_report,
    make_trip,
    make_trip_master_data,
    make_user,
)


async def test_make_user_creates_department_when_omitted(db_session):
    user = await make_user(db_session)

    assert user.id is not None
    assert user.department_id is not None
    assert user.role is UserRole.EMPLOYEE


async def test_make_trip_accepts_overrides(db_session):
    user = await make_user(db_session)

    trip = await make_trip(
        db_session, user=user, status=TripStatus.SUBMITTED, city="서산", start_date=date(2026, 3, 2)
    )

    assert trip.city == "서산"
    assert trip.start_date == date(2026, 3, 2)
    assert trip.end_date == date(2026, 3, 4)
    assert trip.status is TripStatus.SUBMITTED


async def test_make_user_ids_are_unique(db_session):
    first = await make_user(db_session)
    second = await make_user(db_session)

    assert first.email != second.email
    assert first.employee_no != second.employee_no


async def test_make_trip_master_data_is_safe_on_seeded_session(seeded):
    """seed_all이 이미 만든 코드그룹·코스트센터와 겹쳐도 UniqueViolation 없이 통과해야 한다."""
    await make_trip_master_data(seeded)


async def test_make_user_with_manager_inherits_manager_department(db_session):
    manager = await make_user(db_session)

    report = await make_user(db_session, manager=manager)

    assert report.department_id == manager.department_id


async def test_make_card_and_transaction(db_session):
    user = await make_user(db_session)
    card = await make_card(db_session, user=user)
    transaction = await make_card_transaction(
        db_session, card=card, approved_at=datetime(2026, 5, 11, 3, tzinfo=timezone.utc)
    )
    assert transaction.card_id == card.id
    assert transaction.amount_krw == Decimal("30000")
    assert transaction.is_cancelled is False


async def test_make_expense_report_and_item(db_session):
    manager = await make_user(db_session, role=UserRole.MANAGER)
    owner = await make_user(db_session, manager=manager)
    trip = await make_trip(db_session, user=owner, status=TripStatus.COMPLETED)
    report = await make_expense_report(db_session, trip=trip, approver=manager)
    item = await make_expense_item(db_session, report=report, amount=Decimal("12000"))
    assert report.status is ExpenseReportStatus.DRAFT
    assert report.trip_id == trip.id
    assert report.user_id == owner.id
    assert report.approver_id == manager.id
    assert item.report_id == report.id


async def test_make_trip_master_data_is_safe_on_a_seeded_session(seeded):
    """seed와 코드·센터가 겹치므로 두 번 만들면 UniqueViolation이 savepoint 안에서
    터지고, 이후 모든 문장이 PendingRollbackError가 되어 원인이 묻힌다."""
    await make_trip_master_data(seeded)
    await make_trip_master_data(seeded)
