from sqlalchemy import func, select

from app.enums import UserRole
from app.models import (
    CardTransaction,
    Code,
    CodeGroup,
    CorporateCard,
    CostCenter,
    Department,
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


async def test_seed_is_idempotent(db_session):
    await seed_all(db_session)
    first_users = await _count(db_session, User)
    first_txns = await _count(db_session, CardTransaction)

    await seed_all(db_session)

    assert await _count(db_session, User) == first_users
    assert await _count(db_session, CardTransaction) == first_txns


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
