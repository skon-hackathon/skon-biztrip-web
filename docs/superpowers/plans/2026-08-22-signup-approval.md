# 회원가입 · 관리자 승인 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 외부인이 스스로 가입하고, 관리자가 `/admin/users`에서 조직 정보(사번·직급·결재자·역할)를 채워 승인하면 로그인할 수 있게 한다.

**Architecture:** `public.user`에 `status`(PENDING/ACTIVE/REJECTED) 컬럼을 더한다. `is_active`의 의미는 바꾸지 않고 단방향 불변식 `status != ACTIVE ⟹ is_active = false`만 유지한다 — 그래야 로그인 게이트와 계정을 공유하는 상대 프로젝트의 시야가 그대로다. 상태 전이는 출장·정산과 같은 구조로 **단일 assert 하나**만 통과한다.

**Tech Stack:** FastAPI · SQLAlchemy 2.0 async · Pydantic v2 · PostgreSQL 16 · SvelteKit 2(Svelte 5 runes) · Tailwind v4 · pytest-asyncio · vitest

**설계 문서:** `docs/superpowers/specs/2026-08-22-signup-approval-design.md`

**선행 조건:** `docs/migrations/2026-08-21-user-table-to-public.sql`은 **이미 실행되었다**(2026-08-22 확인, `public."user"` 존재·로그인 200). 다시 돌리지 말 것 — 스크립트 첫 가드가 예외를 던진다.

---

## 작업 전 읽을 것

- `CLAUDE.md`의 "반드시 지킬 것" 전체. 특히 스코프 표(`SCOPE_REQUIREMENTS`), 상태 전이 단일 assert, `ForeignKey(USER_FK)`, `relationship()` 금지, 모달·중복제출 가드·`text-body` 금지.
- 이 계획의 명령은 전부 `backend/` 또는 `frontend/`에서 실행한다. **backend에서 맨 `python3`는 pyenv 때문에 멈춘다. 항상 `uv run`을 거칠 것.**

전체 검증 명령 (여러 태스크 끝에서 반복 사용):

```bash
cd backend  && uv run pytest -q
cd frontend && npm test
cd frontend && npm run check     # 0 errors / 0 warnings 유지
```

---

## File Structure

**Create:**

| 파일 | 책임 |
| --- | --- |
| `docs/migrations/2026-08-22-user-signup-status.sql` | 운영 DB 스키마 변경 (사람이 실행) |
| `backend/app/services/user_status.py` | 전이 표 · 주체 표 · 단일 `assert_signup_transition_allowed` |
| `backend/app/services/signup.py` | 가입 · 부서 목록 (미인증 경로) |
| `backend/tests/test_user_status.py` | 전이 표 단위 테스트 (DB 없음) |
| `backend/tests/test_signup_api.py` | 가입 API 통합 테스트 |
| `frontend/src/routes/signup/+page.svelte` | 가입 화면 |
| `frontend/src/lib/api/signup.ts` | 미인증 가입 API 클라이언트 |

**Modify:**

| 파일 | 변경 |
| --- | --- |
| `backend/app/enums.py` | `UserStatus` 추가 |
| `backend/app/models/org.py` | `User.status` 추가, `employee_no`·`position_code` nullable |
| `backend/app/services/admin/common.py` | `assert_department` 이동(공유) |
| `backend/app/services/admin/users.py` | `approve_user`·`reject_user`, `status` 필터 |
| `backend/app/routers/auth.py` | `POST /signup` · `GET /departments` · 로그인 상태 분기 |
| `backend/app/routers/admin/users.py` | `POST /{id}/approve` · `POST /{id}/reject` · `status` 쿼리 |
| `backend/app/schemas/auth.py` | `SignupRequest` · `SignupResponse` · `PublicDepartment` |
| `backend/app/schemas/admin.py` | `AdminUserOut.status`, nullable 두 필드, `UserApprove` |
| `backend/app/services/api_scopes.py` | approve·reject 2줄 |
| `backend/app/seed.py` | PENDING 사용자 1명 |
| `backend/tests/factories.py` | `make_user`에 `status` 인자 |
| `frontend/src/lib/api/types.ts` | `UserStatus`, `AdminUser.status`, nullable 두 필드 |
| `frontend/src/lib/api/admin.ts` | `approveUser` · `rejectUser` · `status` 쿼리 |
| `frontend/src/lib/nav.ts` | `PUBLIC_PREFIXES`에 `/signup` |
| `frontend/src/lib/admin.ts` | `STATUS_LABELS` |
| `frontend/src/routes/admin/users/+page.svelte` | status 열·필터·승인 모달 |
| `frontend/src/routes/login/+page.svelte` | 가입 링크 · 상태 안내 문구 |
| `CLAUDE.md` · `docs/phase-status.md` · `docs/manual-scenarios.md` | 문서 |

---

## Task 1: UserStatus enum

**Files:**
- Modify: `backend/app/enums.py`
- Test: `backend/tests/test_user_status.py` (Create)

- [ ] **Step 1: 실패하는 테스트를 쓴다**

`backend/tests/test_user_status.py` 생성:

```python
from app.enums import UserStatus


def test_user_status_members():
    # 리터럴에서 파생시킨다. set(UserStatus)로 쓰면 멤버를 늘리는 변경과 테스트가
    # 함께 움직여 통과한다.
    assert {s.value for s in UserStatus} == {"PENDING", "ACTIVE", "REJECTED"}


def test_user_status_is_str():
    # StrEnum이어야 varchar 저장·JSON 직렬화가 지금의 role과 같은 모양이 된다.
    assert UserStatus.PENDING == "PENDING"
```

- [ ] **Step 2: 실패를 확인한다**

```bash
cd backend && uv run pytest tests/test_user_status.py -q
```

Expected: FAIL — `ImportError: cannot import name 'UserStatus' from 'app.enums'`

- [ ] **Step 3: enum을 추가한다**

`backend/app/enums.py`의 `UserRole` 클래스 **바로 아래**에 추가:

```python
class UserStatus(StrEnum):
    """가입 신청의 생애주기.

    `is_active`(로그인 가능 여부)와 의미가 겹치지 않는다. 불변식은 단방향이다 —
    `status != ACTIVE`이면 반드시 `is_active = false`이지만, 역은 성립하지 않는다.
    승인된 뒤 관리자가 정지시킨 사용자가 `status=ACTIVE` + `is_active=false`이며,
    그것이 "승인 대기"와 구분되어야 하는 경우다.

    공통코드 테이블이 아니라 Python Enum인 이유는 role과 같다 — 가입·승인·로그인
    분기에 박히는 값이므로 관리자가 편집할 수 있으면 안 된다.
    """

    PENDING = "PENDING"
    ACTIVE = "ACTIVE"
    REJECTED = "REJECTED"
```

- [ ] **Step 4: 통과를 확인한다**

```bash
cd backend && uv run pytest tests/test_user_status.py -q
```

Expected: PASS (2 passed)

- [ ] **Step 5: 커밋**

```bash
git add backend/app/enums.py backend/tests/test_user_status.py
git commit -m "feat(user): UserStatus enum 추가"
```

---

## Task 2: 전이 표와 단일 가드

출장·정산과 같은 구조다. 적법성과 주체를 따로 부를 수 있게 열어두면 언젠가 한쪽만 부르고, 그 실패는 fail-open이다.

**Files:**
- Create: `backend/app/services/user_status.py`
- Test: `backend/tests/test_user_status.py` (Modify — Task 1에서 만든 파일에 이어 붙인다)

- [ ] **Step 1: 실패하는 테스트를 쓴다**

`backend/tests/test_user_status.py` **끝에** 추가하고, 파일 맨 위 import를 아래로 교체한다:

```python
import pytest

from app.enums import UserStatus
from app.errors import ConflictError, ForbiddenError
from app.services.user_status import (
    SIGNUP_ALLOWED_TRANSITIONS,
    SIGNUP_TRANSITION_ACTOR,
    SignupActor,
    assert_signup_transition_allowed,
)
```

이어서 파일 끝에:

```python
# 리터럴이다. SIGNUP_ALLOWED_TRANSITIONS에서 파생시키면 표를 넓히는 버그와
# 테스트가 함께 움직여 통과한다.
_LEGAL = [
    (UserStatus.PENDING, UserStatus.ACTIVE),
    (UserStatus.PENDING, UserStatus.REJECTED),
    (UserStatus.REJECTED, UserStatus.PENDING),
]
_ILLEGAL = [
    (UserStatus.ACTIVE, UserStatus.PENDING),
    (UserStatus.ACTIVE, UserStatus.REJECTED),
    (UserStatus.ACTIVE, UserStatus.ACTIVE),
    (UserStatus.PENDING, UserStatus.PENDING),
    (UserStatus.REJECTED, UserStatus.ACTIVE),
    (UserStatus.REJECTED, UserStatus.REJECTED),
]


@pytest.mark.parametrize(("current", "target"), _LEGAL)
def test_legal_transitions_pass(current, target):
    actor = SIGNUP_TRANSITION_ACTOR[(current, target)]
    assert_signup_transition_allowed(current, target, actor=actor)


@pytest.mark.parametrize(("current", "target"), _ILLEGAL)
def test_illegal_transitions_conflict(current, target):
    with pytest.raises(ConflictError) as exc:
        assert_signup_transition_allowed(current, target, actor=SignupActor.ADMIN)
    assert exc.value.code == "USER_INVALID_TRANSITION"
    assert exc.value.status_code == 409


def test_transition_table_covers_every_status():
    assert set(SIGNUP_ALLOWED_TRANSITIONS) == set(UserStatus)


def test_wrong_actor_is_forbidden():
    # 재신청(REJECTED -> PENDING)은 가입자의 전이다. 관리자 주체로 부르면 거부해야 한다.
    with pytest.raises(ForbiddenError) as exc:
        assert_signup_transition_allowed(
            UserStatus.REJECTED, UserStatus.PENDING, actor=SignupActor.ADMIN
        )
    assert exc.value.code == "WRONG_TRANSITION_ACTOR"


def test_admin_transition_rejects_applicant_actor():
    with pytest.raises(ForbiddenError):
        assert_signup_transition_allowed(
            UserStatus.PENDING, UserStatus.ACTIVE, actor=SignupActor.APPLICANT
        )
```

- [ ] **Step 2: 실패를 확인한다**

```bash
cd backend && uv run pytest tests/test_user_status.py -q
```

Expected: FAIL — `ModuleNotFoundError: No module named 'app.services.user_status'`

- [ ] **Step 3: 모듈을 만든다**

`backend/app/services/user_status.py` 생성:

