"""멱등 시드. 이미 데이터가 있으면 해당 블록을 건너뛴다."""

import random
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.enums import ExpenseReportStatus, TripStatus, UserRole, UserStatus
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
from app.security import hash_password

RNG_SEED = 20260812
DEFAULT_PASSWORD = "skon1234!"

CODE_GROUPS: dict[str, tuple[str, list[tuple[str, str, dict]]]] = {
    "TRIP_PURPOSE": (
        "출장목적",
        [
            ("CUSTOMER", "고객미팅", {}),
            ("SUPPORT", "기술지원", {}),
            ("TRAINING", "교육", {}),
            ("CONFERENCE", "컨퍼런스", {}),
            ("AUDIT", "감사", {}),
            ("ETC", "기타", {}),
        ],
    ),
    "DESTINATION_TYPE": ("출장구분", [("DOMESTIC", "국내", {}), ("OVERSEAS", "해외", {})]),
    "TRANSPORT": (
        "이동수단",
        [
            ("AIR", "항공", {}),
            ("RAIL", "철도", {}),
            ("BUS", "버스", {}),
            ("CAR", "자가용", {}),
            ("RENTAL", "렌터카", {}),
        ],
    ),
    "ACCOMMODATION": (
        "숙박유형",
        [
            ("HOTEL", "호텔", {}),
            ("RESIDENCE", "레지던스", {}),
            ("DORM", "사택", {}),
            ("ETC", "기타", {}),
        ],
    ),
    "EXPENSE_CATEGORY": (
        "정산 비목",
        [
            ("MEAL", "식비", {}),
            ("TRANSPORT", "교통비", {}),
            ("LODGING", "숙박비", {}),
            ("ENTERTAIN", "접대비", {}),
            ("ETC", "기타", {}),
        ],
    ),
    "MERCHANT_CATEGORY": (
        "카드 가맹점 업종",
        [
            ("MEAL", "음식점", {}),
            ("TRANSPORT", "교통", {}),
            ("LODGING", "숙박", {}),
            ("ENTERTAIN", "유흥/접대", {}),
            ("ETC", "기타", {}),
        ],
    ),
    "POSITION": (
        "직급",
        [
            ("STAFF", "사원", {}),
            ("SENIOR", "선임", {}),
            ("TEAM_LEADER", "팀장", {}),
            ("DIRECTOR", "임원", {}),
        ],
    ),
    "COUNTRY": (
        "국가",
        [
            ("KR", "대한민국", {"currency": "KRW", "region": "ASIA"}),
            ("US", "미국", {"currency": "USD", "region": "AMERICA"}),
            ("CN", "중국", {"currency": "CNY", "region": "ASIA"}),
            ("JP", "일본", {"currency": "JPY", "region": "ASIA"}),
            ("DE", "독일", {"currency": "EUR", "region": "EUROPE"}),
            ("HU", "헝가리", {"currency": "EUR", "region": "EUROPE"}),
        ],
    ),
    "CURRENCY": (
        "통화",
        [
            ("KRW", "원", {"rate_to_krw": 1}),
            ("USD", "미국 달러", {"rate_to_krw": 1380}),
            ("CNY", "위안", {"rate_to_krw": 190}),
            ("JPY", "엔", {"rate_to_krw": 9}),
            ("EUR", "유로", {"rate_to_krw": 1490}),
        ],
    ),
}

DEPARTMENTS = [
    ("D100", "배터리연구소"),
    ("D200", "생산본부"),
    ("D300", "구매팀"),
    ("D400", "경영지원팀"),
]

FUND_CENTERS = [
    ("FC1010", "배터리연구소 비용처리", "D100"),
    ("FC1020", "생산본부 비용처리", "D200"),
    ("FC1030", "구매팀 비용처리", "D300"),
    ("FC1040", "경영지원팀 비용처리", "D400"),
    ("FC1050", "전사 공통 비용처리", None),
    ("FC1060", "해외법인 비용처리", None),
]

