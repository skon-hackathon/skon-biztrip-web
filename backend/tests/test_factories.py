from datetime import date

from app.enums import TripStatus, UserRole
from tests.factories import make_trip, make_user


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