```python
"""가입 상태전이의 적법성과 수행 주체를 한 번에 판단한다.

호출부는 `assert_signup_transition_allowed` **하나만** 부른다. 적법성 표와 주체 표를
따로 부를 수 있게 열어두지 않는 이유는 출장·정산에서 이미 정한 것과 같다 — 나뉘어 있으면
언젠가 한쪽만 부르고, 그 실패는 fail-open이다. 여기서는 "미인증 가입 경로가 관리자 전용
승인 전이를 통과한다"가 된다.

전이를 추가하고 주체를 빠뜨리면 임포트 시점에 RuntimeError로 죽는다.
"""

from enum import Enum

from app.enums import UserStatus
from app.errors import ConflictError, ForbiddenError


class SignupActor(Enum):
    """전이를 수행할 수 있는 주체."""

    ADMIN = "ADMIN"
    #: 미인증 가입자. 로그인하지 않은 상태에서 재신청을 수행한다.
    APPLICANT = "APPLICANT"


SIGNUP_ALLOWED_TRANSITIONS: dict[UserStatus, frozenset[UserStatus]] = {
    UserStatus.PENDING: frozenset({UserStatus.ACTIVE, UserStatus.REJECTED}),
    UserStatus.REJECTED: frozenset({UserStatus.PENDING}),
    # ACTIVE에서 나가는 전이는 없다. 계정 정지는 전이가 아니라
    # PATCH /admin/users/{id}의 is_active 변경이다.
    UserStatus.ACTIVE: frozenset(),
}

_missing_statuses = set(UserStatus) - set(SIGNUP_ALLOWED_TRANSITIONS)
if _missing_statuses:
    raise RuntimeError(f"SIGNUP_ALLOWED_TRANSITIONS missing entries for {_missing_statuses}")

SIGNUP_TRANSITION_ACTOR: dict[tuple[UserStatus, UserStatus], SignupActor] = {
    (UserStatus.PENDING, UserStatus.ACTIVE): SignupActor.ADMIN,
    (UserStatus.PENDING, UserStatus.REJECTED): SignupActor.ADMIN,
    (UserStatus.REJECTED, UserStatus.PENDING): SignupActor.APPLICANT,
}

_all_transitions = {
    (current, target)
    for current, targets in SIGNUP_ALLOWED_TRANSITIONS.items()
    for target in targets
}
_missing_actors = _all_transitions - set(SIGNUP_TRANSITION_ACTOR)
_extra_actors = set(SIGNUP_TRANSITION_ACTOR) - _all_transitions
if _missing_actors or _extra_actors:
    raise RuntimeError(
        "SIGNUP_TRANSITION_ACTOR가 SIGNUP_ALLOWED_TRANSITIONS와 어긋납니다: "
        f"missing={_missing_actors} extra={_extra_actors}"
    )


def assert_signup_transition_allowed(
    current: UserStatus, target: UserStatus, *, actor: SignupActor
) -> None:
    """적법성과 주체를 한 번에 검사한다. 호출부는 이것만 부른다."""
    if target not in SIGNUP_ALLOWED_TRANSITIONS[current]:
        raise ConflictError(
            "USER_INVALID_TRANSITION",
            f"{current} 상태에서 {target} 로 변경할 수 없습니다",
        )
    expected = SIGNUP_TRANSITION_ACTOR[(current, target)]
    if actor is not expected:
        raise ForbiddenError(
            "WRONG_TRANSITION_ACTOR", "이 전이를 수행할 수 있는 주체가 아닙니다"
        )
```

- [ ] **Step 4: 통과를 확인한다**

```bash
cd backend && uv run pytest tests/test_user_status.py -q
```

Expected: PASS (전체 통과, 15 passed 내외)

- [ ] **Step 5: mutation으로 가드를 확인한다**

`ACTIVE: frozenset()`을 일시적으로 `frozenset({UserStatus.PENDING})`으로 바꾸고 테스트를 돌린다.

```bash
cd backend && uv run pytest tests/test_user_status.py -q
```

Expected: FAIL — `test_illegal_transitions_conflict[ACTIVE-PENDING]`이 깨지고, 주체 표 불일치로 임포트 자체가 `RuntimeError`로 죽는다. **확인 후 반드시 되돌린다.**

```bash
cd backend && git diff --stat app/services/user_status.py
```

Expected: 되돌린 뒤 출력 없음(변경 0건)

- [ ] **Step 6: 커밋**

```bash
git add backend/app/services/user_status.py backend/tests/test_user_status.py
git commit -m "feat(user): 가입 상태전이 표와 단일 가드"
```

---

## Task 3: 모델 · 마이그레이션 SQL

**Files:**
- Modify: `backend/app/models/org.py:20-43`
- Create: `docs/migrations/2026-08-22-user-signup-status.sql`
- Test: `backend/tests/test_models_master.py`

- [ ] **Step 1: 실패하는 테스트를 쓴다**

`backend/tests/test_models_master.py` 끝에 추가한다. 파일 상단에 이미 있는 import는 건드리지 말고, 필요한 것만 함수 안에서 쓴다:

```python
async def test_user_status_defaults_to_active(db_session):
    from app.enums import UserStatus
    from tests.factories import make_user

    user = await make_user(db_session)
    await db_session.flush()
    assert user.status == UserStatus.ACTIVE


async def test_user_allows_null_employee_no_and_position(db_session):
    # 가입 시점에는 사번·직급이 없다. 임시값을 넣지 않고 NULL로 둔다 —
    # 가짜 사번이 상대 프로젝트와 Agent API에 실제 값처럼 노출되지 않게 하려는 것이다.
    from sqlalchemy import select

    from app.enums import UserStatus
    from app.models import Department, User

    department = Department(code="D900", name="가입대기부서")
    db_session.add(department)
    await db_session.flush()

    user = User(
        email="pending@skon.example",
        password_hash="x",
        name="가입자",
        employee_no=None,
        department_id=department.id,
        position_code=None,
        status=UserStatus.PENDING,
        is_active=False,
    )
    db_session.add(user)
    await db_session.flush()

    found = await db_session.scalar(select(User).where(User.email == "pending@skon.example"))
    assert found is not None
    assert found.employee_no is None
    assert found.position_code is None
    assert found.status == UserStatus.PENDING
```

- [ ] **Step 2: 실패를 확인한다**

```bash
cd backend && uv run pytest tests/test_models_master.py -q -k "user_status or null_employee"
```

Expected: FAIL — `TypeError: 'status' is an invalid keyword argument for User` 또는 `IntegrityError: null value in column "employee_no"`

- [ ] **Step 3: 모델을 고친다**

`backend/app/models/org.py`의 `User` 클래스에서 두 컬럼을 nullable로 바꾸고 `status`를 더한다.

`employee_no` 줄을 아래로 교체:

```python
    # 가입 신청 시점에는 값이 없어 NULL이다. ACTIVE로의 승인이 값을 강제한다
    # (services/admin/users.py의 approve_user). unique는 유지한다 — Postgres에서
    # NULL은 서로 충돌하지 않으므로 대기 행이 여럿이어도 문제가 없다.
    employee_no: Mapped[str | None] = mapped_column(String(20), unique=True)
```

`position_code` 줄을 아래로 교체:

```python
    position_code: Mapped[str | None] = mapped_column(String(30))
```

`is_active` 줄 **바로 위**에 추가:

```python
    status: Mapped[UserStatus] = mapped_column(
        # role과 같은 이유로 PG enum을 쓰지 않는다 — 공유 테이블이므로 상대 프로젝트가
        # 우리 스키마의 타입 이름에 묶이면 안 된다.
        SAEnum(UserStatus, name="user_status", native_enum=False, length=20),
        default=UserStatus.ACTIVE,
        server_default=UserStatus.ACTIVE.value,
        nullable=False,
    )
```

파일 상단 import를 교체:

```python
from app.enums import UserRole, UserStatus
```

- [ ] **Step 4: 통과를 확인한다**

```bash
cd backend && uv run pytest tests/test_models_master.py -q
```

Expected: PASS

- [ ] **Step 5: 편집이 반영됐는지 grep으로 확인한다**

```bash
cd backend && grep -n "status\|employee_no\|position_code" app/models/org.py
```

Expected: `employee_no: Mapped[str | None]`, `position_code: Mapped[str | None]`, `status: Mapped[UserStatus]` 세 줄이 보인다

- [ ] **Step 6: 마이그레이션 SQL을 쓴다**

`docs/migrations/2026-08-22-user-signup-status.sql` 생성:

```sql
-- public."user"에 가입 상태 컬럼을 더하고, 가입 시점에 알 수 없는 두 컬럼의 NOT NULL을 푼다.
--
-- 왜: 회원가입을 열되 승인은 관리자가 하기 때문이다. 가입자는 이메일·이름·비밀번호·부서만
-- 내고, 사번·직급·결재자·역할은 관리자가 승인 시점에 채운다. 그 값들은 결재선과 정산 귀속의
-- 근거라 본인이 고르면 틀린다.
--
-- 설계: docs/superpowers/specs/2026-08-22-signup-approval-design.md
--
-- 선행: docs/migrations/2026-08-21-user-table-to-public.sql이 먼저 실행되어 있어야 한다.
--       (2026-08-22 실행 완료. user 테이블은 public에 있다.)
--
-- 이 프로젝트는 Alembic을 쓰지 않는다. 이 파일은 **사람이 psql로 한 번 실행**한다.
-- app.cli init-db는 없는 테이블만 만들 뿐 기존 테이블의 컬럼 변경을 반영하지 않는다.
-- 코드만 배포하고 이걸 돌리지 않으면 status 컬럼이 없어 로그인부터 500이 난다.
--
-- 실행:
--   psql "postgresql://<user>@<host>:<port>/<db>" -v ON_ERROR_STOP=1 \
--        -f docs/migrations/2026-08-22-user-signup-status.sql
--
-- 주의: "user"는 PostgreSQL 예약어다. 따옴표 없이 쓰면 조용히 현재 역할명을 뜻한다.

-- 0) 선행 확인 ---------------------------------------------------------------
DO $$
BEGIN
    IF to_regclass('public."user"') IS NULL THEN
        RAISE EXCEPTION 'public."user"가 없습니다. 2026-08-21 이관 SQL을 먼저 실행하십시오.';
    END IF;
END $$;

BEGIN;

-- 1) status 컬럼 -------------------------------------------------------------
-- DEFAULT 'ACTIVE'이므로 기존 행은 전부 ACTIVE가 된다. 그게 옳다 — 지금 있는 계정은
-- 모두 관리자가 만들었거나 시드로 들어온 승인된 계정이다.
-- PG enum 타입을 만들지 않는 이유는 role과 같다. 계정을 공유하는 상대 프로젝트가
-- 우리 스키마의 타입 이름에 묶이는 결합을 만들지 않는다.
ALTER TABLE public."user"
    ADD COLUMN IF NOT EXISTS status varchar(20) NOT NULL DEFAULT 'ACTIVE';

-- 2) 가입 시점에 알 수 없는 두 컬럼의 NOT NULL 해제 ---------------------------
-- 임시값(예: 'PENDING-<uuid>')을 넣지 않는 이유: 그 가짜 사번이 상대 프로젝트·유저 관리
-- 화면·Agent API에 실제 사번처럼 노출된다. NULL은 "없다"를 정직하게 말한다.
-- employee_no의 unique 제약은 유지한다 — Postgres에서 NULL끼리는 충돌하지 않는다.
ALTER TABLE public."user" ALTER COLUMN employee_no DROP NOT NULL;
ALTER TABLE public."user" ALTER COLUMN position_code DROP NOT NULL;

COMMIT;

-- 3) 검증 ---------------------------------------------------------------------
-- 기대: status는 character varying NOT NULL, 나머지 둘은 is_nullable = YES.
--       기존 계정은 전부 ACTIVE.
SELECT column_name, data_type, is_nullable, column_default
  FROM information_schema.columns
 WHERE table_schema = 'public' AND table_name = 'user'
   AND column_name IN ('status', 'employee_no', 'position_code')
 ORDER BY column_name;

SELECT status, count(*) FROM public."user" GROUP BY status;
```

