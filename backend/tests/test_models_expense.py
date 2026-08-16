from datetime import date, datetime, timezone
from decimal import Decimal

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.enums import (
    ActivityAction,
    EntityType,
    ExpenseReportStatus,
    NotificationType,
    TripStatus,
    UserRole,
)
from app.models import (
    ActivityLog,
    ApiKey,
    CardTransaction,
    CorporateCard,
    Department,
    ExpenseItem,
    ExpenseReport,
    Notification,
    Trip,
    User,
)


async def _fixture_trip(db_session) -> tuple[User, Trip]:
    dept = Department(code="D800", name="정산테스트부서")
    db_session.add(dept)
    await db_session.flush()
    user = User(
        email="exp@skon.example",
        password_hash="x",
        name="최정산",
        employee_no="E8001",
        department_id=dept.id,
        position_code="STAFF",
        role=UserRole.EMPLOYEE,
    )
    db_session.add(user)
    await db_session.flush()
    trip = Trip(
        trip_no="BT-2026-0800",
        user_id=user.id,
        title="서산공장 출장",
        purpose_code="SUPPORT",
        purpose_detail="설비 지원",
        destination_type_code="DOMESTIC",
        country_code="KR",
        city="서산",
        start_date=date(2026, 7, 1),
        end_date=date(2026, 7, 2),
        transport_code="CAR",
        accommodation_code="HOTEL",
        cost_center_code="CC2030",
        estimated_cost=Decimal("200000"),
        status=TripStatus.COMPLETED,
    )
    db_session.add(trip)
    await db_session.flush()
    return user, trip


async def test_card_transaction_and_expense_item_link(db_session):
    user, trip = await _fixture_trip(db_session)

    card = CorporateCard(user_id=user.id, card_no_masked="5678-****-****-1234", brand="BC")
    db_session.add(card)
    await db_session.flush()

    txn = CardTransaction(
        card_id=card.id,
        approved_at=datetime(2026, 7, 1, 12, 30, tzinfo=timezone.utc),
        merchant_name="서산식당",
        merchant_category_code="MEAL",
        amount=Decimal("32000"),
        currency_code="KRW",
        amount_krw=Decimal("32000"),
    )
    db_session.add(txn)
    await db_session.flush()

    report = ExpenseReport(
        report_no="EX-2026-0800",
        trip_id=trip.id,
        user_id=user.id,
        fund_center_code="FC1010",
        cost_center_code="CC2030",
    )
    db_session.add(report)
    await db_session.flush()

    db_session.add(
        ExpenseItem(
            report_id=report.id,
            card_transaction_id=txn.id,
            expense_category_code="MEAL",
            amount_krw=Decimal("32000"),
        )
    )
    await db_session.flush()

    saved = (
        await db_session.execute(select(ExpenseReport).where(ExpenseReport.report_no == "EX-2026-0800"))
    ).scalar_one()
    assert saved.status is ExpenseReportStatus.DRAFT
    assert saved.total_amount_krw == Decimal("0")

    item = (await db_session.execute(select(ExpenseItem))).scalars().first()
    assert item.fund_center_code is None
    assert item.cost_center_code is None
    assert item.is_excluded is False


async def test_expense_item_unique_constraint_on_report_and_card_transaction(db_session):
    user, trip = await _fixture_trip(db_session)

    card = CorporateCard(user_id=user.id, card_no_masked="1111-****-****-2222", brand="BC")
    db_session.add(card)
    await db_session.flush()

    txn = CardTransaction(
        card_id=card.id,
        approved_at=datetime(2026, 7, 1, 9, 0, tzinfo=timezone.utc),
        merchant_name="서산주유소",
        merchant_category_code="FUEL",
        amount=Decimal("50000"),
        currency_code="KRW",
        amount_krw=Decimal("50000"),
    )
    db_session.add(txn)
    await db_session.flush()

    report = ExpenseReport(report_no="EX-2026-0801", trip_id=trip.id, user_id=user.id)
    db_session.add(report)
    await db_session.flush()

    # PostgreSQL은 NULL을 서로 다른 값으로 취급하므로 card_transaction_id가 NULL인
    # 수기 입력 항목은 같은 보고서에 여러 개 있어도 유니크 제약에 걸리지 않는다.
    db_session.add(
        ExpenseItem(
            report_id=report.id,
            card_transaction_id=None,
            expense_category_code="MEAL",
            amount_krw=Decimal("10000"),
        )
    )
    db_session.add(
        ExpenseItem(
            report_id=report.id,
            card_transaction_id=None,
            expense_category_code="MEAL",
            amount_krw=Decimal("12000"),
        )
    )
    await db_session.flush()

    null_items = (
        await db_session.execute(
            select(ExpenseItem).where(
                ExpenseItem.report_id == report.id, ExpenseItem.card_transaction_id.is_(None)
            )
        )
    ).scalars().all()
    assert len(null_items) == 2

    # 같은 카드 거래를 같은 보고서에 두 번 연결하면 유니크 제약을 위반해야 한다.
    db_session.add(
        ExpenseItem(
            report_id=report.id,
            card_transaction_id=txn.id,
            expense_category_code="FUEL",
            amount_krw=Decimal("50000"),
        )
    )
    await db_session.flush()

    db_session.add(
        ExpenseItem(
            report_id=report.id,
            card_transaction_id=txn.id,
            expense_category_code="FUEL",
            amount_krw=Decimal("50000"),
        )
    )
    with pytest.raises(IntegrityError):
        await db_session.flush()
    await db_session.rollback()


async def test_api_key_stores_hash_and_scopes(db_session):
    user, _ = await _fixture_trip(db_session)

    db_session.add(
        ApiKey(
            user_id=user.id,
            name="agent-key",
            key_prefix="sk_live_abcd1234",
            key_hash="0" * 64,
            scopes=["trips:read", "trips:write"],
        )
    )
    await db_session.flush()

    key = (await db_session.execute(select(ApiKey))).scalar_one()
    assert key.scopes == ["trips:read", "trips:write"]
    assert key.revoked_at is None
    assert key.last_used_at is None


async def test_notification_and_activity_log(db_session):
    user, trip = await _fixture_trip(db_session)

    db_session.add(
        Notification(
            user_id=user.id,
            type=NotificationType.TRIP_SUBMITTED,
            title="결재 요청",
            body="서산공장 출장 결재 요청",
            link_url=f"/trips/{trip.id}",
        )
    )
    db_session.add(
        ActivityLog(
            entity_type=EntityType.TRIP,
            entity_id=trip.id,
            actor_id=user.id,
            action=ActivityAction.SUBMITTED,
            from_status="DRAFT",
            to_status="SUBMITTED",
        )
    )
    await db_session.flush()

    noti = (await db_session.execute(select(Notification))).scalar_one()
    log = (await db_session.execute(select(ActivityLog))).scalar_one()
    assert noti.is_read is False
    assert log.entity_type is EntityType.TRIP
