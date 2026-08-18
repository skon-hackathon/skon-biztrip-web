# Phase 4 (개발자) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 사용자가 웹에서 API Key를 발급·폐기하고, 그 키로 외부 Agent가 **웹과 물리적으로 같은 엔드포인트**를 스코프 범위 안에서 호출할 수 있게 한다.

**Architecture:** 인증은 기존 `get_principal()` 단일 의존성이 JWT와 `X-API-Key` 두 경로를 모두 처리한다. 스코프 검사는 **엔드포인트마다 붙이는 의존성이 아니라** `get_principal()` 안의 단 한 지점에서 `SCOPE_REQUIREMENTS` 표를 조회해 수행한다 — 엔드포인트별 의존성은 "빠뜨리면 조용히 전권"이라는 fail-open이 되기 때문이다. 표가 실제 라우트와 어긋나면 `main.py` 임포트 시점에 `RuntimeError`로 죽는다(`TRANSITION_ACTOR` 소진 가드와 같은 패턴). 키 관리 엔드포인트 자체는 JWT 전용이라 키가 키를 낳지 못한다.

**Tech Stack:** FastAPI · SQLAlchemy 2 async · pytest-asyncio · SvelteKit 2 / Svelte 5 (runes) · Tailwind v4 · vitest

---

## 이 Phase가 닫는 것

| spec | 내용 |
|---|---|
| 5.7 | `api_key` 테이블 활용, 평문 키 1회 노출 |
| 7 인증 | `X-API-Key` 경로, 스코프 6종, `last_used_at` 갱신, 폐기·만료 키 401 |
| 6 화면 | `/settings/api-keys`, `/developers` |
| 8 테스트 | "JWT 경로와 API Key 경로 **양쪽에서 동일 시나리오**" |
| 10 | OpenAPI 정리 |

## 반드시 지킬 것 (기존 `CLAUDE.md` + Phase 3 이월)

- `app/deps.py`의 `UNRESTRICTED`는 **센티널 동일성 비교**로만 판정한다. `getattr(request.state, "scopes", None)`처럼 기본값을 두면 의존성을 빠뜨린 엔드포인트가 조용히 전권을 얻는다.
- 새 예외는 `app/errors.py`의 `AppError` 계열. 응답 바디는 `{"error": {"code","message","field"}}` 하나뿐.
- `relationship()`을 붙이지 않는다. 이름이 필요하면 명시적 조인 / `id.in_(...)`.
- 프론트의 인증 호출은 전부 `authRequest`. raw `request`는 `login`·`restore`만.
- `crypto.randomUUID()` 등 SecureContext 전용 API 금지. 고유 id는 `$props.id()`, 컴포넌트당 **한 번만**.
- `text-body` 금지 → `text-body-md` / `text-body-sm`.
- 새 폼 첫 줄에 `if (submitting) return;`.
- 가드를 추가하면 **mutation으로 확인**한다. 그 줄을 지웠을 때 실패하는 테스트가 없으면 그 테스트는 아무것도 지키지 않는다.
- 백엔드 명령은 항상 `uv run`을 거친다. 맨 `python3`는 pyenv 때문에 죽고 heredoc 안에서는 조용히 실패한다.

## 확정한 설계 결정

| 쟁점 | 결정 | 이유 |
|---|---|---|
| 스코프 검사 위치 | `get_principal()` 안 **한 곳** + 라우트 표 | 엔드포인트별 `Depends(require_scope(...))`는 빠뜨리면 fail-open. 상태전이에서 이미 같은 실수를 세 번 했다 |
| 표 정합성 | `assert_scope_table_complete(app)`를 `main.py`가 임포트 시점에 호출 | 라우트를 추가하고 스코프를 안 적으면 **기동 실패**. 조용한 전권 부여가 불가능해진다 |
| 키 관리 API 인증 | **JWT 전용** (`JwtOnlyUser`) | API Key가 새 키를 발급하면 스코프 제한이 무의미해진다(키 세탁) |
| 두 헤더가 동시에 오면 | `X-API-Key` 우선 | 브라우저는 항상 `Authorization`을 보낸다. 명시적으로 얹은 키가 더 구체적인 의도이고, 어느 쪽이든 결정적이어야 한다 |
| 평문 키 | 발급 응답 1회만. DB에는 SHA-256만 | spec 5.7 |
| 키 형식 | `sk_live_` + `secrets.token_hex(16)` (총 40자). `key_prefix`는 앞 16자 | 영숫자만이라 복사·URL·셸 인용에서 사고가 없다 |
| 스코프 없는 엔드포인트 | `/auth/me`·`/codes`·`/fund-centers`·`/cost-centers`·`/notifications`·`/scopes`·`/api-keys` → `None` | spec이 스코프를 6종으로 고정했다. 마스터 데이터는 쓰기의 전제조건이고, 알림·키는 본인 리소스다. 다만 표에 **명시적으로 `None`을 적어야** 소진 가드를 통과한다 |
| `last_used_at` | 검증 성공 시 매번 갱신하고 그 자리에서 commit | spec 7. 데모에서 "마지막 사용"이 실시간으로 움직이는 게 이 Phase의 데모 포인트다 |
| 키 개수 | 사용자당 활성 10개 (`MAX_ACTIVE_KEYS`) | 무한 발급 방지. 금액 상한과 같은 종류의 방어선 |
| 시드 | 데모 키를 시드하지 않는다 | 리포지토리에 유효한 평문 키를 두지 않는다. `/developers`가 발급 화면으로 유도한다 |
| 폐기 | `POST /api-keys/{id}/revoke` (soft, `revoked_at`) | `DELETE`는 하드 삭제로 읽힌다. 감사 흔적을 남긴다 |

## File Structure

**백엔드 — 생성**

| 파일 | 책임 |
|---|---|
| `app/services/api_scopes.py` | `SCOPE_REQUIREMENTS` 표 · `required_scope_for` · `assert_scope_table_complete` · 스코프 설명 카탈로그. DB 접근 없음 |
| `app/services/api_keys.py` | 키 생성·해시(순수) + 인증·목록·발급·폐기(DB) |
| `app/schemas/api_key.py` | `ApiKeyOut` `ApiKeyCreate` `ApiKeyCreated` `ScopeInfo` |
| `app/routers/api_keys.py` | `GET|POST /api/v1/api-keys` · `POST /api/v1/api-keys/{key_id}/revoke` |
| `app/routers/meta.py` | `GET /api/v1/scopes` |
| `app/openapi.py` | securitySchemes 주입 + operation 설명에 필요 스코프 표기 |

**백엔드 — 수정**

| 파일 | 변경 |
|---|---|
| `app/deps.py` | API Key 분기 · 스코프 강제 · `JwtOnlyUser` |
| `app/main.py` | 라우터 2개 등록 · 표 소진 가드 호출 · `app.openapi` 교체 |

**백엔드 — 테스트 생성**

`tests/test_api_scopes.py` · `tests/test_api_keys_service.py` · `tests/test_api_keys_api.py` · `tests/test_apikey_auth.py` · `tests/test_scope_enforcement.py` · `tests/test_openapi.py`
`tests/factories.py`에 `make_api_key` 추가.

**프론트 — 생성**

| 파일 | 책임 |
|---|---|
| `src/lib/api/api-keys.ts` | 키 API 클라이언트 |
| `src/lib/api/meta.ts` | `GET /scopes` |
| `src/lib/api-keys.ts` | 순수 — 스코프 라벨·상태 라벨/톤·curl 스니펫 생성 |
| `src/lib/api-keys.test.ts` | 위 모듈의 vitest |
| `src/routes/settings/api-keys/+page.svelte` | 발급·조회·폐기 |
| `src/routes/developers/+page.svelte` | 가이드 (스코프 표 + curl + `/docs` 링크) |

**프론트 — 수정**: `src/lib/api/types.ts` (타입 4종 추가)

`AppShell.svelte`의 가운데 탭에는 이미 `/developers`가 있다(현재는 죽은 링크). 헤더는 건드리지 않고, `/developers` 안에서 `/settings/api-keys`로 유도한다.

---

## Task 1: 키 생성·해시 순수 함수

**Files:**
- Create: `backend/app/services/api_keys.py`
- Test: `backend/tests/test_api_keys_service.py`

- [ ] **Step 1: 실패하는 테스트를 쓴다**

`backend/tests/test_api_keys_service.py`:

```python
"""API Key 발급·인증. 평문은 발급 응답에만 존재하고 DB에는 해시만 남는다."""

import hashlib

from app.services.api_keys import KEY_PREFIX, generate_key, hash_key


def test_generate_key_returns_prefixed_plaintext():
    raw, prefix, digest = generate_key()
    assert raw.startswith(KEY_PREFIX)
    assert len(raw) == len(KEY_PREFIX) + 32
    assert raw[len(KEY_PREFIX) :].isalnum()


def test_prefix_is_the_display_head_of_the_raw_key():
    raw, prefix, _ = generate_key()
    assert prefix == raw[:16]
    assert len(prefix) <= 30  # api_key.key_prefix 컬럼 길이


def test_hash_is_sha256_hex_of_the_raw_key():
    raw, _, digest = generate_key()
    assert digest == hashlib.sha256(raw.encode()).hexdigest()
    assert len(digest) == 64  # api_key.key_hash 컬럼 길이


def test_generate_key_is_not_deterministic():
    assert generate_key()[0] != generate_key()[0]


def test_hash_key_matches_generate_key():
    raw, _, digest = generate_key()
    assert hash_key(raw) == digest
```

- [ ] **Step 2: 실패를 확인한다**

Run: `cd backend && uv run pytest tests/test_api_keys_service.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.services.api_keys'`

- [ ] **Step 3: 최소 구현**

`backend/app/services/api_keys.py`:

```python
"""API Key 발급·인증·폐기.

평문 키는 발급 응답에서 단 한 번만 나가고 DB에는 SHA-256 해시만 남는다(spec 5.7).
비밀번호와 달리 bcrypt를 쓰지 않는 이유: 키는 128비트 난수라 사전공격 대상이 아니고,
매 API 호출마다 bcrypt를 태우면 요청당 수십 ms가 그냥 사라진다.
"""

import hashlib
import secrets

#: 평문 키 접두어. spec 5.7의 표기를 그대로 쓴다.
KEY_PREFIX = "sk_live_"
#: 목록에 보여줄 앞부분 길이. 접두어(8) + 난수 8자.
PREFIX_DISPLAY_LEN = 16


def hash_key(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


def generate_key() -> tuple[str, str, str]:
    """(평문, 표시용 접두어, 해시)를 만든다. 평문은 호출자가 즉시 응답에 실어 보내고 버린다."""
    raw = f"{KEY_PREFIX}{secrets.token_hex(16)}"
    return raw, raw[:PREFIX_DISPLAY_LEN], hash_key(raw)
```

- [ ] **Step 4: 통과를 확인한다**

Run: `cd backend && uv run pytest tests/test_api_keys_service.py -v`
Expected: 5 passed

- [ ] **Step 5: 커밋**

```bash
git add backend/app/services/api_keys.py backend/tests/test_api_keys_service.py
git commit -m "feat(api-keys): add key generation and SHA-256 hashing"
```

---

## Task 2: 스코프 요구 표

**Files:**
- Create: `backend/app/services/api_scopes.py`
- Test: `backend/tests/test_api_scopes.py`

- [ ] **Step 1: 실패하는 테스트를 쓴다**

`backend/tests/test_api_scopes.py`:

```python
"""스코프 요구 표. 이 표가 유일한 권한 선언 지점이다."""

import pytest

from app.enums import ApiKeyScope
from app.errors import ForbiddenError
from app.services.api_scopes import (
    SCOPE_DESCRIPTIONS,
    SCOPE_REQUIREMENTS,
    required_scope_for,
    scope_catalog,
)


def test_read_endpoint_requires_read_scope():
    assert required_scope_for("GET", "/api/v1/trips") is ApiKeyScope.TRIPS_READ


def test_write_endpoint_requires_write_scope():
    assert required_scope_for("POST", "/api/v1/trips/{trip_id}/submit") is ApiKeyScope.TRIPS_WRITE


def test_master_data_endpoint_requires_no_scope():
    assert required_scope_for("GET", "/api/v1/codes") is None


def test_undeclared_route_is_rejected_not_allowed():
    """표에 없는 경로는 통과가 아니라 거부다. 여기서 통과시키면 신규 라우트가 전권이 된다."""
    with pytest.raises(ForbiddenError) as exc:
        required_scope_for("GET", "/api/v1/does-not-exist")
    assert exc.value.code == "SCOPE_UNDECLARED"


def test_method_matters():
    assert required_scope_for("GET", "/api/v1/trips") is ApiKeyScope.TRIPS_READ
    assert required_scope_for("POST", "/api/v1/trips") is ApiKeyScope.TRIPS_WRITE


def test_every_scope_has_a_description():
    assert set(SCOPE_DESCRIPTIONS) == set(ApiKeyScope)


def test_catalog_lists_endpoints_per_scope():
    catalog = {entry.scope: entry for entry in scope_catalog()}
    assert set(catalog) == set(ApiKeyScope)
    trips_read = catalog[ApiKeyScope.TRIPS_READ]
    assert "GET /api/v1/trips" in trips_read.endpoints
    assert "POST /api/v1/trips" not in trips_read.endpoints


def test_admin_scope_has_no_endpoints_yet():
    """/admin/*는 Phase 5다. 카탈로그는 빈 목록을 정직하게 노출한다."""
    catalog = {entry.scope: entry for entry in scope_catalog()}
    assert catalog[ApiKeyScope.ADMIN].endpoints == []


def test_table_has_no_duplicate_or_lowercase_methods():
    for method, path in SCOPE_REQUIREMENTS:
        assert method == method.upper()
        assert path.startswith("/api/v1/")
```

- [ ] **Step 2: 실패를 확인한다**

Run: `cd backend && uv run pytest tests/test_api_scopes.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.services.api_scopes'`

- [ ] **Step 3: 최소 구현**

`backend/app/services/api_scopes.py`:

