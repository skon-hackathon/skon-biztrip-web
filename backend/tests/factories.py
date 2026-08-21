"""테스트용 최소 객체 생성기.

Trip·User는 NOT NULL 컬럼이 많아 테스트마다 손으로 채우면 금세 어긋난다.
trip_no는 BT-9999-* 를 쓴다 — 채번 테스트(현재 연도)와 절대 겹치지 않게 하기 위해서다.
생성된 email·employee_no·trip_no 값 자체를 단언하지 말 것 — `_counter`는 세션 동안
초기화되지 않아 `-k`·`--lf`·단일 파일 실행에 따라 값이 달라진다.
"""

from datetime import date, datetime, timedelta
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.enums import ExpenseReportStatus, TripStatus, UserRole, UserStatus
from app.models import (
    ApiKey,
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
    status: UserStatus = UserStatus.ACTIVE,
    is_active: bool = True,
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
        status=status,
        is_active=is_active,
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
        "cost_center_code": "CC2030",
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
        "EXPENSE_CATEGORY": ["MEAL", "TRANSPORT", "LODGING", "ETC"],
        "MERCHANT_CATEGORY": ["MEAL", "TRANSPORT", "LODGING", "ETC"],
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

    fund_center_code = "FC1010"
    existing_fund = (
        await session.execute(select(FundCenter.code).where(FundCenter.code == fund_center_code))
    ).scalar_one_or_none()
    if existing_fund is None:
        await make_fund_center(session, fund_center_code)


async def make_card(session: AsyncSession, *, user: User, is_active: bool = True) -> CorporateCard:
    n = _next()
    card = CorporateCard(
        user_id=user.id,
        card_no_masked=f"5678-****-****-9{n:03d}",
        brand="BC",
        is_active=is_active,
    )
    session.add(card)
    await session.flush()
    return card


async def make_card_transaction(
    session: AsyncSession,
    *,
    card: CorporateCard,
    approved_at: datetime,
    merchant_category_code: str = "MEAL",
    amount: Decimal = Decimal("30000"),
    is_cancelled: bool = False,
) -> CardTransaction:
    transaction = CardTransaction(
        card_id=card.id,
        approved_at=approved_at,
        merchant_name="한밭식당",
        merchant_category_code=merchant_category_code,
        amount=amount,
        currency_code="KRW",
        amount_krw=amount,
        is_cancelled=is_cancelled,
    )
    session.add(transaction)
    await session.flush()
    return transaction


async def make_expense_report(
    session: AsyncSession,
    *,
    trip: Trip,
    approver: User | None = None,
    status: ExpenseReportStatus = ExpenseReportStatus.DRAFT,
    fund_center_code: str | None = "FC1010",
    cost_center_code: str | None = None,
) -> ExpenseReport:
    """report_no는 EX-9999-* 를 쓴다 — 채번 테스트(현재 연도)와 겹치지 않게 하기 위해서다."""
    n = _next()
    report = ExpenseReport(
        report_no=f"EX-9999-{n:04d}",
        trip_id=trip.id,
        user_id=trip.user_id,
        status=status,
        fund_center_code=fund_center_code,
        cost_center_code=cost_center_code or trip.cost_center_code,
        approver_id=approver.id if approver else trip.approver_id,
    )
    session.add(report)
    await session.flush()
    return report


async def make_expense_item(
    session: AsyncSession,
    *,
    report: ExpenseReport,
    amount: Decimal = Decimal("30000"),
    card_transaction: CardTransaction | None = None,
    expense_category_code: str = "MEAL",
    is_excluded: bool = False,
    fund_center_code: str | None = None,
    cost_center_code: str | None = None,
) -> ExpenseItem:
    item = ExpenseItem(
        report_id=report.id,
        card_transaction_id=card_transaction.id if card_transaction else None,
        expense_category_code=expense_category_code,
        amount_krw=amount,
        is_excluded=is_excluded,
        fund_center_code=fund_center_code,
        cost_center_code=cost_center_code,
    )
    session.add(item)
    await session.flush()
    return item


async def make_api_key(
    session: AsyncSession,
    *,
    user: User,
    scopes: list[str] | None = None,
    name: str = "테스트 키",
    expires_at: datetime | None = None,
    revoked_at: datetime | None = None,
) -> tuple[str, ApiKey]:
    """(평문, 행)을 돌려준다. 평문은 여기서만 얻을 수 있다 — DB에는 해시만 남는다."""
    from app.services.api_keys import generate_key

    raw, prefix, digest = generate_key()
    key = ApiKey(
        user_id=user.id,
        name=name,
        key_prefix=prefix,
        key_hash=digest,
        # StrEnum 멤버가 섞여 들어와도 ARRAY(String)에는 값 문자열로 저장되게 강제한다.
        scopes=[str(scope) for scope in (scopes or [])],
        expires_at=expires_at,
        revoked_at=revoked_at,
    )
    session.add(key)
    await session.flush()
    return raw, key