COST_CENTERS = [
    ("CC2010", "배터리연구소 R&D", "D100"),
    ("CC2020", "배터리연구소 시험", "D100"),
    ("CC2030", "생산본부 울산", "D200"),
    ("CC2040", "생산본부 서산", "D200"),
    ("CC2050", "생산본부 품질", "D200"),
    ("CC2060", "구매 국내", "D300"),
    ("CC2070", "구매 해외", "D300"),
    ("CC2080", "경영지원 인사", "D400"),
    ("CC2090", "경영지원 재무", "D400"),
    ("CC2100", "전사 공통", None),
]

TRIP_PURPOSE_LABELS = {code: label for code, label, _ in CODE_GROUPS["TRIP_PURPOSE"][1]}

DOMESTIC_CITIES = ["울산", "서산", "대전", "광주", "포항", "청주"]
OVERSEAS = [("US", "Atlanta"), ("CN", "Yancheng"), ("HU", "Iváncsa"), ("DE", "München"), ("JP", "Osaka")]
MERCHANTS = {
    "MEAL": ["한밭식당", "미가정식", "스타벅스 울산점", "본죽 서산점", "Panera Bread"],
    "TRANSPORT": ["코레일", "카카오T", "인천공항리무진", "Uber", "SK렌터카"],
    "LODGING": ["롯데시티호텔", "신라스테이", "Hampton Inn", "APA Hotel"],
    "ENTERTAIN": ["대가야한우", "명가정육식당"],
    "ETC": ["다이소 울산점", "GS25 서산점", "Walgreens"],
}


async def _is_seeded(session: AsyncSession, model) -> bool:
    count = (await session.execute(select(func.count()).select_from(model))).scalar_one()
    return count > 0


async def _seed_codes(session: AsyncSession) -> None:
    if await _is_seeded(session, CodeGroup):
        return
    for group_code, (name, items) in CODE_GROUPS.items():
        group = CodeGroup(group_code=group_code, name=name)
        session.add(group)
        await session.flush()
        for order, (code, label, extra) in enumerate(items, start=1):
            session.add(
                Code(group_id=group.id, code=code, name=label, sort_order=order, extra=extra)
            )
    await session.flush()


async def _seed_org(session: AsyncSession) -> dict[str, Department]:
    existing = (
        (await session.execute(select(Department).order_by(Department.id))).scalars().all()
    )
    if existing:
        return {d.code: d for d in existing}

    depts = {}
    for code, name in DEPARTMENTS:
        dept = Department(code=code, name=name)
        session.add(dept)
        depts[code] = dept
    await session.flush()
    return depts


async def _seed_centers(session: AsyncSession, depts: dict[str, Department]) -> None:
    # FundCenter와 CostCenter는 서로 독립적으로 채워진 상태일 수 있으므로
    # 각각 자신의 테이블만 보고 판단한다 (하나만 보고 둘 다 건너뛰면 안 됨).
    if not await _is_seeded(session, FundCenter):
        for code, name, dept_code in FUND_CENTERS:
            session.add(
                FundCenter(
                    code=code, name=name, department_id=depts[dept_code].id if dept_code else None
                )
            )
    if not await _is_seeded(session, CostCenter):
        for code, name, dept_code in COST_CENTERS:
            session.add(
                CostCenter(
                    code=code, name=name, department_id=depts[dept_code].id if dept_code else None
                )
            )
    await session.flush()


