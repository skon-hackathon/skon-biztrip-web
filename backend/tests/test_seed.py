from datetime import timedelta

from sqlalchemy import DateTime, cast, func, select

from app.enums import TripStatus, UserRole
from app.models import (
    CardTransaction,
    Code,
    CodeGroup,
    CorporateCard,
    CostCenter,
    Department,
    ExpenseItem,
    ExpenseReport,
    FundCenter,
    Trip,
    User,
)
from app.seed import seed_all


async def _count(db_session, model) -> int:
    return (await db_session.execute(select(func.count()).select_from(model))).scalar_one()


async def test_seed_creates_expected_master_data(db_session):
    await seed_all(db_session)

    assert await _count(db_session, Department) == 4
    assert await _count(db_session, User) == 14
    assert await _count(db_session, CodeGroup) == 9
    assert await _count(db_session, FundCenter) == 6
    assert await _count(db_session, CostCenter) == 10
    assert await _count(db_session, CorporateCard) == 14
    assert await _count(db_session, Trip) == 40
    assert await _count(db_session, ExpenseReport) == 12
    assert await _count(db_session, CardTransaction) >= 600
    assert await _count(db_session, ExpenseItem) >= 24


async def test_seed_is_idempotent(db_session):
    await seed_all(db_session)
    first_users = await _count(db_session, User)
    first_txns = await _count(db_session, CardTransaction)
    first_trips = await _count(db_session, Trip)
    first_reports = await _count(db_session, ExpenseReport)

    await seed_all(db_session)

    assert await _count(db_session, User) == first_users
    assert await _count(db_session, CardTransaction) == first_txns
    assert await _count(db_session, Trip) == first_trips
    assert await _count(db_session, ExpenseReport) == first_reports


async def test_seed_expense_report_totals_match_items(db_session):
    await seed_all(db_session)

    reports = (await db_session.execute(select(ExpenseReport))).scalars().all()
    assert reports, "expected at least one seeded expense report"
    for report in reports:
        total = (
            await db_session.execute(
                select(func.coalesce(func.sum(ExpenseItem.amount_krw), 0)).where(
                    ExpenseItem.report_id == report.id
                )
            )
        ).scalar_one()
        assert total == report.total_amount_krw


async def test_seed_completed_or_settled_trips_have_a_matching_card_transaction(db_session):
    """Phase 3 자동매칭 데모가 성립하려면, COMPLETED/SETTLED 상태인 모든 출장에 대해
    저자 본인 카드에서 발생한 취소되지 않은 카드거래가 출장 기간(start_date~end_date,
    당일 전체 포함) 안에 최소 1건 존재해야 한다. Date와 timestamptz 경계를 명시적으로
    UTC로 맞춰 비교한다 — 그냥 <= end_date로 비교하면 종료일 당일 자정 이후 거래가
    잘려나간다."""
    await seed_all(db_session)

    window_start = func.timezone("UTC", cast(Trip.start_date, DateTime))
    window_end_exclusive = func.timezone("UTC", cast(Trip.end_date, DateTime)) + timedelta(days=1)

    has_match = (
        select(CardTransaction.id)
        .join(CorporateCard, CorporateCard.id == CardTransaction.card_id)
        .where(
            CorporateCard.user_id == Trip.user_id,
            CardTransaction.is_cancelled.is_(False),
            CardTransaction.approved_at >= window_start,
            CardTransaction.approved_at < window_end_exclusive,
        )
        .exists()
    )

    missing = (
        await db_session.execute(
            select(func.count())
            .select_from(Trip)
            .where(Trip.status.in_([TripStatus.COMPLETED, TripStatus.SETTLED]))
            .where(~has_match)
        )
    ).scalar_one()

    assert missing == 0


async def test_seed_creates_one_admin_and_three_managers(db_session):
    await seed_all(db_session)

    admins = (
        await db_session.execute(select(func.count()).select_from(User).where(User.role == UserRole.ADMIN))
    ).scalar_one()
    managers = (
        await db_session.execute(
            select(func.count()).select_from(User).where(User.role == UserRole.MANAGER)
        )
    ).scalar_one()

    assert admins == 1
    assert managers == 3


async def test_seed_country_code_carries_currency_in_extra(db_session):
    await seed_all(db_session)

    group = (
        await db_session.execute(select(CodeGroup).where(CodeGroup.group_code == "COUNTRY"))
    ).scalar_one()
    us = (
        await db_session.execute(select(Code).where(Code.group_id == group.id, Code.code == "US"))
    ).scalar_one()

    assert us.extra["currency"] == "USD"
