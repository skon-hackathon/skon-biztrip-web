from datetime import date
from decimal import Decimal

from sqlalchemy import select

from app.enums import TripStatus, UserRole
from app.models import Department, Trip, User


async def _make_user(db_session) -> User:
    dept = Department(code="D900", name="테스트부서")
    db_session.add(dept)
    await db_session.flush()
    user = User(
        email="trip@skon.example",
        password_hash="x",
        name="박출장",
        employee_no="E9001",
        department_id=dept.id,
        position_code="STAFF",
        role=UserRole.EMPLOYEE,
    )
    db_session.add(user)
    await db_session.flush()
    return user


async def test_trip_defaults_to_draft(db_session):
    user = await _make_user(db_session)

    db_session.add(
        Trip(
            trip_no="BT-2026-0001",
            user_id=user.id,
            title="울산공장 품질점검",
            purpose_code="AUDIT",
            purpose_detail="라인 3 품질 이슈 현장 확인",
            destination_type_code="DOMESTIC",
            country_code="KR",
            city="울산",
            start_date=date(2026, 9, 1),
            end_date=date(2026, 9, 3),
            transport_code="RAIL",
            accommodation_code="HOTEL",
            cost_center_code="CC2030",
            estimated_cost=Decimal("450000"),
        )
    )
    await db_session.flush()

    trip = (await db_session.execute(select(Trip).where(Trip.trip_no == "BT-2026-0001"))).scalar_one()
    assert trip.status is TripStatus.DRAFT
    assert trip.approver_id is None
    assert trip.estimated_cost == Decimal("450000")
