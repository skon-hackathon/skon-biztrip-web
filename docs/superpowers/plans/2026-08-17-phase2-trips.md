# Phase 2: 출장 — 신청·목록·상세·수정·결재·타임라인·알림 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 출장 신청부터 결재까지의 전체 흐름을 웹 UI와 API 양쪽에서 동작시킨다. 사람이 화면에서 하는 일(신청·상신·승인·반려·완료)을 Agent가 같은 엔드포인트로 수행할 수 있다.

**Architecture:** 백엔드는 `routers/`(HTTP·인증) → `services/`(비즈니스 규칙) → `models/`(ORM) 3계층을 유지한다. 도메인 규칙은 DB를 모르는 순수 함수(`services/trip_rules.py`)로 분리해 단위테스트로 전부 덮고, 상태 전이는 `services/trips.py`의 함수들만 통과하며 그 안에서 `services/history.py`가 `activity_log`와 `notification`을 함께 기록한다. 프론트엔드는 SvelteKit SPA로, 인증이 필요한 모든 호출이 `authRequest`를 거쳐 401을 전역 처리한다.

**Tech Stack:** FastAPI · SQLAlchemy 2.0 async · Pydantic v2 · pytest / SvelteKit 2 · Svelte 5 runes · TailwindCSS v4 · vitest

---

## 이 Phase가 만드는 것

| 영역 | 산출물 |
|---|---|
| API | `GET·POST /trips`, `GET·PATCH·DELETE /trips/{id}`, `POST /trips/{id}/submit·approve·reject·reopen·complete`, `GET /trips/{id}/timeline`, `GET /codes`, `GET /codes/{group_code}`, `GET /fund-centers`, `GET /cost-centers`, `GET /notifications`, `POST /notifications/{id}/read` |
| 화면 | `/trips`, `/trips/new`, `/trips/[id]`, `/trips/[id]/edit`, `/approvals`, `/notifications`, 대시보드 `/` 연결 |
| 이월 처리 | `validate_codes` 오케스트레이터, 교차필드 검증, 전이 권한·조건, 이름 직렬화 N+1 방지, `authRequest` 래퍼, 전역 401, 딥링크 보존, 공개 경로 접두사 매칭 |

## 이 Phase가 만들지 않는 것

- 정산(`expense_report` / `expense_item` / 자동매칭 / 카드내역 화면) — Phase 3
- `COMPLETED → SETTLED` 전이 — 정산서 승인이 트리거이므로 Phase 3
- API Key 인증과 스코프 검사(`request.state.scopes`의 `UNRESTRICTED` 센티널 비교) — Phase 4
- Admin CRUD — Phase 5
- 744px 미만 반응형 붕괴(햄버거·시트) — 데스크톱 데모 우선, 모바일 대응 Phase에서 처음부터 만든다
- 비밀번호 변경 엔드포인트 및 그에 딸린 72바이트 길이 검증 — 해당 엔드포인트를 만드는 Phase에서

## 파일 구조

**백엔드 — 신규**

| 파일 | 책임 |
|---|---|
| `backend/app/services/centers.py` | 활성 Fund/Cost Center 코드 로드, 코스트센터 검증 |
| `backend/app/services/trip_rules.py` | 출장 도메인 순수 규칙 (날짜·금액·권한·수정가능·완료조건). DB 접근 없음 |
| `backend/app/services/numbering.py` | `BT-YYYY-NNNN` 출장번호 채번 |
| `backend/app/services/history.py` | `record_transition` — ActivityLog + Notification 단일 기록 지점 |
| `backend/app/services/trips.py` | 출장 조회·목록·생성·수정·삭제·전이·타임라인. 스키마를 반환한다 |
| `backend/app/services/notifications.py` | 알림 목록·읽음 처리 |
| `backend/app/schemas/common.py` | `Page[T]` 페이징 봉투 |
| `backend/app/schemas/trip.py` | 출장 요청·응답 스키마 |
| `backend/app/schemas/code.py` | 공통코드 응답 스키마 |
| `backend/app/schemas/center.py` | 센터 응답 스키마 |
| `backend/app/schemas/notification.py` | 알림 응답 스키마 |
| `backend/app/routers/trips.py` | 출장 HTTP 계층 |
| `backend/app/routers/codes.py` | 공통코드 조회 |
| `backend/app/routers/centers.py` | Fund/Cost Center 조회 |
| `backend/app/routers/notifications.py` | 알림 |
| `backend/tests/factories.py` | 테스트 객체 생성기 |

**백엔드 — 수정**

- `backend/app/services/codes.py` — `validate_codes` 오케스트레이터, `load_code_groups`, `load_code_group` 추가
- `backend/app/main.py` — 라우터 등록
- `backend/tests/conftest.py` — `seeded`·`login_as` 픽스처 추가 (루프 스코프·`join_transaction_mode`·스키마 가드는 손대지 않는다)

**프론트엔드 — 신규**

| 파일 | 책임 |
|---|---|
| `frontend/src/lib/nav.ts` | `safeRedirect` — 로그인 후 복귀 경로 검증 |
| `frontend/src/lib/format.ts` | 날짜·금액 포맷터 |
| `frontend/src/lib/trip-status.ts` | 상태 라벨·톤 매핑 |
| `frontend/src/lib/api/trips.ts` · `codes.ts` · `centers.ts` · `notifications.ts` | API 호출부 |
| `frontend/src/lib/components/Select.svelte` · `Textarea.svelte` · `EmptyState.svelte` · `StatusBadge.svelte` · `TripCard.svelte` · `FilterBar.svelte` · `Timeline.svelte` · `TripForm.svelte` | UI |
| `frontend/src/routes/trips/+page.svelte` · `trips/new/+page.svelte` · `trips/[id]/+page.svelte` · `trips/[id]/edit/+page.svelte` · `approvals/+page.svelte` · `notifications/+page.svelte` | 화면 |

**프론트엔드 — 수정**

- `frontend/src/lib/api/client.ts` — `RequestOptions` export
- `frontend/src/lib/stores/auth.svelte.ts` — `authRequest`, `onUnauthorized`
- `frontend/src/lib/api/types.ts` — 출장·코드·알림 타입
- `frontend/src/routes/+layout.svelte` — 공개 경로 접두사, 딥링크 보존
- `frontend/src/routes/login/+page.svelte` — `redirect` 복귀
- `frontend/src/lib/components/AppShell.svelte` — 결재함·알림 진입점
- `frontend/src/routes/+page.svelte` — 대시보드 실데이터

---

## Task 1: 테스트 픽스처와 팩토리

**Files:**
- Create: `backend/tests/factories.py`
- Modify: `backend/tests/conftest.py`
- Test: `backend/tests/test_factories.py`

Phase 2는 통합 테스트가 많고, `Trip`·`User`는 NOT NULL 컬럼이 많아 테스트마다 손으로 채우면 금방 어긋난다. 먼저 만든다.

- [ ] **Step 1: 팩토리 작성**

`backend/tests/factories.py`:

```python
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
    겹치므로 `seeded` 세션에서 불러도 안전하도록 이미 있는 것은 건너뛴다.

    멱등하지 않으면 `seeded`에서 UniqueViolation이 나는데, 그 IntegrityError는
    savepoint 안에서 터져 세션을 오염시키므로 이후 모든 문장이 PendingRollbackError로
    바뀌고 원인이 묻힌다."""
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
```

- [ ] **Step 2: conftest 픽스처 추가**

`backend/tests/conftest.py`의 맨 끝(현재 `client` 픽스처 아래)에 추가한다. **기존 픽스처는 한 줄도 고치지 않는다** — 루프 스코프·`join_transaction_mode="create_savepoint"`·테스트 스키마 가드는 리뷰를 거쳐 고정된 값이다.

```python
@pytest.fixture
async def seeded(db_session) -> AsyncSession:
    """데모 시드를 적재한 세션. seed_all은 commit하지만 db_session의 외부 트랜잭션이
    통째로 롤백되므로 테스트 간 누수는 없다."""
    await seed_all(db_session)
    return db_session


@pytest.fixture
def login_as(client: httpx.AsyncClient) -> Callable[[str], Awaitable[dict[str, str]]]:
    """이메일로 로그인해 Authorization 헤더를 만든다. seeded와 함께 쓴다."""

    async def _login(email: str) -> dict[str, str]:
        response = await client.post(
            "/api/v1/auth/login", json={"email": email, "password": DEFAULT_PASSWORD}
        )
        assert response.status_code == 200, response.text
        return {"Authorization": f"Bearer {response.json()['access_token']}"}

    return _login
```

같은 파일 상단 import 블록에 다음을 더한다:

```python
from collections.abc import Awaitable, Callable

from app.seed import DEFAULT_PASSWORD, seed_all
```

(`AsyncGenerator`를 이미 `collections.abc`에서 가져오고 있으므로 그 줄에 합쳐도 된다.)

- [ ] **Step 3: 팩토리 테스트 작성**

`backend/tests/test_factories.py`:

```python
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


async def test_make_trip_master_data_is_safe_on_seeded_session(seeded):
    """seed_all이 이미 만든 코드그룹·코스트센터와 겹쳐도 UniqueViolation 없이 통과해야 한다."""
    await make_trip_master_data(seeded)


async def test_make_user_with_manager_inherits_manager_department(db_session):
    manager = await make_user(db_session)

    report = await make_user(db_session, manager=manager)

    assert report.department_id == manager.department_id
```

이 파일 상단 import는 다음과 같다:

```python
from datetime import date

from app.enums import TripStatus, UserRole
from tests.factories import make_trip, make_trip_master_data, make_user
```

- [ ] **Step 4: 테스트 실행**

Run: `cd backend && uv run pytest tests/test_factories.py -v`
Expected: 3 passed

- [ ] **Step 5: 커밋**

```bash
git add backend/tests/factories.py backend/tests/conftest.py backend/tests/test_factories.py
git commit -m "test: add object factories and seeded/login_as fixtures"
```

---

## Task 2: `validate_codes` 오케스트레이터

**Files:**
- Modify: `backend/app/services/codes.py`
- Test: `backend/tests/test_codes_service.py`

출장 쓰기 경로는 코드값 5개를 한 요청에서 검증한다. `load_active_codes` + `assert_valid_code` 쌍을 다섯 번 반복하면 그룹명과 `field=` 문자열을 잘못 짝지을 위험이 있다. 도입 근거는 성능이 아니라 **호출부 실수 방지**다.

**`asyncio.gather`를 쓰지 않는다.** Phase 1 이월 메모는 gather를 제안했지만 `AsyncSession`은 동시 사용이 금지돼 있다 — 같은 세션에 대해 `execute`를 병렬로 걸면 `InvalidRequestError`가 난다. 대신 그룹 수와 무관하게 **쿼리 2개**(그룹 일괄 조회 + 코드 일괄 조회)로 끝내는 방식을 쓴다. 이쪽이 gather보다 빠르고 안전하다.

- [ ] **Step 1: 실패하는 테스트 작성**

`backend/tests/test_codes_service.py` 끝에 추가:

```python
async def test_validate_codes_accepts_all_valid_values(db_session):
    await make_code_group(db_session, "TRANSPORT", ["AIR", "RAIL"])
    await make_code_group(db_session, "ACCOMMODATION", ["HOTEL"])

    await validate_codes(
        db_session,
        [
            ("TRANSPORT", "transport_code", "AIR"),
            ("ACCOMMODATION", "accommodation_code", "HOTEL"),
        ],
    )


async def test_validate_codes_reports_the_offending_field(db_session):
    await make_code_group(db_session, "TRANSPORT", ["AIR", "RAIL"])
    await make_code_group(db_session, "ACCOMMODATION", ["HOTEL"])

    with pytest.raises(ValidationError) as exc_info:
        await validate_codes(
            db_session,
            [
                ("TRANSPORT", "transport_code", "AIR"),
                ("ACCOMMODATION", "accommodation_code", "IGLOO"),
            ],
        )

    error = exc_info.value
    assert error.code == "INVALID_CODE"
    assert error.field == "accommodation_code"
    assert "ACCOMMODATION" in error.message


async def test_validate_codes_reports_the_first_failure_in_spec_order(db_session):
    await make_code_group(db_session, "TRANSPORT", ["AIR"])
    await make_code_group(db_session, "ACCOMMODATION", ["HOTEL"])

    with pytest.raises(ValidationError) as exc_info:
        await validate_codes(
            db_session,
            [
                ("TRANSPORT", "transport_code", "ROCKET"),
                ("ACCOMMODATION", "accommodation_code", "IGLOO"),
            ],
        )

    assert exc_info.value.field == "transport_code"


async def test_validate_codes_raises_for_unknown_group(db_session):
    await make_code_group(db_session, "TRANSPORT", ["AIR"])

    with pytest.raises(ValidationError) as exc_info:
        await validate_codes(
            db_session,
            [("TRANSPORT", "transport_code", "AIR"), ("NOPE", "nope_code", "X")],
        )

    error = exc_info.value
    assert error.code == "UNKNOWN_CODE_GROUP"
    # 그룹 부재도 어느 입력 필드 탓인지 가리켜야 한다. field가 없으면 코드 필드
    # 다섯 개 중 어디를 고쳐야 하는지 알 수 없는 400이 된다.
    assert error.field == "nope_code"


async def test_validate_codes_rejects_inactive_group(db_session):
    await make_code_group(db_session, "RETIRED", ["AIR"], is_active=False)

    with pytest.raises(ValidationError) as exc_info:
        await validate_codes(db_session, [("RETIRED", "transport_code", "AIR")])

    error = exc_info.value
    assert error.code == "UNKNOWN_CODE_GROUP"
    assert error.field == "transport_code"


async def test_validate_codes_rejects_inactive_code_value(db_session):
    group = await make_code_group(db_session, "TRANSPORT", ["AIR"])
    db_session.add(Code(group_id=group.id, code="SHIP", name="선박", sort_order=2, is_active=False))
    await db_session.flush()

    with pytest.raises(ValidationError) as exc_info:
        await validate_codes(db_session, [("TRANSPORT", "transport_code", "SHIP")])

    assert exc_info.value.code == "INVALID_CODE"


async def test_validate_codes_reports_missing_group_before_bad_value(db_session):
    """설정 오류(그룹 부재)를 사용자 오타(값 오류)보다 먼저 보고한다."""
    await make_code_group(db_session, "TRANSPORT", ["AIR"])

    with pytest.raises(ValidationError) as exc_info:
        await validate_codes(
            db_session,
            [("TRANSPORT", "transport_code", "ROCKET"), ("NOPE", "nope_code", "X")],
        )

    assert exc_info.value.code == "UNKNOWN_CODE_GROUP"


async def test_validate_codes_treats_group_with_no_active_codes_as_invalid_value(db_session):
    await make_code_group(db_session, "EMPTY_GROUP", [])

    with pytest.raises(ValidationError) as exc_info:
        await validate_codes(db_session, [("EMPTY_GROUP", "some_code", "X")])

    assert exc_info.value.code == "INVALID_CODE"


async def test_validate_codes_issues_two_queries_regardless_of_group_count(db_session):
    await make_code_group(db_session, "TRANSPORT", ["AIR"])
    await make_code_group(db_session, "ACCOMMODATION", ["HOTEL"])
    await make_code_group(db_session, "COUNTRY", ["KR"])

    counter = {"n": 0}

    @event.listens_for(db_session.sync_session, "do_orm_execute")
    def _count(_context) -> None:
        counter["n"] += 1

    await validate_codes(
        db_session,
        [
            ("TRANSPORT", "transport_code", "AIR"),
            ("ACCOMMODATION", "accommodation_code", "HOTEL"),
            ("COUNTRY", "country_code", "KR"),
        ],
    )

    assert counter["n"] == 2
```

같은 파일 상단 import를 다음으로 교체한다:

```python
import pytest
from sqlalchemy import event

from app.errors import ValidationError
from app.models import Code, CodeGroup
from app.services.codes import assert_valid_code, load_active_codes, validate_codes
from tests.factories import make_code_group
```

- [ ] **Step 2: 실패 확인**

Run: `cd backend && uv run pytest tests/test_codes_service.py -v`
Expected: FAIL — `ImportError: cannot import name 'validate_codes'`

- [ ] **Step 3: 구현**

`backend/app/services/codes.py` 상단 import를 다음으로 교체:

```python
from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.errors import ValidationError
from app.models import Code, CodeGroup

#: (group_code, 응답 field 이름, 검증할 값)
CodeSpec = tuple[str, str, str | None]
```

파일 끝에 추가:

```python
async def validate_codes(session: AsyncSession, specs: Sequence[CodeSpec]) -> None:
    """여러 코드값을 한 번에 검증한다.

    호출부가 `load_active_codes` + `assert_valid_code`를 필드 수만큼 반복하면 그룹명과
    field 문자열을 잘못 짝짓기 쉽다. 그 실수를 구조적으로 막는 것이 이 함수의 목적이다.

    `asyncio.gather`로 병렬화하지 않는다 — AsyncSession은 동시 사용이 금지돼 있어
    같은 세션에 execute를 병렬로 걸면 InvalidRequestError가 난다. 대신 그룹 수와
    무관하게 쿼리 2개로 끝낸다.

    보고 순서는 두 단계다. 코드그룹 부재(설정 오류)를 값 오류(사용자 오타)보다 먼저
    보고하고, 각 단계 안에서는 specs 순서를 따른다. 어떤 필드가 먼저 걸리는지가
    결정적이어야 호출부와 테스트가 흔들리지 않는다.
    """
    if not specs:
        return

    wanted = {group_code for group_code, _, _ in specs}
    group_rows = await session.execute(
        select(CodeGroup.id, CodeGroup.group_code).where(
            CodeGroup.group_code.in_(wanted), CodeGroup.is_active.is_(True)
        )
    )
    group_id_by_code = {group_code: group_id for group_id, group_code in group_rows}

    # field를 실어 보낸다. load_active_codes는 필드를 모르지만 여기는 알고 있고,
    # 그게 없으면 "그룹이 비활성" 오류가 코드 필드 다섯 개 중 어디를 가리키는지
    # 알 수 없는 400이 된다.
    for group_code, field, _ in specs:
        if group_code not in group_id_by_code:
            raise ValidationError(
                "UNKNOWN_CODE_GROUP",
                f"존재하지 않는 코드그룹입니다: {group_code}",
                field=field,
            )

    code_rows = await session.execute(
        select(Code.group_id, Code.code).where(
            Code.group_id.in_(group_id_by_code.values()), Code.is_active.is_(True)
        )
    )
    allowed: dict[int, set[str]] = {}
    for group_id, code in code_rows:
        allowed.setdefault(group_id, set()).add(code)

    for group_code, field, value in specs:
        assert_valid_code(
            group_code,
            value,
            allowed.get(group_id_by_code[group_code], set()),
            field=field,
        )
```

- [ ] **Step 4: 통과 확인**

Run: `cd backend && uv run pytest tests/test_codes_service.py -v`
Expected: 15 passed

**두 `is_active` 필터가 진짜 걸리는지 확인할 것.** `CodeGroup.is_active.is_(True)`와 `Code.is_active.is_(True)`를 각각 지웠을 때 새 테스트가 실패해야 한다. 실패하지 않으면 그 테스트는 아무것도 지키지 않는 것이다 — 이 함수의 존재 이유가 "비활성화된 코드값이 저장되는 것을 막는 것"이므로 이 확인을 건너뛰지 말 것.

- [ ] **Step 5: 커밋**

```bash
git add backend/app/services/codes.py backend/tests/test_codes_service.py
git commit -m "feat: add validate_codes orchestrator for multi-field code validation"
```

---

## Task 3: 센터 검증 서비스

**Files:**
- Create: `backend/app/services/centers.py`
- Test: `backend/tests/test_centers_service.py`

`cost_center_code`는 공통코드가 아니라 전용 마스터(`cost_center`)를 참조한다. 코드값 검증과 같은 자리에서 같은 모양의 에러를 내야 호출부가 헷갈리지 않는다.

- [ ] **Step 1: 실패하는 테스트 작성**

`backend/tests/test_centers_service.py`:

```python
import pytest

from app.errors import ValidationError
from app.models import CostCenter, FundCenter
from app.services.centers import assert_cost_center, load_active_center_codes
from tests.factories import make_cost_center, make_fund_center


async def test_load_active_center_codes_returns_only_active(db_session):
    await make_cost_center(db_session, "CC9001")
    await make_cost_center(db_session, "CC9002", is_active=False)

    codes = await load_active_center_codes(db_session, CostCenter)

    assert codes == {"CC9001"}


async def test_load_active_center_codes_is_per_model(db_session):
    await make_cost_center(db_session, "CC9001")
    await make_fund_center(db_session, "FC9001")

    assert await load_active_center_codes(db_session, FundCenter) == {"FC9001"}


async def test_assert_cost_center_accepts_active_code(db_session):
    await make_cost_center(db_session, "CC9001")

    await assert_cost_center(db_session, "CC9001")


async def test_assert_cost_center_rejects_inactive_code(db_session):
    await make_cost_center(db_session, "CC9002", is_active=False)

    with pytest.raises(ValidationError) as exc_info:
        await assert_cost_center(db_session, "CC9002")

    error = exc_info.value
    assert error.status_code == 400
    assert error.code == "INVALID_COST_CENTER"
    assert error.field == "cost_center_code"


async def test_assert_cost_center_rejects_unknown_code(db_session):
    """Agent가 없는 코드를 지어내는 경우 — 실제로 가장 흔한 실패다."""
    await make_cost_center(db_session, "CC9001")

    with pytest.raises(ValidationError) as exc_info:
        await assert_cost_center(db_session, "CC9999")

    assert exc_info.value.code == "INVALID_COST_CENTER"


async def test_assert_cost_center_rejects_none(db_session):
    with pytest.raises(ValidationError) as exc_info:
        await assert_cost_center(db_session, None)

    assert exc_info.value.code == "INVALID_COST_CENTER"


async def test_assert_cost_center_reports_a_custom_field(db_session):
    with pytest.raises(ValidationError) as exc_info:
        await assert_cost_center(db_session, "CC9999", field="items.0.cost_center_code")

    assert exc_info.value.field == "items.0.cost_center_code"
```

- [ ] **Step 2: 실패 확인**

Run: `cd backend && uv run pytest tests/test_centers_service.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.services.centers'`

- [ ] **Step 3: 구현**

`backend/app/services/centers.py`:

```python
"""Fund Center / Cost Center 마스터 조회와 검증.

공통코드가 아니라 전용 테이블이라 `services/codes.py`와 분리하되, 실패 시 에러 모양은
같게 맞춘다 (400 / field 지정). 호출부가 두 종류의 마스터를 구분해서 다룰 이유가 없다.
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.errors import ValidationError
from app.models import CostCenter, FundCenter

CenterModel = type[FundCenter] | type[CostCenter]


async def load_active_center_codes(session: AsyncSession, model: CenterModel) -> set[str]:
    """활성 센터 코드 집합.

    model을 인자로 받는 이유는 Phase 3의 fund center 쓰기 경로가 같은 쿼리를 그대로
    쓰기 때문이다. Phase 2에서 실제로 넘어오는 값은 CostCenter 하나뿐이다.
    """
    rows = await session.execute(select(model.code).where(model.is_active.is_(True)))
    return set(rows.scalars().all())


async def assert_cost_center(
    session: AsyncSession, code: str | None, *, field: str = "cost_center_code"
) -> None:
    """값 하나를 검사하는데 집합 전체를 읽는 이유는 **테이블이 작아서**다 (시드 기준
    코스트센터 10건·펀드센터 6건). `validate_codes`와의 일관성 때문이 아니다 — 그쪽은
    한 쿼리를 다섯 필드에 분산시키는 이득이 있지만 여기엔 없다. `CostCenter.code`는
    unique·index라 값 하나면 존재 확인 쿼리가 자연스럽다. 큰 마스터 테이블에
    이 모양을 복사하지 말 것.
    """
    allowed = await load_active_center_codes(session, CostCenter)
    if code not in allowed:
        # "존재하지 않는"이라고 쓰지 않는다 — 비활성 코드는 존재하기 때문이다.
        raise ValidationError(
            "INVALID_COST_CENTER", f"사용할 수 없는 코스트센터입니다: {code}", field=field
        )
```

- [ ] **Step 4: 통과 확인**

Run: `cd backend && uv run pytest tests/test_centers_service.py -v`
Expected: 7 passed

- [ ] **Step 5: 커밋**

```bash
git add backend/app/services/centers.py backend/tests/test_centers_service.py
git commit -m "feat: add cost center validation service"
```

---

## Task 4: 출장 도메인 순수 규칙

**Files:**
- Create: `backend/app/services/trip_rules.py`
- Test: `backend/tests/test_trip_rules.py`

`trip_status.py`는 전이의 **적법성**만 판단한다. 여기 있는 것들은 전이의 **조건과 권한**, 그리고 모델에 `CheckConstraint`를 걸지 않아 비어 있는 교차필드 제약이다. 모델이 막아줄 거라고 가정하지 말 것 — 막아주지 않는다.

- [ ] **Step 1: 실패하는 테스트 작성**

`backend/tests/test_trip_rules.py`:

