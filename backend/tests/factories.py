"""테스트용 최소 객체 생성기.

Trip·User는 NOT NULL 컬럼이 많아 테스트마다 손으로 채우면 금세 어긋난다.
trip_no는 BT-9999-* 를 쓴다 — 채번 테스트(현재 연도)와 절대 겹치지 않게 하기 위해서다.
생성된 email·employee_no·trip_no 값 자체를 단언하지 말 것 — `_counter`는 세션 동안
초기화되지 않아 `-k`·`--lf`·단일 파일 실행에 따라 값이 달라진다.
"""

from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.enums import TripStatus, UserRole
from app.models import Code, CodeGroup, CostCenter, Department, FundCenter, Trip, User


_counter = {"n": 0}


def _next() -> int:
    _counter["n"] += 1
    return _counter["n"]


async def make_department(session: AsyncSession, *, name: str = "테스트부서") -> Department:
    dept = Department(code=f"D9{_next():03d}", name=name)
    session.add(dept)
    await session.flush()
    return dept


async def make_user(
    session: AsyncSession,
    *,
    department: Department | None = None,
    role: UserRole = UserRole.EMPLOYEE,
    manager: User | None = None,
    name: str = "박출장",
) -> User:
    # app/seed.py의 _seed_users와 같은 순서: 명시적 department > manager의 department > 새로 생성.
    # 그래야 팩토리로 만든 조직도 seed와 같은 모양(매니저와 보고자가 같은 부서)이 된다.
    if department is not None:
        department_id = department.id
    elif manager is not None:
        department_id = manager.department_id
    else:
        department_id = (await make_department(session)).id
    n = _next()
    user = User(
        email=f"factory{n}@skon.example",
        password_hash="x",
        name=name,
        employee_no=f"E9{n:03d}",
        department_id=department_id,
        position_code="STAFF",
        role=role,
        manager_id=manager.id if manager else None,
    )
    session.add(user)
    await session.flush()
    return user


async def make_code_group(
    session: AsyncSession, group_code: str, codes: list[str], *, is_active: bool = True
) -> CodeGroup:
    group = CodeGroup(group_code=group_code, name=group_code, is_active=is_active)
    session.add(group)
    await session.flush()
    for order, code in enumerate(codes, start=1):
        session.add(Code(group_id=group.id, code=code, name=code, sort_order=order))
    await session.flush()
    return group


async def make_cost_center(
    session: AsyncSession, code: str = "CC9001", *, is_active: bool = True
) -> CostCenter:
    center = CostCenter(code=code, name=f"{code} 센터", is_active=is_active)
    session.add(center)
    await session.flush()
    return center


async def make_fund_center(
    session: AsyncSession, code: str = "FC9001", *, is_active: bool = True
) -> FundCenter:
    center = FundCenter(code=code, name=f"{code} 센터", is_active=is_active)
    session.add(center)
    await session.flush()
    return center


async def make_trip(
    session: AsyncSession, *, user: User, status: TripStatus = TripStatus.DRAFT, **overrides
) -> Trip:
    n = _next()
    start = overrides.pop("start_date", date(2026, 9, 1))
    values = {
        "trip_no": f"BT-9999-{n:04d}",
        "user_id": user.id,
        "title": "울산공장 품질점검",
        "purpose_code": "AUDIT",
        "purpose_detail": "라인 3 품질 이슈 현장 확인",
        "destination_type_code": "DOMESTIC",
        "country_code": "KR",
        "city": "울산",
        "start_date": start,
        "end_date": overrides.pop("end_date", start + timedelta(days=2)),
        "transport_code": "RAIL",
        "accommodation_code": "HOTEL",
        "cost_center_code": "CC2030",
        "estimated_cost": Decimal("450000"),
        "status": status,
    }
    values.update(overrides)
    trip = Trip(**values)
    session.add(trip)
    await session.flush()
    return trip


async def make_trip_master_data(session: AsyncSession) -> None:
    """make_trip이 쓰는 코드값과 코스트센터를 실제로 존재하게 만든다.

    서비스 레이어 검증을 타는 테스트에서만 필요하다 (모델 레벨 테스트는 코드값을
    검증하지 않으므로 없어도 통과한다). app/seed.py가 만드는 것과 group_code·code가
    겹치므로 `seeded` 세션에서 불러도 안전하도록 이미 있는 것은 건너뛴다."""
    groups = {
        "TRIP_PURPOSE": ["AUDIT", "CUSTOMER"],
        "DESTINATION_TYPE": ["DOMESTIC", "OVERSEAS"],
        "COUNTRY": ["KR", "US"],
        "TRANSPORT": ["RAIL", "AIR"],
        "ACCOMMODATION": ["HOTEL", "DORM"],
    }
    existing_groups = set(
        (
            await session.execute(
                select(CodeGroup.group_code).where(CodeGroup.group_code.in_(groups))
            )
        ).scalars()
    )
    for group_code, codes in groups.items():
        if group_code not in existing_groups:
            await make_code_group(session, group_code, codes)

    cost_center_code = "CC2030"
    existing_center = (
        await session.execute(
            select(CostCenter.code).where(CostCenter.code == cost_center_code)
        )
    ).scalar_one_or_none()
    if existing_center is None:
        await make_cost_center(session, cost_center_code)
