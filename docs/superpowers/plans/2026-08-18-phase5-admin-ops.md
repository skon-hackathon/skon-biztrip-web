# Phase 5 (운영) — Admin CRUD · 반응형 · 배포 검증 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 관리자가 마스터 데이터(공통코드·FC/CC·부서·사용자·법인카드)를 웹과 API 양쪽에서 CRUD 할 수 있게 하고, 744px 미만 반응형을 처음으로 넣고, 4개 이미지 빌드·기동을 다시 검증한다.

**Architecture:** 기존 3계층을 그대로 따른다 — `routers/admin/*` → `services/admin/*` → `models`. 관리자 라우트는 `AdminUser`(role=ADMIN) 의존성과 `SCOPE_REQUIREMENTS`의 `ApiKeyScope.ADMIN` 항목 **둘 다**를 통과해야 한다. 삭제는 전부 `services/admin/common.py`의 `delete_entity` 하나를 거쳐 `IntegrityError`를 409 `HAS_DEPENDENTS`로 바꾼다(안 하면 500이 되고 Agent가 재시도한다). 프론트는 `/admin` 레이아웃 아래 5개 화면을 두고, 목록·에러·중복제출 가드를 `AdminResource`(runes 스토어) 하나로 공유한다.

**Tech Stack:** FastAPI 0.141 / SQLAlchemy 2 async / Pydantic v2 / pytest-asyncio(auto) — SvelteKit 2 + Svelte 5 runes / Tailwind v4 / vitest — Docker Compose.

---

## 반드시 먼저 읽을 것

- `CLAUDE.md` — 특히 "반드시 지킬 것" 전체. 이 계획은 그 규칙을 전제한다.
- `docs/phase-status.md`의 **"Phase 4에서 넘어온 항목"**과 **"Phase 5 착수 시 반드시 볼 것"**.

이 계획이 이월 항목에서 실제로 처리하는 것:

| 이월 항목 | 처리 태스크 |
|---|---|
| `/admin/*`은 `SCOPE_REQUIREMENTS`에 `ApiKeyScope.ADMIN`으로 등록 (빠뜨리면 기동 실패) | Task 4·5·6·7·8 (각 라우터와 **같은 커밋**) |
| Admin 삭제는 `IntegrityError` → 409 `HAS_DEPENDENTS` | Task 1 (`delete_entity`) · Task 8(실제 FK 경로 검증) |
| 비밀번호 엔드포인트는 72바이트를 막아야 한다 (bcrypt 5.x는 자르지 않고 던진다) | Task 1 (`assert_password_length`) · Task 7 |
| `admin` 스코프에 엔드포인트가 없다 | Task 9 (키로 admin API 호출 e2e) |
| 반응형 744px 미완 (화면 13개) | Task 18·19 |
| 브라우저 수동 시나리오 23개 미확인 + Phase 5 신규 | Task 22 |
| 배포 재검증 | Task 20·21 |

이 계획이 **처리하지 않는** 이월 항목(그대로 다음으로 넘긴다): `last_used_at` 스로틀, 출장 상세의 정산서 존재 판정(`size=100`), 항목 FC/CC override 재검증, `q`의 LIKE 이스케이프, `next_report_no`의 `max()+1`, 매칭 후보 페이징, 알림 폴링, 대시보드 집계 4회 호출. Task 23에서 문서에 남긴다.

---

## 확정된 설계 결정 (구현 전에 읽을 것)

| 쟁점 | 결정 | 이유 |
|---|---|---|
| Admin 인가 | `AdminUser` = `Depends(require_role(UserRole.ADMIN))` + 표의 `ApiKeyScope.ADMIN` **둘 다** | 역할은 사람을, 스코프는 키를 막는다. 하나만 두면 ADMIN이 발급한 `trips:read` 키가 admin API를 열거나(스코프만 빠짐), admin 스코프 키가 EMPLOYEE 소유일 때 통과한다(역할만 빠짐) |
| 라우터 배치 | `app/routers/admin/` 패키지 5모듈, `main.py`가 각각 include | 중첩 `include_router`를 쓰지 않는다 — 라우트 탐지(`iter_route_contexts`)에 층을 하나 더 얹을 이유가 없다 |
| 비밀번호 설정 | `POST /admin/users/{id}/password`는 **JWT 전용**(`JwtOnlyUser`) | admin 스코프 키로 남의 비밀번호를 바꾸면 그 계정으로 로그인해 JWT를 얻고, JWT로 전권 키를 발급할 수 있다. 키 관리 API를 JWT 전용으로 둔 이유가 우회된다 |
| 비밀번호 길이 검사 위치 | Pydantic이 아니라 서비스 (`assert_password_length`) | `max_length`는 **문자 수**라 한글 72자(216바이트)를 통과시킨다. 바이트 검사여야 하고, 도메인 코드(`PASSWORD_TOO_LONG`)로 내려야 Agent가 원인을 안다 |
| 사용자 삭제 | 없음. `is_active=false`로 비활성화 | `user.id`는 trip·expense_report·card·api_key·activity_log가 참조한다. 삭제는 사실상 항상 409이고, 감사 흔적을 지우는 것이 옳지도 않다 |
| 자기 자신 강등 | 409 `CANNOT_DEMOTE_SELF` | 마지막 ADMIN이 스스로를 EMPLOYEE로 바꾸면 아무도 Admin 화면에 못 들어간다. 복구 경로가 DB 직접 수정뿐이 된다 |
| 코드 삭제 | 활성 코드는 409 `CODE_STILL_ACTIVE`. 먼저 비활성화해야 지울 수 있다 | 업무 테이블이 코드값을 **문자열**로 들고 있어 FK가 없다 → DB가 막아주지 못한다. "비활성화 후 삭제" 2단계가 유일하게 값싼 방어선이다 |
| 코드그룹 삭제 | 코드가 남아 있으면 409 `HAS_DEPENDENTS` | `CodeGroup.codes`는 `cascade="all, delete-orphan"`이라 ORM 삭제가 자식을 조용히 쓸어간다. 그룹 하나 지우려다 코드 12개가 사라지는 것을 명시적 2단계로 바꾼다 |
| 센터 삭제 | 참조(trip·expense_report·expense_item의 코드 문자열)가 있으면 409 `HAS_DEPENDENTS` | 코드와 같은 이유로 FK가 없다. 다만 참조처가 3개뿐이라 열거해서 막을 수 있다 |
| 유니크 위반 | 삽입 전 SELECT로 확인해 409 + `field` | `IntegrityError`를 잡으면 어느 컬럼이 겹쳤는지 알 수 없어 `field`를 못 채운다. TOCTOU가 남지만 최종 방어선은 DB 제약이다 (`MAX_ACTIVE_KEYS`와 같은 종류의 미결) |
| Admin 목록 응답 | 비활성 행도 **포함**한다 (`AdminCodeGroupOut` 등 전용 스키마) | 기존 `/codes`·`/fund-centers`는 활성만 준다. 관리 화면이 비활성 행을 못 보면 되살릴 방법이 없다. 스키마를 나눠 두 독자를 분리한다 |
| PATCH 부분 갱신 | `payload.model_dump(exclude_unset=True)` | `parent_id: int \| None = None`은 "미지정"과 "null로 지우기"가 구분되지 않는다. `exclude_unset`이 유일한 구분 수단이다 |
| 프론트 공유 | `AdminResource`(runes 스토어)가 목록·로딩·에러·**중복 제출 가드**를 소유 | 화면 5개에 같은 가드를 손으로 다섯 번 넣으면 하나는 빠진다. 가드를 vitest로 한 번 고정한다 |
| 반응형 기준선 | `--breakpoint-tablet: 744px` 신설. 기존 `md:`(768px)는 건드리지 않는다 | DESIGN.md가 744px를 규정한다. `--breakpoint-md`를 덮으면 기존 13개 화면의 그리드가 전부 함께 움직인다 |

---

## 파일 구조

**백엔드 — 신규**

| 파일 | 책임 |
|---|---|
| `backend/app/services/admin/__init__.py` | 빈 패키지 마커 |
| `backend/app/services/admin/common.py` | `assert_password_length`(순수) · `assert_unique` · `delete_entity`(IntegrityError→409) |
| `backend/app/services/admin/departments.py` | 부서 CRUD + 상위부서 검증 |
| `backend/app/services/admin/codes.py` | 코드그룹·코드 CRUD + 2단계 삭제 규칙 |
| `backend/app/services/admin/centers.py` | FC/CC CRUD (모델 파라미터로 공유) + 참조 검사 |
| `backend/app/services/admin/users.py` | 사용자 CRUD(삭제 없음) + 비밀번호 설정 + 자기강등 금지 |
| `backend/app/services/admin/cards.py` | 법인카드 CRUD |
| `backend/app/routers/admin/__init__.py` | 빈 패키지 마커 |
| `backend/app/routers/admin/{departments,codes,centers,users,cards}.py` | 얇은 라우터 5종 |
| `backend/app/schemas/admin.py` | Admin 전용 요청·응답 스키마 |

**백엔드 — 수정**

| 파일 | 변경 |
|---|---|
| `backend/app/deps.py` | `AdminUser` 추가 |
| `backend/app/services/api_scopes.py` | `SCOPE_REQUIREMENTS`에 admin 28항목 + `SCOPE_DESCRIPTIONS[ADMIN]` 문구 |
| `backend/app/main.py` | 라우터 5개 include |
| `backend/app/openapi.py` | JWT 전용 경로 집합에 비밀번호 경로 추가 |

**프론트 — 신규**

| 파일 | 책임 |
|---|---|
| `frontend/src/lib/api/admin.ts` | Admin API 호출 (전부 `authRequest`) |
| `frontend/src/lib/admin.ts` | 순수 헬퍼 (라벨·옵션 빌더) |
| `frontend/src/lib/stores/admin-resource.svelte.ts` | 목록·로딩·에러·중복제출 가드 |
| `frontend/src/routes/admin/+layout.svelte` | ADMIN 가드 + 서브탭 |
| `frontend/src/routes/admin/{codes,centers,users,departments,cards}/+page.svelte` | 화면 5종 |

**프론트 — 수정**: `lib/api/types.ts`(Admin 타입) · `lib/components/AppShell.svelte`(관리 링크 + 햄버거) · `src/app.css`(breakpoint) · 표를 쓰는 기존 화면들(가로 스크롤).

---

## Task 1: Admin 공통 — 삭제 변환과 비밀번호 가드

**Files:**
- Create: `backend/app/services/admin/__init__.py`
- Create: `backend/app/services/admin/common.py`
- Test: `backend/tests/test_admin_common.py`

- [ ] **Step 1: 실패하는 테스트를 쓴다**

`backend/tests/test_admin_common.py`:

```python
"""Admin CRUD가 공유하는 가드. 여기가 뚫리면 삭제는 500, 비밀번호는 500이 된다."""

import pytest

from app.errors import ConflictError, ValidationError
from app.models import Department
from app.services.admin.common import (
    assert_password_length,
    assert_unique,
    delete_entity,
)
from tests.factories import make_department, make_user


def test_eight_character_ascii_password_passes():
    assert assert_password_length("abcd1234") is None


def test_short_password_is_rejected_with_a_field():
    with pytest.raises(ValidationError) as exc:
        assert_password_length("abc123")
    assert exc.value.code == "PASSWORD_TOO_SHORT"
    assert exc.value.field == "password"


def test_korean_password_of_exactly_72_bytes_passes():
    # 한글 1자 = UTF-8 3바이트. 24자 = 72바이트 = 경계값.
    assert assert_password_length("가" * 24) is None


def test_korean_password_over_72_bytes_is_rejected():
    # 25자 = 75바이트. bcrypt 5.x는 자르지 않고 예외를 던지므로 여기서 막지 않으면 500이다.
    with pytest.raises(ValidationError) as exc:
        assert_password_length("가" * 25)
    assert exc.value.code == "PASSWORD_TOO_LONG"
    assert exc.value.field == "password"


async def test_delete_entity_turns_a_reference_into_409(db_session):
    department = await make_department(db_session)
    await make_user(db_session, department=department)

    with pytest.raises(ConflictError) as exc:
        await delete_entity(db_session, department, message="참조가 있습니다")

    assert exc.value.code == "HAS_DEPENDENTS"
    assert exc.value.status_code == 409


async def test_delete_entity_removes_an_unreferenced_row(db_session):
    department = await make_department(db_session)
    department_id = department.id

    await delete_entity(db_session, department, message="참조가 있습니다")

    assert await db_session.get(Department, department_id) is None


async def test_assert_unique_rejects_an_existing_value(db_session):
    department = await make_department(db_session)

    with pytest.raises(ConflictError) as exc:
        await assert_unique(
            db_session,
            Department.code,
            department.code,
            code="DUPLICATE_DEPARTMENT_CODE",
            message="이미 있는 부서 코드입니다",
            field="code",
        )

    assert exc.value.field == "code"


async def test_assert_unique_allows_a_new_value(db_session):
    assert (
        await assert_unique(
            db_session,
            Department.code,
            "D-NEVER-USED",
            code="DUPLICATE_DEPARTMENT_CODE",
            message="이미 있는 부서 코드입니다",
            field="code",
        )
        is None
    )
```

- [ ] **Step 2: 실패를 확인한다**

```bash
cd /Users/namkon/projects/skon-biztrip-web/backend && uv run pytest tests/test_admin_common.py -v
```

Expected: collection error — `ModuleNotFoundError: No module named 'app.services.admin'`

- [ ] **Step 3: 구현한다**

`backend/app/services/admin/__init__.py`: 빈 파일.

```bash
cd /Users/namkon/projects/skon-biztrip-web/backend && mkdir -p app/services/admin && : > app/services/admin/__init__.py
```

`backend/app/services/admin/common.py`:

```python
"""Admin CRUD가 공유하는 세 가지 가드.

`delete_entity`가 존재하는 이유는 spec 7 "마스터 데이터" 절이다. 마스터 FK에는 `ondelete`를
걸지 않으므로 참조가 남은 행을 지우면 PostgreSQL이 거부하는 것이 옳다. 다만 그 `IntegrityError`를
그대로 두면 통일 에러 핸들러의 catch-all로 떨어져 **500**이 되고, Agent는 5xx를 재시도하므로
절대 성공할 수 없는 요청에 재시도 루프가 걸린다. 출장 금액 오버플로에서 이미 겪은 실패다.
"""

from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.errors import ConflictError, ValidationError

#: bcrypt 5.x는 72바이트를 넘는 비밀번호를 자르지 않고 예외로 던진다. UTF-8 한글은 3바이트라
#: **24자면 경계**다. Pydantic의 max_length는 문자 수라서 이 검사를 대신할 수 없다.
MAX_PASSWORD_BYTES = 72
MIN_PASSWORD_LENGTH = 8


def assert_password_length(password: str, *, field: str = "password") -> None:
    """순수 검증 — DB 접근 없음."""
    if len(password) < MIN_PASSWORD_LENGTH:
        raise ValidationError(
            "PASSWORD_TOO_SHORT",
            f"비밀번호는 {MIN_PASSWORD_LENGTH}자 이상이어야 합니다",
            field=field,
        )
    if len(password.encode("utf-8")) > MAX_PASSWORD_BYTES:
        raise ValidationError(
            "PASSWORD_TOO_LONG",
            f"비밀번호는 UTF-8 기준 {MAX_PASSWORD_BYTES}바이트를 넘을 수 없습니다 (한글 24자)",
            field=field,
        )


async def assert_unique(
    session: AsyncSession, column, value: str, *, code: str, message: str, field: str
) -> None:
    """유니크 위반을 삽입 전에 409로 잡는다.

    `IntegrityError`를 받아 변환하지 않는 이유: 어떤 컬럼이 겹쳤는지 알 수 없어 `field`를
    채울 수 없다. TOCTOU가 남지만(동시에 같은 코드를 만들면 둘 다 통과) 최종 방어선은 DB의
    유니크 제약이다.
    """
    found = await session.scalar(select(column).where(column == value).limit(1))
    if found is not None:
        raise ConflictError(code, message, field=field)


async def delete_entity(session: AsyncSession, entity: Any, *, message: str) -> None:
    """ORM 삭제 + 참조 위반을 409 `HAS_DEPENDENTS`로 변환한다.

    Core의 일괄 `delete()`가 아니라 `session.delete()`를 쓴다 — `CodeGroup.codes`의
    `cascade="all, delete-orphan"`은 ORM 객체 삭제에만 적용되기 때문이다(spec 7).
    """
    await session.delete(entity)
    try:
        await session.flush()
    except IntegrityError as exc:
        # 실패한 flush 뒤의 세션은 오염 상태다. 롤백하지 않으면 이후 모든 문장이
        # PendingRollbackError가 되어 진짜 원인이 묻힌다.
        await session.rollback()
        raise ConflictError("HAS_DEPENDENTS", message) from exc
    await session.commit()
```

- [ ] **Step 4: 통과를 확인한다**

```bash
cd /Users/namkon/projects/skon-biztrip-web/backend && uv run pytest tests/test_admin_common.py -v
```

Expected: 8 passed

- [ ] **Step 5: mutation으로 가드를 확인한다**

`delete_entity`의 `except IntegrityError` 블록을 잠시 지우고(=`await session.flush()`만 남기고) 위 명령을 다시 돌린다. `test_delete_entity_turns_a_reference_into_409`가 **실패**해야 한다. 그다음 `MAX_PASSWORD_BYTES`를 `1000`으로 바꿔 `test_korean_password_over_72_bytes_is_rejected`가 실패하는지 본다. 둘 다 확인했으면 원복한다.

```bash
cd /Users/namkon/projects/skon-biztrip-web/backend && git diff --stat app/services/admin/common.py
```

Expected: 원복 후 diff 없음 (출력 없음)

- [ ] **Step 6: 커밋**

```bash
cd /Users/namkon/projects/skon-biztrip-web && git add backend/app/services/admin backend/tests/test_admin_common.py && git commit -m "feat(admin): add shared delete/unique/password guards"
```

---

## Task 2: `AdminUser` 의존성

**Files:**
- Modify: `backend/app/deps.py` (import 1줄 + 파일 끝 3줄)
- Test: `backend/tests/test_admin_deps.py`

`_enforce_scope`는 건드리지 않는다. 이 함수는 JWT여도 `required_scope_for`를 먼저 불러 표에 없는
경로를 403으로 떨어뜨리는데, 그건 실수가 아니라 "소진 가드가 우회된 상황에서도 fail-closed"라는
의도된 방어다. 그래서 probe 테스트가 자기 경로를 표에 **주입**한다.

- [ ] **Step 1: 실패하는 테스트를 쓴다**

`backend/tests/test_admin_deps.py`:

```python
"""AdminUser는 역할을 본다. 스코프(키)는 SCOPE_REQUIREMENTS가 따로 본다 — 둘 다 필요하다."""

import httpx
import pytest
from fastapi import FastAPI

from app.db import get_db
from app.deps import AdminUser
from app.enums import ApiKeyScope, UserRole
from app.errors import register_error_handlers
from app.security import create_access_token
from app.services.api_scopes import SCOPE_REQUIREMENTS
from tests.factories import make_user


@pytest.fixture
def probe_app(db_session, monkeypatch):
    """AdminUser 하나만 붙은 최소 앱.

    경로를 SCOPE_REQUIREMENTS에 주입하는 이유: `_enforce_scope`는 JWT 요청에서도 표를 먼저
    조회하고, 표에 없으면 403 SCOPE_UNDECLARED를 던진다(의도된 fail-closed). 주입하지 않으면
    역할 검사에 도달하기 전에 스코프 검사에서 떨어져 이 테스트가 아무것도 검증하지 못한다.
    """
    monkeypatch.setitem(SCOPE_REQUIREMENTS, ("GET", "/probe"), ApiKeyScope.ADMIN)

    app = FastAPI()
    register_error_handlers(app)

    @app.get("/probe")
    async def probe(user: AdminUser) -> dict[str, str]:
        return {"name": user.name}

    app.dependency_overrides[get_db] = lambda: db_session
    return app


async def _call(app, headers: dict[str, str]) -> httpx.Response:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        return await client.get("/probe", headers=headers)


async def test_admin_passes(probe_app, db_session):
    admin = await make_user(db_session, role=UserRole.ADMIN, name="관리자")
    token = create_access_token(user_id=admin.id)

    response = await _call(probe_app, {"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    assert response.json() == {"name": "관리자"}


async def test_manager_is_rejected(probe_app, db_session):
    manager = await make_user(db_session, role=UserRole.MANAGER)
    token = create_access_token(user_id=manager.id)

    response = await _call(probe_app, {"Authorization": f"Bearer {token}"})

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "FORBIDDEN_ROLE"


async def test_employee_is_rejected(probe_app, db_session):
    employee = await make_user(db_session, role=UserRole.EMPLOYEE)
    token = create_access_token(user_id=employee.id)

    response = await _call(probe_app, {"Authorization": f"Bearer {token}"})

    assert response.status_code == 403
```

- [ ] **Step 2: 실패를 확인한다**

```bash
uv run pytest tests/test_admin_deps.py -v
```

Expected: collection error — `ImportError: cannot import name 'AdminUser' from 'app.deps'`

- [ ] **Step 3: 구현한다**

`backend/app/deps.py`의 import 블록에 한 줄 추가한다 (`from app.errors import ...` 아래):

```python
from app.enums import UserRole
```

파일 맨 끝(`JwtOnlyUser` 아래)에 추가한다:

```python
#: Admin 전용 라우트. 역할(사람)과 스코프(키)는 서로를 대체하지 않는다 —
#: 역할만 보면 ADMIN이 발급한 `trips:read` 키가 admin API를 열고, 스코프만 보면
#: admin 스코프를 가진 EMPLOYEE 소유 키가 통과한다. 둘 다 통과해야 한다.
AdminUser = Annotated[User, Depends(require_role(UserRole.ADMIN))]
```

- [ ] **Step 4: 통과를 확인한다**

```bash
cd /Users/namkon/projects/skon-biztrip-web/backend && uv run pytest tests/test_admin_deps.py tests/test_scope_enforcement.py tests/test_api_scopes.py -v
```

Expected: `test_admin_deps.py` 3 passed, 기존 스코프 테스트 전부 passed

- [ ] **Step 5: mutation 확인**

`AdminUser`를 `require_role(UserRole.ADMIN, UserRole.MANAGER)`로 바꿔 `test_manager_is_rejected`가 실패하는지 본다. 확인 후 원복하고 `git diff app/deps.py`로 원복을 눈으로 확인한다.

- [ ] **Step 6: 전체 테스트 + 커밋**

```bash
cd /Users/namkon/projects/skon-biztrip-web/backend && uv run pytest -q
cd /Users/namkon/projects/skon-biztrip-web && git add backend/app/deps.py backend/tests/test_admin_deps.py && git commit -m "feat(admin): add AdminUser role dependency"
```

---

## Task 3: Admin 스키마

**Files:**
- Create: `backend/app/schemas/admin.py`
- Test: `backend/tests/test_schemas_admin.py`

- [ ] **Step 1: 실패하는 테스트를 쓴다**

`backend/tests/test_schemas_admin.py`:

```python
"""PATCH 스키마는 '미지정'과 'null로 지우기'를 구분해야 한다 — exclude_unset이 그 수단이다."""

import pytest
from pydantic import ValidationError as PydanticValidationError

from app.enums import UserRole
from app.schemas.admin import (
    AdminUserCreate,
    CenterUpdate,
    CodeCreate,
    DepartmentCreate,
    DepartmentUpdate,
)


def test_department_update_omits_unset_fields():
    payload = DepartmentUpdate.model_validate({"name": "새이름"})
    assert payload.model_dump(exclude_unset=True) == {"name": "새이름"}


def test_department_update_keeps_an_explicit_null_parent():
    payload = DepartmentUpdate.model_validate({"parent_id": None})
    assert payload.model_dump(exclude_unset=True) == {"parent_id": None}


def test_center_update_keeps_an_explicit_false():
    payload = CenterUpdate.model_validate({"is_active": False})
    assert payload.model_dump(exclude_unset=True) == {"is_active": False}


def test_department_code_cannot_be_empty():
    with pytest.raises(PydanticValidationError):
        DepartmentCreate.model_validate({"code": "", "name": "부서"})


def test_code_create_defaults_extra_to_an_empty_dict():
    payload = CodeCreate.model_validate({"code": "AIR", "name": "항공"})
    assert payload.extra == {}
    assert payload.sort_order == 0
    assert payload.is_active is True


def test_admin_user_create_defaults_to_employee():
    payload = AdminUserCreate.model_validate(
        {
            "email": "new@skon.example",
            "password": "skon1234!",
            "name": "신입",
            "employee_no": "E9999",
            "department_id": 1,
            "position_code": "STAFF",
        }
    )
    assert payload.role is UserRole.EMPLOYEE
    assert payload.is_active is True
    assert payload.manager_id is None
```

