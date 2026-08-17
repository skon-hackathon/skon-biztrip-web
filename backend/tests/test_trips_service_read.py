from datetime import date

import pytest
from sqlalchemy import event

from app.enums import TripStatus, UserRole
from app.errors import ForbiddenError, NotFoundError
from app.services.trips import TripFilters, get_trip, list_trips
from tests.factories import make_cost_center, make_trip, make_user


async def test_list_returns_only_my_trips(db_session):
    manager = await make_user(db_session, role=UserRole.MANAGER, name="김연구")
    me = await make_user(db_session, manager=manager, name="나")
    other = await make_user(db_session, manager=manager, name="남")
    await make_trip(db_session, user=me)
    await make_trip(db_session, user=other)

    page = await list_trips(db_session, user=me, filters=TripFilters())

    assert page.total == 1
    assert page.items[0].user_name == "나"


async def test_list_approvals_scope_returns_trips_assigned_to_me(db_session):
    manager = await make_user(db_session, role=UserRole.MANAGER, name="김연구")
    employee = await make_user(db_session, manager=manager, name="이사원")
    await make_trip(db_session, user=employee, status=TripStatus.SUBMITTED, approver_id=manager.id)
    await make_trip(db_session, user=employee)

    page = await list_trips(db_session, user=manager, filters=TripFilters(scope="approvals"))

    assert page.total == 1
    assert page.items[0].approver_name == "김연구"
    assert page.items[0].user_name == "이사원"


async def test_list_all_scope_requires_admin(db_session):
    user = await make_user(db_session)

    with pytest.raises(ForbiddenError) as exc_info:
        await list_trips(db_session, user=user, filters=TripFilters(scope="all"))

    assert exc_info.value.status_code == 403
    assert exc_info.value.code == "FORBIDDEN_SCOPE"


async def test_list_all_scope_allows_admin(db_session):
    admin = await make_user(db_session, role=UserRole.ADMIN)
    other = await make_user(db_session)
    await make_trip(db_session, user=other)

    page = await list_trips(db_session, user=admin, filters=TripFilters(scope="all"))

    assert page.total == 1


async def test_list_filters_by_status_and_country(db_session):
    user = await make_user(db_session)
    await make_trip(db_session, user=user, status=TripStatus.DRAFT, country_code="KR")
    await make_trip(db_session, user=user, status=TripStatus.SUBMITTED, country_code="KR")
    await make_trip(db_session, user=user, status=TripStatus.SUBMITTED, country_code="US")

    page = await list_trips(
        db_session,
        user=user,
        filters=TripFilters(status=[TripStatus.SUBMITTED], country_code="US"),
    )

    assert page.total == 1
    assert page.items[0].country_code == "US"


async def test_list_filters_by_multiple_statuses(db_session):
    user = await make_user(db_session)
    await make_trip(db_session, user=user, status=TripStatus.DRAFT)
    await make_trip(db_session, user=user, status=TripStatus.SUBMITTED)
    await make_trip(db_session, user=user, status=TripStatus.APPROVED)

    page = await list_trips(
        db_session,
        user=user,
        filters=TripFilters(status=[TripStatus.SUBMITTED, TripStatus.APPROVED]),
    )

    assert page.total == 2


async def test_list_filters_by_destination_type(db_session):
    user = await make_user(db_session)
    await make_trip(db_session, user=user, destination_type_code="DOMESTIC")
    await make_trip(db_session, user=user, destination_type_code="OVERSEAS")

    page = await list_trips(
        db_session, user=user, filters=TripFilters(destination_type_code="OVERSEAS")
    )

    assert page.total == 1


async def test_list_filters_by_start_date_window(db_session):
    user = await make_user(db_session)
    await make_trip(db_session, user=user, start_date=date(2026, 1, 10))
    await make_trip(db_session, user=user, start_date=date(2026, 5, 10))

    page = await list_trips(
        db_session,
        user=user,
        filters=TripFilters(start_date_from=date(2026, 4, 1), start_date_to=date(2026, 6, 1)),
    )

    assert page.total == 1
    assert page.items[0].start_date == date(2026, 5, 10)