```python
"""엔드포인트별 필요 스코프 선언 (spec 7 인증).

**이 표가 유일한 선언 지점이다.** 엔드포인트마다 `Depends(require_scope(...))`를 붙이는
방식을 쓰지 않는 이유는 상태전이에서 이미 배운 것과 같다 — 빠뜨릴 수 있는 검사는 언젠가
빠뜨리고, 그 실패는 fail-open이다. 여기서는 "스코프 의존성을 안 붙인 엔드포인트가
API Key에게 전권을 준다"가 된다.

표에 없는 경로는 통과가 아니라 403이며, `assert_scope_table_complete`가 임포트 시점에
표와 실제 라우트가 어긋나는 것을 잡는다.
"""

from dataclasses import dataclass

from app.enums import ApiKeyScope
from app.errors import ForbiddenError

_TR = ApiKeyScope.TRIPS_READ
_TW = ApiKeyScope.TRIPS_WRITE
_ER = ApiKeyScope.EXPENSES_READ
_EW = ApiKeyScope.EXPENSES_WRITE
_CR = ApiKeyScope.CARDS_READ

#: (HTTP 메서드, FastAPI 라우트 경로) -> 필요 스코프. None은 "인증만 하면 됨".
#:
#: None을 쓰는 경로는 두 종류뿐이다.
#: 1. 마스터/참조 데이터 (`/codes` `/fund-centers` `/cost-centers`) — 모든 쓰기의 전제조건이고
#:    spec이 스코프를 6종으로 고정했으므로 별도 스코프를 만들지 않는다.
#: 2. 본인 리소스 (`/auth/me` `/notifications`).
#: 어느 쪽이든 **표에 명시적으로 적어야** 소진 가드를 통과한다. 빠뜨리면 기동이 실패한다.
#: `/api-keys`·`/scopes`는 라우터가 생기는 Task 10·11에서 함께 추가한다 — 라우트 없는 표
#: 항목도 소진 가드가 거부하므로 표와 라우터는 반드시 같은 커밋에서 움직인다.
SCOPE_REQUIREMENTS: dict[tuple[str, str], ApiKeyScope | None] = {
    ("GET", "/api/v1/auth/me"): None,
    ("GET", "/api/v1/codes"): None,
    ("GET", "/api/v1/codes/{group_code}"): None,
    ("GET", "/api/v1/fund-centers"): None,
    ("GET", "/api/v1/cost-centers"): None,
    ("GET", "/api/v1/notifications"): None,
    ("POST", "/api/v1/notifications/{notification_id}/read"): None,
    ("GET", "/api/v1/trips"): _TR,
    ("POST", "/api/v1/trips"): _TW,
    ("GET", "/api/v1/trips/{trip_id}"): _TR,
    ("PATCH", "/api/v1/trips/{trip_id}"): _TW,
    ("DELETE", "/api/v1/trips/{trip_id}"): _TW,
    ("POST", "/api/v1/trips/{trip_id}/submit"): _TW,
    ("POST", "/api/v1/trips/{trip_id}/approve"): _TW,
    ("POST", "/api/v1/trips/{trip_id}/reject"): _TW,
    ("POST", "/api/v1/trips/{trip_id}/reopen"): _TW,
    ("POST", "/api/v1/trips/{trip_id}/complete"): _TW,
    ("GET", "/api/v1/trips/{trip_id}/timeline"): _TR,
    ("GET", "/api/v1/cards"): _CR,
    ("GET", "/api/v1/card-transactions"): _CR,
    ("GET", "/api/v1/expenses"): _ER,
    ("POST", "/api/v1/expenses"): _EW,
    ("GET", "/api/v1/expenses/{report_id}"): _ER,
    ("PATCH", "/api/v1/expenses/{report_id}"): _EW,
    ("GET", "/api/v1/expenses/{report_id}/match-candidates"): _ER,
    ("GET", "/api/v1/expenses/{report_id}/timeline"): _ER,
    ("POST", "/api/v1/expenses/{report_id}/items"): _EW,
    ("PATCH", "/api/v1/expense-items/{item_id}"): _EW,
    ("DELETE", "/api/v1/expense-items/{item_id}"): _EW,
    ("POST", "/api/v1/expenses/{report_id}/submit"): _EW,
    ("POST", "/api/v1/expenses/{report_id}/approve"): _EW,
    ("POST", "/api/v1/expenses/{report_id}/reject"): _EW,
    ("POST", "/api/v1/expenses/{report_id}/reopen"): _EW,
}

SCOPE_DESCRIPTIONS: dict[ApiKeyScope, str] = {
    ApiKeyScope.TRIPS_READ: "출장 조회 — 목록·상세·타임라인",
    ApiKeyScope.TRIPS_WRITE: "출장 쓰기 — 신청·수정·삭제·상신·결재·완료",
    ApiKeyScope.EXPENSES_READ: "정산 조회 — 목록·상세·매칭후보·타임라인",
    ApiKeyScope.EXPENSES_WRITE: "정산 쓰기 — 생성·항목 편집·제출·결재",
    ApiKeyScope.CARDS_READ: "법인카드 조회 — 카드 목록·카드거래",
    ApiKeyScope.ADMIN: "관리자 API (Phase 5에서 열림)",
}


@dataclass(frozen=True)
class ScopeCatalogEntry:
    scope: ApiKeyScope
    description: str
    endpoints: list[str]


def scope_catalog() -> list[ScopeCatalogEntry]:
    """스코프별 설명과 해당 엔드포인트. `/api/v1/scopes`와 `/developers` 가이드가 함께 쓴다.

    가이드를 손으로 적으면 표와 어긋난다. 같은 표에서 뽑아 어긋날 수 없게 한다.
    """
    grouped: dict[ApiKeyScope, list[str]] = {scope: [] for scope in ApiKeyScope}
    for (method, path), scope in SCOPE_REQUIREMENTS.items():
        if scope is not None:
            grouped[scope].append(f"{method} {path}")
    return [
        ScopeCatalogEntry(
            scope=scope,
            description=SCOPE_DESCRIPTIONS[scope],
            endpoints=sorted(grouped[scope]),
        )
        for scope in ApiKeyScope
    ]


def required_scope_for(method: str, path: str) -> ApiKeyScope | None:
    """이 엔드포인트에 필요한 스코프. 표에 없으면 **거부한다**.

    없으면 통과시키고 싶은 유혹이 있는데, 그러면 새 라우트가 스코프 선언 없이 배포됐을 때
    조용히 전권이 된다. 소진 가드가 있어 이 예외는 실전에서 발생하지 않아야 하지만,
    가드가 우회된 상황에서도 fail-closed로 남기려고 둔다.
    """
    key = (method.upper(), path)
    if key not in SCOPE_REQUIREMENTS:
        raise ForbiddenError(
            "SCOPE_UNDECLARED", "이 엔드포인트에 필요한 스코프가 선언되지 않았습니다"
        )
    return SCOPE_REQUIREMENTS[key]
```

- [ ] **Step 4: 통과를 확인한다**

Run: `cd backend && uv run pytest tests/test_api_scopes.py -v`
Expected: 9 passed

- [ ] **Step 5: 커밋**

```bash
git add backend/app/services/api_scopes.py backend/tests/test_api_scopes.py
git commit -m "feat(api-keys): declare per-endpoint scope requirements"
```

---

## Task 3: 표 소진 가드 (라우트와 표의 정합성)

라우트를 추가하고 스코프를 안 적으면 **기동이 실패해야** 한다. 이게 이 Phase의 핵심 안전장치다.

**Files:**
- Modify: `backend/app/services/api_scopes.py` (함수 추가)
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_api_scopes.py` (추가)

- [ ] **Step 1: 실패하는 테스트를 쓴다**

`backend/tests/test_api_scopes.py` 끝에 추가:

```python
from fastapi import FastAPI

from app.deps import get_principal
from app.main import app as real_app
from app.services.api_scopes import assert_scope_table_complete


def test_real_app_passes_the_completeness_guard():
    assert_scope_table_complete(real_app)  # 예외가 없으면 성공


def test_guard_rejects_an_authenticated_route_missing_from_the_table():
    probe = FastAPI()

    @probe.get("/api/v1/unlisted")
    async def unlisted(user=Depends(get_principal)):  # noqa: B008
        return {}

    with pytest.raises(RuntimeError) as exc:
        assert_scope_table_complete(probe)
    assert "GET /api/v1/unlisted" in str(exc.value)


def test_guard_ignores_routes_that_do_not_authenticate():
    """`/auth/login`·헬스체크처럼 get_principal을 안 쓰는 라우트는 스코프 개념이 없다."""
    probe = FastAPI()

    @probe.get("/api/v1/open")
    async def open_route():
        return {}

    assert_scope_table_complete(probe)  # 예외 없음


def test_guard_rejects_a_table_entry_with_no_matching_route():
    """경로 이름을 바꾸고 표를 안 고치면 그 항목은 죽은 선언이 된다."""
    probe = FastAPI()

    @probe.get("/api/v1/auth/me")
    async def me(user=Depends(get_principal)):  # noqa: B008
        return {}

    with pytest.raises(RuntimeError) as exc:
        assert_scope_table_complete(probe)
    assert "GET /api/v1/trips" in str(exc.value)
```

`tests/test_api_scopes.py` 상단 import에 `from fastapi import Depends`를 추가한다.

- [ ] **Step 2: 실패를 확인한다**

Run: `cd backend && uv run pytest tests/test_api_scopes.py -v -k guard`
Expected: FAIL — `ImportError: cannot import name 'assert_scope_table_complete'`

- [ ] **Step 3: 구현**

`backend/app/services/api_scopes.py` 끝에 추가:

```python
def _authenticated_routes(app) -> set[tuple[str, str]]:
    """`get_principal`을 통과하는 (메서드, 경로) 전부.

    의존성 트리를 재귀로 훑는다 — `get_principal`이 직접 붙지 않고 `JwtOnlyUser`처럼
    한 겹 감싸서 붙는 경우가 있기 때문이다. 얕게만 보면 그런 라우트가 표 검사에서
    통째로 빠진다.
    """
    from fastapi.routing import APIRoute

    from app.deps import get_principal

    found: set[tuple[str, str]] = set()
    for route in app.routes:
        if not isinstance(route, APIRoute):
            continue
        stack = list(route.dependant.dependencies)
        calls = set()
        while stack:
            dependency = stack.pop()
            if dependency.call is not None:
                calls.add(dependency.call)
            stack.extend(dependency.dependencies)
        if get_principal not in calls:
            continue
        for method in route.methods - {"HEAD", "OPTIONS"}:
            found.add((method, route.path))
    return found


def assert_scope_table_complete(app) -> None:
    """표와 실제 라우트가 정확히 일치하는지 임포트 시점에 확인한다.

    양방향으로 본다. 라우트가 표에 없으면 스코프 미선언이고, 표에 있는데 라우트가 없으면
    경로 변경 후 죽은 선언이 남은 것이다. 후자를 방치하면 다음 사람이 그 항목을 보고
    "이 경로는 보호되고 있다"고 잘못 믿는다.
    """
    routes = _authenticated_routes(app)
    declared = set(SCOPE_REQUIREMENTS)
    missing = routes - declared
    extra = declared - routes
    if missing or extra:
        raise RuntimeError(
            "SCOPE_REQUIREMENTS가 실제 라우트와 어긋납니다. "
            f"표에 없는 라우트={sorted(f'{m} {p}' for m, p in missing)} "
            f"라우트가 없는 표 항목={sorted(f'{m} {p}' for m, p in extra)}"
        )
```

`backend/app/main.py`에서 라우터 등록 **뒤**에 호출을 추가한다 (Task 9·10에서 라우터 2개를 더 등록한 뒤에도 이 줄은 마지막에 있어야 한다):

```python
from app.services.api_scopes import assert_scope_table_complete

...
app.include_router(trips.router)

# 라우트를 추가하고 SCOPE_REQUIREMENTS에 적지 않으면 여기서 기동이 실패한다.
# 조용히 전권을 얻는 엔드포인트가 생기는 것보다 못 뜨는 게 낫다.
assert_scope_table_complete(app)
```

- [ ] **Step 4: 통과를 확인한다**

Run: `cd backend && uv run pytest tests/test_api_scopes.py -v`
Expected: 13 passed

- [ ] **Step 5: mutation으로 가드를 검증한다**

```bash
cd backend
# 표에서 한 항목을 지운다
uv run python - <<'EOF'
from pathlib import Path
p = Path("app/services/api_scopes.py")
s = p.read_text()
assert '    ("GET", "/api/v1/cards"): _CR,\n' in s
p.write_text(s.replace('    ("GET", "/api/v1/cards"): _CR,\n', ""))
EOF
grep -c '"/api/v1/cards"' app/services/api_scopes.py   # 1 (card-transactions만 남음)
uv run pytest tests/test_api_scopes.py -q
```

Expected: 임포트/실행이 `RuntimeError: SCOPE_REQUIREMENTS가 실제 라우트와 어긋납니다 ... 표에 없는 라우트=['GET /api/v1/cards']`로 실패한다.

되돌린다:

```bash
cd backend && git checkout app/services/api_scopes.py && uv run pytest tests/test_api_scopes.py -q
```

Expected: 13 passed

- [ ] **Step 6: 커밋**

```bash
git add backend/app/services/api_scopes.py backend/app/main.py backend/tests/test_api_scopes.py
git commit -m "feat(api-keys): fail startup when a route declares no scope"
```

---

## Task 4: 팩토리에 `make_api_key` 추가

**Files:**
- Modify: `backend/tests/factories.py`
- Test: `backend/tests/test_factories.py`

- [ ] **Step 1: 실패하는 테스트를 쓴다**

`backend/tests/test_factories.py` 끝에 추가:

```python
async def test_make_api_key_returns_raw_and_row(db_session):
    from app.enums import ApiKeyScope
    from app.services.api_keys import hash_key
    from tests.factories import make_api_key, make_user

    user = await make_user(db_session)
    raw, key = await make_api_key(db_session, user=user, scopes=[ApiKeyScope.TRIPS_READ])

    assert raw.startswith("sk_live_")
    assert key.key_hash == hash_key(raw)
    assert key.scopes == ["trips:read"]
    assert key.revoked_at is None
```

- [ ] **Step 2: 실패를 확인한다**

Run: `cd backend && uv run pytest tests/test_factories.py -v -k api_key`
Expected: FAIL — `ImportError: cannot import name 'make_api_key'`

- [ ] **Step 3: 구현**

`backend/tests/factories.py` 상단 import에 `ApiKey`를 추가하고(`from app.models import (... ApiKey, ...)`) 끝에 추가:

```python
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
```

- [ ] **Step 4: 통과를 확인한다**

Run: `cd backend && uv run pytest tests/test_factories.py -v`
Expected: all passed

- [ ] **Step 5: 커밋**

```bash
git add backend/tests/factories.py backend/tests/test_factories.py
git commit -m "test(api-keys): add make_api_key factory"
```

---

## Task 5: API Key 인증 (DB 조회 · 폐기·만료 판정)

**Files:**
- Modify: `backend/app/services/api_keys.py`
- Test: `backend/tests/test_api_keys_service.py`

- [ ] **Step 1: 실패하는 테스트를 쓴다**

`backend/tests/test_api_keys_service.py` 끝에 추가:

```python
from datetime import datetime, timedelta, timezone

import pytest

from app.enums import ApiKeyScope
from app.errors import AuthError
from app.services.api_keys import authenticate_key, key_state
from tests.factories import make_api_key, make_user


def _now() -> datetime:
    return datetime(2026, 8, 18, 3, 0, tzinfo=timezone.utc)


async def test_authenticate_returns_owner_and_scopes(db_session):
    user = await make_user(db_session)
    raw, _ = await make_api_key(
        db_session, user=user, scopes=[ApiKeyScope.TRIPS_READ, ApiKeyScope.CARDS_READ]
    )

    principal, scopes = await authenticate_key(db_session, raw)

    assert principal.id == user.id
    assert scopes == ["trips:read", "cards:read"]


async def test_unknown_key_is_rejected(db_session):
    with pytest.raises(AuthError) as exc:
        await authenticate_key(db_session, "sk_live_" + "0" * 32)
    assert exc.value.code == "INVALID_API_KEY"


async def test_malformed_key_is_rejected_without_a_query(db_session):
    with pytest.raises(AuthError) as exc:
        await authenticate_key(db_session, "not-a-key")
    assert exc.value.code == "INVALID_API_KEY"


async def test_revoked_key_is_rejected_with_its_own_code(db_session):
    user = await make_user(db_session)
    raw, _ = await make_api_key(db_session, user=user, revoked_at=_now())
    with pytest.raises(AuthError) as exc:
        await authenticate_key(db_session, raw)
    assert exc.value.code == "API_KEY_REVOKED"


async def test_expired_key_is_rejected_with_its_own_code(db_session):
    user = await make_user(db_session)
    raw, _ = await make_api_key(
        db_session, user=user, expires_at=datetime.now(timezone.utc) - timedelta(seconds=1)
    )
    with pytest.raises(AuthError) as exc:
        await authenticate_key(db_session, raw)
    assert exc.value.code == "API_KEY_EXPIRED"


async def test_key_of_an_inactive_user_is_rejected(db_session):
    user = await make_user(db_session)
    user.is_active = False
    await db_session.flush()
    raw, _ = await make_api_key(db_session, user=user)
    with pytest.raises(AuthError) as exc:
        await authenticate_key(db_session, raw)
    assert exc.value.code == "INVALID_API_KEY"


async def test_successful_authentication_stamps_last_used_at(db_session):
    user = await make_user(db_session)
    raw, key = await make_api_key(db_session, user=user)
    assert key.last_used_at is None

    await authenticate_key(db_session, raw)
    await db_session.refresh(key)

    assert key.last_used_at is not None


def test_key_state_is_pure():
    active = _now()
    assert key_state(revoked_at=None, expires_at=None, now=active) == "ACTIVE"
    assert key_state(revoked_at=active, expires_at=None, now=active) == "REVOKED"
    assert (
        key_state(revoked_at=None, expires_at=active - timedelta(seconds=1), now=active)
        == "EXPIRED"
    )
    assert (
        key_state(revoked_at=None, expires_at=active + timedelta(days=1), now=active) == "ACTIVE"
    )
    # 폐기가 만료보다 우선 — 사용자가 명시적으로 끈 것이 더 중요한 사실이다
    assert (
        key_state(revoked_at=active, expires_at=active - timedelta(days=1), now=active)
        == "REVOKED"
    )
```

- [ ] **Step 2: 실패를 확인한다**

Run: `cd backend && uv run pytest tests/test_api_keys_service.py -v`
Expected: FAIL — `ImportError: cannot import name 'authenticate_key'`

- [ ] **Step 3: 구현**

`backend/app/services/api_keys.py`에 추가 (상단 import 갱신 포함):

```python
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.errors import AuthError
from app.models import ApiKey, User