- [ ] **Step 2: 실패를 확인한다**

```bash
cd /Users/namkon/projects/skon-biztrip-web/backend && uv run pytest tests/test_schemas_admin.py -v
```

Expected: collection error — `ModuleNotFoundError: No module named 'app.schemas.admin'`

- [ ] **Step 3: 구현한다**

`backend/app/schemas/admin.py`:

```python
"""Admin CRUD의 요청·응답 스키마.

`/codes`·`/fund-centers`가 쓰는 스키마와 나눠 둔 이유: 일반 화면은 **활성 값만** 봐야 하고
관리 화면은 **비활성 값도** 봐야 한다. 한 스키마를 두 독자가 공유하면 언젠가 비활성 코드가
출장 신청 드롭다운에 나타난다.

PATCH 스키마의 필드는 전부 Optional이며 서비스가 `model_dump(exclude_unset=True)`로 읽는다 —
`parent_id=None`이 "안 보냄"인지 "null로 지우기"인지는 그 방법으로만 구분된다.
"""

from typing import Any

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.enums import UserRole

# --- 부서 -------------------------------------------------------------------


class DepartmentCreate(BaseModel):
    code: str = Field(min_length=1, max_length=20)
    name: str = Field(min_length=1, max_length=100)
    parent_id: int | None = None


class DepartmentUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    parent_id: int | None = None


class DepartmentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    code: str
    name: str
    parent_id: int | None


# --- 공통코드 ---------------------------------------------------------------


class CodeGroupCreate(BaseModel):
    group_code: str = Field(min_length=1, max_length=40)
    name: str = Field(min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=255)
    is_active: bool = True


class CodeGroupUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=255)
    is_active: bool | None = None


class CodeCreate(BaseModel):
    code: str = Field(min_length=1, max_length=40)
    name: str = Field(min_length=1, max_length=100)
    sort_order: int = 0
    is_active: bool = True
    extra: dict[str, Any] = Field(default_factory=dict)


class CodeUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    sort_order: int | None = None
    is_active: bool | None = None
    extra: dict[str, Any] | None = None


class AdminCodeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    code: str
    name: str
    sort_order: int
    is_active: bool
    extra: dict[str, Any]


class AdminCodeGroupOut(BaseModel):
    id: int
    group_code: str
    name: str
    description: str | None
    is_active: bool
    codes: list[AdminCodeOut]


# --- FC / CC ----------------------------------------------------------------


class CenterCreate(BaseModel):
    code: str = Field(min_length=1, max_length=20)
    name: str = Field(min_length=1, max_length=100)
    department_id: int | None = None
    is_active: bool = True


class CenterUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    department_id: int | None = None
    is_active: bool | None = None


class AdminCenterOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    code: str
    name: str
    department_id: int | None
    is_active: bool


# --- 사용자 -----------------------------------------------------------------


class AdminUserCreate(BaseModel):
    email: EmailStr
    # 길이는 서비스의 assert_password_length가 본다. max_length는 **문자 수**라
    # 한글 72자(216바이트)를 통과시켜 bcrypt에서 터진다.
    password: str = Field(min_length=1)
    name: str = Field(min_length=1, max_length=50)
    employee_no: str = Field(min_length=1, max_length=20)
    department_id: int
    position_code: str = Field(min_length=1, max_length=30)
    manager_id: int | None = None
    role: UserRole = UserRole.EMPLOYEE
    is_active: bool = True


class AdminUserUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=50)
    department_id: int | None = None
    position_code: str | None = Field(default=None, min_length=1, max_length=30)
    manager_id: int | None = None
    role: UserRole | None = None
    is_active: bool | None = None


class PasswordSet(BaseModel):
    password: str = Field(min_length=1)


class AdminUserOut(BaseModel):
    id: int
    email: str
    name: str
    employee_no: str
    department_id: int
    department_name: str
    position_code: str
    manager_id: int | None
    manager_name: str | None
    role: UserRole
    is_active: bool


# --- 법인카드 ---------------------------------------------------------------


class AdminCardCreate(BaseModel):
    user_id: int
    card_no_masked: str = Field(min_length=1, max_length=30)
    brand: str = Field(min_length=1, max_length=30)
    is_active: bool = True


class AdminCardUpdate(BaseModel):
    card_no_masked: str | None = Field(default=None, min_length=1, max_length=30)
    brand: str | None = Field(default=None, min_length=1, max_length=30)
    is_active: bool | None = None


class AdminCardOut(BaseModel):
    id: int
    user_id: int
    user_name: str
    card_no_masked: str
    brand: str
    is_active: bool
```

- [ ] **Step 4: 통과를 확인한다**

```bash
cd /Users/namkon/projects/skon-biztrip-web/backend && uv run pytest tests/test_schemas_admin.py -v
```

Expected: 6 passed

- [ ] **Step 5: 커밋**

```bash
cd /Users/namkon/projects/skon-biztrip-web && git add backend/app/schemas/admin.py backend/tests/test_schemas_admin.py && git commit -m "feat(admin): add admin request/response schemas"
```

---

## Task 4: 부서 CRUD

**Files:**
- Create: `backend/app/services/admin/departments.py`
- Create: `backend/app/routers/admin/__init__.py` (빈 파일)
- Create: `backend/app/routers/admin/departments.py`
- Modify: `backend/app/services/api_scopes.py` (표에 4항목)
- Modify: `backend/app/main.py` (import + include)
- Test: `backend/tests/test_admin_departments_api.py`

**표와 라우터는 같은 커밋에서 움직인다.** 표에 안 적으면 `main.py` 임포트에서 `RuntimeError`로 앱이 뜨지 않는다. 이건 버그가 아니라 설계다.

- [ ] **Step 1: 실패하는 테스트를 쓴다**

`backend/tests/test_admin_departments_api.py`:

```python
"""부서 Admin CRUD. 역할 검사 + 참조 삭제 변환이 핵심이다."""

from tests.factories import make_department, make_user
from app.enums import UserRole


async def test_employee_cannot_list_departments(client, seeded, login_as):
    headers = await login_as("user1@skon.example")

    response = await client.get("/api/v1/admin/departments", headers=headers)

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "FORBIDDEN_ROLE"


async def test_manager_cannot_list_departments(client, seeded, login_as):
    headers = await login_as("manager1@skon.example")

    assert (await client.get("/api/v1/admin/departments", headers=headers)).status_code == 403


async def test_admin_lists_departments_in_code_order(client, seeded, login_as):
    headers = await login_as("admin@skon.example")

    response = await client.get("/api/v1/admin/departments", headers=headers)

    assert response.status_code == 200
    codes = [row["code"] for row in response.json()]
    assert codes == sorted(codes)
    assert "D100" in codes


async def test_admin_creates_a_department(client, seeded, login_as):
    headers = await login_as("admin@skon.example")

    response = await client.post(
        "/api/v1/admin/departments",
        headers=headers,
        json={"code": "D900", "name": "신규팀", "parent_id": None},
    )

    assert response.status_code == 201
    assert response.json()["code"] == "D900"
    listed = await client.get("/api/v1/admin/departments", headers=headers)
    assert "D900" in [row["code"] for row in listed.json()]


async def test_duplicate_department_code_is_409_with_a_field(client, seeded, login_as):
    headers = await login_as("admin@skon.example")

    response = await client.post(
        "/api/v1/admin/departments", headers=headers, json={"code": "D100", "name": "중복"}
    )

    assert response.status_code == 409
    body = response.json()["error"]
    assert body["code"] == "DUPLICATE_DEPARTMENT_CODE"
    assert body["field"] == "code"


async def test_unknown_parent_is_400(client, seeded, login_as):
    headers = await login_as("admin@skon.example")

    response = await client.post(
        "/api/v1/admin/departments",
        headers=headers,
        json={"code": "D901", "name": "고아", "parent_id": 999999},
    )

    assert response.status_code == 400
    body = response.json()["error"]
    assert body["code"] == "INVALID_PARENT"
    assert body["field"] == "parent_id"


async def test_department_cannot_be_its_own_parent(client, seeded, login_as, db_session):
    headers = await login_as("admin@skon.example")
    department = await make_department(db_session, name="자기참조")
    await db_session.commit()

    response = await client.patch(
        f"/api/v1/admin/departments/{department.id}",
        headers=headers,
        json={"parent_id": department.id},
    )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "INVALID_PARENT"


async def test_patch_only_changes_sent_fields(client, seeded, login_as, db_session):
    headers = await login_as("admin@skon.example")
    parent = await make_department(db_session, name="상위")
    child = await make_department(db_session, name="하위")
    child.parent_id = parent.id
    await db_session.commit()

    response = await client.patch(
        f"/api/v1/admin/departments/{child.id}", headers=headers, json={"name": "이름만변경"}
    )

    assert response.status_code == 200
    body = response.json()
    assert body["name"] == "이름만변경"
    # parent_id를 보내지 않았으므로 그대로여야 한다. exclude_unset이 없으면 null로 지워진다.
    assert body["parent_id"] == parent.id


async def test_explicit_null_clears_the_parent(client, seeded, login_as, db_session):
    headers = await login_as("admin@skon.example")
    parent = await make_department(db_session, name="상위2")
    child = await make_department(db_session, name="하위2")
    child.parent_id = parent.id
    await db_session.commit()

    response = await client.patch(
        f"/api/v1/admin/departments/{child.id}", headers=headers, json={"parent_id": None}
    )

    assert response.status_code == 200
    assert response.json()["parent_id"] is None


async def test_deleting_a_referenced_department_is_409(client, seeded, login_as, db_session):
    headers = await login_as("admin@skon.example")
    department = await make_department(db_session, name="사람있는부서")
    await make_user(db_session, department=department, role=UserRole.EMPLOYEE)
    await db_session.commit()

    response = await client.delete(
        f"/api/v1/admin/departments/{department.id}", headers=headers
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "HAS_DEPENDENTS"


async def test_deleting_an_empty_department_succeeds(client, seeded, login_as, db_session):
    headers = await login_as("admin@skon.example")
    department = await make_department(db_session, name="빈부서")
    await db_session.commit()

    response = await client.delete(
        f"/api/v1/admin/departments/{department.id}", headers=headers
    )

    assert response.status_code == 204
    listed = await client.get("/api/v1/admin/departments", headers=headers)
    assert department.id not in [row["id"] for row in listed.json()]


async def test_missing_department_is_404(client, seeded, login_as):
    headers = await login_as("admin@skon.example")

    response = await client.patch(
        "/api/v1/admin/departments/999999", headers=headers, json={"name": "없음"}
    )

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "DEPARTMENT_NOT_FOUND"
```

- [ ] **Step 2: 실패를 확인한다**

```bash
cd /Users/namkon/projects/skon-biztrip-web/backend && uv run pytest tests/test_admin_departments_api.py -q
```

Expected: 전부 실패 (404 — 라우트가 없다)

- [ ] **Step 3: 서비스를 구현한다**

`backend/app/services/admin/departments.py`:

```python
"""부서 마스터 CRUD.

부서 트리의 순환(A→B→A)은 검사하지 않는다. 자기 자신만 막는다 — 데모 조직은 2단계이고,
일반 순환 검출은 재귀 조회가 필요해 값에 비해 비싸다. 이 한계는 phase-status에 남긴다.
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.errors import NotFoundError, ValidationError
from app.models import Department
from app.schemas.admin import DepartmentCreate, DepartmentOut, DepartmentUpdate
from app.services.admin.common import assert_unique, delete_entity


async def list_departments(session: AsyncSession) -> list[DepartmentOut]:
    rows = (
        (await session.execute(select(Department).order_by(Department.code))).scalars().all()
    )
    return [DepartmentOut.model_validate(row) for row in rows]


async def _load(session: AsyncSession, department_id: int) -> Department:
    department = await session.get(Department, department_id)
    if department is None:
        raise NotFoundError("DEPARTMENT_NOT_FOUND", f"존재하지 않는 부서입니다: {department_id}")
    return department


async def _assert_parent(
    session: AsyncSession, parent_id: int | None, *, self_id: int | None = None
) -> None:
    if parent_id is None:
        return
    if self_id is not None and parent_id == self_id:
        raise ValidationError(
            "INVALID_PARENT", "자기 자신을 상위 부서로 지정할 수 없습니다", field="parent_id"
        )
    if await session.get(Department, parent_id) is None:
        raise ValidationError(
            "INVALID_PARENT", f"존재하지 않는 상위 부서입니다: {parent_id}", field="parent_id"
        )


async def create_department(
    session: AsyncSession, *, payload: DepartmentCreate
) -> DepartmentOut:
    await assert_unique(
        session,
        Department.code,
        payload.code,
        code="DUPLICATE_DEPARTMENT_CODE",
        message=f"이미 있는 부서 코드입니다: {payload.code}",
        field="code",
    )
    await _assert_parent(session, payload.parent_id)
    department = Department(code=payload.code, name=payload.name, parent_id=payload.parent_id)
    session.add(department)
    await session.commit()
    await session.refresh(department)
    return DepartmentOut.model_validate(department)


async def update_department(
    session: AsyncSession, *, department_id: int, payload: DepartmentUpdate
) -> DepartmentOut:
    department = await _load(session, department_id)
    # exclude_unset이 "안 보냄"과 "null로 지우기"를 가르는 유일한 수단이다.
    changes = payload.model_dump(exclude_unset=True)
    if "parent_id" in changes:
        await _assert_parent(session, changes["parent_id"], self_id=department.id)
    for field, value in changes.items():
        setattr(department, field, value)
    await session.commit()
    await session.refresh(department)
    return DepartmentOut.model_validate(department)


async def delete_department(session: AsyncSession, *, department_id: int) -> None:
    department = await _load(session, department_id)
    await delete_entity(
        session,
        department,
        message="이 부서를 참조하는 사용자·센터가 있어 삭제할 수 없습니다",
    )
```

- [ ] **Step 4: 라우터를 만든다**

```bash
cd /Users/namkon/projects/skon-biztrip-web/backend && mkdir -p app/routers/admin && : > app/routers/admin/__init__.py
```

`backend/app/routers/admin/departments.py`:

```python
from fastapi import APIRouter, status

from app.deps import AdminUser, DbSession
from app.schemas.admin import DepartmentCreate, DepartmentOut, DepartmentUpdate
from app.services.admin import departments as service

router = APIRouter(prefix="/api/v1/admin/departments", tags=["admin"])


@router.get("", response_model=list[DepartmentOut])
async def list_departments(user: AdminUser, session: DbSession) -> list[DepartmentOut]:
    return await service.list_departments(session)


@router.post("", response_model=DepartmentOut, status_code=status.HTTP_201_CREATED)
async def create_department(
    payload: DepartmentCreate, user: AdminUser, session: DbSession
) -> DepartmentOut:
    return await service.create_department(session, payload=payload)


@router.patch("/{department_id}", response_model=DepartmentOut)
async def update_department(
    department_id: int, payload: DepartmentUpdate, user: AdminUser, session: DbSession
) -> DepartmentOut:
    return await service.update_department(
        session, department_id=department_id, payload=payload
    )


@router.delete("/{department_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_department(department_id: int, user: AdminUser, session: DbSession) -> None:
    await service.delete_department(session, department_id=department_id)
```

- [ ] **Step 5: 스코프 표와 main.py를 같은 커밋에서 고친다**

`backend/app/services/api_scopes.py`의 별칭 블록에 한 줄 추가:

```python
_AD = ApiKeyScope.ADMIN
```

`SCOPE_REQUIREMENTS` 딕셔너리 끝(정산 항목들 뒤)에 추가:

```python
    ("GET", "/api/v1/admin/departments"): _AD,
    ("POST", "/api/v1/admin/departments"): _AD,
    ("PATCH", "/api/v1/admin/departments/{department_id}"): _AD,
    ("DELETE", "/api/v1/admin/departments/{department_id}"): _AD,
```

`backend/app/main.py`의 import 블록에 추가:

```python
from app.routers.admin import departments as admin_departments
```

include 목록에 추가 (`app.include_router(api_keys.router)` 위, 알파벳 순서 유지):

```python
app.include_router(admin_departments.router)
```

- [ ] **Step 6: 통과를 확인한다**

```bash
cd /Users/namkon/projects/skon-biztrip-web/backend && uv run pytest tests/test_admin_departments_api.py -v
```

Expected: 12 passed

- [ ] **Step 7: 소진 가드가 살아 있는지 mutation으로 확인한다**

`SCOPE_REQUIREMENTS`에서 `("DELETE", "/api/v1/admin/departments/{department_id}")` 한 줄을 지우고:

```bash
cd /Users/namkon/projects/skon-biztrip-web/backend && uv run pytest tests/test_admin_departments_api.py -q 2>&1 | tail -5
```

Expected: `RuntimeError: SCOPE_REQUIREMENTS가 실제 라우트와 어긋납니다` (수집 단계에서 실패). 확인 후 원복하고 `grep -n "admin/departments" app/services/api_scopes.py`로 4줄이 모두 있는지 눈으로 확인한다.

- [ ] **Step 8: 커밋**

```bash
cd /Users/namkon/projects/skon-biztrip-web/backend && uv run pytest -q
cd /Users/namkon/projects/skon-biztrip-web && git add backend/app backend/tests/test_admin_departments_api.py && git commit -m "feat(admin): department CRUD with scope table entries"
```

---

## Task 5: 공통코드 CRUD (그룹 + 코드)

**Files:**
- Create: `backend/app/services/admin/codes.py`
- Create: `backend/app/routers/admin/codes.py`
- Modify: `backend/app/services/api_scopes.py` (7항목), `backend/app/main.py`
- Test: `backend/tests/test_admin_codes_api.py`

- [ ] **Step 1: 실패하는 테스트를 쓴다**

`backend/tests/test_admin_codes_api.py`:

```python
"""공통코드 Admin CRUD.

업무 테이블이 코드값을 문자열로 들고 있어 FK가 없다 — DB가 막아주지 않으므로
"비활성화 후 삭제" 2단계를 서비스가 강제한다.
"""


async def _admin(login_as):
    return await login_as("admin@skon.example")


async def test_employee_cannot_read_admin_code_groups(client, seeded, login_as):
    headers = await login_as("user1@skon.example")

    assert (await client.get("/api/v1/admin/code-groups", headers=headers)).status_code == 403


async def test_admin_list_includes_inactive_codes(client, seeded, login_as):
    """관리 화면은 비활성 코드를 봐야 되살릴 수 있다. /api/v1/codes와 다른 점이다."""
    headers = await _admin(login_as)
    groups = (await client.get("/api/v1/admin/code-groups", headers=headers)).json()
    transport = next(g for g in groups if g["group_code"] == "TRANSPORT")
    code_id = transport["codes"][0]["id"]

    await client.patch(
        f"/api/v1/admin/codes/{code_id}", headers=headers, json={"is_active": False}
    )

    admin_groups = (await client.get("/api/v1/admin/code-groups", headers=headers)).json()
    admin_transport = next(g for g in admin_groups if g["group_code"] == "TRANSPORT")
    assert code_id in [c["id"] for c in admin_transport["codes"]]

    public = (await client.get("/api/v1/codes/TRANSPORT", headers=headers)).json()
    assert transport["codes"][0]["code"] not in [c["code"] for c in public["codes"]]


async def test_admin_creates_a_group_and_a_code(client, seeded, login_as):
    headers = await _admin(login_as)

    group = await client.post(
        "/api/v1/admin/code-groups",
        headers=headers,
        json={"group_code": "RISK_LEVEL", "name": "위험도"},
    )
    assert group.status_code == 201
    group_id = group.json()["id"]

    code = await client.post(
        f"/api/v1/admin/code-groups/{group_id}/codes",
        headers=headers,
        json={"code": "HIGH", "name": "높음", "sort_order": 1, "extra": {"color": "red"}},
    )

    assert code.status_code == 201
    assert code.json()["extra"] == {"color": "red"}


async def test_duplicate_group_code_is_409(client, seeded, login_as):
    headers = await _admin(login_as)

    response = await client.post(
        "/api/v1/admin/code-groups",
        headers=headers,
        json={"group_code": "TRANSPORT", "name": "중복"},
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "DUPLICATE_CODE_GROUP"


async def test_duplicate_code_within_a_group_is_409(client, seeded, login_as):
    headers = await _admin(login_as)
    groups = (await client.get("/api/v1/admin/code-groups", headers=headers)).json()
    transport = next(g for g in groups if g["group_code"] == "TRANSPORT")

    response = await client.post(
        f"/api/v1/admin/code-groups/{transport['id']}/codes",
        headers=headers,
        json={"code": transport["codes"][0]["code"], "name": "중복"},
    )

    assert response.status_code == 409
    body = response.json()["error"]
    assert body["code"] == "DUPLICATE_CODE"
    assert body["field"] == "code"


async def test_active_code_cannot_be_deleted(client, seeded, login_as):
    """활성 코드를 지우면 그 값을 쓰는 출장·정산 행이 고아가 된다. 2단계를 강제한다."""
    headers = await _admin(login_as)
    groups = (await client.get("/api/v1/admin/code-groups", headers=headers)).json()
    code_id = next(g for g in groups if g["group_code"] == "TRANSPORT")["codes"][0]["id"]

    response = await client.delete(f"/api/v1/admin/codes/{code_id}", headers=headers)

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "CODE_STILL_ACTIVE"


async def test_inactive_code_can_be_deleted(client, seeded, login_as):
    headers = await _admin(login_as)
    group = (
        await client.post(
            "/api/v1/admin/code-groups",
            headers=headers,
            json={"group_code": "TEMP_GROUP", "name": "임시"},
        )
    ).json()
    code = (
        await client.post(
            f"/api/v1/admin/code-groups/{group['id']}/codes",
            headers=headers,
            json={"code": "TMP", "name": "임시코드", "is_active": False},
        )
    ).json()

    response = await client.delete(f"/api/v1/admin/codes/{code['id']}", headers=headers)

    assert response.status_code == 204


async def test_group_with_codes_cannot_be_deleted(client, seeded, login_as):
    """cascade="all, delete-orphan"이 자식을 조용히 쓸어가는 것을 막는다."""
    headers = await _admin(login_as)
    groups = (await client.get("/api/v1/admin/code-groups", headers=headers)).json()
    transport = next(g for g in groups if g["group_code"] == "TRANSPORT")

    response = await client.delete(
        f"/api/v1/admin/code-groups/{transport['id']}", headers=headers
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "HAS_DEPENDENTS"


async def test_empty_group_can_be_deleted(client, seeded, login_as):
    headers = await _admin(login_as)
    group = (
        await client.post(
            "/api/v1/admin/code-groups",
            headers=headers,
            json={"group_code": "EMPTY_GROUP", "name": "빈그룹"},
        )
    ).json()

    response = await client.delete(f"/api/v1/admin/code-groups/{group['id']}", headers=headers)

    assert response.status_code == 204


async def test_deactivating_a_group_hides_it_from_the_public_endpoint(client, seeded, login_as):
    headers = await _admin(login_as)
    groups = (await client.get("/api/v1/admin/code-groups", headers=headers)).json()
    accommodation = next(g for g in groups if g["group_code"] == "ACCOMMODATION")

    await client.patch(
        f"/api/v1/admin/code-groups/{accommodation['id']}",
        headers=headers,
        json={"is_active": False},
    )

    public = await client.get("/api/v1/codes/ACCOMMODATION", headers=headers)
    assert public.status_code == 404


async def test_missing_group_is_404(client, seeded, login_as):
    headers = await _admin(login_as)

    response = await client.post(
        "/api/v1/admin/code-groups/999999/codes",
        headers=headers,
        json={"code": "X", "name": "없는그룹"},
    )

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "CODE_GROUP_NOT_FOUND"
```

- [ ] **Step 2: 실패를 확인한다**

```bash
cd /Users/namkon/projects/skon-biztrip-web/backend && uv run pytest tests/test_admin_codes_api.py -q
```

Expected: 전부 실패 (404)

- [ ] **Step 3: 서비스를 구현한다**

`backend/app/services/admin/codes.py`:

```python
"""공통코드 그룹·코드 CRUD.

삭제가 2단계인 이유는 참조 방식 때문이다. 업무 테이블은 `trip.transport_code = 'AIR'`처럼
**코드값 문자열**을 저장하므로 FK가 없고, PostgreSQL이 삭제를 막아주지 않는다. 그래서
`delete_entity`(IntegrityError→409)만으로는 아무것도 지켜지지 않는다. 대신 서비스가
"비활성화된 코드만 삭제 가능", "코드가 없는 그룹만 삭제 가능"을 강제한다.
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.errors import ConflictError, NotFoundError
from app.models import Code, CodeGroup
from app.schemas.admin import (
    AdminCodeGroupOut,
    AdminCodeOut,
    CodeCreate,
    CodeGroupCreate,
    CodeGroupUpdate,
    CodeUpdate,
)
from app.services.admin.common import assert_unique, delete_entity


def _to_out(group: CodeGroup) -> AdminCodeGroupOut:
    """비활성 코드도 포함한다 — 관리 화면이 못 보면 되살릴 수 없다.
    `CodeGroup.codes`는 lazy="selectin"이라 그룹 조회 한 번에 함께 실려온다."""
    return AdminCodeGroupOut(
        id=group.id,
        group_code=group.group_code,
        name=group.name,
        description=group.description,
        is_active=group.is_active,
        codes=[
            AdminCodeOut.model_validate(code)
            for code in sorted(group.codes, key=lambda c: (c.sort_order, c.code))
        ],
    )


async def list_code_groups(session: AsyncSession) -> list[AdminCodeGroupOut]:
    groups = (
        (await session.execute(select(CodeGroup).order_by(CodeGroup.group_code)))
        .scalars()
        .all()
    )
    return [_to_out(group) for group in groups]


async def _load_group(session: AsyncSession, group_id: int) -> CodeGroup:
    group = await session.get(CodeGroup, group_id)
    if group is None:
        raise NotFoundError("CODE_GROUP_NOT_FOUND", f"존재하지 않는 코드그룹입니다: {group_id}")
    return group


async def _load_code(session: AsyncSession, code_id: int) -> Code:
    code = await session.get(Code, code_id)
    if code is None:
        raise NotFoundError("CODE_NOT_FOUND", f"존재하지 않는 코드입니다: {code_id}")
    return code


async def create_code_group(
    session: AsyncSession, *, payload: CodeGroupCreate
) -> AdminCodeGroupOut:
    await assert_unique(
        session,
        CodeGroup.group_code,
        payload.group_code,
        code="DUPLICATE_CODE_GROUP",
        message=f"이미 있는 코드그룹입니다: {payload.group_code}",
        field="group_code",
    )
    group = CodeGroup(
        group_code=payload.group_code,
        name=payload.name,
        description=payload.description,
        is_active=payload.is_active,
    )
    session.add(group)
    await session.commit()
    await session.refresh(group)
    return _to_out(group)


async def update_code_group(
    session: AsyncSession, *, group_id: int, payload: CodeGroupUpdate
) -> AdminCodeGroupOut:
    group = await _load_group(session, group_id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(group, field, value)
    await session.commit()
    await session.refresh(group)
    return _to_out(group)


async def delete_code_group(session: AsyncSession, *, group_id: int) -> None:
    group = await _load_group(session, group_id)
    if group.codes:
        raise ConflictError(
            "HAS_DEPENDENTS",
            f"코드 {len(group.codes)}개가 남아 있는 그룹은 삭제할 수 없습니다. "
            "코드를 먼저 지우거나 그룹을 비활성화하세요",
        )
    await delete_entity(session, group, message="이 코드그룹을 참조하는 데이터가 있습니다")


async def create_code(
    session: AsyncSession, *, group_id: int, payload: CodeCreate
) -> AdminCodeOut:
    group = await _load_group(session, group_id)
    # 유니크가 (group_id, code) 복합이라 assert_unique(단일 컬럼)를 쓸 수 없다.
    existing = await session.scalar(
        select(Code.id).where(Code.group_id == group.id, Code.code == payload.code).limit(1)
    )
    if existing is not None:
        raise ConflictError(
            "DUPLICATE_CODE",
            f"{group.group_code} 그룹에 이미 있는 코드입니다: {payload.code}",
            field="code",
        )
    code = Code(
        group_id=group.id,
        code=payload.code,
        name=payload.name,
        sort_order=payload.sort_order,
        is_active=payload.is_active,
        extra=payload.extra,
    )
    session.add(code)
    await session.commit()
    await session.refresh(code)
    return AdminCodeOut.model_validate(code)


async def update_code(
    session: AsyncSession, *, code_id: int, payload: CodeUpdate
) -> AdminCodeOut:
    code = await _load_code(session, code_id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(code, field, value)
    await session.commit()
    await session.refresh(code)
    return AdminCodeOut.model_validate(code)


async def delete_code(session: AsyncSession, *, code_id: int) -> None:
    code = await _load_code(session, code_id)
    if code.is_active:
        raise ConflictError(
            "CODE_STILL_ACTIVE",
            "활성 코드는 삭제할 수 없습니다. 먼저 비활성화하세요 "
            "(업무 데이터가 코드값을 문자열로 참조하므로 DB가 막아주지 못합니다)",
        )
    await delete_entity(session, code, message="이 코드를 참조하는 데이터가 있습니다")
```

- [ ] **Step 4: 라우터를 만든다**

`backend/app/routers/admin/codes.py`:

```python
from fastapi import APIRouter, status

from app.deps import AdminUser, DbSession
from app.schemas.admin import (
    AdminCodeGroupOut,
    AdminCodeOut,
    CodeCreate,
    CodeGroupCreate,
    CodeGroupUpdate,
    CodeUpdate,
)
from app.services.admin import codes as service

router = APIRouter(prefix="/api/v1/admin", tags=["admin"])


@router.get("/code-groups", response_model=list[AdminCodeGroupOut])
async def list_code_groups(user: AdminUser, session: DbSession) -> list[AdminCodeGroupOut]:
    return await service.list_code_groups(session)


@router.post(
    "/code-groups", response_model=AdminCodeGroupOut, status_code=status.HTTP_201_CREATED
)
async def create_code_group(
    payload: CodeGroupCreate, user: AdminUser, session: DbSession
) -> AdminCodeGroupOut:
    return await service.create_code_group(session, payload=payload)


@router.patch("/code-groups/{group_id}", response_model=AdminCodeGroupOut)
async def update_code_group(
    group_id: int, payload: CodeGroupUpdate, user: AdminUser, session: DbSession
) -> AdminCodeGroupOut:
    return await service.update_code_group(session, group_id=group_id, payload=payload)


@router.delete("/code-groups/{group_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_code_group(group_id: int, user: AdminUser, session: DbSession) -> None:
    await service.delete_code_group(session, group_id=group_id)


@router.post(
    "/code-groups/{group_id}/codes",
    response_model=AdminCodeOut,
    status_code=status.HTTP_201_CREATED,
)
async def create_code(
    group_id: int, payload: CodeCreate, user: AdminUser, session: DbSession
) -> AdminCodeOut:
    return await service.create_code(session, group_id=group_id, payload=payload)


@router.patch("/codes/{code_id}", response_model=AdminCodeOut)
async def update_code(
    code_id: int, payload: CodeUpdate, user: AdminUser, session: DbSession
) -> AdminCodeOut:
    return await service.update_code(session, code_id=code_id, payload=payload)


@router.delete("/codes/{code_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_code(code_id: int, user: AdminUser, session: DbSession) -> None:
    await service.delete_code(session, code_id=code_id)
```

- [ ] **Step 5: 표와 main.py**

`SCOPE_REQUIREMENTS`에 추가:

```python
    ("GET", "/api/v1/admin/code-groups"): _AD,
    ("POST", "/api/v1/admin/code-groups"): _AD,
    ("PATCH", "/api/v1/admin/code-groups/{group_id}"): _AD,
    ("DELETE", "/api/v1/admin/code-groups/{group_id}"): _AD,
    ("POST", "/api/v1/admin/code-groups/{group_id}/codes"): _AD,
    ("PATCH", "/api/v1/admin/codes/{code_id}"): _AD,
    ("DELETE", "/api/v1/admin/codes/{code_id}"): _AD,
```

`main.py`:

```python
from app.routers.admin import codes as admin_codes
...
app.include_router(admin_codes.router)
```

- [ ] **Step 6: 통과를 확인한다**

```bash
cd /Users/namkon/projects/skon-biztrip-web/backend && uv run pytest tests/test_admin_codes_api.py tests/test_codes_api.py -v
```

Expected: 신규 11 passed + 기존 codes 테스트 passed

- [ ] **Step 7: mutation**

`delete_code`의 `if code.is_active:` 블록을 지우고 `test_active_code_cannot_be_deleted`가 실패하는지, `delete_code_group`의 `if group.codes:` 블록을 지우고 `test_group_with_codes_cannot_be_deleted`가 실패하는지 확인한다. 둘 다 원복.

- [ ] **Step 8: 커밋**

```bash
cd /Users/namkon/projects/skon-biztrip-web/backend && uv run pytest -q
cd /Users/namkon/projects/skon-biztrip-web && git add backend/app backend/tests/test_admin_codes_api.py && git commit -m "feat(admin): code group/code CRUD with two-step delete"
```

---

## Task 6: FC / CC CRUD

**Files:**
- Create: `backend/app/services/admin/centers.py`
- Create: `backend/app/routers/admin/centers.py`
- Modify: `backend/app/services/api_scopes.py` (8항목), `backend/app/main.py`
- Test: `backend/tests/test_admin_centers_api.py`

- [ ] **Step 1: 실패하는 테스트를 쓴다**

`backend/tests/test_admin_centers_api.py`:

```python
"""FC/CC Admin CRUD. 참조는 FK가 아니라 코드 문자열이므로 서비스가 직접 센다."""

import pytest


@pytest.mark.parametrize("kind", ["fund-centers", "cost-centers"])
async def test_employee_cannot_read_admin_centers(client, seeded, login_as, kind):
    headers = await login_as("user1@skon.example")

    assert (await client.get(f"/api/v1/admin/{kind}", headers=headers)).status_code == 403


@pytest.mark.parametrize("kind", ["fund-centers", "cost-centers"])
async def test_admin_creates_and_lists_a_center(client, seeded, login_as, kind):
    headers = await login_as("admin@skon.example")

    created = await client.post(
        f"/api/v1/admin/{kind}",
        headers=headers,
        json={"code": "ZZ9999", "name": "테스트센터", "department_id": None},
    )

    assert created.status_code == 201
    listed = (await client.get(f"/api/v1/admin/{kind}", headers=headers)).json()
    assert "ZZ9999" in [row["code"] for row in listed]


async def test_admin_list_includes_inactive_centers(client, seeded, login_as):
    """/api/v1/cost-centers는 활성만 준다. 관리 목록은 비활성도 보여야 한다."""
    headers = await login_as("admin@skon.example")
    created = (
        await client.post(
            "/api/v1/admin/cost-centers",
            headers=headers,
            json={"code": "CC9998", "name": "비활성센터", "is_active": False},
        )
    ).json()

    admin_list = (await client.get("/api/v1/admin/cost-centers", headers=headers)).json()
    public_list = (await client.get("/api/v1/cost-centers", headers=headers)).json()

    assert created["id"] in [row["id"] for row in admin_list]
    assert "CC9998" not in [row["code"] for row in public_list]


async def test_duplicate_center_code_is_409(client, seeded, login_as):
    headers = await login_as("admin@skon.example")

    response = await client.post(
        "/api/v1/admin/cost-centers", headers=headers, json={"code": "CC2100", "name": "중복"}
    )

    assert response.status_code == 409
    body = response.json()["error"]
    assert body["code"] == "DUPLICATE_CENTER_CODE"
    assert body["field"] == "code"


async def test_unknown_department_is_400(client, seeded, login_as):
    headers = await login_as("admin@skon.example")

    response = await client.post(
        "/api/v1/admin/fund-centers",
        headers=headers,
        json={"code": "FC9999", "name": "고아센터", "department_id": 999999},
    )

    assert response.status_code == 400
    body = response.json()["error"]
    assert body["code"] == "INVALID_DEPARTMENT"
    assert body["field"] == "department_id"


async def test_referenced_cost_center_cannot_be_deleted(client, seeded, login_as):
    """시드의 출장들이 CC2100을 쓴다. FK가 없으므로 서비스가 세지 않으면 조용히 지워진다."""
    headers = await login_as("admin@skon.example")
    centers = (await client.get("/api/v1/admin/cost-centers", headers=headers)).json()
    target = next(row for row in centers if row["code"] == "CC2100")

    response = await client.delete(
        f"/api/v1/admin/cost-centers/{target['id']}", headers=headers
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "HAS_DEPENDENTS"


async def test_unreferenced_center_can_be_deleted(client, seeded, login_as):
    headers = await login_as("admin@skon.example")
    created = (
        await client.post(
            "/api/v1/admin/cost-centers", headers=headers, json={"code": "CC9997", "name": "임시"}
        )
    ).json()

    response = await client.delete(
        f"/api/v1/admin/cost-centers/{created['id']}", headers=headers
    )

    assert response.status_code == 204


async def test_deactivating_a_center_blocks_new_trips(client, seeded, login_as):
    """마스터를 끄면 그 값으로는 새 쓰기가 통과하지 못해야 한다."""
    headers = await login_as("admin@skon.example")
    # 출장 생성은 신청자 계정으로 한다 — admin은 manager_id가 없어 결재자 규칙에 걸릴 수 있다.
    author_headers = await login_as("user1@skon.example")
    centers = (await client.get("/api/v1/admin/cost-centers", headers=headers)).json()
    target = next(row for row in centers if row["code"] == "CC2100")

    await client.patch(
        f"/api/v1/admin/cost-centers/{target['id']}", headers=headers, json={"is_active": False}
    )

    response = await client.post(
        "/api/v1/trips",
        headers=author_headers,
        json={
            "title": "비활성 센터",
            "purpose_code": "CUSTOMER",
            "purpose_detail": "점검",
            "destination_type_code": "DOMESTIC",
            "country_code": "KR",
            "city": "울산",
            "start_date": "2026-09-01",
            "end_date": "2026-09-02",
            "transport_code": "AIR",
            "accommodation_code": "HOTEL",
            "cost_center_code": "CC2100",
            "estimated_cost": "300000",
        },
    )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "INVALID_COST_CENTER"


async def test_missing_center_is_404(client, seeded, login_as):
    headers = await login_as("admin@skon.example")

    response = await client.patch(
        "/api/v1/admin/fund-centers/999999", headers=headers, json={"name": "없음"}
    )

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "CENTER_NOT_FOUND"
```

- [ ] **Step 2: 실패를 확인한다**

```bash
cd /Users/namkon/projects/skon-biztrip-web/backend && uv run pytest tests/test_admin_centers_api.py -q
```

Expected: 전부 실패 (404)

- [ ] **Step 3: 서비스를 구현한다**

`backend/app/services/admin/centers.py`:

```python
"""Fund Center / Cost Center CRUD.

두 테이블은 컬럼이 같고 규칙도 같아서 모델을 파라미터로 받는다 (`services/centers.py`와 같은
방식). 코드를 두 벌로 두면 한쪽만 고치는 날이 온다.

삭제 전 참조 검사를 서비스가 직접 하는 이유: 업무 테이블은 센터를 **코드 문자열**로 참조하므로
FK가 없고, `delete_entity`의 IntegrityError 변환이 아무것도 잡지 못한다. 참조처가 3곳뿐이라
열거해서 막을 수 있다 — 이 목록은 새 참조처가 생기면 함께 늘려야 한다.
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.errors import ConflictError, NotFoundError, ValidationError
from app.models import (
    CostCenter,
    Department,
    ExpenseItem,
    ExpenseReport,
    FundCenter,
    Trip,
)
from app.schemas.admin import AdminCenterOut, CenterCreate, CenterUpdate
from app.services.admin.common import assert_unique, delete_entity

CenterModel = type[FundCenter] | type[CostCenter]

#: 모델 -> ((참조 컬럼, 사람이 읽을 이름), ...). FK가 없으므로 이 표가 유일한 방어선이다.
_REFERENCES: dict[CenterModel, tuple[tuple[object, str], ...]] = {
    CostCenter: (
        (Trip.cost_center_code, "출장"),
        (ExpenseReport.cost_center_code, "정산서"),
        (ExpenseItem.cost_center_code, "정산항목"),
    ),
    FundCenter: (
        (ExpenseReport.fund_center_code, "정산서"),
        (ExpenseItem.fund_center_code, "정산항목"),
    ),
}


async def list_centers(session: AsyncSession, model: CenterModel) -> list[AdminCenterOut]:
    """비활성 포함. 활성만 필요한 화면은 기존 `/fund-centers`·`/cost-centers`를 쓴다."""
    rows = (await session.execute(select(model).order_by(model.code))).scalars().all()
    return [AdminCenterOut.model_validate(row) for row in rows]


async def _load(session: AsyncSession, model: CenterModel, center_id: int):
    center = await session.get(model, center_id)
    if center is None:
        raise NotFoundError("CENTER_NOT_FOUND", f"존재하지 않는 센터입니다: {center_id}")
    return center


async def _assert_department(session: AsyncSession, department_id: int | None) -> None:
    if department_id is None:
        return
    if await session.get(Department, department_id) is None:
        raise ValidationError(
            "INVALID_DEPARTMENT",
            f"존재하지 않는 부서입니다: {department_id}",
            field="department_id",
        )


async def create_center(
    session: AsyncSession, model: CenterModel, *, payload: CenterCreate
) -> AdminCenterOut:
    await assert_unique(
        session,
        model.code,
        payload.code,
        code="DUPLICATE_CENTER_CODE",
        message=f"이미 있는 센터 코드입니다: {payload.code}",
        field="code",
    )
    await _assert_department(session, payload.department_id)
    center = model(
        code=payload.code,
        name=payload.name,
        department_id=payload.department_id,
        is_active=payload.is_active,
    )
    session.add(center)
    await session.commit()
    await session.refresh(center)
    return AdminCenterOut.model_validate(center)


async def update_center(
    session: AsyncSession, model: CenterModel, *, center_id: int, payload: CenterUpdate
) -> AdminCenterOut:
    center = await _load(session, model, center_id)
    changes = payload.model_dump(exclude_unset=True)
    if "department_id" in changes:
        await _assert_department(session, changes["department_id"])
    for field, value in changes.items():
        setattr(center, field, value)
    await session.commit()
    await session.refresh(center)
    return AdminCenterOut.model_validate(center)


async def delete_center(session: AsyncSession, model: CenterModel, *, center_id: int) -> None:
    center = await _load(session, model, center_id)
    for column, label in _REFERENCES[model]:
        found = await session.scalar(select(column).where(column == center.code).limit(1))
        if found is not None:
            raise ConflictError(
                "HAS_DEPENDENTS", f"{label}이(가) 이 센터를 참조하고 있어 삭제할 수 없습니다"
            )
    await delete_entity(session, center, message="이 센터를 참조하는 데이터가 있습니다")
```

- [ ] **Step 4: 라우터를 만든다**

`backend/app/routers/admin/centers.py`:

```python
"""FC/CC 라우터. 두 리소스가 같은 서비스를 모델만 바꿔 호출한다.

경로를 하나로 합치고 `kind`를 path 파라미터로 받는 방법은 쓰지 않는다 —
`/admin/{kind}`는 스코프 표에서 두 리소스를 구분할 수 없게 만들고, OpenAPI에서도
어떤 값이 유효한지 드러나지 않는다.
"""

from fastapi import APIRouter, status

from app.deps import AdminUser, DbSession
from app.models import CostCenter, FundCenter
from app.schemas.admin import AdminCenterOut, CenterCreate, CenterUpdate
from app.services.admin import centers as service

router = APIRouter(prefix="/api/v1/admin", tags=["admin"])


@router.get("/fund-centers", response_model=list[AdminCenterOut])
async def list_fund_centers(user: AdminUser, session: DbSession) -> list[AdminCenterOut]:
    return await service.list_centers(session, FundCenter)


@router.post(
    "/fund-centers", response_model=AdminCenterOut, status_code=status.HTTP_201_CREATED
)
async def create_fund_center(
    payload: CenterCreate, user: AdminUser, session: DbSession
) -> AdminCenterOut:
    return await service.create_center(session, FundCenter, payload=payload)


@router.patch("/fund-centers/{center_id}", response_model=AdminCenterOut)
async def update_fund_center(
    center_id: int, payload: CenterUpdate, user: AdminUser, session: DbSession
) -> AdminCenterOut:
    return await service.update_center(
        session, FundCenter, center_id=center_id, payload=payload
    )


@router.delete("/fund-centers/{center_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_fund_center(center_id: int, user: AdminUser, session: DbSession) -> None:
    await service.delete_center(session, FundCenter, center_id=center_id)


@router.get("/cost-centers", response_model=list[AdminCenterOut])
async def list_cost_centers(user: AdminUser, session: DbSession) -> list[AdminCenterOut]:
    return await service.list_centers(session, CostCenter)


@router.post(
    "/cost-centers", response_model=AdminCenterOut, status_code=status.HTTP_201_CREATED
)
async def create_cost_center(
    payload: CenterCreate, user: AdminUser, session: DbSession
) -> AdminCenterOut:
    return await service.create_center(session, CostCenter, payload=payload)


@router.patch("/cost-centers/{center_id}", response_model=AdminCenterOut)
async def update_cost_center(
    center_id: int, payload: CenterUpdate, user: AdminUser, session: DbSession
) -> AdminCenterOut:
    return await service.update_center(
        session, CostCenter, center_id=center_id, payload=payload
    )


@router.delete("/cost-centers/{center_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_cost_center(center_id: int, user: AdminUser, session: DbSession) -> None:
    await service.delete_center(session, CostCenter, center_id=center_id)
```

- [ ] **Step 5: 표와 main.py**

```python
    ("GET", "/api/v1/admin/fund-centers"): _AD,
    ("POST", "/api/v1/admin/fund-centers"): _AD,
    ("PATCH", "/api/v1/admin/fund-centers/{center_id}"): _AD,
    ("DELETE", "/api/v1/admin/fund-centers/{center_id}"): _AD,
    ("GET", "/api/v1/admin/cost-centers"): _AD,
    ("POST", "/api/v1/admin/cost-centers"): _AD,
    ("PATCH", "/api/v1/admin/cost-centers/{center_id}"): _AD,
    ("DELETE", "/api/v1/admin/cost-centers/{center_id}"): _AD,
```

```python
from app.routers.admin import centers as admin_centers
...
app.include_router(admin_centers.router)
```

- [ ] **Step 6: 통과 확인**

```bash
cd /Users/namkon/projects/skon-biztrip-web/backend && uv run pytest tests/test_admin_centers_api.py tests/test_centers_api.py -v
```

Expected: 신규 12 passed(파라미터화 포함) + 기존 centers 테스트 passed

- [ ] **Step 7: mutation**

`delete_center`의 참조 루프를 통째로 지우고 `test_referenced_cost_center_cannot_be_deleted`가 실패하는지 확인한다. 그다음 `_REFERENCES[CostCenter]`에서 `Trip.cost_center_code` 한 줄만 지워도 같은 테스트가 실패하는지 확인한다(표의 항목 하나하나가 실제로 일한다는 증거). 원복.

- [ ] **Step 8: 커밋**

```bash
cd /Users/namkon/projects/skon-biztrip-web/backend && uv run pytest -q
cd /Users/namkon/projects/skon-biztrip-web && git add backend/app backend/tests/test_admin_centers_api.py && git commit -m "feat(admin): fund/cost center CRUD with reference guard"
```

---

## Task 7: 사용자 CRUD + 비밀번호 설정

**Files:**
- Create: `backend/app/services/admin/users.py`
- Create: `backend/app/routers/admin/users.py`
- Modify: `backend/app/deps.py` (`JwtOnlyAdmin` 추가)
- Modify: `backend/app/services/api_scopes.py` (5항목), `backend/app/main.py`
- Test: `backend/tests/test_admin_users_api.py`

- [ ] **Step 1: 실패하는 테스트를 쓴다**

`backend/tests/test_admin_users_api.py`:

```python
"""사용자 Admin CRUD.

삭제는 없다(비활성화만). 비밀번호 설정은 JWT 전용이다 — admin 스코프 키로 남의 비밀번호를
바꿀 수 있으면 그 계정으로 로그인해 전권 키를 발급할 수 있고, 키 관리 API를 JWT 전용으로
막아둔 이유가 통째로 우회된다.
"""

import pytest
from sqlalchemy import event

from app.enums import ApiKeyScope
from tests.factories import make_api_key, make_user


@pytest.fixture
def count_statements(test_engine):
    """실행된 SQL 문 수를 센다. 행 수에 비례해 늘어나면 N+1이다."""
    counter = {"n": 0}

    def before(conn, cursor, statement, parameters, context, executemany):
        counter["n"] += 1

    event.listen(test_engine.sync_engine, "before_cursor_execute", before)
    yield counter
    event.remove(test_engine.sync_engine, "before_cursor_execute", before)


async def test_employee_cannot_list_users(client, seeded, login_as):
    headers = await login_as("user1@skon.example")

    assert (await client.get("/api/v1/admin/users", headers=headers)).status_code == 403


async def test_admin_lists_users_with_names_resolved(client, seeded, login_as):
    headers = await login_as("admin@skon.example")

    response = await client.get("/api/v1/admin/users?size=100", headers=headers)

    assert response.status_code == 200
    body = response.json()
    assert body["total"] >= 14
    user1 = next(row for row in body["items"] if row["email"] == "user1@skon.example")
    assert user1["department_name"]
    assert user1["manager_name"] == "김연구"


async def test_user_list_query_count_does_not_grow_with_rows(
    client, seeded, login_as, count_statements
):
    headers = await login_as("admin@skon.example")
    await client.get("/api/v1/admin/users?size=1", headers=headers)  # 워밍업

    start = count_statements["n"]
    await client.get("/api/v1/admin/users?size=1", headers=headers)
    one_row = count_statements["n"] - start

    start = count_statements["n"]
    await client.get("/api/v1/admin/users?size=100", headers=headers)
    many_rows = count_statements["n"] - start

    assert one_row == many_rows


async def test_user_search_matches_name_email_and_employee_no(client, seeded, login_as):
    headers = await login_as("admin@skon.example")

    for term in ("김연구", "manager1@skon.example", "E0002"):
        response = await client.get(f"/api/v1/admin/users?q={term}", headers=headers)
        emails = [row["email"] for row in response.json()["items"]]
        assert "manager1@skon.example" in emails, term


async def test_admin_creates_a_user_who_can_log_in(client, seeded, login_as):
    headers = await login_as("admin@skon.example")
    departments = (await client.get("/api/v1/admin/departments", headers=headers)).json()

    created = await client.post(
        "/api/v1/admin/users",
        headers=headers,
        json={
            "email": "new.hire@skon.example",
            "password": "skon1234!",
            "name": "신입사원",
            "employee_no": "E9001",
            "department_id": departments[0]["id"],
            "position_code": "STAFF",
        },
    )

    assert created.status_code == 201
    assert created.json()["role"] == "EMPLOYEE"
    login = await client.post(
        "/api/v1/auth/login",
        json={"email": "new.hire@skon.example", "password": "skon1234!"},
    )
    assert login.status_code == 200


async def test_duplicate_email_is_409(client, seeded, login_as):
    headers = await login_as("admin@skon.example")
    departments = (await client.get("/api/v1/admin/departments", headers=headers)).json()

    response = await client.post(
        "/api/v1/admin/users",
        headers=headers,
        json={
            "email": "user1@skon.example",
            "password": "skon1234!",
            "name": "중복",
            "employee_no": "E9002",
            "department_id": departments[0]["id"],
            "position_code": "STAFF",
        },
    )

    assert response.status_code == 409
    body = response.json()["error"]
    assert body["code"] == "DUPLICATE_EMAIL"
    assert body["field"] == "email"


async def test_unknown_position_code_is_400(client, seeded, login_as):
    headers = await login_as("admin@skon.example")
    departments = (await client.get("/api/v1/admin/departments", headers=headers)).json()

    response = await client.post(
        "/api/v1/admin/users",
        headers=headers,
        json={
            "email": "bad.position@skon.example",
            "password": "skon1234!",
            "name": "잘못된직급",
            "employee_no": "E9003",
            "department_id": departments[0]["id"],
            "position_code": "NOT_A_POSITION",
        },
    )

    assert response.status_code == 400
    body = response.json()["error"]
    assert body["code"] == "INVALID_CODE"
    assert body["field"] == "position_code"


async def test_short_password_is_400_not_422(client, seeded, login_as):
    headers = await login_as("admin@skon.example")
    departments = (await client.get("/api/v1/admin/departments", headers=headers)).json()

    response = await client.post(
        "/api/v1/admin/users",
        headers=headers,
        json={
            "email": "short.pw@skon.example",
            "password": "abc",
            "name": "짧은비번",
            "employee_no": "E9004",
            "department_id": departments[0]["id"],
            "position_code": "STAFF",
        },
    )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "PASSWORD_TOO_SHORT"


async def test_korean_password_over_72_bytes_is_400_not_500(client, seeded, login_as):
    """bcrypt 5.x는 72바이트 초과를 자르지 않고 던진다 — 막지 않으면 500이고 Agent가 재시도한다."""
    headers = await login_as("admin@skon.example")
    users = (await client.get("/api/v1/admin/users?size=100", headers=headers)).json()
    target = next(row for row in users["items"] if row["email"] == "user1@skon.example")

    response = await client.post(
        f"/api/v1/admin/users/{target['id']}/password",
        headers=headers,
        json={"password": "가" * 25},
    )

    assert response.status_code == 400
    body = response.json()["error"]
    assert body["code"] == "PASSWORD_TOO_LONG"
    assert body["field"] == "password"


async def test_password_reset_changes_the_login(client, seeded, login_as):
    headers = await login_as("admin@skon.example")
    users = (await client.get("/api/v1/admin/users?size=100", headers=headers)).json()
    target = next(row for row in users["items"] if row["email"] == "user2@skon.example")

    response = await client.post(
        f"/api/v1/admin/users/{target['id']}/password",
        headers=headers,
        json={"password": "새비밀번호1234"},
    )

    assert response.status_code == 204
    login = await client.post(
        "/api/v1/auth/login",
        json={"email": "user2@skon.example", "password": "새비밀번호1234"},
    )
    assert login.status_code == 200


async def test_password_reset_rejects_api_keys(client, seeded, db_session, login_as):
    """admin 스코프 키가 비밀번호를 바꿀 수 있으면 키가 JWT로 승격되는 길이 열린다."""
    headers = await login_as("admin@skon.example")
    users = (await client.get("/api/v1/admin/users?size=100", headers=headers)).json()
    target = next(row for row in users["items"] if row["email"] == "user3@skon.example")

    from sqlalchemy import select

    from app.models import User

    admin = (
        await db_session.execute(select(User).where(User.email == "admin@skon.example"))
    ).scalar_one()
    raw, _ = await make_api_key(db_session, user=admin, scopes=[ApiKeyScope.ADMIN])
    await db_session.commit()

    response = await client.post(
        f"/api/v1/admin/users/{target['id']}/password",
        headers={"X-API-Key": raw},
        json={"password": "키로바꾸기1234"},
    )

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "API_KEY_FORBIDDEN"


async def test_admin_cannot_demote_self(client, seeded, login_as, db_session):
    """마지막 ADMIN이 스스로를 강등하면 복구 경로가 DB 직접 수정뿐이 된다."""
    headers = await login_as("admin@skon.example")
    users = (await client.get("/api/v1/admin/users?size=100", headers=headers)).json()
    me = next(row for row in users["items"] if row["email"] == "admin@skon.example")

    response = await client.patch(
        f"/api/v1/admin/users/{me['id']}", headers=headers, json={"role": "EMPLOYEE"}
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "CANNOT_DEMOTE_SELF"


async def test_admin_cannot_deactivate_self(client, seeded, login_as):
    headers = await login_as("admin@skon.example")
    users = (await client.get("/api/v1/admin/users?size=100", headers=headers)).json()
    me = next(row for row in users["items"] if row["email"] == "admin@skon.example")

    response = await client.patch(
        f"/api/v1/admin/users/{me['id']}", headers=headers, json={"is_active": False}
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "CANNOT_DEMOTE_SELF"


async def test_deactivated_user_cannot_log_in(client, seeded, login_as):
    headers = await login_as("admin@skon.example")
    users = (await client.get("/api/v1/admin/users?size=100", headers=headers)).json()
    target = next(row for row in users["items"] if row["email"] == "user4@skon.example")

    await client.patch(
        f"/api/v1/admin/users/{target['id']}", headers=headers, json={"is_active": False}
    )

    login = await client.post(
        "/api/v1/auth/login", json={"email": "user4@skon.example", "password": "skon1234!"}
    )
    assert login.status_code == 401


async def test_manager_cannot_point_at_itself(client, seeded, login_as, db_session):
    headers = await login_as("admin@skon.example")
    victim = await make_user(db_session, name="자기결재")
    await db_session.commit()

    response = await client.patch(
        f"/api/v1/admin/users/{victim.id}", headers=headers, json={"manager_id": victim.id}
    )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "INVALID_MANAGER"


async def test_get_single_user_is_404_when_missing(client, seeded, login_as):
    headers = await login_as("admin@skon.example")

    response = await client.get("/api/v1/admin/users/999999", headers=headers)

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "USER_NOT_FOUND"
```

- [ ] **Step 2: 실패를 확인한다**

```bash
uv run pytest tests/test_admin_users_api.py -q
```

Expected: 전부 실패 (404 / ImportError)

- [ ] **Step 3: `JwtOnlyAdmin` 의존성을 추가한다**

`backend/app/deps.py`의 `JwtOnlyUser` 아래:

```python
async def require_jwt_admin(request: Request, user: AdminUser) -> User:
    """관리자이면서 **로그인 세션**일 것. 비밀번호 설정 전용이다.

    admin 스코프 키가 남의 비밀번호를 바꿀 수 있으면, 그 계정으로 로그인해 JWT를 얻고
    JWT로 전권 키를 발급할 수 있다. 키 관리 API를 JWT 전용으로 둔 방어가 통째로 우회된다.
    """
    if getattr(request.state, "auth_method", None) != "jwt":
        raise ForbiddenError("API_KEY_FORBIDDEN", "이 작업은 로그인 세션에서만 가능합니다")
    return user


JwtOnlyAdmin = Annotated[User, Depends(require_jwt_admin)]
```

- [ ] **Step 4: 서비스를 구현한다**

`backend/app/services/admin/users.py`:

```python
"""사용자 마스터 CRUD.

삭제 엔드포인트가 없는 이유: `user.id`는 trip·expense_report·corporate_card·api_key·
activity_log가 참조한다. 삭제는 사실상 항상 409이고, 감사 흔적을 지우는 것도 옳지 않다.
비활성화(`is_active=false`)가 유일한 종료 경로이며 로그인이 즉시 막힌다.

이름 해석(부서명·결재자명)은 행마다 조회하지 않는다. `id.in_(...)` 일괄 조회 2번으로
끝내며, 그 사실을 쿼리 수 테스트가 고정한다.
"""

from dataclasses import dataclass

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.enums import UserRole
from app.errors import ConflictError, NotFoundError, ValidationError
from app.models import Department, User
from app.schemas.admin import AdminUserCreate, AdminUserOut, AdminUserUpdate, PasswordSet
from app.schemas.common import Page
from app.security import hash_password
from app.services.admin.common import assert_password_length, assert_unique
from app.services.codes import validate_codes

#: 직급은 공통코드 POSITION 그룹에서만 나온다. 모든 쓰기 경로가 이 검증을 지난다.
_POSITION_GROUP = "POSITION"


@dataclass(frozen=True)
class UserFilters:
    q: str | None = None
    department_id: int | None = None
    role: UserRole | None = None
    is_active: bool | None = None
    page: int = 1
    size: int = 20


async def _to_out(session: AsyncSession, users: list[User]) -> list[AdminUserOut]:
    department_ids = {user.department_id for user in users}
    manager_ids = {user.manager_id for user in users if user.manager_id is not None}

    department_names: dict[int, str] = {}
    if department_ids:
        rows = await session.execute(
            select(Department.id, Department.name).where(Department.id.in_(department_ids))
        )
        department_names = {row[0]: row[1] for row in rows}

    manager_names: dict[int, str] = {}
    if manager_ids:
        rows = await session.execute(select(User.id, User.name).where(User.id.in_(manager_ids)))
        manager_names = {row[0]: row[1] for row in rows}

    return [
        AdminUserOut(
            id=user.id,
            email=user.email,
            name=user.name,
            employee_no=user.employee_no,
            department_id=user.department_id,
            department_name=department_names.get(user.department_id, ""),
            position_code=user.position_code,
            manager_id=user.manager_id,
            manager_name=manager_names.get(user.manager_id) if user.manager_id else None,
            role=user.role,
            is_active=user.is_active,
        )
        for user in users
    ]


async def list_users(session: AsyncSession, *, filters: UserFilters) -> Page[AdminUserOut]:
    conditions = []
    if filters.q:
        # 출장 목록의 q와 같은 판단: LIKE 와일드카드를 이스케이프하지 않는다(데모 범위).
        pattern = f"%{filters.q}%"
        conditions.append(
            or_(
                User.name.ilike(pattern),
                User.email.ilike(pattern),
                User.employee_no.ilike(pattern),
            )
        )
    if filters.department_id is not None:
        conditions.append(User.department_id == filters.department_id)
    if filters.role is not None:
        conditions.append(User.role == filters.role)
    if filters.is_active is not None:
        conditions.append(User.is_active.is_(filters.is_active))

    total = await session.scalar(
        select(func.count()).select_from(User).where(*conditions)
    )
    rows = (
        (
            await session.execute(
                select(User)
                .where(*conditions)
                .order_by(User.employee_no)
                .offset((filters.page - 1) * filters.size)
                .limit(filters.size)
            )
        )
        .scalars()
        .all()
    )
    return Page(
        items=await _to_out(session, list(rows)),
        total=total or 0,
        page=filters.page,
        size=filters.size,
    )


async def _load(session: AsyncSession, user_id: int) -> User:
    user = await session.get(User, user_id)
    if user is None:
        raise NotFoundError("USER_NOT_FOUND", f"존재하지 않는 사용자입니다: {user_id}")
    return user


async def get_user(session: AsyncSession, *, user_id: int) -> AdminUserOut:
    user = await _load(session, user_id)
    return (await _to_out(session, [user]))[0]


async def _assert_department(session: AsyncSession, department_id: int) -> None:
    if await session.get(Department, department_id) is None:
        raise ValidationError(
            "INVALID_DEPARTMENT",
            f"존재하지 않는 부서입니다: {department_id}",
            field="department_id",
        )


async def _assert_manager(
    session: AsyncSession, manager_id: int | None, *, self_id: int | None = None
) -> None:
    if manager_id is None:
        return
    if self_id is not None and manager_id == self_id:
        raise ValidationError(
            "INVALID_MANAGER", "자기 자신을 결재자로 지정할 수 없습니다", field="manager_id"
        )
    if await session.get(User, manager_id) is None:
        raise ValidationError(
            "INVALID_MANAGER", f"존재하지 않는 결재자입니다: {manager_id}", field="manager_id"
        )


async def create_user(session: AsyncSession, *, payload: AdminUserCreate) -> AdminUserOut:
    assert_password_length(payload.password)
    await assert_unique(
        session,
        User.email,
        payload.email,
        code="DUPLICATE_EMAIL",
        message=f"이미 사용 중인 이메일입니다: {payload.email}",
        field="email",
    )
    await assert_unique(
        session,
        User.employee_no,
        payload.employee_no,
        code="DUPLICATE_EMPLOYEE_NO",
        message=f"이미 사용 중인 사번입니다: {payload.employee_no}",
        field="employee_no",
    )
    await _assert_department(session, payload.department_id)
    await _assert_manager(session, payload.manager_id)
    await validate_codes(session, [(_POSITION_GROUP, "position_code", payload.position_code)])

    user = User(
        email=payload.email,
        password_hash=hash_password(payload.password),
        name=payload.name,
        employee_no=payload.employee_no,
        department_id=payload.department_id,
        position_code=payload.position_code,
        manager_id=payload.manager_id,
        role=payload.role,
        is_active=payload.is_active,
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return (await _to_out(session, [user]))[0]


async def update_user(
    session: AsyncSession, *, actor: User, user_id: int, payload: AdminUserUpdate
) -> AdminUserOut:
    user = await _load(session, user_id)
    changes = payload.model_dump(exclude_unset=True)

    # 자기 자신을 강등·비활성화하면 아무도 Admin 화면에 들어갈 수 없게 될 수 있다.
    # 복구 경로가 DB 직접 수정뿐이므로 막는다.
    if user.id == actor.id:
        if changes.get("role") not in (None, UserRole.ADMIN):
            raise ConflictError(
                "CANNOT_DEMOTE_SELF", "자기 자신의 관리자 권한을 내릴 수 없습니다", field="role"
            )
        if changes.get("is_active") is False:
            raise ConflictError(
                "CANNOT_DEMOTE_SELF", "자기 자신을 비활성화할 수 없습니다", field="is_active"
            )

    if "department_id" in changes and changes["department_id"] is not None:
        await _assert_department(session, changes["department_id"])
    if "manager_id" in changes:
        await _assert_manager(session, changes["manager_id"], self_id=user.id)
    if "position_code" in changes and changes["position_code"] is not None:
        await validate_codes(
            session, [(_POSITION_GROUP, "position_code", changes["position_code"])]
        )

    for field, value in changes.items():
        setattr(user, field, value)
    await session.commit()
    await session.refresh(user)
    return (await _to_out(session, [user]))[0]


async def set_password(session: AsyncSession, *, user_id: int, payload: PasswordSet) -> None:
    user = await _load(session, user_id)
    assert_password_length(payload.password)
    user.password_hash = hash_password(payload.password)
    await session.commit()
```

- [ ] **Step 5: 라우터를 만든다**

`backend/app/routers/admin/users.py`:

```python
from typing import Annotated

from fastapi import APIRouter, Query, status

from app.deps import AdminUser, DbSession, JwtOnlyAdmin
from app.enums import UserRole
from app.schemas.admin import AdminUserCreate, AdminUserOut, AdminUserUpdate, PasswordSet
from app.schemas.common import Page
from app.services.admin import users as service

router = APIRouter(prefix="/api/v1/admin/users", tags=["admin"])


@router.get("", response_model=Page[AdminUserOut])
async def list_users(
    user: AdminUser,
    session: DbSession,
    q: str | None = None,
    department_id: int | None = None,
    role: UserRole | None = None,
    is_active: bool | None = None,
    page: Annotated[int, Query(ge=1)] = 1,
    size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> Page[AdminUserOut]:
    return await service.list_users(
        session,
        filters=service.UserFilters(
            q=q,
            department_id=department_id,
            role=role,
            is_active=is_active,
            page=page,
            size=size,
        ),
    )


@router.post("", response_model=AdminUserOut, status_code=status.HTTP_201_CREATED)
async def create_user(
    payload: AdminUserCreate, user: AdminUser, session: DbSession
) -> AdminUserOut:
    return await service.create_user(session, payload=payload)


@router.get("/{user_id}", response_model=AdminUserOut)
async def get_user(user_id: int, user: AdminUser, session: DbSession) -> AdminUserOut:
    return await service.get_user(session, user_id=user_id)


@router.patch("/{user_id}", response_model=AdminUserOut)
async def update_user(
    user_id: int, payload: AdminUserUpdate, user: AdminUser, session: DbSession
) -> AdminUserOut:
    return await service.update_user(session, actor=user, user_id=user_id, payload=payload)


@router.post("/{user_id}/password", status_code=status.HTTP_204_NO_CONTENT)
async def set_password(
    user_id: int, payload: PasswordSet, user: JwtOnlyAdmin, session: DbSession
) -> None:
    """**로그인 세션 전용.** API Key로는 호출할 수 없다 — 키가 JWT로 승격되는 경로를 막는다."""
    await service.set_password(session, user_id=user_id, payload=payload)
```

- [ ] **Step 6: 표와 main.py**

```python
    ("GET", "/api/v1/admin/users"): _AD,
    ("POST", "/api/v1/admin/users"): _AD,
    ("GET", "/api/v1/admin/users/{user_id}"): _AD,
    ("PATCH", "/api/v1/admin/users/{user_id}"): _AD,
    ("POST", "/api/v1/admin/users/{user_id}/password"): _AD,
```

```python
from app.routers.admin import users as admin_users
...
app.include_router(admin_users.router)
```

- [ ] **Step 7: 통과 확인**

```bash
cd /Users/namkon/projects/skon-biztrip-web/backend && uv run pytest tests/test_admin_users_api.py -v
```

Expected: 16 passed

- [ ] **Step 8: mutation**

세 가지를 각각 확인한다.

1. `_to_out`의 일괄 조회를 행별 `await session.get(Department, ...)`로 바꾸면 `test_user_list_query_count_does_not_grow_with_rows`가 실패해야 한다.
2. `update_user`의 자기강등 블록을 지우면 `test_admin_cannot_demote_self`와 `test_admin_cannot_deactivate_self`가 실패해야 한다.
3. 라우터의 `JwtOnlyAdmin`을 `AdminUser`로 바꾸면 `test_password_reset_rejects_api_keys`가 실패해야 한다.

셋 다 확인 후 원복하고 `git diff --stat`으로 원복을 눈으로 확인한다.

- [ ] **Step 9: 커밋**

```bash
cd /Users/namkon/projects/skon-biztrip-web/backend && uv run pytest -q
cd /Users/namkon/projects/skon-biztrip-web && git add backend/app backend/tests/test_admin_users_api.py && git commit -m "feat(admin): user CRUD and JWT-only password reset"
```

---

## Task 8: 법인카드 CRUD

**Files:**
- Create: `backend/app/services/admin/cards.py`
- Create: `backend/app/routers/admin/cards.py`
- Modify: `backend/app/services/api_scopes.py` (4항목), `backend/app/main.py`
- Test: `backend/tests/test_admin_cards_api.py`

여기가 `delete_entity`의 **진짜 FK 경로**다. `card_transaction.card_id`는 실제 FK이므로 거래가 있는 카드를 지우면 PostgreSQL이 거부하고, 변환이 없으면 500이 된다.

- [ ] **Step 1: 실패하는 테스트를 쓴다**

`backend/tests/test_admin_cards_api.py`:

```python
"""법인카드 Admin CRUD. card_transaction.card_id가 실제 FK라 삭제 변환이 여기서 검증된다."""

from tests.factories import make_card, make_card_transaction, make_user


async def test_employee_cannot_list_admin_cards(client, seeded, login_as):
    headers = await login_as("user1@skon.example")

    assert (await client.get("/api/v1/admin/cards", headers=headers)).status_code == 403


async def test_admin_sees_all_cards_with_owner_names(client, seeded, login_as):
    """일반 /cards는 **내** 카드만 준다. 관리자는 전부 봐야 한다."""
    headers = await login_as("admin@skon.example")

    response = await client.get("/api/v1/admin/cards", headers=headers)

    assert response.status_code == 200
    rows = response.json()
    assert len(rows) >= 14
    assert all(row["user_name"] for row in rows)


async def test_admin_creates_a_card(client, seeded, login_as):
    headers = await login_as("admin@skon.example")
    users = (await client.get("/api/v1/admin/users?size=1", headers=headers)).json()
    owner_id = users["items"][0]["id"]

    response = await client.post(
        "/api/v1/admin/cards",
        headers=headers,
        json={"user_id": owner_id, "card_no_masked": "1234-****-****-9999", "brand": "신한"},
    )

    assert response.status_code == 201
    assert response.json()["user_id"] == owner_id


async def test_unknown_owner_is_400(client, seeded, login_as):
    headers = await login_as("admin@skon.example")

    response = await client.post(
        "/api/v1/admin/cards",
        headers=headers,
        json={"user_id": 999999, "card_no_masked": "1234-****-****-0000", "brand": "신한"},
    )

    assert response.status_code == 400
    body = response.json()["error"]
    assert body["code"] == "INVALID_USER"
    assert body["field"] == "user_id"


async def test_card_with_transactions_cannot_be_deleted(client, seeded, login_as, db_session):
    """FK 위반이 500이 되면 Agent가 5xx를 재시도한다. 409로 변환돼야 한다."""
    headers = await login_as("admin@skon.example")
    owner = await make_user(db_session)
    card = await make_card(db_session, user=owner)
    await make_card_transaction(db_session, card=card)
    await db_session.commit()

    response = await client.delete(f"/api/v1/admin/cards/{card.id}", headers=headers)

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "HAS_DEPENDENTS"


async def test_card_without_transactions_can_be_deleted(client, seeded, login_as, db_session):
    headers = await login_as("admin@skon.example")
    owner = await make_user(db_session)
    card = await make_card(db_session, user=owner)
    await db_session.commit()

    response = await client.delete(f"/api/v1/admin/cards/{card.id}", headers=headers)

    assert response.status_code == 204


async def test_deactivating_a_card_keeps_it_in_the_admin_list(client, seeded, login_as, db_session):
    headers = await login_as("admin@skon.example")
    owner = await make_user(db_session)
    card = await make_card(db_session, user=owner)
    await db_session.commit()

    response = await client.patch(
        f"/api/v1/admin/cards/{card.id}", headers=headers, json={"is_active": False}
    )

    assert response.status_code == 200
    assert response.json()["is_active"] is False
    rows = (await client.get("/api/v1/admin/cards", headers=headers)).json()
    assert card.id in [row["id"] for row in rows]


async def test_missing_card_is_404(client, seeded, login_as):
    headers = await login_as("admin@skon.example")

    response = await client.patch(
        "/api/v1/admin/cards/999999", headers=headers, json={"brand": "없음"}
    )

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "CARD_NOT_FOUND"
```