- [ ] **Step 7: 마이그레이션을 실행한다**

```bash
set -a; . /Users/namkon/projects/skon-biztrip-web/backend/.env; set +a
docker exec -e PGPASSWORD="$DB_PASSWORD" -i postgres-pgvector \
  psql -U "$DB_USER" -d "$DB_NAME" -v ON_ERROR_STOP=1 \
  < /Users/namkon/projects/skon-biztrip-web/docs/migrations/2026-08-22-user-signup-status.sql
```

Expected: `DO` / `BEGIN` / `ALTER TABLE` ×3 / `COMMIT` 뒤에 검증 결과 — `status | character varying | NO`, `employee_no | ... | YES`, `position_code | ... | YES`, 그리고 `ACTIVE | 14`

- [ ] **Step 8: 커밋**

```bash
git add backend/app/models/org.py backend/tests/test_models_master.py docs/migrations/2026-08-22-user-signup-status.sql
git commit -m "feat(user): status 컬럼과 nullable 사번·직급"
```

---

## Task 4: 팩토리와 시드

**Files:**
- Modify: `backend/tests/factories.py:47-80`
- Modify: `backend/app/seed.py`
- Test: `backend/tests/test_seed.py`

- [ ] **Step 1: 실패하는 테스트를 쓴다**

`backend/tests/test_seed.py` 끝에 추가:

```python
async def test_seed_creates_one_pending_user(db_session, seeded):
    # 승인 화면을 시연하려면 대기 건이 있어야 한다. 없으면 데모마다 사람이 손으로
    # 가입해야 승인 흐름을 보여줄 수 있다.
    from sqlalchemy import select

    from app.enums import UserStatus
    from app.models import User

    rows = (
        (await db_session.execute(select(User).where(User.status == UserStatus.PENDING)))
        .scalars()
        .all()
    )
    assert len(rows) == 1
    pending = rows[0]
    assert pending.is_active is False
    assert pending.employee_no is None
    assert pending.position_code is None
```

- [ ] **Step 2: 실패를 확인한다**

```bash
cd backend && uv run pytest tests/test_seed.py -q -k pending
```

Expected: FAIL — `assert 0 == 1`

- [ ] **Step 3: 팩토리에 status 인자를 더한다**

`backend/tests/factories.py`의 `make_user` 시그니처에 인자를 더하고 `User(...)`에 넘긴다.

시그니처의 `name: str = "박출장",` 다음 줄에 추가:

```python
    status: UserStatus = UserStatus.ACTIVE,
    is_active: bool = True,
```

`User(` 생성자 안 `role=role,` 다음 줄에 추가:

```python
        status=status,
        is_active=is_active,
```

파일 상단 import에 `UserStatus`를 더한다. 기존 줄이 `from app.enums import UserRole`이면:

```python
from app.enums import UserRole, UserStatus
```

- [ ] **Step 4: 시드에 PENDING 사용자를 더한다**

`backend/app/seed.py`의 `_seed_users` 함수 **맨 끝**(기존 사용자 생성이 모두 끝난 뒤)에 추가한다. 함수가 사용자 목록을 반환한다면 반환문 **앞**에 넣는다:

```python
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
                department_id=departments[0].id,
                position_code=None,
                manager_id=None,
                role=UserRole.EMPLOYEE,
                status=UserStatus.PENDING,
                is_active=False,
            )
        )
        await session.flush()
```

`seed.py` 상단 import에 `UserStatus`를 더한다. `departments[0]`가 그 스코프에 없으면, 이미 만들어진 부서 리스트 변수명을 그대로 쓴다 — `_seed_users`가 부서를 어떻게 받는지 확인하고 첫 부서의 `id`를 쓴다.

- [ ] **Step 5: 통과를 확인한다**

```bash
cd backend && uv run pytest tests/test_seed.py -q
```

Expected: PASS

- [ ] **Step 6: 멱등성을 확인한다**

```bash
cd backend && uv run pytest tests/test_seed.py -q -k "idempot or twice"
```

Expected: PASS (기존 멱등성 테스트가 있으면 통과. 없으면 이 단계는 건너뛴다)

- [ ] **Step 7: 커밋**

```bash
git add backend/tests/factories.py backend/app/seed.py backend/tests/test_seed.py
git commit -m "feat(seed): 승인 대기 계정 1건 추가"
```

---

## Task 5: 스키마 (Pydantic)

**Files:**
- Modify: `backend/app/schemas/auth.py`
- Modify: `backend/app/schemas/admin.py:120-159`
- Test: `backend/tests/test_schemas_admin.py`

- [ ] **Step 1: 실패하는 테스트를 쓴다**

`backend/tests/test_schemas_admin.py` 끝에 추가:

```python
def test_admin_user_out_allows_null_employee_no():
    from app.enums import UserRole, UserStatus
    from app.schemas.admin import AdminUserOut

    out = AdminUserOut(
        id=1,
        email="a@b.com",
        name="가입자",
        employee_no=None,
        department_id=1,
        department_name="부서",
        position_code=None,
        manager_id=None,
        manager_name=None,
        role=UserRole.EMPLOYEE,
        status=UserStatus.PENDING,
        is_active=False,
    )
    assert out.employee_no is None
    assert out.status is UserStatus.PENDING


def test_admin_user_update_has_no_status_field():
    # status는 전이 엔드포인트만 바꾼다. PATCH로 바꿀 수 있으면 전이 가드를
    # 우회하는 두 번째 경로가 생긴다.
    from app.schemas.admin import AdminUserUpdate

    assert "status" not in AdminUserUpdate.model_fields


def test_user_approve_requires_employee_no_and_position():
    import pytest
    from pydantic import ValidationError as PydanticValidationError

    from app.schemas.admin import UserApprove

    with pytest.raises(PydanticValidationError):
        UserApprove(position_code="STAFF")
    with pytest.raises(PydanticValidationError):
        UserApprove(employee_no="E0100")

    approved = UserApprove(employee_no="E0100", position_code="STAFF")
    assert approved.manager_id is None
    assert approved.role.value == "EMPLOYEE"
```

- [ ] **Step 2: 실패를 확인한다**

```bash
cd backend && uv run pytest tests/test_schemas_admin.py -q -k "null_employee or no_status or approve_requires"
```

Expected: FAIL — `ImportError: cannot import name 'UserApprove'`

- [ ] **Step 3: admin 스키마를 고친다**

`backend/app/schemas/admin.py`에서 `AdminUserOut`의 두 필드를 nullable로 바꾸고 `status`를 더한다:

```python
class AdminUserOut(BaseModel):
    id: int
    email: str
    name: str
    # 가입 대기 계정은 아직 값이 없다. 승인이 값을 채운다.
    employee_no: str | None
    department_id: int
    department_name: str
    position_code: str | None
    manager_id: int | None
    manager_name: str | None
    role: UserRole
    status: UserStatus
    is_active: bool
```

`PasswordSet` 클래스 **바로 위**에 추가:

```python
class UserApprove(BaseModel):
    """가입 승인 시 관리자가 채우는 조직 정보.

    전부 필수다(manager_id 제외). 이 값들이 있어야 ACTIVE가 될 수 있고,
    그 강제가 컬럼 NOT NULL 대신 여기와 서비스에 있다.
    """

    employee_no: str = Field(min_length=1, max_length=20)
    position_code: str = Field(min_length=1, max_length=30)
    manager_id: int | None = None
    role: UserRole = UserRole.EMPLOYEE
```

파일 상단 import에 `UserStatus`를 더한다:

```python
from app.enums import UserRole, UserStatus
```

`AdminUserUpdate`에는 `status`를 **넣지 않는다.**

- [ ] **Step 4: auth 스키마를 더한다**

`backend/app/schemas/auth.py`를 아래로 교체:

```python
from pydantic import BaseModel, EmailStr, Field

from app.enums import UserRole


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class UserOut(BaseModel):
    id: int
    email: str
    name: str
    # ACTIVE 계정만 토큰을 얻을 수 있고, 승인이 이 두 값을 강제하므로
    # 로그인·/auth/me 응답에서는 항상 값이 있다. 모델은 nullable이지만
    # 여기서 str로 두는 것이 프론트 계약을 좁게 유지한다.
    employee_no: str
    position_code: str
    role: UserRole
    department_id: int
    department_name: str
    manager_id: int | None


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


class SignupRequest(BaseModel):
    email: EmailStr
    # 길이는 서비스의 assert_password_length가 본다. max_length는 **문자 수**라
    # 한글 72자(216바이트)를 통과시켜 bcrypt에서 터진다.
    password: str = Field(min_length=1)
    name: str = Field(min_length=1, max_length=50)
    department_id: int


class SignupResponse(BaseModel):
    """토큰을 넣지 않는다. 승인 전에는 로그인할 수 없으므로 토큰을 주면 거짓말이 된다."""

    email: str
    status: str
    message: str


class PublicDepartment(BaseModel):
    """미인증 가입 폼의 부서 드롭다운용. id·name만 낸다."""

    id: int
    name: str
```

- [ ] **Step 5: 통과를 확인한다**

```bash
cd backend && uv run pytest tests/test_schemas_admin.py -q
```

Expected: PASS

- [ ] **Step 6: 커밋**

```bash
git add backend/app/schemas/auth.py backend/app/schemas/admin.py backend/tests/test_schemas_admin.py
git commit -m "feat(user): 가입·승인 스키마"
```

---

## Task 6: 부서 검증 공유 이동

`signup.py`가 부서 존재 검증을 써야 한다. 복사하면 검증이 두 벌이 되어 한쪽만 고쳐진다.

**Files:**
- Modify: `backend/app/services/admin/common.py`
- Modify: `backend/app/services/admin/users.py:126-132`
- Test: `backend/tests/test_admin_common.py`

- [ ] **Step 1: 실패하는 테스트를 쓴다**

`backend/tests/test_admin_common.py` 끝에 추가:

```python
async def test_assert_department_rejects_missing(db_session):
    import pytest

    from app.errors import ValidationError
    from app.services.admin.common import assert_department

    with pytest.raises(ValidationError) as exc:
        await assert_department(db_session, 999999)
    assert exc.value.code == "INVALID_DEPARTMENT"
    assert exc.value.field == "department_id"


async def test_assert_department_accepts_existing(db_session):
    from app.services.admin.common import assert_department
    from tests.factories import make_department

    department = await make_department(db_session)
    await db_session.flush()
    await assert_department(db_session, department.id)  # 예외가 나지 않으면 통과
```

- [ ] **Step 2: 실패를 확인한다**

```bash
cd backend && uv run pytest tests/test_admin_common.py -q -k assert_department
```

Expected: FAIL — `ImportError: cannot import name 'assert_department'`

- [ ] **Step 3: common.py로 옮긴다**

`backend/app/services/admin/common.py`의 `assert_unique` **위**에 추가:

```python
async def assert_department(session: AsyncSession, department_id: int) -> None:
    """부서 존재 확인.

    `user.department_id`에는 FK가 없다 — 공유 테이블이 우리 스키마를 역참조하면 계정을
    공유하는 상대 프로젝트가 사용자를 만들 때 우리 department 행이 있어야 하기 때문이다.
    그래서 존재 검증을 서비스가 한다. 관리자 생성/수정과 미인증 가입이 **같은 함수**를
    부른다 — 복사하면 검증이 두 벌이 되어 한쪽만 고쳐진다.
    """
    from app.models import Department

    if await session.get(Department, department_id) is None:
        raise ValidationError(
            "INVALID_DEPARTMENT",
            f"존재하지 않는 부서입니다: {department_id}",
            field="department_id",
        )
```

