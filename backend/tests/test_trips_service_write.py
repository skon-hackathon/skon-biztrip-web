from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import select

from app.enums import ActivityAction, TripStatus
from app.errors import ConflictError, ForbiddenError, NotFoundError, ValidationError
from app.models import ActivityLog, Trip
from app.schemas.trip import TripCreate, TripUpdate
from app.services.trips import create_trip, delete_trip, update_trip
from tests.factories import make_trip, make_trip_master_data, make_user


def _payload(**overrides) -> TripCreate:
    values = {
        "title": "울산공장 품질점검",
        "purpose_code": "AUDIT",
        "purpose_detail": "라인 3 품질 이슈 현장 확인",
        "destination_type_code": "DOMESTIC",
        "country_code": "KR",
        "city": "울산",
        "start_date": date(2026, 9, 1),
        "end_date": date(2026, 9, 3),
        "transport_code": "RAIL",
        "accommodation_code": "HOTEL",
        "cost_center_code": "CC2030",
        "estimated_cost": Decimal("450000"),
    }
    values.update(overrides)
    return TripCreate.model_validate(values)


async def test_create_returns_draft_with_generated_number(db_session):
    await make_trip_master_data(db_session)
    user = await make_user(db_session)

    detail = await create_trip(db_session, user=user, payload=_payload())

    assert detail.status is TripStatus.DRAFT
    assert detail.trip_no.startswith("BT-")
    assert detail.approver_id is None
    assert detail.user_name == "박출장"


async def test_create_writes_an_activity_log(db_session):
    await make_trip_master_data(db_session)
    user = await make_user(db_session)

    detail = await create_trip(db_session, user=user, payload=_payload())

    log = (await db_session.execute(select(ActivityLog))).scalar_one()
    assert log.entity_id == detail.id
    assert log.action is ActivityAction.CREATED
    assert log.to_status == "DRAFT"


async def test_create_rejects_unknown_code_value(db_session):
    await make_trip_master_data(db_session)
    user = await make_user(db_session)

    with pytest.raises(ValidationError) as exc_info:
        await create_trip(db_session, user=user, payload=_payload(transport_code="ROCKET"))

    assert exc_info.value.code == "INVALID_CODE"
    assert exc_info.value.field == "transport_code"


async def test_create_rejects_unknown_cost_center(db_session):
    await make_trip_master_data(db_session)
    user = await make_user(db_session)

    with pytest.raises(ValidationError) as exc_info:
        await create_trip(db_session, user=user, payload=_payload(cost_center_code="CC0000"))

    assert exc_info.value.code == "INVALID_COST_CENTER"


async def test_create_rejects_end_before_start(db_session):
    await make_trip_master_data(db_session)
    user = await make_user(db_session)

    with pytest.raises(ValidationError) as exc_info:
        await create_trip(
            db_session,
            user=user,
            payload=_payload(start_date=date(2026, 9, 5), end_date=date(2026, 9, 1)),
        )

    assert exc_info.value.code == "INVALID_DATE_RANGE"


async def test_create_rejects_negative_estimated_cost(db_session):
    await make_trip_master_data(db_session)
    user = await make_user(db_session)

    with pytest.raises(ValidationError) as exc_info:
        await create_trip(db_session, user=user, payload=_payload(estimated_cost=Decimal("-1")))

    assert exc_info.value.code == "INVALID_AMOUNT"


async def test_create_rejects_amount_that_would_overflow_the_column(db_session):
    """Numeric(14, 2)를 넘는 값은 400으로 막는다. 통과시키면 flush에서 500이 되고,
    Agent는 5xx를 재시도하므로 성공할 수 없는 요청에 재시도 루프가 걸린다."""
    await make_trip_master_data(db_session)
    user = await make_user(db_session)

    with pytest.raises(ValidationError) as exc_info:
        await create_trip(
            db_session, user=user, payload=_payload(estimated_cost=Decimal("1000000000000"))
        )

    assert exc_info.value.code == "INVALID_AMOUNT"