먼저 `backend/tests/factories.py`에 `make_card`·`make_card_transaction`이 있는지 확인한다.

```bash
cd /Users/namkon/projects/skon-biztrip-web/backend && grep -n "def make_card" tests/factories.py
```

없으면 아래를 `tests/factories.py`에 추가한다 (이미 있으면 이 단계는 건너뛴다).

```python
async def make_card(
    session: AsyncSession, *, user: User, is_active: bool = True
) -> CorporateCard:
    card = CorporateCard(
        user_id=user.id,
        card_no_masked=f"9{_next():03d}-****-****-0000",
        brand="테스트카드",
        is_active=is_active,
    )
    session.add(card)
    await session.flush()
    return card


async def make_card_transaction(
    session: AsyncSession,
    *,
    card: CorporateCard,
    amount_krw: Decimal = Decimal("10000.00"),
    is_cancelled: bool = False,
) -> CardTransaction:
    transaction = CardTransaction(
        card_id=card.id,
        approved_at=datetime.now(),
        merchant_name=f"테스트가맹점{_next()}",
        merchant_category_code="RESTAURANT",
        amount=amount_krw,
        currency_code="KRW",
        amount_krw=amount_krw,
        is_cancelled=is_cancelled,
    )
    session.add(transaction)
    await session.flush()
    return transaction
```

- [ ] **Step 2: 실패를 확인한다**

```bash
cd /Users/namkon/projects/skon-biztrip-web/backend && uv run pytest tests/test_admin_cards_api.py -q
```

Expected: 전부 실패 (404)

- [ ] **Step 3: 서비스를 구현한다**

`backend/app/services/admin/cards.py`:

```python
"""법인카드 마스터 CRUD.

일반 `/cards`는 **본인** 카드만 준다(소유자 필터를 서비스가 건다). 관리자는 전부 봐야 하므로
필터가 없는 별도 조회를 둔다 — 기존 서비스에 "관리자면 필터 생략" 분기를 넣지 않는다.
그 분기는 언젠가 잘못된 호출자에게도 열린다.
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.errors import NotFoundError, ValidationError
from app.models import CorporateCard, User
from app.schemas.admin import AdminCardCreate, AdminCardOut, AdminCardUpdate
from app.services.admin.common import delete_entity


async def _to_out(session: AsyncSession, cards: list[CorporateCard]) -> list[AdminCardOut]:
    owner_ids = {card.user_id for card in cards}
    names: dict[int, str] = {}
    if owner_ids:
        rows = await session.execute(select(User.id, User.name).where(User.id.in_(owner_ids)))
        names = {row[0]: row[1] for row in rows}
    return [
        AdminCardOut(
            id=card.id,
            user_id=card.user_id,
            user_name=names.get(card.user_id, ""),
            card_no_masked=card.card_no_masked,
            brand=card.brand,
            is_active=card.is_active,
        )
        for card in cards
    ]


async def list_cards(session: AsyncSession) -> list[AdminCardOut]:
    cards = (
        (await session.execute(select(CorporateCard).order_by(CorporateCard.id)))
        .scalars()
        .all()
    )
    return await _to_out(session, list(cards))


async def _load(session: AsyncSession, card_id: int) -> CorporateCard:
    card = await session.get(CorporateCard, card_id)
    if card is None:
        raise NotFoundError("CARD_NOT_FOUND", f"존재하지 않는 카드입니다: {card_id}")
    return card


async def create_card(session: AsyncSession, *, payload: AdminCardCreate) -> AdminCardOut:
    if await session.get(User, payload.user_id) is None:
        raise ValidationError(
            "INVALID_USER", f"존재하지 않는 사용자입니다: {payload.user_id}", field="user_id"
        )
    card = CorporateCard(
        user_id=payload.user_id,
        card_no_masked=payload.card_no_masked,
        brand=payload.brand,
        is_active=payload.is_active,
    )
    session.add(card)
    await session.commit()
    await session.refresh(card)
    return (await _to_out(session, [card]))[0]


async def update_card(
    session: AsyncSession, *, card_id: int, payload: AdminCardUpdate
) -> AdminCardOut:
    card = await _load(session, card_id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(card, field, value)
    await session.commit()
    await session.refresh(card)
    return (await _to_out(session, [card]))[0]


async def delete_card(session: AsyncSession, *, card_id: int) -> None:
    card = await _load(session, card_id)
    await delete_entity(
        session, card, message="이 카드의 거래내역이 있어 삭제할 수 없습니다. 비활성화하세요"
    )
```

- [ ] **Step 4: 라우터를 만든다**

`backend/app/routers/admin/cards.py`:

```python
from fastapi import APIRouter, status

from app.deps import AdminUser, DbSession
from app.schemas.admin import AdminCardCreate, AdminCardOut, AdminCardUpdate
from app.services.admin import cards as service

router = APIRouter(prefix="/api/v1/admin/cards", tags=["admin"])


@router.get("", response_model=list[AdminCardOut])
async def list_cards(user: AdminUser, session: DbSession) -> list[AdminCardOut]:
    return await service.list_cards(session)


@router.post("", response_model=AdminCardOut, status_code=status.HTTP_201_CREATED)
async def create_card(
    payload: AdminCardCreate, user: AdminUser, session: DbSession
) -> AdminCardOut:
    return await service.create_card(session, payload=payload)


@router.patch("/{card_id}", response_model=AdminCardOut)
async def update_card(
    card_id: int, payload: AdminCardUpdate, user: AdminUser, session: DbSession
) -> AdminCardOut:
    return await service.update_card(session, card_id=card_id, payload=payload)


@router.delete("/{card_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_card(card_id: int, user: AdminUser, session: DbSession) -> None:
    await service.delete_card(session, card_id=card_id)
```

- [ ] **Step 5: 표와 main.py**

```python
    ("GET", "/api/v1/admin/cards"): _AD,
    ("POST", "/api/v1/admin/cards"): _AD,
    ("PATCH", "/api/v1/admin/cards/{card_id}"): _AD,
    ("DELETE", "/api/v1/admin/cards/{card_id}"): _AD,
```

```python
from app.routers.admin import cards as admin_cards
...
app.include_router(admin_cards.router)
```

- [ ] **Step 6: 통과 확인**

```bash
cd /Users/namkon/projects/skon-biztrip-web/backend && uv run pytest tests/test_admin_cards_api.py tests/test_cards_api.py -v
```

Expected: 신규 8 passed + 기존 cards 테스트 passed

- [ ] **Step 7: mutation**

`delete_card`의 `delete_entity` 호출을 `await session.delete(card); await session.commit()`로 바꾸면 `test_card_with_transactions_cannot_be_deleted`가 **500**을 받아 실패해야 한다. 이게 이월 항목이 경고한 바로 그 실패다. 원복.

- [ ] **Step 8: 커밋**

```bash
cd /Users/namkon/projects/skon-biztrip-web/backend && uv run pytest -q
cd /Users/namkon/projects/skon-biztrip-web && git add backend/app backend/tests/test_admin_cards_api.py backend/tests/factories.py && git commit -m "feat(admin): corporate card CRUD"
```

---

## Task 9: `admin` 스코프 e2e + OpenAPI 정리

**Files:**
- Modify: `backend/app/services/api_scopes.py` (`SCOPE_DESCRIPTIONS[ADMIN]` 문구)
- Modify: `backend/app/openapi.py` (JWT 전용 경로 집합)
- Test: `backend/tests/test_admin_scope_e2e.py`, `backend/tests/test_openapi.py` (추가)

- [ ] **Step 1: 실패하는 테스트를 쓴다**

`backend/tests/test_admin_scope_e2e.py`:

```python
"""Agent가 admin 스코프 키로 Admin API를 쓰는 경로. 웹과 같은 엔드포인트여야 한다."""

from sqlalchemy import select

from app.enums import ApiKeyScope, UserRole
from app.models import User
from tests.factories import make_api_key, make_user


async def _admin_user(db_session) -> User:
    return (
        await db_session.execute(select(User).where(User.email == "admin@skon.example"))
    ).scalar_one()


async def test_admin_scope_key_can_create_a_department(client, seeded, db_session):
    admin = await _admin_user(db_session)
    raw, _ = await make_api_key(db_session, user=admin, scopes=[ApiKeyScope.ADMIN])
    await db_session.commit()

    response = await client.post(
        "/api/v1/admin/departments",
        headers={"X-API-Key": raw},
        json={"code": "D910", "name": "Agent가 만든 부서"},
    )

    assert response.status_code == 201


async def test_key_without_admin_scope_is_403(client, seeded, db_session):
    admin = await _admin_user(db_session)
    raw, _ = await make_api_key(db_session, user=admin, scopes=[ApiKeyScope.TRIPS_READ])
    await db_session.commit()

    response = await client.get("/api/v1/admin/departments", headers={"X-API-Key": raw})

    assert response.status_code == 403
    body = response.json()["error"]
    assert body["code"] == "SCOPE_REQUIRED"
    assert "admin" in body["message"]


async def test_admin_scope_key_owned_by_an_employee_is_403(client, seeded, db_session):
    """스코프는 권한을 **축소만** 한다. admin 스코프가 역할을 만들어주지는 않는다."""
    employee = await make_user(db_session, role=UserRole.EMPLOYEE)
    raw, _ = await make_api_key(db_session, user=employee, scopes=[ApiKeyScope.ADMIN])
    await db_session.commit()

    response = await client.get("/api/v1/admin/departments", headers={"X-API-Key": raw})

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "FORBIDDEN_ROLE"


async def test_scope_catalog_lists_admin_endpoints(client, seeded, login_as):
    """/developers 가이드가 이 응답을 그리므로, 표가 늘면 가이드가 저절로 따라온다."""
    headers = await login_as("admin@skon.example")

    response = await client.get("/api/v1/scopes", headers=headers)

    admin_entry = next(row for row in response.json() if row["scope"] == "admin")
    assert "GET /api/v1/admin/users" in admin_entry["endpoints"]
    assert "Phase 5" not in admin_entry["description"]
```

`backend/tests/test_openapi.py`에 추가:

```python
async def test_password_endpoint_does_not_advertise_the_api_key_scheme(client):
    """스키마를 기계로 읽는 Agent가 키로 호출해도 된다고 믿으면 안 된다."""
    schema = (await client.get("/openapi.json")).json()
    operation = schema["paths"]["/api/v1/admin/users/{user_id}/password"]["post"]

    assert operation["security"] == [{"BearerAuth": []}]


async def test_admin_operations_declare_the_admin_scope(client):
    schema = (await client.get("/openapi.json")).json()
    operation = schema["paths"]["/api/v1/admin/users"]["get"]

    assert "admin" in operation["description"]
```

- [ ] **Step 2: 실패를 확인한다**

```bash
cd /Users/namkon/projects/skon-biztrip-web/backend && uv run pytest tests/test_admin_scope_e2e.py tests/test_openapi.py -q
```

Expected: `test_scope_catalog_lists_admin_endpoints`와 `test_password_endpoint_does_not_advertise_the_api_key_scheme`가 실패 (설명 문구 / security)

- [ ] **Step 3: 구현한다**

`backend/app/services/api_scopes.py`의 설명 교체:

```python
    ApiKeyScope.ADMIN: "관리자 API — 공통코드·센터·부서·사용자·법인카드 마스터 CRUD",
```

`backend/app/openapi.py`의 JWT 전용 판정을 경로 집합으로 바꾼다.

```python
#: JWT 전용 경로. API Key로는 열리지 않는다 (키가 키를 낳지 못하게, 키가 사람이 되지 못하게).
_JWT_ONLY_PREFIX = "/api/v1/api-keys"
#: 접두어로는 잡히지 않는 개별 경로. 비밀번호 설정은 /admin/users 아래 있지만
#: 그 형제 라우트들은 키로 열려 있어야 한다.
_JWT_ONLY_PATHS = frozenset({"/api/v1/admin/users/{user_id}/password"})


def _is_jwt_only(path: str) -> bool:
    return path.startswith(_JWT_ONLY_PREFIX) or path in _JWT_ONLY_PATHS
```

그리고 오퍼레이션 루프의 분기를 바꾼다.

```python
            if _is_jwt_only(path):
                operation["security"] = _JWT_ONLY_SECURITY
                note = "**로그인 세션 전용** — API Key로는 호출할 수 없습니다."
```

- [ ] **Step 4: 통과 확인**

```bash
cd /Users/namkon/projects/skon-biztrip-web/backend && uv run pytest tests/test_admin_scope_e2e.py tests/test_openapi.py -v
```

Expected: 전부 passed

- [ ] **Step 5: 전체 백엔드 스위트**

```bash
cd /Users/namkon/projects/skon-biztrip-web/backend && uv run pytest -q
```

Expected: 486건 + Phase 5 신규(약 70건) 전부 passed, 실패 0

- [ ] **Step 6: 커밋**

```bash
cd /Users/namkon/projects/skon-biztrip-web && git add backend && git commit -m "feat(admin): admin scope end-to-end and OpenAPI security for password reset"
```

---

## Task 10: 프론트 타입 + Admin API 클라이언트

**Files:**
- Modify: `frontend/src/lib/api/types.ts` (파일 끝에 추가)
- Create: `frontend/src/lib/api/admin.ts`

인증이 필요한 호출은 **전부 `authRequest`**를 쓴다. raw `request`를 쓰면 조용히 미인증 요청이 나가고 그 401은 진짜 인증 실패와 구분되지 않는다.

- [ ] **Step 1: 타입을 추가한다**

`frontend/src/lib/api/types.ts` 끝에 붙인다.

```ts
export interface Department {
	id: number;
	code: string;
	name: string;
	parent_id: number | null;
}

export interface DepartmentInput {
	code: string;
	name: string;
	parent_id?: number | null;
}

export interface AdminCode {
	id: number;
	code: string;
	name: string;
	sort_order: number;
	is_active: boolean;
	extra: Record<string, unknown>;
}

export interface AdminCodeGroup {
	id: number;
	group_code: string;
	name: string;
	description: string | null;
	is_active: boolean;
	codes: AdminCode[];
}

export interface AdminCenter {
	id: number;
	code: string;
	name: string;
	department_id: number | null;
	is_active: boolean;
}

/** FC/CC는 컬럼도 규칙도 같아서 화면 하나가 탭으로 다룬다. */
export type CenterKind = 'fund-centers' | 'cost-centers';

export interface AdminUser {
	id: number;
	email: string;
	name: string;
	employee_no: string;
	department_id: number;
	department_name: string;
	position_code: string;
	manager_id: number | null;
	manager_name: string | null;
	role: UserRole;
	is_active: boolean;
}

export interface AdminUserInput {
	email: string;
	password: string;
	name: string;
	employee_no: string;
	department_id: number;
	position_code: string;
	manager_id?: number | null;
	role?: UserRole;
	is_active?: boolean;
}

export interface AdminUserPatch {
	name?: string;
	department_id?: number;
	position_code?: string;
	manager_id?: number | null;
	role?: UserRole;
	is_active?: boolean;
}

export interface AdminCard {
	id: number;
	user_id: number;
	user_name: string;
	card_no_masked: string;
	brand: string;
	is_active: boolean;
}
```

- [ ] **Step 2: API 클라이언트를 만든다**

`frontend/src/lib/api/admin.ts`:

```ts
import { authRequest } from '$lib/stores/auth.svelte';
import { toQueryString } from './query';
import type {
	AdminCard,
	AdminCenter,
	AdminCode,
	AdminCodeGroup,
	AdminUser,
	AdminUserInput,
	AdminUserPatch,
	CenterKind,
	Department,
	DepartmentInput,
	Page
} from './types';

// --- 부서 -------------------------------------------------------------------

export function listDepartments(): Promise<Department[]> {
	return authRequest<Department[]>('/api/v1/admin/departments');
}

export function createDepartment(input: DepartmentInput): Promise<Department> {
	return authRequest<Department>('/api/v1/admin/departments', { method: 'POST', body: input });
}

export function updateDepartment(
	id: number,
	patch: Partial<DepartmentInput>
): Promise<Department> {
	return authRequest<Department>(`/api/v1/admin/departments/${id}`, {
		method: 'PATCH',
		body: patch
	});
}

export function deleteDepartment(id: number): Promise<void> {
	return authRequest<void>(`/api/v1/admin/departments/${id}`, { method: 'DELETE' });
}

// --- 공통코드 ---------------------------------------------------------------

export function listCodeGroups(): Promise<AdminCodeGroup[]> {
	return authRequest<AdminCodeGroup[]>('/api/v1/admin/code-groups');
}

export function createCodeGroup(input: {
	group_code: string;
	name: string;
	description?: string | null;
}): Promise<AdminCodeGroup> {
	return authRequest<AdminCodeGroup>('/api/v1/admin/code-groups', {
		method: 'POST',
		body: input
	});
}

export function updateCodeGroup(
	id: number,
	patch: { name?: string; description?: string | null; is_active?: boolean }
): Promise<AdminCodeGroup> {
	return authRequest<AdminCodeGroup>(`/api/v1/admin/code-groups/${id}`, {
		method: 'PATCH',
		body: patch
	});
}

export function deleteCodeGroup(id: number): Promise<void> {
	return authRequest<void>(`/api/v1/admin/code-groups/${id}`, { method: 'DELETE' });
}

export function createCode(
	groupId: number,
	input: { code: string; name: string; sort_order?: number }
): Promise<AdminCode> {
	return authRequest<AdminCode>(`/api/v1/admin/code-groups/${groupId}/codes`, {
		method: 'POST',
		body: input
	});
}

export function updateCode(
	id: number,
	patch: { name?: string; sort_order?: number; is_active?: boolean }
): Promise<AdminCode> {
	return authRequest<AdminCode>(`/api/v1/admin/codes/${id}`, { method: 'PATCH', body: patch });
}

export function deleteCode(id: number): Promise<void> {
	return authRequest<void>(`/api/v1/admin/codes/${id}`, { method: 'DELETE' });
}

// --- FC / CC ----------------------------------------------------------------

export function listCenters(kind: CenterKind): Promise<AdminCenter[]> {
	return authRequest<AdminCenter[]>(`/api/v1/admin/${kind}`);
}

export function createCenter(
	kind: CenterKind,
	input: { code: string; name: string; department_id?: number | null }
): Promise<AdminCenter> {
	return authRequest<AdminCenter>(`/api/v1/admin/${kind}`, { method: 'POST', body: input });
}

export function updateCenter(
	kind: CenterKind,
	id: number,
	patch: { name?: string; department_id?: number | null; is_active?: boolean }
): Promise<AdminCenter> {
	return authRequest<AdminCenter>(`/api/v1/admin/${kind}/${id}`, {
		method: 'PATCH',
		body: patch
	});
}

export function deleteCenter(kind: CenterKind, id: number): Promise<void> {
	return authRequest<void>(`/api/v1/admin/${kind}/${id}`, { method: 'DELETE' });
}

// --- 사용자 -----------------------------------------------------------------

export function listUsers(query: { q?: string; page?: number; size?: number } = {}): Promise<
	Page<AdminUser>
> {
	return authRequest<Page<AdminUser>>(`/api/v1/admin/users${toQueryString(query)}`);
}

export function createUser(input: AdminUserInput): Promise<AdminUser> {
	return authRequest<AdminUser>('/api/v1/admin/users', { method: 'POST', body: input });
}

export function updateUser(id: number, patch: AdminUserPatch): Promise<AdminUser> {
	return authRequest<AdminUser>(`/api/v1/admin/users/${id}`, { method: 'PATCH', body: patch });
}

export function setUserPassword(id: number, password: string): Promise<void> {
	return authRequest<void>(`/api/v1/admin/users/${id}/password`, {
		method: 'POST',
		body: { password }
	});
}

// --- 법인카드 ---------------------------------------------------------------

export function listAdminCards(): Promise<AdminCard[]> {
	return authRequest<AdminCard[]>('/api/v1/admin/cards');
}

export function createAdminCard(input: {
	user_id: number;
	card_no_masked: string;
	brand: string;
}): Promise<AdminCard> {
	return authRequest<AdminCard>('/api/v1/admin/cards', { method: 'POST', body: input });
}

export function updateAdminCard(
	id: number,
	patch: { card_no_masked?: string; brand?: string; is_active?: boolean }
): Promise<AdminCard> {
	return authRequest<AdminCard>(`/api/v1/admin/cards/${id}`, { method: 'PATCH', body: patch });
}

export function deleteAdminCard(id: number): Promise<void> {
	return authRequest<void>(`/api/v1/admin/cards/${id}`, { method: 'DELETE' });
}
```

- [ ] **Step 3: 타입체크**

```bash
npm run check
```

Expected: `0 errors / 0 warnings` (경고 0을 유지한다)

- [ ] **Step 4: 커밋**

```bash
cd /Users/namkon/projects/skon-biztrip-web && git add frontend/src/lib/api && git commit -m "feat(admin): frontend types and admin API client"
```

---

## Task 11: `AdminResource` 스토어 + 순수 헬퍼

**Files:**
- Create: `frontend/src/lib/stores/admin-resource.svelte.ts`
- Create: `frontend/src/lib/stores/admin-resource.svelte.test.ts`
- Create: `frontend/src/lib/admin.ts`
- Create: `frontend/src/lib/admin.test.ts`

화면 5개가 같은 중복 제출 가드를 각자 들고 있으면 하나는 반드시 빠진다. 가드를 스토어 하나에 두고 vitest로 고정한다.

- [ ] **Step 1: 실패하는 테스트를 쓴다**

`frontend/src/lib/stores/admin-resource.svelte.test.ts`:

```ts
import { describe, expect, it, vi } from 'vitest';
import { AdminResource } from './admin-resource.svelte';
import { ApiError } from '$lib/api/client';

function deferred<T>() {
	let resolve!: (value: T) => void;
	let reject!: (reason: unknown) => void;
	const promise = new Promise<T>((res, rej) => {
		resolve = res;
		reject = rej;
	});
	return { promise, resolve, reject };
}

describe('AdminResource.load', () => {
	it('fills items and clears loading', async () => {
		const resource = new AdminResource(async () => [1, 2, 3]);

		await resource.load();

		expect(resource.items).toEqual([1, 2, 3]);
		expect(resource.loading).toBe(false);
		expect(resource.error).toBe('');
	});

	it('keeps the ApiError message', async () => {
		const resource = new AdminResource(async () => {
			throw new ApiError(409, 'HAS_DEPENDENTS', '참조가 있어 삭제할 수 없습니다');
		});

		await resource.load();

		expect(resource.error).toBe('참조가 있어 삭제할 수 없습니다');
		expect(resource.loading).toBe(false);
	});

	it('falls back for non-ApiError failures', async () => {
		const resource = new AdminResource(async () => {
			throw new Error('네트워크');
		});

		await resource.load();

		expect(resource.error).toBe('목록을 불러오지 못했습니다');
	});
});

describe('AdminResource.run', () => {
	it('reloads after a successful write', async () => {
		const loader = vi.fn(async () => ['a']);
		const resource = new AdminResource(loader);
		await resource.load();
		loader.mockClear();

		const ok = await resource.run(async () => undefined, '실패');

		expect(ok).toBe(true);
		expect(loader).toHaveBeenCalledTimes(1);
	});

	it('drops a second write while the first is in flight', async () => {
		// 버튼 disabled만으로는 form.requestSubmit() 경로를 막지 못한다.
		// 생성은 멱등하지 않으므로 두 번째 POST가 곧 중복 레코드다.
		const gate = deferred<void>();
		const action = vi.fn(async () => {
			await gate.promise;
		});
		const resource = new AdminResource(async () => []);

		const first = resource.run(action, '실패');
		const second = await resource.run(action, '실패');
		gate.resolve();
		await first;

		expect(second).toBe(false);
		expect(action).toHaveBeenCalledTimes(1);
	});

	it('reports failure and stays usable', async () => {
		const resource = new AdminResource(async () => []);

		const ok = await resource.run(async () => {
			throw new ApiError(400, 'INVALID_CODE', '코드가 잘못되었습니다');
		}, '실패');

		expect(ok).toBe(false);
		expect(resource.error).toBe('코드가 잘못되었습니다');
		expect(resource.busy).toBe(false);
	});
});
```