def key_state(
    *, revoked_at: datetime | None, expires_at: datetime | None, now: datetime
) -> str:
    """ACTIVE | REVOKED | EXPIRED. 목록 표시와 인증 판정이 같은 규칙을 쓰게 하려고 순수 함수로 둔다."""
    if revoked_at is not None:
        return "REVOKED"
    if expires_at is not None and expires_at <= now:
        return "EXPIRED"
    return "ACTIVE"


async def authenticate_key(session: AsyncSession, raw: str) -> tuple[User, list[str]]:
    """평문 키로 소유자와 스코프를 얻는다. 실패는 전부 401이다.

    폐기·만료를 각각 다른 코드로 돌려주는 이유: Agent가 "키를 갱신하면 되는 상황"과
    "관리자가 끈 상황"을 구분해야 재시도 여부를 판단할 수 있다. 존재하지 않는 키는
    이 둘과 섞어 `INVALID_API_KEY` 하나로 뭉갠다 — 남의 키의 상태를 알려줄 이유가 없다.
    """
    if not raw.startswith(KEY_PREFIX):
        raise AuthError("INVALID_API_KEY", "유효하지 않은 API Key입니다")

    key = (
        await session.execute(select(ApiKey).where(ApiKey.key_hash == hash_key(raw)))
    ).scalar_one_or_none()
    if key is None:
        raise AuthError("INVALID_API_KEY", "유효하지 않은 API Key입니다")

    now = datetime.now(timezone.utc)
    state = key_state(revoked_at=key.revoked_at, expires_at=key.expires_at, now=now)
    if state == "REVOKED":
        raise AuthError("API_KEY_REVOKED", "폐기된 API Key입니다")
    if state == "EXPIRED":
        raise AuthError("API_KEY_EXPIRED", "만료된 API Key입니다")

    user = await session.get(User, key.user_id)
    # 퇴사 처리된 사용자의 키가 계속 살아 있으면 안 된다. 키가 아니라 사용자 쪽 문제이므로
    # 상태를 구분해 알려주지 않는다.
    if user is None or not user.is_active:
        raise AuthError("INVALID_API_KEY", "유효하지 않은 API Key입니다")

    key.last_used_at = now
    await session.flush()
    return user, list(key.scopes)
```

- [ ] **Step 4: 통과를 확인한다**

Run: `cd backend && uv run pytest tests/test_api_keys_service.py -v`
Expected: 13 passed

- [ ] **Step 5: mutation으로 가드를 검증한다**

`authenticate_key`에서 `if state == "REVOKED": raise ...` 두 줄을 지우고 `uv run pytest tests/test_api_keys_service.py -q`를 돌린다.
Expected: `test_revoked_key_is_rejected_with_its_own_code` 실패. 같은 방식으로 `is_active` 검사를 지우면 `test_key_of_an_inactive_user_is_rejected`가 실패한다. 확인 후 `git checkout backend/app/services/api_keys.py`로 되돌리고 다시 13 passed를 확인한다.

- [ ] **Step 6: 커밋**

```bash
git add backend/app/services/api_keys.py backend/tests/test_api_keys_service.py
git commit -m "feat(api-keys): authenticate raw keys and stamp last_used_at"
```

---

## Task 6: `get_principal`의 API Key 분기

**Files:**
- Modify: `backend/app/deps.py`
- Test: `backend/tests/test_apikey_auth.py`

- [ ] **Step 1: 실패하는 테스트를 쓴다**

`backend/tests/test_apikey_auth.py`:

```python
"""X-API-Key 인증 경로. 웹과 같은 엔드포인트를 키로 호출할 수 있어야 한다."""

from datetime import datetime, timedelta, timezone

from app.enums import ApiKeyScope
from tests.factories import make_api_key, make_user


async def test_api_key_can_call_the_same_endpoint_as_the_browser(client, db_session, seeded):
    user = await make_user(db_session, name="에이전트")
    raw, _ = await make_api_key(db_session, user=user, scopes=[ApiKeyScope.TRIPS_READ])

    response = await client.get("/api/v1/trips", headers={"X-API-Key": raw})

    assert response.status_code == 200
    assert "items" in response.json()


async def test_api_key_identifies_its_owner(client, db_session, seeded):
    user = await make_user(db_session, name="키주인")
    raw, _ = await make_api_key(db_session, user=user)

    response = await client.get("/api/v1/auth/me", headers={"X-API-Key": raw})

    assert response.status_code == 200
    assert response.json()["name"] == "키주인"


async def test_missing_credentials_are_401(client, seeded):
    response = await client.get("/api/v1/auth/me")
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "MISSING_CREDENTIALS"


async def test_unknown_api_key_is_401(client, seeded):
    response = await client.get("/api/v1/auth/me", headers={"X-API-Key": "sk_live_" + "0" * 32})
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "INVALID_API_KEY"


async def test_revoked_api_key_is_401(client, db_session, seeded):
    user = await make_user(db_session)
    raw, _ = await make_api_key(db_session, user=user, revoked_at=datetime.now(timezone.utc))
    response = await client.get("/api/v1/auth/me", headers={"X-API-Key": raw})
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "API_KEY_REVOKED"


async def test_expired_api_key_is_401(client, db_session, seeded):
    user = await make_user(db_session)
    raw, _ = await make_api_key(
        db_session, user=user, expires_at=datetime.now(timezone.utc) - timedelta(days=1)
    )
    response = await client.get("/api/v1/auth/me", headers={"X-API-Key": raw})
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "API_KEY_EXPIRED"


async def test_api_key_wins_when_both_headers_are_present(client, db_session, login_as, seeded):
    """브라우저는 항상 Authorization을 보낸다. 명시적으로 얹은 키가 이긴다 — 결정적이어야 한다."""
    key_owner = await make_user(db_session, name="키주인")
    raw, _ = await make_api_key(db_session, user=key_owner)
    headers = await login_as("user1@skon.example")
    headers["X-API-Key"] = raw

    response = await client.get("/api/v1/auth/me", headers=headers)

    assert response.status_code == 200
    assert response.json()["name"] == "키주인"


async def test_last_used_at_is_persisted_across_requests(client, db_session, seeded):
    user = await make_user(db_session)
    raw, key = await make_api_key(db_session, user=user)

    await client.get("/api/v1/auth/me", headers={"X-API-Key": raw})
    await db_session.refresh(key)

    assert key.last_used_at is not None
```

- [ ] **Step 2: 실패를 확인한다**

Run: `cd backend && uv run pytest tests/test_apikey_auth.py -v`
Expected: 대부분 401 `MISSING_CREDENTIALS`로 FAIL (아직 `X-API-Key`를 읽지 않는다)

- [ ] **Step 3: 구현**

`backend/app/deps.py`를 아래로 교체한다 (스코프 강제는 Task 7에서 붙인다):

```python
from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.errors import AuthError, ForbiddenError
from app.models import User
from app.security import decode_access_token
from app.services.api_keys import authenticate_key

DbSession = Annotated[AsyncSession, Depends(get_db)]

#: Agent가 쓰는 헤더 이름 (spec 7).
API_KEY_HEADER = "X-API-Key"


class _Unrestricted:
    """JWT 인증에는 스코프 제한이 없음을 나타내는 센티널."""

    def __repr__(self) -> str:  # pragma: no cover - 디버깅 편의용
        return "UNRESTRICTED"


UNRESTRICTED = _Unrestricted()


async def _authenticate_jwt(request: Request, session: AsyncSession) -> User:
    header = request.headers.get("Authorization")
    if not header or not header.lower().startswith("bearer "):
        raise AuthError("MISSING_CREDENTIALS", "인증 정보가 없습니다")

    user_id = decode_access_token(header.split(" ", 1)[1].strip())
    user = await session.get(User, user_id)
    if user is None or not user.is_active:
        raise AuthError("INVALID_TOKEN", "유효하지 않은 토큰입니다")
    return user


async def get_principal(request: Request, session: DbSession) -> User:
    """JWT 또는 API Key로 인증한다. 웹과 Agent가 같은 라우터를 쓰는 지점이다.

    두 헤더가 동시에 오면 `X-API-Key`가 이긴다. 브라우저는 로그인해 있으면 항상
    Authorization을 보내므로, 키를 명시적으로 얹은 쪽이 더 구체적인 의도이고
    무엇보다 우선순위가 결정적이어야 한다.
    """
    api_key = request.headers.get(API_KEY_HEADER)
    if api_key:
        user, scopes = await authenticate_key(session, api_key.strip())
        # 여기서 commit하는 이유: last_used_at은 요청의 성패와 무관하게 남아야 한다.
        # 이후 서비스가 실패해 롤백해도 "이 키가 쓰였다"는 사실은 지워지면 안 된다.
        # 아직 아무 도메인 작업도 시작되지 않은 시점이라 다른 트랜잭션을 끊지 않는다.
        await session.commit()
        request.state.scopes = scopes
        request.state.auth_method = "api_key"
        return user

    user = await _authenticate_jwt(request, session)
    # UNRESTRICTED 센티널을 쓰는 이유: None을 쓰면 "제한 없음"과 "get_principal이 아예
    # 실행되지 않음"이 구분되지 않는다. 스코프 검사기가 기본값으로 읽는 순간,
    # 의존성을 빠뜨린 엔드포인트가 조용히 전체 권한을 얻는다.
    request.state.scopes = UNRESTRICTED
    request.state.auth_method = "jwt"
    return user


CurrentUser = Annotated[User, Depends(get_principal)]


def require_role(*roles: str):
    async def checker(user: CurrentUser) -> User:
        if user.role not in roles:
            raise ForbiddenError("FORBIDDEN_ROLE", "권한이 없습니다")
        return user

    return checker
```

- [ ] **Step 4: 통과를 확인한다**

Run: `cd backend && uv run pytest tests/test_apikey_auth.py tests/test_auth.py -v`
Expected: all passed

- [ ] **Step 5: 회귀 확인**

Run: `cd backend && uv run pytest -q`
Expected: 기존 408건 + 신규 전부 passed

- [ ] **Step 6: 커밋**

```bash
git add backend/app/deps.py backend/tests/test_apikey_auth.py
git commit -m "feat(api-keys): authenticate requests with X-API-Key"
```

---

## Task 7: 스코프 강제 (단일 지점)

**Files:**
- Modify: `backend/app/deps.py`
- Test: `backend/tests/test_scope_enforcement.py`

- [ ] **Step 1: 실패하는 테스트를 쓴다**

`backend/tests/test_scope_enforcement.py`:

```python
"""스코프 강제. 검사는 get_principal 안 한 곳에서만 일어난다."""

from app.enums import ApiKeyScope
from tests.factories import make_api_key, make_user


async def test_key_without_the_scope_is_403(client, db_session, seeded):
    user = await make_user(db_session)
    raw, _ = await make_api_key(db_session, user=user, scopes=[ApiKeyScope.CARDS_READ])

    response = await client.get("/api/v1/trips", headers={"X-API-Key": raw})

    assert response.status_code == 403
    body = response.json()["error"]
    assert body["code"] == "SCOPE_REQUIRED"
    # Agent가 어떤 스코프를 붙여야 하는지 메시지만 보고 알 수 있어야 한다
    assert "trips:read" in body["message"]


