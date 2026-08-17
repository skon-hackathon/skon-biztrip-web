from datetime import date

from app.services.numbering import next_trip_no
from tests.factories import make_trip, make_user


async def test_first_trip_of_the_year(db_session):
    assert await next_trip_no(db_session, date(2026, 1, 5)) == "BT-2026-0001"


async def test_increments_from_the_highest_existing_number(db_session):
    user = await make_user(db_session)
    await make_trip(db_session, user=user, trip_no="BT-2026-0007")
    await make_trip(db_session, user=user, trip_no="BT-2026-0003")

    assert await next_trip_no(db_session, date(2026, 8, 17)) == "BT-2026-0008"


async def test_numbering_is_scoped_per_year(db_session):
    user = await make_user(db_session)
    await make_trip(db_session, user=user, trip_no="BT-2025-0100")

    assert await next_trip_no(db_session, date(2026, 1, 1)) == "BT-2026-0001"


async def test_continues_after_the_demo_seed(seeded):
    assert await next_trip_no(seeded, date(2026, 8, 17)) == "BT-2026-0041"