- [ ] **Step 4: admin/users.py에서 지우고 참조를 바꾼다**

`backend/app/services/admin/users.py`에서 `_assert_department` 함수 정의(126~132줄 부근)를 **통째로 삭제**하고, import를 아래로 교체:

```python
from app.services.admin.common import assert_department, assert_password_length, assert_unique
```

호출부 두 곳(`create_user`의 `await _assert_department(session, payload.department_id)`와 `update_user`의 `await _assert_department(session, changes["department_id"])`)에서 `_assert_department` → `assert_department`로 바꾼다.

- [ ] **Step 5: 편집이 반영됐는지 grep으로 확인한다**

```bash
cd backend && grep -rn "_assert_department" app/
```

Expected: 출력 없음 (언더스코어 버전이 남아 있으면 안 된다)

- [ ] **Step 6: 통과를 확인한다**

```bash
cd backend && uv run pytest tests/test_admin_common.py tests/test_admin_users_api.py -q
```

Expected: PASS

- [ ] **Step 7: 커밋**

```bash
git add backend/app/services/admin/common.py backend/app/services/admin/users.py backend/tests/test_admin_common.py
git commit -m "refactor(admin): 부서 검증을 common으로 옮겨 가입 경로와 공유"
```

---

## Task 7: 가입 서비스

**Files:**
- Create: `backend/app/services/signup.py`
- Test: `backend/tests/test_signup_api.py` (Create — 서비스 테스트는 Task 8의 API 테스트로 함께 덮는다)

- [ ] **Step 1: 서비스를 만든다**

이 태스크는 서비스만 만들고, 테스트는 Task 8에서 API와 함께 쓴다 — 서비스가 라우터 없이 호출될 일이 없어 통합 테스트가 더 정확하기 때문이다.

`backend/app/services/signup.py` 생성:

```python
"""미인증 가입 경로.

가입은 열되 승인은 관리자가 한다. 가입자는 이메일·이름·비밀번호·부서만 내고,
사번·직급·결재자·역할은 관리자가 승인 시점에 채운다 — 그 값들은 결재선과 정산 귀속의
근거라 본인이 고르면 틀린다.
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.enums import UserRole, UserStatus
from app.errors import ConflictError
from app.models import Department, User
from app.schemas.auth import PublicDepartment, SignupRequest, SignupResponse
from app.security import hash_password
from app.services.admin.common import assert_department, assert_password_length
from app.services.user_status import SignupActor, assert_signup_transition_allowed

_PENDING_MESSAGE = "가입 신청이 접수되었습니다. 관리자 승인 후 로그인할 수 있습니다."


async def list_public_departments(session: AsyncSession) -> list[PublicDepartment]:
    """미인증 가입 폼의 부서 드롭다운용. id·name만 낸다.

    부서명이 로그인 없이 보이는 것은 의도된 노출이다. 데모 조직도이고, 대안(부서를
    관리자가 승인 시점에 고르게 하기)은 가입자가 자기 소속을 아는데도 못 적게 만든다.
    """
    rows = await session.execute(
        select(Department.id, Department.name).order_by(Department.code)
    )
    return [PublicDepartment(id=row[0], name=row[1]) for row in rows]


async def signup(session: AsyncSession, *, payload: SignupRequest) -> SignupResponse:
    assert_password_length(payload.password)
    await assert_department(session, payload.department_id)

    existing = await session.scalar(select(User).where(User.email == payload.email))
    if existing is not None:
        return await _resubmit(session, existing=existing, payload=payload)

    user = User(
        email=payload.email,
        password_hash=hash_password(payload.password),
        name=payload.name,
        employee_no=None,
        department_id=payload.department_id,
        position_code=None,
        manager_id=None,
        role=UserRole.EMPLOYEE,
        status=UserStatus.PENDING,
        # 불변식: status != ACTIVE 이면 is_active = false.
        is_active=False,
    )
    session.add(user)
    await session.commit()
    return SignupResponse(
        email=user.email, status=UserStatus.PENDING.value, message=_PENDING_MESSAGE
    )


async def _resubmit(
    session: AsyncSession, *, existing: User, payload: SignupRequest
) -> SignupResponse:
    """이미 있는 이메일의 분기.

    PENDING을 덮어쓰지 않는 것이 중요하다. 덮어쓰기를 허용하면 남이 신청해 둔 대기 계정에
    내가 아는 비밀번호를 덮어씌운 뒤 승인을 기다려 **계정을 가로챌 수 있다.**
    REJECTED는 이미 관리자가 거부한 행이라 같은 위험이 없다.
    """
    if existing.status is UserStatus.PENDING:
        raise ConflictError(
            "ALREADY_PENDING", "이미 승인 대기 중인 이메일입니다", field="email"
        )
    if existing.status is UserStatus.ACTIVE:
        raise ConflictError(
            "DUPLICATE_EMAIL", f"이미 사용 중인 이메일입니다: {payload.email}", field="email"
        )

    # REJECTED -> PENDING. 전이 가드는 하나만 통과한다.
    assert_signup_transition_allowed(
        existing.status, UserStatus.PENDING, actor=SignupActor.APPLICANT
    )
    existing.name = payload.name
    existing.department_id = payload.department_id
    existing.password_hash = hash_password(payload.password)
    existing.status = UserStatus.PENDING
    existing.is_active = False
    await session.commit()
    return SignupResponse(
        email=existing.email, status=UserStatus.PENDING.value, message=_PENDING_MESSAGE
    )
```

- [ ] **Step 2: 임포트가 깨지지 않는지 확인한다**

```bash
cd backend && uv run python -c "import app.services.signup; print('ok')"
```

Expected: `ok`

- [ ] **Step 3: 커밋**

```bash
git add backend/app/services/signup.py
git commit -m "feat(signup): 가입 서비스"
```

---

## Task 8: 가입 라우터 + 부서 목록 + 테스트

**Files:**
- Modify: `backend/app/routers/auth.py`
- Test: `backend/tests/test_signup_api.py` (Create)

- [ ] **Step 1: 실패하는 테스트를 쓴다**

`backend/tests/test_signup_api.py` 생성:

```python
"""가입 API. 미인증 경로이므로 토큰 없이 호출한다."""

import pytest
from sqlalchemy import select

from app.enums import UserStatus
from app.models import User
from tests.factories import make_department, make_user

_PW = "signup1234!"


async def _department_id(db_session) -> int:
    department = await make_department(db_session)
    await db_session.flush()
    return department.id


async def test_public_departments_needs_no_token(client, db_session):
    await _department_id(db_session)
    await db_session.commit()

    response = await client.get("/api/v1/auth/departments")
    assert response.status_code == 200
    body = response.json()
    assert len(body) >= 1
    # id·name만 낸다. 다른 필드가 새면 안 된다.
    assert set(body[0]) == {"id", "name"}


async def test_signup_creates_pending_user(client, db_session):
    department_id = await _department_id(db_session)
    await db_session.commit()

    response = await client.post(
        "/api/v1/auth/signup",
        json={
            "email": "newcomer@skon.example",
            "password": _PW,
            "name": "새사람",
            "department_id": department_id,
        },
    )
    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "PENDING"
    assert "access_token" not in body  # 승인 전에 토큰을 주면 거짓말이 된다

    user = await db_session.scalar(
        select(User).where(User.email == "newcomer@skon.example")
    )
    assert user is not None
    assert user.status is UserStatus.PENDING
    assert user.is_active is False
    assert user.employee_no is None
    assert user.position_code is None


async def test_signup_rejects_short_password(client, db_session):
    department_id = await _department_id(db_session)
    await db_session.commit()

    response = await client.post(
        "/api/v1/auth/signup",
        json={
            "email": "short@skon.example",
            "password": "1234",
            "name": "짧은비번",
            "department_id": department_id,
        },
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "PASSWORD_TOO_SHORT"


async def test_signup_rejects_unknown_department(client, db_session):
    response = await client.post(
        "/api/v1/auth/signup",
        json={
            "email": "nodept@skon.example",
            "password": _PW,
            "name": "부서없음",
            "department_id": 999999,
        },
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "INVALID_DEPARTMENT"


async def test_signup_conflicts_with_active_email(client, db_session):
    user = await make_user(db_session)
    await db_session.commit()

    response = await client.post(
        "/api/v1/auth/signup",
        json={
            "email": user.email,
            "password": _PW,
            "name": "중복",
            "department_id": user.department_id,
        },
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "DUPLICATE_EMAIL"


async def test_signup_conflicts_with_pending_email(client, db_session):
    """대기 중인 신청은 덮어쓰지 않는다 — 계정 탈취 경로가 된다."""
    user = await make_user(db_session, status=UserStatus.PENDING, is_active=False)
    original_hash = user.password_hash
    await db_session.commit()

    response = await client.post(
        "/api/v1/auth/signup",
        json={
            "email": user.email,
            "password": "attacker-known-pw",
            "name": "가로채기",
            "department_id": user.department_id,
        },
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "ALREADY_PENDING"

    await db_session.refresh(user)
    assert user.password_hash == original_hash  # 비밀번호가 덮이지 않았다


async def test_signup_resubmits_after_rejection(client, db_session):
    user = await make_user(db_session, status=UserStatus.REJECTED, is_active=False)
    original_hash = user.password_hash
    await db_session.commit()

    response = await client.post(
        "/api/v1/auth/signup",
        json={
            "email": user.email,
            "password": _PW,
            "name": "재신청",
            "department_id": user.department_id,
        },
    )
    assert response.status_code == 201
    assert response.json()["status"] == "PENDING"

    await db_session.refresh(user)
    assert user.status is UserStatus.PENDING
    assert user.is_active is False
    assert user.name == "재신청"
    assert user.password_hash != original_hash
```

- [ ] **Step 2: 실패를 확인한다**

```bash
cd backend && uv run pytest tests/test_signup_api.py -q
```

Expected: FAIL — 전부 404 (`assert 404 == 201` 등)

- [ ] **Step 3: 라우터를 더한다**

`backend/app/routers/auth.py`에서 import를 아래로 교체:

```python
from fastapi import APIRouter, status as http_status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.deps import CurrentUser, DbSession
from app.errors import AuthError
from app.models import Department, User
from app.schemas.auth import (
    LoginRequest,
    LoginResponse,
    PublicDepartment,
    SignupRequest,
    SignupResponse,
    UserOut,
)
from app.security import create_access_token, hash_password, verify_password
from app.services import signup as signup_service
```

파일 **끝**에 추가:

```python
@router.get("/departments", response_model=list[PublicDepartment])
async def public_departments(session: DbSession) -> list[PublicDepartment]:
    """**미인증.** 가입 폼의 부서 드롭다운용으로 id·name만 낸다.

    `get_principal`을 지나지 않으므로 `SCOPE_REQUIREMENTS`에 넣지 않는다 — 소진 가드는
    인증 라우트만 대조한다.
    """
    return await signup_service.list_public_departments(session)


@router.post(
    "/signup", response_model=SignupResponse, status_code=http_status.HTTP_201_CREATED
)
async def signup(payload: SignupRequest, session: DbSession) -> SignupResponse:
    """**미인증.** 가입 신청만 만든다. 승인 전에는 로그인할 수 없으므로 토큰을 주지 않는다."""
    return await signup_service.signup(session, payload=payload)
```