async def test_read_scope_cannot_write(client, db_session, seeded):
    user = await make_user(db_session)
    raw, _ = await make_api_key(db_session, user=user, scopes=[ApiKeyScope.TRIPS_READ])

    response = await client.post(
        "/api/v1/trips",
        headers={"X-API-Key": raw},
        json={
            "title": "스코프 테스트",
            "purpose_code": "CUSTOMER",
            "purpose_detail": "라인 점검",
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

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "SCOPE_REQUIRED"


async def test_write_scope_does_not_imply_read(client, db_session, seeded):
    """쓰기가 읽기를 포함한다고 가정하지 않는다. 표에 적힌 것만 통과한다."""
    user = await make_user(db_session)
    raw, _ = await make_api_key(db_session, user=user, scopes=[ApiKeyScope.TRIPS_WRITE])

    response = await client.get("/api/v1/trips", headers={"X-API-Key": raw})

    assert response.status_code == 403


async def test_scopeless_endpoint_passes_with_any_key(client, db_session, seeded):
    user = await make_user(db_session)
    raw, _ = await make_api_key(db_session, user=user, scopes=[])

    for path in ("/api/v1/auth/me", "/api/v1/codes", "/api/v1/fund-centers"):
        response = await client.get(path, headers={"X-API-Key": raw})
        assert response.status_code == 200, path


async def test_jwt_is_unrestricted(client, login_as, seeded):
    """JWT는 전 권한(role 범위 내)이다 — 스코프 개념이 적용되지 않는다."""
    headers = await login_as("user1@skon.example")
    for path in ("/api/v1/trips", "/api/v1/cards", "/api/v1/expenses"):
        response = await client.get(path, headers=headers)
        assert response.status_code == 200, path


async def test_role_check_still_applies_to_keys(client, db_session, seeded):
    """스코프는 권한을 **축소만** 한다. 키가 있다고 역할을 넘어설 수 없다."""
    from app.enums import TripStatus
    from tests.factories import make_trip

    owner = await make_user(db_session, name="신청자")
    trip = await make_trip(db_session, user=owner, status=TripStatus.SUBMITTED)
    stranger = await make_user(db_session, name="남")
    raw, _ = await make_api_key(db_session, user=stranger, scopes=[ApiKeyScope.TRIPS_WRITE])

    response = await client.post(f"/api/v1/trips/{trip.id}/approve", headers={"X-API-Key": raw})

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "TRIP_NOT_FOUND"
```

`make_trip`의 시그니처는 `tests/factories.py`에서 확인하고 필요하면 인자 이름을 맞춘다.

- [ ] **Step 2: 실패를 확인한다**

Run: `cd backend && uv run pytest tests/test_scope_enforcement.py -v`
Expected: FAIL — 스코프 없는 키가 200을 받는다 (`assert 200 == 403`)

- [ ] **Step 3: 구현**

`backend/app/deps.py`: import에 `required_scope_for`를 추가하고, `_enforce_scope`를 넣은 뒤 `get_principal`이 두 분기 **모두**에서 그것을 통과하게 고친다.

```python
from app.errors import AuthError, ForbiddenError
from app.services.api_scopes import required_scope_for


def _enforce_scope(request: Request) -> None:
    """이 요청이 이 엔드포인트를 부를 스코프를 가졌는지 본다.

    검사가 여기 한 곳에만 있는 것이 핵심이다. 엔드포인트마다 의존성을 붙이는 방식은
    빠뜨릴 수 있고, 빠뜨린 결과가 fail-open(그 엔드포인트만 전권)이다.
    """
    route = request.scope.get("route")
    path = getattr(route, "path", None)
    if path is None:  # pragma: no cover - 라우팅된 요청에는 항상 route가 있다
        raise ForbiddenError("SCOPE_UNDECLARED", "경로를 확인할 수 없습니다")

    required = required_scope_for(request.method, path)
    scopes = request.state.scopes
    # 센티널과의 **동일성** 비교. `if not scopes`나 `getattr(..., None)`로 바꾸면
    # 스코프가 빈 키가 전권을 얻는다.
    if scopes is UNRESTRICTED:
        return
    if required is None:
        return
    if str(required) not in scopes:
        raise ForbiddenError(
            "SCOPE_REQUIRED", f"이 요청에는 {required} 스코프가 필요합니다"
        )
```

`get_principal`의 두 분기를 이렇게 바꾼다:

```python
    api_key = request.headers.get(API_KEY_HEADER)
    if api_key:
        user, scopes = await authenticate_key(session, api_key.strip())
        await session.commit()
        request.state.scopes = scopes
        request.state.auth_method = "api_key"
    else:
        user = await _authenticate_jwt(request, session)
        request.state.scopes = UNRESTRICTED
        request.state.auth_method = "jwt"

    _enforce_scope(request)
    return user
```

- [ ] **Step 4: 통과를 확인한다**

Run: `cd backend && uv run pytest tests/test_scope_enforcement.py -v`
Expected: 6 passed

- [ ] **Step 5: mutation으로 가드를 검증한다**

```bash
cd backend
# (a) 센티널 비교를 느슨하게 바꾼다
uv run python - <<'EOF'
from pathlib import Path
p = Path("app/deps.py")
s = p.read_text()
assert "if scopes is UNRESTRICTED:" in s
p.write_text(s.replace("if scopes is UNRESTRICTED:", "if not scopes:"))
EOF
grep -n "if not scopes:" app/deps.py    # 편집이 실제로 반영됐는지 확인
uv run pytest tests/test_scope_enforcement.py -q
```

Expected: `test_scopeless_endpoint_passes_with_any_key`가 아니라 **`test_key_without_the_scope_is_403`류가 통과**해버리는지 확인한다. 정확히는 스코프가 빈 키를 만들어 `/api/v1/trips`를 부르는 경우가 전권이 된다. 아래 테스트를 추가해 그 구멍을 고정한다:

```python
async def test_empty_scope_key_is_not_unrestricted(client, db_session, seeded):
    """스코프가 빈 키는 '제한 없음'이 아니라 '아무 것도 못 함'이다."""
    user = await make_user(db_session)
    raw, _ = await make_api_key(db_session, user=user, scopes=[])
    response = await client.get("/api/v1/trips", headers={"X-API-Key": raw})
    assert response.status_code == 403
```

이 테스트를 넣은 상태에서 위 mutation을 다시 적용하면 실패해야 한다.

```bash
cd backend && git checkout app/deps.py && uv run pytest tests/test_scope_enforcement.py -q
```

Expected: 7 passed

- [ ] **Step 6: 회귀 확인**

Run: `cd backend && uv run pytest -q`
Expected: 전부 passed

- [ ] **Step 7: 커밋**

```bash
git add backend/app/deps.py backend/tests/test_scope_enforcement.py
git commit -m "feat(api-keys): enforce scopes in a single place"
```

---

## Task 8: 키 관리 API는 JWT 전용

API Key가 새 API Key를 발급할 수 있으면 스코프 제한이 무의미해진다.

**Files:**
- Modify: `backend/app/deps.py`
- Test: `backend/tests/test_scope_enforcement.py` (추가) — 라우터가 생긴 뒤 Task 10에서 엔드투엔드로 다시 확인한다

- [ ] **Step 1: 실패하는 테스트를 쓴다**

`backend/tests/test_scope_enforcement.py` 끝에 추가:

```python
async def test_jwt_only_dependency_rejects_api_keys(db_session):
    """의존성 단위 테스트. 라우터는 Task 10에서 붙는다."""
    import pytest
    from fastapi import Request

    from app.deps import get_jwt_principal
    from app.errors import ForbiddenError

    request = Request({"type": "http", "method": "GET", "headers": [], "path": "/"})
    request.state.auth_method = "api_key"
    user = await make_user(db_session)

    with pytest.raises(ForbiddenError) as exc:
        await get_jwt_principal(request, user)
    assert exc.value.code == "API_KEY_FORBIDDEN"


async def test_jwt_only_dependency_accepts_jwt(db_session):
    from fastapi import Request

    from app.deps import get_jwt_principal

    request = Request({"type": "http", "method": "GET", "headers": [], "path": "/"})
    request.state.auth_method = "jwt"
    user = await make_user(db_session)

    assert await get_jwt_principal(request, user) is user


async def test_jwt_only_dependency_rejects_unknown_auth_method(db_session):
    """auth_method가 없으면 거부한다 — 모르면 막는 쪽이 기본값이다."""
    import pytest
    from fastapi import Request

    from app.deps import get_jwt_principal
    from app.errors import ForbiddenError

    request = Request({"type": "http", "method": "GET", "headers": [], "path": "/"})
    user = await make_user(db_session)

    with pytest.raises(ForbiddenError):
        await get_jwt_principal(request, user)
```

- [ ] **Step 2: 실패를 확인한다**

Run: `cd backend && uv run pytest tests/test_scope_enforcement.py -v -k jwt_only`
Expected: FAIL — `ImportError: cannot import name 'get_jwt_principal'`

- [ ] **Step 3: 구현**

`backend/app/deps.py` 끝에 추가:

```python
async def get_jwt_principal(request: Request, user: CurrentUser) -> User:
    """로그인 세션(JWT)에서만 허용하는 엔드포인트용.

    API Key로 새 API Key를 만들 수 있으면 스코프 제한이 통째로 무의미해진다 —
    `cards:read` 키 하나로 전권 키를 찍어낼 수 있게 된다. 그래서 키 관리 API는
    사람이 로그인한 세션에서만 열린다.

    `get_principal`을 거쳐 오므로 스코프 표 소진 가드도 이 라우트를 함께 검사한다.
    auth_method가 없으면(=예상 못 한 경로) 통과가 아니라 거부다.
    """
    if getattr(request.state, "auth_method", None) != "jwt":
        raise ForbiddenError("API_KEY_FORBIDDEN", "이 작업은 로그인 세션에서만 가능합니다")
    return user


JwtOnlyUser = Annotated[User, Depends(get_jwt_principal)]
```

- [ ] **Step 4: 통과를 확인한다**

Run: `cd backend && uv run pytest tests/test_scope_enforcement.py -v`
Expected: 10 passed

- [ ] **Step 5: 커밋**

```bash
git add backend/app/deps.py backend/tests/test_scope_enforcement.py
git commit -m "feat(api-keys): add JWT-only dependency for key management"
```

---

## Task 9: 발급·목록·폐기 서비스

**Files:**
- Modify: `backend/app/services/api_keys.py`
- Test: `backend/tests/test_api_keys_service.py`

- [ ] **Step 1: 실패하는 테스트를 쓴다**

`backend/tests/test_api_keys_service.py` 끝에 추가:

```python
from app.errors import ConflictError, NotFoundError, ValidationError
from app.schemas.api_key import ApiKeyCreate
from app.services.api_keys import MAX_ACTIVE_KEYS, create_key, list_keys, revoke_key


async def test_create_returns_plaintext_once_and_stores_only_the_hash(db_session):
    user = await make_user(db_session)
    created = await create_key(
        db_session,
        user=user,
        payload=ApiKeyCreate(name="에이전트 키", scopes=[ApiKeyScope.TRIPS_READ]),
    )

    assert created.key.startswith("sk_live_")
    assert created.key_prefix == created.key[:16]
    # 목록에는 평문이 없다
    listed = await list_keys(db_session, user=user)
    assert not hasattr(listed[0], "key")
    assert listed[0].key_prefix == created.key_prefix


async def test_create_rejects_an_unknown_scope(db_session):
    user = await make_user(db_session)
    with pytest.raises(ValidationError) as exc:
        await create_key(
            db_session, user=user, payload=ApiKeyCreate(name="x", scopes=["trips:delete"])
        )
    assert exc.value.code == "INVALID_SCOPE"
    assert exc.value.field == "scopes"


async def test_create_requires_at_least_one_scope(db_session):
    """스코프 0개 키는 아무 것도 못 하므로 만들 이유가 없다. 만들게 두면 사용자가 헤맨다."""
    user = await make_user(db_session)
    with pytest.raises(ValidationError) as exc:
        await create_key(db_session, user=user, payload=ApiKeyCreate(name="x", scopes=[]))
    assert exc.value.code == "SCOPES_REQUIRED"


async def test_create_deduplicates_scopes(db_session):
    user = await make_user(db_session)
    created = await create_key(
        db_session,
        user=user,
        payload=ApiKeyCreate(
            name="x", scopes=[ApiKeyScope.TRIPS_READ, ApiKeyScope.TRIPS_READ]
        ),
    )
    assert created.scopes == ["trips:read"]


async def test_create_sets_expiry_from_days(db_session):
    user = await make_user(db_session)
    created = await create_key(
        db_session,
        user=user,
        payload=ApiKeyCreate(name="x", scopes=[ApiKeyScope.TRIPS_READ], expires_in_days=30),
    )
    assert created.expires_at is not None
    delta = created.expires_at - datetime.now(timezone.utc)
    assert timedelta(days=29) < delta <= timedelta(days=30)


async def test_create_without_expiry_never_expires(db_session):
    user = await make_user(db_session)
    created = await create_key(
        db_session, user=user, payload=ApiKeyCreate(name="x", scopes=[ApiKeyScope.TRIPS_READ])
    )
    assert created.expires_at is None


async def test_active_key_count_is_capped(db_session):
    user = await make_user(db_session)
    for index in range(MAX_ACTIVE_KEYS):
        await make_api_key(db_session, user=user, name=f"키{index}")

    with pytest.raises(ConflictError) as exc:
        await create_key(
            db_session, user=user, payload=ApiKeyCreate(name="넘침", scopes=[ApiKeyScope.TRIPS_READ])
        )
    assert exc.value.code == "TOO_MANY_KEYS"


async def test_revoked_keys_do_not_count_towards_the_cap(db_session):
    user = await make_user(db_session)
    for index in range(MAX_ACTIVE_KEYS):
        await make_api_key(
            db_session, user=user, name=f"키{index}", revoked_at=datetime.now(timezone.utc)
        )

    created = await create_key(
        db_session, user=user, payload=ApiKeyCreate(name="새 키", scopes=[ApiKeyScope.TRIPS_READ])
    )
    assert created.key.startswith("sk_live_")


async def test_list_shows_only_my_keys_newest_first(db_session):
    mine = await make_user(db_session, name="나")
    other = await make_user(db_session, name="남")
    await make_api_key(db_session, user=other, name="남의 키")
    await make_api_key(db_session, user=mine, name="내 키 1")
    await make_api_key(db_session, user=mine, name="내 키 2")

    listed = await list_keys(db_session, user=mine)

    assert [item.name for item in listed] == ["내 키 2", "내 키 1"]


async def test_list_reports_state(db_session):
    user = await make_user(db_session)
    await make_api_key(db_session, user=user, name="살아있음")
    await make_api_key(
        db_session, user=user, name="만료됨", expires_at=datetime.now(timezone.utc) - timedelta(days=1)
    )
    await make_api_key(db_session, user=user, name="폐기됨", revoked_at=datetime.now(timezone.utc))

    states = {item.name: item.state for item in await list_keys(db_session, user=user)}

    assert states == {"살아있음": "ACTIVE", "만료됨": "EXPIRED", "폐기됨": "REVOKED"}


async def test_revoke_marks_the_key_and_kills_authentication(db_session):
    user = await make_user(db_session)
    raw, key = await make_api_key(db_session, user=user)

    result = await revoke_key(db_session, user=user, key_id=key.id)

    assert result.state == "REVOKED"
    with pytest.raises(AuthError) as exc:
        await authenticate_key(db_session, raw)
    assert exc.value.code == "API_KEY_REVOKED"


async def test_revoking_someone_elses_key_is_404(db_session):
    mine = await make_user(db_session, name="나")
    other = await make_user(db_session, name="남")
    _, key = await make_api_key(db_session, user=other)

    with pytest.raises(NotFoundError) as exc:
        await revoke_key(db_session, user=mine, key_id=key.id)
    assert exc.value.code == "API_KEY_NOT_FOUND"


async def test_revoking_twice_is_409(db_session):
    user = await make_user(db_session)
    _, key = await make_api_key(db_session, user=user, revoked_at=datetime.now(timezone.utc))

    with pytest.raises(ConflictError) as exc:
        await revoke_key(db_session, user=user, key_id=key.id)
    assert exc.value.code == "API_KEY_ALREADY_REVOKED"
```

- [ ] **Step 2: 실패를 확인한다**

Run: `cd backend && uv run pytest tests/test_api_keys_service.py -v -k create`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.schemas.api_key'`

- [ ] **Step 3: 스키마를 만든다**

`backend/app/schemas/api_key.py`:

```python
from datetime import datetime

from pydantic import BaseModel, Field

from app.enums import ApiKeyScope

#: 만료 최대치. 무제한 키를 허용하되(만료 없음), 숫자를 넣을 거면 상식적인 범위로 막는다.
MAX_EXPIRES_DAYS = 365


class ApiKeyCreate(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    # 스코프는 문자열로 받고 서비스가 검증한다. 여기서 Enum으로 강제하면 오타가
    # 422 SCHEMA_INVALID로 떨어져 "어떤 값이 유효한지"를 알려주지 못한다.
    scopes: list[str]
    expires_in_days: int | None = Field(default=None, ge=1, le=MAX_EXPIRES_DAYS)


class ApiKeyOut(BaseModel):
    id: int
    name: str
    key_prefix: str
    scopes: list[str]
    state: str
    last_used_at: datetime | None
    expires_at: datetime | None
    revoked_at: datetime | None
    created_at: datetime


class ApiKeyCreated(ApiKeyOut):
    """발급 직후에만 존재하는 응답. `key`는 이 응답 이후 어디에도 남지 않는다."""

    key: str


class ScopeInfo(BaseModel):
    scope: ApiKeyScope
    description: str
    endpoints: list[str]
```

- [ ] **Step 4: 서비스를 구현한다**

`backend/app/services/api_keys.py`에 추가:

```python
from datetime import timedelta

from sqlalchemy import func

from app.enums import ApiKeyScope
from app.errors import ConflictError, NotFoundError, ValidationError
from app.schemas.api_key import ApiKeyCreate, ApiKeyCreated, ApiKeyOut

#: 사용자당 활성 키 상한. 무한 발급을 막는 방어선이고, 목록 UI가 감당할 수 있는 크기다.
MAX_ACTIVE_KEYS = 10


def _to_out(key: ApiKey, now: datetime) -> ApiKeyOut:
    return ApiKeyOut(
        id=key.id,
        name=key.name,
        key_prefix=key.key_prefix,
        scopes=list(key.scopes),
        state=key_state(revoked_at=key.revoked_at, expires_at=key.expires_at, now=now),
        last_used_at=key.last_used_at,
        expires_at=key.expires_at,
        revoked_at=key.revoked_at,
        created_at=key.created_at,
    )


def _validate_scopes(scopes: list[str]) -> list[str]:
    """중복을 제거하고 선언 순서로 정렬한다. 알 수 없는 값은 400이다.

    유효값을 메시지에 실어 보낸다 — Agent가 오타를 스스로 고칠 수 있어야 한다.
    """
    if not scopes:
        raise ValidationError("SCOPES_REQUIRED", "스코프를 최소 1개 선택하세요", field="scopes")
    known = {str(scope) for scope in ApiKeyScope}
    unknown = sorted({str(scope) for scope in scopes} - known)
    if unknown:
        raise ValidationError(
            "INVALID_SCOPE",
            f"알 수 없는 스코프입니다: {', '.join(unknown)} (가능한 값: {', '.join(sorted(known))})",
            field="scopes",
        )
    requested = {str(scope) for scope in scopes}
    return [str(scope) for scope in ApiKeyScope if str(scope) in requested]


async def create_key(
    session: AsyncSession, *, user: User, payload: ApiKeyCreate
) -> ApiKeyCreated:
    scopes = _validate_scopes(payload.scopes)
    now = datetime.now(timezone.utc)

    active = (
        await session.execute(
            select(func.count())
            .select_from(ApiKey)
            .where(
                ApiKey.user_id == user.id,
                ApiKey.revoked_at.is_(None),
                (ApiKey.expires_at.is_(None)) | (ApiKey.expires_at > now),
            )
        )
    ).scalar_one()
    if active >= MAX_ACTIVE_KEYS:
        raise ConflictError(
            "TOO_MANY_KEYS", f"활성 키는 최대 {MAX_ACTIVE_KEYS}개입니다. 쓰지 않는 키를 폐기하세요"
        )

    raw, prefix, digest = generate_key()
    key = ApiKey(
        user_id=user.id,
        name=payload.name,
        key_prefix=prefix,
        key_hash=digest,
        scopes=scopes,
        expires_at=(
            now + timedelta(days=payload.expires_in_days) if payload.expires_in_days else None
        ),
    )
    session.add(key)
    await session.commit()
    await session.refresh(key)
    # 평문은 이 응답에만 존재한다. 여기서 흘리지 않으면 사용자는 영영 볼 수 없다(spec 5.7).
    return ApiKeyCreated(**_to_out(key, now).model_dump(), key=raw)


async def list_keys(session: AsyncSession, *, user: User) -> list[ApiKeyOut]:
    now = datetime.now(timezone.utc)
    rows = (
        (
            await session.execute(
                select(ApiKey)
                .where(ApiKey.user_id == user.id)
                .order_by(ApiKey.created_at.desc(), ApiKey.id.desc())
            )
        )
        .scalars()
        .all()
    )
    return [_to_out(row, now) for row in rows]


async def revoke_key(session: AsyncSession, *, user: User, key_id: int) -> ApiKeyOut:
    key = await session.get(ApiKey, key_id)
    # 남의 키는 존재 자체를 알리지 않는다.
    if key is None or key.user_id != user.id:
        raise NotFoundError("API_KEY_NOT_FOUND", "API Key를 찾을 수 없습니다")
    if key.revoked_at is not None:
        raise ConflictError("API_KEY_ALREADY_REVOKED", "이미 폐기된 키입니다")

    key.revoked_at = datetime.now(timezone.utc)
    await session.commit()
    await session.refresh(key)
    return _to_out(key, datetime.now(timezone.utc))
```

`tests/test_api_keys_service.py`의 `list_keys` 정렬 테스트는 `created_at`이 같은 초에 몰릴 수 있으므로 `ApiKey.id.desc()` 보조 정렬에 의존한다.

- [ ] **Step 5: 통과를 확인한다**

Run: `cd backend && uv run pytest tests/test_api_keys_service.py -v`
Expected: 26 passed

- [ ] **Step 6: mutation으로 가드를 검증한다**

`_validate_scopes`의 `unknown` 검사를 지우면 `test_create_rejects_an_unknown_scope`가, 소유자 조건(`key.user_id != user.id`)을 지우면 `test_revoking_someone_elses_key_is_404`가, 활성 개수 조건에서 `revoked_at.is_(None)`을 지우면 `test_revoked_keys_do_not_count_towards_the_cap`이 실패해야 한다. 각각 확인 후 `git checkout backend/app/services/api_keys.py`.

- [ ] **Step 7: 커밋**

```bash
git add backend/app/services/api_keys.py backend/app/schemas/api_key.py backend/tests/test_api_keys_service.py
git commit -m "feat(api-keys): issue, list and revoke keys"
```

---

## Task 10: `/api/v1/api-keys` 라우터

라우터와 `SCOPE_REQUIREMENTS` 항목은 **반드시 같은 커밋에서** 움직인다. 한쪽만 바꾸면 소진 가드가 기동을 막는다 — 그게 이 가드의 목적이다.

**Files:**
- Create: `backend/app/routers/api_keys.py`
- Modify: `backend/app/services/api_scopes.py` (표에 3줄 추가)
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_api_keys_api.py`

- [ ] **Step 1: 실패하는 테스트를 쓴다**

`backend/tests/test_api_keys_api.py`:

```python
"""API Key 관리 엔드포인트. 로그인 세션 전용이다."""

from app.enums import ApiKeyScope
from tests.factories import make_api_key, make_user


async def test_issue_returns_the_plaintext_key_once(client, login_as, seeded):
    headers = await login_as("user1@skon.example")

    created = await client.post(
        "/api/v1/api-keys",
        headers=headers,
        json={"name": "내 에이전트", "scopes": ["trips:read", "trips:write"]},
    )

    assert created.status_code == 201
    body = created.json()
    assert body["key"].startswith("sk_live_")
    assert body["scopes"] == ["trips:read", "trips:write"]
    assert body["state"] == "ACTIVE"

    listed = await client.get("/api/v1/api-keys", headers=headers)
    assert listed.status_code == 200
    row = next(item for item in listed.json() if item["id"] == body["id"])
    assert "key" not in row  # 평문은 목록에 절대 없다
    assert row["key_prefix"] == body["key_prefix"]


async def test_issued_key_works_on_the_same_endpoints(client, login_as, seeded):
    headers = await login_as("user1@skon.example")
    created = await client.post(
        "/api/v1/api-keys", headers=headers, json={"name": "키", "scopes": ["trips:read"]}
    )
    raw = created.json()["key"]

    response = await client.get("/api/v1/trips", headers={"X-API-Key": raw})

    assert response.status_code == 200


async def test_unknown_scope_is_400_with_field(client, login_as, seeded):
    headers = await login_as("user1@skon.example")
    response = await client.post(
        "/api/v1/api-keys", headers=headers, json={"name": "키", "scopes": ["trips:delete"]}
    )
    assert response.status_code == 400
    body = response.json()["error"]
    assert body["code"] == "INVALID_SCOPE"
    assert body["field"] == "scopes"


async def test_revoke_kills_the_key(client, login_as, seeded):
    headers = await login_as("user1@skon.example")
    created = await client.post(
        "/api/v1/api-keys", headers=headers, json={"name": "키", "scopes": ["trips:read"]}
    )
    body = created.json()

    revoked = await client.post(f"/api/v1/api-keys/{body['id']}/revoke", headers=headers)
    assert revoked.status_code == 200
    assert revoked.json()["state"] == "REVOKED"

    denied = await client.get("/api/v1/trips", headers={"X-API-Key": body["key"]})
    assert denied.status_code == 401
    assert denied.json()["error"]["code"] == "API_KEY_REVOKED"


async def test_cannot_see_or_revoke_someone_elses_key(client, db_session, login_as, seeded):
    other = await make_user(db_session, name="남")
    _, key = await make_api_key(db_session, user=other, scopes=[ApiKeyScope.TRIPS_READ])
    headers = await login_as("user1@skon.example")

    listed = await client.get("/api/v1/api-keys", headers=headers)
    assert all(item["id"] != key.id for item in listed.json())

    response = await client.post(f"/api/v1/api-keys/{key.id}/revoke", headers=headers)
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "API_KEY_NOT_FOUND"


async def test_an_api_key_cannot_mint_another_key(client, db_session, seeded):
    """키 세탁 방지 — cards:read 키 하나로 전권 키를 찍어낼 수 있으면 스코프가 무의미하다."""
    user = await make_user(db_session)
    raw, _ = await make_api_key(db_session, user=user, scopes=[ApiKeyScope.TRIPS_WRITE])

    response = await client.post(
        "/api/v1/api-keys",
        headers={"X-API-Key": raw},
        json={"name": "탈취", "scopes": ["trips:read"]},
    )

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "API_KEY_FORBIDDEN"


async def test_an_api_key_cannot_list_keys(client, db_session, seeded):
    user = await make_user(db_session)
    raw, _ = await make_api_key(db_session, user=user, scopes=[ApiKeyScope.TRIPS_READ])
    response = await client.get("/api/v1/api-keys", headers={"X-API-Key": raw})
    assert response.status_code == 403


async def test_expiry_days_out_of_range_is_422(client, login_as, seeded):
    headers = await login_as("user1@skon.example")
    response = await client.post(
        "/api/v1/api-keys",
        headers=headers,
        json={"name": "키", "scopes": ["trips:read"], "expires_in_days": 400},
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "SCHEMA_INVALID"
```

- [ ] **Step 2: 실패를 확인한다**

Run: `cd backend && uv run pytest tests/test_api_keys_api.py -v`
Expected: FAIL — 404 (라우트 없음)

- [ ] **Step 3: 라우터를 만든다**

`backend/app/routers/api_keys.py`:

```python
from fastapi import APIRouter, status

from app.deps import DbSession, JwtOnlyUser
from app.schemas.api_key import ApiKeyCreate, ApiKeyCreated, ApiKeyOut
from app.services import api_keys as api_key_service

router = APIRouter(prefix="/api/v1/api-keys", tags=["api-keys"])


@router.get("", response_model=list[ApiKeyOut])
async def list_api_keys(user: JwtOnlyUser, session: DbSession) -> list[ApiKeyOut]:
    return await api_key_service.list_keys(session, user=user)


@router.post("", response_model=ApiKeyCreated, status_code=status.HTTP_201_CREATED)
async def create_api_key(
    payload: ApiKeyCreate, user: JwtOnlyUser, session: DbSession
) -> ApiKeyCreated:
    """평문 키는 이 응답에만 담긴다. 다시 조회할 방법이 없다 (spec 5.7)."""
    return await api_key_service.create_key(session, user=user, payload=payload)


@router.post("/{key_id}/revoke", response_model=ApiKeyOut)
async def revoke_api_key(key_id: int, user: JwtOnlyUser, session: DbSession) -> ApiKeyOut:
    return await api_key_service.revoke_key(session, user=user, key_id=key_id)
```

- [ ] **Step 4: 표에 3줄을 추가한다**

`backend/app/services/api_scopes.py`의 `SCOPE_REQUIREMENTS`에서 `("GET", "/api/v1/notifications"): None,` 바로 위에 넣는다:

```python
    ("GET", "/api/v1/api-keys"): None,
    ("POST", "/api/v1/api-keys"): None,
    ("POST", "/api/v1/api-keys/{key_id}/revoke"): None,
```

- [ ] **Step 5: 라우터를 등록한다**

`backend/app/main.py`의 import에 `api_keys`를 추가하고 `assert_scope_table_complete(app)` **위에** 등록한다:

```python
from app.routers import api_keys, auth, cards, centers, codes, expenses, notifications, trips
...
app.include_router(api_keys.router)
```

- [ ] **Step 6: 통과를 확인한다**

Run: `cd backend && uv run pytest tests/test_api_keys_api.py tests/test_api_scopes.py -v`
Expected: all passed

- [ ] **Step 7: 표를 빠뜨리면 죽는지 확인한다 (mutation)**

```bash
cd backend
uv run python - <<'EOF'
from pathlib import Path
p = Path("app/services/api_scopes.py")
s = p.read_text()
target = '    ("POST", "/api/v1/api-keys"): None,\n'
assert target in s
p.write_text(s.replace(target, "", 1))
EOF
grep -c '"/api/v1/api-keys"' app/services/api_scopes.py   # 1 (GET만 남음)
uv run pytest tests/test_api_keys_api.py -q
```

Expected: 컬렉션 단계에서 `RuntimeError: SCOPE_REQUIREMENTS가 실제 라우트와 어긋납니다 ... ['POST /api/v1/api-keys']`

```bash
cd backend && git checkout app/services/api_scopes.py && uv run pytest tests/test_api_keys_api.py -q
```

Expected: 8 passed

- [ ] **Step 8: 커밋**

```bash
git add backend/app/routers/api_keys.py backend/app/services/api_scopes.py backend/app/main.py backend/tests/test_api_keys_api.py
git commit -m "feat(api-keys): add /api/v1/api-keys endpoints (JWT only)"
```

---

## Task 11: `GET /api/v1/scopes`

`/developers` 가이드가 스코프 표를 손으로 적으면 코드와 어긋난다. 같은 표에서 뽑아 내려준다.

**Files:**
- Create: `backend/app/routers/meta.py`
- Modify: `backend/app/services/api_scopes.py` (표에 1줄)
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_api_keys_api.py` (추가)

- [ ] **Step 1: 실패하는 테스트를 쓴다**

`backend/tests/test_api_keys_api.py` 끝에 추가:

```python
async def test_scope_catalog_is_served_from_the_same_table(client, login_as, seeded):
    headers = await login_as("user1@skon.example")

    response = await client.get("/api/v1/scopes", headers=headers)

    assert response.status_code == 200
    body = response.json()
    assert [item["scope"] for item in body] == [
        "trips:read",
        "trips:write",
        "expenses:read",
        "expenses:write",
        "cards:read",
        "admin",
    ]
    trips_read = next(item for item in body if item["scope"] == "trips:read")
    assert "GET /api/v1/trips" in trips_read["endpoints"]
    assert trips_read["description"]


async def test_scope_catalog_is_readable_with_any_key(client, db_session, seeded):
    """Agent가 자기 키로 '무엇을 부를 수 있는지'를 스스로 조회할 수 있어야 한다."""
    user = await make_user(db_session)
    raw, _ = await make_api_key(db_session, user=user, scopes=[ApiKeyScope.CARDS_READ])
    response = await client.get("/api/v1/scopes", headers={"X-API-Key": raw})
    assert response.status_code == 200
```

- [ ] **Step 2: 실패를 확인한다**

Run: `cd backend && uv run pytest tests/test_api_keys_api.py -v -k scope_catalog`
Expected: FAIL — 404

- [ ] **Step 3: 구현**

`backend/app/routers/meta.py`:

```python
from fastapi import APIRouter

from app.deps import CurrentUser
from app.schemas.api_key import ScopeInfo
from app.services.api_scopes import scope_catalog

router = APIRouter(prefix="/api/v1", tags=["meta"])


@router.get("/scopes", response_model=list[ScopeInfo])
async def list_scopes(user: CurrentUser) -> list[ScopeInfo]:
    """스코프별 설명과 해당 엔드포인트. `/developers` 가이드와 Agent가 같은 것을 본다.

    `user`를 쓰지 않지만 의존성은 유지한다 — 인증 없이 열면 라우트 목록이 그대로 노출되고,
    무엇보다 스코프 표 소진 가드가 이 라우트를 검사 대상에서 빼버린다.
    """
    return [
        ScopeInfo(scope=entry.scope, description=entry.description, endpoints=entry.endpoints)
        for entry in scope_catalog()
    ]
```

`backend/app/services/api_scopes.py`의 표에 추가:

```python
    ("GET", "/api/v1/scopes"): None,
```

`backend/app/main.py`: import에 `meta`를 추가하고 `assert_scope_table_complete(app)` 위에 `app.include_router(meta.router)`를 넣는다.

- [ ] **Step 4: 통과를 확인한다**

Run: `cd backend && uv run pytest tests/test_api_keys_api.py -v`
Expected: 10 passed

- [ ] **Step 5: 커밋**

```bash
git add backend/app/routers/meta.py backend/app/services/api_scopes.py backend/app/main.py backend/tests/test_api_keys_api.py
git commit -m "feat(api-keys): expose the scope catalog at /api/v1/scopes"
```

---

## Task 12: JWT 경로와 Key 경로의 동일 시나리오 검증

spec 8이 요구하는 항목이자 이 프로젝트의 핵심 메시지("사람이 화면에서 하는 일과 동일한 일을 Agent가 API Key로 수행한다")를 실제로 고정하는 테스트다.

**Files:**
- Test: `backend/tests/test_apikey_auth.py` (추가)

- [ ] **Step 1: 테스트를 쓴다**

`backend/tests/test_apikey_auth.py` 끝에 추가:

```python
#: 코드값은 전부 app/seed.py의 CODE_GROUPS에 실재하는 값이다. purpose_code에 "MEETING"
#: 같은 없는 값을 넣으면 400 INVALID_CODE가 나서 인증 테스트가 엉뚱한 이유로 깨진다.
TRIP_PAYLOAD = {
    "title": "울산 공장 점검",
    "purpose_code": "CUSTOMER",
    "purpose_detail": "라인 점검 및 협력사 미팅",
    "destination_type_code": "DOMESTIC",
    "country_code": "KR",
    "city": "울산",
    "start_date": "2026-09-01",
    "end_date": "2026-09-02",
    "transport_code": "AIR",
    "accommodation_code": "HOTEL",
    "cost_center_code": "CC2100",
    "estimated_cost": "300000",
}


async def _create_and_submit(client, headers) -> dict:
    created = await client.post("/api/v1/trips", headers=headers, json=TRIP_PAYLOAD)
    assert created.status_code == 201, created.text
    trip_id = created.json()["id"]
    submitted = await client.post(f"/api/v1/trips/{trip_id}/submit", headers=headers)
    assert submitted.status_code == 200, submitted.text
    return submitted.json()


async def test_jwt_and_api_key_produce_identical_results(client, db_session, login_as, seeded):
    """같은 사용자, 같은 엔드포인트, 두 인증 경로. 결과가 갈리면 안 된다."""
    jwt_headers = await login_as("user1@skon.example")

    from sqlalchemy import select

    from app.models import User

    user = (
        await db_session.execute(select(User).where(User.email == "user1@skon.example"))
    ).scalar_one()
    raw, _ = await make_api_key(
        db_session,
        user=user,
        scopes=[ApiKeyScope.TRIPS_READ, ApiKeyScope.TRIPS_WRITE],
    )
    key_headers = {"X-API-Key": raw}

    via_jwt = await _create_and_submit(client, jwt_headers)
    via_key = await _create_and_submit(client, key_headers)

    assert via_jwt["status"] == via_key["status"] == "SUBMITTED"
    assert via_jwt["title"] == via_key["title"]
    # 두 건 모두 같은 신청자로 기록된다
    assert via_jwt["user_id"] == via_key["user_id"]


async def test_timeline_is_recorded_for_the_api_key_path(client, db_session, login_as, seeded):
    """웹 경로로 들어오든 키 경로로 들어오든 이력이 누락될 수 없다 (spec 5.8)."""
    from sqlalchemy import select

    from app.models import User

    user = (
        await db_session.execute(select(User).where(User.email == "user1@skon.example"))
    ).scalar_one()
    raw, _ = await make_api_key(
        db_session, user=user, scopes=[ApiKeyScope.TRIPS_READ, ApiKeyScope.TRIPS_WRITE]
    )
    headers = {"X-API-Key": raw}

    trip = await _create_and_submit(client, headers)
    timeline = await client.get(f"/api/v1/trips/{trip['id']}/timeline", headers=headers)

    assert timeline.status_code == 200
    assert [entry["action"] for entry in timeline.json()] == ["CREATED", "SUBMITTED"]


async def test_error_contract_is_identical_on_both_paths(client, db_session, login_as, seeded):
    """409 도메인 코드가 두 경로에서 같아야 Agent가 웹과 같은 판단을 할 수 있다."""
    from sqlalchemy import select

    from app.models import User

    user = (
        await db_session.execute(select(User).where(User.email == "user1@skon.example"))
    ).scalar_one()
    raw, _ = await make_api_key(
        db_session, user=user, scopes=[ApiKeyScope.TRIPS_READ, ApiKeyScope.TRIPS_WRITE]
    )

    jwt_headers = await login_as("user1@skon.example")
    trip = await _create_and_submit(client, jwt_headers)

    for headers in (jwt_headers, {"X-API-Key": raw}):
        again = await client.post(f"/api/v1/trips/{trip['id']}/submit", headers=headers)
        assert again.status_code == 409
        assert again.json()["error"]["code"] == "TRIP_INVALID_TRANSITION"
```

- [ ] **Step 2: 실행**

Run: `cd backend && uv run pytest tests/test_apikey_auth.py -v`
Expected: all passed (구현은 이미 끝났고, 이 태스크는 계약을 고정한다)

- [ ] **Step 3: 전체 회귀**

Run: `cd backend && uv run pytest -q`
Expected: 전부 passed

- [ ] **Step 4: 커밋**

```bash
git add backend/tests/test_apikey_auth.py
git commit -m "test(api-keys): pin JWT/API-key parity for the same scenario"
```

---

## Task 13: OpenAPI 정리

**Files:**
- Create: `backend/app/openapi.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_openapi.py`

- [ ] **Step 1: 실패하는 테스트를 쓴다**

`backend/tests/test_openapi.py`:

```python
"""/docs가 Agent 개발자에게 실제로 쓸모 있어야 한다."""


async def test_both_auth_schemes_are_documented(client):
    schema = (await client.get("/openapi.json")).json()
    schemes = schema["components"]["securitySchemes"]

    assert schemes["BearerAuth"] == {"type": "http", "scheme": "bearer", "bearerFormat": "JWT"}
    assert schemes["ApiKeyAuth"] == {"type": "apiKey", "in": "header", "name": "X-API-Key"}


async def test_protected_operations_declare_both_schemes(client):
    schema = (await client.get("/openapi.json")).json()
    operation = schema["paths"]["/api/v1/trips"]["get"]
    names = {name for entry in operation["security"] for name in entry}
    assert names == {"BearerAuth", "ApiKeyAuth"}


async def test_login_is_not_marked_as_protected(client):
    schema = (await client.get("/openapi.json")).json()
    assert "security" not in schema["paths"]["/api/v1/auth/login"]["post"]


async def test_required_scope_is_written_into_the_description(client):
    schema = (await client.get("/openapi.json")).json()
    assert "`trips:write`" in schema["paths"]["/api/v1/trips"]["post"]["description"]
    assert "`trips:read`" in schema["paths"]["/api/v1/trips"]["get"]["description"]


async def test_scopeless_endpoints_say_so(client):
    schema = (await client.get("/openapi.json")).json()
    assert "스코프 불필요" in schema["paths"]["/api/v1/codes"]["get"]["description"]


async def test_jwt_only_endpoints_are_marked(client):
    schema = (await client.get("/openapi.json")).json()
    description = schema["paths"]["/api/v1/api-keys"]["post"]["description"]
    assert "로그인 세션 전용" in description
```

- [ ] **Step 2: 실패를 확인한다**

Run: `cd backend && uv run pytest tests/test_openapi.py -v`
Expected: FAIL — `KeyError: 'securitySchemes'`

- [ ] **Step 3: 구현**

`backend/app/openapi.py`:

```python
"""OpenAPI 스키마 보강.

FastAPI 기본 스키마에는 인증 방식과 필요 스코프가 없다. `/docs`만 보고 Agent를 붙일 수
있어야 하므로 두 가지를 주입한다.
1. securitySchemes 2종 (JWT / X-API-Key)
2. 각 오퍼레이션 설명에 필요 스코프 한 줄

설명은 `SCOPE_REQUIREMENTS`에서 뽑는다 — 손으로 적으면 표와 어긋난다.
"""

from fastapi import FastAPI
from fastapi.openapi.utils import get_openapi

from app.services.api_scopes import SCOPE_REQUIREMENTS

_SECURITY_SCHEMES = {
    "BearerAuth": {"type": "http", "scheme": "bearer", "bearerFormat": "JWT"},
    "ApiKeyAuth": {"type": "apiKey", "in": "header", "name": "X-API-Key"},
}

_SECURITY = [{"BearerAuth": []}, {"ApiKeyAuth": []}]

#: JWT 전용 경로. API Key로는 열리지 않는다 (키가 키를 낳지 못하게).
_JWT_ONLY_PREFIX = "/api/v1/api-keys"

_DESCRIPTION = """\
SK온 출장시스템 데모 API.

**웹 UI와 외부 Agent가 물리적으로 같은 엔드포인트를 씁니다.** 화면에서 하는 일은
전부 이 API로 할 수 있습니다.

## 인증

- 브라우저: `Authorization: Bearer <JWT>` — 로그인 시 발급, 8시간 만료
- Agent: `X-API-Key: sk_live_...` — `/settings/api-keys`에서 발급, 키의 스코프만큼만 허용

두 헤더가 함께 오면 `X-API-Key`가 우선합니다.

## 에러

모든 에러 응답이 같은 모양입니다.

```json
{"error": {"code": "TRIP_INVALID_TRANSITION", "message": "...", "field": null}}
```

`code`는 기계가 읽는 도메인 코드입니다. 409의 `code`를 보고 재시도 여부를 판단하세요.
"""


def build_openapi(app: FastAPI):
    def custom_openapi():
        if app.openapi_schema:
            return app.openapi_schema

        schema = get_openapi(
            title=app.title,
            version=app.version,
            description=_DESCRIPTION,
            routes=app.routes,
        )
        schema.setdefault("components", {})["securitySchemes"] = _SECURITY_SCHEMES

        for (method, path), scope in SCOPE_REQUIREMENTS.items():
            operation = schema.get("paths", {}).get(path, {}).get(method.lower())
            if operation is None:  # pragma: no cover - 소진 가드가 먼저 잡는다
                continue
            operation["security"] = _SECURITY
            if scope is None:
                note = "**스코프 불필요** — 인증만 하면 호출할 수 있습니다."
            else:
                note = f"**필요 스코프**: `{scope}`"
            if path.startswith(_JWT_ONLY_PREFIX):
                note = "**로그인 세션 전용** — API Key로는 호출할 수 없습니다."
            existing = operation.get("description", "")
            operation["description"] = f"{existing}\n\n{note}".strip()

        app.openapi_schema = schema
        return schema

    return custom_openapi
```

`backend/app/main.py`: `assert_scope_table_complete(app)` 다음 줄에 추가한다.

```python
from app.openapi import build_openapi

...
assert_scope_table_complete(app)
app.openapi = build_openapi(app)
```

- [ ] **Step 4: 통과를 확인한다**

Run: `cd backend && uv run pytest tests/test_openapi.py -v`
Expected: 6 passed

- [ ] **Step 5: 전체 회귀**

Run: `cd backend && uv run pytest -q`
Expected: 전부 passed

- [ ] **Step 6: 커밋**

```bash
git add backend/app/openapi.py backend/app/main.py backend/tests/test_openapi.py
git commit -m "docs(api): document auth schemes and required scopes in OpenAPI"
```

---

## Task 14: 프론트 타입과 API 클라이언트

**Files:**
- Modify: `frontend/src/lib/api/types.ts`
- Create: `frontend/src/lib/api/api-keys.ts`
- Create: `frontend/src/lib/api/meta.ts`

- [ ] **Step 1: 타입을 추가한다**

`frontend/src/lib/api/types.ts` 끝에 추가:

```ts
export type ApiKeyScope =
	| 'trips:read'
	| 'trips:write'
	| 'expenses:read'
	| 'expenses:write'
	| 'cards:read'
	| 'admin';

export type ApiKeyState = 'ACTIVE' | 'REVOKED' | 'EXPIRED';

export interface ApiKeySummary {
	id: number;
	name: string;
	key_prefix: string;
	scopes: ApiKeyScope[];
	state: ApiKeyState;
	last_used_at: string | null;
	expires_at: string | null;
	revoked_at: string | null;
	created_at: string;
}

/** 발급 직후에만 존재한다. `key`는 이 응답 이후 어디에서도 다시 얻을 수 없다. */
export interface ApiKeyCreated extends ApiKeySummary {
	key: string;
}

export interface ScopeInfo {
	scope: ApiKeyScope;
	description: string;
	endpoints: string[];
}
```

- [ ] **Step 2: 클라이언트를 만든다**

`frontend/src/lib/api/api-keys.ts`:

```ts
import { authRequest } from '$lib/stores/auth.svelte';
import type { ApiKeyCreated, ApiKeyScope, ApiKeySummary } from './types';

export interface ApiKeyCreateInput {
	name: string;
	scopes: ApiKeyScope[];
	expires_in_days?: number | null;
}

export function listApiKeys(): Promise<ApiKeySummary[]> {
	return authRequest<ApiKeySummary[]>('/api/v1/api-keys');
}

export function createApiKey(input: ApiKeyCreateInput): Promise<ApiKeyCreated> {
	return authRequest<ApiKeyCreated>('/api/v1/api-keys', { method: 'POST', body: input });
}

export function revokeApiKey(id: number): Promise<ApiKeySummary> {
	return authRequest<ApiKeySummary>(`/api/v1/api-keys/${id}/revoke`, { method: 'POST' });
}
```

`frontend/src/lib/api/meta.ts`:

```ts
import { authRequest } from '$lib/stores/auth.svelte';
import type { ScopeInfo } from './types';

export function listScopes(): Promise<ScopeInfo[]> {
	return authRequest<ScopeInfo[]>('/api/v1/scopes');
}
```

- [ ] **Step 3: 타입체크**

Run: `cd frontend && npm run check`
Expected: 0 errors / 0 warnings

- [ ] **Step 4: 커밋**

```bash
git add frontend/src/lib/api/types.ts frontend/src/lib/api/api-keys.ts frontend/src/lib/api/meta.ts
git commit -m "feat(web): add api-key and scope API clients"
```

---

## Task 15: 프론트 순수 모듈 (라벨·curl 스니펫)

**Files:**
- Create: `frontend/src/lib/api-keys.ts`
- Test: `frontend/src/lib/api-keys.test.ts`

- [ ] **Step 1: 실패하는 테스트를 쓴다**

`frontend/src/lib/api-keys.test.ts`:

```ts
import { describe, expect, it } from 'vitest';
import { KEY_STATE_LABELS, KEY_STATE_TONES, SCOPE_LABELS, curlSnippet } from './api-keys';

describe('SCOPE_LABELS', () => {
	it('covers every scope the backend can return', () => {
		expect(Object.keys(SCOPE_LABELS).sort()).toEqual(
			['admin', 'cards:read', 'expenses:read', 'expenses:write', 'trips:read', 'trips:write'].sort()
		);
	});
});

describe('KEY_STATE_*', () => {
	it('covers every state', () => {
		expect(Object.keys(KEY_STATE_LABELS).sort()).toEqual(['ACTIVE', 'EXPIRED', 'REVOKED']);
		expect(Object.keys(KEY_STATE_TONES).sort()).toEqual(['ACTIVE', 'EXPIRED', 'REVOKED']);
	});
});

describe('curlSnippet', () => {
	it('builds a GET snippet with the key header', () => {
		expect(curlSnippet({ method: 'GET', path: '/api/v1/trips?scope=mine' })).toBe(
			[
				'curl -s "$SKON_BASE_URL/api/v1/trips?scope=mine" \\',
				'  -H "X-API-Key: $SKON_API_KEY"'
			].join('\n')
		);
	});

	it('adds the method, content type and body for writes', () => {
		expect(
			curlSnippet({ method: 'POST', path: '/api/v1/trips', body: { title: '울산 공장 점검' } })
		).toBe(
			[
				'curl -s -X POST "$SKON_BASE_URL/api/v1/trips" \\',
				'  -H "X-API-Key: $SKON_API_KEY" \\',
				'  -H "Content-Type: application/json" \\',
				`  -d '${JSON.stringify({ title: '울산 공장 점검' })}'`
			].join('\n')
		);
	});

	it('omits -X for GET so the snippet reads like the docs', () => {
		expect(curlSnippet({ method: 'GET', path: '/api/v1/cards' })).not.toContain('-X GET');
	});
});
```

- [ ] **Step 2: 실패를 확인한다**

Run: `cd frontend && npm test -- --run src/lib/api-keys.test.ts`
Expected: FAIL — `Failed to resolve import "./api-keys"`

- [ ] **Step 3: 구현**

`frontend/src/lib/api-keys.ts`:

```ts
import type { ApiKeyScope, ApiKeyState } from '$lib/api/types';

export const SCOPE_LABELS: Record<ApiKeyScope, string> = {
	'trips:read': '출장 조회',
	'trips:write': '출장 쓰기',
	'expenses:read': '정산 조회',
	'expenses:write': '정산 쓰기',
	'cards:read': '법인카드 조회',
	admin: '관리자 (Phase 5)'
};

/** 발급 폼의 표시 순서. 백엔드 ApiKeyScope 선언 순서와 같게 유지한다. */
export const SCOPE_ORDER: ApiKeyScope[] = [
	'trips:read',
	'trips:write',
	'expenses:read',
	'expenses:write',
	'cards:read',
	'admin'
];

export const KEY_STATE_LABELS: Record<ApiKeyState, string> = {
	ACTIVE: '사용중',
	REVOKED: '폐기됨',
	EXPIRED: '만료됨'
};

/** Badge.svelte의 tone과 그대로 맞춘다. */
export const KEY_STATE_TONES: Record<ApiKeyState, 'neutral' | 'primary' | 'success' | 'danger'> = {
	ACTIVE: 'success',
	REVOKED: 'danger',
	EXPIRED: 'neutral'
};

export const EXPIRY_OPTIONS: { value: string; label: string }[] = [
	{ value: '', label: '만료 없음' },
	{ value: '30', label: '30일' },
	{ value: '90', label: '90일' },
	{ value: '365', label: '365일' }
];

/**
 * `/developers` 가이드의 curl 예제. 셸 변수 두 개(`$SKON_BASE_URL`·`$SKON_API_KEY`)를
 * 쓰므로 사용자가 키를 문서에 붙여넣을 일이 없다.
 */
export function curlSnippet(input: {
	method: 'GET' | 'POST' | 'PATCH' | 'DELETE';
	path: string;
	body?: unknown;
}): string {
	const verb = input.method === 'GET' ? 'curl -s' : `curl -s -X ${input.method}`;
	const lines = [`${verb} "$SKON_BASE_URL${input.path}" \\`, '  -H "X-API-Key: $SKON_API_KEY"'];
	if (input.body !== undefined) {
		lines[lines.length - 1] += ' \\';
		lines.push('  -H "Content-Type: application/json" \\');
		lines.push(`  -d '${JSON.stringify(input.body)}'`);
	}
	return lines.join('\n');
}
```

- [ ] **Step 4: 통과를 확인한다**

Run: `cd frontend && npm test -- --run src/lib/api-keys.test.ts`
Expected: 4 passed

- [ ] **Step 5: 커밋**

```bash
git add frontend/src/lib/api-keys.ts frontend/src/lib/api-keys.test.ts
git commit -m "feat(web): add api-key labels and curl snippet builder"
```

---

## Task 16: `/settings/api-keys` 화면

**Files:**
- Create: `frontend/src/routes/settings/api-keys/+page.svelte`

- [ ] **Step 1: 페이지를 만든다**

`frontend/src/routes/settings/api-keys/+page.svelte`:

```svelte
<script lang="ts">
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import { ApiError } from '$lib/api/client';
	import { createApiKey, listApiKeys, revokeApiKey } from '$lib/api/api-keys';
	import type { ApiKeyCreated, ApiKeyScope, ApiKeySummary } from '$lib/api/types';
	import {
		EXPIRY_OPTIONS,
		KEY_STATE_LABELS,
		KEY_STATE_TONES,
		SCOPE_LABELS,
		SCOPE_ORDER
	} from '$lib/api-keys';
	import { formatDateTime } from '$lib/format';
	import Badge from '$lib/components/Badge.svelte';
	import Button from '$lib/components/Button.svelte';
	import Card from '$lib/components/Card.svelte';
	import EmptyState from '$lib/components/EmptyState.svelte';
	import Select from '$lib/components/Select.svelte';
	import TextInput from '$lib/components/TextInput.svelte';

	let keys = $state<ApiKeySummary[]>([]);
	let loading = $state(true);
	let errorMessage = $state('');

	let name = $state('');
	let selectedScopes = $state<ApiKeyScope[]>([]);
	let expiresInDays = $state('');
	let submitting = $state(false);

	/** 발급 직후 한 번만 보여줄 평문. 이 화면을 떠나면 영영 못 본다. */
	let issued = $state<ApiKeyCreated | null>(null);
	let copyNotice = $state('');
	let keyInput = $state<HTMLInputElement | null>(null);
	let confirmingId = $state<number | null>(null);

	onMount(load);

	async function load(): Promise<void> {
		loading = true;
		try {
			keys = await listApiKeys();
			errorMessage = '';
		} catch (error) {
			errorMessage = error instanceof ApiError ? error.message : '키를 불러오지 못했습니다';
		} finally {
			loading = false;
		}
	}

	function toggleScope(scope: ApiKeyScope): void {
		selectedScopes = selectedScopes.includes(scope)
			? selectedScopes.filter((item) => item !== scope)
			: [...selectedScopes, scope];
	}

	async function handleSubmit(event: SubmitEvent): Promise<void> {
		event.preventDefault();
		// 버튼 disabled만으로는 form.requestSubmit() 경로를 막지 못한다. 발급은 멱등하지 않다.
		if (submitting) return;
		submitting = true;
		errorMessage = '';
		copyNotice = '';
		try {
			issued = await createApiKey({
				name,
				scopes: selectedScopes,
				expires_in_days: expiresInDays ? Number(expiresInDays) : null
			});
			name = '';
			selectedScopes = [];
			expiresInDays = '';
			await load();
		} catch (error) {
			errorMessage = error instanceof ApiError ? error.message : '발급에 실패했습니다';
		} finally {
			submitting = false;
		}
	}

	/**
	 * 운영은 평문 HTTP라 SecureContext가 아니다 — `navigator.clipboard`는 아예 없을 수 있다.
	 * 있으면 쓰고, 없으면 선택 + execCommand로 떨어지고, 그것도 실패하면 직접 복사하라고 말한다.
	 * localhost에서는 첫 경로가 항상 성공하므로 이 폴백은 배포 후에야 검증된다.
	 */
	async function copyKey(): Promise<void> {
		const value = issued?.key ?? '';
		if (!value) return;
		try {
			if (navigator.clipboard?.writeText) {
				await navigator.clipboard.writeText(value);
				copyNotice = '복사했습니다';
				return;
			}
		} catch {
			// 폴백으로 넘어간다
		}
		keyInput?.select();
		const copied = document.execCommand?.('copy');
		copyNotice = copied ? '복사했습니다' : '직접 선택해 복사하세요';
	}

	async function revoke(id: number): Promise<void> {
		try {
			await revokeApiKey(id);
			confirmingId = null;
			if (issued?.id === id) issued = null;
			await load();
		} catch (error) {
			errorMessage = error instanceof ApiError ? error.message : '폐기에 실패했습니다';
		}
	}
</script>

<div class="flex items-center justify-between">
	<h1 class="text-display-xl">API 키</h1>
	<!-- 전체 새로고침(window.location)을 쓰지 않는다 — 인증 스토어가 restore를 다시 돌아야 한다. -->
	<Button variant="secondary" onclick={() => goto('/developers')}>개발자 가이드</Button>
</div>

<p class="mt-4 text-body-md text-muted">
	여기서 발급한 키로 외부 Agent가 웹 화면과 <strong>같은 엔드포인트</strong>를 호출합니다. 키의 권한은
	선택한 스코프까지만입니다.
</p>

{#if issued}
	<div class="mt-8 rounded-md border-2 border-primary p-6">
		<h2 class="text-title-md">발급된 키 — 지금 복사하세요</h2>
		<p class="mt-2 text-body-sm text-error">
			이 값은 <strong>다시 볼 수 없습니다.</strong> 서버에는 해시만 저장되며, 잃어버리면 새 키를 발급해야
			합니다.
		</p>
		<div class="mt-4 flex gap-3">
			<input
				bind:this={keyInput}
				value={issued.key}
				readonly
				aria-label="발급된 API 키"
				class="h-14 flex-1 rounded-sm border border-hairline bg-surface-soft px-3 font-mono text-body-sm text-ink"
			/>
			<Button onclick={copyKey}>복사</Button>
			<Button variant="secondary" onclick={() => (issued = null)}>닫기</Button>
		</div>
		{#if copyNotice}
			<p class="mt-2 text-body-sm text-muted" role="status">{copyNotice}</p>
		{/if}
	</div>
{/if}

<Card>
	<form onsubmit={handleSubmit} class="mt-0">
		<h2 class="text-title-md">새 키 발급</h2>
		<div class="mt-4 grid grid-cols-1 gap-4 md:grid-cols-2">
			<TextInput label="이름" bind:value={name} placeholder="정산 자동화 Agent" />
			<Select label="만료" bind:value={expiresInDays} options={EXPIRY_OPTIONS} placeholder="만료 없음" />
		</div>
		<fieldset class="mt-6">
			<legend class="text-caption text-muted">스코프</legend>
			<div class="mt-2 grid grid-cols-1 gap-2 md:grid-cols-3">
				{#each SCOPE_ORDER as scope (scope)}
					<label class="flex items-center gap-2 text-body-sm text-ink">
						<input
							type="checkbox"
							class="h-4 w-4"
							checked={selectedScopes.includes(scope)}
							onchange={() => toggleScope(scope)}
						/>
						<span class="font-mono text-body-sm">{scope}</span>
						<span class="text-muted">{SCOPE_LABELS[scope]}</span>
					</label>
				{/each}
			</div>
		</fieldset>
		<div class="mt-6">
			<Button type="submit" disabled={submitting || !name || selectedScopes.length === 0}>
				{submitting ? '발급 중…' : '발급'}
			</Button>
		</div>
	</form>
</Card>

{#if errorMessage}
	<p class="mt-6 text-body-sm text-error" role="alert">{errorMessage}</p>
{/if}

<h2 class="mt-12 text-title-md">발급된 키</h2>
{#if loading}
	<p class="mt-4 text-body-sm text-muted">불러오는 중…</p>
{:else if keys.length === 0}
	<EmptyState title="발급된 키가 없습니다" description="위에서 첫 키를 발급하세요." />
{:else}
	<table class="mt-4 w-full border-collapse">
		<thead>
			<tr class="border-b border-hairline text-left text-caption text-muted">
				<th class="py-3">이름</th>
				<th class="py-3">키</th>
				<th class="py-3">스코프</th>
				<th class="py-3">상태</th>
				<th class="py-3">마지막 사용</th>
				<th class="py-3">만료</th>
				<th class="py-3"></th>
			</tr>
		</thead>
		<tbody>
			{#each keys as key (key.id)}
				<tr class="border-b border-hairline">
					<td class="py-3 text-body-sm text-ink">{key.name}</td>
					<td class="py-3 font-mono text-body-sm text-muted">{key.key_prefix}…</td>
					<td class="py-3 text-body-sm text-muted">{key.scopes.join(', ')}</td>
					<td class="py-3">
						<Badge tone={KEY_STATE_TONES[key.state]}>{KEY_STATE_LABELS[key.state]}</Badge>
					</td>
					<td class="py-3 text-body-sm text-muted">
						{key.last_used_at ? formatDateTime(key.last_used_at) : '없음'}
					</td>
					<td class="py-3 text-body-sm text-muted">
						{key.expires_at ? formatDateTime(key.expires_at) : '없음'}
					</td>
					<td class="py-3 text-right">
						{#if key.state === 'ACTIVE'}
							{#if confirmingId === key.id}
								<Button variant="tertiary" onclick={() => revoke(key.id)}>정말 폐기</Button>
								<Button variant="tertiary" onclick={() => (confirmingId = null)}>취소</Button>
							{:else}
								<Button variant="tertiary" onclick={() => (confirmingId = key.id)}>폐기</Button>
							{/if}
						{/if}
					</td>
				</tr>
			{/each}
		</tbody>
	</table>
{/if}
```

`Badge.svelte`는 `tone`(`neutral|primary|success|danger`)과 children을, `EmptyState.svelte`는 `title`·`description`·`action`을 받는다 — 위 코드가 쓰는 것과 같다.

- [ ] **Step 2: 타입체크**

Run: `cd frontend && npm run check`
Expected: 0 errors / 0 warnings

- [ ] **Step 3: 개발 서버에서 눈으로 확인한다**

```bash
cd backend && uv run uvicorn app.main:app --reload --port 8000    # 터미널 1
cd frontend && npm run dev                                        # 터미널 2
```

`http://localhost:5173/settings/api-keys`에서 발급 → 평문 1회 노출 → 목록 반영 → 폐기 → 상태가 `폐기됨`으로 바뀌는지 확인한다.

- [ ] **Step 4: 커밋**

```bash
git add frontend/src/routes/settings/api-keys/+page.svelte
git commit -m "feat(web): add API key management screen"
```

---

## Task 17: `/developers` 가이드

`AppShell`의 가운데 탭에 이미 링크가 있고 지금은 404다. 이 태스크가 그걸 채운다.

**Files:**
- Create: `frontend/src/routes/developers/+page.svelte`

- [ ] **Step 1: 페이지를 만든다**

`frontend/src/routes/developers/+page.svelte`:

```svelte
<script lang="ts">
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import { ApiError } from '$lib/api/client';
	import { listScopes } from '$lib/api/meta';
	import type { ScopeInfo } from '$lib/api/types';
	import { curlSnippet } from '$lib/api-keys';
	import Button from '$lib/components/Button.svelte';
	import Card from '$lib/components/Card.svelte';

	let scopes = $state<ScopeInfo[]>([]);
	let errorMessage = $state('');

	// 스코프 표를 화면에 하드코딩하지 않는다 — 백엔드의 SCOPE_REQUIREMENTS에서 뽑아
	// 내려주므로 코드와 문서가 어긋날 수 없다.
	onMount(async () => {
		try {
			scopes = await listScopes();
		} catch (error) {
			errorMessage = error instanceof ApiError ? error.message : '스코프를 불러오지 못했습니다';
		}
	});

	const examples = [
		{
			title: '1. 내 출장 목록',
			snippet: curlSnippet({ method: 'GET', path: '/api/v1/trips?scope=mine&status=DRAFT' }),
			scope: 'trips:read'
		},
		{
			title: '2. 출장 신청',
			snippet: curlSnippet({
				method: 'POST',
				path: '/api/v1/trips',
				// 코드값은 /api/v1/codes가 내려주는 실제 값이다. 가짜 값을 예제에 쓰면
				// 그대로 복사한 사용자가 400 INVALID_CODE를 만난다.
				body: {
					title: '울산 공장 점검',
					purpose_code: 'CUSTOMER',
					purpose_detail: '라인 점검 및 협력사 미팅',
					destination_type_code: 'DOMESTIC',
					country_code: 'KR',
					city: '울산',
					start_date: '2026-09-01',
					end_date: '2026-09-02',
					transport_code: 'AIR',
					accommodation_code: 'HOTEL',
					cost_center_code: 'CC2100',
					estimated_cost: '300000'
				}
			}),
			scope: 'trips:write'
		},
		{
			title: '3. 상신',
			snippet: curlSnippet({ method: 'POST', path: '/api/v1/trips/41/submit' }),
			scope: 'trips:write'
		},
		{
			title: '4. 정산서 생성 후 카드거래 자동매칭 후보 조회',
			snippet: curlSnippet({ method: 'GET', path: '/api/v1/expenses/13/match-candidates' }),
			scope: 'expenses:read'
		},
		{
			title: '5. 정산 항목 담기',
			snippet: curlSnippet({
				method: 'POST',
				path: '/api/v1/expenses/13/items',
				body: { card_transaction_id: 512, expense_type_code: 'MEAL' }
			}),
			scope: 'expenses:write'
		}
	];
</script>

<h1 class="text-display-xl">개발자 가이드</h1>
<p class="mt-4 max-w-[720px] text-body-md text-muted">
	이 시스템의 웹 화면은 공개 API 위에 그려져 있습니다. <strong>사람이 화면에서 하는 일과 똑같은 일을
	AI Agent가 API Key로 수행할 수 있습니다</strong> — 별도의 Agent 전용 엔드포인트는 없습니다.
</p>

<div class="mt-8 flex gap-3">
	<Button onclick={() => goto('/settings/api-keys')}>API 키 발급</Button>
	<Button variant="secondary" onclick={() => window.open('/docs', '_blank')}>
		OpenAPI 문서 (/docs)
	</Button>
</div>

<h2 class="mt-12 text-display-sm">1. 인증</h2>
<Card>
	<p class="text-body-md text-ink">
		모든 요청에 <code class="font-mono">X-API-Key</code> 헤더를 붙입니다. 브라우저는
		<code class="font-mono">Authorization: Bearer &lt;JWT&gt;</code>를 쓰며, 두 헤더가 함께 오면 API
		Key가 우선합니다.
	</p>
	<pre class="mt-4 overflow-x-auto rounded-sm bg-surface-soft p-4 font-mono text-body-sm text-ink">export SKON_BASE_URL=http://localhost
export SKON_API_KEY=sk_live_...</pre>
</Card>

<h2 class="mt-12 text-display-sm">2. 스코프</h2>
{#if errorMessage}
	<p class="mt-4 text-body-sm text-error" role="alert">{errorMessage}</p>
{:else}
	<table class="mt-4 w-full border-collapse">
		<thead>
			<tr class="border-b border-hairline text-left text-caption text-muted">
				<th class="py-3">스코프</th>
				<th class="py-3">설명</th>
				<th class="py-3">엔드포인트</th>
			</tr>
		</thead>
		<tbody>
			{#each scopes as info (info.scope)}
				<tr class="border-b border-hairline align-top">
					<td class="py-3 font-mono text-body-sm text-ink">{info.scope}</td>
					<td class="py-3 text-body-sm text-muted">{info.description}</td>
					<td class="py-3 font-mono text-body-sm text-muted">
						{#if info.endpoints.length === 0}
							—
						{:else}
							{#each info.endpoints as endpoint (endpoint)}
								<div>{endpoint}</div>
							{/each}
						{/if}
					</td>
				</tr>
			{/each}
		</tbody>
	</table>
	<p class="mt-3 text-body-sm text-muted">
		표에 없는 엔드포인트(<code class="font-mono">/auth/me</code>,
		<code class="font-mono">/codes</code>, <code class="font-mono">/fund-centers</code>,
		<code class="font-mono">/cost-centers</code>, <code class="font-mono">/notifications</code>,
		<code class="font-mono">/scopes</code>)는 인증만 하면 호출할 수 있습니다.
		<code class="font-mono">/api-keys</code>는 로그인 세션 전용이라 API Key로 새 키를 만들 수 없습니다.
	</p>
{/if}

<h2 class="mt-12 text-display-sm">3. 시나리오</h2>
<div class="mt-4 flex flex-col gap-6">
	{#each examples as example (example.title)}
		<Card>
			<div class="flex items-baseline justify-between">
				<h3 class="text-title-md">{example.title}</h3>
				<span class="font-mono text-body-sm text-muted">{example.scope}</span>
			</div>
			<pre
				class="mt-3 overflow-x-auto rounded-sm bg-surface-soft p-4 font-mono text-body-sm text-ink">{example.snippet}</pre>
		</Card>
	{/each}
</div>

<h2 class="mt-12 text-display-sm">4. 에러 처리</h2>
<Card>
	<p class="text-body-md text-ink">모든 에러 응답이 같은 모양입니다.</p>
	<pre class="mt-3 overflow-x-auto rounded-sm bg-surface-soft p-4 font-mono text-body-sm text-ink">{JSON.stringify(
			{ error: { code: 'TRIP_INVALID_TRANSITION', message: '이미 상신된 출장입니다', field: null } },
			null,
			2
		)}</pre>
	<table class="mt-4 w-full border-collapse">
		<tbody>
			{#each [['400', '입력 검증 실패 — field에 문제 필드가 담깁니다'], ['401', '인증 실패 — 키 없음·폐기(API_KEY_REVOKED)·만료(API_KEY_EXPIRED)'], ['403', '스코프 부족 — SCOPE_REQUIRED. 메시지에 필요한 스코프가 있습니다'], ['404', '리소스 없음 — 타인 리소스 접근도 404입니다'], ['409', '상태전이 위반 — code를 보고 재시도 여부를 판단하세요'], ['422', '스키마 위반 — SCHEMA_INVALID']] as [code, meaning] (code)}
				<tr class="border-b border-hairline">
					<td class="w-16 py-2 font-mono text-body-sm text-ink">{code}</td>
					<td class="py-2 text-body-sm text-muted">{meaning}</td>
				</tr>
			{/each}
		</tbody>
	</table>
</Card>
```

`app.css`가 정의하는 타이포 유틸리티는 `text-display-xl|lg|md|sm` · `text-rating` · `text-title-md|sm` · `text-body-md|sm` · `text-caption|caption-sm` · `text-badge` · `text-nav-link` · `text-button-md|sm` **뿐이다**. `text-title-lg`는 없으므로 h2에는 `text-display-sm`을 쓴다. **`text-body`는 쓰지 않는다** — `--color-body` 때문에 색상 유틸리티로 잡히고 조용히 틀린다.

- [ ] **Step 2: 타입체크**

Run: `cd frontend && npm run check`
Expected: 0 errors / 0 warnings

- [ ] **Step 3: 눈으로 확인한다**

`http://localhost:5173/developers` — 스코프 표가 API에서 채워지고, 헤더 가운데 "개발자" 탭이 활성으로 표시되는지 본다.

- [ ] **Step 4: 커밋**

```bash
git add frontend/src/routes/developers/+page.svelte
git commit -m "feat(web): add /developers API guide"
```

---

## Task 18: 프론트 전체 검증

**Files:** 없음 (검증만)

- [ ] **Step 1: 테스트**

Run: `cd frontend && npm test`
Expected: 기존 55건 + 신규 4건 = 59건 passed

- [ ] **Step 2: 타입체크**

Run: `cd frontend && npm run check`
Expected: `0 errors / 0 warnings`

- [ ] **Step 3: 빌드**

Run: `cd frontend && npm run build`
Expected: 성공

- [ ] **Step 4: 백엔드 전체**

Run: `cd backend && uv run pytest -q`
Expected: 전부 passed

- [ ] **Step 5: 커밋 (변경이 있었다면)**

```bash
git add -A frontend backend
git commit -m "chore: green typecheck, tests and build for phase 4"
```

---

## Task 19: 실서버 curl 검증 (Agent 경로 실측)

Phase 2·3과 같은 방식으로, **Agent가 밟을 경로를 사람이 그대로 밟는다.** 여기서 나온 실측값을 `docs/phase-status.md`에 적는다.

**Files:** 없음 (검증만). 결과는 Task 21에서 문서화한다.

- [ ] **Step 1: 서버를 띄운다**

```bash
cd backend && uv run uvicorn app.main:app --reload --port 8000
```

- [ ] **Step 2: 로그인해서 JWT를 얻고 키를 발급한다**

```bash
export SKON_BASE_URL=http://localhost:8000
TOKEN=$(curl -s -X POST "$SKON_BASE_URL/api/v1/auth/login" \
  -H "Content-Type: application/json" \
  -d '{"email":"user1@skon.example","password":"skon1234!"}' | python3 -c 'import json,sys;print(json.load(sys.stdin)["access_token"])')

curl -s -X POST "$SKON_BASE_URL/api/v1/api-keys" \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"name":"검증용 Agent","scopes":["trips:read","trips:write"]}'
```

Expected: 201, 바디에 `key`가 `sk_live_`로 시작하는 40자.

```bash
export SKON_API_KEY=sk_live_...   # 위 응답의 key
```

- [ ] **Step 3: 키가 웹과 같은 엔드포인트를 여는지 본다**

```bash
curl -s "$SKON_BASE_URL/api/v1/trips?scope=mine&size=3" -H "X-API-Key: $SKON_API_KEY"
curl -s "$SKON_BASE_URL/api/v1/auth/me" -H "X-API-Key: $SKON_API_KEY"
```

Expected: 200, `/auth/me`가 키 소유자(user1)를 돌려준다.

- [ ] **Step 4: 스코프 부족을 확인한다**

```bash
curl -s -o /dev/null -w '%{http_code}\n' "$SKON_BASE_URL/api/v1/cards" -H "X-API-Key: $SKON_API_KEY"
curl -s "$SKON_BASE_URL/api/v1/cards" -H "X-API-Key: $SKON_API_KEY"
```

Expected: `403`, 바디 `{"error":{"code":"SCOPE_REQUIRED","message":"이 요청에는 cards:read 스코프가 필요합니다","field":null}}`

- [ ] **Step 5: 쓰기 전체 흐름을 키로 수행한다**

```bash
curl -s -X POST "$SKON_BASE_URL/api/v1/trips" \
  -H "X-API-Key: $SKON_API_KEY" -H "Content-Type: application/json" \
  -d '{"title":"키로 만든 출장","purpose_code":"CUSTOMER","purpose_detail":"라인 점검","destination_type_code":"DOMESTIC","country_code":"KR","city":"울산","start_date":"2026-09-01","end_date":"2026-09-02","transport_code":"AIR","accommodation_code":"HOTEL","cost_center_code":"CC2100","estimated_cost":"300000"}'
# 위 응답의 id로
curl -s -X POST "$SKON_BASE_URL/api/v1/trips/<ID>/submit" -H "X-API-Key: $SKON_API_KEY"
curl -s "$SKON_BASE_URL/api/v1/trips/<ID>/timeline" -H "X-API-Key: $SKON_API_KEY"
```

Expected: 201 → 200(`SUBMITTED`) → 타임라인 `CREATED`·`SUBMITTED`. **웹으로 만든 출장과 구분되지 않는다**는 것이 요점이다.

- [ ] **Step 6: 키 관리가 JWT 전용인지 확인한다**

```bash
curl -s -X POST "$SKON_BASE_URL/api/v1/api-keys" \
  -H "X-API-Key: $SKON_API_KEY" -H "Content-Type: application/json" \
  -d '{"name":"키로 만든 키","scopes":["admin"]}'
```

Expected: 403 `API_KEY_FORBIDDEN`

- [ ] **Step 7: `last_used_at`이 움직이는지 확인한다**

```bash
curl -s "$SKON_BASE_URL/api/v1/api-keys" -H "Authorization: Bearer $TOKEN"
```

Expected: 방금 쓴 키의 `last_used_at`이 채워져 있다.

- [ ] **Step 8: 폐기 후 401을 확인한다**

```bash
curl -s -X POST "$SKON_BASE_URL/api/v1/api-keys/<KEY_ID>/revoke" -H "Authorization: Bearer $TOKEN"
curl -s "$SKON_BASE_URL/api/v1/trips" -H "X-API-Key: $SKON_API_KEY"
```

Expected: 200(`state: "REVOKED"`) → 401 `API_KEY_REVOKED`

- [ ] **Step 9: OpenAPI를 눈으로 확인한다**

`http://localhost:8000/docs`에서 우상단 Authorize에 `BearerAuth`·`ApiKeyAuth` 두 항목이 있고, `POST /api/v1/trips` 설명에 **필요 스코프: `trips:write`**가 보이는지 확인한다.

- [ ] **Step 10: 실측 결과를 메모해 둔다** (Task 21에서 `phase-status.md`에 옮긴다)

---

## Task 20: 브라우저 수동 시나리오

Phase 4 신규분만 여기서 확인한다. Phase 2·3에서 이월된 14개는 여전히 미확인이며 그 사실을 Task 21에서 갱신한다.

**Files:** 없음 (검증만)

- [ ] **Step 1: 발급 흐름**

`/developers` → "API 키 발급" 버튼 → `/settings/api-keys`로 이동한다.

- [ ] **Step 2: 평문 1회 노출**

이름 + 스코프 2개를 골라 발급 → 상단에 평문 키 박스가 뜨고 경고 문구가 보인다. "닫기" 후 **다시 열 방법이 없다**(목록에는 접두어만).

- [ ] **Step 3: 복사 폴백**

"복사" 버튼 → `복사했습니다`. 운영(평문 HTTP)에서도 같은지 확인한다 — `navigator.clipboard`가 없으므로 `execCommand` 경로를 탄다. localhost에서는 이 폴백이 검증되지 않는다.

- [ ] **Step 4: 중복 제출 가드**

발급 버튼을 빠르게 두 번 누르거나 이름 입력창에서 Enter를 연타한다 → 키가 하나만 생긴다.

- [ ] **Step 5: 스코프 미선택**

이름만 넣고 발급 시도 → 버튼이 비활성. 서버측 가드는 `SCOPES_REQUIRED` 테스트가 지킨다.

- [ ] **Step 6: 폐기 2단계**

"폐기" → "정말 폐기" → 상태가 `폐기됨`으로 바뀌고 폐기 버튼이 사라진다.

- [ ] **Step 7: 스코프 표 동기화**

`/developers`의 스코프 표가 API 응답으로 채워지는지, `admin` 행의 엔드포인트가 `—`인지 확인한다.

- [ ] **Step 8: 헤더 탭**

`/developers`에서 가운데 "개발자" 탭에 밑줄이 생긴다 (더 이상 404가 아니다).

- [ ] **Step 9: 전역 401**

개발자 도구에서 `localStorage.removeItem('skon.token')` 후 `/settings/api-keys`를 새로고침 → 로그인으로 튕기고 `redirect` 쿼리에 원래 경로가 보존된다.

---

## Task 21: 문서 갱신

**Files:**
- Modify: `docs/phase-status.md`
- Modify: `CLAUDE.md`

- [ ] **Step 1: `docs/phase-status.md`를 갱신한다**

- 표에서 Phase 4를 **완료**로, Phase 5를 "다음"으로 바꾼다.
- 상단 "기준"을 `Phase 4 (개발자) 완료 시점`으로, Phase 4 계획 링크를 추가한다.
- 테스트 건수를 실제 수치로 갱신한다 (`cd backend && uv run pytest -q | tail -1`, `cd frontend && npm test`).
- "Phase 4 — 완료" 절을 추가한다. 최소한 다음을 담는다:
  - 서비스 계층 표 (`api_scopes.py` · `api_keys.py`)
  - API 표 (`GET|POST /api/v1/api-keys` · `POST /api/v1/api-keys/{id}/revoke` · `GET /api/v1/scopes`)
  - 프론트 (`/settings/api-keys` · `/developers` · `lib/api-keys.ts`)
  - 확정한 설계 결정 표 (이 계획의 "확정한 설계 결정"을 결과 기준으로 옮긴다)
  - Task 19의 curl 실측 결과 (에러 코드 실측 포함: `SCOPE_REQUIRED` · `API_KEY_FORBIDDEN` · `API_KEY_REVOKED` · `API_KEY_EXPIRED` · `INVALID_SCOPE`)
  - mutation 검증 목록 (센티널 비교, 스코프 표 소진 가드, 폐기·만료 판정, 소유자 조건, 활성 개수 조건)
- "Phase 3에서 넘어온 항목" 절을 "Phase 4에서 넘어온 항목"으로 갱신한다. **Phase 4에서 처리하지 않은 것들을 그대로 남긴다**:
  - 출장 상세의 정산서 존재 확인이 `size=100` 목록 조회
  - 항목 FC/CC override가 마스터 비활성화 시 재검증되지 않음
  - `q`의 LIKE 와일드카드 미이스케이프
  - `next_trip_no`·`next_report_no`의 `max()+1`
  - 매칭 후보 조회 페이징 없음
  - 브라우저 수동 시나리오 14개 미확인 (Phase 4 신규 9개는 Task 20에서 확인)
  - 반응형 미구현 — Phase 4에서 `/settings/api-keys`·`/developers` 2개가 늘었다 (표가 넓어 좁은 화면에서 가로 스크롤 필요)
- Phase 4 신규 이월 항목을 추가한다:
  - **`last_used_at`을 매 요청 갱신한다.** 요청당 UPDATE + COMMIT 1회. 데모 규모에서는 문제없지만 트래픽이 늘면 60초 스로틀이나 배치 갱신으로 옮긴다.
  - **`admin` 스코프에 엔드포인트가 없다.** Phase 5에서 `/admin/*`을 만들면 `SCOPE_REQUIREMENTS`에 `ApiKeyScope.ADMIN`으로 등록해야 하며, 등록하지 않으면 기동이 실패한다(가드가 잡는다).
  - **키 발급·폐기는 `activity_log`에 남지 않는다.** `EntityType`이 `TRIP|EXPENSE_REPORT`뿐이라 새 멤버가 필요하고 spec에 없다. 감사 요구가 생기면 그때 넣는다.
  - **rate limit·IP 제한 없음** (spec 7이 명시적으로 범위 밖).

- [ ] **Step 2: `CLAUDE.md`를 갱신한다**

- 상단 문장을 `Phase 1~4 완료. 다음은 Phase 5(운영).`로 바꾼다.
- "반드시 지킬 것"에 스코프 규칙을 추가한다:

```markdown
**스코프 검사는 `get_principal` 안 한 곳에서만 한다.** 엔드포인트마다 `Depends(require_scope(...))`를 붙이는 방식은 쓰지 않는다 — 빠뜨리면 그 엔드포인트만 조용히 전권이 되는 fail-open이다. 필요 스코프는 `app/services/api_scopes.py`의 `SCOPE_REQUIREMENTS` 표가 유일하게 선언하며, `main.py`가 임포트 시점에 `assert_scope_table_complete(app)`로 표와 실제 라우트를 양방향 대조한다. **새 엔드포인트를 만들면 같은 커밋에서 표에 넣어야 하고, 빠뜨리면 앱이 뜨지 않는다.** `request.state.scopes`는 `UNRESTRICTED` 센티널과 **동일성 비교**만 한다 — `if not scopes`로 바꾸면 스코프가 빈 키가 전권을 얻는다.

**키 관리 API는 JWT 전용이다.** `app/deps.py`의 `JwtOnlyUser`를 쓴다. API Key로 새 키를 발급할 수 있으면 `cards:read` 키 하나로 전권 키를 찍어낼 수 있어 스코프 제한 전체가 무의미해진다.

**평문 API Key는 발급 응답에만 존재한다.** DB에는 SHA-256만 남는다. 목록·상세 응답에 `key`를 실으려는 어떤 변경도 거부한다.
```

- "다음 Phase로 넘어간 항목" 절을 Phase 5 기준으로 다시 쓴다 (위 Step 1의 이월 목록 요약).
- 테스트 건수를 갱신한다.

- [ ] **Step 3: 최종 확인**

```bash
cd backend && uv run pytest -q
cd frontend && npm test && npm run check && npm run build
```

Expected: 전부 통과, `0 errors / 0 warnings`

- [ ] **Step 4: 커밋**

```bash
git add docs/phase-status.md CLAUDE.md
git commit -m "docs: record Phase 4 completion and carry-over items"
```

---

## 완료 조건

- [ ] `X-API-Key`로 웹과 **같은 엔드포인트**를 호출할 수 있다 (Task 12·19에서 실측)
- [ ] 스코프가 부족하면 403 `SCOPE_REQUIRED`이고 메시지가 필요한 스코프를 알려준다
- [ ] 스코프 선언을 빠뜨린 라우트가 있으면 **앱이 뜨지 않는다**
- [ ] 평문 키는 발급 응답 1회뿐이고 DB에는 해시만 있다
- [ ] API Key로는 키를 발급할 수 없다 (403 `API_KEY_FORBIDDEN`)
- [ ] 폐기·만료 키는 각각 구분되는 401 코드를 돌려준다
- [ ] `/settings/api-keys`에서 발급·조회·폐기가 되고 평문 1회 경고가 보인다
- [ ] `/developers`의 스코프 표가 백엔드 표에서 채워진다 (하드코딩 아님)
- [ ] `/docs`에 두 인증 방식과 오퍼레이션별 필요 스코프가 문서화돼 있다
- [ ] 백엔드 `pytest` 전부 통과, 프론트 `npm test`·`npm run check`(0/0)·`npm run build` 통과
- [ ] `docs/phase-status.md`·`CLAUDE.md` 갱신