```python
from datetime import date
from decimal import Decimal

import pytest

from app.enums import TripStatus, UserRole
from app.errors import ConflictError, ForbiddenError, ValidationError
from app.services.trip_rules import (
    assert_completable,
    assert_date_range,
    assert_deletable,
    assert_editable,
    assert_estimated_cost,
    assert_has_approver,
    assert_trip_owner,
    assert_reject_reason,
    assert_trip_approver,
    can_view_trip,
)


def test_date_range_accepts_same_day():
    assert_date_range(start_date=date(2026, 9, 1), end_date=date(2026, 9, 1))


def test_date_range_rejects_end_before_start():
    with pytest.raises(ValidationError) as exc_info:
        assert_date_range(start_date=date(2026, 9, 3), end_date=date(2026, 9, 1))

    error = exc_info.value
    assert error.status_code == 400
    assert error.code == "INVALID_DATE_RANGE"
    assert error.field == "end_date"


def test_estimated_cost_accepts_zero():
    assert_estimated_cost(Decimal("0"))


def test_estimated_cost_rejects_negative():
    with pytest.raises(ValidationError) as exc_info:
        assert_estimated_cost(Decimal("-1"))

    assert exc_info.value.code == "INVALID_AMOUNT"
    assert exc_info.value.field == "estimated_cost"


@pytest.mark.parametrize("role", [UserRole.EMPLOYEE, UserRole.MANAGER])
def test_owner_and_approver_can_view(role):
    assert can_view_trip(user_id=1, role=role, owner_id=1, approver_id=9) is True
    assert can_view_trip(user_id=9, role=role, owner_id=1, approver_id=9) is True
    assert can_view_trip(user_id=5, role=role, owner_id=1, approver_id=9) is False


def test_admin_can_view_anything():
    assert can_view_trip(user_id=5, role=UserRole.ADMIN, owner_id=1, approver_id=9) is True


def test_can_view_handles_missing_approver():
    assert can_view_trip(user_id=1, role=UserRole.EMPLOYEE, owner_id=1, approver_id=None) is True
    assert can_view_trip(user_id=2, role=UserRole.EMPLOYEE, owner_id=1, approver_id=None) is False


def test_assert_owner_rejects_other_user():
    with pytest.raises(ForbiddenError) as exc_info:
        assert_trip_owner(user_id=2, owner_id=1)

    assert exc_info.value.status_code == 403
    assert exc_info.value.code == "NOT_TRIP_OWNER"


def test_assert_trip_approver_rejects_other_user():
    with pytest.raises(ForbiddenError) as exc_info:
        assert_trip_approver(user_id=2, approver_id=9)

    assert exc_info.value.code == "NOT_TRIP_APPROVER"


def test_assert_trip_approver_rejects_unassigned_trip():
    with pytest.raises(ForbiddenError):
        assert_trip_approver(user_id=2, approver_id=None)


@pytest.mark.parametrize("status", [TripStatus.DRAFT, TripStatus.REJECTED])
def test_editable_statuses(status):
    assert_editable(status)


@pytest.mark.parametrize(
    "status",
    [TripStatus.SUBMITTED, TripStatus.APPROVED, TripStatus.COMPLETED, TripStatus.SETTLED],
)
def test_non_editable_statuses(status):
    with pytest.raises(ConflictError) as exc_info:
        assert_editable(status)

    assert exc_info.value.status_code == 409
    assert exc_info.value.code == "TRIP_NOT_EDITABLE"


def test_only_draft_is_deletable():
    assert_deletable(TripStatus.DRAFT)
    with pytest.raises(ConflictError) as exc_info:
        assert_deletable(TripStatus.REJECTED)

    assert exc_info.value.code == "TRIP_NOT_DELETABLE"


def test_completable_requires_end_date_in_the_past():
    assert_completable(date(2026, 8, 16), today=date(2026, 8, 17))


@pytest.mark.parametrize("end_date", [date(2026, 8, 17), date(2026, 8, 18)])
def test_not_completable_before_end_date_passes(end_date):
    with pytest.raises(ConflictError) as exc_info:
        assert_completable(end_date, today=date(2026, 8, 17))

    assert exc_info.value.code == "TRIP_NOT_ENDED"


def test_reject_reason_is_trimmed_and_returned():
    assert assert_reject_reason("  예산 초과  ") == "예산 초과"


@pytest.mark.parametrize("reason", [None, "", "   "])
def test_reject_reason_is_required(reason):
    with pytest.raises(ValidationError) as exc_info:
        assert_reject_reason(reason)

    assert exc_info.value.code == "REJECT_REASON_REQUIRED"
    assert exc_info.value.field == "reason"


def test_assert_has_approver_returns_manager_id():
    assert assert_has_approver(7) == 7


def test_assert_has_approver_rejects_none():
    with pytest.raises(ConflictError) as exc_info:
        assert_has_approver(None)

    assert exc_info.value.status_code == 409
    assert exc_info.value.code == "NO_APPROVER"
```

- [ ] **Step 2: 실패 확인**

Run: `cd backend && uv run pytest tests/test_trip_rules.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.services.trip_rules'`

- [ ] **Step 3: 구현**

`backend/app/services/trip_rules.py`:

```python
"""출장 도메인의 순수 규칙. DB 접근이 없어 단위테스트로 전부 덮는다.

`trip_status.py`가 전이의 적법성만 판단하는 것과 짝을 이룬다. 여기서는 전이의 조건과
권한, 그리고 모델에 CheckConstraint를 걸지 않아 비어 있는 교차필드 제약을 담당한다.
모델이 막아줄 거라고 가정하지 말 것 — 막아주지 않는다.
"""

from datetime import date
from decimal import Decimal

from app.enums import TripStatus, UserRole
from app.errors import ConflictError, ForbiddenError, ValidationError

#: 신청자가 내용을 고칠 수 있는 상태. 반려된 출장은 고쳐서 되살리는 것이 정상 경로다 —
#: 다만 수정만으로는 REJECTED에 머무르고, reopen으로 DRAFT를 거쳐야 다시 상신할 수 있다.
EDITABLE_STATUSES = frozenset({TripStatus.DRAFT, TripStatus.REJECTED})

#: 삭제는 임시저장만. EDITABLE_STATUSES와 같은 모양으로 둔다 — 한쪽만 `is` 비교를 쓰면
#: StrEnum이 값으로 해시되기 때문에 raw 문자열에서 두 함수의 판정이 갈린다.
DELETABLE_STATUSES = frozenset({TripStatus.DRAFT})

#: Trip.estimated_cost는 Numeric(14, 2) — 정수부 12자리가 최대다. 넘으면 flush에서
#: Postgres numeric overflow가 나고 통일 핸들러의 catch-all에 걸려 500이 된다.
#: Agent는 5xx를 재시도하므로 절대 성공할 수 없는 요청에 재시도 루프가 걸린다.
MAX_ESTIMATED_COST = Decimal("999999999999.99")


def assert_date_range(*, start_date: date, end_date: date) -> None:
    # 키워드 전용이다. date 두 개를 위치로 받으면 인자를 바꿔 넘겼을 때 규칙이
    # 조용히 뒤집힌다.
    if end_date < start_date:
        raise ValidationError(
            "INVALID_DATE_RANGE", "종료일은 시작일보다 빠를 수 없습니다", field="end_date"
        )


def assert_estimated_cost(estimated_cost: Decimal) -> None:
    if estimated_cost < 0:
        raise ValidationError(
            "INVALID_AMOUNT", "예상 비용은 0 이상이어야 합니다", field="estimated_cost"
        )
    if estimated_cost > MAX_ESTIMATED_COST:
        raise ValidationError(
            "INVALID_AMOUNT",
            f"예상 비용은 {MAX_ESTIMATED_COST} 이하여야 합니다",
            field="estimated_cost",
        )


def can_view_trip(*, user_id: int, role: UserRole, owner_id: int, approver_id: int | None) -> bool:
    """신청자·결재자·ADMIN만 출장을 볼 수 있다.

    이 판정이 False면 호출부는 403이 아니라 **404**를 낸다. 타인 리소스의 존재 자체를
    알려주지 않는 것이 이 프로젝트의 규칙이다.
    """
    if role == UserRole.ADMIN:
        return True
    return user_id == owner_id or (approver_id is not None and user_id == approver_id)


def assert_trip_owner(*, user_id: int, owner_id: int) -> None:
    if user_id != owner_id:
        raise ForbiddenError("NOT_TRIP_OWNER", "본인이 신청한 출장만 처리할 수 있습니다")


def assert_trip_approver(*, user_id: int, approver_id: int | None) -> None:
    if approver_id is None or user_id != approver_id:
        raise ForbiddenError("NOT_TRIP_APPROVER", "이 출장의 결재자가 아닙니다")


def assert_editable(status: TripStatus) -> None:
    if status not in EDITABLE_STATUSES:
        raise ConflictError("TRIP_NOT_EDITABLE", f"{status} 상태의 출장은 수정할 수 없습니다")


def assert_deletable(status: TripStatus) -> None:
    if status not in DELETABLE_STATUSES:
        raise ConflictError("TRIP_NOT_DELETABLE", "임시저장 상태의 출장만 삭제할 수 있습니다")


def assert_completable(end_date: date, *, today: date) -> None:
    """spec 5.4: APPROVED → COMPLETED는 end_date가 오늘 이전일 것.

    today를 인자로 받는 이유는 테스트를 결정적으로 만들기 위해서다. 호출부가
    date.today()를 넘긴다.
    """
    if end_date >= today:
        raise ConflictError("TRIP_NOT_ENDED", "종료일이 지난 출장만 완료 처리할 수 있습니다")


def assert_reject_reason(reason: str | None) -> str:
    text = (reason or "").strip()
    if not text:
        raise ValidationError("REJECT_REASON_REQUIRED", "반려 사유를 입력해야 합니다", field="reason")
    return text


def assert_has_approver(manager_id: int | None) -> int:
    """결재자는 신청자의 manager_id로 자동 결정된다 (spec 5.1). 없으면 상신할 수 없다."""
    if manager_id is None:
        raise ConflictError("NO_APPROVER", "결재자가 지정되지 않아 상신할 수 없습니다")
    return manager_id


class TransitionActor(StrEnum):
    OWNER = "OWNER"
    APPROVER = "APPROVER"
    SYSTEM = "SYSTEM"


#: 각 전이를 수행할 수 있는 주체. ALLOWED_TRANSITIONS와 키가 정확히 일치해야 한다.
TRANSITION_ACTOR: dict[tuple[TripStatus, TripStatus], TransitionActor] = {
    (TripStatus.DRAFT, TripStatus.SUBMITTED): TransitionActor.OWNER,
    (TripStatus.SUBMITTED, TripStatus.APPROVED): TransitionActor.APPROVER,
    (TripStatus.SUBMITTED, TripStatus.REJECTED): TransitionActor.APPROVER,
    (TripStatus.REJECTED, TripStatus.DRAFT): TransitionActor.OWNER,
    (TripStatus.APPROVED, TripStatus.COMPLETED): TransitionActor.OWNER,
    (TripStatus.COMPLETED, TripStatus.SETTLED): TransitionActor.SYSTEM,
}

# trip_status.py의 _missing 가드와 같은 이유로 import 시점에 확인한다. 새 전이를 추가하고
# 주체를 빠뜨리면 조용히 "아무나 가능"이 되는 것이 아니라 여기서 죽어야 한다.
_legal_transitions = {
    (current, target)
    for current, targets in ALLOWED_TRANSITIONS.items()
    for target in targets
}
if _legal_transitions != set(TRANSITION_ACTOR):
    raise RuntimeError(
        "TRANSITION_ACTOR와 ALLOWED_TRANSITIONS의 전이 목록이 다릅니다: "
        f"{_legal_transitions ^ set(TRANSITION_ACTOR)}"
    )


def assert_transition_allowed(
    current: TripStatus,
    target: TripStatus,
    *,
    user_id: int,
    owner_id: int,
    approver_id: int | None,
) -> None:
    """전이의 적법성과 수행 주체를 한 번에 검사한다.

    호출부가 두 검사를 따로 부르면 언젠가 한쪽을 빠뜨리고, 그 실패는 조용하다 —
    load_visible_trip을 이미 통과한 결재자가 신청자만 할 수 있는 전이를 수행하게 된다.
    권한 검사가 fail-open이 되지 않도록 두 판단을 한 함수에 묶는다.

    적법성을 먼저 본다. 결재자가 DRAFT 출장에 approve를 걸면 "권한 없음"보다
    TRIP_INVALID_TRANSITION(409)이 더 쓸모 있는 답이고, 어차피 그 결재자는 상태를
    이미 볼 수 있으므로 상태를 알려주는 것이 정보 노출도 아니다.
    """
    assert_trip_transition(current, target)

    actor = TRANSITION_ACTOR[(current, target)]
    if actor is TransitionActor.OWNER:
        assert_trip_owner(user_id=user_id, owner_id=owner_id)
    elif actor is TransitionActor.APPROVER:
        assert_trip_approver(user_id=user_id, approver_id=approver_id)
    else:
        # COMPLETED → SETTLED는 정산서 승인이 트리거하는 시스템 전이다 (spec 5.4).
        # 사용자가 직접 부를 수 있는 경로를 열어두지 않는다.
        raise ForbiddenError(
            "SYSTEM_TRANSITION_ONLY", "시스템만 수행할 수 있는 전이입니다"
        )
```

이 모듈의 import 블록에 두 줄을 더한다:

```python
from enum import StrEnum

from app.services.trip_status import ALLOWED_TRANSITIONS, assert_trip_transition
```

`trip_status.py`는 손대지 않는다 — 적법성만 묻는 호출부를 위해 그대로 남긴다.

전이 검사 테스트는 다음을 덮는다.

- `TRANSITION_ACTOR` 항목을 지우면 **import 시점에** `RuntimeError`가 난다 (임시로 지워 확인 후 복원)
- 여섯 전이 각각이 올바른 주체는 통과시키고 반대 주체는 거부한다 (신청자가 approve → `NOT_TRIP_APPROVER`, 결재자가 complete → `NOT_TRIP_OWNER`)
- `COMPLETED → SETTLED`는 신청자·결재자 모두 `SYSTEM_TRANSITION_ONLY`로 막는다
- 불법 전이는 호출자가 다른 전이의 올바른 주체라도 `TRIP_INVALID_TRANSITION`(409)이다

- [ ] **Step 4: 통과 확인**

Run: `cd backend && uv run pytest tests/test_trip_rules.py -v`
Expected: 27 passed

- [ ] **Step 5: 커밋**

```bash
git add backend/app/services/trip_rules.py backend/tests/test_trip_rules.py
git commit -m "feat: add pure trip domain rules"
```

---

## Task 5: 출장번호 채번

**Files:**
- Create: `backend/app/services/numbering.py`
- Test: `backend/tests/test_numbering.py`

- [ ] **Step 1: 실패하는 테스트 작성**

`backend/tests/test_numbering.py`:

```python
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
```

- [ ] **Step 2: 실패 확인**

Run: `cd backend && uv run pytest tests/test_numbering.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.services.numbering'`

- [ ] **Step 3: 구현**

`backend/app/services/numbering.py`:

```python
"""업무 문서번호 채번.

`max() + 1` 방식이라 동시에 두 요청이 들어오면 같은 번호를 계산할 수 있다. 이 데모는
단일 백엔드 인스턴스로 배포하고, 마지막 방어선으로 `trip.trip_no`에 unique 제약이
걸려 있어 중복 저장은 일어나지 않는다 (그 경우 500이 난다). 멀티 레플리카로 가면
Postgres 시퀀스나 advisory lock이 필요하다.
"""

from datetime import date

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Trip


async def next_trip_no(session: AsyncSession, today: date) -> str:
    """`BT-YYYY-NNNN`. 연도별로 0001부터 다시 센다.

    today를 인자로 받는 이유는 테스트를 결정적으로 만들기 위해서다.
    """
    prefix = f"BT-{today.year}-"
    last = (
        await session.execute(
            select(func.max(Trip.trip_no)).where(Trip.trip_no.like(f"{prefix}%"))
        )
    ).scalar_one_or_none()
    sequence = int(last[len(prefix) :]) + 1 if last else 1
    return f"{prefix}{sequence:04d}"
```

- [ ] **Step 4: 통과 확인**

Run: `cd backend && uv run pytest tests/test_numbering.py -v`
Expected: 4 passed

- [ ] **Step 5: 커밋**

```bash
git add backend/app/services/numbering.py backend/tests/test_numbering.py
git commit -m "feat: add trip number sequencing"
```

---

## Task 6: 이력·알림 단일 기록 지점

**Files:**
- Create: `backend/app/services/history.py`
- Test: `backend/tests/test_history_service.py`

spec 5.8: 모든 상태 전이는 서비스 레이어의 단일 지점을 통과하며, 그 지점에서 `activity_log`와 `notification`을 함께 기록한다. 웹 경로로 들어오든 API Key 경로로 들어오든 이력이 누락될 수 없어야 한다.

- [ ] **Step 1: 실패하는 테스트 작성**

`backend/tests/test_history_service.py`:

```python
from sqlalchemy import select

from app.enums import ActivityAction, EntityType, NotificationType, TripStatus
from app.models import ActivityLog, Notification
from app.services.history import NotifySpec, record_transition
from tests.factories import make_trip, make_user


async def test_records_activity_log(db_session):
    user = await make_user(db_session)
    trip = await make_trip(db_session, user=user)

    await record_transition(
        db_session,
        entity_type=EntityType.TRIP,
        entity_id=trip.id,
        actor_id=user.id,
        action=ActivityAction.CREATED,
        to_status=TripStatus.DRAFT.value,
        memo="출장 신청서 작성",
    )

    log = (await db_session.execute(select(ActivityLog))).scalar_one()
    assert log.entity_type is EntityType.TRIP
    assert log.entity_id == trip.id
    assert log.actor_id == user.id
    assert log.action is ActivityAction.CREATED
    assert log.from_status is None
    assert log.to_status == "DRAFT"
    assert log.memo == "출장 신청서 작성"


async def test_records_notification_for_another_user(db_session):
    manager = await make_user(db_session, name="김연구")
    employee = await make_user(db_session, manager=manager)
    trip = await make_trip(db_session, user=employee)

    await record_transition(
        db_session,
        entity_type=EntityType.TRIP,
        entity_id=trip.id,
        actor_id=employee.id,
        action=ActivityAction.SUBMITTED,
        from_status="DRAFT",
        to_status="SUBMITTED",
        notify=NotifySpec(
            user_id=manager.id,
            type=NotificationType.TRIP_SUBMITTED,
            title="출장 결재 요청",
            body="박출장님이 출장을 상신했습니다.",
            link_url=f"/trips/{trip.id}",
        ),
    )

    notification = (await db_session.execute(select(Notification))).scalar_one()
    assert notification.user_id == manager.id
    assert notification.type is NotificationType.TRIP_SUBMITTED
    assert notification.is_read is False
    assert notification.link_url == f"/trips/{trip.id}"


async def test_does_not_notify_the_actor_themselves(db_session):
    user = await make_user(db_session)
    trip = await make_trip(db_session, user=user)

    await record_transition(
        db_session,
        entity_type=EntityType.TRIP,
        entity_id=trip.id,
        actor_id=user.id,
        action=ActivityAction.APPROVED,
        notify=NotifySpec(
            user_id=user.id,
            type=NotificationType.TRIP_APPROVED,
            title="승인됨",
            body="본인이 본인 것을 승인",
        ),
    )

    assert (await db_session.execute(select(Notification))).scalars().all() == []
    assert len((await db_session.execute(select(ActivityLog))).scalars().all()) == 1


async def test_activity_log_is_written_without_notification(db_session):
    user = await make_user(db_session)
    trip = await make_trip(db_session, user=user)

    await record_transition(
        db_session,
        entity_type=EntityType.TRIP,
        entity_id=trip.id,
        actor_id=user.id,
        action=ActivityAction.COMPLETED,
        from_status="APPROVED",
        to_status="COMPLETED",
    )

    assert (await db_session.execute(select(Notification))).scalars().all() == []
    assert (await db_session.execute(select(ActivityLog))).scalar_one().to_status == "COMPLETED"
```

- [ ] **Step 2: 실패 확인**

Run: `cd backend && uv run pytest tests/test_history_service.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.services.history'`

- [ ] **Step 3: 구현**

`backend/app/services/history.py`:

```python
"""상태 전이 이력과 알림을 함께 남기는 단일 지점 (spec 5.8).

전이를 수행하는 서비스 함수는 반드시 이 함수를 호출한다. 두 테이블에 따로 쓰게 두면
언젠가 한쪽을 빠뜨리고, 그러면 "웹으로 하면 알림이 오는데 API로 하면 안 온다" 같은
경로별 불일치가 생긴다.
"""

from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from app.enums import ActivityAction, EntityType, NotificationType
from app.models import ActivityLog, Notification


@dataclass(frozen=True)
class NotifySpec:
    user_id: int
    type: NotificationType
    title: str
    body: str
    link_url: str | None = None


async def record_transition(
    session: AsyncSession,
    *,
    entity_type: EntityType,
    entity_id: int,
    actor_id: int,
    action: ActivityAction,
    from_status: str | None = None,
    to_status: str | None = None,
    memo: str | None = None,
    notify: NotifySpec | None = None,
) -> None:
    session.add(
        ActivityLog(
            entity_type=entity_type,
            entity_id=entity_id,
            actor_id=actor_id,
            action=action,
            from_status=from_status,
            to_status=to_status,
            memo=memo,
        )
    )
    # 자기가 한 일을 자기에게 알리지 않는다. ADMIN이 자기 출장을 스스로 결재하는
    # 데모 시나리오에서 실제로 발생한다.
    if notify is not None and notify.user_id != actor_id:
        session.add(
            Notification(
                user_id=notify.user_id,
                type=notify.type,
                title=notify.title,
                body=notify.body,
                link_url=notify.link_url,
            )
        )
    await session.flush()
```

- [ ] **Step 4: 통과 확인**

Run: `cd backend && uv run pytest tests/test_history_service.py -v`
Expected: 4 passed

- [ ] **Step 5: 커밋**

```bash
git add backend/app/services/history.py backend/tests/test_history_service.py
git commit -m "feat: add single-point activity log and notification recorder"
```

---

## Task 7: 응답 스키마

**Files:**
- Create: `backend/app/schemas/common.py`
- Create: `backend/app/schemas/trip.py`
- Test: `backend/tests/test_schemas_trip.py`

- [ ] **Step 1: 실패하는 테스트 작성**

`backend/tests/test_schemas_trip.py`:

```python
from datetime import date
from decimal import Decimal

import pytest
from pydantic import ValidationError as PydanticValidationError

from app.enums import TripStatus
from app.schemas.common import Page
from app.schemas.trip import TripCreate, TripListItem, TripUpdate


def _create_payload(**overrides) -> dict:
    payload = {
        "title": "울산공장 품질점검",
        "purpose_code": "AUDIT",
        "purpose_detail": "라인 3 품질 이슈 현장 확인",
        "destination_type_code": "DOMESTIC",
        "country_code": "KR",
        "city": "울산",
        "start_date": "2026-09-01",
        "end_date": "2026-09-03",
        "transport_code": "RAIL",
        "accommodation_code": "HOTEL",
        "cost_center_code": "CC2030",
        "estimated_cost": "450000",
    }
    payload.update(overrides)
    return payload


def test_trip_create_parses_dates_and_decimal():
    payload = TripCreate.model_validate(_create_payload())

    assert payload.start_date == date(2026, 9, 1)
    assert payload.estimated_cost == Decimal("450000")


def test_trip_create_rejects_blank_title():
    with pytest.raises(PydanticValidationError):
        TripCreate.model_validate(_create_payload(title=""))


def test_trip_update_tracks_which_fields_were_sent():
    payload = TripUpdate.model_validate({"city": "서산"})

    assert payload.model_dump(exclude_unset=True) == {"city": "서산"}


def test_trip_update_allows_empty_body():
    assert TripUpdate.model_validate({}).model_dump(exclude_unset=True) == {}


def test_page_is_generic_over_the_item_type():
    page = Page[TripListItem](
        items=[
            TripListItem(
                id=1,
                trip_no="BT-2026-0001",
                title="울산공장 품질점검",
                city="울산",
                country_code="KR",
                destination_type_code="DOMESTIC",
                purpose_code="AUDIT",
                start_date=date(2026, 9, 1),
                end_date=date(2026, 9, 3),
                status=TripStatus.DRAFT,
                estimated_cost=Decimal("450000"),
                user_id=1,
                user_name="박출장",
                approver_id=None,
                approver_name=None,
            )
        ],
        total=1,
        page=1,
        size=20,
    )

    assert page.items[0].trip_no == "BT-2026-0001"
    assert page.model_dump()["total"] == 1
```

- [ ] **Step 2: 실패 확인**

Run: `cd backend && uv run pytest tests/test_schemas_trip.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.schemas.common'`

- [ ] **Step 3: 구현**

`backend/app/schemas/common.py`:

```python
from typing import Generic, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class Page(BaseModel, Generic[T]):
    """목록 응답의 공통 봉투. Agent가 total만 보고 페이징 여부를 판단할 수 있게 한다."""

    items: list[T]
    total: int
    page: int
    size: int
```

`backend/app/schemas/trip.py`:

```python
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, Field

from app.enums import ActivityAction, TripStatus


class TripCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    purpose_code: str = Field(min_length=1, max_length=40)
    purpose_detail: str = Field(min_length=1)
    destination_type_code: str = Field(min_length=1, max_length=40)
    country_code: str = Field(min_length=1, max_length=40)
    city: str = Field(min_length=1, max_length=80)
    start_date: date
    end_date: date
    transport_code: str = Field(min_length=1, max_length=40)
    accommodation_code: str = Field(min_length=1, max_length=40)
    cost_center_code: str = Field(min_length=1, max_length=20)
    # ge=0을 여기에 걸지 않는다. 금액·날짜 같은 교차/도메인 제약은 services/trip_rules.py가
    # 400 + 도메인 코드로 돌려주기로 통일했다. Pydantic이 먼저 잡으면 422 SCHEMA_INVALID가
    # 나가 Agent가 보는 에러 코드가 필드마다 달라진다.
    estimated_cost: Decimal


class TripUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    purpose_code: str | None = Field(default=None, min_length=1, max_length=40)
    purpose_detail: str | None = Field(default=None, min_length=1)
    destination_type_code: str | None = Field(default=None, min_length=1, max_length=40)
    country_code: str | None = Field(default=None, min_length=1, max_length=40)
    city: str | None = Field(default=None, min_length=1, max_length=80)
    start_date: date | None = None
    end_date: date | None = None
    transport_code: str | None = Field(default=None, min_length=1, max_length=40)
    accommodation_code: str | None = Field(default=None, min_length=1, max_length=40)
    cost_center_code: str | None = Field(default=None, min_length=1, max_length=20)
    estimated_cost: Decimal | None = None


class TripListItem(BaseModel):
    id: int
    trip_no: str
    title: str
    city: str
    country_code: str
    destination_type_code: str
    purpose_code: str
    start_date: date
    end_date: date
    status: TripStatus
    estimated_cost: Decimal
    user_id: int
    user_name: str
    approver_id: int | None
    approver_name: str | None


class TripDetail(TripListItem):
    purpose_detail: str
    transport_code: str
    accommodation_code: str
    cost_center_code: str
    cost_center_name: str | None
    submitted_at: datetime | None
    approved_at: datetime | None
    reject_reason: str | None
    created_at: datetime
    updated_at: datetime


class TimelineEntry(BaseModel):
    id: int
    action: ActivityAction
    from_status: str | None
    to_status: str | None
    memo: str | None
    actor_id: int
    actor_name: str
    created_at: datetime


class RejectRequest(BaseModel):
    reason: str
```

- [ ] **Step 4: 통과 확인**

Run: `cd backend && uv run pytest tests/test_schemas_trip.py -v`
Expected: 5 passed

- [ ] **Step 5: 커밋**

```bash
git add backend/app/schemas/common.py backend/app/schemas/trip.py backend/tests/test_schemas_trip.py
git commit -m "feat: add trip request and response schemas"
```

---

## Task 8: 출장 조회·목록 서비스

**Files:**
- Create: `backend/app/services/trips.py`
- Test: `backend/tests/test_trips_service_read.py`

**N+1 금지.** `Trip.user_id`/`approver_id`에 `relationship()`이 없는 것은 의도적이다. 이름이 필요하면 id를 모아 한 번에 가져온다. `app/routers/auth.py`의 `_to_user_out`을 목록에서 행마다 부르는 형태로 베끼지 말 것 — 40건 목록에서 80번의 쿼리가 된다.

- [ ] **Step 1: 실패하는 테스트 작성**

`backend/tests/test_trips_service_read.py`:

```python
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
```

- [ ] **Step 2: 실패 확인**

Run: `cd backend && uv run pytest tests/test_trips_service_read.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.services.trips'`

- [ ] **Step 3: 구현**

`backend/app/services/trips.py`:

```python
"""출장 서비스. 라우터는 이 모듈의 함수만 부르고 스키마를 그대로 응답한다.

이름 컬럼(user_name·approver_name)은 relationship 없이 id를 모아 한 번에 조회한다.
`relationship(lazy="selectin")`을 습관적으로 붙이지 말 것 — 이 프로젝트는 의도치 않은
eager loading을 이미 세 번 되돌린 이력이 있다.
"""

from dataclasses import dataclass, field
from datetime import date

from sqlalchemy import ColumnElement, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.enums import TripStatus, UserRole
from app.errors import ForbiddenError, NotFoundError
from app.models import CostCenter, Trip, User
from app.schemas.common import Page
from app.schemas.trip import TripDetail, TripListItem
from app.services.trip_rules import can_view_trip


@dataclass(frozen=True)
class TripFilters:
    scope: str = "mine"
    status: list[TripStatus] = field(default_factory=list)
    destination_type_code: str | None = None
    country_code: str | None = None
    q: str | None = None
    start_date_from: date | None = None
    start_date_to: date | None = None
    page: int = 1
    size: int = 20


async def _names_by_id(session: AsyncSession, user_ids: set[int]) -> dict[int, str]:
    if not user_ids:
        return {}
    rows = await session.execute(select(User.id, User.name).where(User.id.in_(user_ids)))
    return {user_id: name for user_id, name in rows}


async def build_list_items(session: AsyncSession, trips: list[Trip]) -> list[TripListItem]:
    ids = {trip.user_id for trip in trips} | {
        trip.approver_id for trip in trips if trip.approver_id is not None
    }
    names = await _names_by_id(session, ids)
    return [
        TripListItem(
            id=trip.id,
            trip_no=trip.trip_no,
            title=trip.title,
            city=trip.city,
            country_code=trip.country_code,
            destination_type_code=trip.destination_type_code,
            purpose_code=trip.purpose_code,
            start_date=trip.start_date,
            end_date=trip.end_date,
            status=trip.status,
            estimated_cost=trip.estimated_cost,
            user_id=trip.user_id,
            user_name=names.get(trip.user_id, ""),
            approver_id=trip.approver_id,
            approver_name=names.get(trip.approver_id) if trip.approver_id else None,
        )
        for trip in trips
    ]


async def build_detail(session: AsyncSession, trip: Trip) -> TripDetail:
    [item] = await build_list_items(session, [trip])
    cost_center_name = (
        await session.execute(
            select(CostCenter.name).where(CostCenter.code == trip.cost_center_code)
        )
    ).scalar_one_or_none()
    return TripDetail(
        **item.model_dump(),
        purpose_detail=trip.purpose_detail,
        transport_code=trip.transport_code,
        accommodation_code=trip.accommodation_code,
        cost_center_code=trip.cost_center_code,
        cost_center_name=cost_center_name,
        submitted_at=trip.submitted_at,
        approved_at=trip.approved_at,
        reject_reason=trip.reject_reason,
        created_at=trip.created_at,
        updated_at=trip.updated_at,
    )


async def load_visible_trip(session: AsyncSession, trip_id: int, user: User) -> Trip:
    """볼 수 없는 출장은 없는 것으로 취급한다 (spec 7: 타인 리소스 접근도 404)."""
    trip = await session.get(Trip, trip_id)
    if trip is None or not can_view_trip(
        user_id=user.id, role=user.role, owner_id=trip.user_id, approver_id=trip.approver_id
    ):
        raise NotFoundError("TRIP_NOT_FOUND", "출장을 찾을 수 없습니다")
    return trip


def _scope_conditions(user: User, scope: str) -> list[ColumnElement[bool]]:
    if scope == "mine":
        return [Trip.user_id == user.id]
    if scope == "approvals":
        # EMPLOYEE가 불러도 막지 않는다 — 결재자로 배정된 적이 없으면 그냥 0건이다.
        # 역할로 막으면 "팀장으로 승격됐는데 결재함이 안 열린다" 같은 상태 의존이 생긴다.
        return [Trip.approver_id == user.id]
    if user.role is not UserRole.ADMIN:
        raise ForbiddenError("FORBIDDEN_SCOPE", "전체 출장을 조회할 권한이 없습니다")
    return []


async def list_trips(
    session: AsyncSession, *, user: User, filters: TripFilters
) -> Page[TripListItem]:
    conditions = _scope_conditions(user, filters.scope)
    if filters.status:
        conditions.append(Trip.status.in_(filters.status))
    if filters.destination_type_code:
        conditions.append(Trip.destination_type_code == filters.destination_type_code)
    if filters.country_code:
        conditions.append(Trip.country_code == filters.country_code)
    if filters.start_date_from:
        conditions.append(Trip.start_date >= filters.start_date_from)
    if filters.start_date_to:
        conditions.append(Trip.start_date <= filters.start_date_to)
    if filters.q:
        # 사용자 입력의 % 와 _ 는 이스케이프하지 않는다. 검색 범위가 넓어질 뿐이고
        # 데모 규모에서 실질적 문제가 없다.
        like = f"%{filters.q}%"
        conditions.append(
            or_(Trip.title.ilike(like), Trip.city.ilike(like), Trip.trip_no.ilike(like))
        )

    total = (
        await session.execute(select(func.count()).select_from(Trip).where(*conditions))
    ).scalar_one()
    rows = (
        (
            await session.execute(
                select(Trip)
                .where(*conditions)
                .order_by(Trip.start_date.desc(), Trip.id.desc())
                .offset((filters.page - 1) * filters.size)
                .limit(filters.size)
            )
        )
        .scalars()
        .all()
    )
    return Page[TripListItem](
        items=await build_list_items(session, list(rows)),
        total=total,
        page=filters.page,
        size=filters.size,
    )


async def get_trip(session: AsyncSession, *, user: User, trip_id: int) -> TripDetail:
    return await build_detail(session, await load_visible_trip(session, trip_id, user))
```

- [ ] **Step 4: 통과 확인**

Run: `cd backend && uv run pytest tests/test_trips_service_read.py -v`
Expected: 14 passed

- [ ] **Step 5: 커밋**

```bash
git add backend/app/services/trips.py backend/tests/test_trips_service_read.py
git commit -m "feat: add trip read and list service without N+1 name lookups"
```

---

## Task 9: 출장 생성·수정·삭제 서비스

**Files:**
- Modify: `backend/app/services/trips.py`
- Test: `backend/tests/test_trips_service_write.py`

- [ ] **Step 1: 실패하는 테스트 작성**

`backend/tests/test_trips_service_write.py`:

```python
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
```

- [ ] **Step 2: 실패 확인**

Run: `cd backend && uv run pytest tests/test_trips_service_write.py -v`
Expected: FAIL — `ImportError: cannot import name 'create_trip' from 'app.services.trips'`

- [ ] **Step 3: 구현**

`backend/app/services/trips.py`의 import 블록을 다음으로 교체한다:

```python
from dataclasses import dataclass, field
from datetime import date

from sqlalchemy import ColumnElement, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.enums import ActivityAction, EntityType, TripStatus, UserRole
from app.errors import ForbiddenError, NotFoundError
from app.models import CostCenter, Trip, User
from app.schemas.common import Page
from app.schemas.trip import TripCreate, TripDetail, TripListItem, TripUpdate
from app.services.centers import assert_cost_center
from app.services.codes import validate_codes
from app.services.history import record_transition
from app.services.numbering import next_trip_no
from app.services.trip_rules import (
    assert_date_range,
    assert_deletable,
    assert_editable,
    assert_estimated_cost,
    assert_trip_owner,
    can_view_trip,
)
```

파일 끝에 추가:

```python
#: 코드값 검증이 필요한 필드. (group_code, 필드명) 짝을 여기 한 곳에서만 관리한다.
_CODE_FIELDS: tuple[tuple[str, str], ...] = (
    ("TRIP_PURPOSE", "purpose_code"),
    ("DESTINATION_TYPE", "destination_type_code"),
    ("COUNTRY", "country_code"),
    ("TRANSPORT", "transport_code"),
    ("ACCOMMODATION", "accommodation_code"),
)


async def _validate_writable_fields(session: AsyncSession, values: dict) -> None:
    await validate_codes(
        session, [(group, field_name, values[field_name]) for group, field_name in _CODE_FIELDS]
    )
    await assert_cost_center(session, values["cost_center_code"])
    assert_date_range(start_date=values["start_date"], end_date=values["end_date"])
    assert_estimated_cost(values["estimated_cost"])


async def create_trip(session: AsyncSession, *, user: User, payload: TripCreate) -> TripDetail:
    values = payload.model_dump()
    await _validate_writable_fields(session, values)

    trip = Trip(
        **values,
        trip_no=await next_trip_no(session, date.today()),
        user_id=user.id,
        status=TripStatus.DRAFT,
    )
    session.add(trip)
    await session.flush()
    await record_transition(
        session,
        entity_type=EntityType.TRIP,
        entity_id=trip.id,
        actor_id=user.id,
        action=ActivityAction.CREATED,
        to_status=TripStatus.DRAFT.value,
        memo="출장 신청서 작성",
    )
    await session.commit()
    return await build_detail(session, trip)


async def update_trip(
    session: AsyncSession, *, user: User, trip_id: int, payload: TripUpdate
) -> TripDetail:
    trip = await load_visible_trip(session, trip_id, user)
    assert_trip_owner(user_id=user.id, owner_id=trip.user_id)
    assert_editable(trip.status)

    changes = payload.model_dump(exclude_unset=True)
    # 보낸 필드만이 아니라 **병합 결과**를 검증한다. end_date만 바꿔도 start_date와의
    # 관계가 깨질 수 있고, destination_type만 바꿔도 country와 어긋날 수 있다.
    merged = {
        name: changes.get(name, getattr(trip, name))
        for name in (
            "purpose_code",
            "destination_type_code",
            "country_code",
            "transport_code",
            "accommodation_code",
            "cost_center_code",
            "start_date",
            "end_date",
            "estimated_cost",
        )
    }
    await _validate_writable_fields(session, merged)

    for name, value in changes.items():
        setattr(trip, name, value)
    await session.flush()
    await record_transition(
        session,
        entity_type=EntityType.TRIP,
        entity_id=trip.id,
        actor_id=user.id,
        action=ActivityAction.UPDATED,
        from_status=trip.status.value,
        to_status=trip.status.value,
        memo="출장 정보 수정",
    )
    await session.commit()
    return await build_detail(session, trip)


async def delete_trip(session: AsyncSession, *, user: User, trip_id: int) -> None:
    trip = await load_visible_trip(session, trip_id, user)
    assert_trip_owner(user_id=user.id, owner_id=trip.user_id)
    assert_deletable(trip.status)
    # activity_log.entity_id에는 FK가 없으므로 함께 지울 것이 없다. 삭제된 출장의
    # 이력이 남지만, 임시저장만 삭제 가능하므로 남는 이력은 CREATED/UPDATED뿐이다.
    await session.delete(trip)
    await session.commit()
```

- [ ] **Step 4: 통과 확인**

Run: `cd backend && uv run pytest tests/test_trips_service_write.py -v`
Expected: 15 passed

- [ ] **Step 5: 커밋**

```bash
git add backend/app/services/trips.py backend/tests/test_trips_service_write.py
git commit -m "feat: add trip create, update and delete service"
```

---

## Task 10: 상태 전이 서비스와 타임라인

**Files:**
- Modify: `backend/app/services/trips.py`
- Test: `backend/tests/test_trips_service_transitions.py`

전이는 `assert_trip_transition`(적법성) → `trip_rules`(권한·조건) → 필드 갱신 → `record_transition`(이력·알림) → `commit` 순서를 모든 함수가 똑같이 지킨다.

- [ ] **Step 1: 실패하는 테스트 작성**

`backend/tests/test_trips_service_transitions.py`:

```python
from datetime import date, timedelta

import pytest
from sqlalchemy import select

from app.enums import ActivityAction, NotificationType, TripStatus
from app.errors import ConflictError, ForbiddenError, NotFoundError, ValidationError
from app.models import ActivityLog, Notification
from app.schemas.trip import RejectRequest
from app.services.trips import (
    approve_trip,
    complete_trip,
    list_timeline,
    reject_trip,
    reopen_trip,
    submit_trip,
)
from tests.factories import make_trip, make_user


async def _pair(db_session):
    manager = await make_user(db_session, name="김연구")
    employee = await make_user(db_session, manager=manager, name="이사원")
    return manager, employee


async def test_submit_assigns_the_managers_approval(db_session):
    manager, employee = await _pair(db_session)
    trip = await make_trip(db_session, user=employee)

    detail = await submit_trip(db_session, user=employee, trip_id=trip.id)

    assert detail.status is TripStatus.SUBMITTED
    assert detail.approver_id == manager.id
    assert detail.submitted_at is not None


async def test_submit_notifies_the_approver(db_session):
    manager, employee = await _pair(db_session)
    trip = await make_trip(db_session, user=employee)

    await submit_trip(db_session, user=employee, trip_id=trip.id)

    notification = (await db_session.execute(select(Notification))).scalar_one()
    assert notification.user_id == manager.id
    assert notification.type is NotificationType.TRIP_SUBMITTED
    assert notification.link_url == f"/trips/{trip.id}"


async def test_submit_requires_a_manager(db_session):
    orphan = await make_user(db_session)
    trip = await make_trip(db_session, user=orphan)

    with pytest.raises(ConflictError) as exc_info:
        await submit_trip(db_session, user=orphan, trip_id=trip.id)

    assert exc_info.value.code == "NO_APPROVER"


async def test_submit_rejects_non_draft(db_session):
    _, employee = await _pair(db_session)
    trip = await make_trip(db_session, user=employee, status=TripStatus.APPROVED)

    with pytest.raises(ConflictError) as exc_info:
        await submit_trip(db_session, user=employee, trip_id=trip.id)

    assert exc_info.value.code == "TRIP_INVALID_TRANSITION"


async def test_submit_clears_the_previous_reject_reason(db_session):
    manager, employee = await _pair(db_session)
    trip = await make_trip(
        db_session, user=employee, status=TripStatus.DRAFT, reject_reason="예산 초과"
    )

    detail = await submit_trip(db_session, user=employee, trip_id=trip.id)

    assert detail.reject_reason is None


async def test_approve_by_the_assigned_approver(db_session):
    manager, employee = await _pair(db_session)
    trip = await make_trip(
        db_session, user=employee, status=TripStatus.SUBMITTED, approver_id=manager.id
    )

    detail = await approve_trip(db_session, user=manager, trip_id=trip.id)

    assert detail.status is TripStatus.APPROVED
    assert detail.approved_at is not None
    notification = (await db_session.execute(select(Notification))).scalar_one()
    assert notification.user_id == employee.id
    assert notification.type is NotificationType.TRIP_APPROVED


async def test_approve_by_the_owner_is_forbidden(db_session):
    manager, employee = await _pair(db_session)
    trip = await make_trip(
        db_session, user=employee, status=TripStatus.SUBMITTED, approver_id=manager.id
    )

    with pytest.raises(ForbiddenError) as exc_info:
        await approve_trip(db_session, user=employee, trip_id=trip.id)

    assert exc_info.value.code == "NOT_TRIP_APPROVER"


async def test_reject_stores_the_reason_and_notifies(db_session):
    manager, employee = await _pair(db_session)
    trip = await make_trip(
        db_session, user=employee, status=TripStatus.SUBMITTED, approver_id=manager.id
    )

    detail = await reject_trip(
        db_session, user=manager, trip_id=trip.id, payload=RejectRequest(reason="  예산 초과  ")
    )

    assert detail.status is TripStatus.REJECTED
    assert detail.reject_reason == "예산 초과"
    notification = (await db_session.execute(select(Notification))).scalar_one()
    assert notification.user_id == employee.id
    assert notification.type is NotificationType.TRIP_REJECTED
    assert "예산 초과" in notification.body


async def test_reject_requires_a_reason(db_session):
    manager, employee = await _pair(db_session)
    trip = await make_trip(
        db_session, user=employee, status=TripStatus.SUBMITTED, approver_id=manager.id
    )

    with pytest.raises(ValidationError) as exc_info:
        await reject_trip(
            db_session, user=manager, trip_id=trip.id, payload=RejectRequest(reason="   ")
        )

    assert exc_info.value.code == "REJECT_REASON_REQUIRED"


async def test_reopen_returns_a_rejected_trip_to_draft(db_session):
    manager, employee = await _pair(db_session)
    trip = await make_trip(
        db_session,
        user=employee,
        status=TripStatus.REJECTED,
        approver_id=manager.id,
        reject_reason="예산 초과",
    )

    detail = await reopen_trip(db_session, user=employee, trip_id=trip.id)

    assert detail.status is TripStatus.DRAFT
    assert detail.approver_id is None
    assert detail.submitted_at is None
    # 무엇을 고쳐야 하는지 화면에서 계속 보여야 하므로 사유는 남긴다.
    assert detail.reject_reason == "예산 초과"


async def test_reopen_rejects_non_rejected_trip(db_session):
    _, employee = await _pair(db_session)
    trip = await make_trip(db_session, user=employee, status=TripStatus.DRAFT)

    with pytest.raises(ConflictError) as exc_info:
        await reopen_trip(db_session, user=employee, trip_id=trip.id)

    assert exc_info.value.code == "TRIP_INVALID_TRANSITION"


async def test_complete_requires_the_trip_to_have_ended(db_session):
    manager, employee = await _pair(db_session)
    future = date.today() + timedelta(days=3)
    trip = await make_trip(
        db_session,
        user=employee,
        status=TripStatus.APPROVED,
        approver_id=manager.id,
        start_date=future,
    )

    with pytest.raises(ConflictError) as exc_info:
        await complete_trip(db_session, user=employee, trip_id=trip.id)

    assert exc_info.value.code == "TRIP_NOT_ENDED"


async def test_complete_after_the_end_date(db_session):
    manager, employee = await _pair(db_session)
    past = date.today() - timedelta(days=10)
    trip = await make_trip(
        db_session,
        user=employee,
        status=TripStatus.APPROVED,
        approver_id=manager.id,
        start_date=past,
    )

    detail = await complete_trip(db_session, user=employee, trip_id=trip.id)

    assert detail.status is TripStatus.COMPLETED
    # 완료는 본인이 본인 출장에 대해 하는 일이라 알릴 상대가 없다.
    assert (await db_session.execute(select(Notification))).scalars().all() == []
    log = (await db_session.execute(select(ActivityLog))).scalar_one()
    assert log.action is ActivityAction.COMPLETED


async def test_complete_by_the_approver_is_forbidden(db_session):
    manager, employee = await _pair(db_session)
    past = date.today() - timedelta(days=10)
    trip = await make_trip(
        db_session,
        user=employee,
        status=TripStatus.APPROVED,
        approver_id=manager.id,
        start_date=past,
    )

    with pytest.raises(ForbiddenError) as exc_info:
        await complete_trip(db_session, user=manager, trip_id=trip.id)

    assert exc_info.value.code == "NOT_TRIP_OWNER"


async def test_timeline_is_ordered_and_carries_actor_names(db_session):
    manager, employee = await _pair(db_session)
    trip = await make_trip(db_session, user=employee)
    await submit_trip(db_session, user=employee, trip_id=trip.id)
    await approve_trip(db_session, user=manager, trip_id=trip.id)

    entries = await list_timeline(db_session, user=employee, trip_id=trip.id)

    assert [entry.action for entry in entries] == [
        ActivityAction.SUBMITTED,
        ActivityAction.APPROVED,
    ]
    assert [entry.actor_name for entry in entries] == ["이사원", "김연구"]
    assert entries[0].from_status == "DRAFT"
    assert entries[1].to_status == "APPROVED"


async def test_timeline_of_someone_elses_trip_is_404(db_session):
    _, employee = await _pair(db_session)
    stranger = await make_user(db_session)
    trip = await make_trip(db_session, user=employee)

    with pytest.raises(NotFoundError) as exc_info:
        await list_timeline(db_session, user=stranger, trip_id=trip.id)

    assert exc_info.value.status_code == 404
```

- [ ] **Step 2: 실패 확인**

Run: `cd backend && uv run pytest tests/test_trips_service_transitions.py -v`
Expected: FAIL — `ImportError: cannot import name 'submit_trip' from 'app.services.trips'`

- [ ] **Step 3: 구현**

`backend/app/services/trips.py`의 import 블록을 다음으로 교체한다 (Task 9에서 만든 것에서 추가된 항목만 표시가 아니라 **전체 교체**):

```python
from dataclasses import dataclass, field
from datetime import date, datetime, timezone

from sqlalchemy import ColumnElement, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.enums import ActivityAction, EntityType, NotificationType, TripStatus, UserRole
from app.errors import ForbiddenError, NotFoundError
from app.models import ActivityLog, CostCenter, Trip, User
from app.schemas.common import Page
from app.schemas.trip import (
    RejectRequest,
    TimelineEntry,
    TripCreate,
    TripDetail,
    TripListItem,
    TripUpdate,
)
from app.services.centers import assert_cost_center
from app.services.codes import validate_codes
from app.services.history import NotifySpec, record_transition
from app.services.numbering import next_trip_no
from app.services.trip_rules import (
    assert_completable,
    assert_date_range,
    assert_deletable,
    assert_editable,
    assert_estimated_cost,
    assert_has_approver,
    assert_reject_reason,
    assert_transition_allowed,
    assert_trip_owner,
    can_view_trip,
)
```

`assert_trip_transition`·`assert_trip_approver`를 직접 import하지 않는다. 전이 검사는 전부 `assert_transition_allowed` 하나를 지나야 하며, 두 검사를 따로 부를 수 있게 열어두면 언젠가 한쪽만 부른다.

파일 끝에 추가:

```python
def _link(trip: Trip) -> str:
    return f"/trips/{trip.id}"


def _assert_transition(trip: Trip, user: User, target: TripStatus) -> None:
    """전이 검사는 이 한 줄만 부른다.

    적법성과 수행 주체를 따로 부르던 때는 한쪽을 빠뜨려도 조용했고, 그 실패는
    fail-open이었다 — 출장을 볼 수 있는 결재자가 신청자 전용 전이를 통과했다.
    """
    assert_transition_allowed(
        trip.status,
        target,
        user_id=user.id,
        owner_id=trip.user_id,
        approver_id=trip.approver_id,
    )


async def submit_trip(session: AsyncSession, *, user: User, trip_id: int) -> TripDetail:
    trip = await load_visible_trip(session, trip_id, user)
    _assert_transition(trip, user, TripStatus.SUBMITTED)
    # 모델에 CheckConstraint가 없으므로 상신 시점에 한 번 더 본다. DB를 직접 고친
    # 데이터가 결재로 흘러가는 것을 막는 마지막 지점이다.
    assert_date_range(start_date=trip.start_date, end_date=trip.end_date)
    approver_id = assert_has_approver(user.manager_id)

    from_status = trip.status
    trip.status = TripStatus.SUBMITTED
    trip.approver_id = approver_id
    trip.submitted_at = datetime.now(timezone.utc)
    trip.approved_at = None
    trip.reject_reason = None
    await session.flush()

    await record_transition(
        session,
        entity_type=EntityType.TRIP,
        entity_id=trip.id,
        actor_id=user.id,
        action=ActivityAction.SUBMITTED,
        from_status=from_status.value,
        to_status=TripStatus.SUBMITTED.value,
        notify=NotifySpec(
            user_id=approver_id,
            type=NotificationType.TRIP_SUBMITTED,
            title="출장 결재 요청",
            body=f"{user.name}님이 '{trip.title}' 출장을 상신했습니다.",
            link_url=_link(trip),
        ),
    )
    await session.commit()
    return await build_detail(session, trip)


async def approve_trip(session: AsyncSession, *, user: User, trip_id: int) -> TripDetail:
    trip = await load_visible_trip(session, trip_id, user)
    _assert_transition(trip, user, TripStatus.APPROVED)

    from_status = trip.status
    trip.status = TripStatus.APPROVED
    trip.approved_at = datetime.now(timezone.utc)
    await session.flush()

    await record_transition(
        session,
        entity_type=EntityType.TRIP,
        entity_id=trip.id,
        actor_id=user.id,
        action=ActivityAction.APPROVED,
        from_status=from_status.value,
        to_status=TripStatus.APPROVED.value,
        notify=NotifySpec(
            user_id=trip.user_id,
            type=NotificationType.TRIP_APPROVED,
            title="출장이 승인되었습니다",
            body=f"'{trip.title}' 출장이 {user.name}님에게 승인되었습니다.",
            link_url=_link(trip),
        ),
    )
    await session.commit()
    return await build_detail(session, trip)


async def reject_trip(
    session: AsyncSession, *, user: User, trip_id: int, payload: RejectRequest
) -> TripDetail:
    trip = await load_visible_trip(session, trip_id, user)
    _assert_transition(trip, user, TripStatus.REJECTED)
    reason = assert_reject_reason(payload.reason)

    from_status = trip.status
    trip.status = TripStatus.REJECTED
    trip.reject_reason = reason
    await session.flush()

    await record_transition(
        session,
        entity_type=EntityType.TRIP,
        entity_id=trip.id,
        actor_id=user.id,
        action=ActivityAction.REJECTED,
        from_status=from_status.value,
        to_status=TripStatus.REJECTED.value,
        memo=reason,
        notify=NotifySpec(
            user_id=trip.user_id,
            type=NotificationType.TRIP_REJECTED,
            title="출장이 반려되었습니다",
            body=f"'{trip.title}' 출장이 반려되었습니다. 사유: {reason}",
            link_url=_link(trip),
        ),
    )
    await session.commit()
    return await build_detail(session, trip)


async def reopen_trip(session: AsyncSession, *, user: User, trip_id: int) -> TripDetail:
    """반려된 출장을 임시저장으로 되돌려 재상신할 수 있게 한다 (spec 5.4의 REJECTED → DRAFT).

    spec 7의 엔드포인트 목록에는 없지만 spec 5.4의 상태도가 요구하는 전이다. 이것이
    없으면 반려된 출장은 영원히 반려 상태로 남는다.
    """
    trip = await load_visible_trip(session, trip_id, user)
    _assert_transition(trip, user, TripStatus.DRAFT)

    from_status = trip.status
    trip.status = TripStatus.DRAFT
    trip.approver_id = None
    trip.submitted_at = None
    trip.approved_at = None
    # reject_reason은 남긴다 — 무엇을 고쳐야 하는지 화면에서 계속 보여야 한다.
    # 다음 상신에서 submit_trip이 지운다.
    await session.flush()

    await record_transition(
        session,
        entity_type=EntityType.TRIP,
        entity_id=trip.id,
        actor_id=user.id,
        action=ActivityAction.UPDATED,
        from_status=from_status.value,
        to_status=TripStatus.DRAFT.value,
        memo="재작성을 위해 임시저장으로 되돌림",
    )
    await session.commit()
    return await build_detail(session, trip)


async def complete_trip(session: AsyncSession, *, user: User, trip_id: int) -> TripDetail:
    trip = await load_visible_trip(session, trip_id, user)
    _assert_transition(trip, user, TripStatus.COMPLETED)
    assert_completable(trip.end_date, today=date.today())

    from_status = trip.status
    trip.status = TripStatus.COMPLETED
    await session.flush()

    await record_transition(
        session,
        entity_type=EntityType.TRIP,
        entity_id=trip.id,
        actor_id=user.id,
        action=ActivityAction.COMPLETED,
        from_status=from_status.value,
        to_status=TripStatus.COMPLETED.value,
        memo="출장 완료 처리",
    )
    await session.commit()
    return await build_detail(session, trip)


async def list_timeline(
    session: AsyncSession, *, user: User, trip_id: int
) -> list[TimelineEntry]:
    trip = await load_visible_trip(session, trip_id, user)
    rows = (
        (
            await session.execute(
                select(ActivityLog)
                .where(
                    ActivityLog.entity_type == EntityType.TRIP,
                    ActivityLog.entity_id == trip.id,
                )
                .order_by(ActivityLog.created_at, ActivityLog.id)
            )
        )
        .scalars()
        .all()
    )
    names = await _names_by_id(session, {row.actor_id for row in rows})
    return [
        TimelineEntry(
            id=row.id,
            action=row.action,
            from_status=row.from_status,
            to_status=row.to_status,
            memo=row.memo,
            actor_id=row.actor_id,
            actor_name=names.get(row.actor_id, ""),
            created_at=row.created_at,
        )
        for row in rows
    ]
```

- [ ] **Step 4: 통과 확인**

Run: `cd backend && uv run pytest tests/test_trips_service_transitions.py -v`
Expected: 16 passed

- [ ] **Step 5: 전체 백엔드 테스트 확인**

Run: `cd backend && uv run pytest`
Expected: 전부 통과 (Phase 1의 116건 + 지금까지 추가분)

- [ ] **Step 6: 커밋**

```bash
git add backend/app/services/trips.py backend/tests/test_trips_service_transitions.py
git commit -m "feat: add trip state transitions and timeline service"
```

---

## Task 11: 출장 라우터 — CRUD와 목록

**Files:**
- Create: `backend/app/routers/trips.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_trips_api.py`

라우터에 로직을 두지 않는다. 쿼리 파라미터를 `TripFilters`로 옮기고 서비스를 부르는 것이 전부다.

- [ ] **Step 1: 실패하는 테스트 작성**

`backend/tests/test_trips_api.py`:

```python
from datetime import date, timedelta


def _body(**overrides) -> dict:
    payload = {
        "title": "울산공장 품질점검",
        "purpose_code": "AUDIT",
        "purpose_detail": "라인 3 품질 이슈 현장 확인",
        "destination_type_code": "DOMESTIC",
        "country_code": "KR",
        "city": "울산",
        "start_date": "2026-09-01",
        "end_date": "2026-09-03",
        "transport_code": "RAIL",
        "accommodation_code": "HOTEL",
        "cost_center_code": "CC2030",
        "estimated_cost": "450000",
    }
    payload.update(overrides)
    return payload


async def test_list_requires_authentication(client, seeded):
    response = await client.get("/api/v1/trips")

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "MISSING_CREDENTIALS"


async def test_list_returns_my_trips_paged(client, seeded, login_as):
    headers = await login_as("user1@skon.example")

    response = await client.get("/api/v1/trips", headers=headers, params={"size": 5})

    assert response.status_code == 200
    body = response.json()
    assert body["page"] == 1
    assert body["size"] == 5
    assert body["total"] >= 1
    assert len(body["items"]) <= 5
    assert all(item["user_name"] for item in body["items"])


async def test_list_rejects_all_scope_for_employee(client, seeded, login_as):
    headers = await login_as("user1@skon.example")

    response = await client.get("/api/v1/trips", headers=headers, params={"scope": "all"})

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "FORBIDDEN_SCOPE"


async def test_list_accepts_repeated_status_params(client, seeded, login_as):
    headers = await login_as("user1@skon.example")

    response = await client.get(
        "/api/v1/trips", headers=headers, params=[("status", "APPROVED"), ("status", "COMPLETED")]
    )

    assert response.status_code == 200
    assert {item["status"] for item in response.json()["items"]} <= {"APPROVED", "COMPLETED"}


async def test_list_rejects_unknown_status_value(client, seeded, login_as):
    headers = await login_as("user1@skon.example")

    response = await client.get("/api/v1/trips", headers=headers, params={"status": "NOPE"})

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "SCHEMA_INVALID"


async def test_create_returns_201_with_draft(client, seeded, login_as):
    headers = await login_as("user1@skon.example")

    response = await client.post("/api/v1/trips", headers=headers, json=_body())

    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "DRAFT"
    assert body["trip_no"].startswith("BT-")
    assert body["cost_center_name"]


async def test_create_rejects_invalid_code_with_field(client, seeded, login_as):
    headers = await login_as("user1@skon.example")

    response = await client.post(
        "/api/v1/trips", headers=headers, json=_body(transport_code="ROCKET")
    )

    assert response.status_code == 400
    error = response.json()["error"]
    assert error["code"] == "INVALID_CODE"
    assert error["field"] == "transport_code"


async def test_create_rejects_bad_date_range(client, seeded, login_as):
    headers = await login_as("user1@skon.example")

    response = await client.post(
        "/api/v1/trips", headers=headers, json=_body(start_date="2026-09-05", end_date="2026-09-01")
    )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "INVALID_DATE_RANGE"


async def test_get_detail_of_my_trip(client, seeded, login_as):
    headers = await login_as("user1@skon.example")
    created = await client.post("/api/v1/trips", headers=headers, json=_body())
    trip_id = created.json()["id"]

    response = await client.get(f"/api/v1/trips/{trip_id}", headers=headers)

    assert response.status_code == 200
    assert response.json()["purpose_detail"] == "라인 3 품질 이슈 현장 확인"


async def test_get_someone_elses_trip_is_404(client, seeded, login_as):
    mine = await login_as("user1@skon.example")
    created = await client.post("/api/v1/trips", headers=mine, json=_body())
    trip_id = created.json()["id"]
    theirs = await login_as("user2@skon.example")

    response = await client.get(f"/api/v1/trips/{trip_id}", headers=theirs)

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "TRIP_NOT_FOUND"


async def test_patch_updates_a_draft(client, seeded, login_as):
    headers = await login_as("user1@skon.example")
    created = await client.post("/api/v1/trips", headers=headers, json=_body())
    trip_id = created.json()["id"]

    response = await client.patch(
        f"/api/v1/trips/{trip_id}", headers=headers, json={"city": "서산"}
    )

    assert response.status_code == 200
    assert response.json()["city"] == "서산"
    assert response.json()["title"] == "울산공장 품질점검"


async def test_delete_removes_a_draft(client, seeded, login_as):
    headers = await login_as("user1@skon.example")
    created = await client.post("/api/v1/trips", headers=headers, json=_body())
    trip_id = created.json()["id"]

    response = await client.delete(f"/api/v1/trips/{trip_id}", headers=headers)

    assert response.status_code == 204
    assert (await client.get(f"/api/v1/trips/{trip_id}", headers=headers)).status_code == 404
```

- [ ] **Step 2: 실패 확인**

Run: `cd backend && uv run pytest tests/test_trips_api.py -v`
Expected: FAIL — 전부 404 (`/api/v1/trips` 라우트가 없음)

- [ ] **Step 3: 라우터 구현**

`backend/app/routers/trips.py`:

```python
from datetime import date
from typing import Annotated, Literal

from fastapi import APIRouter, Query, status

from app.deps import CurrentUser, DbSession
from app.enums import TripStatus
from app.schemas.common import Page
from app.schemas.trip import TripCreate, TripDetail, TripListItem, TripUpdate
from app.services import trips as trip_service

router = APIRouter(prefix="/api/v1/trips", tags=["trips"])


@router.get("", response_model=Page[TripListItem])
async def list_trips(
    user: CurrentUser,
    session: DbSession,
    scope: Annotated[Literal["mine", "approvals", "all"], Query()] = "mine",
    status_: Annotated[list[TripStatus] | None, Query(alias="status")] = None,
    destination_type_code: str | None = None,
    country_code: str | None = None,
    q: str | None = None,
    start_date_from: date | None = None,
    start_date_to: date | None = None,
    page: Annotated[int, Query(ge=1)] = 1,
    size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> Page[TripListItem]:
    return await trip_service.list_trips(
        session,
        user=user,
        filters=trip_service.TripFilters(
            scope=scope,
            status=status_ or [],
            destination_type_code=destination_type_code,
            country_code=country_code,
            q=q,
            start_date_from=start_date_from,
            start_date_to=start_date_to,
            page=page,
            size=size,
        ),
    )


@router.post("", response_model=TripDetail, status_code=status.HTTP_201_CREATED)
async def create_trip(payload: TripCreate, user: CurrentUser, session: DbSession) -> TripDetail:
    return await trip_service.create_trip(session, user=user, payload=payload)


@router.get("/{trip_id}", response_model=TripDetail)
async def get_trip(trip_id: int, user: CurrentUser, session: DbSession) -> TripDetail:
    return await trip_service.get_trip(session, user=user, trip_id=trip_id)


@router.patch("/{trip_id}", response_model=TripDetail)
async def update_trip(
    trip_id: int, payload: TripUpdate, user: CurrentUser, session: DbSession
) -> TripDetail:
    return await trip_service.update_trip(session, user=user, trip_id=trip_id, payload=payload)


@router.delete("/{trip_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_trip(trip_id: int, user: CurrentUser, session: DbSession) -> None:
    await trip_service.delete_trip(session, user=user, trip_id=trip_id)
```

`status_`에 `alias="status"`를 쓰는 이유: 파라미터 이름 `status`가 `fastapi.status` 모듈과 충돌한다. 쿼리스트링에서는 여전히 `?status=APPROVED`다.

- [ ] **Step 4: main.py에 등록**

`backend/app/main.py`의 import를 수정하고 라우터를 등록한다:

```python
from app.routers import auth, trips
```

```python
register_error_handlers(app)
app.include_router(auth.router)
app.include_router(trips.router)
```

- [ ] **Step 5: 통과 확인**

Run: `cd backend && uv run pytest tests/test_trips_api.py -v`
Expected: 12 passed

- [ ] **Step 6: 커밋**

```bash
git add backend/app/routers/trips.py backend/app/main.py backend/tests/test_trips_api.py
git commit -m "feat: add trip CRUD and list endpoints"
```

---

## Task 12: 출장 라우터 — 전이와 타임라인

**Files:**
- Modify: `backend/app/routers/trips.py`
- Test: `backend/tests/test_trips_transitions_api.py`

- [ ] **Step 1: 실패하는 테스트 작성**

`backend/tests/test_trips_transitions_api.py`:

```python
from sqlalchemy import select

from app.enums import TripStatus
from app.models import Trip


async def _first_trip_id(session, status: TripStatus) -> int:
    """시드 출장 중 지정 상태의 첫 건 id."""
    trip = (
        await session.execute(select(Trip).where(Trip.status == status).order_by(Trip.id))
    ).scalars().first()
    return trip.id


async def _owner_email(session, trip_id: int) -> str:
    from app.models import User

    trip = await session.get(Trip, trip_id)
    user = await session.get(User, trip.user_id)
    return user.email


async def _approver_email(session, trip_id: int) -> str:
    from app.models import User

    trip = await session.get(Trip, trip_id)
    approver = await session.get(User, trip.approver_id)
    return approver.email


async def test_submit_moves_draft_to_submitted(client, seeded, login_as):
    trip_id = await _first_trip_id(seeded, TripStatus.DRAFT)
    headers = await login_as(await _owner_email(seeded, trip_id))

    response = await client.post(f"/api/v1/trips/{trip_id}/submit", headers=headers)

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "SUBMITTED"
    assert body["approver_id"] is not None


async def test_submit_twice_returns_409_with_domain_code(client, seeded, login_as):
    trip_id = await _first_trip_id(seeded, TripStatus.DRAFT)
    headers = await login_as(await _owner_email(seeded, trip_id))
    await client.post(f"/api/v1/trips/{trip_id}/submit", headers=headers)

    response = await client.post(f"/api/v1/trips/{trip_id}/submit", headers=headers)

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "TRIP_INVALID_TRANSITION"


async def test_approve_by_the_assigned_manager(client, seeded, login_as):
    trip_id = await _first_trip_id(seeded, TripStatus.SUBMITTED)
    headers = await login_as(await _approver_email(seeded, trip_id))

    response = await client.post(f"/api/v1/trips/{trip_id}/approve", headers=headers)

    assert response.status_code == 200
    assert response.json()["status"] == "APPROVED"


async def test_approve_by_the_owner_is_403(client, seeded, login_as):
    trip_id = await _first_trip_id(seeded, TripStatus.SUBMITTED)
    headers = await login_as(await _owner_email(seeded, trip_id))

    response = await client.post(f"/api/v1/trips/{trip_id}/approve", headers=headers)

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "NOT_TRIP_APPROVER"


async def test_reject_requires_a_reason(client, seeded, login_as):
    trip_id = await _first_trip_id(seeded, TripStatus.SUBMITTED)
    headers = await login_as(await _approver_email(seeded, trip_id))

    response = await client.post(
        f"/api/v1/trips/{trip_id}/reject", headers=headers, json={"reason": "  "}
    )

    assert response.status_code == 400
    error = response.json()["error"]
    assert error["code"] == "REJECT_REASON_REQUIRED"
    assert error["field"] == "reason"


async def test_reject_then_reopen_then_resubmit(client, seeded, login_as):
    trip_id = await _first_trip_id(seeded, TripStatus.SUBMITTED)
    approver = await login_as(await _approver_email(seeded, trip_id))
    owner = await login_as(await _owner_email(seeded, trip_id))

    rejected = await client.post(
        f"/api/v1/trips/{trip_id}/reject", headers=approver, json={"reason": "예산 초과"}
    )
    assert rejected.status_code == 200
    assert rejected.json()["reject_reason"] == "예산 초과"

    reopened = await client.post(f"/api/v1/trips/{trip_id}/reopen", headers=owner)
    assert reopened.status_code == 200
    assert reopened.json()["status"] == "DRAFT"

    resubmitted = await client.post(f"/api/v1/trips/{trip_id}/submit", headers=owner)
    assert resubmitted.status_code == 200
    assert resubmitted.json()["status"] == "SUBMITTED"
    assert resubmitted.json()["reject_reason"] is None


async def test_complete_requires_the_trip_to_have_ended(client, seeded, login_as):
    from datetime import date, timedelta

    trip = (
        await seeded.execute(
            select(Trip).where(Trip.status == TripStatus.APPROVED).order_by(Trip.id)
        )
    ).scalars().first()
    trip.start_date = date.today() + timedelta(days=3)
    trip.end_date = date.today() + timedelta(days=5)
    await seeded.flush()
    headers = await login_as(await _owner_email(seeded, trip.id))

    response = await client.post(f"/api/v1/trips/{trip.id}/complete", headers=headers)

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "TRIP_NOT_ENDED"


async def test_timeline_lists_transitions_with_actor_names(client, seeded, login_as):
    trip_id = await _first_trip_id(seeded, TripStatus.DRAFT)
    owner = await login_as(await _owner_email(seeded, trip_id))
    await client.post(f"/api/v1/trips/{trip_id}/submit", headers=owner)

    response = await client.get(f"/api/v1/trips/{trip_id}/timeline", headers=owner)

    assert response.status_code == 200
    entries = response.json()
    assert entries[-1]["action"] == "SUBMITTED"
    assert entries[-1]["actor_name"]
    assert entries[-1]["to_status"] == "SUBMITTED"


async def test_notification_reaches_the_approver(client, seeded, login_as):
    trip_id = await _first_trip_id(seeded, TripStatus.DRAFT)
    owner = await login_as(await _owner_email(seeded, trip_id))
    await client.post(f"/api/v1/trips/{trip_id}/submit", headers=owner)

    from app.models import Notification

    rows = (await seeded.execute(select(Notification))).scalars().all()
    assert any(n.link_url == f"/trips/{trip_id}" for n in rows)
```

- [ ] **Step 2: 실패 확인**

Run: `cd backend && uv run pytest tests/test_trips_transitions_api.py -v`
Expected: FAIL — 전이 엔드포인트가 없어 404

- [ ] **Step 3: 구현**

`backend/app/routers/trips.py` 상단 import에 `RejectRequest`와 `TimelineEntry`를 더한다:

```python
from app.schemas.trip import (
    RejectRequest,
    TimelineEntry,
    TripCreate,
    TripDetail,
    TripListItem,
    TripUpdate,
)
```

파일 끝에 추가:

```python
@router.post("/{trip_id}/submit", response_model=TripDetail)
async def submit_trip(trip_id: int, user: CurrentUser, session: DbSession) -> TripDetail:
    return await trip_service.submit_trip(session, user=user, trip_id=trip_id)


@router.post("/{trip_id}/approve", response_model=TripDetail)
async def approve_trip(trip_id: int, user: CurrentUser, session: DbSession) -> TripDetail:
    return await trip_service.approve_trip(session, user=user, trip_id=trip_id)


@router.post("/{trip_id}/reject", response_model=TripDetail)
async def reject_trip(
    trip_id: int, payload: RejectRequest, user: CurrentUser, session: DbSession
) -> TripDetail:
    return await trip_service.reject_trip(session, user=user, trip_id=trip_id, payload=payload)


@router.post("/{trip_id}/reopen", response_model=TripDetail)
async def reopen_trip(trip_id: int, user: CurrentUser, session: DbSession) -> TripDetail:
    return await trip_service.reopen_trip(session, user=user, trip_id=trip_id)


@router.post("/{trip_id}/complete", response_model=TripDetail)
async def complete_trip(trip_id: int, user: CurrentUser, session: DbSession) -> TripDetail:
    return await trip_service.complete_trip(session, user=user, trip_id=trip_id)


@router.get("/{trip_id}/timeline", response_model=list[TimelineEntry])
async def get_timeline(trip_id: int, user: CurrentUser, session: DbSession) -> list[TimelineEntry]:
    return await trip_service.list_timeline(session, user=user, trip_id=trip_id)
```

- [ ] **Step 4: 통과 확인**

Run: `cd backend && uv run pytest tests/test_trips_transitions_api.py -v`
Expected: 9 passed

- [ ] **Step 5: 커밋**

```bash
git add backend/app/routers/trips.py backend/tests/test_trips_transitions_api.py
git commit -m "feat: add trip transition and timeline endpoints"
```

---

## Task 13: 공통코드 조회 API

**Files:**
- Modify: `backend/app/services/codes.py`
- Create: `backend/app/schemas/code.py`
- Create: `backend/app/routers/codes.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_codes_api.py`

출장 폼의 드롭다운이 여기서 값을 가져온다. Agent도 같은 엔드포인트로 유효값을 스스로 발견한다 (spec 5.2).

- [ ] **Step 1: 실패하는 테스트 작성**

`backend/tests/test_codes_api.py`:

```python
async def test_codes_require_authentication(client, seeded):
    assert (await client.get("/api/v1/codes")).status_code == 401


async def test_list_all_groups(client, seeded, login_as):
    headers = await login_as("user1@skon.example")

    response = await client.get("/api/v1/codes", headers=headers)

    assert response.status_code == 200
    groups = {group["group_code"] for group in response.json()}
    assert {"TRIP_PURPOSE", "DESTINATION_TYPE", "TRANSPORT", "ACCOMMODATION", "COUNTRY"} <= groups


async def test_get_one_group_sorted_with_extra(client, seeded, login_as):
    headers = await login_as("user1@skon.example")

    response = await client.get("/api/v1/codes/COUNTRY", headers=headers)

    assert response.status_code == 200
    body = response.json()
    assert body["group_code"] == "COUNTRY"
    assert [code["sort_order"] for code in body["codes"]] == sorted(
        code["sort_order"] for code in body["codes"]
    )
    korea = next(code for code in body["codes"] if code["code"] == "KR")
    assert korea["extra"]["currency"] == "KRW"


async def test_unknown_group_is_404(client, seeded, login_as):
    headers = await login_as("user1@skon.example")

    response = await client.get("/api/v1/codes/NOPE", headers=headers)

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "CODE_GROUP_NOT_FOUND"


async def test_inactive_codes_are_hidden(client, seeded, login_as, db_session):
    from sqlalchemy import select

    from app.models import Code, CodeGroup

    group_id = (
        await db_session.execute(select(CodeGroup.id).where(CodeGroup.group_code == "TRANSPORT"))
    ).scalar_one()
    code = (
        await db_session.execute(
            select(Code).where(Code.group_id == group_id, Code.code == "BUS")
        )
    ).scalar_one()
    code.is_active = False
    await db_session.flush()
    headers = await login_as("user1@skon.example")

    response = await client.get("/api/v1/codes/TRANSPORT", headers=headers)

    assert "BUS" not in {item["code"] for item in response.json()["codes"]}
```

- [ ] **Step 2: 실패 확인**

Run: `cd backend && uv run pytest tests/test_codes_api.py -v`
Expected: FAIL — 401 대신 404 (라우트 없음)

- [ ] **Step 3: 스키마·서비스·라우터 구현**

`backend/app/schemas/code.py`:

```python
from typing import Any

from pydantic import BaseModel


class CodeOut(BaseModel):
    code: str
    name: str
    sort_order: int
    extra: dict[str, Any]


class CodeGroupOut(BaseModel):
    group_code: str
    name: str
    description: str | None
    codes: list[CodeOut]
```

`backend/app/services/codes.py` 끝에 추가 (import에 `NotFoundError`를 더한다):