- [ ] **Step 4: 통과를 확인한다**

```bash
cd backend && uv run pytest tests/test_signup_api.py -q
```

Expected: PASS (7 passed)

- [ ] **Step 5: 스코프 표 가드가 여전히 통과하는지 확인한다**

```bash
cd backend && uv run pytest tests/test_api_scopes.py tests/test_scope_enforcement.py -q
```

Expected: PASS — 새 라우트는 미인증이라 표에 없어야 맞다. 실패하면 `get_principal`이 딸려 들어간 것이다.

- [ ] **Step 6: mutation으로 탈취 가드를 확인한다**

`app/services/signup.py`의 `ALREADY_PENDING` 분기 3줄을 일시적으로 주석 처리한다.

```bash
cd backend && uv run pytest tests/test_signup_api.py -q -k pending_email
```

Expected: FAIL — `test_signup_conflicts_with_pending_email`이 깨진다. **확인 후 되돌린다.**

```bash
cd backend && git diff --stat app/services/signup.py
```

Expected: 되돌린 뒤 출력 없음

- [ ] **Step 7: 커밋**

```bash
git add backend/app/routers/auth.py backend/tests/test_signup_api.py
git commit -m "feat(signup): 가입·부서목록 미인증 엔드포인트"
```

---

## Task 9: 로그인 상태 안내

**Files:**
- Modify: `backend/app/routers/auth.py:32-47`
- Test: `backend/tests/test_auth.py`

- [ ] **Step 1: 실패하는 테스트를 쓴다**

`backend/tests/test_auth.py` 끝에 추가:

```python
async def test_pending_user_with_correct_password_gets_pending_code(client, db_session):
    from app.enums import UserStatus
    from app.security import hash_password
    from tests.factories import make_user

    user = await make_user(db_session, status=UserStatus.PENDING, is_active=False)
    user.password_hash = hash_password("pending1234!")
    await db_session.commit()

    response = await client.post(
        "/api/v1/auth/login", json={"email": user.email, "password": "pending1234!"}
    )
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "PENDING_APPROVAL"


async def test_pending_user_with_wrong_password_leaks_nothing(client, db_session):
    """상태는 비밀번호를 맞힌 사람에게만 알린다. 아니면 계정 존재가 샌다."""
    from app.enums import UserStatus
    from app.security import hash_password
    from tests.factories import make_user

    user = await make_user(db_session, status=UserStatus.PENDING, is_active=False)
    user.password_hash = hash_password("pending1234!")
    await db_session.commit()

    response = await client.post(
        "/api/v1/auth/login", json={"email": user.email, "password": "wrong-password"}
    )
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "INVALID_CREDENTIALS"


async def test_rejected_user_gets_rejected_code(client, db_session):
    from app.enums import UserStatus
    from app.security import hash_password
    from tests.factories import make_user

    user = await make_user(db_session, status=UserStatus.REJECTED, is_active=False)
    user.password_hash = hash_password("rejected1234!")
    await db_session.commit()

    response = await client.post(
        "/api/v1/auth/login", json={"email": user.email, "password": "rejected1234!"}
    )
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "SIGNUP_REJECTED"


async def test_suspended_active_user_stays_generic(client, db_session):
    """승인됐지만 관리자가 정지시킨 계정은 기존 메시지를 유지한다."""
    from app.enums import UserStatus
    from app.security import hash_password
    from tests.factories import make_user

    user = await make_user(db_session, status=UserStatus.ACTIVE, is_active=False)
    user.password_hash = hash_password("suspended1234!")
    await db_session.commit()

    response = await client.post(
        "/api/v1/auth/login", json={"email": user.email, "password": "suspended1234!"}
    )
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "INVALID_CREDENTIALS"
```

- [ ] **Step 2: 실패를 확인한다**

```bash
cd backend && uv run pytest tests/test_auth.py -q -k "pending or rejected or suspended"
```

Expected: FAIL — `assert 'INVALID_CREDENTIALS' == 'PENDING_APPROVAL'`

- [ ] **Step 3: 로그인 함수를 고친다**

`backend/app/routers/auth.py`의 `login` 함수 본문을 아래로 교체:

```python
@router.post("/login", response_model=LoginResponse)
async def login(payload: LoginRequest, session: DbSession) -> LoginResponse:
    user = (
        await session.execute(select(User).where(User.email == payload.email))
    ).scalar_one_or_none()
    # 사용자가 없거나 비활성이어도 bcrypt 검증을 항상 수행한다. 건너뛰면 응답 시간으로
    # 계정 존재 여부가 새어나가, 위에서 에러 코드를 통일한 의미가 사라진다.
    stored_hash = user.password_hash if user is not None else _DUMMY_PASSWORD_HASH
    password_ok = verify_password(payload.password, stored_hash)
    if user is None or not password_ok:
        raise AuthError("INVALID_CREDENTIALS", "이메일 또는 비밀번호가 올바르지 않습니다")

    # 여기서부터는 비밀번호를 맞힌 사람이다. 그에게만 가입 상태를 알린다 — 상태를 비밀번호
    # 검증 **앞에서** 보면 이메일만으로 계정 존재가 드러난다. 순서가 방어의 전부다.
    if user.status is UserStatus.PENDING:
        raise AuthError("PENDING_APPROVAL", "관리자 승인 대기 중입니다")
    if user.status is UserStatus.REJECTED:
        raise AuthError("SIGNUP_REJECTED", "가입이 거절되었습니다. 관리자에게 문의하십시오")
    if not user.is_active:
        # 승인됐지만 관리자가 정지시킨 계정. 이유를 알릴 근거가 없으므로 기존 메시지다.
        raise AuthError("INVALID_CREDENTIALS", "이메일 또는 비밀번호가 올바르지 않습니다")

    return LoginResponse(
        access_token=create_access_token(user_id=user.id),
        user=await _to_user_out(session, user),
    )
```

파일 상단 import에 `UserStatus`를 더한다:

```python
from app.enums import UserStatus
```

- [ ] **Step 4: 통과를 확인한다**

```bash
cd backend && uv run pytest tests/test_auth.py -q
```

Expected: PASS

- [ ] **Step 5: mutation으로 순서 가드를 확인한다**

상태 검사 블록을 `password_ok` 검사 **위**로 옮긴다.

```bash
cd backend && uv run pytest tests/test_auth.py -q -k wrong_password_leaks
```

Expected: FAIL — `test_pending_user_with_wrong_password_leaks_nothing`이 깨진다. **확인 후 되돌린다.**

```bash
cd backend && git diff --stat app/routers/auth.py
```

Expected: 되돌린 뒤 출력 없음

- [ ] **Step 6: 커밋**

```bash
git add backend/app/routers/auth.py backend/tests/test_auth.py
git commit -m "feat(auth): 승인 대기·거절 상태를 비밀번호 검증 뒤에만 알린다"
```

---

## Task 10: 승인 · 거절 서비스

**Files:**
- Modify: `backend/app/services/admin/users.py`
- Test: `backend/tests/test_admin_users_api.py` (Task 11에서 API와 함께)

- [ ] **Step 1: 서비스 함수를 더한다**

`backend/app/services/admin/users.py`의 `_to_out` 안 `AdminUserOut(` 생성자에 `status`를 더한다. `role=user.role,` 다음 줄:

```python
            status=user.status,
```

`UserFilters` 데이터클래스에 필드를 더한다. `is_active: bool | None = None` 다음 줄:

```python
    status: UserStatus | None = None
```

`list_users`의 조건 블록에 더한다. `if filters.is_active is not None:` 블록 다음:

```python
    if filters.status is not None:
        conditions.append(User.status == filters.status)
```

파일 **끝**에 추가:

```python
async def approve_user(
    session: AsyncSession, *, user_id: int, payload: UserApprove
) -> AdminUserOut:
    """가입 승인. 관리자가 조직 정보를 채우고 계정을 연다.

    검증은 create_user의 것을 그대로 쓴다 — 사번 unique, 직급 공통코드, 결재자 존재·
    자기참조 금지. 컬럼 NOT NULL이 빠진 자리를 이 검증이 메운다.
    """
    user = await _load(session, user_id)
    assert_signup_transition_allowed(user.status, UserStatus.ACTIVE, actor=SignupActor.ADMIN)

    await assert_unique(
        session,
        User.employee_no,
        payload.employee_no,
        code="DUPLICATE_EMPLOYEE_NO",
        message=f"이미 사용 중인 사번입니다: {payload.employee_no}",
        field="employee_no",
    )
    await _assert_manager(session, payload.manager_id, self_id=user.id)
    await validate_codes(session, [(_POSITION_GROUP, "position_code", payload.position_code)])

    user.employee_no = payload.employee_no
    user.position_code = payload.position_code
    user.manager_id = payload.manager_id
    user.role = payload.role
    user.status = UserStatus.ACTIVE
    # 불변식의 반대편. 승인이 로그인을 연다.
    user.is_active = True
    await session.commit()
    await session.refresh(user)
    return (await _to_out(session, [user]))[0]


async def reject_user(session: AsyncSession, *, user_id: int) -> AdminUserOut:
    """가입 거절. 행은 지우지 않는다 — 거절 이력이 남고, 이메일 unique 제약과 충돌하지
    않으며, 재신청 경로(REJECTED -> PENDING)가 생긴다."""
    user = await _load(session, user_id)
    assert_signup_transition_allowed(user.status, UserStatus.REJECTED, actor=SignupActor.ADMIN)
    user.status = UserStatus.REJECTED
    user.is_active = False
    await session.commit()
    await session.refresh(user)
    return (await _to_out(session, [user]))[0]
```

import를 더한다. 파일 상단:

```python
from app.enums import UserRole, UserStatus
from app.schemas.admin import (
    AdminUserCreate,
    AdminUserOut,
    AdminUserUpdate,
    PasswordSet,
    UserApprove,
)
from app.services.user_status import SignupActor, assert_signup_transition_allowed
```

- [ ] **Step 2: create_user가 status를 명시하는지 확인한다**

`create_user`의 `User(...)` 생성자에 `status`를 넣지 **않는다** — 모델 default가 `ACTIVE`다. 관리자가 직접 만든 계정은 항상 승인된 계정이다.

```bash
cd backend && uv run pytest tests/test_admin_users_api.py -q
```

Expected: PASS (기존 테스트가 여전히 통과)

- [ ] **Step 3: 커밋**

```bash
git add backend/app/services/admin/users.py
git commit -m "feat(admin): 가입 승인·거절 서비스"
```

---

## Task 11: 승인 · 거절 라우터 + 스코프 표

**Files:**
- Modify: `backend/app/routers/admin/users.py`
- Modify: `backend/app/services/api_scopes.py:90-94`
- Test: `backend/tests/test_admin_users_api.py`

- [ ] **Step 1: 실패하는 테스트를 쓴다**

`backend/tests/test_admin_users_api.py` 끝에 추가:

```python
async def _pending(db_session):
    from app.enums import UserStatus
    from tests.factories import make_user

    user = await make_user(db_session, status=UserStatus.PENDING, is_active=False)
    user.employee_no = None
    user.position_code = None
    await db_session.commit()
    return user


async def test_approve_fills_org_fields_and_opens_login(client, db_session, seeded, login_as):
    from app.enums import UserStatus

    user = await _pending(db_session)
    headers = await login_as("admin@skon.example")

    response = await client.post(
        f"/api/v1/admin/users/{user.id}/approve",
        json={"employee_no": "E0777", "position_code": "STAFF", "role": "EMPLOYEE"},
        headers=headers,
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ACTIVE"
    assert body["employee_no"] == "E0777"
    assert body["is_active"] is True

    await db_session.refresh(user)
    assert user.status is UserStatus.ACTIVE
    assert user.is_active is True


async def test_approve_rejects_duplicate_employee_no(client, db_session, seeded, login_as):
    user = await _pending(db_session)
    headers = await login_as("admin@skon.example")

    response = await client.post(
        f"/api/v1/admin/users/{user.id}/approve",
        json={"employee_no": "E0001", "position_code": "STAFF"},
        headers=headers,
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "DUPLICATE_EMPLOYEE_NO"


async def test_approve_rejects_unknown_position(client, db_session, seeded, login_as):
    user = await _pending(db_session)
    headers = await login_as("admin@skon.example")

    response = await client.post(
        f"/api/v1/admin/users/{user.id}/approve",
        json={"employee_no": "E0778", "position_code": "NOT_A_CODE"},
        headers=headers,
    )
    assert response.status_code == 400


async def test_approve_twice_conflicts(client, db_session, seeded, login_as):
    user = await _pending(db_session)
    headers = await login_as("admin@skon.example")
    body = {"employee_no": "E0779", "position_code": "STAFF"}

    first = await client.post(
        f"/api/v1/admin/users/{user.id}/approve", json=body, headers=headers
    )
    assert first.status_code == 200

    second = await client.post(
        f"/api/v1/admin/users/{user.id}/approve",
        json={"employee_no": "E0780", "position_code": "STAFF"},
        headers=headers,
    )
    assert second.status_code == 409
    assert second.json()["error"]["code"] == "USER_INVALID_TRANSITION"


async def test_reject_closes_account(client, db_session, seeded, login_as):
    from app.enums import UserStatus

    user = await _pending(db_session)
    headers = await login_as("admin@skon.example")

    response = await client.post(
        f"/api/v1/admin/users/{user.id}/reject", headers=headers
    )
    assert response.status_code == 200
    assert response.json()["status"] == "REJECTED"

    await db_session.refresh(user)
    assert user.status is UserStatus.REJECTED
    assert user.is_active is False


async def test_reject_active_user_conflicts(client, db_session, seeded, login_as):
    from tests.factories import make_user

    user = await make_user(db_session)
    await db_session.commit()
    headers = await login_as("admin@skon.example")

    response = await client.post(
        f"/api/v1/admin/users/{user.id}/reject", headers=headers
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "USER_INVALID_TRANSITION"


async def test_list_users_filters_by_status(client, db_session, seeded, login_as):
    await _pending(db_session)
    headers = await login_as("admin@skon.example")

    response = await client.get("/api/v1/admin/users?status=PENDING", headers=headers)
    assert response.status_code == 200
    items = response.json()["items"]
    assert len(items) >= 1
    assert all(item["status"] == "PENDING" for item in items)


async def test_patch_cannot_change_status(client, db_session, seeded, login_as):
    """status는 전이 엔드포인트만 바꾼다. PATCH로 열리면 전이 가드 우회 경로가 생긴다."""
    from app.enums import UserStatus

    user = await _pending(db_session)
    headers = await login_as("admin@skon.example")

    response = await client.patch(
        f"/api/v1/admin/users/{user.id}", json={"status": "ACTIVE"}, headers=headers
    )
    # Pydantic이 모르는 필드를 무시하든 거부하든, 상태는 바뀌지 않아야 한다.
    await db_session.refresh(user)
    assert user.status is UserStatus.PENDING
    assert response.status_code in (200, 422)
```

- [ ] **Step 2: 실패를 확인한다**

```bash
cd backend && uv run pytest tests/test_admin_users_api.py -q -k "approve or reject or filters_by_status"
```

Expected: FAIL — 404

- [ ] **Step 3: 스코프 표에 두 줄을 더한다**

`backend/app/services/api_scopes.py`의 `("POST", "/api/v1/admin/users/{user_id}/password"): _AD,` **다음 줄**에 추가:

```python
    ("POST", "/api/v1/admin/users/{user_id}/approve"): _AD,
    ("POST", "/api/v1/admin/users/{user_id}/reject"): _AD,
```

- [ ] **Step 4: 라우터를 더한다**

`backend/app/routers/admin/users.py`에서 import를 교체:

```python
from app.enums import UserRole, UserStatus
from app.schemas.admin import (
    AdminUserCreate,
    AdminUserOut,
    AdminUserUpdate,
    PasswordSet,
    UserApprove,
)
```

`list_users`의 시그니처에 `is_active` 다음 줄로 추가하고, `UserFilters(...)`에도 넘긴다:

```python
    status: UserStatus | None = None,
```

```python
            status=status,
```

파일 **끝**에 추가:

```python
@router.post("/{user_id}/approve", response_model=AdminUserOut)
async def approve_user(
    user_id: int, payload: UserApprove, user: AdminUser, session: DbSession
) -> AdminUserOut:
    """가입 승인. 관리자가 사번·직급·결재자·역할을 채우면 계정이 열린다."""
    return await service.approve_user(session, user_id=user_id, payload=payload)


@router.post("/{user_id}/reject", response_model=AdminUserOut)
async def reject_user(user_id: int, user: AdminUser, session: DbSession) -> AdminUserOut:
    """가입 거절. 행은 남으므로 같은 이메일로 재신청할 수 있다."""
    return await service.reject_user(session, user_id=user_id)
```

- [ ] **Step 5: 통과를 확인한다**

```bash
cd backend && uv run pytest tests/test_admin_users_api.py -q
```

Expected: PASS

- [ ] **Step 6: 스코프 표 완전성 가드를 확인한다**

```bash
cd backend && uv run pytest tests/test_api_scopes.py tests/test_scope_enforcement.py tests/test_admin_scope_e2e.py -q
```

Expected: PASS

- [ ] **Step 7: mutation으로 스코프 가드를 확인한다**

Step 3에서 더한 두 줄을 일시적으로 지운다.

```bash
cd backend && uv run pytest tests/test_api_scopes.py -q
```

Expected: FAIL 또는 임포트 시점 예외 — "SCOPE_REQUIREMENTS가 실제 라우트와 어긋납니다". **확인 후 되돌린다.**

- [ ] **Step 8: 백엔드 전체를 돌린다**

```bash
cd backend && uv run pytest -q
```

Expected: PASS (569건 + 이번에 더한 것들)

- [ ] **Step 9: 커밋**

```bash
git add backend/app/routers/admin/users.py backend/app/services/api_scopes.py backend/tests/test_admin_users_api.py
git commit -m "feat(admin): 승인·거절 엔드포인트와 status 필터"
```

---

## Task 12: 프론트 타입 · API 클라이언트 · 공개 경로

**Files:**
- Modify: `frontend/src/lib/api/types.ts:303-335`
- Modify: `frontend/src/lib/api/admin.ts:123-137`
- Create: `frontend/src/lib/api/signup.ts`
- Modify: `frontend/src/lib/nav.ts:2`
- Modify: `frontend/src/lib/admin.ts`
- Test: `frontend/src/lib/nav.test.ts` (있으면 수정, 없으면 생성)

- [ ] **Step 1: 실패하는 테스트를 쓴다**

`frontend/src/lib/nav.test.ts`에 추가한다. 파일이 없으면 아래 내용으로 생성한다:

```ts
import { describe, expect, it } from 'vitest';
import { isPublicPath } from './nav';

describe('isPublicPath', () => {
	it('가입 화면은 로그인 없이 열린다', () => {
		expect(isPublicPath('/signup')).toBe(true);
	});

	it('로그인 화면은 공개다', () => {
		expect(isPublicPath('/login')).toBe(true);
	});

	it('출장 목록은 공개가 아니다', () => {
		expect(isPublicPath('/trips')).toBe(false);
	});
});
```

- [ ] **Step 2: 실패를 확인한다**

```bash
cd frontend && npm test -- nav
```

Expected: FAIL — `expected false to be true` (`/signup`)

- [ ] **Step 3: 공개 경로를 더한다**

`frontend/src/lib/nav.ts`의 2번째 줄을 교체:

```ts
const PUBLIC_PREFIXES = ['/login', '/signup'];
```

- [ ] **Step 4: 통과를 확인한다**

```bash
cd frontend && npm test -- nav
```

Expected: PASS

- [ ] **Step 5: 타입을 더한다**

`frontend/src/lib/api/types.ts`의 `AdminUser` 인터페이스 **위**에 추가:

```ts
export type UserStatus = 'PENDING' | 'ACTIVE' | 'REJECTED';
```

`AdminUser`를 교체:

```ts
export interface AdminUser {
	id: number;
	email: string;
	name: string;
	// 가입 대기 계정은 아직 값이 없다. 승인이 채운다.
	employee_no: string | null;
	department_id: number;
	department_name: string;
	position_code: string | null;
	manager_id: number | null;
	manager_name: string | null;
	role: UserRole;
	status: UserStatus;
	is_active: boolean;
}
```

파일 끝에 추가:

```ts
export interface UserApproveInput {
	employee_no: string;
	position_code: string;
	manager_id?: number | null;
	role?: UserRole;
}

export interface SignupInput {
	email: string;
	password: string;
	name: string;
	department_id: number;
}

export interface SignupResult {
	email: string;
	status: UserStatus;
	message: string;
}

export interface PublicDepartment {
	id: number;
	name: string;
}
```

- [ ] **Step 6: admin 클라이언트를 더한다**

`frontend/src/lib/api/admin.ts`의 `setUserPassword` **다음**에 추가:

```ts
export function approveUser(id: number, input: UserApproveInput): Promise<AdminUser> {
	return authRequest<AdminUser>(`/api/v1/admin/users/${id}/approve`, {
		method: 'POST',
		body: input
	});
}

export function rejectUser(id: number): Promise<AdminUser> {
	return authRequest<AdminUser>(`/api/v1/admin/users/${id}/reject`, { method: 'POST' });
}
```

파일 상단 import에 `UserApproveInput`을 더한다.

- [ ] **Step 7: 가입 클라이언트를 만든다**

`frontend/src/lib/api/signup.ts` 생성:

```ts
import { request } from './client';
import type { PublicDepartment, SignupInput, SignupResult } from './types';

// 미인증 호출이므로 authRequest가 아니라 raw request를 쓴다. login과 같은 부류이며,
// 이 두 경로 외에 raw request를 늘리지 않는다 — 토큰을 손으로 붙이는 곳이 생기면
// 하나만 빠뜨려도 조용히 미인증 요청이 나가고 그 401은 진짜 인증 실패와 구분되지 않는다.
export function listPublicDepartments(): Promise<PublicDepartment[]> {
	return request<PublicDepartment[]>('/api/v1/auth/departments');
}

export function signup(input: SignupInput): Promise<SignupResult> {
	return request<SignupResult>('/api/v1/auth/signup', { method: 'POST', body: input });
}
```

- [ ] **Step 8: 상태 라벨을 더한다**

`frontend/src/lib/admin.ts`에 추가한다. 기존 `ROLE_LABELS` 근처:

```ts
export const STATUS_LABELS: Record<UserStatus, string> = {
	PENDING: '승인 대기',
	ACTIVE: '활성',
	REJECTED: '거절됨'
};
```