async def test_create_numbers_trips_sequentially(db_session):
    await make_trip_master_data(db_session)
    user = await make_user(db_session)

    first = await create_trip(db_session, user=user, payload=_payload())
    second = await create_trip(db_session, user=user, payload=_payload())

    assert first.trip_no != second.trip_no


async def test_update_applies_only_the_sent_fields(db_session):
    await make_trip_master_data(db_session)
    user = await make_user(db_session)
    trip = await make_trip(db_session, user=user)

    detail = await update_trip(
        db_session, user=user, trip_id=trip.id, payload=TripUpdate(city="서산")
    )

    assert detail.city == "서산"
    assert detail.title == "울산공장 품질점검"


async def test_update_validates_merged_dates_not_just_sent_ones(db_session):
    await make_trip_master_data(db_session)
    user = await make_user(db_session)
    trip = await make_trip(db_session, user=user, start_date=date(2026, 9, 1))

    with pytest.raises(ValidationError) as exc_info:
        await update_trip(
            db_session, user=user, trip_id=trip.id, payload=TripUpdate(end_date=date(2026, 8, 1))
        )

    assert exc_info.value.code == "INVALID_DATE_RANGE"


async def test_update_rejects_submitted_trip(db_session):
    await make_trip_master_data(db_session)
    user = await make_user(db_session)
    trip = await make_trip(db_session, user=user, status=TripStatus.SUBMITTED)

    with pytest.raises(ConflictError) as exc_info:
        await update_trip(db_session, user=user, trip_id=trip.id, payload=TripUpdate(city="서산"))

    assert exc_info.value.code == "TRIP_NOT_EDITABLE"


async def test_update_allows_rejected_trip(db_session):
    await make_trip_master_data(db_session)
    user = await make_user(db_session)
    trip = await make_trip(db_session, user=user, status=TripStatus.REJECTED)

    detail = await update_trip(
        db_session, user=user, trip_id=trip.id, payload=TripUpdate(city="서산")
    )

    assert detail.city == "서산"


async def test_update_by_approver_is_forbidden(db_session):
    await make_trip_master_data(db_session)
    manager = await make_user(db_session)
    user = await make_user(db_session, manager=manager)
    trip = await make_trip(
        db_session, user=user, status=TripStatus.REJECTED, approver_id=manager.id
    )

    with pytest.raises(ForbiddenError) as exc_info:
        await update_trip(
            db_session, user=manager, trip_id=trip.id, payload=TripUpdate(city="서산")
        )

    assert exc_info.value.code == "NOT_TRIP_OWNER"


async def test_update_writes_an_activity_log(db_session):
    await make_trip_master_data(db_session)
    user = await make_user(db_session)
    trip = await make_trip(db_session, user=user)

    await update_trip(db_session, user=user, trip_id=trip.id, payload=TripUpdate(city="서산"))

    log = (await db_session.execute(select(ActivityLog))).scalar_one()
    assert log.action is ActivityAction.UPDATED
    assert log.from_status == "DRAFT"
    assert log.to_status == "DRAFT"


async def test_delete_removes_a_draft(db_session):
    user = await make_user(db_session)
    trip = await make_trip(db_session, user=user)

    await delete_trip(db_session, user=user, trip_id=trip.id)

    assert (await db_session.execute(select(Trip))).scalars().all() == []


async def test_delete_rejects_non_draft(db_session):
    user = await make_user(db_session)
    trip = await make_trip(db_session, user=user, status=TripStatus.SUBMITTED)

    with pytest.raises(ConflictError) as exc_info:
        await delete_trip(db_session, user=user, trip_id=trip.id)

    assert exc_info.value.code == "TRIP_NOT_DELETABLE"


async def test_delete_of_someone_elses_trip_is_404(db_session):
    owner = await make_user(db_session)
    stranger = await make_user(db_session)
    trip = await make_trip(db_session, user=owner)

    with pytest.raises(NotFoundError):
        await delete_trip(db_session, user=stranger, trip_id=trip.id)