```python
def _to_group_out(group: CodeGroup) -> CodeGroupOut:
    """CodeGroup.codes는 lazy="selectin"이라 그룹 조회 한 번에 함께 실려온다.
    비활성 코드는 여기서 걸러낸다 — 관리자만 보는 값을 폼 드롭다운에 내보내지 않는다."""
    return CodeGroupOut(
        group_code=group.group_code,
        name=group.name,
        description=group.description,
        codes=[
            CodeOut(code=code.code, name=code.name, sort_order=code.sort_order, extra=code.extra)
            for code in sorted(
                (code for code in group.codes if code.is_active), key=lambda c: c.sort_order
            )
        ],
    )


async def load_code_groups(session: AsyncSession) -> list[CodeGroupOut]:
    groups = (
        (
            await session.execute(
                select(CodeGroup)
                .where(CodeGroup.is_active.is_(True))
                .order_by(CodeGroup.group_code)
            )
        )
        .scalars()
        .all()
    )
    return [_to_group_out(group) for group in groups]


async def load_code_group(session: AsyncSession, group_code: str) -> CodeGroupOut:
    group = (
        await session.execute(
            select(CodeGroup).where(
                CodeGroup.group_code == group_code, CodeGroup.is_active.is_(True)
            )
        )
    ).scalar_one_or_none()
    if group is None:
        raise NotFoundError("CODE_GROUP_NOT_FOUND", f"존재하지 않는 코드그룹입니다: {group_code}")
    return _to_group_out(group)
```

같은 파일 상단 import를 다음으로 교체:

```python
from app.errors import NotFoundError, ValidationError
from app.models import Code, CodeGroup
from app.schemas.code import CodeGroupOut, CodeOut
```

`backend/app/routers/codes.py`:

```python
from fastapi import APIRouter

from app.deps import CurrentUser, DbSession
from app.schemas.code import CodeGroupOut
from app.services import codes as code_service

router = APIRouter(prefix="/api/v1/codes", tags=["codes"])


@router.get("", response_model=list[CodeGroupOut])
async def list_code_groups(user: CurrentUser, session: DbSession) -> list[CodeGroupOut]:
    return await code_service.load_code_groups(session)


@router.get("/{group_code}", response_model=CodeGroupOut)
async def get_code_group(group_code: str, user: CurrentUser, session: DbSession) -> CodeGroupOut:
    return await code_service.load_code_group(session, group_code)
```

`backend/app/main.py`:

```python
from app.routers import auth, codes, trips
```

```python
app.include_router(codes.router)
```

- [ ] **Step 4: 통과 확인**

Run: `cd backend && uv run pytest tests/test_codes_api.py -v`
Expected: 5 passed

- [ ] **Step 5: 커밋**

```bash
git add backend/app/schemas/code.py backend/app/services/codes.py backend/app/routers/codes.py backend/app/main.py backend/tests/test_codes_api.py
git commit -m "feat: add common code lookup endpoints"
```

---

## Task 14: 센터 조회 API

**Files:**
- Create: `backend/app/schemas/center.py`
- Modify: `backend/app/services/centers.py`
- Create: `backend/app/routers/centers.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_centers_api.py`

- [ ] **Step 1: 실패하는 테스트 작성**

`backend/tests/test_centers_api.py`:

```python
async def test_centers_require_authentication(client, seeded):
    assert (await client.get("/api/v1/cost-centers")).status_code == 401


async def test_list_cost_centers(client, seeded, login_as):
    headers = await login_as("user1@skon.example")

    response = await client.get("/api/v1/cost-centers", headers=headers)

    assert response.status_code == 200
    codes = [center["code"] for center in response.json()]
    assert "CC2030" in codes
    assert codes == sorted(codes)


async def test_list_fund_centers(client, seeded, login_as):
    headers = await login_as("user1@skon.example")

    response = await client.get("/api/v1/fund-centers", headers=headers)

    assert response.status_code == 200
    assert "FC1010" in [center["code"] for center in response.json()]


async def test_inactive_centers_are_hidden(client, seeded, login_as, db_session):
    from sqlalchemy import select

    from app.models import CostCenter

    center = (
        await db_session.execute(select(CostCenter).where(CostCenter.code == "CC2030"))
    ).scalar_one()
    center.is_active = False
    await db_session.flush()
    headers = await login_as("user1@skon.example")

    response = await client.get("/api/v1/cost-centers", headers=headers)

    assert "CC2030" not in [center["code"] for center in response.json()]
```

- [ ] **Step 2: 실패 확인**

Run: `cd backend && uv run pytest tests/test_centers_api.py -v`
Expected: FAIL — 404 (라우트 없음)

- [ ] **Step 3: 구현**

`backend/app/schemas/center.py`:

```python
from pydantic import BaseModel, ConfigDict


class CenterOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    code: str
    name: str
    department_id: int | None
```

먼저 `backend/app/services/centers.py`에 조회 함수를 추가한다. **라우터에 쿼리를 두지 않는다** — `is_active` 필터가 서비스와 라우터 두 곳에 생기면 나중에 한쪽만 고치게 된다.

```python
async def load_active_centers(session: AsyncSession, model: CenterModel) -> list[CenterOut]:
    """활성 센터를 코드 순으로 돌려준다. Task 3의 load_active_center_codes와 달리
    이름·부서까지 필요해서 엔티티를 읽는다 — 화면 드롭다운이 코드만으로는 못 쓴다."""
    rows = (
        (
            await session.execute(
                select(model).where(model.is_active.is_(True)).order_by(model.code)
            )
        )
        .scalars()
        .all()
    )
    return [CenterOut.model_validate(row) for row in rows]
```

`app/services/centers.py` 상단 import에 `from app.schemas.center import CenterOut`를 더한다.

`backend/app/routers/centers.py`:

```python
from fastapi import APIRouter

from app.deps import CurrentUser, DbSession
from app.models import CostCenter, FundCenter
from app.schemas.center import CenterOut
from app.services.centers import load_active_centers

router = APIRouter(prefix="/api/v1", tags=["centers"])


@router.get("/fund-centers", response_model=list[CenterOut])
async def list_fund_centers(user: CurrentUser, session: DbSession) -> list[CenterOut]:
    return await load_active_centers(session, FundCenter)


@router.get("/cost-centers", response_model=list[CenterOut])
async def list_cost_centers(user: CurrentUser, session: DbSession) -> list[CenterOut]:
    return await load_active_centers(session, CostCenter)
```

`backend/app/main.py`:

```python
from app.routers import auth, centers, codes, trips
```

```python
app.include_router(centers.router)
```

- [ ] **Step 4: 통과 확인**

Run: `cd backend && uv run pytest tests/test_centers_api.py -v`
Expected: 4 passed

- [ ] **Step 5: 커밋**

```bash
git add backend/app/schemas/center.py backend/app/routers/centers.py backend/app/main.py backend/tests/test_centers_api.py
git commit -m "feat: add fund and cost center lookup endpoints"
```

---

## Task 15: 알림 API

**Files:**
- Create: `backend/app/schemas/notification.py`
- Create: `backend/app/services/notifications.py`
- Create: `backend/app/routers/notifications.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_notifications_api.py`

- [ ] **Step 1: 실패하는 테스트 작성**

`backend/tests/test_notifications_api.py`:

```python
from sqlalchemy import select

from app.enums import TripStatus
from app.models import Trip, User


async def _submit_one_trip(client, session, login_as) -> tuple[dict, str]:
    """시드의 DRAFT 출장을 상신해 결재자에게 알림을 만든다. (결재자 헤더, 출장 링크) 반환."""
    trip = (
        await session.execute(select(Trip).where(Trip.status == TripStatus.DRAFT).order_by(Trip.id))
    ).scalars().first()
    owner = await session.get(User, trip.user_id)
    owner_headers = await login_as(owner.email)
    await client.post(f"/api/v1/trips/{trip.id}/submit", headers=owner_headers)
    await session.refresh(trip)
    approver = await session.get(User, trip.approver_id)
    return await login_as(approver.email), f"/trips/{trip.id}"


async def test_notifications_require_authentication(client, seeded):
    assert (await client.get("/api/v1/notifications")).status_code == 401


async def test_list_returns_my_notifications_with_unread_count(client, seeded, login_as):
    approver_headers, link = await _submit_one_trip(client, seeded, login_as)

    response = await client.get("/api/v1/notifications", headers=approver_headers)

    assert response.status_code == 200
    body = response.json()
    assert body["unread"] >= 1
    assert body["items"][0]["link_url"] == link
    assert body["items"][0]["is_read"] is False


async def test_list_can_filter_unread_only(client, seeded, login_as):
    approver_headers, _ = await _submit_one_trip(client, seeded, login_as)
    listed = await client.get("/api/v1/notifications", headers=approver_headers)
    notification_id = listed.json()["items"][0]["id"]
    await client.post(f"/api/v1/notifications/{notification_id}/read", headers=approver_headers)

    response = await client.get(
        "/api/v1/notifications", headers=approver_headers, params={"unread_only": "true"}
    )

    assert notification_id not in [item["id"] for item in response.json()["items"]]
    assert response.json()["unread"] == 0


async def test_mark_read_returns_the_updated_notification(client, seeded, login_as):
    approver_headers, _ = await _submit_one_trip(client, seeded, login_as)
    listed = await client.get("/api/v1/notifications", headers=approver_headers)
    notification_id = listed.json()["items"][0]["id"]

    response = await client.post(
        f"/api/v1/notifications/{notification_id}/read", headers=approver_headers
    )

    assert response.status_code == 200
    assert response.json()["is_read"] is True


async def test_cannot_read_someone_elses_notification(client, seeded, login_as):
    approver_headers, _ = await _submit_one_trip(client, seeded, login_as)
    listed = await client.get("/api/v1/notifications", headers=approver_headers)
    notification_id = listed.json()["items"][0]["id"]
    stranger = await login_as("user2@skon.example")

    response = await client.post(
        f"/api/v1/notifications/{notification_id}/read", headers=stranger
    )

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "NOTIFICATION_NOT_FOUND"
```

- [ ] **Step 2: 실패 확인**

Run: `cd backend && uv run pytest tests/test_notifications_api.py -v`
Expected: FAIL — 404 (라우트 없음)

- [ ] **Step 3: 구현**

`backend/app/schemas/notification.py`:

```python
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.enums import NotificationType
from app.schemas.common import Page


class NotificationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    type: NotificationType
    title: str
    body: str
    link_url: str | None
    is_read: bool
    created_at: datetime


class NotificationPage(Page[NotificationOut]):
    #: 읽지 않은 **전체** 개수. 헤더의 뱃지가 목록을 다시 세지 않게 하려고 봉투에 싣는다.
    unread: int
```

`backend/app/services/notifications.py`:

```python
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.errors import NotFoundError
from app.models import Notification, User
from app.schemas.notification import NotificationOut, NotificationPage


async def list_notifications(
    session: AsyncSession, *, user: User, unread_only: bool = False, page: int = 1, size: int = 20
) -> NotificationPage:
    conditions = [Notification.user_id == user.id]
    if unread_only:
        conditions.append(Notification.is_read.is_(False))

    total = (
        await session.execute(select(func.count()).select_from(Notification).where(*conditions))
    ).scalar_one()
    unread = (
        await session.execute(
            select(func.count())
            .select_from(Notification)
            .where(Notification.user_id == user.id, Notification.is_read.is_(False))
        )
    ).scalar_one()
    rows = (
        (
            await session.execute(
                select(Notification)
                .where(*conditions)
                .order_by(Notification.created_at.desc(), Notification.id.desc())
                .offset((page - 1) * size)
                .limit(size)
            )
        )
        .scalars()
        .all()
    )
    return NotificationPage(
        items=[NotificationOut.model_validate(row) for row in rows],
        total=total,
        unread=unread,
        page=page,
        size=size,
    )


async def mark_read(session: AsyncSession, *, user: User, notification_id: int) -> NotificationOut:
    notification = await session.get(Notification, notification_id)
    # 타인의 알림은 존재 자체를 알리지 않는다.
    if notification is None or notification.user_id != user.id:
        raise NotFoundError("NOTIFICATION_NOT_FOUND", "알림을 찾을 수 없습니다")
    notification.is_read = True
    await session.commit()
    return NotificationOut.model_validate(notification)
```

`backend/app/routers/notifications.py`:

```python
from typing import Annotated

from fastapi import APIRouter, Query

from app.deps import CurrentUser, DbSession
from app.schemas.notification import NotificationOut, NotificationPage
from app.services import notifications as notification_service

router = APIRouter(prefix="/api/v1/notifications", tags=["notifications"])


@router.get("", response_model=NotificationPage)
async def list_notifications(
    user: CurrentUser,
    session: DbSession,
    unread_only: bool = False,
    page: Annotated[int, Query(ge=1)] = 1,
    size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> NotificationPage:
    return await notification_service.list_notifications(
        session, user=user, unread_only=unread_only, page=page, size=size
    )


@router.post("/{notification_id}/read", response_model=NotificationOut)
async def mark_read(
    notification_id: int, user: CurrentUser, session: DbSession
) -> NotificationOut:
    return await notification_service.mark_read(
        session, user=user, notification_id=notification_id
    )
```

`backend/app/main.py`:

```python
from app.routers import auth, centers, codes, notifications, trips
```

```python
app.include_router(notifications.router)
```

- [ ] **Step 4: 통과 확인**

Run: `cd backend && uv run pytest tests/test_notifications_api.py -v`
Expected: 5 passed

- [ ] **Step 5: 백엔드 전체 확인**

Run: `cd backend && uv run pytest`
Expected: 전부 통과

- [ ] **Step 6: 커밋**

```bash
git add backend/app/schemas/notification.py backend/app/services/notifications.py backend/app/routers/notifications.py backend/app/main.py backend/tests/test_notifications_api.py
git commit -m "feat: add notification endpoints"
```

---

## Task 16: 딥링크 보존과 공개 경로 접두사

**Files:**
- Create: `frontend/src/lib/nav.ts`
- Create: `frontend/src/lib/nav.test.ts`
- Modify: `frontend/src/routes/+layout.svelte`
- Modify: `frontend/src/routes/login/+page.svelte`

Phase 1 이월: 미로그인 상태로 `/trips/42`에 접근하면 `/login`으로 튕기고 로그인 후 하드코딩된 `/`로 간다. 공유 가능한 출장 링크가 생기는 지금 반드시 걸린다.

- [ ] **Step 1: 실패하는 테스트 작성**

`frontend/src/lib/nav.test.ts`:

```ts
import { describe, expect, it } from 'vitest';
import { isPublicPath, loginPathFor, safeRedirect } from './nav';

describe('isPublicPath', () => {
	it('matches the public route itself', () => {
		expect(isPublicPath('/login')).toBe(true);
	});

	it('matches children of a public route', () => {
		expect(isPublicPath('/login/reset')).toBe(true);
	});

	it('does not match a route that merely shares a prefix', () => {
		expect(isPublicPath('/login-help')).toBe(false);
	});

	it('rejects protected routes', () => {
		expect(isPublicPath('/trips/42')).toBe(false);
	});
});

describe('safeRedirect', () => {
	it('keeps an internal path', () => {
		expect(safeRedirect('/trips/42?tab=timeline')).toBe('/trips/42?tab=timeline');
	});

	it('falls back to root when absent', () => {
		expect(safeRedirect(null)).toBe('/');
	});

	it('rejects protocol-relative URLs that would leave the site', () => {
		expect(safeRedirect('//evil.example/phish')).toBe('/');
	});

	it('rejects absolute URLs', () => {
		expect(safeRedirect('https://evil.example')).toBe('/');
	});
});

describe('loginPathFor', () => {
	it('encodes the target so query strings survive', () => {
		expect(loginPathFor('/trips', '?status=SUBMITTED')).toBe(
			'/login?redirect=%2Ftrips%3Fstatus%3DSUBMITTED'
		);
	});

	it('does not add a redirect for the root path', () => {
		expect(loginPathFor('/', '')).toBe('/login');
	});
});
```

- [ ] **Step 2: 실패 확인**

Run: `cd frontend && npm test`
Expected: FAIL — `Failed to resolve import "./nav"`

- [ ] **Step 3: 구현**

`frontend/src/lib/nav.ts`:

```ts
/** 로그인 없이 볼 수 있는 라우트. 자식 경로까지 공개로 취급한다. */
const PUBLIC_PREFIXES = ['/login'];

export function isPublicPath(pathname: string): boolean {
	return PUBLIC_PREFIXES.some((prefix) => pathname === prefix || pathname.startsWith(`${prefix}/`));
}

/**
 * 로그인 후 돌아갈 경로를 검증한다.
 * `//host` 형태는 브라우저가 프로토콜 상대 URL로 해석해 외부 사이트로 나가므로 막는다.
 */
export function safeRedirect(target: string | null): string {
	if (!target || !target.startsWith('/') || target.startsWith('//')) return '/';
	return target;
}

/** 가드가 보낼 로그인 경로. 원래 가려던 곳을 redirect 쿼리에 보존한다. */
export function loginPathFor(pathname: string, search: string): string {
	const target = `${pathname}${search}`;
	if (target === '/') return '/login';
	return `/login?redirect=${encodeURIComponent(target)}`;
}
```

- [ ] **Step 4: 통과 확인**

Run: `cd frontend && npm test`
Expected: nav.test.ts 10건 통과

- [ ] **Step 5: 레이아웃 가드 교체**

`frontend/src/routes/+layout.svelte` 전체를 다음으로 교체한다:

```svelte
<script lang="ts">
	import '../app.css';
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import { page } from '$app/state';
	import AppShell from '$lib/components/AppShell.svelte';
	import { isPublicPath, loginPathFor } from '$lib/nav';
	import { auth } from '$lib/stores/auth.svelte';

	let { children } = $props();

	let restored = $state(false);

	// 복원은 마운트 시 한 번만. $effect 안에서 호출하면 auth 상태 변경이
	// 다시 effect를 트리거해 무한 루프가 된다.
	onMount(async () => {
		// 세션 만료 등으로 401이 나면 스토어가 이 콜백으로 화면을 정리한다.
		// 스토어가 $app/navigation을 직접 import하면 vitest에서 못 돌리므로 주입한다.
		auth.onUnauthorized = () => {
			goto(loginPathFor(page.url.pathname, page.url.search));
		};
		await auth.restore();
		restored = true;
	});

	$effect(() => {
		if (!restored) return;
		if (auth.user === null && !isPublicPath(page.url.pathname)) {
			goto(loginPathFor(page.url.pathname, page.url.search));
		}
	});
</script>