파일 상단 import에 `UserStatus`를 더한다.

- [ ] **Step 9: 타입체크를 돌린다**

```bash
cd frontend && npm run check
```

Expected: 이 시점에는 `admin/users/+page.svelte`가 `user.employee_no`(now nullable)를 그대로 쓰고 있어 **에러가 날 수 있다.** Task 13에서 고친다. 에러 내용을 기록만 하고 넘어간다.

- [ ] **Step 10: 커밋**

```bash
git add frontend/src/lib/api/types.ts frontend/src/lib/api/admin.ts frontend/src/lib/api/signup.ts frontend/src/lib/nav.ts frontend/src/lib/admin.ts frontend/src/lib/nav.test.ts
git commit -m "feat(front): 가입·승인 타입과 API 클라이언트"
```

---

## Task 13: 관리자 화면 — status 열 · 필터 · 승인 모달

**Files:**
- Modify: `frontend/src/routes/admin/users/+page.svelte`

- [ ] **Step 1: script 블록을 확장한다**

`frontend/src/routes/admin/users/+page.svelte`의 import 블록을 교체:

```svelte
	import {
		approveUser,
		createUser,
		listDepartments,
		listUsers,
		rejectUser,
		setUserPassword,
		updateUser
	} from '$lib/api/admin';
	import { AdminResource } from '$lib/stores/admin-resource.svelte';
	import { ROLE_LABELS, STATUS_LABELS, activeLabel, departmentOptions } from '$lib/admin';
	import { auth } from '$lib/stores/auth.svelte';
	import type { AdminUser, Department, UserRole, UserStatus } from '$lib/api/types';
	import Badge from '$lib/components/Badge.svelte';
	import Button from '$lib/components/Button.svelte';
	import Card from '$lib/components/Card.svelte';
	import EmptyState from '$lib/components/EmptyState.svelte';
	import Modal from '$lib/components/Modal.svelte';
	import Select from '$lib/components/Select.svelte';
	import TextInput from '$lib/components/TextInput.svelte';
```

`ROLE_OPTIONS` 아래에 추가:

```svelte
	const STATUS_OPTIONS: { value: string; label: string }[] = [
		{ value: '', label: '전체' },
		{ value: 'PENDING', label: STATUS_LABELS.PENDING },
		{ value: 'ACTIVE', label: STATUS_LABELS.ACTIVE },
		{ value: 'REJECTED', label: STATUS_LABELS.REJECTED }
	];

	// Badge의 Tone은 neutral | primary | success | danger 넷뿐이다.
	// 'warning'은 존재하지 않으므로 쓰면 svelte-check가 에러를 낸다.
	function statusTone(status: UserStatus): 'success' | 'primary' | 'danger' {
		if (status === 'ACTIVE') return 'success';
		if (status === 'PENDING') return 'primary';
		return 'danger';
	}
```

`let search = $state('');` 다음 줄에 추가:

```svelte
	let statusFilter = $state('');
```

목록 로더를 교체:

```svelte
	const users = new AdminResource<AdminUser>(async () => {
		const page = await listUsers({
			q: search || undefined,
			status: statusFilter || undefined,
			size: 100
		});
		return page.items;
	});
```

`newPassword` 선언 아래에 승인 모달 상태를 더한다:

```svelte
	// 승인 모달. 대상이 null이면 닫힌 상태다.
	let approving = $state<AdminUser | null>(null);
	let approveEmployeeNo = $state('');
	let approvePositionCode = $state('STAFF');
	let approveManagerId = $state('');
	let approveRole = $state('EMPLOYEE');

	// 결재자 후보는 이미 불러온 목록에서 고른다. 승인 대기 계정은 결재자가 될 수 없다.
	const managerChoices = $derived([
		{ value: '', label: '없음' },
		...users.items
			.filter((candidate) => candidate.status === 'ACTIVE')
			.map((candidate) => ({
				value: String(candidate.id),
				label: `${candidate.name} (${candidate.employee_no ?? '—'})`
			}))
	]);

	function openApprove(user: AdminUser): void {
		approving = user;
		approveEmployeeNo = '';
		approvePositionCode = 'STAFF';
		approveManagerId = '';
		approveRole = 'EMPLOYEE';
	}

	async function confirmApprove(): Promise<void> {
		// 중복 제출 가드. 버튼 disabled만으로는 다른 경로를 막지 못하고,
		// 승인은 멱등하지 않아 두 번째 호출이 409로 떨어진다.
		if (approving === null || users.busy) return;
		const target = approving;
		const ok = await users.run(
			() =>
				approveUser(target.id, {
					employee_no: approveEmployeeNo,
					position_code: approvePositionCode,
					manager_id: approveManagerId ? Number(approveManagerId) : null,
					role: approveRole as UserRole
				}),
			'승인하지 못했습니다'
		);
		if (ok) approving = null;
	}

	function reject(user: AdminUser): void {
		void users.run(() => rejectUser(user.id), '거절하지 못했습니다');
	}
```

- [ ] **Step 2: 검색 줄에 상태 필터를 더한다**

`<div class="mt-8 flex items-end gap-3">` 블록을 교체:

```svelte
<div class="mt-8 flex flex-col gap-3 tablet:flex-row tablet:items-end">
	<div class="w-full tablet:max-w-md">
		<TextInput label="검색" bind:value={search} placeholder="이름 · 이메일 · 사번" />
	</div>
	<div class="w-full tablet:max-w-[12rem]">
		<Select label="상태" bind:value={statusFilter} options={STATUS_OPTIONS} />
	</div>
	<Button variant="secondary" onclick={() => users.load()}>검색</Button>
</div>
```

- [ ] **Step 3: 표에 status를 반영한다**

`<td class="py-3 font-mono text-body-sm text-muted">{user.employee_no}</td>`를 교체 — 대기 계정은 사번이 없다:

```svelte
						<td class="py-3 font-mono text-body-sm text-muted">{user.employee_no ?? '—'}</td>
```

상태 `<td>` 블록을 교체:

```svelte
						<td class="py-3">
							<div class="flex flex-wrap items-center gap-2">
								<Badge tone={statusTone(user.status)}>{STATUS_LABELS[user.status]}</Badge>
								{#if user.status === 'ACTIVE'}
									<Badge tone={user.is_active ? 'success' : 'neutral'}>
										{activeLabel(user.is_active)}
									</Badge>
								{/if}
							</div>
						</td>
```

액션 `<td>`의 `{:else}` 분기를 교체 — 대기 계정에는 승인·거절만 보인다:

```svelte
							{:else if user.status === 'PENDING'}
								<Button variant="tertiary" onclick={() => openApprove(user)}>승인</Button>
								<Button variant="tertiary" onclick={() => reject(user)}>거절</Button>
							{:else}
								<Button variant="tertiary" onclick={() => (resettingId = user.id)}>
									비밀번호
								</Button>
								<Button
									variant="tertiary"
									disabled={user.id === auth.user?.id || user.status !== 'ACTIVE'}
									onclick={() => toggleActive(user)}
								>
									{user.is_active ? '비활성화' : '활성화'}
								</Button>
							{/if}
```

역할 `<select>`에 `disabled`를 더한다 — 대기 계정의 역할은 승인 모달에서 정한다:

```svelte
								<select
									aria-label="{user.name} 역할"
									value={user.role}
									disabled={user.status !== 'ACTIVE'}
									onchange={(event) => changeRole(user, event.currentTarget.value as UserRole)}
									class="h-10 rounded-sm border border-hairline bg-canvas px-2 text-body-sm text-ink disabled:opacity-50"
								>
```

- [ ] **Step 4: 승인 모달을 더한다**

파일 **끝**에 추가:

```svelte
<Modal open={approving !== null} title="가입 승인" onclose={() => (approving = null)}>
	{#if approving}
		<p class="text-body-sm text-muted">
			{approving.name} ({approving.email}) · {approving.department_name}
		</p>
		<div class="mt-4 grid grid-cols-1 gap-4 tablet:grid-cols-2">
			<TextInput label="사번" bind:value={approveEmployeeNo} placeholder="E0100" />
			<TextInput label="직급코드" bind:value={approvePositionCode} placeholder="STAFF" />
			<Select label="결재자" bind:value={approveManagerId} options={managerChoices} />
			<Select label="역할" bind:value={approveRole} options={ROLE_OPTIONS} />
		</div>
		<div class="mt-6 flex justify-end gap-2">
			<Button variant="secondary" onclick={() => (approving = null)}>취소</Button>
			<Button
				disabled={users.busy || !approveEmployeeNo || !approvePositionCode}
				onclick={confirmApprove}
			>
				{users.busy ? '처리 중…' : '승인'}
			</Button>
		</div>
	{/if}
</Modal>
```

- [ ] **Step 5: 안내 문구를 갱신한다**

목록 아래 `<p class="mt-3 text-caption text-muted">` 블록을 교체:

```svelte
	<p class="mt-3 text-caption text-muted">
		사용자는 삭제할 수 없습니다 — 출장·정산·카드가 참조합니다. 비활성화하면 로그인이 즉시
		막힙니다. 자기 자신은 강등·비활성화할 수 없습니다(409). 승인 대기 계정은 사번·직급이
		비어 있으며, 승인할 때 채웁니다. 거절해도 행은 남아 같은 이메일로 재신청할 수 있습니다.
	</p>
```

- [ ] **Step 6: 타입체크를 돌린다**

```bash
cd frontend && npm run check
```

Expected: 0 errors / 0 warnings

- [ ] **Step 7: 커밋**

```bash
git add frontend/src/routes/admin/users/+page.svelte
git commit -m "feat(front): 관리자 화면 승인·거절과 상태 필터"
```

---

## Task 14: 가입 화면 · 로그인 안내

**Files:**
- Create: `frontend/src/routes/signup/+page.svelte`
- Modify: `frontend/src/routes/login/+page.svelte`

- [ ] **Step 1: 가입 화면을 만든다**

`frontend/src/routes/signup/+page.svelte` 생성:

```svelte
<script lang="ts">
	import { onMount } from 'svelte';
	import { ApiError } from '$lib/api/client';
	import { listPublicDepartments, signup } from '$lib/api/signup';
	import type { PublicDepartment } from '$lib/api/types';
	import Button from '$lib/components/Button.svelte';
	import Card from '$lib/components/Card.svelte';
	import Select from '$lib/components/Select.svelte';
	import TextInput from '$lib/components/TextInput.svelte';

	let email = $state('');
	let password = $state('');
	let name = $state('');
	let departmentId = $state('');
	let departments = $state<PublicDepartment[]>([]);
	let submitting = $state(false);
	let error = $state<string | null>(null);
	let done = $state(false);

	const departmentChoices = $derived([
		{ value: '', label: '부서를 고르세요' },
		...departments.map((department) => ({
			value: String(department.id),
			label: department.name
		}))
	]);

	onMount(async () => {
		try {
			departments = await listPublicDepartments();
		} catch {
			error = '부서 목록을 불러오지 못했습니다';
		}
	});

	async function handleSubmit(event: SubmitEvent): Promise<void> {
		event.preventDefault();
		// 버튼의 disabled만으로는 form.requestSubmit() 경로를 막지 못한다.
		// 가입은 멱등하지 않아 중복 POST가 곧 중복 신청이다.
		if (submitting) return;
		submitting = true;
		error = null;
		try {
			await signup({
				email,
				password,
				name,
				department_id: Number(departmentId)
			});
			done = true;
		} catch (caught) {
			error =
				caught instanceof ApiError ? caught.message : '가입 신청을 보내지 못했습니다';
		} finally {
			submitting = false;
		}
	}
</script>

<div class="flex min-h-screen items-center justify-center px-4 py-12">
	<div class="w-full max-w-md">
		<h1 class="text-title-lg text-ink">회원가입</h1>
		<p class="mt-2 text-body-sm text-muted">
			관리자 승인 후 로그인할 수 있습니다. 사번·직급·결재자는 승인할 때 관리자가 지정합니다.
		</p>

		<div class="mt-6">
		<Card>
			{#if done}
				<p class="text-body-md text-ink">가입 신청이 접수되었습니다.</p>
				<p class="mt-2 text-body-sm text-muted">
					관리자 승인 후 로그인할 수 있습니다. 승인 전에 로그인하면 대기 중이라고 안내됩니다.
				</p>
				<div class="mt-6">
					<Button variant="secondary" onclick={() => (window.location.href = '/login')}>
						로그인으로
					</Button>
				</div>
			{:else}
				<form onsubmit={handleSubmit}>
					<div class="grid grid-cols-1 gap-4">
						<TextInput
							label="이메일"
							type="email"
							bind:value={email}
							placeholder="name@skon.example"
						/>
						<TextInput label="이름" bind:value={name} placeholder="김출장" />
						<Select label="부서" bind:value={departmentId} options={departmentChoices} />
						<TextInput
							label="비밀번호"
							type="password"
							bind:value={password}
							placeholder="8자 이상 · UTF-8 72바이트 이하"
						/>
					</div>

					{#if error}
						<p class="mt-4 text-body-sm text-error" role="alert">{error}</p>
					{/if}

					<div class="mt-6">
						<Button
							type="submit"
							disabled={submitting || !email || !name || !departmentId || !password}
						>
							{submitting ? '보내는 중…' : '가입 신청'}
						</Button>
					</div>
				</form>

				<p class="mt-6 text-caption text-muted">
					이미 계정이 있으신가요? <a class="underline" href="/login">로그인</a>
				</p>
			{/if}
		</Card>
		</div>
	</div>
</div>
```

`Card`는 `padded`·`hoverable`·`children`만 받고 `class` prop이 없다. 그래서 여백은 위처럼
바깥 `<div class="mt-6">`가 준다.

- [ ] **Step 2: 로그인 화면에 링크와 안내를 더한다**

`frontend/src/routes/login/+page.svelte`를 읽고, 에러 메시지를 표시하는 부분 **아래**에 가입 링크를 더한다:

```svelte
<p class="mt-6 text-caption text-muted">
	계정이 없으신가요? <a class="underline" href="/signup">회원가입</a>
</p>
```

에러 메시지는 서버가 이미 상태별 문구를 내려주므로(`PENDING_APPROVAL` → "관리자 승인 대기 중입니다") 별도 매핑을 추가하지 않는다. 현재 화면이 `ApiError.message`를 그대로 보여주는지 확인하고, 코드별로 하드코딩된 문구를 쓰고 있다면 `message`를 쓰도록 바꾼다.

- [ ] **Step 3: 타입체크와 테스트를 돌린다**

```bash
cd frontend && npm run check && npm test
```

Expected: 0 errors / 0 warnings, 테스트 전부 통과

- [ ] **Step 4: 커밋**

```bash
git add frontend/src/routes/signup/+page.svelte frontend/src/routes/login/+page.svelte
git commit -m "feat(front): 가입 화면과 로그인 안내"
```

---

## Task 15: 브라우저 확인

타입체크·빌드·테스트·curl만 통과한 상태로 넘기지 않는다. Phase 4·5의 화면 7개가 렌더 확인 없이 이월된 전례가 있다.

**Files:** 없음 (수동 확인)

- [ ] **Step 1: 백엔드와 프론트를 띄운다**

```bash
cd backend && uv run uvicorn app.main:app --reload --port 8000
```

별도 터미널:

```bash
cd frontend && npm run dev
```

- [ ] **Step 2: 시드를 다시 돌린다**

```bash
cd backend && uv run python -m app.cli seed
```

Expected: 멱등하게 완료. `newbie@skon.example`가 PENDING으로 들어간다.

- [ ] **Step 3: 가입 흐름을 확인한다**

`http://localhost:5173/signup`을 연다.

- 부서 드롭다운이 채워지는가 (미인증 호출이 200인가)
- 짧은 비밀번호로 제출 → "비밀번호는 8자 이상이어야 합니다"
- 정상 제출 → 완료 문구로 교체되는가
- 같은 이메일로 다시 제출 → "이미 승인 대기 중인 이메일입니다"

- [ ] **Step 4: 승인 전 로그인을 확인한다**

`http://localhost:5173/login`에서 방금 가입한 계정으로 로그인 → "관리자 승인 대기 중입니다"

틀린 비밀번호로 로그인 → "이메일 또는 비밀번호가 올바르지 않습니다" (상태가 새지 않는다)

- [ ] **Step 5: 승인을 확인한다**

`admin@skon.example` / `skon1234!`로 로그인 → `/admin/users`

- 상태 열에 "승인 대기" 배지가 보이는가
- 상태 필터를 "승인 대기"로 바꾸고 검색 → 대기 건만 남는가
- [승인] → 모달이 열리는가. **Esc로 닫히는가. 백드롭 클릭으로 닫히는가. 내용 클릭으로는 안 닫히는가**
- 사번을 기존 값(`E0001`)으로 넣고 승인 → "이미 사용 중인 사번입니다"
- 새 사번으로 승인 → 목록이 갱신되고 상태가 "활성"으로 바뀌는가

- [ ] **Step 6: 승인 후 로그인을 확인한다**

로그아웃 후 가입 계정으로 로그인 → 성공. 상단에 이름·부서가 맞게 나오는가.

- [ ] **Step 7: 거절과 재신청을 확인한다**

다른 계정으로 가입 → 관리자가 [거절] → 상태가 "거절됨"

같은 이메일로 다시 가입 → 201, 상태가 다시 "승인 대기"

- [ ] **Step 8: 반응형을 확인한다**

브라우저 폭을 744px 아래로 줄여 `/admin/users`와 `/signup`이 깨지지 않는지 본다.

- [ ] **Step 9: 확인 결과를 기록한다**

`docs/manual-scenarios.md`에 이번 시나리오를 추가하고 확인한 항목을 체크한다.

---

## Task 16: 문서 갱신

**Files:**
- Modify: `CLAUDE.md`
- Modify: `docs/phase-status.md`
- Modify: `docs/manual-scenarios.md`

- [ ] **Step 1: CLAUDE.md에 불변식을 적는다**

"반드시 지킬 것" 절의 `user` 테이블 문단 **다음**에 추가:

```markdown
**`status`와 `is_active`는 의미가 겹치지 않는다.** `status`(`UserStatus`)는 가입 신청의
생애주기이고 `is_active`는 로그인 가능 여부다. 불변식은 **단방향**이다 — `status != ACTIVE`이면
반드시 `is_active = false`이지만 역은 성립하지 않는다. 승인 뒤 관리자가 정지시킨 계정이
`status=ACTIVE` + `is_active=false`이며, 그것이 "승인 대기"와 구분되어야 하는 경우다. 단방향으로
둔 덕분에 `is_active`의 의미가 바뀌지 않아 로그인 게이트도, 계정을 공유하는 상대 프로젝트의
시야도 그대로다.

**로그인은 비밀번호 검증에 성공한 뒤에만 `status`를 본다.** 앞에서 보면 이메일만으로 계정
존재가 드러나 더미 해시로 타이밍까지 맞춘 방어가 무의미해진다. 순서가 방어의 전부다.

**`status`는 `assert_signup_transition_allowed` 하나만 통과한다.** 출장·정산과 같은 구조이며
이유도 같다. `AdminUserUpdate`에 `status`를 넣지 않는 것은 그래서다 — `PATCH`로 바꿀 수 있으면
전이 가드를 우회하는 두 번째 경로가 생긴다. 전이를 추가하고 `SIGNUP_TRANSITION_ACTOR`를
빠뜨리면 임포트 시점에 `RuntimeError`로 죽는다.

**가입은 `PENDING` 행을 덮어쓰지 않는다.** 덮어쓰기를 허용하면 남이 신청해 둔 대기 계정에 내가
아는 비밀번호를 덮어씌운 뒤 승인을 기다려 계정을 가로챌 수 있다. `REJECTED`만 재신청으로
덮어쓴다.

**`employee_no`·`position_code`는 nullable이다.** 가입 시점에 값이 없기 때문이며, 임시값 대신
NULL을 쓰는 이유는 가짜 사번이 상대 프로젝트·유저 관리 화면·Agent API에 실제 값처럼 노출되지
않게 하려는 것이다. 값의 강제는 컬럼이 아니라 `approve_user`가 한다.
```

"마이그레이션" 절에 한 문단 추가:

```markdown
2026-08-22의 `status` 컬럼 추가와 `employee_no`·`position_code` NOT NULL 해제도 같은 경우다.
실행할 SQL은 `docs/migrations/2026-08-22-user-signup-status.sql`이며 **코드 머지와 별개로
사람이 psql로 한 번 돌려야 한다.** 안 돌리면 없는 `status` 컬럼을 찔러 로그인부터 500이 난다.
```

- [ ] **Step 2: phase-status.md에 이월 항목을 적는다**

"후속 수정" 절에 추가:

```markdown
- `POST /api/v1/auth/signup`은 **미인증 쓰기 엔드포인트이며 rate limit이 없다.** 스팸 가입이
  가능하다. 데모 범위로 의도한 생략이며, 외부에 오래 열어둘 것이면 IP 단위 스로틀을 먼저 붙인다.
- 가입·승인·거절이 `activity_log`에 남지 않는다. `EntityType`에 `USER` 멤버가 없다 —
  키 발급·Admin 마스터 변경이 로그에 남지 않는 기존 항목과 같은 건이다.
- `GET /api/v1/auth/departments`는 미인증으로 부서명을 노출한다. 가입 폼의 드롭다운 때문이며
  의도된 노출이다.
```

- [ ] **Step 3: 문서 링크가 맞는지 확인한다**

```bash
cd /Users/namkon/projects/skon-biztrip-web && grep -n "2026-08-22" CLAUDE.md docs/phase-status.md
```

Expected: 마이그레이션 파일 경로가 실제 파일과 일치한다

- [ ] **Step 4: 전체 검증**

```bash
cd backend  && uv run pytest -q
cd frontend && npm test && npm run check
```

Expected: 전부 통과, 0 errors / 0 warnings

- [ ] **Step 5: 커밋**

```bash
git add CLAUDE.md docs/phase-status.md docs/manual-scenarios.md
git commit -m "docs: 가입·승인 불변식과 이월 항목"
```

---

## 완료 기준

- [ ] `uv run pytest -q` 전부 통과
- [ ] `npm test` · `npm run check` 통과 (0 errors / 0 warnings)
- [ ] 마이그레이션 SQL이 운영 DB에서 실행됨 (Task 3 Step 7)
- [ ] Task 15의 브라우저 확인 9단계를 실제로 돌림
- [ ] `git log --oneline`에 태스크별 커밋이 남아 있음