`frontend/src/lib/admin.test.ts`:

```ts
import { describe, expect, it } from 'vitest';
import { ROLE_LABELS, activeLabel, departmentNameById, departmentOptions } from './admin';
import type { Department } from '$lib/api/types';

const departments: Department[] = [
	{ id: 1, code: 'D100', name: '연구소', parent_id: null },
	{ id: 2, code: 'D110', name: '배터리연구팀', parent_id: 1 }
];

describe('departmentOptions', () => {
	it('labels options with code and name', () => {
		expect(departmentOptions(departments)).toEqual([
			{ value: '1', label: 'D100 · 연구소' },
			{ value: '2', label: 'D110 · 배터리연구팀' }
		]);
	});

	it('can prepend a none option for nullable fields', () => {
		expect(departmentOptions(departments, { noneLabel: '상위 없음' })[0]).toEqual({
			value: '',
			label: '상위 없음'
		});
	});
});

describe('departmentNameById', () => {
	it('resolves a name', () => {
		expect(departmentNameById(departments, 2)).toBe('배터리연구팀');
	});

	it('shows a dash for null', () => {
		expect(departmentNameById(departments, null)).toBe('—');
	});

	it('shows the raw id when the department is unknown', () => {
		expect(departmentNameById(departments, 99)).toBe('#99');
	});
});

describe('labels', () => {
	it('translates roles', () => {
		expect(ROLE_LABELS.MANAGER).toBe('결재자');
	});

	it('translates the active flag', () => {
		expect(activeLabel(true)).toBe('사용');
		expect(activeLabel(false)).toBe('중지');
	});
});
```

- [ ] **Step 2: 실패를 확인한다**

```bash
cd /Users/namkon/projects/skon-biztrip-web/frontend && npm test
```

Expected: 두 파일 모두 "Failed to resolve import" 로 실패

- [ ] **Step 3: 구현한다**

`frontend/src/lib/stores/admin-resource.svelte.ts`:

```ts
import { ApiError } from '$lib/api/client';

export function describeError(error: unknown, fallback: string): string {
	return error instanceof ApiError ? error.message : fallback;
}

/**
 * Admin 화면 5개가 공유하는 목록 상태.
 *
 * 중복 제출 가드를 여기에 두는 이유: 화면마다 `if (submitting) return;`을 손으로 넣으면
 * 언젠가 하나를 빠뜨리고, 생성은 멱등하지 않아 그게 곧 중복 레코드다. 가드가 한 곳에
 * 있으면 테스트도 한 번만 쓰면 된다.
 */
export class AdminResource<T> {
	items = $state<T[]>([]);
	loading = $state(true);
	error = $state('');
	busy = $state(false);

	// 파라미터 프로퍼티(`private readonly loader`) 대신 명시적 필드를 쓴다 —
	// 룬 필드와 섞였을 때 컴파일 순서가 도구에 따라 달라지는 것을 피한다.
	private readonly loader: () => Promise<T[]>;

	constructor(loader: () => Promise<T[]>) {
		this.loader = loader;
	}

	async load(): Promise<void> {
		this.loading = true;
		try {
			this.items = await this.loader();
			this.error = '';
		} catch (error) {
			this.error = describeError(error, '목록을 불러오지 못했습니다');
		} finally {
			this.loading = false;
		}
	}

	/** 쓰기 1건 + 재조회. 진행 중이면 두 번째 호출을 버리고 false를 돌려준다. */
	async run(action: () => Promise<unknown>, failureMessage: string): Promise<boolean> {
		if (this.busy) return false;
		this.busy = true;
		this.error = '';
		try {
			await action();
			await this.load();
			return true;
		} catch (error) {
			this.error = describeError(error, failureMessage);
			return false;
		} finally {
			this.busy = false;
		}
	}
}
```

`frontend/src/lib/admin.ts`:

```ts
import type { Department, UserRole } from '$lib/api/types';

/** Admin 서브탭. `/admin` 레이아웃이 그린다. */
export const ADMIN_TABS = [
	{ href: '/admin/codes', label: '공통코드' },
	{ href: '/admin/centers', label: '센터' },
	{ href: '/admin/departments', label: '부서' },
	{ href: '/admin/users', label: '사용자' },
	{ href: '/admin/cards', label: '법인카드' }
] as const;

export const ROLE_LABELS: Record<UserRole, string> = {
	EMPLOYEE: '사원',
	MANAGER: '결재자',
	ADMIN: '관리자'
};

export function activeLabel(isActive: boolean): string {
	return isActive ? '사용' : '중지';
}

/** Select는 문자열 value만 다루므로 id를 문자열로 낮춘다. */
export function departmentOptions(
	departments: Department[],
	options: { noneLabel?: string } = {}
): { value: string; label: string }[] {
	const rows = departments.map((department) => ({
		value: String(department.id),
		label: `${department.code} · ${department.name}`
	}));
	return options.noneLabel ? [{ value: '', label: options.noneLabel }, ...rows] : rows;
}

/** 목록 표의 부서 칸. 알 수 없는 id를 조용히 빈칸으로 만들지 않는다 — 데이터 이상을 드러낸다. */
export function departmentNameById(departments: Department[], id: number | null): string {
	if (id === null) return '—';
	return departments.find((department) => department.id === id)?.name ?? `#${id}`;
}
```

- [ ] **Step 4: 통과 확인**

```bash
cd /Users/namkon/projects/skon-biztrip-web/frontend && npm test
```

Expected: 기존 60건 + 신규 11건 전부 통과

- [ ] **Step 5: mutation**

`AdminResource.run`의 `if (this.busy) return false;`를 지우고 `npm test`를 돌린다. `drops a second write while the first is in flight`가 **실패**해야 한다. 원복.

- [ ] **Step 6: 커밋**

```bash
cd /Users/namkon/projects/skon-biztrip-web && git add frontend/src/lib && git commit -m "feat(admin): shared admin resource store and pure helpers"
```

---

## Task 12: `/admin` 레이아웃 + 헤더 진입점

**Files:**
- Create: `frontend/src/routes/admin/+layout.svelte`
- Modify: `frontend/src/lib/components/AppShell.svelte` (우측 블록에 링크 1개)

- [ ] **Step 1: 레이아웃을 만든다**

`frontend/src/routes/admin/+layout.svelte`:

```svelte
<script lang="ts">
	import { page } from '$app/state';
	import { goto } from '$app/navigation';
	import { auth } from '$lib/stores/auth.svelte';
	import { ADMIN_TABS } from '$lib/admin';
	import type { Snippet } from 'svelte';

	let { children }: { children: Snippet } = $props();

	// 서버가 403으로 막지만, 화면까지 오면 빈 표와 에러 문구만 보인다.
	// 라우트 가드는 UX용이고 권한의 근거는 서버다.
	const isAdmin = $derived(auth.user?.role === 'ADMIN');

	$effect(() => {
		if (auth.user && !isAdmin) goto('/');
	});

	function isActive(href: string): boolean {
		return page.url.pathname === href || page.url.pathname.startsWith(`${href}/`);
	}
</script>