{#if !restored}
	<div class="flex min-h-screen items-center justify-center text-body-sm text-muted">
		불러오는 중…
	</div>
{:else if isPublicPath(page.url.pathname)}
	{@render children()}
{:else if auth.user}
	<AppShell>
		{@render children()}
	</AppShell>
{/if}
```

- [ ] **Step 6: 로그인 후 복귀 경로 적용**

`frontend/src/routes/login/+page.svelte`의 `<script>`에서 import에 두 줄을 더하고 `handleSubmit`의 `goto('/')`를 바꾼다:

```ts
	import { page } from '$app/state';
	import { safeRedirect } from '$lib/nav';
```

```ts
			await auth.login(email, password);
			await goto(safeRedirect(page.url.searchParams.get('redirect')));
```

- [ ] **Step 7: 타입체크**

Run: `cd frontend && npm run check`
Expected: 0 errors

- [ ] **Step 8: 커밋**

```bash
git add frontend/src/lib/nav.ts frontend/src/lib/nav.test.ts frontend/src/routes/+layout.svelte frontend/src/routes/login/+page.svelte
git commit -m "feat: preserve deep links through login and match public routes by prefix"
```

---

## Task 17: `authRequest` 래퍼와 전역 401 처리

**Files:**
- Modify: `frontend/src/lib/api/client.ts`
- Modify: `frontend/src/lib/stores/auth.svelte.ts`
- Test: `frontend/src/lib/stores/auth.svelte.test.ts`

Phase 1 이월: `request()`의 `token`이 선택 파라미터라 인증이 필요한 호출부마다 `{ token: auth.token }`를 손으로 붙여야 한다. 이번 Phase에서만 수십 곳이 생기고, 하나라도 빠뜨리면 조용히 미인증 요청이 나가 401이 뜬다. 컴파일 타임 신호가 없다.

- [ ] **Step 1: 실패하는 테스트 작성**

`frontend/src/lib/stores/auth.svelte.test.ts`의 기존 `describe` 아래에 추가한다 (상단 import에 `authRequest`를 더한다):

```ts
import { afterEach, describe, expect, it, vi } from 'vitest';
import { auth, authRequest } from './auth.svelte';
```

```ts
describe('authRequest', () => {
	afterEach(() => {
		auth.token = null;
		auth.user = null;
		auth.onUnauthorized = null;
		vi.unstubAllGlobals();
	});

	it('sends the stored token without the caller passing it', async () => {
		vi.stubGlobal('localStorage', createLocalStorageStub());
		const fetchMock = vi
			.fn()
			.mockResolvedValue(
				new Response(JSON.stringify({ ok: true }), {
					status: 200,
					headers: { 'Content-Type': 'application/json' }
				})
			);
		auth.token = 'live-token';

		await authRequest('/api/v1/trips', { fetchImpl: fetchMock });

		const [, init] = fetchMock.mock.calls[0];
		expect(init.headers.Authorization).toBe('Bearer live-token');
	});

	it('clears the session and calls onUnauthorized on 401', async () => {
		const storage = createLocalStorageStub({ 'skon.token': 'expired' });
		vi.stubGlobal('localStorage', storage);
		vi.stubGlobal(
			'fetch',
			vi.fn().mockResolvedValue(
				new Response(JSON.stringify({ error: { code: 'TOKEN_EXPIRED', message: '만료' } }), {
					status: 401,
					headers: { 'Content-Type': 'application/json' }
				})
			)
		);
		const onUnauthorized = vi.fn();
		auth.token = 'expired';
		auth.onUnauthorized = onUnauthorized;

		await expect(authRequest('/api/v1/trips')).rejects.toMatchObject({ status: 401 });

		expect(auth.token).toBeNull();
		expect(auth.user).toBeNull();
		expect(onUnauthorized).toHaveBeenCalledTimes(1);
	});

	it('leaves the session alone for non-401 failures', async () => {
		vi.stubGlobal('localStorage', createLocalStorageStub());
		vi.stubGlobal(
			'fetch',
			vi.fn().mockResolvedValue(
				new Response(JSON.stringify({ error: { code: 'TRIP_NOT_FOUND', message: '없음' } }), {
					status: 404,
					headers: { 'Content-Type': 'application/json' }
				})
			)
		);
		const onUnauthorized = vi.fn();
		auth.token = 'live-token';
		auth.onUnauthorized = onUnauthorized;

		await expect(authRequest('/api/v1/trips/1')).rejects.toMatchObject({ status: 404 });

		expect(auth.token).toBe('live-token');
		expect(onUnauthorized).not.toHaveBeenCalled();
	});
});
```

- [ ] **Step 2: 실패 확인**

Run: `cd frontend && npm test`
Expected: FAIL — `authRequest` is not exported

- [ ] **Step 3: `RequestOptions`를 export**

`frontend/src/lib/api/client.ts`의 `interface RequestOptions`를 `export interface RequestOptions`로 바꾼다.

- [ ] **Step 4: 구현**

`frontend/src/lib/stores/auth.svelte.ts`를 다음으로 교체한다:

```ts
import { ApiError, request, type RequestOptions } from '$lib/api/client';
import type { LoginResponse, User } from '$lib/api/types';

const TOKEN_KEY = 'skon.token';

class AuthStore {
	token = $state<string | null>(null);
	user = $state<User | null>(null);
	loading = $state(true);

	/**
	 * 세션이 끊겼을 때 화면을 정리할 콜백. +layout.svelte가 마운트 시 주입한다.
	 * 여기서 $app/navigation을 직접 import하면 vitest가 이 모듈을 못 불러온다.
	 */
	onUnauthorized: (() => void) | null = null;

	async restore(): Promise<void> {
		this.loading = true;
		const stored = localStorage.getItem(TOKEN_KEY);
		if (!stored) {
			this.loading = false;
			return;
		}
		this.token = stored;
		try {
			this.user = await request<User>('/api/v1/auth/me', { token: stored });
		} catch {
			this.clear();
		}
		this.loading = false;
	}

	async login(email: string, password: string): Promise<void> {
		this.loading = true;
		try {
			const result = await request<LoginResponse>('/api/v1/auth/login', {
				method: 'POST',
				body: { email, password }
			});
			this.token = result.access_token;
			this.user = result.user;
			localStorage.setItem(TOKEN_KEY, result.access_token);
		} finally {
			this.loading = false;
		}
	}

	clear(): void {
		this.token = null;
		this.user = null;
		localStorage.removeItem(TOKEN_KEY);
	}
}

export const auth = new AuthStore();

/**
 * 인증이 필요한 모든 호출은 이걸 쓴다. raw `request`는 미인증 호출(login)과
 * 토큰을 명시적으로 넘기는 곳(restore)에서만 쓴다.
 *
 * JWT는 8시간 만료이고 refresh 토큰이 없다. 세션 중간에 만료되면 여기서 정리하지
 * 않는 한 헤더에 이름이 계속 보이고, SPA 내비게이션은 onMount를 다시 태우지 않아
 * 전체 새로고침 전까지 자가 복구가 안 된다.
 */
export async function authRequest<T>(
	path: string,
	options: Omit<RequestOptions, 'token'> = {}
): Promise<T> {
	try {
		return await request<T>(path, { ...options, token: auth.token });
	} catch (error) {
		if (error instanceof ApiError && error.status === 401) {
			auth.clear();
			auth.onUnauthorized?.();
		}
		throw error;
	}
}
```

- [ ] **Step 5: 통과 확인**

Run: `cd frontend && npm test`
Expected: 기존 9건 + 신규 3건 통과

- [ ] **Step 6: 커밋**

```bash
git add frontend/src/lib/api/client.ts frontend/src/lib/stores/auth.svelte.ts frontend/src/lib/stores/auth.svelte.test.ts
git commit -m "feat: add authRequest wrapper with global 401 handling"
```

---

## Task 18: 포맷터와 상태 라벨

**Files:**
- Create: `frontend/src/lib/format.ts`
- Create: `frontend/src/lib/format.test.ts`
- Create: `frontend/src/lib/trip-status.ts`

- [ ] **Step 1: 실패하는 테스트 작성**

`frontend/src/lib/format.test.ts`:

```ts
import { describe, expect, it } from 'vitest';
import { formatDate, formatDateRange, formatDateTime, formatKrw, tripLength } from './format';

describe('formatDate', () => {
	it('renders an ISO date as dotted numbers', () => {
		expect(formatDate('2026-08-17')).toBe('2026.08.17');
	});

	it('returns an empty string for junk', () => {
		expect(formatDate('')).toBe('');
	});
});

describe('formatDateRange', () => {
	it('collapses the shared year and month', () => {
		expect(formatDateRange('2026-08-17', '2026-08-19')).toBe('2026.08.17 – 19');
	});

	it('collapses only the year when months differ', () => {
		expect(formatDateRange('2026-08-30', '2026-09-02')).toBe('2026.08.30 – 09.02');
	});

	it('keeps both years when they differ', () => {
		expect(formatDateRange('2026-12-30', '2027-01-02')).toBe('2026.12.30 – 2027.01.02');
	});
});

describe('formatDateTime', () => {
	// 타임존을 Asia/Seoul로 고정했으므로 실행 머신의 TZ와 무관하게 같은 값이 나온다.
	it('renders an instant in KST', () => {
		expect(formatDateTime('2026-08-17T05:30:00Z')).toBe('2026.08.17 14:30');
	});

	it('returns an empty string for an unparsable value', () => {
		expect(formatDateTime('nope')).toBe('');
	});
});

describe('formatKrw', () => {
	it('accepts the decimal string the API sends', () => {
		expect(formatKrw('1200000.00')).toBe('1,200,000원');
	});

	it('accepts a number', () => {
		expect(formatKrw(4500)).toBe('4,500원');
	});

	it('falls back for non-numeric input', () => {
		expect(formatKrw('abc')).toBe('-');
	});
});

describe('tripLength', () => {
	it('labels a same-day trip', () => {
		expect(tripLength('2026-08-17', '2026-08-17')).toBe('당일');
	});

	it('counts nights and days', () => {
		expect(tripLength('2026-08-17', '2026-08-19')).toBe('2박 3일');
	});
});
```

- [ ] **Step 2: 실패 확인**

Run: `cd frontend && npm test`
Expected: FAIL — `Failed to resolve import "./format"`

- [ ] **Step 3: 구현**

`frontend/src/lib/format.ts`:

```ts
/**
 * 날짜 문자열(YYYY-MM-DD)은 Date로 파싱하지 않는다. `new Date('2026-08-17')`은 UTC
 * 자정으로 해석돼 음수 오프셋 타임존에서 하루 밀린다. 문자열을 그대로 자른다.
 */
function parts(isoDate: string): [string, string, string] | null {
	const [year, month, day] = isoDate.split('-');
	return year && month && day ? [year, month, day] : null;
}

/** 시각은 KST로 고정 렌더한다 — 실행 머신의 TZ에 따라 값이 달라지면 안 된다. */
const KST_DATETIME = new Intl.DateTimeFormat('sv-SE', {
	timeZone: 'Asia/Seoul',
	year: 'numeric',
	month: '2-digit',
	day: '2-digit',
	hour: '2-digit',
	minute: '2-digit',
	hour12: false
});

export function formatDate(isoDate: string): string {
	const value = parts(isoDate);
	return value ? value.join('.') : '';
}

export function formatDateRange(startDate: string, endDate: string): string {
	const start = parts(startDate);
	const end = parts(endDate);
	if (!start || !end) return '';
	const [sy, sm, sd] = start;
	const [ey, em, ed] = end;
	if (sy === ey && sm === em) return `${sy}.${sm}.${sd} – ${ed}`;
	if (sy === ey) return `${sy}.${sm}.${sd} – ${em}.${ed}`;
	return `${sy}.${sm}.${sd} – ${ey}.${em}.${ed}`;
}

export function formatDateTime(iso: string): string {
	const parsed = new Date(iso);
	if (Number.isNaN(parsed.getTime())) return '';
	return KST_DATETIME.format(parsed).replaceAll('-', '.');
}

/** 금액은 API가 Decimal을 문자열로 보낸다 ("450000.00"). */
export function formatKrw(amount: string | number): string {
	const value = typeof amount === 'string' ? Number(amount) : amount;
	if (!Number.isFinite(value)) return '-';
	return `${new Intl.NumberFormat('ko-KR').format(Math.round(value))}원`;
}

export function tripLength(startDate: string, endDate: string): string {
	const nights = Math.round(
		(Date.parse(`${endDate}T00:00:00Z`) - Date.parse(`${startDate}T00:00:00Z`)) / 86_400_000
	);
	if (!Number.isFinite(nights) || nights <= 0) return '당일';
	return `${nights}박 ${nights + 1}일`;
}
```

`frontend/src/lib/trip-status.ts`:

```ts
import type { TripStatus } from '$lib/api/types';

export const TRIP_STATUS_LABELS: Record<TripStatus, string> = {
	DRAFT: '임시저장',
	SUBMITTED: '승인대기',
	APPROVED: '승인',
	REJECTED: '반려',
	COMPLETED: '완료',
	SETTLED: '정산완료'
};

/** Badge.svelte의 tone과 그대로 맞춘다. */
export const TRIP_STATUS_TONES: Record<TripStatus, 'neutral' | 'primary' | 'success' | 'danger'> = {
	DRAFT: 'neutral',
	SUBMITTED: 'primary',
	APPROVED: 'success',
	REJECTED: 'danger',
	COMPLETED: 'success',
	SETTLED: 'neutral'
};

/** 목록 필터의 상태 드롭다운 순서 — spec 5.4의 전이 순서를 따른다. */
export const TRIP_STATUS_ORDER: TripStatus[] = [
	'DRAFT',
	'SUBMITTED',
	'APPROVED',
	'REJECTED',
	'COMPLETED',
	'SETTLED'
];
```

- [ ] **Step 4: 통과 확인**

Run: `cd frontend && npm test`
Expected: format.test.ts 10건 통과

- [ ] **Step 5: 커밋**

```bash
git add frontend/src/lib/format.ts frontend/src/lib/format.test.ts frontend/src/lib/trip-status.ts
git commit -m "feat: add date and currency formatters with trip status labels"
```

---

## Task 19: API 타입과 호출부

**Files:**
- Modify: `frontend/src/lib/api/types.ts`
- Create: `frontend/src/lib/api/trips.ts`
- Create: `frontend/src/lib/api/codes.ts`
- Create: `frontend/src/lib/api/centers.ts`
- Create: `frontend/src/lib/api/notifications.ts`

호출부에 테스트를 붙이지 않는다 — `authRequest`와 `request`가 이미 덮여 있고, 이 파일들은 경로 문자열과 타입뿐이라 테스트가 구현을 복사하는 꼴이 된다. 대신 `npm run check`가 타입 오류를 잡는다.

- [ ] **Step 1: 타입 추가**

`frontend/src/lib/api/types.ts` 끝에 추가:

```ts
export type TripStatus =
	| 'DRAFT'
	| 'SUBMITTED'
	| 'APPROVED'
	| 'REJECTED'
	| 'COMPLETED'
	| 'SETTLED';

export type ActivityAction =
	| 'CREATED'
	| 'UPDATED'
	| 'SUBMITTED'
	| 'APPROVED'
	| 'REJECTED'
	| 'COMPLETED'
	| 'SETTLED';

export interface Page<T> {
	items: T[];
	total: number;
	page: number;
	size: number;
}

export interface TripListItem {
	id: number;
	trip_no: string;
	title: string;
	city: string;
	country_code: string;
	destination_type_code: string;
	purpose_code: string;
	start_date: string;
	end_date: string;
	status: TripStatus;
	estimated_cost: string;
	user_id: number;
	user_name: string;
	approver_id: number | null;
	approver_name: string | null;
}

export interface TripDetail extends TripListItem {
	purpose_detail: string;
	transport_code: string;
	accommodation_code: string;
	cost_center_code: string;
	cost_center_name: string | null;
	submitted_at: string | null;
	approved_at: string | null;
	reject_reason: string | null;
	created_at: string;
	updated_at: string;
}

export interface TimelineEntry {
	id: number;
	action: ActivityAction;
	from_status: string | null;
	to_status: string | null;
	memo: string | null;
	actor_id: number;
	actor_name: string;
	created_at: string;
}

/** 신청·수정 폼이 다루는 필드. 수정은 이 타입의 부분집합을 보낸다. */
export interface TripInput {
	title: string;
	purpose_code: string;
	purpose_detail: string;
	destination_type_code: string;
	country_code: string;
	city: string;
	start_date: string;
	end_date: string;
	transport_code: string;
	accommodation_code: string;
	cost_center_code: string;
	estimated_cost: string;
}

export interface CodeItem {
	code: string;
	name: string;
	sort_order: number;
	extra: Record<string, unknown>;
}

export interface CodeGroup {
	group_code: string;
	name: string;
	description: string | null;
	codes: CodeItem[];
}

export interface Center {
	code: string;
	name: string;
	department_id: number | null;
}

export type NotificationType =
	| 'TRIP_SUBMITTED'
	| 'TRIP_APPROVED'
	| 'TRIP_REJECTED'
	| 'EXPENSE_SUBMITTED'
	| 'EXPENSE_APPROVED'
	| 'EXPENSE_REJECTED';

export interface NotificationItem {
	id: number;
	type: NotificationType;
	title: string;
	body: string;
	link_url: string | null;
	is_read: boolean;
	created_at: string;
}

export interface NotificationPage extends Page<NotificationItem> {
	unread: number;
}
```

- [ ] **Step 2: 출장 호출부 작성**

`frontend/src/lib/api/trips.ts`:

```ts
import { authRequest } from '$lib/stores/auth.svelte';
import type { Page, TimelineEntry, TripDetail, TripInput, TripListItem, TripStatus } from './types';

export interface TripQuery {
	scope?: 'mine' | 'approvals' | 'all';
	status?: TripStatus[];
	destination_type_code?: string;
	country_code?: string;
	q?: string;
	start_date_from?: string;
	start_date_to?: string;
	page?: number;
	size?: number;
}

export function tripQueryString(query: TripQuery): string {
	const params = new URLSearchParams();
	for (const [key, value] of Object.entries(query)) {
		if (value === undefined || value === null || value === '') continue;
		// status는 반복 파라미터다 (?status=A&status=B). 백엔드가 list로 받는다.
		if (Array.isArray(value)) value.forEach((item) => params.append(key, String(item)));
		else params.set(key, String(value));
	}
	const search = params.toString();
	return search ? `?${search}` : '';
}

export function listTrips(query: TripQuery = {}): Promise<Page<TripListItem>> {
	return authRequest<Page<TripListItem>>(`/api/v1/trips${tripQueryString(query)}`);
}

export function getTrip(id: number): Promise<TripDetail> {
	return authRequest<TripDetail>(`/api/v1/trips/${id}`);
}

export function createTrip(body: TripInput): Promise<TripDetail> {
	return authRequest<TripDetail>('/api/v1/trips', { method: 'POST', body });
}

export function updateTrip(id: number, body: Partial<TripInput>): Promise<TripDetail> {
	return authRequest<TripDetail>(`/api/v1/trips/${id}`, { method: 'PATCH', body });
}

export function deleteTrip(id: number): Promise<void> {
	return authRequest<void>(`/api/v1/trips/${id}`, { method: 'DELETE' });
}

export function submitTrip(id: number): Promise<TripDetail> {
	return authRequest<TripDetail>(`/api/v1/trips/${id}/submit`, { method: 'POST' });
}

export function approveTrip(id: number): Promise<TripDetail> {
	return authRequest<TripDetail>(`/api/v1/trips/${id}/approve`, { method: 'POST' });
}

export function rejectTrip(id: number, reason: string): Promise<TripDetail> {
	return authRequest<TripDetail>(`/api/v1/trips/${id}/reject`, {
		method: 'POST',
		body: { reason }
	});
}

export function reopenTrip(id: number): Promise<TripDetail> {
	return authRequest<TripDetail>(`/api/v1/trips/${id}/reopen`, { method: 'POST' });
}

export function completeTrip(id: number): Promise<TripDetail> {
	return authRequest<TripDetail>(`/api/v1/trips/${id}/complete`, { method: 'POST' });
}

export function getTimeline(id: number): Promise<TimelineEntry[]> {
	return authRequest<TimelineEntry[]>(`/api/v1/trips/${id}/timeline`);
}
```

- [ ] **Step 3: 나머지 호출부 작성**

`frontend/src/lib/api/codes.ts`:

```ts
import { authRequest } from '$lib/stores/auth.svelte';
import type { CodeGroup } from './types';

export function listCodeGroups(): Promise<CodeGroup[]> {
	return authRequest<CodeGroup[]>('/api/v1/codes');
}

export function getCodeGroup(groupCode: string): Promise<CodeGroup> {
	return authRequest<CodeGroup>(`/api/v1/codes/${groupCode}`);
}

/** 폼이 쓰기 좋게 group_code를 키로 하는 맵으로 접는다. */
export function byGroupCode(groups: CodeGroup[]): Record<string, CodeGroup> {
	return Object.fromEntries(groups.map((group) => [group.group_code, group]));
}
```

`frontend/src/lib/api/centers.ts`:

```ts
import { authRequest } from '$lib/stores/auth.svelte';
import type { Center } from './types';

export function listCostCenters(): Promise<Center[]> {
	return authRequest<Center[]>('/api/v1/cost-centers');
}

export function listFundCenters(): Promise<Center[]> {
	return authRequest<Center[]>('/api/v1/fund-centers');
}
```

`frontend/src/lib/api/notifications.ts`:

```ts
import { authRequest } from '$lib/stores/auth.svelte';
import type { NotificationItem, NotificationPage } from './types';

export function listNotifications(
	options: { unread_only?: boolean; page?: number; size?: number } = {}
): Promise<NotificationPage> {
	const params = new URLSearchParams();
	if (options.unread_only) params.set('unread_only', 'true');
	if (options.page) params.set('page', String(options.page));
	if (options.size) params.set('size', String(options.size));
	const search = params.toString();
	return authRequest<NotificationPage>(`/api/v1/notifications${search ? `?${search}` : ''}`);
}

export function markNotificationRead(id: number): Promise<NotificationItem> {
	return authRequest<NotificationItem>(`/api/v1/notifications/${id}/read`, { method: 'POST' });
}
```

- [ ] **Step 4: 타입체크**

Run: `cd frontend && npm run check`
Expected: 0 errors

- [ ] **Step 5: 커밋**

```bash
git add frontend/src/lib/api/
git commit -m "feat: add trip, code, center and notification API clients"
```

---

## Task 20: 공용 폼·표시 컴포넌트

**Files:**
- Create: `frontend/src/lib/components/Select.svelte`
- Create: `frontend/src/lib/components/Textarea.svelte`
- Create: `frontend/src/lib/components/EmptyState.svelte`
- Create: `frontend/src/lib/components/StatusBadge.svelte`

**`text-body` 클래스를 쓰지 않는다.** `--color-body` 때문에 Tailwind가 이걸 색상 유틸리티로 생성한다. 본문 타이포는 `text-body-md` / `text-body-sm`으로 명시한다. 에러가 나지 않고 조용히 틀린다.

**고유 id는 `$props.id()`를 쓴다.** 운영은 평문 HTTP로 서빙되므로 `crypto.randomUUID()`는 존재하지 않아 페이지 전체가 렌더에 실패한다. 로컬에서는 멀쩡해 보여 발견이 늦다.

- [ ] **Step 1: `Select.svelte` 작성**

`TextInput.svelte`와 같은 구조·같은 클래스를 쓴다.

```svelte
<script lang="ts">
	let {
		label,
		value = $bindable(''),
		options,
		placeholder = '선택하세요',
		error = '',
		id,
		name,
		disabled = false
	}: {
		label: string;
		value?: string;
		options: { value: string; label: string }[];
		placeholder?: string;
		error?: string;
		id?: string;
		name?: string;
		disabled?: boolean;
	} = $props();

	const fallbackId = $props.id();
	const selectId = $derived(id ?? fallbackId);
	const errorId = $derived(`${selectId}-error`);
</script>

<div class="flex flex-col gap-2">
	<label for={selectId} class="text-caption text-muted">{label}</label>
	<select
		id={selectId}
		{name}
		{disabled}
		bind:value
		aria-invalid={!!error}
		aria-describedby={error ? errorId : undefined}
		class="h-14 rounded-sm border bg-canvas px-3 text-body-md text-ink outline-none focus:border-2 focus:border-ink disabled:text-muted-soft {error
			? 'border-error'
			: 'border-hairline'}"
	>
		<option value="" disabled>{placeholder}</option>
		{#each options as option (option.value)}
			<option value={option.value}>{option.label}</option>
		{/each}
	</select>
	{#if error}
		<p id={errorId} class="text-caption-sm text-error">{error}</p>
	{/if}
</div>
```

- [ ] **Step 2: `Textarea.svelte` 작성**

```svelte
<script lang="ts">
	let {
		label,
		value = $bindable(''),
		placeholder = '',
		rows = 4,
		error = '',
		id,
		name
	}: {
		label: string;
		value?: string;
		placeholder?: string;
		rows?: number;
		error?: string;
		id?: string;
		name?: string;
	} = $props();

	const fallbackId = $props.id();
	const areaId = $derived(id ?? fallbackId);
	const errorId = $derived(`${areaId}-error`);
</script>

<div class="flex flex-col gap-2">
	<label for={areaId} class="text-caption text-muted">{label}</label>
	<textarea
		id={areaId}
		{name}
		{rows}
		{placeholder}
		bind:value
		aria-invalid={!!error}
		aria-describedby={error ? errorId : undefined}
		class="rounded-sm border bg-canvas p-3 text-body-md text-ink outline-none focus:border-2 focus:border-ink {error
			? 'border-error'
			: 'border-hairline'}"
	></textarea>
	{#if error}
		<p id={errorId} class="text-caption-sm text-error">{error}</p>
	{/if}
</div>
```

- [ ] **Step 3: `EmptyState.svelte` 작성**

```svelte
<script lang="ts">
	import type { Snippet } from 'svelte';

	let {
		title,
		description = '',
		action
	}: { title: string; description?: string; action?: Snippet } = $props();
</script>

<div class="flex flex-col items-center gap-3 rounded-md border border-hairline py-16 text-center">
	<p class="text-title-md text-ink">{title}</p>
	{#if description}
		<p class="text-body-sm text-muted">{description}</p>
	{/if}
	{#if action}
		<div class="mt-2">{@render action()}</div>
	{/if}
</div>
```

- [ ] **Step 4: `StatusBadge.svelte` 작성**

```svelte
<script lang="ts">
	import Badge from '$lib/components/Badge.svelte';
	import { TRIP_STATUS_LABELS, TRIP_STATUS_TONES } from '$lib/trip-status';
	import type { TripStatus } from '$lib/api/types';

	let { status }: { status: TripStatus } = $props();
</script>

<Badge tone={TRIP_STATUS_TONES[status]}>{TRIP_STATUS_LABELS[status]}</Badge>
```

- [ ] **Step 5: 타입체크**

Run: `cd frontend && npm run check`
Expected: 0 errors

- [ ] **Step 6: 커밋**

```bash
git add frontend/src/lib/components/Select.svelte frontend/src/lib/components/Textarea.svelte frontend/src/lib/components/EmptyState.svelte frontend/src/lib/components/StatusBadge.svelte
git commit -m "feat: add select, textarea, empty state and status badge components"
```

---

## Task 21: 출장 카드와 필터 바

**Files:**
- Create: `frontend/src/lib/components/TripCard.svelte`
- Create: `frontend/src/lib/components/FilterBar.svelte`

DESIGN.md 매핑: `property-card` → 출장 카드(상태 뱃지 floating), `search-bar-pill` + `search-orb` → 목록 상단 필터.

- [ ] **Step 1: `TripCard.svelte` 작성**

```svelte
<script lang="ts">
	import Card from '$lib/components/Card.svelte';
	import StatusBadge from '$lib/components/StatusBadge.svelte';
	import { formatDateRange, formatKrw, tripLength } from '$lib/format';
	import type { TripListItem } from '$lib/api/types';

	let { trip, showOwner = false }: { trip: TripListItem; showOwner?: boolean } = $props();
</script>

<a href="/trips/{trip.id}" class="block">
	<Card hoverable>
		<div class="flex items-start justify-between gap-4">
			<div class="min-w-0">
				<p class="text-caption text-muted">{trip.trip_no}</p>
				<p class="mt-1 truncate text-title-md text-ink">{trip.title}</p>
			</div>
			<StatusBadge status={trip.status} />
		</div>

		<p class="mt-4 text-body-sm text-muted">
			{trip.city} · {trip.destination_type_code === 'OVERSEAS' ? '해외' : '국내'} · {tripLength(
				trip.start_date,
				trip.end_date
			)}
		</p>
		<p class="mt-1 text-body-sm text-muted">
			{formatDateRange(trip.start_date, trip.end_date)}
		</p>

		<div class="mt-4 flex items-end justify-between">
			{#if showOwner}
				<p class="text-body-sm text-muted">{trip.user_name}</p>
			{:else}
				<p class="text-body-sm text-muted">
					{trip.approver_name ? `결재자 ${trip.approver_name}` : '결재자 미지정'}
				</p>
			{/if}
			<p class="text-title-md text-ink">{formatKrw(trip.estimated_cost)}</p>
		</div>
	</Card>
</a>
```

- [ ] **Step 2: `FilterBar.svelte` 작성**

`search-bar-pill`: 흰 배경, 완전 라운드, 세로 hairline으로 나뉜 세그먼트, 우측 SK레드 orb.

```svelte
<script lang="ts">
	import { TRIP_STATUS_LABELS, TRIP_STATUS_ORDER } from '$lib/trip-status';
	import type { TripStatus } from '$lib/api/types';

	let {
		q = $bindable(''),
		startDateFrom = $bindable(''),
		status = $bindable<TripStatus | ''>(''),
		onsearch
	}: {
		q?: string;
		startDateFrom?: string;
		status?: TripStatus | '';
		onsearch: () => void;
	} = $props();

	const qId = $props.id();
	const dateId = $props.id();
	const statusId = $props.id();

	function handleSubmit(event: SubmitEvent): void {
		event.preventDefault();
		onsearch();
	}
</script>

<form onsubmit={handleSubmit}>
	<div
		class="flex h-16 items-center rounded-full border border-hairline bg-canvas pr-2 shadow-float"
	>
		<div class="flex flex-1 flex-col justify-center px-6">
			<label for={qId} class="text-badge tracking-wide text-muted uppercase">어디로</label>
			<input
				id={qId}
				bind:value={q}
				placeholder="도시 · 제목 · 출장번호"
				class="bg-transparent text-caption text-ink outline-none placeholder:text-muted-soft"
			/>
		</div>

		<div class="h-8 w-px bg-hairline"></div>

		<div class="flex flex-1 flex-col justify-center px-6">
			<label for={dateId} class="text-badge tracking-wide text-muted uppercase">언제부터</label>
			<input
				id={dateId}
				type="date"
				bind:value={startDateFrom}
				class="bg-transparent text-caption text-ink outline-none"
			/>
		</div>

		<div class="h-8 w-px bg-hairline"></div>

		<div class="flex flex-1 flex-col justify-center px-6">
			<label for={statusId} class="text-badge tracking-wide text-muted uppercase">상태</label>
			<select
				id={statusId}
				bind:value={status}
				class="bg-transparent text-caption text-ink outline-none"
			>
				<option value="">전체</option>
				{#each TRIP_STATUS_ORDER as value (value)}
					<option {value}>{TRIP_STATUS_LABELS[value]}</option>
				{/each}
			</select>
		</div>

		<button
			type="submit"
			aria-label="검색"
			class="flex h-12 w-12 shrink-0 items-center justify-center rounded-full bg-primary text-white hover:bg-primary-active"
		>
			<svg viewBox="0 0 24 24" class="h-5 w-5" fill="none" stroke="currentColor" stroke-width="2.5">
				<circle cx="11" cy="11" r="7" />
				<path d="M20 20l-3.5-3.5" stroke-linecap="round" />
			</svg>
		</button>
	</div>
</form>
```

- [ ] **Step 3: 타입체크**

Run: `cd frontend && npm run check`
Expected: 0 errors

- [ ] **Step 4: 커밋**

```bash
git add frontend/src/lib/components/TripCard.svelte frontend/src/lib/components/FilterBar.svelte
git commit -m "feat: add trip card and pill filter bar"
```

---

## Task 22: 출장 목록 화면

**Files:**
- Create: `frontend/src/routes/trips/+page.svelte`

필터 상태는 URL 쿼리에 둔다 — 링크를 공유하면 같은 화면이 열려야 한다. `+page.ts` load 함수를 쓰지 않는다: load는 레이아웃 컴포넌트보다 먼저 실행되므로 `auth.restore()`가 끝나기 전에 토큰 없는 요청이 나간다. 데이터는 컴포넌트에서 받는다.

- [ ] **Step 1: 화면 작성**

```svelte
<script lang="ts">
	import { goto } from '$app/navigation';
	import { page } from '$app/state';
	import { ApiError } from '$lib/api/client';
	import { listTrips, type TripQuery } from '$lib/api/trips';
	import type { Page, TripListItem, TripStatus } from '$lib/api/types';
	import Button from '$lib/components/Button.svelte';
	import EmptyState from '$lib/components/EmptyState.svelte';
	import FilterBar from '$lib/components/FilterBar.svelte';
	import TripCard from '$lib/components/TripCard.svelte';

	const SIZE = 12;

	let result = $state<Page<TripListItem> | null>(null);
	let loading = $state(true);
	let errorMessage = $state('');

	let q = $state(page.url.searchParams.get('q') ?? '');
	let startDateFrom = $state(page.url.searchParams.get('start_date_from') ?? '');
	let status = $state<TripStatus | ''>((page.url.searchParams.get('status') as TripStatus) ?? '');

	const currentPage = $derived(Number(page.url.searchParams.get('page') ?? '1'));
	const totalPages = $derived(result ? Math.max(1, Math.ceil(result.total / SIZE)) : 1);

	// page.url.search만 의존성으로 읽는다. 아래에서 쓰는 result/loading은 이 effect가
	// 읽지 않으므로 대입해도 다시 트리거되지 않는다.
	$effect(() => {
		const search = page.url.search;
		void load(new URLSearchParams(search));
	});

	async function load(params: URLSearchParams): Promise<void> {
		loading = true;
		errorMessage = '';
		const query: TripQuery = { page: Number(params.get('page') ?? '1'), size: SIZE };
		if (params.get('q')) query.q = params.get('q') as string;
		if (params.get('start_date_from')) query.start_date_from = params.get('start_date_from') as string;
		if (params.get('status')) query.status = [params.get('status') as TripStatus];
		try {
			result = await listTrips(query);
		} catch (error) {
			errorMessage = error instanceof ApiError ? error.message : '목록을 불러오지 못했습니다';
		} finally {
			loading = false;
		}
	}

	function applyFilters(): void {
		const params = new URLSearchParams();
		if (q) params.set('q', q);
		if (startDateFrom) params.set('start_date_from', startDateFrom);
		if (status) params.set('status', status);
		goto(`/trips${params.toString() ? `?${params}` : ''}`);
	}

	function goToPage(next: number): void {
		const params = new URLSearchParams(page.url.searchParams);
		params.set('page', String(next));
		goto(`/trips?${params}`);
	}
</script>

<div class="flex items-center justify-between">
	<h1 class="text-display-xl">내 출장</h1>
	<Button onclick={() => goto('/trips/new')}>출장 신청</Button>
</div>

<div class="mt-6">
	<FilterBar bind:q bind:startDateFrom bind:status onsearch={applyFilters} />
</div>

{#if errorMessage}
	<p class="mt-8 text-body-sm text-error" role="alert">{errorMessage}</p>
{:else if loading}
	<p class="mt-8 text-body-sm text-muted">불러오는 중…</p>
{:else if result && result.items.length > 0}
	<p class="mt-8 text-body-sm text-muted">전체 {result.total}건</p>
	<div class="mt-4 grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3">
		{#each result.items as trip (trip.id)}
			<TripCard {trip} />
		{/each}
	</div>

	{#if totalPages > 1}
		<div class="mt-8 flex items-center justify-center gap-4">
			<Button
				variant="secondary"
				disabled={currentPage <= 1}
				onclick={() => goToPage(currentPage - 1)}>이전</Button
			>
			<span class="text-body-sm text-muted">{currentPage} / {totalPages}</span>
			<Button
				variant="secondary"
				disabled={currentPage >= totalPages}
				onclick={() => goToPage(currentPage + 1)}>다음</Button
			>
		</div>
	{/if}
{:else}
	<div class="mt-8">
		<EmptyState title="출장이 없습니다" description="조건을 바꾸거나 새 출장을 신청해 보세요.">
			{#snippet action()}
				<Button onclick={() => goto('/trips/new')}>출장 신청</Button>
			{/snippet}
		</EmptyState>
	</div>
{/if}
```

- [ ] **Step 2: 타입체크**

Run: `cd frontend && npm run check`
Expected: 0 errors

- [ ] **Step 3: 실행 확인**

백엔드(`cd backend && uv run uvicorn app.main:app --reload --port 8000`)와 프론트(`cd frontend && npm run dev`)를 띄우고 `http://localhost:5173/trips`에서 확인한다.

- `user1@skon.example` / `skon1234!`로 로그인하면 출장 카드가 보인다
- 상태를 `승인대기`로 바꾸고 orb를 누르면 URL이 `?status=SUBMITTED`가 되고 목록이 줄어든다
- 브라우저 새로고침 후에도 같은 필터가 유지된다
- 카드를 누르면 `/trips/<id>`로 이동한다 (아직 화면이 없어 404 — Task 24에서 만든다)

- [ ] **Step 4: 커밋**

```bash
git add frontend/src/routes/trips/+page.svelte
git commit -m "feat: add trip list screen with URL-backed filters"
```

---

## Task 23: 출장 폼과 신청 화면

**Files:**
- Create: `frontend/src/lib/components/TripForm.svelte`
- Create: `frontend/src/routes/trips/new/+page.svelte`

**중복 제출 가드를 넣는다.** 버튼의 `disabled`만으로는 `form.requestSubmit()` 경로를 막지 못한다(실측 2회 요청). 출장 신청은 멱등하지 않아 중복 POST가 곧 중복 레코드다.

- [ ] **Step 1: `TripForm.svelte` 작성**

신청과 수정이 같은 폼을 쓴다. 폼은 값만 모아 `onsubmit`으로 올려보내고, 무엇을 할지(생성/수정/상신)는 화면이 정한다.

```svelte
<script lang="ts">
	import { onMount } from 'svelte';
	import { ApiError } from '$lib/api/client';
	import { listCostCenters } from '$lib/api/centers';
	import { byGroupCode, listCodeGroups } from '$lib/api/codes';
	import type { CodeGroup, TripInput } from '$lib/api/types';
	import Select from '$lib/components/Select.svelte';
	import TextInput from '$lib/components/TextInput.svelte';
	import Textarea from '$lib/components/Textarea.svelte';

	let {
		initial,
		disabled = false,
		onchange
	}: {
		initial: TripInput;
		disabled?: boolean;
		onchange: (values: TripInput) => void;
	} = $props();

	let values = $state<TripInput>({ ...initial });
	let groups = $state<Record<string, CodeGroup>>({});
	let costCenters = $state<{ value: string; label: string }[]>([]);
	let loadError = $state('');

	// 부모가 상신/저장 시점에 최신 값을 읽을 수 있게 매 변경을 올려보낸다.
	$effect(() => {
		onchange({ ...values });
	});

	onMount(async () => {
		try {
			const [codeGroups, centers] = await Promise.all([listCodeGroups(), listCostCenters()]);
			groups = byGroupCode(codeGroups);
			costCenters = centers.map((center) => ({
				value: center.code,
				label: `${center.code} · ${center.name}`
			}));
		} catch (error) {
			loadError = error instanceof ApiError ? error.message : '기준정보를 불러오지 못했습니다';
		}
	});

	function optionsOf(groupCode: string): { value: string; label: string }[] {
		return (groups[groupCode]?.codes ?? []).map((code) => ({
			value: code.code,
			label: code.name
		}));
	}
</script>

{#if loadError}
	<p class="text-body-sm text-error" role="alert">{loadError}</p>
{/if}

<div class="flex flex-col gap-6">
	<TextInput label="출장 제목" bind:value={values.title} placeholder="울산공장 품질점검" />

	<div class="grid grid-cols-1 gap-6 md:grid-cols-2">
		<Select label="출장 목적" bind:value={values.purpose_code} options={optionsOf('TRIP_PURPOSE')} />
		<Select
			label="국내 / 해외"
			bind:value={values.destination_type_code}
			options={optionsOf('DESTINATION_TYPE')}
		/>
	</div>

	<Textarea
		label="목적 상세"
		bind:value={values.purpose_detail}
		placeholder="무엇을 하러 가는지 구체적으로 적어주세요"
	/>

	<div class="grid grid-cols-1 gap-6 md:grid-cols-2">
		<Select label="국가" bind:value={values.country_code} options={optionsOf('COUNTRY')} />
		<TextInput label="도시" bind:value={values.city} placeholder="울산" />
	</div>

	<div class="grid grid-cols-1 gap-6 md:grid-cols-2">
		<TextInput label="시작일" type="date" bind:value={values.start_date} />
		<TextInput label="종료일" type="date" bind:value={values.end_date} />
	</div>

	<div class="grid grid-cols-1 gap-6 md:grid-cols-2">
		<Select label="이동수단" bind:value={values.transport_code} options={optionsOf('TRANSPORT')} />
		<Select label="숙박유형" bind:value={values.accommodation_code} options={optionsOf('ACCOMMODATION')} />
	</div>

	<div class="grid grid-cols-1 gap-6 md:grid-cols-2">
		<Select label="코스트센터" bind:value={values.cost_center_code} options={costCenters} />
		<TextInput label="예상 비용 (원)" type="number" bind:value={values.estimated_cost} />
	</div>
</div>
```

- [ ] **Step 2: 신청 화면 작성**

`frontend/src/routes/trips/new/+page.svelte`:

```svelte
<script lang="ts">
	import { goto } from '$app/navigation';
	import { ApiError } from '$lib/api/client';
	import { createTrip, submitTrip } from '$lib/api/trips';
	import type { TripInput } from '$lib/api/types';
	import Button from '$lib/components/Button.svelte';
	import TripForm from '$lib/components/TripForm.svelte';

	const EMPTY: TripInput = {
		title: '',
		purpose_code: '',
		purpose_detail: '',
		destination_type_code: '',
		country_code: '',
		city: '',
		start_date: '',
		end_date: '',
		transport_code: '',
		accommodation_code: '',
		cost_center_code: '',
		estimated_cost: ''
	};

	let values = $state<TripInput>({ ...EMPTY });
	let submitting = $state(false);
	let errorMessage = $state('');

	async function save(alsoSubmit: boolean): Promise<void> {
		// 버튼 disabled만으로는 requestSubmit 경로를 막지 못한다. 출장 신청은
		// 멱등하지 않아 중복 POST가 곧 중복 레코드다.
		if (submitting) return;
		submitting = true;
		errorMessage = '';
		try {
			const created = await createTrip(values);
			if (alsoSubmit) await submitTrip(created.id);
			await goto(`/trips/${created.id}`);
		} catch (error) {
			errorMessage = error instanceof ApiError ? error.message : '저장하지 못했습니다';
		} finally {
			submitting = false;
		}
	}
</script>

<h1 class="text-display-xl">출장 신청</h1>
<p class="mt-2 text-body-md text-muted">필수 항목을 채우고 임시저장하거나 바로 상신하세요.</p>

<div class="mt-8 max-w-[720px]">
	<TripForm initial={EMPTY} onchange={(next) => (values = next)} />

	{#if errorMessage}
		<p class="mt-6 text-body-sm text-error" role="alert">{errorMessage}</p>
	{/if}

	<div class="mt-8 flex gap-3">
		<Button variant="secondary" disabled={submitting} onclick={() => save(false)}>
			{submitting ? '저장 중…' : '임시저장'}
		</Button>
		<Button disabled={submitting} onclick={() => save(true)}>
			{submitting ? '처리 중…' : '저장 후 상신'}
		</Button>
	</div>
</div>
```

- [ ] **Step 3: 타입체크**

Run: `cd frontend && npm run check`
Expected: 0 errors

- [ ] **Step 4: 실행 확인**

`http://localhost:5173/trips/new`에서:

- 드롭다운에 공통코드 값(고객미팅·항공 등)과 코스트센터가 채워진다
- 종료일을 시작일보다 앞으로 두고 저장하면 `종료일은 시작일보다 빠를 수 없습니다`가 뜬다
- 정상 값으로 "저장 후 상신"하면 상세 화면(Task 24 이후)으로 이동한다
- "저장 후 상신"을 연타해도 출장이 하나만 생긴다

- [ ] **Step 5: 커밋**

```bash
git add frontend/src/lib/components/TripForm.svelte frontend/src/routes/trips/new/+page.svelte
git commit -m "feat: add trip form and new trip screen"
```

---

## Task 24: 출장 상세 · 타임라인 · 액션 카드

**Files:**
- Create: `frontend/src/lib/components/Timeline.svelte`
- Create: `frontend/src/routes/trips/[id]/+page.svelte`

DESIGN.md 매핑: 우측 sticky `reservation-card`가 액션 카드가 된다. 좌측 본문 ~64%, 우측 레일 ~32%.

- [ ] **Step 1: `Timeline.svelte` 작성**

```svelte
<script lang="ts">
	import { formatDateTime } from '$lib/format';
	import type { ActivityAction, TimelineEntry } from '$lib/api/types';

	let { entries }: { entries: TimelineEntry[] } = $props();

	const ACTION_LABELS: Record<ActivityAction, string> = {
		CREATED: '작성',
		UPDATED: '수정',
		SUBMITTED: '상신',
		APPROVED: '승인',
		REJECTED: '반려',
		COMPLETED: '완료',
		SETTLED: '정산완료'
	};
</script>

{#if entries.length === 0}
	<p class="text-body-sm text-muted">기록이 없습니다.</p>
{:else}
	<ol class="flex flex-col gap-4">
		{#each entries as entry (entry.id)}
			<li class="flex gap-4">
				<div class="mt-1.5 h-2 w-2 shrink-0 rounded-full bg-primary"></div>
				<div class="min-w-0">
					<p class="text-title-sm text-ink">
						{ACTION_LABELS[entry.action]} · {entry.actor_name}
					</p>
					<p class="mt-1 text-caption-sm text-muted">{formatDateTime(entry.created_at)}</p>
					{#if entry.memo}
						<p class="mt-1 text-body-sm text-muted">{entry.memo}</p>
					{/if}
				</div>
			</li>
		{/each}
	</ol>
{/if}
```

- [ ] **Step 2: 상세 화면 작성**

`frontend/src/routes/trips/[id]/+page.svelte`:

```svelte
<script lang="ts">
	import { goto } from '$app/navigation';
	import { page } from '$app/state';
	import { ApiError } from '$lib/api/client';
	import {
		approveTrip,
		completeTrip,
		deleteTrip,
		getTimeline,
		getTrip,
		rejectTrip,
		reopenTrip,
		submitTrip
	} from '$lib/api/trips';
	import type { TimelineEntry, TripDetail } from '$lib/api/types';
	import Button from '$lib/components/Button.svelte';
	import Card from '$lib/components/Card.svelte';
	import StatusBadge from '$lib/components/StatusBadge.svelte';
	import Textarea from '$lib/components/Textarea.svelte';
	import Timeline from '$lib/components/Timeline.svelte';
	import { formatDateRange, formatDateTime, formatKrw, tripLength } from '$lib/format';
	import { auth } from '$lib/stores/auth.svelte';

	let trip = $state<TripDetail | null>(null);
	let entries = $state<TimelineEntry[]>([]);
	let loading = $state(true);
	let errorMessage = $state('');
	let actionError = $state('');
	let busy = $state(false);
	let rejecting = $state(false);
	let rejectReason = $state('');

	const tripId = $derived(Number(page.params.id));
	const isOwner = $derived(!!trip && trip.user_id === auth.user?.id);
	const isApprover = $derived(!!trip && trip.approver_id === auth.user?.id);

	$effect(() => {
		const id = tripId;
		void load(id);
	});

	async function load(id: number): Promise<void> {
		loading = true;
		errorMessage = '';
		try {
			[trip, entries] = await Promise.all([getTrip(id), getTimeline(id)]);
		} catch (error) {
			errorMessage =
				error instanceof ApiError ? error.message : '출장을 불러오지 못했습니다';
		} finally {
			loading = false;
		}
	}

	async function act(action: (id: number) => Promise<TripDetail>): Promise<void> {
		if (busy) return;
		busy = true;
		actionError = '';
		try {
			trip = await action(tripId);
			entries = await getTimeline(tripId);
			rejecting = false;
			rejectReason = '';
		} catch (error) {
			actionError = error instanceof ApiError ? error.message : '처리하지 못했습니다';
		} finally {
			busy = false;
		}
	}

	async function removeTrip(): Promise<void> {
		if (busy) return;
		busy = true;
		actionError = '';
		try {
			await deleteTrip(tripId);
			await goto('/trips');
		} catch (error) {
			actionError = error instanceof ApiError ? error.message : '삭제하지 못했습니다';
			busy = false;
		}
	}
</script>

{#if loading}
	<p class="text-body-sm text-muted">불러오는 중…</p>
{:else if errorMessage}
	<p class="text-body-sm text-error" role="alert">{errorMessage}</p>
{:else if trip}
	<div class="grid grid-cols-1 gap-8 lg:grid-cols-[minmax(0,1fr)_360px]">
		<div>
			<p class="text-caption text-muted">{trip.trip_no}</p>
			<div class="mt-2 flex items-center gap-3">
				<h1 class="text-display-xl">{trip.title}</h1>
				<StatusBadge status={trip.status} />
			</div>

			{#if trip.status === 'REJECTED' && trip.reject_reason}
				<div class="mt-6 rounded-md border border-error px-4 py-3">
					<p class="text-caption text-error">반려 사유</p>
					<p class="mt-1 text-body-md text-ink">{trip.reject_reason}</p>
				</div>
			{/if}

			<dl class="mt-8 grid grid-cols-1 gap-x-8 gap-y-4 md:grid-cols-2">
				<div>
					<dt class="text-caption text-muted">기간</dt>
					<dd class="mt-1 text-body-md text-ink">
						{formatDateRange(trip.start_date, trip.end_date)} · {tripLength(
							trip.start_date,
							trip.end_date
						)}
					</dd>
				</div>
				<div>
					<dt class="text-caption text-muted">목적지</dt>
					<dd class="mt-1 text-body-md text-ink">{trip.country_code} · {trip.city}</dd>
				</div>
				<div>
					<dt class="text-caption text-muted">이동수단 / 숙박</dt>
					<dd class="mt-1 text-body-md text-ink">
						{trip.transport_code} · {trip.accommodation_code}
					</dd>
				</div>
				<div>
					<dt class="text-caption text-muted">코스트센터</dt>
					<dd class="mt-1 text-body-md text-ink">
						{trip.cost_center_code}{trip.cost_center_name ? ` · ${trip.cost_center_name}` : ''}
					</dd>
				</div>
				<div>
					<dt class="text-caption text-muted">신청자 / 결재자</dt>
					<dd class="mt-1 text-body-md text-ink">
						{trip.user_name} / {trip.approver_name ?? '미지정'}
					</dd>
				</div>
				<div>
					<dt class="text-caption text-muted">상신 / 승인 시각</dt>
					<dd class="mt-1 text-body-md text-ink">
						{trip.submitted_at ? formatDateTime(trip.submitted_at) : '-'} / {trip.approved_at
							? formatDateTime(trip.approved_at)
							: '-'}
					</dd>
				</div>
			</dl>

			<h2 class="mt-10 text-display-sm">출장 목적</h2>
			<p class="mt-2 whitespace-pre-line text-body-md text-ink">{trip.purpose_detail}</p>

			<h2 class="mt-10 text-display-sm">진행 이력</h2>
			<div class="mt-4">
				<Timeline {entries} />
			</div>
		</div>

		<aside class="lg:sticky lg:top-8 lg:self-start">
			<Card>
				<p class="text-caption text-muted">예상 비용</p>
				<p class="mt-1 text-display-md text-ink">{formatKrw(trip.estimated_cost)}</p>

				{#if actionError}
					<p class="mt-4 text-caption-sm text-error" role="alert">{actionError}</p>
				{/if}

				<div class="mt-6 flex flex-col gap-3">
					{#if isOwner && (trip.status === 'DRAFT' || trip.status === 'REJECTED')}
						<Button full disabled={busy} onclick={() => goto(`/trips/${tripId}/edit`)}>
							수정
						</Button>
					{/if}

					{#if isOwner && trip.status === 'DRAFT'}
						<Button full variant="secondary" disabled={busy} onclick={() => act(submitTrip)}>
							상신
						</Button>
						<Button full variant="tertiary" disabled={busy} onclick={removeTrip}>삭제</Button>
					{/if}

					{#if isOwner && trip.status === 'REJECTED'}
						<Button full variant="secondary" disabled={busy} onclick={() => act(reopenTrip)}>
							다시 작성
						</Button>
					{/if}

					{#if isOwner && trip.status === 'APPROVED'}
						<Button full variant="secondary" disabled={busy} onclick={() => act(completeTrip)}>
							완료 처리
						</Button>
					{/if}

					{#if isApprover && trip.status === 'SUBMITTED'}
						<Button full disabled={busy} onclick={() => act(approveTrip)}>승인</Button>
						{#if rejecting}
							<Textarea label="반려 사유" bind:value={rejectReason} rows={3} />
							<Button
								full
								variant="secondary"
								disabled={busy}
								onclick={() => act((id) => rejectTrip(id, rejectReason))}
							>
								반려 확정
							</Button>
							<Button full variant="tertiary" disabled={busy} onclick={() => (rejecting = false)}>
								취소
							</Button>
						{:else}
							<Button full variant="secondary" disabled={busy} onclick={() => (rejecting = true)}>
								반려
							</Button>
						{/if}
					{/if}

					{#if trip.status === 'COMPLETED' || trip.status === 'SETTLED'}
						<p class="text-body-sm text-muted">정산은 Phase 3에서 연결됩니다.</p>
					{/if}
				</div>
			</Card>
		</aside>
	</div>
{/if}
```

- [ ] **Step 3: 타입체크**

Run: `cd frontend && npm run check`
Expected: 0 errors

- [ ] **Step 4: 실행 확인**

- 사원 계정으로 DRAFT 출장 상세를 열면 수정·상신·삭제 버튼이 보인다
- 상신하면 상태 뱃지가 `승인대기`로 바뀌고 타임라인에 `상신` 항목이 추가된다
- 같은 출장을 팀장(`manager1@skon.example` 등 해당 출장의 결재자) 계정으로 열면 승인·반려 버튼이 보인다
- 반려 사유를 비우고 반려하면 `반려 사유를 입력해야 합니다`가 뜬다
- 남의 출장 id를 URL에 직접 넣으면 `출장을 찾을 수 없습니다`가 뜬다

- [ ] **Step 5: 커밋**

```bash
git add frontend/src/lib/components/Timeline.svelte frontend/src/routes/trips/\[id\]/+page.svelte
git commit -m "feat: add trip detail screen with timeline and action rail"
```

---

## Task 25: 출장 수정 화면

**Files:**
- Create: `frontend/src/routes/trips/[id]/edit/+page.svelte`

- [ ] **Step 1: 화면 작성**

```svelte
<script lang="ts">
	import { goto } from '$app/navigation';
	import { page } from '$app/state';
	import { ApiError } from '$lib/api/client';
	import { getTrip, updateTrip } from '$lib/api/trips';
	import type { TripInput } from '$lib/api/types';
	import Button from '$lib/components/Button.svelte';
	import TripForm from '$lib/components/TripForm.svelte';

	let initial = $state<TripInput | null>(null);
	let values = $state<TripInput | null>(null);
	let loading = $state(true);
	let loadError = $state('');
	let errorMessage = $state('');
	let submitting = $state(false);

	const tripId = $derived(Number(page.params.id));

	$effect(() => {
		const id = tripId;
		void load(id);
	});

	async function load(id: number): Promise<void> {
		loading = true;
		loadError = '';
		try {
			const trip = await getTrip(id);
			initial = {
				title: trip.title,
				purpose_code: trip.purpose_code,
				purpose_detail: trip.purpose_detail,
				destination_type_code: trip.destination_type_code,
				country_code: trip.country_code,
				city: trip.city,
				start_date: trip.start_date,
				end_date: trip.end_date,
				transport_code: trip.transport_code,
				accommodation_code: trip.accommodation_code,
				cost_center_code: trip.cost_center_code,
				// API는 Decimal을 "450000.00" 문자열로 보낸다. number 입력에 그대로 넣으면
				// 소수점이 보이므로 정수 문자열로 다듬는다.
				estimated_cost: String(Math.round(Number(trip.estimated_cost)))
			};
			values = { ...initial };
		} catch (error) {
			loadError = error instanceof ApiError ? error.message : '출장을 불러오지 못했습니다';
		} finally {
			loading = false;
		}
	}

	async function save(): Promise<void> {
		if (submitting || !values) return;
		submitting = true;
		errorMessage = '';
		try {
			await updateTrip(tripId, values);
			await goto(`/trips/${tripId}`);
		} catch (error) {
			errorMessage = error instanceof ApiError ? error.message : '저장하지 못했습니다';
		} finally {
			submitting = false;
		}
	}
</script>

<h1 class="text-display-xl">출장 수정</h1>

{#if loading}
	<p class="mt-8 text-body-sm text-muted">불러오는 중…</p>
{:else if loadError}
	<p class="mt-8 text-body-sm text-error" role="alert">{loadError}</p>
{:else if initial}
	<div class="mt-8 max-w-[720px]">
		<TripForm {initial} onchange={(next) => (values = next)} />

		{#if errorMessage}
			<p class="mt-6 text-body-sm text-error" role="alert">{errorMessage}</p>
		{/if}

		<div class="mt-8 flex gap-3">
			<Button variant="secondary" disabled={submitting} onclick={() => goto(`/trips/${tripId}`)}>
				취소
			</Button>
			<Button disabled={submitting} onclick={save}>
				{submitting ? '저장 중…' : '저장'}
			</Button>
		</div>
	</div>
{/if}
```

- [ ] **Step 2: 타입체크**

Run: `cd frontend && npm run check`
Expected: 0 errors

- [ ] **Step 3: 실행 확인**

- DRAFT 출장에서 "수정" → 값이 채워진 폼이 열린다
- 도시를 바꾸고 저장하면 상세로 돌아가 바뀐 값이 보이고, 타임라인에 `수정`이 추가된다
- 이미 상신된 출장의 edit URL로 직접 들어가 저장하면 `SUBMITTED 상태의 출장은 수정할 수 없습니다`가 뜬다

- [ ] **Step 4: 커밋**

```bash
git add frontend/src/routes/trips/\[id\]/edit/+page.svelte
git commit -m "feat: add trip edit screen"
```

---

## Task 26: 결재함

**Files:**
- Create: `frontend/src/routes/approvals/+page.svelte`

- [ ] **Step 1: 화면 작성**

```svelte
<script lang="ts">
	import { ApiError } from '$lib/api/client';
	import { listTrips } from '$lib/api/trips';
	import type { Page, TripListItem, TripStatus } from '$lib/api/types';
	import EmptyState from '$lib/components/EmptyState.svelte';
	import TripCard from '$lib/components/TripCard.svelte';
	import { TRIP_STATUS_LABELS } from '$lib/trip-status';

	const TABS: { value: TripStatus | 'ALL'; label: string }[] = [
		{ value: 'SUBMITTED', label: '결재 대기' },
		{ value: 'APPROVED', label: TRIP_STATUS_LABELS.APPROVED },
		{ value: 'REJECTED', label: TRIP_STATUS_LABELS.REJECTED },
		{ value: 'ALL', label: '전체' }
	];

	let active = $state<TripStatus | 'ALL'>('SUBMITTED');
	let result = $state<Page<TripListItem> | null>(null);
	let loading = $state(true);
	let errorMessage = $state('');

	$effect(() => {
		const status = active;
		void load(status);
	});

	async function load(status: TripStatus | 'ALL'): Promise<void> {
		loading = true;
		errorMessage = '';
		try {
			result = await listTrips({
				scope: 'approvals',
				status: status === 'ALL' ? undefined : [status],
				size: 24
			});
		} catch (error) {
			errorMessage = error instanceof ApiError ? error.message : '결재함을 불러오지 못했습니다';
		} finally {
			loading = false;
		}
	}
</script>

<h1 class="text-display-xl">결재함</h1>
<p class="mt-2 text-body-md text-muted">내가 결재자로 지정된 출장입니다.</p>

<div class="mt-6 flex gap-2">
	{#each TABS as tab (tab.value)}
		<button
			onclick={() => (active = tab.value)}
			aria-pressed={active === tab.value}
			class="h-10 rounded-full border px-4 text-button-sm {active === tab.value
				? 'border-ink bg-ink text-white'
				: 'border-hairline text-ink hover:shadow-float'}"
		>
			{tab.label}
		</button>
	{/each}
</div>

{#if errorMessage}
	<p class="mt-8 text-body-sm text-error" role="alert">{errorMessage}</p>
{:else if loading}
	<p class="mt-8 text-body-sm text-muted">불러오는 중…</p>
{:else if result && result.items.length > 0}
	<p class="mt-8 text-body-sm text-muted">{result.total}건</p>
	<div class="mt-4 grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3">
		{#each result.items as trip (trip.id)}
			<TripCard {trip} showOwner />
		{/each}
	</div>
{:else}
	<div class="mt-8">
		<EmptyState title="결재할 출장이 없습니다" description="상신된 출장이 도착하면 여기에 표시됩니다." />
	</div>
{/if}
```

- [ ] **Step 2: 타입체크**

Run: `cd frontend && npm run check`
Expected: 0 errors

- [ ] **Step 3: 실행 확인**

- 팀장 계정으로 `/approvals`에 들어가면 결재 대기 출장이 보이고 신청자 이름이 카드에 뜬다
- 카드를 눌러 상세에서 승인하면 목록에서 사라지고 `승인` 탭에 나타난다
- 사원 계정으로 들어가면 빈 상태가 보인다 (403이 아니다)

- [ ] **Step 4: 커밋**

```bash
git add frontend/src/routes/approvals/+page.svelte
git commit -m "feat: add approvals inbox screen"
```

---

## Task 27: 알림 화면과 앱 셸 진입점

**Files:**
- Create: `frontend/src/lib/stores/notifications.svelte.ts`
- Create: `frontend/src/routes/notifications/+page.svelte`
- Modify: `frontend/src/lib/components/AppShell.svelte`

상단 내비의 가운데 3-탭(출장 / 정산 / 개발자)은 DESIGN.md의 3-product tab이므로 건드리지 않는다. 결재함과 알림은 **우측 사용자 블록**에 붙인다.

- [ ] **Step 1: 알림 스토어 작성**

```ts
import { listNotifications } from '$lib/api/notifications';

class NotificationStore {
	unread = $state(0);

	/** 실패는 삼킨다 — 헤더 뱃지 때문에 화면 전체가 에러로 덮이면 안 된다. */
	async refresh(): Promise<void> {
		try {
			const page = await listNotifications({ size: 1 });
			this.unread = page.unread;
		} catch {
			this.unread = 0;
		}
	}

	reset(): void {
		this.unread = 0;
	}
}

export const notifications = new NotificationStore();
```

- [ ] **Step 2: 알림 화면 작성**

`frontend/src/routes/notifications/+page.svelte`:

```svelte
<script lang="ts">
	import { goto } from '$app/navigation';
	import { ApiError } from '$lib/api/client';
	import { listNotifications, markNotificationRead } from '$lib/api/notifications';
	import type { NotificationItem } from '$lib/api/types';
	import EmptyState from '$lib/components/EmptyState.svelte';
	import { formatDateTime } from '$lib/format';
	import { notifications } from '$lib/stores/notifications.svelte';
	import { onMount } from 'svelte';

	let items = $state<NotificationItem[]>([]);
	let loading = $state(true);
	let errorMessage = $state('');
	let busyId = $state<number | null>(null);

	onMount(load);

	async function load(): Promise<void> {
		loading = true;
		errorMessage = '';
		try {
			const page = await listNotifications({ size: 50 });
			items = page.items;
			notifications.unread = page.unread;
		} catch (error) {
			errorMessage = error instanceof ApiError ? error.message : '알림을 불러오지 못했습니다';
		} finally {
			loading = false;
		}
	}

	async function open(item: NotificationItem): Promise<void> {
		if (busyId !== null) return;
		busyId = item.id;
		try {
			if (!item.is_read) {
				const updated = await markNotificationRead(item.id);
				items = items.map((row) => (row.id === updated.id ? updated : row));
				notifications.unread = Math.max(0, notifications.unread - 1);
			}
			if (item.link_url) await goto(item.link_url);
		} catch (error) {
			errorMessage = error instanceof ApiError ? error.message : '처리하지 못했습니다';
		} finally {
			busyId = null;
		}
	}
</script>

<h1 class="text-display-xl">알림</h1>

{#if errorMessage}
	<p class="mt-8 text-body-sm text-error" role="alert">{errorMessage}</p>
{:else if loading}
	<p class="mt-8 text-body-sm text-muted">불러오는 중…</p>
{:else if items.length > 0}
	<ul class="mt-8 flex flex-col gap-3">
		{#each items as item (item.id)}
			<li>
				<button
					onclick={() => open(item)}
					class="w-full rounded-md border px-5 py-4 text-left hover:shadow-float {item.is_read
						? 'border-hairline'
						: 'border-ink'}"
				>
					<div class="flex items-center justify-between gap-4">
						<p class="text-title-sm text-ink">{item.title}</p>
						{#if !item.is_read}
							<span class="h-2 w-2 shrink-0 rounded-full bg-primary"></span>
						{/if}
					</div>
					<p class="mt-1 text-body-sm text-muted">{item.body}</p>
					<p class="mt-2 text-caption-sm text-muted">{formatDateTime(item.created_at)}</p>
				</button>
			</li>
		{/each}
	</ul>
{:else}
	<div class="mt-8">
		<EmptyState title="알림이 없습니다" description="결재 요청이나 결과가 오면 여기에 쌓입니다." />
	</div>
{/if}
```

- [ ] **Step 3: `AppShell.svelte` 수정**

`<script>`를 다음으로 교체한다:

```svelte
<script lang="ts">
	import { page } from '$app/state';
	import { goto } from '$app/navigation';
	import { auth } from '$lib/stores/auth.svelte';
	import { notifications } from '$lib/stores/notifications.svelte';
	import type { Snippet } from 'svelte';

	let { children }: { children: Snippet } = $props();

	const tabs = [
		{ href: '/trips', label: '출장' },
		{ href: '/expenses', label: '정산' },
		{ href: '/developers', label: '개발자' }
	];

	// 결재함은 결재자 역할에게만 의미가 있으므로 우측 블록에 조건부로 둔다.
	// 가운데 3-탭은 DESIGN.md의 3-product tab이라 늘리지 않는다.
	const canApprove = $derived(auth.user?.role === 'MANAGER' || auth.user?.role === 'ADMIN');

	// 라우트가 바뀔 때마다 미읽음 수를 새로 센다. 상신·승인이 다른 화면에서
	// 일어나므로 마운트 시 한 번만 세면 뱃지가 곧 낡는다.
	$effect(() => {
		void page.url.pathname;
		void notifications.refresh();
	});

	function isActive(href: string): boolean {
		const path = page.url.pathname;
		return path === href || path.startsWith(`${href}/`);
	}

	function signOut(): void {
		auth.clear();
		notifications.reset();
		goto('/login');
	}
</script>
```

우측 사용자 블록(`<div class="flex items-center justify-self-end gap-4">`)의 `{#if auth.user}` 바로 뒤, 이름 `<span>` **앞에** 다음을 넣는다:

```svelte
				{#if canApprove}
					<a
						href="/approvals"
						aria-current={isActive('/approvals') ? 'page' : undefined}
						class="text-button-sm {isActive('/approvals') ? 'text-ink' : 'text-muted hover:text-ink'}"
					>
						결재함
					</a>
				{/if}
				<a
					href="/notifications"
					aria-label="알림"
					class="relative flex h-10 w-10 items-center justify-center rounded-full hover:shadow-float"
				>
					<svg viewBox="0 0 24 24" class="h-5 w-5" fill="none" stroke="currentColor" stroke-width="2">
						<path d="M6 9a6 6 0 1112 0c0 4 1.5 5 1.5 5h-15S6 13 6 9z" stroke-linejoin="round" />
						<path d="M10 19a2 2 0 004 0" stroke-linecap="round" />
					</svg>
					{#if notifications.unread > 0}
						<span
							class="absolute top-1 right-1 flex h-4 min-w-4 items-center justify-center rounded-full bg-primary px-1 text-badge text-white"
						>
							{notifications.unread > 99 ? '99+' : notifications.unread}
						</span>
					{/if}
				</a>
```

- [ ] **Step 4: 타입체크**

Run: `cd frontend && npm run check`
Expected: 0 errors

- [ ] **Step 5: 실행 확인**

- 사원이 출장을 상신한 뒤 팀장 계정으로 로그인하면 헤더 벨에 숫자 뱃지가 뜬다
- 알림을 누르면 읽음 처리되고 해당 출장 상세로 이동하며 뱃지 숫자가 하나 줄어든다
- 팀장/관리자에게만 "결재함" 링크가 보인다

- [ ] **Step 6: 커밋**

```bash
git add frontend/src/lib/stores/notifications.svelte.ts frontend/src/routes/notifications/+page.svelte frontend/src/lib/components/AppShell.svelte
git commit -m "feat: add notifications screen and header entry points"
```

---

## Task 28: 대시보드 연결

**Files:**
- Modify: `frontend/src/routes/+page.svelte`

Phase 1이 "Phase 2에서 연결"이라고 박아둔 카드 세 개를 실제 수치로 채운다. 전용 집계 API를 만들지 않는다 — `size=1`로 목록을 불러 `total`만 읽으면 된다.

- [ ] **Step 1: 화면 교체**

```svelte
<script lang="ts">
	import { onMount } from 'svelte';
	import { ApiError } from '$lib/api/client';
	import { listNotifications } from '$lib/api/notifications';
	import { listTrips } from '$lib/api/trips';
	import type { NotificationItem, TripListItem } from '$lib/api/types';
	import Badge from '$lib/components/Badge.svelte';
	import Card from '$lib/components/Card.svelte';
	import TripCard from '$lib/components/TripCard.svelte';
	import { formatDateTime } from '$lib/format';
	import { auth } from '$lib/stores/auth.svelte';

	const ROLE_LABELS: Record<string, string> = {
		EMPLOYEE: '사원',
		MANAGER: '팀장',
		ADMIN: '관리자'
	};

	let ongoing = $state(0);
	let waiting = $state(0);
	let unsettled = $state(0);
	let recentTrips = $state<TripListItem[]>([]);
	let recentNotifications = $state<NotificationItem[]>([]);
	let errorMessage = $state('');
	let loading = $state(true);

	onMount(async () => {
		try {
			const [ongoingPage, waitingPage, unsettledPage, latest, notified] = await Promise.all([
				listTrips({ status: ['SUBMITTED', 'APPROVED'], size: 1 }),
				listTrips({ scope: 'approvals', status: ['SUBMITTED'], size: 1 }),
				listTrips({ status: ['COMPLETED'], size: 1 }),
				listTrips({ size: 3 }),
				listNotifications({ size: 5 })
			]);
			ongoing = ongoingPage.total;
			waiting = waitingPage.total;
			unsettled = unsettledPage.total;
			recentTrips = latest.items;
			recentNotifications = notified.items;
		} catch (error) {
			errorMessage = error instanceof ApiError ? error.message : '현황을 불러오지 못했습니다';
		} finally {
			loading = false;
		}
	});
</script>

<h1 class="text-display-xl">안녕하세요, {auth.user?.name}님</h1>
<p class="mt-2 text-body-md text-muted">
	{auth.user?.department_name} · {auth.user?.role ? (ROLE_LABELS[auth.user.role] ?? auth.user.role) : ''}
</p>

{#if errorMessage}
	<p class="mt-8 text-body-sm text-error" role="alert">{errorMessage}</p>
{/if}

<div class="mt-8 grid grid-cols-1 gap-4 md:grid-cols-3">
	<a href="/trips?status=SUBMITTED" class="block">
		<Card hoverable>
			<p class="text-caption text-muted">진행 중 출장</p>
			<p class="mt-2 text-display-md">{loading ? '…' : `${ongoing}건`}</p>
			<div class="mt-3"><Badge>승인대기 · 승인</Badge></div>
		</Card>
	</a>
	<a href="/approvals" class="block">
		<Card hoverable>
			<p class="text-caption text-muted">결재 대기</p>
			<p class="mt-2 text-display-md">{loading ? '…' : `${waiting}건`}</p>
		</Card>
	</a>
	<a href="/trips?status=COMPLETED" class="block">
		<Card hoverable>
			<p class="text-caption text-muted">미정산 출장</p>
			<p class="mt-2 text-display-md">{loading ? '…' : `${unsettled}건`}</p>
			<div class="mt-3"><Badge>정산은 Phase 3</Badge></div>
		</Card>
	</a>
</div>

<div class="mt-12 grid grid-cols-1 gap-8 lg:grid-cols-[minmax(0,2fr)_minmax(0,1fr)]">
	<section>
		<h2 class="text-display-sm">최근 출장</h2>
		<div class="mt-4 grid grid-cols-1 gap-4 md:grid-cols-2">
			{#each recentTrips as trip (trip.id)}
				<TripCard {trip} />
			{/each}
			{#if !loading && recentTrips.length === 0}
				<p class="text-body-sm text-muted">아직 신청한 출장이 없습니다.</p>
			{/if}
		</div>
	</section>

	<section>
		<h2 class="text-display-sm">최근 알림</h2>
		<ul class="mt-4 flex flex-col gap-3">
			{#each recentNotifications as item (item.id)}
				<li class="rounded-md border border-hairline px-4 py-3">
					<a href={item.link_url ?? '/notifications'} class="block">
						<p class="text-title-sm text-ink">{item.title}</p>
						<p class="mt-1 text-caption-sm text-muted">{formatDateTime(item.created_at)}</p>
					</a>
				</li>
			{/each}
			{#if !loading && recentNotifications.length === 0}
				<li class="text-body-sm text-muted">알림이 없습니다.</li>
			{/if}
		</ul>
	</section>
</div>
```

- [ ] **Step 2: 타입체크**

Run: `cd frontend && npm run check`
Expected: 0 errors

- [ ] **Step 3: 실행 확인**

- 로그인 직후 대시보드의 세 카드에 숫자가 뜬다 ("Phase 2에서 연결" 문구가 사라졌다)
- 카드를 누르면 해당 필터가 걸린 목록/결재함으로 이동한다

- [ ] **Step 4: 커밋**

```bash
git add frontend/src/routes/+page.svelte
git commit -m "feat: wire dashboard to real trip and notification data"
```

---

## Task 29: 전체 검증

**Files:** 없음 (검증만)

- [ ] **Step 1: 백엔드 전체 테스트**

Run: `cd backend && uv run pytest`
Expected: 전부 통과. 실패가 하나라도 있으면 여기서 멈추고 고친다.

- [ ] **Step 2: 프론트 테스트·타입체크·빌드**

```bash
cd frontend && npm test
cd frontend && npm run check
cd frontend && npm run build
```
Expected: 테스트 전부 통과 / 0 errors / 빌드 성공

- [ ] **Step 3: 수동 시나리오 — 실브라우저 + 실백엔드**

백엔드와 프론트를 띄우고 아래를 순서대로 확인한다. 각 항목이 실제로 통과하는 것을 눈으로 본 뒤에만 체크한다.

1. **딥링크 보존** — 로그아웃 상태에서 `http://localhost:5173/trips/3`을 연다 → `/login?redirect=%2Ftrips%2F3`로 튕긴다 → 로그인하면 `/trips/3`으로 간다 (`/`가 아니다)
2. **신청 → 상신** — `user1@skon.example`로 신청서를 작성해 "저장 후 상신" → 상세가 `승인대기`이고 타임라인에 `작성`·`상신`이 있다
3. **중복 제출** — 신규 신청 폼에서 "저장 후 상신"을 빠르게 두 번 누른다 → 출장이 **한 건만** 생긴다
4. **결재** — 해당 출장의 결재자 계정으로 로그인 → 헤더 벨에 뱃지, `/approvals`에 카드가 보인다 → 승인한다
5. **반려 → 재작성 → 재상신** — 다른 상신 건을 사유와 함께 반려 → 신청자 계정에서 반려 사유가 빨간 박스로 보인다 → "다시 작성" → 수정 → 다시 상신하면 반려 사유가 사라진다
6. **완료** — 종료일이 지난 승인 건에서 "완료 처리" → `완료`가 된다. 미래 일정 건에서는 `종료일이 지난 출장만 완료 처리할 수 있습니다`가 뜬다
7. **타인 리소스** — 남의 출장 id로 `/trips/<id>`에 직접 접근 → `출장을 찾을 수 없습니다`
8. **전역 401** — devtools에서 `localStorage.setItem('skon.token','garbage')` 후 목록 화면에서 새로고침 없이 필터를 다시 적용 → 로그인 화면으로 정리되어 나간다
9. **Agent 경로 동등성** — 아래 curl이 화면과 같은 결과를 낸다

```bash
TOKEN=$(curl -s localhost:8000/api/v1/auth/login -H 'Content-Type: application/json' \
  -d '{"email":"user1@skon.example","password":"skon1234!"}' | python3 -c 'import sys,json;print(json.load(sys.stdin)["access_token"])')

curl -s "localhost:8000/api/v1/codes/TRANSPORT" -H "Authorization: Bearer $TOKEN"
curl -s "localhost:8000/api/v1/trips?status=SUBMITTED" -H "Authorization: Bearer $TOKEN"
curl -s -X POST localhost:8000/api/v1/trips -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{"title":"Agent가 만든 출장","purpose_code":"AUDIT","purpose_detail":"API로 생성","destination_type_code":"DOMESTIC","country_code":"KR","city":"울산","start_date":"2026-10-01","end_date":"2026-10-03","transport_code":"RAIL","accommodation_code":"HOTEL","cost_center_code":"CC2030","estimated_cost":"300000"}'
```
→ 마지막 응답의 id로 화면 `/trips/<id>`를 열면 방금 만든 출장이 그대로 보인다

10. **409 계약** — 이미 상신된 출장에 `POST /trips/<id>/submit`을 다시 보내면 `{"error":{"code":"TRIP_INVALID_TRANSITION",...}}`가 409로 온다

- [ ] **Step 4: 커밋**

```bash
git commit --allow-empty -m "chore: verify phase 2 end to end"
```

---

## Phase 2 완료 기준

- [ ] `cd backend && uv run pytest` 전부 통과
- [ ] `cd frontend && npm test` 전부 통과
- [ ] `cd frontend && npm run check` 0 errors
- [ ] `cd frontend && npm run build` 성공
- [ ] Task 29 Step 3의 수동 시나리오 10개 전부 확인
- [ ] spec 6의 Phase 2 화면 6개(`/trips` `/trips/new` `/trips/[id]` `/trips/[id]/edit` `/approvals` `/notifications`)와 대시보드가 실데이터로 동작
- [ ] spec 5.4의 전이 6종(상신·승인·반려·재작성·완료, 그리고 각각의 위반 시 409)이 웹과 curl 양쪽에서 동일하게 동작

---

## Phase 2 안에서 처리할 정리 항목

Task 2 리뷰에서 나온 것. **Task 9(출장 생성·수정)가 통과한 뒤에** 손댄다 — 첫 소비자가 자리를 잡기 전에 건드리면 흔들린다.

- **`load_active_codes`의 생산 호출부가 사라졌다.** Task 2 이후 이 함수를 부르는 것은 테스트뿐이고, Phase 2의 나머지 태스크 중 어느 것도 쓰지 않는다(Task 13의 `load_code_groups`는 별도 경로다). 그런데 "그룹 부재 vs 활성 코드 0개" 규칙과 두 개의 `is_active` 필터가 이제 두 벌의 쿼리 구현에 각각 들어 있어, 의미를 바꾸려면 두 곳을 다 찾아야 한다. Task 9 통과 후 둘 중 하나를 택한다 — (a) `load_active_codes`와 딸린 테스트 3건을 지우거나, (b) 두 함수를 `_load_active_codes_by_group(session, group_codes) -> dict[str, set[str]]` 하나 위에 얹는다.
- **그때 `load_active_codes`의 주석도 고친다.** "join은 두 경우를 구분하지 못한다"고 적혀 있으나 이는 **inner** join에만 참이다. LEFT OUTER JOIN은 구분할 수 있다(그룹 없음 → 행 없음, 코드 0개 → `(group, NULL)`). 지금 구조를 바꿀 이유는 없지만 — 근거는 성능이 아니라 호출부 안전이다 — 저 문장은 언젠가 누군가를 오도하거나 잘못된 수정을 부른다.

## Phase 3으로 넘기는 항목

- **`COMPLETED → SETTLED` 전이.** `trip_status.py`에 전이는 이미 열려 있지만 트리거(정산서 APPROVED)가 Phase 3에 있어 아무도 호출하지 않는다. Phase 3의 정산 승인 서비스가 `record_transition`을 통해 함께 기록해야 한다 — 출장 쪽 이력이 비면 타임라인이 끊긴다.
- **`GET /fund-centers`는 만들어만 뒀다.** Phase 2에서 화면이 쓰지 않는다. 정산서 헤더의 FC 셀렉트가 첫 사용처다.
- **`assert_fund_center` 검증기가 없다.** `services/centers.py`에 `load_active_center_codes`만 있고 코스트센터 검증만 있다. 정산서 쓰기 경로를 만들 때 같은 모양으로 추가한다. **그때 순수 함수를 뽑는다** — `assert_cost_center`는 쿼리·멤버십 검사·예외 발생이 한 함수에 붙어 있어서 두 줄짜리 순수 검사에 `db_session`이 필요하다. 지금은 4줄이라 그대로 두지만, `assert_fund_center`가 `if code not in allowed: raise` 블록을 복사하려는 순간이 `assert_center_code(code, allowed, *, field)`를 뽑을 시점이다 (`codes.py`가 `assert_valid_code`를 분리해 둔 것과 같은 모양).
- **`ActivityAction`에 정산 액션이 없다.** 현재 enum은 출장 기준이다. 정산서 전이도 같은 `activity_log`를 쓰되 `entity_type=EXPENSE_REPORT`로 구분한다 — 새 액션 멤버가 필요한지 Phase 3에서 판단한다.
- **알림 뱃지는 라우트 변경 시에만 갱신된다.** 같은 화면에 머무는 동안 새 알림이 오면 보이지 않는다. 폴링이나 SSE는 데모 범위 밖이라 하지 않았다.
- **대시보드는 집계를 위해 목록 API를 4번 부른다.** `size=1`이라 비용은 작지만, 카드가 더 늘면 전용 요약 엔드포인트가 낫다.
- **`q` 필터는 LIKE 와일드카드를 이스케이프하지 않는다.** 사용자가 `%`를 넣으면 검색 범위가 넓어질 뿐이지만, Admin 검색처럼 정확도가 중요한 곳을 만들면 그때 처리한다.
- **출장번호 채번은 `max() + 1`이다.** 단일 인스턴스 전제. 멀티 레플리카로 가면 시퀀스나 advisory lock이 필요하다.
- **744px 미만 반응형 붕괴는 여전히 없다.** 이번 Phase에서 화면이 6개 늘었으므로 모바일 대응 시 작업량이 그만큼 커졌다.
- **`restore()`/`clear()` 경합은 여전히 도달 불가.** `AppShell`은 `auth.user`가 non-null일 때만 마운트된다. "세션 갱신" 같은 호출이 생기면 그때 정리한다.