async def _seed_users(session: AsyncSession, depts: dict[str, Department]) -> list[User]:
    existing = (await session.execute(select(User).order_by(User.id))).scalars().all()
    if existing:
        return list(existing)

    pw = hash_password(DEFAULT_PASSWORD)
    admin = User(
        email="admin@skon.example",
        password_hash=pw,
        name="관리자",
        employee_no="E0001",
        department_id=depts["D400"].id,
        position_code="DIRECTOR",
        role=UserRole.ADMIN,
    )
    session.add(admin)
    await session.flush()

    manager_specs = [
        ("manager1@skon.example", "김연구", "E0002", "D100"),
        ("manager2@skon.example", "박생산", "E0003", "D200"),
        ("manager3@skon.example", "정구매", "E0004", "D300"),
    ]
    managers: list[User] = []
    for email, name, emp_no, dept_code in manager_specs:
        manager = User(
            email=email,
            password_hash=pw,
            name=name,
            employee_no=emp_no,
            department_id=depts[dept_code].id,
            position_code="TEAM_LEADER",
            role=UserRole.MANAGER,
            manager_id=admin.id,
        )
        session.add(manager)
        managers.append(manager)
    await session.flush()

    given = ["민수", "지훈", "서연", "예은", "도윤", "하준", "시우", "채원", "은우", "다은"]
    surnames = ["이", "최", "강", "조", "윤", "장", "임", "한", "오", "서"]
    employees: list[User] = []
    for index in range(10):
        manager = managers[index % 3]
        employee = User(
            email=f"user{index + 1}@skon.example",
            password_hash=pw,
            name=f"{surnames[index]}{given[index]}",
            employee_no=f"E{index + 5:04d}",
            department_id=manager.department_id,
            position_code="STAFF" if index % 2 == 0 else "SENIOR",
            role=UserRole.EMPLOYEE,
            manager_id=manager.id,
        )
        session.add(employee)
        employees.append(employee)
    await session.flush()

    # 승인 화면 시연용 대기 계정. 시드는 멱등해야 하므로 이메일로 존재를 확인하고 건너뛴다.
    pending_email = "newbie@skon.example"
    exists = await session.scalar(select(User).where(User.email == pending_email))
    if exists is None:
        session.add(
            User(
                email=pending_email,
                password_hash=pw,
                name="신입가입",
                employee_no=None,
                department_id=depts["D100"].id,
                position_code=None,
                manager_id=None,
                role=UserRole.EMPLOYEE,
                status=UserStatus.PENDING,
                is_active=False,
            )
        )
        await session.flush()

    return [admin, *managers, *employees]


async def _seed_cards(session: AsyncSession, users: list[User], rng: random.Random) -> None:
    if await _is_seeded(session, CorporateCard):
        return

    cards: list[CorporateCard] = []
    for index, user in enumerate(users):
        card = CorporateCard(
            user_id=user.id,
            card_no_masked=f"5678-****-****-{1000 + index:04d}",
            brand=rng.choice(["BC", "신한", "하나"]),
        )
        session.add(card)
        cards.append(card)
    await session.flush()

    today = date.today()
    for card in cards:
        for _ in range(rng.randint(45, 60)):
            category = rng.choices(
                ["MEAL", "TRANSPORT", "LODGING", "ENTERTAIN", "ETC"],
                weights=[45, 25, 15, 5, 10],
            )[0]
            days_ago = rng.randint(0, 180)
            approved = datetime.combine(
                today - timedelta(days=days_ago),
                datetime.min.time(),
                tzinfo=timezone.utc,
            ) + timedelta(hours=rng.randint(7, 22), minutes=rng.choice([0, 15, 30, 45]))
            base = {
                "MEAL": rng.randrange(8000, 60000, 500),
                "TRANSPORT": rng.randrange(3000, 180000, 500),
                "LODGING": rng.randrange(80000, 320000, 1000),
                "ENTERTAIN": rng.randrange(90000, 400000, 1000),
                "ETC": rng.randrange(3000, 50000, 500),
            }[category]
            session.add(
                CardTransaction(
                    card_id=card.id,
                    approved_at=approved,
                    merchant_name=rng.choice(MERCHANTS[category]),
                    merchant_category_code=category,
                    amount=Decimal(base),
                    currency_code="KRW",
                    amount_krw=Decimal(base),
                    is_cancelled=rng.random() < 0.02,
                )
            )
    await session.flush()