async def test_list_search_matches_title_city_and_trip_no(db_session):
    user = await make_user(db_session)
    await make_trip(db_session, user=user, title="헝가리 배터리 감사", city="Iváncsa")
    await make_trip(db_session, user=user, title="울산공장 품질점검", city="울산")

    assert (await list_trips(db_session, user=user, filters=TripFilters(q="헝가리"))).total == 1
    assert (await list_trips(db_session, user=user, filters=TripFilters(q="울산"))).total == 1
    assert (await list_trips(db_session, user=user, filters=TripFilters(q="BT-9999"))).total == 2


async def test_list_is_ordered_by_start_date_desc_and_paginated(db_session):
    user = await make_user(db_session)
    for day in (1, 2, 3):
        await make_trip(db_session, user=user, start_date=date(2026, 5, day))

    first = await list_trips(db_session, user=user, filters=TripFilters(page=1, size=2))
    second = await list_trips(db_session, user=user, filters=TripFilters(page=2, size=2))

    assert first.total == 3
    assert [item.start_date.day for item in first.items] == [3, 2]
    assert [item.start_date.day for item in second.items] == [1]


async def test_list_does_not_issue_a_query_per_row(db_session):
    manager = await make_user(db_session, role=UserRole.MANAGER)
    user = await make_user(db_session, manager=manager)
    for _ in range(10):
        await make_trip(db_session, user=user, status=TripStatus.SUBMITTED, approver_id=manager.id)

    counter = {"n": 0}

    @event.listens_for(db_session.sync_session, "do_orm_execute")
    def _count(_context) -> None:
        counter["n"] += 1

    page = await list_trips(db_session, user=user, filters=TripFilters())

    assert page.total == 10
    # count + rows + names 한 번씩. 행 수가 늘어도 이 값은 변하지 않아야 한다.
    assert counter["n"] == 3


async def test_get_trip_returns_detail_with_names(db_session):
    await make_cost_center(db_session, "CC2030")
    manager = await make_user(db_session, role=UserRole.MANAGER, name="김연구")
    user = await make_user(db_session, manager=manager, name="이사원")
    trip = await make_trip(
        db_session, user=user, status=TripStatus.SUBMITTED, approver_id=manager.id
    )

    detail = await get_trip(db_session, user=user, trip_id=trip.id)

    assert detail.user_name == "이사원"
    assert detail.approver_name == "김연구"
    assert detail.cost_center_name == "CC2030 센터"
    assert detail.purpose_detail == "라인 3 품질 이슈 현장 확인"


async def test_get_trip_hides_other_peoples_trips_as_404(db_session):
    owner = await make_user(db_session)
    stranger = await make_user(db_session)
    trip = await make_trip(db_session, user=owner)

    with pytest.raises(NotFoundError) as exc_info:
        await get_trip(db_session, user=stranger, trip_id=trip.id)

    assert exc_info.value.status_code == 404
    assert exc_info.value.code == "TRIP_NOT_FOUND"


async def test_get_trip_returns_404_for_missing_id(db_session):
    user = await make_user(db_session)

    with pytest.raises(NotFoundError):
        await get_trip(db_session, user=user, trip_id=999_999)


async def test_approver_can_read_the_trip(db_session):
    manager = await make_user(db_session, role=UserRole.MANAGER)
    user = await make_user(db_session, manager=manager)
    trip = await make_trip(
        db_session, user=user, status=TripStatus.SUBMITTED, approver_id=manager.id
    )

    detail = await get_trip(db_session, user=manager, trip_id=trip.id)

    assert detail.id == trip.id


async def test_admin_can_read_anyones_trip(db_session):
    admin = await make_user(db_session, role=UserRole.ADMIN)
    owner = await make_user(db_session)
    trip = await make_trip(db_session, user=owner)

    detail = await get_trip(db_session, user=admin, trip_id=trip.id)

    assert detail.id == trip.id