{#if isAdmin}
	<h1 class="text-display-xl">관리</h1>
	<p class="mt-2 text-body-md text-muted">
		마스터 데이터를 고치면 출장·정산 화면의 드롭다운과 <strong>API 검증</strong>이 함께 바뀝니다.
	</p>

	<nav aria-label="관리 메뉴" class="mt-8 flex gap-6 overflow-x-auto border-b border-hairline">
		{#each ADMIN_TABS as tab (tab.href)}
			<a
				href={tab.href}
				aria-current={isActive(tab.href) ? 'page' : undefined}
				class="shrink-0 pb-3 text-nav-link {isActive(tab.href)
					? 'border-b-2 border-ink text-ink'
					: 'text-muted hover:text-ink'}"
			>
				{tab.label}
			</a>
		{/each}
	</nav>

	<div class="mt-8">
		{@render children()}
	</div>
{/if}
```

- [ ] **Step 2: 헤더에 진입점을 붙인다**

`frontend/src/lib/components/AppShell.svelte`의 `<script>`에 추가한다 (`canApprove` 아래):

```ts
	// 관리 링크는 ADMIN에게만 보인다. 가운데 3-탭은 DESIGN.md 규칙이라 늘리지 않는다.
	const isAdmin = $derived(auth.user?.role === 'ADMIN');
```

우측 블록의 결재함 링크 블록 **아래**에 추가한다:

```svelte
				{#if isAdmin}
					<a
						href="/admin/codes"
						aria-current={isActive('/admin') ? 'page' : undefined}
						class="text-button-sm {isActive('/admin') ? 'text-ink' : 'text-muted hover:text-ink'}"
					>
						관리
					</a>
				{/if}
```

- [ ] **Step 3: 타입체크 + 테스트**

```bash
cd /Users/namkon/projects/skon-biztrip-web/frontend && npm run check && npm test
```

Expected: `0 errors / 0 warnings`, 테스트 71건 통과

- [ ] **Step 4: 커밋**

```bash
cd /Users/namkon/projects/skon-biztrip-web && git add frontend/src && git commit -m "feat(admin): admin layout with role guard and header entry"
```

---

## Task 13: `/admin/codes` 화면

**Files:**
- Create: `frontend/src/routes/admin/codes/+page.svelte`

- [ ] **Step 1: 화면을 만든다**

`frontend/src/routes/admin/codes/+page.svelte`:

```svelte
<script lang="ts">
	import { onMount } from 'svelte';
	import {
		createCode,
		createCodeGroup,
		deleteCode,
		deleteCodeGroup,
		listCodeGroups,
		updateCode,
		updateCodeGroup
	} from '$lib/api/admin';
	import { AdminResource } from '$lib/stores/admin-resource.svelte';
	import { activeLabel } from '$lib/admin';
	import type { AdminCode, AdminCodeGroup } from '$lib/api/types';
	import Badge from '$lib/components/Badge.svelte';
	import Button from '$lib/components/Button.svelte';
	import Card from '$lib/components/Card.svelte';
	import EmptyState from '$lib/components/EmptyState.svelte';
	import TextInput from '$lib/components/TextInput.svelte';

	const groups = new AdminResource<AdminCodeGroup>(listCodeGroups);

	let groupCode = $state('');
	let groupName = $state('');
	let openGroupId = $state<number | null>(null);
	let newCode = $state('');
	let newCodeName = $state('');
	let confirmingGroupId = $state<number | null>(null);
	let confirmingCodeId = $state<number | null>(null);

	// onMount가 Promise를 반환하면 cleanup 함수로 오해될 수 있다. void로 끊는다.
	onMount(() => {
		void groups.load();
	});

	async function submitGroup(event: SubmitEvent): Promise<void> {
		event.preventDefault();
		// 중복 제출 가드는 AdminResource.run 안에 있다.
		const ok = await groups.run(
			() => createCodeGroup({ group_code: groupCode, name: groupName }),
			'코드그룹을 만들지 못했습니다'
		);
		if (ok) {
			groupCode = '';
			groupName = '';
		}
	}

	async function submitCode(event: SubmitEvent, groupId: number): Promise<void> {
		event.preventDefault();
		const ok = await groups.run(
			() => createCode(groupId, { code: newCode, name: newCodeName }),
			'코드를 추가하지 못했습니다'
		);
		if (ok) {
			newCode = '';
			newCodeName = '';
		}
	}

	function toggleGroup(group: AdminCodeGroup): void {
		void groups.run(
			() => updateCodeGroup(group.id, { is_active: !group.is_active }),
			'그룹 상태를 바꾸지 못했습니다'
		);
	}

	function toggleCode(code: AdminCode): void {
		void groups.run(
			() => updateCode(code.id, { is_active: !code.is_active }),
			'코드 상태를 바꾸지 못했습니다'
		);
	}

	async function removeGroup(id: number): Promise<void> {
		const ok = await groups.run(() => deleteCodeGroup(id), '그룹을 삭제하지 못했습니다');
		if (ok) confirmingGroupId = null;
	}

	async function removeCode(id: number): Promise<void> {
		const ok = await groups.run(() => deleteCode(id), '코드를 삭제하지 못했습니다');
		if (ok) confirmingCodeId = null;
	}
</script>

<Card>
	<form onsubmit={submitGroup}>
		<h2 class="text-title-md">새 코드그룹</h2>
		<div class="mt-4 grid grid-cols-1 gap-4 tablet:grid-cols-2">
			<TextInput label="그룹코드" bind:value={groupCode} placeholder="RISK_LEVEL" />
			<TextInput label="이름" bind:value={groupName} placeholder="위험도" />
		</div>
		<div class="mt-6">
			<Button type="submit" disabled={groups.busy || !groupCode || !groupName}>
				{groups.busy ? '처리 중…' : '추가'}
			</Button>
		</div>
	</form>
</Card>

{#if groups.error}
	<p class="mt-6 text-body-sm text-error" role="alert">{groups.error}</p>
{/if}

{#if groups.loading}
	<p class="mt-8 text-body-sm text-muted">불러오는 중…</p>
{:else if groups.items.length === 0}
	<EmptyState title="코드그룹이 없습니다" description="위에서 첫 그룹을 만드세요." />
{:else}
	<div class="mt-8 flex flex-col gap-4">
		{#each groups.items as group (group.id)}
			<Card>
				<div class="flex flex-wrap items-center justify-between gap-3">
					<div class="flex items-center gap-3">
						<span class="font-mono text-body-md text-ink">{group.group_code}</span>
						<span class="text-body-sm text-muted">{group.name}</span>
						<Badge tone={group.is_active ? 'success' : 'neutral'}>
							{activeLabel(group.is_active)}
						</Badge>
						<span class="text-caption text-muted">코드 {group.codes.length}개</span>
					</div>
					<div class="flex items-center gap-3">
						<Button
							variant="tertiary"
							onclick={() => (openGroupId = openGroupId === group.id ? null : group.id)}
						>
							{openGroupId === group.id ? '접기' : '코드 보기'}
						</Button>
						<Button variant="tertiary" onclick={() => toggleGroup(group)}>
							{group.is_active ? '중지' : '사용'}
						</Button>
						{#if confirmingGroupId === group.id}
							<Button variant="tertiary" onclick={() => removeGroup(group.id)}>정말 삭제</Button>
							<Button variant="tertiary" onclick={() => (confirmingGroupId = null)}>취소</Button>
						{:else}
							<Button variant="tertiary" onclick={() => (confirmingGroupId = group.id)}>
								삭제
							</Button>
						{/if}
					</div>
				</div>

				{#if openGroupId === group.id}
					<div class="mt-6 overflow-x-auto">
						<table class="w-full min-w-[560px] border-collapse">
							<thead>
								<tr class="border-b border-hairline text-left text-caption text-muted">
									<th class="py-3">코드</th>
									<th class="py-3">이름</th>
									<th class="py-3">정렬</th>
									<th class="py-3">상태</th>
									<th class="py-3"></th>
								</tr>
							</thead>
							<tbody>
								{#each group.codes as code (code.id)}
									<tr class="border-b border-hairline">
										<td class="py-3 font-mono text-body-sm text-ink">{code.code}</td>
										<td class="py-3 text-body-sm text-ink">{code.name}</td>
										<td class="py-3 text-body-sm text-muted">{code.sort_order}</td>
										<td class="py-3">
											<Badge tone={code.is_active ? 'success' : 'neutral'}>
												{activeLabel(code.is_active)}
											</Badge>
										</td>
										<td class="py-3 text-right">
											<Button variant="tertiary" onclick={() => toggleCode(code)}>
												{code.is_active ? '중지' : '사용'}
											</Button>
											{#if confirmingCodeId === code.id}
												<Button variant="tertiary" onclick={() => removeCode(code.id)}>
													정말 삭제
												</Button>
												<Button variant="tertiary" onclick={() => (confirmingCodeId = null)}>
													취소
												</Button>
											{:else}
												<Button variant="tertiary" onclick={() => (confirmingCodeId = code.id)}>
													삭제
												</Button>
											{/if}
										</td>
									</tr>
								{/each}
							</tbody>
						</table>
					</div>

					<form onsubmit={(event) => submitCode(event, group.id)} class="mt-6">
						<div class="grid grid-cols-1 gap-4 tablet:grid-cols-2">
							<TextInput label="새 코드" bind:value={newCode} placeholder="HIGH" />
							<TextInput label="새 코드 이름" bind:value={newCodeName} placeholder="높음" />
						</div>
						<div class="mt-4">
							<Button type="submit" disabled={groups.busy || !newCode || !newCodeName}>
								코드 추가
							</Button>
						</div>
					</form>
					<p class="mt-3 text-caption text-muted">
						활성 코드는 삭제할 수 없습니다 — 업무 데이터가 코드값을 문자열로 참조하므로 먼저 중지해야
						합니다.
					</p>
				{/if}
			</Card>
		{/each}
	</div>
{/if}
```

- [ ] **Step 2: 타입체크**

```bash
cd /Users/namkon/projects/skon-biztrip-web/frontend && npm run check
```

Expected: `0 errors / 0 warnings`

- [ ] **Step 3: 커밋**

```bash
cd /Users/namkon/projects/skon-biztrip-web && git add frontend/src/routes/admin && git commit -m "feat(admin): code group and code management screen"
```

---

## Task 14: `/admin/centers` 화면 (FC/CC 탭)

**Files:**
- Create: `frontend/src/routes/admin/centers/+page.svelte`

- [ ] **Step 1: 화면을 만든다**

`frontend/src/routes/admin/centers/+page.svelte`:

```svelte
<script lang="ts">
	import { onMount } from 'svelte';
	import {
		createCenter,
		deleteCenter,
		listCenters,
		listDepartments,
		updateCenter
	} from '$lib/api/admin';
	import { AdminResource } from '$lib/stores/admin-resource.svelte';
	import { activeLabel, departmentNameById, departmentOptions } from '$lib/admin';
	import type { AdminCenter, CenterKind, Department } from '$lib/api/types';
	import Badge from '$lib/components/Badge.svelte';
	import Button from '$lib/components/Button.svelte';
	import Card from '$lib/components/Card.svelte';
	import EmptyState from '$lib/components/EmptyState.svelte';
	import Select from '$lib/components/Select.svelte';
	import TextInput from '$lib/components/TextInput.svelte';

	const KINDS: { value: CenterKind; label: string }[] = [
		{ value: 'fund-centers', label: 'Fund Center (비용처리)' },
		{ value: 'cost-centers', label: 'Cost Center (비용사용)' }
	];

	let kind = $state<CenterKind>('fund-centers');
	// 로더가 kind를 클로저로 읽으므로 탭을 바꾸고 load()만 다시 부르면 된다.
	const centers = new AdminResource<AdminCenter>(() => listCenters(kind));
	const departments = new AdminResource<Department>(listDepartments);

	let code = $state('');
	let name = $state('');
	let departmentId = $state('');
	let confirmingId = $state<number | null>(null);

	onMount(() => {
		void departments.load();
	});

	$effect(() => {
		void kind;
		void centers.load();
	});

	const departmentChoices = $derived(
		departmentOptions(departments.items, { noneLabel: '부서 없음' })
	);

	async function submit(event: SubmitEvent): Promise<void> {
		event.preventDefault();
		const ok = await centers.run(
			() =>
				createCenter(kind, {
					code,
					name,
					department_id: departmentId ? Number(departmentId) : null
				}),
			'센터를 만들지 못했습니다'
		);
		if (ok) {
			code = '';
			name = '';
			departmentId = '';
		}
	}

	function toggle(center: AdminCenter): void {
		void centers.run(
			() => updateCenter(kind, center.id, { is_active: !center.is_active }),
			'상태를 바꾸지 못했습니다'
		);
	}

	async function remove(id: number): Promise<void> {
		const ok = await centers.run(() => deleteCenter(kind, id), '삭제하지 못했습니다');
		if (ok) confirmingId = null;
	}
</script>

<div class="flex gap-3">
	{#each KINDS as option (option.value)}
		<button
			type="button"
			onclick={() => (kind = option.value)}
			aria-pressed={kind === option.value}
			class="rounded-full px-5 py-2.5 text-button-sm {kind === option.value
				? 'bg-ink text-white'
				: 'border border-hairline text-ink hover:shadow-float'}"
		>
			{option.label}
		</button>
	{/each}
</div>

<Card>
	<form onsubmit={submit}>
		<h2 class="text-title-md">새 센터</h2>
		<div class="mt-4 grid grid-cols-1 gap-4 tablet:grid-cols-3">
			<TextInput label="코드" bind:value={code} placeholder="FC1090" />
			<TextInput label="이름" bind:value={name} placeholder="배터리연구소" />
			<Select
				label="부서"
				bind:value={departmentId}
				options={departmentChoices}
				placeholder="부서 없음"
			/>
		</div>
		<div class="mt-6">
			<Button type="submit" disabled={centers.busy || !code || !name}>
				{centers.busy ? '처리 중…' : '추가'}
			</Button>
		</div>
	</form>
</Card>

{#if centers.error}
	<p class="mt-6 text-body-sm text-error" role="alert">{centers.error}</p>
{/if}

{#if centers.loading}
	<p class="mt-8 text-body-sm text-muted">불러오는 중…</p>
{:else if centers.items.length === 0}
	<EmptyState title="센터가 없습니다" description="위에서 첫 센터를 만드세요." />
{:else}
	<div class="mt-8 overflow-x-auto">
		<table class="w-full min-w-[640px] border-collapse">
			<thead>
				<tr class="border-b border-hairline text-left text-caption text-muted">
					<th class="py-3">코드</th>
					<th class="py-3">이름</th>
					<th class="py-3">부서</th>
					<th class="py-3">상태</th>
					<th class="py-3"></th>
				</tr>
			</thead>
			<tbody>
				{#each centers.items as center (center.id)}
					<tr class="border-b border-hairline">
						<td class="py-3 font-mono text-body-sm text-ink">{center.code}</td>
						<td class="py-3 text-body-sm text-ink">{center.name}</td>
						<td class="py-3 text-body-sm text-muted">
							{departmentNameById(departments.items, center.department_id)}
						</td>
						<td class="py-3">
							<Badge tone={center.is_active ? 'success' : 'neutral'}>
								{activeLabel(center.is_active)}
							</Badge>
						</td>
						<td class="py-3 text-right">
							<Button variant="tertiary" onclick={() => toggle(center)}>
								{center.is_active ? '중지' : '사용'}
							</Button>
							{#if confirmingId === center.id}
								<Button variant="tertiary" onclick={() => remove(center.id)}>정말 삭제</Button>
								<Button variant="tertiary" onclick={() => (confirmingId = null)}>취소</Button>
							{:else}
								<Button variant="tertiary" onclick={() => (confirmingId = center.id)}>삭제</Button>
							{/if}
						</td>
					</tr>
				{/each}
			</tbody>
		</table>
	</div>
	<p class="mt-3 text-caption text-muted">
		출장·정산서가 참조하는 센터는 삭제되지 않습니다(409). 쓰지 않으려면 중지하세요.
	</p>
{/if}
```

- [ ] **Step 2: 타입체크 + 커밋**

```bash
cd /Users/namkon/projects/skon-biztrip-web/frontend && npm run check
cd /Users/namkon/projects/skon-biztrip-web && git add frontend/src/routes/admin && git commit -m "feat(admin): fund/cost center management screen"
```

---

## Task 15: `/admin/departments` 화면

**Files:**
- Create: `frontend/src/routes/admin/departments/+page.svelte`

- [ ] **Step 1: 화면을 만든다**

`frontend/src/routes/admin/departments/+page.svelte`:

```svelte
<script lang="ts">
	import { onMount } from 'svelte';
	import {
		createDepartment,
		deleteDepartment,
		listDepartments,
		updateDepartment
	} from '$lib/api/admin';
	import { AdminResource } from '$lib/stores/admin-resource.svelte';
	import { departmentNameById, departmentOptions } from '$lib/admin';
	import type { Department } from '$lib/api/types';
	import Button from '$lib/components/Button.svelte';
	import Card from '$lib/components/Card.svelte';
	import EmptyState from '$lib/components/EmptyState.svelte';
	import Select from '$lib/components/Select.svelte';
	import TextInput from '$lib/components/TextInput.svelte';

	const departments = new AdminResource<Department>(listDepartments);

	let code = $state('');
	let name = $state('');
	let parentId = $state('');
	let editingId = $state<number | null>(null);
	let editingName = $state('');
	let confirmingId = $state<number | null>(null);

	onMount(() => {
		void departments.load();
	});

	const parentChoices = $derived(
		departmentOptions(departments.items, { noneLabel: '상위 없음' })
	);

	async function submit(event: SubmitEvent): Promise<void> {
		event.preventDefault();
		const ok = await departments.run(
			() =>
				createDepartment({ code, name, parent_id: parentId ? Number(parentId) : null }),
			'부서를 만들지 못했습니다'
		);
		if (ok) {
			code = '';
			name = '';
			parentId = '';
		}
	}

	function startEdit(department: Department): void {
		editingId = department.id;
		editingName = department.name;
	}

	async function saveEdit(id: number): Promise<void> {
		const ok = await departments.run(
			() => updateDepartment(id, { name: editingName }),
			'이름을 바꾸지 못했습니다'
		);
		if (ok) editingId = null;
	}

	async function remove(id: number): Promise<void> {
		const ok = await departments.run(() => deleteDepartment(id), '삭제하지 못했습니다');
		if (ok) confirmingId = null;
	}
</script>

<Card>
	<form onsubmit={submit}>
		<h2 class="text-title-md">새 부서</h2>
		<div class="mt-4 grid grid-cols-1 gap-4 tablet:grid-cols-3">
			<TextInput label="부서코드" bind:value={code} placeholder="D400" />
			<TextInput label="이름" bind:value={name} placeholder="품질보증팀" />
			<Select
				label="상위 부서"
				bind:value={parentId}
				options={parentChoices}
				placeholder="상위 없음"
			/>
		</div>
		<div class="mt-6">
			<Button type="submit" disabled={departments.busy || !code || !name}>
				{departments.busy ? '처리 중…' : '추가'}
			</Button>
		</div>
	</form>
</Card>

{#if departments.error}
	<p class="mt-6 text-body-sm text-error" role="alert">{departments.error}</p>
{/if}

{#if departments.loading}
	<p class="mt-8 text-body-sm text-muted">불러오는 중…</p>
{:else if departments.items.length === 0}
	<EmptyState title="부서가 없습니다" description="위에서 첫 부서를 만드세요." />
{:else}
	<div class="mt-8 overflow-x-auto">
		<table class="w-full min-w-[600px] border-collapse">
			<thead>
				<tr class="border-b border-hairline text-left text-caption text-muted">
					<th class="py-3">코드</th>
					<th class="py-3">이름</th>
					<th class="py-3">상위</th>
					<th class="py-3"></th>
				</tr>
			</thead>
			<tbody>
				{#each departments.items as department (department.id)}
					<tr class="border-b border-hairline">
						<td class="py-3 font-mono text-body-sm text-ink">{department.code}</td>
						<td class="py-3 text-body-sm text-ink">
							{#if editingId === department.id}
								<TextInput label="이름" bind:value={editingName} />
							{:else}
								{department.name}
							{/if}
						</td>
						<td class="py-3 text-body-sm text-muted">
							{departmentNameById(departments.items, department.parent_id)}
						</td>
						<td class="py-3 text-right">
							{#if editingId === department.id}
								<Button variant="tertiary" onclick={() => saveEdit(department.id)}>저장</Button>
								<Button variant="tertiary" onclick={() => (editingId = null)}>취소</Button>
							{:else}
								<Button variant="tertiary" onclick={() => startEdit(department)}>이름 변경</Button>
								{#if confirmingId === department.id}
									<Button variant="tertiary" onclick={() => remove(department.id)}>
										정말 삭제
									</Button>
									<Button variant="tertiary" onclick={() => (confirmingId = null)}>취소</Button>
								{:else}
									<Button variant="tertiary" onclick={() => (confirmingId = department.id)}>
										삭제
									</Button>
								{/if}
							{/if}
						</td>
					</tr>
				{/each}
			</tbody>
		</table>
	</div>
	<p class="mt-3 text-caption text-muted">
		사용자·센터가 속한 부서는 삭제되지 않습니다(409 HAS_DEPENDENTS).
	</p>
{/if}
```

- [ ] **Step 2: 타입체크 + 커밋**

```bash
cd /Users/namkon/projects/skon-biztrip-web/frontend && npm run check
cd /Users/namkon/projects/skon-biztrip-web && git add frontend/src/routes/admin && git commit -m "feat(admin): department management screen"
```

---

## Task 16: `/admin/users` 화면

**Files:**
- Create: `frontend/src/routes/admin/users/+page.svelte`

- [ ] **Step 1: 화면을 만든다**

`frontend/src/routes/admin/users/+page.svelte`:

```svelte
<script lang="ts">
	import { onMount } from 'svelte';
	import {
		createUser,
		listDepartments,
		listUsers,
		setUserPassword,
		updateUser
	} from '$lib/api/admin';
	import { AdminResource } from '$lib/stores/admin-resource.svelte';
	import { ROLE_LABELS, activeLabel, departmentOptions } from '$lib/admin';
	import { auth } from '$lib/stores/auth.svelte';
	import type { AdminUser, Department, UserRole } from '$lib/api/types';
	import Badge from '$lib/components/Badge.svelte';
	import Button from '$lib/components/Button.svelte';
	import Card from '$lib/components/Card.svelte';
	import EmptyState from '$lib/components/EmptyState.svelte';
	import Select from '$lib/components/Select.svelte';
	import TextInput from '$lib/components/TextInput.svelte';

	const ROLE_OPTIONS: { value: UserRole; label: string }[] = [
		{ value: 'EMPLOYEE', label: ROLE_LABELS.EMPLOYEE },
		{ value: 'MANAGER', label: ROLE_LABELS.MANAGER },
		{ value: 'ADMIN', label: ROLE_LABELS.ADMIN }
	];

	let search = $state('');
	// 목록은 페이지 응답이므로 items만 뽑아 AdminResource에 담는다.
	const users = new AdminResource<AdminUser>(async () => {
		const page = await listUsers({ q: search || undefined, size: 100 });
		return page.items;
	});
	const departments = new AdminResource<Department>(listDepartments);

	let email = $state('');
	let password = $state('');
	let name = $state('');
	let employeeNo = $state('');
	let departmentId = $state('');
	let positionCode = $state('STAFF');
	// Select의 bind:value는 string이다. UserRole로 선언하면 svelte-check가 에러를 낸다.
	let role = $state('EMPLOYEE');

	let resettingId = $state<number | null>(null);
	let newPassword = $state('');

	onMount(() => {
		void departments.load();
		void users.load();
	});

	const departmentChoices = $derived(departmentOptions(departments.items));

	async function submit(event: SubmitEvent): Promise<void> {
		event.preventDefault();
		const ok = await users.run(
			() =>
				createUser({
					email,
					password,
					name,
					employee_no: employeeNo,
					department_id: Number(departmentId),
					position_code: positionCode,
					role: role as UserRole
				}),
			'사용자를 만들지 못했습니다'
		);
		if (ok) {
			email = '';
			password = '';
			name = '';
			employeeNo = '';
			departmentId = '';
			role = 'EMPLOYEE';
		}
	}

	function toggleActive(user: AdminUser): void {
		void users.run(
			() => updateUser(user.id, { is_active: !user.is_active }),
			'상태를 바꾸지 못했습니다'
		);
	}

	function changeRole(user: AdminUser, next: UserRole): void {
		void users.run(() => updateUser(user.id, { role: next }), '역할을 바꾸지 못했습니다');
	}

	async function resetPassword(id: number): Promise<void> {
		const ok = await users.run(
			() => setUserPassword(id, newPassword),
			'비밀번호를 바꾸지 못했습니다'
		);
		if (ok) {
			resettingId = null;
			newPassword = '';
		}
	}
</script>

<Card>
	<form onsubmit={submit}>
		<h2 class="text-title-md">새 사용자</h2>
		<div class="mt-4 grid grid-cols-1 gap-4 tablet:grid-cols-3">
			<TextInput label="이메일" type="email" bind:value={email} placeholder="name@skon.example" />
			<TextInput label="이름" bind:value={name} placeholder="김출장" />
			<TextInput label="사번" bind:value={employeeNo} placeholder="E0100" />
			<Select label="부서" bind:value={departmentId} options={departmentChoices} />
			<TextInput label="직급코드" bind:value={positionCode} placeholder="STAFF" />
			<Select label="역할" bind:value={role} options={ROLE_OPTIONS} />
			<TextInput
				label="초기 비밀번호"
				type="password"
				bind:value={password}
				placeholder="8자 이상 · UTF-8 72바이트 이하"
			/>
		</div>
		<div class="mt-6">
			<Button
				type="submit"
				disabled={users.busy || !email || !name || !employeeNo || !departmentId || !password}
			>
				{users.busy ? '처리 중…' : '추가'}
			</Button>
		</div>
	</form>
</Card>

{#if users.error}
	<p class="mt-6 text-body-sm text-error" role="alert">{users.error}</p>
{/if}

<div class="mt-8 flex items-end gap-3">
	<div class="w-full max-w-md">
		<TextInput label="검색" bind:value={search} placeholder="이름 · 이메일 · 사번" />
	</div>
	<Button variant="secondary" onclick={() => users.load()}>검색</Button>
</div>

{#if users.loading}
	<p class="mt-8 text-body-sm text-muted">불러오는 중…</p>
{:else if users.items.length === 0}
	<EmptyState title="사용자가 없습니다" description="검색어를 바꾸거나 새 사용자를 추가하세요." />
{:else}
	<div class="mt-6 overflow-x-auto">
		<table class="w-full min-w-[900px] border-collapse">
			<thead>
				<tr class="border-b border-hairline text-left text-caption text-muted">
					<th class="py-3">사번</th>
					<th class="py-3">이름</th>
					<th class="py-3">이메일</th>
					<th class="py-3">부서</th>
					<th class="py-3">결재자</th>
					<th class="py-3">역할</th>
					<th class="py-3">상태</th>
					<th class="py-3"></th>
				</tr>
			</thead>
			<tbody>
				{#each users.items as user (user.id)}
					<tr class="border-b border-hairline">
						<td class="py-3 font-mono text-body-sm text-muted">{user.employee_no}</td>
						<td class="py-3 text-body-sm text-ink">{user.name}</td>
						<td class="py-3 text-body-sm text-muted">{user.email}</td>
						<td class="py-3 text-body-sm text-muted">{user.department_name}</td>
						<td class="py-3 text-body-sm text-muted">{user.manager_name ?? '—'}</td>
						<td class="py-3">
							<select
								aria-label="{user.name} 역할"
								value={user.role}
								onchange={(event) => changeRole(user, event.currentTarget.value as UserRole)}
								class="h-10 rounded-sm border border-hairline bg-canvas px-2 text-body-sm text-ink"
							>
								{#each ROLE_OPTIONS as option (option.value)}
									<option value={option.value}>{option.label}</option>
								{/each}
							</select>
						</td>
						<td class="py-3">
							<Badge tone={user.is_active ? 'success' : 'neutral'}>
								{activeLabel(user.is_active)}
							</Badge>
						</td>
						<td class="py-3 text-right">
							{#if resettingId === user.id}
								<div class="flex items-center justify-end gap-2">
									<input
										type="password"
										bind:value={newPassword}
										aria-label="{user.name} 새 비밀번호"
										class="h-10 rounded-sm border border-hairline px-2 text-body-sm"
									/>
									<Button variant="tertiary" onclick={() => resetPassword(user.id)}>저장</Button>
									<Button variant="tertiary" onclick={() => (resettingId = null)}>취소</Button>
								</div>
							{:else}
								<Button variant="tertiary" onclick={() => (resettingId = user.id)}>
									비밀번호
								</Button>
								<Button
									variant="tertiary"
									disabled={user.id === auth.user?.id}
									onclick={() => toggleActive(user)}
								>
									{user.is_active ? '비활성화' : '활성화'}
								</Button>
							{/if}
						</td>
					</tr>
				{/each}
			</tbody>
		</table>
	</div>
	<p class="mt-3 text-caption text-muted">
		사용자는 삭제할 수 없습니다 — 출장·정산·카드가 참조합니다. 비활성화하면 로그인이 즉시 막힙니다.
		자기 자신은 강등·비활성화할 수 없습니다(409).
	</p>
{/if}
```

- [ ] **Step 2: 타입체크 + 커밋**

```bash
cd /Users/namkon/projects/skon-biztrip-web/frontend && npm run check
cd /Users/namkon/projects/skon-biztrip-web && git add frontend/src/routes/admin && git commit -m "feat(admin): user management screen"
```

---

## Task 17: `/admin/cards` 화면

**Files:**
- Create: `frontend/src/routes/admin/cards/+page.svelte`

- [ ] **Step 1: 화면을 만든다**

`frontend/src/routes/admin/cards/+page.svelte`:

```svelte
<script lang="ts">
	import { onMount } from 'svelte';
	import {
		createAdminCard,
		deleteAdminCard,
		listAdminCards,
		listUsers,
		updateAdminCard
	} from '$lib/api/admin';
	import { AdminResource } from '$lib/stores/admin-resource.svelte';
	import { activeLabel } from '$lib/admin';
	import type { AdminCard, AdminUser } from '$lib/api/types';
	import Badge from '$lib/components/Badge.svelte';
	import Button from '$lib/components/Button.svelte';
	import Card from '$lib/components/Card.svelte';
	import EmptyState from '$lib/components/EmptyState.svelte';
	import Select from '$lib/components/Select.svelte';
	import TextInput from '$lib/components/TextInput.svelte';

	const cards = new AdminResource<AdminCard>(listAdminCards);
	const users = new AdminResource<AdminUser>(async () => (await listUsers({ size: 100 })).items);

	let ownerId = $state('');
	let cardNo = $state('');
	let brand = $state('');
	let confirmingId = $state<number | null>(null);

	onMount(() => {
		void users.load();
		void cards.load();
	});

	const ownerChoices = $derived(
		users.items.map((user) => ({
			value: String(user.id),
			label: `${user.name} · ${user.employee_no}`
		}))
	);

	async function submit(event: SubmitEvent): Promise<void> {
		event.preventDefault();
		const ok = await cards.run(
			() =>
				createAdminCard({
					user_id: Number(ownerId),
					card_no_masked: cardNo,
					brand
				}),
			'카드를 만들지 못했습니다'
		);
		if (ok) {
			ownerId = '';
			cardNo = '';
			brand = '';
		}
	}

	function toggle(card: AdminCard): void {
		void cards.run(
			() => updateAdminCard(card.id, { is_active: !card.is_active }),
			'상태를 바꾸지 못했습니다'
		);
	}

	async function remove(id: number): Promise<void> {
		const ok = await cards.run(() => deleteAdminCard(id), '삭제하지 못했습니다');
		if (ok) confirmingId = null;
	}
</script>

<Card>
	<form onsubmit={submit}>
		<h2 class="text-title-md">새 법인카드</h2>
		<div class="mt-4 grid grid-cols-1 gap-4 tablet:grid-cols-3">
			<Select label="소유자" bind:value={ownerId} options={ownerChoices} placeholder="사용자 선택" />
			<TextInput label="카드번호(마스킹)" bind:value={cardNo} placeholder="5327-****-****-1234" />
			<TextInput label="브랜드" bind:value={brand} placeholder="신한" />
		</div>
		<div class="mt-6">
			<Button type="submit" disabled={cards.busy || !ownerId || !cardNo || !brand}>
				{cards.busy ? '처리 중…' : '추가'}
			</Button>
		</div>
	</form>
</Card>

{#if cards.error}
	<p class="mt-6 text-body-sm text-error" role="alert">{cards.error}</p>
{/if}

{#if cards.loading}
	<p class="mt-8 text-body-sm text-muted">불러오는 중…</p>
{:else if cards.items.length === 0}
	<EmptyState title="법인카드가 없습니다" description="위에서 첫 카드를 등록하세요." />
{:else}
	<div class="mt-8 overflow-x-auto">
		<table class="w-full min-w-[720px] border-collapse">
			<thead>
				<tr class="border-b border-hairline text-left text-caption text-muted">
					<th class="py-3">소유자</th>
					<th class="py-3">카드번호</th>
					<th class="py-3">브랜드</th>
					<th class="py-3">상태</th>
					<th class="py-3"></th>
				</tr>
			</thead>
			<tbody>
				{#each cards.items as card (card.id)}
					<tr class="border-b border-hairline">
						<td class="py-3 text-body-sm text-ink">{card.user_name}</td>
						<td class="py-3 font-mono text-body-sm text-muted">{card.card_no_masked}</td>
						<td class="py-3 text-body-sm text-muted">{card.brand}</td>
						<td class="py-3">
							<Badge tone={card.is_active ? 'success' : 'neutral'}>
								{activeLabel(card.is_active)}
							</Badge>
						</td>
						<td class="py-3 text-right">
							<Button variant="tertiary" onclick={() => toggle(card)}>
								{card.is_active ? '중지' : '사용'}
							</Button>
							{#if confirmingId === card.id}
								<Button variant="tertiary" onclick={() => remove(card.id)}>정말 삭제</Button>
								<Button variant="tertiary" onclick={() => (confirmingId = null)}>취소</Button>
							{:else}
								<Button variant="tertiary" onclick={() => (confirmingId = card.id)}>삭제</Button>
							{/if}
						</td>
					</tr>
				{/each}
			</tbody>
		</table>
	</div>
	<p class="mt-3 text-caption text-muted">거래내역이 있는 카드는 삭제되지 않습니다(409). 중지하세요.</p>
{/if}
```

- [ ] **Step 2: 타입체크 + 전체 프론트 테스트**

```bash
cd /Users/namkon/projects/skon-biztrip-web/frontend && npm run check && npm test && npm run build
```

Expected: `0 errors / 0 warnings`, 테스트 71건 통과, 빌드 성공

- [ ] **Step 3: 커밋**

```bash
cd /Users/namkon/projects/skon-biztrip-web && git add frontend/src/routes/admin && git commit -m "feat(admin): corporate card management screen"
```

---

## Task 18: 744px 반응형 — 헤더 햄버거 시트

**Files:**
- Modify: `frontend/src/app.css` (`@theme`에 breakpoint 1줄)
- Modify: `frontend/src/lib/components/AppShell.svelte` (헤더 전체)

DESIGN.md 522·534행: 744px 미만에서 상단 내비는 로고 + 햄버거로 접히고 제품 탭은 시트 뒤로 들어간다. 지금은 뼈대가 없어 375px에서 탭이 두 줄로 깨지고 우측 블록이 화면 밖으로 나간다.

- [ ] **Step 1: breakpoint를 정의한다**

`frontend/src/app.css`의 `@theme` 블록 안, `--font-sans` 위에 추가한다.

```css
	/* DESIGN.md breakpoints — 744px 미만은 모바일(햄버거 시트).
	   기존 md:(768px)는 그대로 둔다. --breakpoint-md를 덮으면 13개 화면의 그리드가 함께 움직인다. */
	--breakpoint-tablet: 744px;
```

- [ ] **Step 2: AppShell을 반응형으로 바꾼다**

`frontend/src/lib/components/AppShell.svelte`를 아래 내용으로 통째로 교체한다.

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
	const isAdmin = $derived(auth.user?.role === 'ADMIN');

	let menuOpen = $state(false);

	// 라우트가 바뀔 때마다 미읽음 수를 새로 센다. 상신·승인이 다른 화면에서
	// 일어나므로 마운트 시 한 번만 세면 뱃지가 곧 낡는다.
	$effect(() => {
		void page.url.pathname;
		void notifications.refresh();
	});

	// 내비게이션이 끝나면 시트를 닫는다. 열어둔 채로 화면이 바뀌면 뒤 화면이 가려진다.
	$effect(() => {
		void page.url.pathname;
		menuOpen = false;
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

<div class="min-h-screen bg-canvas">
	<header
		class="grid h-20 grid-cols-[1fr_auto] items-center border-b border-hairline px-4 tablet:grid-cols-[1fr_auto_1fr] tablet:px-8"
	>
		<a href="/" class="flex items-center justify-self-start">
			<img src="/skon-logo.png" alt="SK온 출장시스템" class="h-8 w-auto" />
		</a>

		<nav aria-label="주 메뉴" class="hidden items-center justify-self-center gap-8 tablet:flex">
			{#each tabs as tab (tab.href)}
				<a
					href={tab.href}
					aria-current={isActive(tab.href) ? 'page' : undefined}
					class="pb-1 text-nav-link {isActive(tab.href)
						? 'border-b-2 border-ink text-ink'
						: 'text-muted hover:text-ink'}"
				>
					{tab.label}
				</a>
			{/each}
		</nav>

		<div class="hidden items-center justify-self-end gap-4 tablet:flex">
			{#if auth.user}
				<a
					href="/cards"
					aria-current={isActive('/cards') ? 'page' : undefined}
					class="text-button-sm {isActive('/cards') ? 'text-ink' : 'text-muted hover:text-ink'}"
				>
					카드
				</a>
				{#if canApprove}
					<a
						href="/approvals"
						aria-current={isActive('/approvals') ? 'page' : undefined}
						class="text-button-sm {isActive('/approvals')
							? 'text-ink'
							: 'text-muted hover:text-ink'}"
					>
						결재함
					</a>
				{/if}
				{#if isAdmin}
					<a
						href="/admin/codes"
						aria-current={isActive('/admin') ? 'page' : undefined}
						class="text-button-sm {isActive('/admin') ? 'text-ink' : 'text-muted hover:text-ink'}"
					>
						관리
					</a>
				{/if}
				<a
					href="/notifications"
					aria-label="알림"
					class="relative flex h-10 w-10 items-center justify-center rounded-full hover:shadow-float"
				>
					<svg
						viewBox="0 0 24 24"
						class="h-5 w-5"
						fill="none"
						stroke="currentColor"
						stroke-width="2"
					>
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
				<span class="text-body-sm text-muted">{auth.user.name} · {auth.user.department_name}</span>
				<button
					onclick={signOut}
					class="h-10 rounded-full border border-hairline px-4 text-button-sm text-ink hover:shadow-float"
				>
					로그아웃
				</button>
			{/if}
		</div>

		<!-- 744px 미만: 로고 + 햄버거만 남긴다 (DESIGN.md Mobile 행). -->
		<button
			type="button"
			onclick={() => (menuOpen = !menuOpen)}
			aria-expanded={menuOpen}
			aria-controls="mobile-menu"
			aria-label="메뉴"
			class="relative flex h-10 w-10 items-center justify-center justify-self-end rounded-full hover:shadow-float tablet:hidden"
		>
			<svg viewBox="0 0 24 24" class="h-5 w-5" fill="none" stroke="currentColor" stroke-width="2">
				<path d="M4 7h16M4 12h16M4 17h16" stroke-linecap="round" />
			</svg>
			{#if notifications.unread > 0}
				<span
					class="absolute top-0 right-0 flex h-4 min-w-4 items-center justify-center rounded-full bg-primary px-1 text-badge text-white"
				>
					{notifications.unread > 99 ? '99+' : notifications.unread}
				</span>
			{/if}
		</button>
	</header>

	{#if menuOpen && auth.user}
		<div id="mobile-menu" class="border-b border-hairline px-4 py-4 tablet:hidden">
			<nav aria-label="모바일 메뉴" class="flex flex-col gap-1">
				{#each tabs as tab (tab.href)}
					<a href={tab.href} class="py-3 text-nav-link text-ink">{tab.label}</a>
				{/each}
				<a href="/cards" class="py-3 text-nav-link text-ink">카드</a>
				{#if canApprove}
					<a href="/approvals" class="py-3 text-nav-link text-ink">결재함</a>
				{/if}
				{#if isAdmin}
					<a href="/admin/codes" class="py-3 text-nav-link text-ink">관리</a>
				{/if}
				<a href="/notifications" class="py-3 text-nav-link text-ink">
					알림{notifications.unread > 0 ? ` (${notifications.unread})` : ''}
				</a>
			</nav>
			<div class="mt-4 flex items-center justify-between border-t border-hairline pt-4">
				<span class="text-body-sm text-muted">
					{auth.user.name} · {auth.user.department_name}
				</span>
				<button
					onclick={signOut}
					class="h-10 rounded-full border border-hairline px-4 text-button-sm text-ink"
				>
					로그아웃
				</button>
			</div>
		</div>
	{/if}

	<main class="mx-auto max-w-[1280px] px-4 py-8 tablet:px-8 tablet:py-12">
		{@render children()}
	</main>
</div>
```

- [ ] **Step 3: 타입체크 + 빌드**

```bash
cd /Users/namkon/projects/skon-biztrip-web/frontend && npm run check && npm run build
```

Expected: `0 errors / 0 warnings`, 빌드 성공

- [ ] **Step 4: 실제 폭에서 확인한다**

`npm run dev` 후 브라우저 개발자도구에서 375px·744px·1280px 세 폭을 본다. 확인 항목:

1. 375px — 헤더에 로고와 햄버거만 있고 가로 스크롤이 없다.
2. 375px — 햄버거를 누르면 시트가 열리고 탭·카드·결재함·관리·알림이 세로로 보인다.
3. 375px — 시트에서 링크를 누르면 이동 후 시트가 닫힌다.
4. 744px — 가운데 3-탭과 우측 블록이 다시 보이고 햄버거는 사라진다.
5. 1280px — Phase 4까지의 모양과 동일하다.

브라우저 도구가 없는 환경이면 **확인했다고 적지 말고** Task 22의 미확인 목록에 넣는다.

- [ ] **Step 5: 커밋**

```bash
cd /Users/namkon/projects/skon-biztrip-web && git add frontend/src/app.css frontend/src/lib/components/AppShell.svelte && git commit -m "feat(ui): collapse header to a hamburger sheet below 744px"
```

---

## Task 19: 744px 반응형 — 표 가로 스크롤

**Files:**
- Modify: `frontend/src/lib/components/CardTransactionTable.svelte:16`
- Modify: `frontend/src/lib/components/ExpenseItemsTable.svelte:31`
- Modify: `frontend/src/routes/settings/api-keys/+page.svelte:199`
- Modify: `frontend/src/routes/developers/+page.svelte:104,161`

그리드는 이미 `grid-cols-1`이 기본이라 좁은 화면에서 1열로 떨어진다. 남은 것은 표다 — 넓은 표는 폭을 줄이면 셀이 뭉개지거나 화면 밖으로 나간다. **열을 숨기지 않는다**: 관리자·정산 표에서 열을 감추면 무엇이 빠졌는지 알 수 없다. 컨테이너에 가로 스크롤을 주고 표에 최소 폭을 준다.

- [ ] **Step 1: 다섯 군데를 같은 방식으로 고친다**

각 `<table class="...">`를 아래 모양으로 감싼다. 최소 폭은 열 수에 맞춘다 (열당 약 110px, 아래 값 사용).

| 파일 | 최소 폭 |
|---|---|
| `CardTransactionTable.svelte` | `min-w-[720px]` |
| `ExpenseItemsTable.svelte` | `min-w-[860px]` |
| `settings/api-keys/+page.svelte` | `min-w-[860px]` |
| `developers/+page.svelte` (104행, 스코프 표) | `min-w-[640px]` |
| `developers/+page.svelte` (161행, 에러 표) | `min-w-[560px]` |

예 — `CardTransactionTable.svelte`:

```svelte
<div class="overflow-x-auto">
	<table class="w-full min-w-[720px] border-collapse">
		<!-- 기존 내용 그대로 -->
	</table>
</div>
```

`settings/api-keys/+page.svelte`의 표는 `mt-4`를 감싸는 div로 옮긴다:

```svelte
<div class="mt-4 overflow-x-auto">
	<table class="w-full min-w-[860px] border-collapse">
```

`developers/+page.svelte`의 두 표도 같은 방식이며 `mt-4`를 바깥 div로 옮긴다.

- [ ] **Step 2: 편집이 실제로 반영됐는지 확인한다**

```bash
cd /Users/namkon/projects/skon-biztrip-web/frontend && grep -rn "overflow-x-auto" src | sed 's|^src/||'
```

Expected: 위 5곳 + Task 13~17에서 만든 admin 화면 5곳 + admin 레이아웃 탭 1곳이 모두 나온다 (총 11줄 이상)

- [ ] **Step 3: 타입체크 · 테스트 · 빌드**

```bash
cd /Users/namkon/projects/skon-biztrip-web/frontend && npm run check && npm test && npm run build
```

Expected: `0 errors / 0 warnings`, 71건 통과, 빌드 성공

- [ ] **Step 4: 커밋**

```bash
cd /Users/namkon/projects/skon-biztrip-web && git add frontend/src && git commit -m "feat(ui): let wide tables scroll horizontally on narrow screens"
```

---

## Task 20: 배포 이미지 빌드 · 기동 검증

**Files:** 없음 (검증 태스크). 실패하면 원인 파일을 고친다.

- [ ] **Step 1: 백엔드가 임포트 단계에서 뜨는지 먼저 본다**

```bash
cd /Users/namkon/projects/skon-biztrip-web/backend && uv run python -c "import app.main; print('routes', len(app.main.app.routes))"
```

Expected: `routes` 뒤에 숫자. `RuntimeError: SCOPE_REQUIREMENTS가 실제 라우트와 어긋납니다`가 나오면 표에서 빠진 항목을 채운다 (에러 메시지가 어느 쪽인지 알려준다).

- [ ] **Step 2: 이미지를 빌드하고 띄운다**

```bash
cd /Users/namkon/projects/skon-biztrip-web && docker compose -p skon-prod up -d --build
```

Expected: 3서비스(backend·frontend·ingress) `Started`. DB는 스택 밖이다.

Docker Engine 20.10.9 이하라면 백엔드가 `can't start new thread`로 죽는다(기본 seccomp에 `clone3` 없음). 그때는:

```bash
docker compose -p skon-prod -f docker-compose.yml -f docker-compose.old-docker.yml up -d --build
```

- [ ] **Step 3: 헬스체크**

```bash
curl -s http://localhost/api/v1/health && echo && curl -s http://localhost/api/v1/health/db
```

Expected: `{"status":"ok"}` 와 `{"status":"ok","host":...,"schema":...}` — schema가 `DB_SCHEMA`와 같아야 한다.

- [ ] **Step 4: 스키마를 갱신한다 (새 테이블은 없지만 확인한다)**

Phase 5는 새 테이블을 만들지 않는다. `init-db`는 없는 테이블만 만들므로 안전하게 확인만 한다.

```bash
cd /Users/namkon/projects/skon-biztrip-web/backend && uv run python -m app.cli check
```

Expected: 접속 성공 메시지

- [ ] **Step 5: 정적 자산이 서빙되는지 본다**

```bash
curl -s -o /dev/null -w "%{http_code}\n" http://localhost/
curl -s -o /dev/null -w "%{http_code}\n" http://localhost/admin/codes
```

Expected: 둘 다 `200` (SPA fallback이 동작한다)

- [ ] **Step 6: 결과를 기록한다**

성공/실패와 사용한 compose 파일 조합을 Task 23의 phase-status 갱신에 쓸 수 있게 적어 둔다. 실패했다면 여기서 멈추고 원인을 고친 뒤 다시 돌린다.

---

## Task 21: 실서버 curl 시나리오 (Agent 경로)

**Files:** 없음 (검증 태스크)

Phase 2·3·4와 같은 방식으로, 사람이 화면에서 하는 일을 Agent가 그대로 하는지 확인한다. 아래를 순서대로 실행하고 각 Expected를 눈으로 대조한다.

- [ ] **Step 1: 관리자 로그인**

```bash
TOKEN=$(curl -s -X POST http://localhost/api/v1/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"email":"admin@skon.example","password":"skon1234!"}' | python3 -c 'import sys,json;print(json.load(sys.stdin)["access_token"])')
echo "${TOKEN:0:12}…"
```

Expected: 토큰 앞부분이 출력된다

- [ ] **Step 2: 부서 생성 → 중복 → 삭제 불가**

```bash
curl -s -X POST http://localhost/api/v1/admin/departments -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' -d '{"code":"D500","name":"검증팀"}'
echo
curl -s -X POST http://localhost/api/v1/admin/departments -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' -d '{"code":"D500","name":"중복"}'
echo
curl -s -o /dev/null -w "%{http_code}\n" -X DELETE http://localhost/api/v1/admin/departments/1 \
  -H "Authorization: Bearer $TOKEN"
```

Expected: 201 바디 / `DUPLICATE_DEPARTMENT_CODE` + `"field":"code"` / `409` (D100에 사용자가 있다)

- [ ] **Step 3: admin 스코프 키를 발급해 같은 일을 시킨다**

```bash
KEY=$(curl -s -X POST http://localhost/api/v1/api-keys -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' -d '{"name":"운영 Agent","scopes":["admin"]}' \
  | python3 -c 'import sys,json;print(json.load(sys.stdin)["key"])')
curl -s -X POST http://localhost/api/v1/admin/code-groups -H "X-API-Key: $KEY" \
  -H 'Content-Type: application/json' -d '{"group_code":"RISK_LEVEL","name":"위험도"}'
```

Expected: 201 — **웹 화면과 같은 엔드포인트**를 키가 그대로 쓴다

- [ ] **Step 4: 스코프·역할·JWT 전용의 세 가지 거부를 확인한다**

```bash
# 1) 스코프 없는 키
TRIPKEY=$(curl -s -X POST http://localhost/api/v1/api-keys -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' -d '{"name":"출장 전용","scopes":["trips:read"]}' \
  | python3 -c 'import sys,json;print(json.load(sys.stdin)["key"])')
curl -s http://localhost/api/v1/admin/users -H "X-API-Key: $TRIPKEY"; echo

# 2) 관리자가 아닌 사람의 JWT
UTOKEN=$(curl -s -X POST http://localhost/api/v1/auth/login -H 'Content-Type: application/json' \
  -d '{"email":"user1@skon.example","password":"skon1234!"}' \
  | python3 -c 'import sys,json;print(json.load(sys.stdin)["access_token"])')
curl -s http://localhost/api/v1/admin/users -H "Authorization: Bearer $UTOKEN"; echo

# 3) admin 스코프 키로 비밀번호 변경 시도
curl -s -X POST http://localhost/api/v1/admin/users/2/password -H "X-API-Key: $KEY" \
  -H 'Content-Type: application/json' -d '{"password":"newpassword123"}'; echo
```

Expected: `SCOPE_REQUIRED` (admin 필요) / `FORBIDDEN_ROLE` / `API_KEY_FORBIDDEN`

- [ ] **Step 5: 비밀번호 72바이트 경계**

```bash
curl -s -X POST http://localhost/api/v1/admin/users/2/password -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{"password":"가가가가가가가가가가가가가가가가가가가가가가가가가"}'; echo
```

Expected: 400 `PASSWORD_TOO_LONG` + `"field":"password"` (한글 25자 = 75바이트). **500이 나오면 안 된다** — 그게 이월 항목이 경고한 실패다.

- [ ] **Step 6: 마스터 변경이 업무 API에 즉시 반영되는지**

```bash
CC=$(curl -s http://localhost/api/v1/admin/cost-centers -H "Authorization: Bearer $TOKEN" \
  | python3 -c 'import sys,json;print([c["id"] for c in json.load(sys.stdin) if c["code"]=="CC2100"][0])')
curl -s -X PATCH "http://localhost/api/v1/admin/cost-centers/$CC" -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' -d '{"is_active":false}' > /dev/null
curl -s -X POST http://localhost/api/v1/trips -H "Authorization: Bearer $UTOKEN" \
  -H 'Content-Type: application/json' \
  -d '{"title":"비활성 센터 검증","purpose_code":"CUSTOMER","purpose_detail":"확인","destination_type_code":"DOMESTIC","country_code":"KR","city":"울산","start_date":"2026-09-10","end_date":"2026-09-11","transport_code":"AIR","accommodation_code":"HOTEL","cost_center_code":"CC2100","estimated_cost":"300000"}'
echo
# 원상복구 — 다음 데모가 CC2100을 쓴다
curl -s -X PATCH "http://localhost/api/v1/admin/cost-centers/$CC" -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' -d '{"is_active":true}' > /dev/null
```

Expected: 400 `INVALID_COST_CENTER` — 관리 화면의 토글이 업무 검증에 그대로 걸린다. 마지막 줄로 반드시 되돌린다.

- [ ] **Step 7: 검증용으로 만든 키를 폐기한다**

```bash
curl -s http://localhost/api/v1/api-keys -H "Authorization: Bearer $TOKEN" \
  | python3 -c 'import sys,json;[print(k["id"],k["name"],k["state"]) for k in json.load(sys.stdin)]'
# 위에서 만든 두 키의 id로:
# curl -s -X POST http://localhost/api/v1/api-keys/<id>/revoke -H "Authorization: Bearer $TOKEN"
```

Expected: 검증에 쓴 키가 `REVOKED`가 된다. 남긴 데모 데이터(D500·RISK_LEVEL 등)는 Task 23에 기록한다.

---

## Task 22: 브라우저 수동 시나리오

**Files:**
- Create: `docs/manual-scenarios.md`

Phase 2~4에서 미룬 23개 + Phase 5 신규를 한 문서로 모은다. 흩어져 있으면 아무도 안 돈다.

- [ ] **Step 1: 체크리스트 문서를 만든다**

`docs/manual-scenarios.md`:

```markdown
# 브라우저 수동 시나리오

- 실행 방법: `docker compose -p skon-prod up -d --build` 후 `http://localhost` (평문 HTTP — SecureContext가 아니다)
- 계정: `admin@skon.example` · `manager1@skon.example` · `user1@skon.example` / 비밀번호 `skon1234!`
- 각 항목 앞의 체크박스는 **직접 눌러 본 뒤에만** 채운다. 못 돌렸으면 비워 두고 phase-status에 남긴다.

## Phase 2 이월 (8)

- [ ] 로그인 전 `/trips/3` 딥링크 → 로그인 후 그 화면으로 복귀
- [ ] 출장 신청 폼에서 제출 버튼 연타 → 출장이 1건만 생성
- [ ] 반려된 출장에서 재작성(reopen) → DRAFT로 돌아오고 수정 가능
- [ ] 토큰 만료 상태로 목록 진입 → 로그인 화면으로 정리 (전역 401)
- [ ] 결재함이 MANAGER·ADMIN에게만 보인다
- [ ] 알림 벨 뱃지 숫자가 라우트 이동 후 갱신
- [ ] 목록 필터(상태·국가·기간·검색)가 URL과 함께 동작
- [ ] 타임라인이 CREATED·SUBMITTED·APPROVED 순으로 표시

## Phase 3 이월 (6)

- [ ] `/cards` 카드·기간·업종·검색 필터
- [ ] 정산서 생성 시 출장의 cost_center_code 승계
- [ ] 매칭 후보 "담기" → 항목 테이블에 추가되고 합계 갱신
- [ ] 항목의 부서 지정(상속 ↔ override) 토글
- [ ] FC 없이 제출 → 400 `CENTER_REQUIRED` 메시지 노출
- [ ] 정산 승인 후 출장이 SETTLED로 표시

## Phase 4 이월 (9)

- [ ] `/settings/api-keys` 렌더 (Phase 4에서 렌더 확인이 전혀 안 됐다)
- [ ] 키 발급 흐름 → 평문 1회 노출
- [ ] 복사 버튼 (평문 HTTP라 `navigator.clipboard`가 없다 — `execCommand` 폴백 확인)
- [ ] 발급 폼 연타 → 키 1개만 생성
- [ ] 스코프 미선택 시 발급 버튼 비활성
- [ ] 폐기 2단계 확인 → 목록 상태가 REVOKED
- [ ] `/developers` 렌더 + 스코프 표가 `GET /scopes` 응답과 일치
- [ ] 헤더 탭 활성 표시
- [ ] 전역 401 처리

## Phase 5 신규 (10)

- [ ] `/admin/codes` 그룹 생성 → 코드 추가 → 중지 → 삭제(2단계) 동작
- [ ] 활성 코드 삭제 시 409 메시지가 화면에 보인다
- [ ] `/admin/centers` FC/CC 탭 전환 시 목록이 바뀐다
- [ ] 참조 중인 센터 삭제 → 409 메시지
- [ ] `/admin/departments` 사용자 있는 부서 삭제 → 409 메시지
- [ ] `/admin/users` 검색 → 역할 변경 → 비활성화 (자기 자신은 비활성화 버튼이 disabled)
- [ ] `/admin/users` 비밀번호 재설정 후 그 계정으로 로그인
- [ ] `/admin/cards` 거래 있는 카드 삭제 → 409 메시지
- [ ] EMPLOYEE 계정으로 `/admin/codes` 직접 진입 → 대시보드로 돌아간다
- [ ] 375px에서 햄버거 시트 열림 → 링크 이동 후 자동 닫힘, 가로 스크롤 없음
```

- [ ] **Step 2: 실행 가능한 만큼 돌린다**

브라우저를 쓸 수 있으면 위 항목을 실제로 눌러 보고 체크한다. **브라우저 도구가 없으면 아무것도 체크하지 않는다.** 통과했다고 적는 것이 미확인으로 남기는 것보다 나쁘다 — Phase 4가 그렇게 렌더 미확인 화면 2개를 남겼다.

- [ ] **Step 3: 발견한 결함을 고친다**

시나리오에서 실패한 항목이 있으면 그 자리에서 고치고, 고친 내용을 커밋 메시지에 남긴다. 고칠 수 없는 것(설계 결정)은 Task 23의 이월 목록에 넣는다.

- [ ] **Step 4: 커밋**

```bash
cd /Users/namkon/projects/skon-biztrip-web && git add docs/manual-scenarios.md && git commit -m "docs: consolidate manual browser scenarios"
```

---

## Task 23: 문서 갱신

**Files:**
- Modify: `docs/phase-status.md`
- Modify: `CLAUDE.md`

- [ ] **Step 1: 최종 수치를 얻는다**

```bash
cd /Users/namkon/projects/skon-biztrip-web/backend && uv run pytest -q 2>&1 | tail -3
cd /Users/namkon/projects/skon-biztrip-web/frontend && npm test 2>&1 | tail -5
cd /Users/namkon/projects/skon-biztrip-web/frontend && npm run check 2>&1 | tail -3
```

실제로 출력된 숫자를 쓴다. **추정치를 적지 않는다.**

- [ ] **Step 2: `docs/phase-status.md`를 갱신한다**

다음을 반영한다.

1. 머리말의 "기준"을 `Phase 5 (운영) 완료 시점`으로, Phase 계획 목록에 `Phase 5 계획: superpowers/plans/2026-08-18-phase5-admin-ops.md` 추가.
2. 표의 Phase 5 행을 **완료**로 바꾸고, "이후 Phase" 절을 상황에 맞게 정리.
3. 테스트 줄을 Step 1의 실측치로 교체.
4. `## Phase 5 — 완료` 절 신설. 다음을 포함한다.
   - 백엔드 서비스 표 (`admin/common` `admin/departments` `admin/codes` `admin/centers` `admin/users` `admin/cards`)
   - 엔드포인트 목록 28개
   - 프론트 화면 5개 + `AdminResource` + `admin.ts`
   - 확정한 설계 결정 표 (이 계획의 "확정된 설계 결정" 표를 결과 기준으로 옮긴다)
   - mutation 검증 목록 (Task 1·4·5·6·7·8·11에서 실제로 깨뜨린 것)
   - Task 20·21의 실서버 검증 결과
   - Task 22의 시나리오 결과 (돌린 것 / 못 돌린 것을 있는 그대로)
5. "Phase 4에서 넘어온 항목" 중 처리된 것을 "Phase 5에서 처리한 이월 항목"으로 옮긴다: `/admin/*` 스코프 등록, `HAS_DEPENDENTS` 변환, 비밀번호 72바이트, admin 스코프 엔드포인트, 반응형 헤더/표.
6. "Phase 5에서 넘어온 항목"을 새로 쓴다. 최소한 다음을 포함한다.
   - 부서 트리의 **일반 순환**(A→B→A)은 검사하지 않는다. 자기 자신만 막는다.
   - 유니크 검사에 TOCTOU가 있다(삽입 전 SELECT). 최종 방어선은 DB 제약이며 그때는 500이다.
   - 코드/센터 삭제 가드는 **참조 열거**에 의존한다. 새 테이블이 코드 문자열을 참조하면 `_REFERENCES`와 코드 삭제 규칙을 함께 늘려야 한다.
   - DESIGN.md의 "모바일에서 reservation card → 화면 하단 sticky bar"는 미구현이다(현재는 아래로 쌓인다).
   - Task 22에서 못 돌린 시나리오 목록.
   - Phase 4에서 그대로 넘어온 것들: `last_used_at` 매요청 갱신, 출장 상세의 정산서 존재 판정(`size=100`), 항목 FC/CC override 재검증, `q`의 LIKE 이스케이프, `next_report_no`의 `max()+1`, 매칭 후보 페이징, 알림 폴링, 대시보드 집계 4회 호출, 키 발급·폐기가 activity_log에 없음.
   - Task 21에서 운영 DB에 남긴 데모 데이터(D500·RISK_LEVEL·폐기된 키 등)를 실제 남긴 것만 적는다.

- [ ] **Step 3: `CLAUDE.md`를 갱신한다**

1. 상단 문장을 `Phase 1~5 완료`로 바꾸고 "다음은 Phase 5" 문장을 지운다.
2. 명령어 절의 테스트 건수를 실측치로 교체.
3. "반드시 지킬 것"에 Phase 5에서 고정된 규칙 3개를 추가한다.

```markdown
**Admin 삭제는 `services/admin/common.py`의 `delete_entity`만 쓴다.** `IntegrityError`를 409 `HAS_DEPENDENTS`로 바꾸고 실패한 flush 뒤 세션을 롤백한다. 직접 `session.delete()`+`commit()`을 쓰면 참조가 남은 삭제가 500이 되고 Agent가 재시도한다. 코드값·센터처럼 **FK가 없는 참조**는 DB가 막아주지 못하므로 서비스가 따로 센다 (`admin/centers.py`의 `_REFERENCES`, `admin/codes.py`의 비활성화 선행 규칙). 코드 문자열을 참조하는 테이블을 새로 만들면 그 표도 함께 늘려야 한다.

**비밀번호를 받는 경로는 `assert_password_length`를 지난다.** bcrypt 5.x는 72바이트 초과를 자르지 않고 던진다(한글 24자가 경계). Pydantic의 `max_length`는 문자 수라 이 검사를 대신할 수 없다.

**비밀번호 설정은 JWT 전용(`JwtOnlyAdmin`)이다.** admin 스코프 키로 남의 비밀번호를 바꿀 수 있으면 그 계정으로 로그인해 전권 키를 발급할 수 있고, 키 관리 API를 JWT 전용으로 막아둔 이유가 통째로 우회된다.
```

4. 프론트 규칙에 한 줄 추가한다.

```markdown
**Admin 화면의 목록·에러·중복제출 가드는 `AdminResource`를 쓴다.** 화면마다 `if (submitting) return;`을 손으로 넣으면 하나는 빠지고, 생성은 멱등하지 않아 그게 곧 중복 레코드다. 반응형 분기는 `tablet:`(744px)이며 `md:`(768px)와 다르다 — DESIGN.md 기준선은 744px다.
```

5. 맨 아래 "다음 Phase로 넘어간 항목" 절을 Phase 5 이월 요약으로 교체한다.

- [ ] **Step 4: 문서가 코드와 맞는지 확인한다**

```bash
cd /Users/namkon/projects/skon-biztrip-web && grep -c "_AD," backend/app/services/api_scopes.py
grep -n "Phase" CLAUDE.md | head -5
```

Expected: `_AD,` 28줄(문서에 적은 엔드포인트 수와 일치), CLAUDE.md에 "Phase 5" 미완 문구가 남아 있지 않다

- [ ] **Step 5: 커밋**

```bash
cd /Users/namkon/projects/skon-biztrip-web && git add docs CLAUDE.md && git commit -m "docs: record Phase 5 completion and carry-over items"
```

---

## 완료 조건

- [ ] `cd backend && uv run pytest` — 실패 0
- [ ] `cd frontend && npm test` — 실패 0
- [ ] `cd frontend && npm run check` — 0 errors / 0 warnings
- [ ] `cd frontend && npm run build` — 성공
- [ ] `uv run python -c "import app.main"` — 소진 가드 통과 (표와 라우트 일치)
- [ ] `docker compose -p skon-prod up -d --build` 후 `/api/v1/health`·`/api/v1/health/db` 200
- [ ] Task 21의 curl 시나리오 전부 Expected와 일치
- [ ] `docs/phase-status.md`에 Phase 5 절과 이월 목록이 있다
- [ ] Task 22에서 **실제로 돌린** 시나리오만 체크되어 있다