async def _seed_trips(session: AsyncSession, users: list[User], rng: random.Random) -> None:
    if await _is_seeded(session, Trip):
        return

    employees = [u for u in users if u.role == UserRole.EMPLOYEE]
    statuses = (
        [TripStatus.DRAFT] * 5
        + [TripStatus.SUBMITTED] * 7
        + [TripStatus.APPROVED] * 8
        + [TripStatus.REJECTED] * 3
        + [TripStatus.COMPLETED] * 9
        + [TripStatus.SETTLED] * 8
    )
    today = date.today()
    trips: list[Trip] = []

    for index, status in enumerate(statuses, start=1):
        author = employees[index % len(employees)]
        overseas = rng.random() < 0.3
        if overseas:
            country, city = rng.choice(OVERSEAS)
            duration = rng.randint(3, 7)
        else:
            country, city = "KR", rng.choice(DOMESTIC_CITIES)
            duration = rng.randint(1, 3)

        if status in {TripStatus.COMPLETED, TripStatus.SETTLED}:
            # 반드시 과거여야 한다. 종료일이 오늘 이전이어야 COMPLETED로 갈 수 있고,
            # 카드거래(최근 180일)와 기간이 겹쳐야 정산 자동매칭 데모가 성립한다.
            start = today - timedelta(days=rng.randint(duration + 1, 170))
        elif status == TripStatus.APPROVED:
            # 승인만 된 출장은 다가오는 일정일 수도, 이미 다녀온 것일 수도 있다.
            start = today - timedelta(days=rng.randint(-30, 60))
        else:
            # DRAFT / SUBMITTED / REJECTED — 아직 확정 전이라 미래가 자연스럽다.
            start = today - timedelta(days=rng.randint(-45, 30))
        purpose = rng.choice(["CUSTOMER", "SUPPORT", "TRAINING", "CONFERENCE", "AUDIT"])

        submitted_at = None
        approved_at = None
        if status != TripStatus.DRAFT:
            # 시작일보다 며칠 앞서 제출하고, 그로부터 1~2일 뒤 승인되었다고 본다.
            submitted_at = datetime.combine(
                start - timedelta(days=rng.randint(3, 10)),
                datetime.min.time(),
                tzinfo=timezone.utc,
            ) + timedelta(hours=rng.randint(9, 18), minutes=rng.choice([0, 15, 30, 45]))
            if status in {TripStatus.APPROVED, TripStatus.COMPLETED, TripStatus.SETTLED}:
                approved_at = submitted_at + timedelta(
                    days=rng.randint(1, 2), hours=rng.randint(0, 8)
                )

        trip = Trip(
            trip_no=f"BT-2026-{index:04d}",
            user_id=author.id,
            title=f"{city} {'해외' if overseas else '국내'}출장",
            purpose_code=purpose,
            purpose_detail=f"{city} 현장 {TRIP_PURPOSE_LABELS[purpose]} 목적 출장",
            destination_type_code="OVERSEAS" if overseas else "DOMESTIC",
            country_code=country,
            city=city,
            start_date=start,
            end_date=start + timedelta(days=duration),
            # 신청 화면은 코스트센터를 받지 않지만, 시드 출장에는 값을 넣는다 — 정산서가
            # 이 값을 승계하는 경로(services/expenses.py)를 데모에서 보여주기 위해서다.
            cost_center_code=rng.choice([c[0] for c in COST_CENTERS]),
            status=status,
            approver_id=author.manager_id if status != TripStatus.DRAFT else None,
            submitted_at=submitted_at,
            approved_at=approved_at,
            reject_reason="사유 보완 필요" if status == TripStatus.REJECTED else None,
        )
        session.add(trip)
        trips.append(trip)
    await session.flush()

    # 완료/정산된 출장은 실제로 그 기간 동안 저자 본인이 쓴 카드거래가 있어야
    # Phase 3의 자동매칭 데모가 성립한다. 카드거래를 출장과 무관하게 생성하면
    # 매칭 후보가 순전히 우연에 의존하게 되어 후보가 0건인 출장이 나온다.
    cards_by_user = {
        card.user_id: card for card in (await session.execute(select(CorporateCard))).scalars().all()
    }
    for trip in trips:
        if trip.status not in {TripStatus.COMPLETED, TripStatus.SETTLED}:
            continue
        card = cards_by_user.get(trip.user_id)
        if card is None:
            continue
        trip_duration = (trip.end_date - trip.start_date).days
        if trip_duration >= 2:
            # 여러 밤을 묵는 출장이라 숙박비도 자연스럽다.
            categories, weights = ["MEAL", "TRANSPORT", "LODGING"], [55, 30, 15]
        else:
            categories, weights = ["MEAL", "TRANSPORT"], [65, 35]
        for _ in range(rng.randint(2, 5)):
            category = rng.choices(categories, weights=weights)[0]
            day_offset = rng.randint(0, trip_duration)
            approved = datetime.combine(
                trip.start_date + timedelta(days=day_offset),
                datetime.min.time(),
                tzinfo=timezone.utc,
            ) + timedelta(hours=rng.randint(7, 22), minutes=rng.choice([0, 15, 30, 45]))
            base = {
                "MEAL": rng.randrange(8000, 60000, 500),
                "TRANSPORT": rng.randrange(3000, 180000, 500),
                "LODGING": rng.randrange(80000, 320000, 1000),
            }[category]
            session.add(
                CardTransaction(
                    card_id=card.id,
                    approved_at=approved,
                    merchant_name=rng.choice(MERCHANTS[category]),
                    merchant_category_code=category,
                    amount=Decimal(base),
                    currency_code="KRW",
                    amount_krw=Decimal(base),
                    is_cancelled=False,
                )
            )
    await session.flush()

    # SETTLED 출장은 정산서가 APPROVED로 승인됐다는 뜻이므로 정산서가 **반드시** 있어야
    # 한다. 그래서 SETTLED를 먼저 채우고 남는 자리를 COMPLETED로 메운다. 덕분에 정산서가
    # 없는 COMPLETED 출장이 남아 "미정산" 데모와 정산서 생성 시나리오가 성립한다.
    settled_trips = [t for t in trips if t.status == TripStatus.SETTLED]
    completed_trips = [t for t in trips if t.status == TripStatus.COMPLETED]
    settleable = (settled_trips + completed_trips)[:12]
    for index, trip in enumerate(settleable, start=1):
        report = ExpenseReport(
            report_no=f"EX-2026-{index:04d}",
            trip_id=trip.id,
            user_id=trip.user_id,
            status=(
                ExpenseReportStatus.APPROVED
                if trip.status == TripStatus.SETTLED
                else ExpenseReportStatus.DRAFT
            ),
            fund_center_code=rng.choice([c[0] for c in FUND_CENTERS]),
            cost_center_code=trip.cost_center_code,
        )
        session.add(report)
        await session.flush()

        total = Decimal("0")
        for _ in range(rng.randint(2, 5)):
            amount = Decimal(rng.randrange(10000, 250000, 1000))
            total += amount
            session.add(
                ExpenseItem(
                    report_id=report.id,
                    expense_category_code=rng.choice(["MEAL", "TRANSPORT", "LODGING", "ETC"]),
                    amount_krw=amount,
                )
            )
        report.total_amount_krw = total
    await session.flush()


async def seed_all(session: AsyncSession) -> None:
    await _seed_codes(session)
    depts = await _seed_org(session)
    await _seed_centers(session, depts)
    users = await _seed_users(session, depts)
    # 블록마다 독립 시드를 쓴다. 공용 rng 하나를 돌려쓰면 앞 블록이 early-return으로
    # 난수를 소비하지 않았을 때 뒤 블록 결과가 통째로 달라진다.
    await _seed_cards(session, users, random.Random(f"{RNG_SEED}-cards"))
    await _seed_trips(session, users, random.Random(f"{RNG_SEED}-trips"))
    await session.commit()
