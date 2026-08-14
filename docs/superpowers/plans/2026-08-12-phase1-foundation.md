# SK온 출장시스템 Phase 1 (기반) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 로컬에서 `docker compose -f docker-compose.dev.yml up -d db` + backend/frontend 실행만으로 로그인이 동작하는 기반 골격을 만든다 — 전체 DB 스키마, 시드 데이터, JWT 인증, DESIGN.md 토큰이 적용된 SvelteKit 셸까지.

**Architecture:** 백엔드는 `routers/` → `services/` → `models/` 3계층. 비즈니스 규칙(코드 검증, 상태전이)은 DB 없는 순수 함수로 `services/`에 고립시켜 단위테스트한다. 프론트는 SvelteKit `adapter-static` SPA이며 DESIGN.md 토큰을 Tailwind v4 `@theme`로 이식한다. 인증은 단일 dependency `get_principal()`이 담당하고, Phase 1에서는 JWT 분기만 구현한다(API Key 분기는 Phase 4).

**Tech Stack:** Python 3.12 / FastAPI / SQLAlchemy 2.0 async / asyncpg / Pydantic v2 / PyJWT / bcrypt / uv · pytest / httpx · SvelteKit 2 / Svelte 5 runes / TailwindCSS v4 / Vite · PostgreSQL 16 · Docker Compose

**Spec:** `docs/superpowers/specs/2026-08-12-skon-biztrip-web-design.md`

---

## File Structure

### Backend (`backend/`)

| 파일 | 책임 |
|---|---|
| `pyproject.toml` | 의존성·도구 설정 |
| `.env.example` | 로컬 환경변수 템플릿 |
| `app/config.py` | `Settings` (pydantic-settings) |
| `app/db.py` | async engine, sessionmaker, `get_db` dependency |
| `app/enums.py` | 상태·역할·스코프 Python Enum (공통코드로 빼지 않는 값) |
| `app/errors.py` | 도메인 예외 + 통일 에러 응답 핸들러 |
| `app/security.py` | bcrypt 해시, JWT 인코드/디코드 |
| `app/deps.py` | `get_principal`, `require_scope` |
| `app/models/base.py` | `Base`, `TimestampMixin` |
| `app/models/org.py` | `Department`, `User` |
| `app/models/code.py` | `CodeGroup`, `Code` |
| `app/models/center.py` | `FundCenter`, `CostCenter` |
| `app/models/trip.py` | `Trip` |
| `app/models/expense.py` | `CorporateCard`, `CardTransaction`, `ExpenseReport`, `ExpenseItem` |
| `app/models/apikey.py` | `ApiKey` |
| `app/models/activity.py` | `Notification`, `ActivityLog` |
| `app/services/codes.py` | `validate_code` (DB 조회 + 순수 검증 분리) |
| `app/services/trip_status.py` | 전이 허용표 + `assert_transition` (순수) |
| `app/routers/auth.py` | `/auth/login`, `/auth/me` |
| `app/schemas/auth.py` | 로그인 요청·응답, `UserOut` |
| `app/seed.py` | 멱등 시드 |
| `app/main.py` | 앱 조립, startup에서 `create_all` + seed |
| `tests/conftest.py` | 테스트 DB 엔진, 트랜잭션 롤백 세션, HTTP 클라이언트 |

### Frontend (`frontend/`)

| 파일 | 책임 |
|---|---|
| `svelte.config.js` | adapter-static |
| `vite.config.ts` | `/api` proxy → `localhost:8000` |
| `src/app.css` | Tailwind v4 `@theme` — DESIGN.md 토큰 이식 |
| `src/lib/api/client.ts` | fetch 래퍼, 토큰 부착, 통일 에러 파싱 |
| `src/lib/stores/auth.svelte.ts` | 로그인 상태 (runes) |
| `src/lib/components/Button.svelte` | `button-primary` / `secondary` / `tertiary` |
| `src/lib/components/TextInput.svelte` | `text-input` 토큰 |
| `src/lib/components/Badge.svelte` | `guest-favorite-badge` 기반 상태 뱃지 |
| `src/lib/components/Card.svelte` | `property-card` 표면 |
| `src/lib/components/AppShell.svelte` | `top-nav` + 3-product tab |
| `src/routes/+layout.ts` | `ssr = false`, `prerender = true` |
| `src/routes/+layout.svelte` | 셸 적용, 인증 가드 |
| `src/routes/login/+page.svelte` | 로그인 |
| `src/routes/+page.svelte` | 대시보드 placeholder |

### Root

`docker-compose.dev.yml` (db 전용) · `README.md`

---

## Task 1: 백엔드 스캐폴드 + health 엔드포인트

**Files:**
- Create: `backend/pyproject.toml`, `backend/app/__init__.py`, `backend/app/main.py`, `backend/tests/__init__.py`, `backend/tests/test_health.py`, `backend/.env.example`, `backend/.python-version`

- [ ] **Step 1: uv 프로젝트 생성**

```bash
mkdir -p backend/app backend/tests
cd backend
uv init --bare --python 3.12
uv add "fastapi>=0.115" "uvicorn[standard]>=0.32" "sqlalchemy[asyncio]>=2.0.36" "asyncpg>=0.30" "pydantic-settings>=2.6" "pyjwt>=2.9" "bcrypt>=4.2"
uv add --dev "pytest>=8.3" "pytest-asyncio>=0.24" "httpx>=0.27"
```

- [ ] **Step 2: pytest 설정 추가**

`backend/pyproject.toml` 끝에 append:

```toml
[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
```

- [ ] **Step 3: 실패하는 테스트 작성**

`backend/tests/test_health.py`:

```python
import httpx

from app.main import app


async def test_health_returns_ok():
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/v1/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
```

빈 파일 생성: `backend/app/__init__.py`, `backend/tests/__init__.py`

- [ ] **Step 4: 테스트 실패 확인**

Run: `cd backend && uv run pytest tests/test_health.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.main'`

- [ ] **Step 5: 최소 구현**

`backend/app/main.py`:

```python
from fastapi import FastAPI

app = FastAPI(title="SK온 출장시스템 API", version="1.0.0", docs_url="/docs")


@app.get("/api/v1/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
```

- [ ] **Step 6: 테스트 통과 확인**

Run: `cd backend && uv run pytest tests/test_health.py -v`
Expected: PASS (1 passed)

- [ ] **Step 7: 커밋**

```bash
git add backend/
git commit -m "feat(backend): scaffold FastAPI app with health endpoint"
```

---

## Task 2: 개발용 DB 컨테이너 + 설정

**Files:**
- Create: `docker-compose.dev.yml`, `backend/app/config.py`, `backend/.env.example`
- Test: `backend/tests/test_config.py`

- [ ] **Step 1: dev compose 작성**

`docker-compose.dev.yml`:

```yaml
services:
  db:
    image: postgres:16-alpine
    container_name: skon-db-dev
    environment:
      POSTGRES_USER: skon
      POSTGRES_PASSWORD: skon
      POSTGRES_DB: skon
    ports:
      - "5432:5432"
    volumes:
      - skon_pgdata_dev:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U skon -d skon"]
      interval: 5s
      timeout: 3s
      retries: 10

volumes:
  skon_pgdata_dev:
```

- [ ] **Step 2: DB 기동 및 테스트 DB 생성**

```bash
docker compose -f docker-compose.dev.yml up -d db
docker exec skon-db-dev psql -U skon -d skon -c "SELECT 1;"
docker exec skon-db-dev psql -U skon -d postgres -c "CREATE DATABASE skon_test OWNER skon;"
```

Expected: `SELECT 1` 이 `1` 반환, `CREATE DATABASE` 성공

- [ ] **Step 3: 실패하는 테스트 작성**

`backend/tests/test_config.py`:

```python
from app.config import Settings


def test_settings_reads_database_url_from_env(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://u:p@h:5432/d")
    monkeypatch.setenv("JWT_SECRET", "s3cret")

    settings = Settings()

    assert settings.database_url == "postgresql+asyncpg://u:p@h:5432/d"
    assert settings.jwt_secret == "s3cret"
    assert settings.jwt_expire_hours == 8
```

- [ ] **Step 4: 테스트 실패 확인**

Run: `cd backend && uv run pytest tests/test_config.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.config'`

- [ ] **Step 5: 구현**

`backend/app/config.py`:

```python
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+asyncpg://skon:skon@localhost:5432/skon"
    jwt_secret: str = "dev-only-insecure-secret"
    jwt_algorithm: str = "HS256"
    jwt_expire_hours: int = 8
    seed_on_startup: bool = True


@lru_cache
def get_settings() -> Settings:
    return Settings()
```

`backend/.env.example`:

```
DATABASE_URL=postgresql+asyncpg://skon:skon@localhost:5432/skon
JWT_SECRET=dev-only-insecure-secret
SEED_ON_STARTUP=true
```

- [ ] **Step 6: 테스트 통과 확인**

Run: `cd backend && uv run pytest tests/test_config.py -v`
Expected: PASS

- [ ] **Step 7: 커밋**

```bash
git add docker-compose.dev.yml backend/
git commit -m "feat: add dev postgres compose and settings"
```

---

## Task 3: DB 세션 + 테스트 픽스처

**Files:**
- Create: `backend/app/db.py`, `backend/app/models/__init__.py`, `backend/app/models/base.py`, `backend/tests/conftest.py`
- Modify: `backend/pyproject.toml` (pytest-asyncio 루프 스코프)
- Test: `backend/tests/test_db.py`

- [ ] **Step 1: 실패하는 테스트 작성**

`backend/tests/test_db.py`:

```python
from sqlalchemy import text


async def test_session_fixture_can_query(db_session):
    result = await db_session.execute(text("SELECT 1"))

    assert result.scalar_one() == 1
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `cd backend && uv run pytest tests/test_db.py -v`
Expected: FAIL — `fixture 'db_session' not found`

- [ ] **Step 3: Base 및 세션 구현**

`backend/app/models/base.py`:

```python
from datetime import datetime

from sqlalchemy import DateTime, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    # eager_defaults=True: SQLAlchemy 2.0 기본값 "auto"는 INSERT에만 RETURNING을 쓴다.
    # 그래서 UPDATE 뒤 server-onupdate 컬럼(updated_at)이 expire 상태로 남고,
    # expire_on_commit=False여도 커밋 후 읽으면 async에서 MissingGreenlet이 난다.
    __mapper_args__ = {"eager_defaults": True}


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
```

`backend/app/models/__init__.py`:

```python
from app.models.base import Base, TimestampMixin

__all__ = ["Base", "TimestampMixin"]
```

`backend/app/db.py`:

```python
from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import get_settings

engine = create_async_engine(get_settings().database_url, echo=False, future=True)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with SessionLocal() as session:
        yield session
```

- [ ] **Step 4: pytest-asyncio 루프 스코프 설정 + conftest 작성**

먼저 `backend/pyproject.toml`의 `[tool.pytest.ini_options]` 블록을 아래로 교체한다.

```toml
[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
asyncio_default_fixture_loop_scope = "session"
asyncio_default_test_loop_scope = "session"
```

**이유:** pytest-asyncio 1.x에서 `asyncio_mode = "auto"`만 지정하면 `asyncio_default_fixture_loop_scope`가 `None`(= function 스코프), `asyncio_default_test_loop_scope`가 `function`으로 떨어진다. 그러면 아래 session 스코프 `test_engine`이 만든 async 엔진이 첫 테스트가 끝날 때 닫히는 이벤트 루프에 묶여, 두 번째 테스트부터 asyncpg/SQLAlchemy가 "attached to a different loop" 계열 오류를 낸다. 실측 결과 두 키를 **모두** `"session"`으로 지정해야 fixture와 test가 같은 루프를 공유한다 (`asyncio_default_fixture_loop_scope`만으로는 불충분).

그다음 `backend/tests/conftest.py`:

```python
from collections.abc import AsyncGenerator

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.db import get_db
from app.main import app
from app.models import Base

TEST_DATABASE_URL = "postgresql+asyncpg://skon:skon@localhost:5432/skon_test"


@pytest.fixture(scope="session")
async def test_engine():
    engine = create_async_engine(TEST_DATABASE_URL, future=True)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest.fixture
async def db_session(test_engine) -> AsyncGenerator[AsyncSession, None]:
    """각 테스트를 외부 트랜잭션 안에서 실행하고 끝나면 롤백한다."""
    connection = await test_engine.connect()
    transaction = await connection.begin()
    session = async_sessionmaker(
        bind=connection, expire_on_commit=False, join_transaction_mode="create_savepoint"
    )()

    try:
        yield session
    finally:
        await session.close()
        await transaction.rollback()
        await connection.close()


@pytest.fixture
async def client(db_session) -> AsyncGenerator[httpx.AsyncClient, None]:
    app.dependency_overrides[get_db] = lambda: db_session
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()
```

**`join_transaction_mode="create_savepoint"`가 왜 필요한가:** 기본값 `"conditional_savepoint"`는 바깥 트랜잭션이 SAVEPOINT가 아닌 평범한 트랜잭션일 때 `"rollback_only"`로 떨어진다. 이 모드에서는 테스트 안의 `session.commit()`은 흡수되지만 `session.rollback()`이 바깥 커넥션 트랜잭션까지 전파되어 픽스처가 들고 있던 `transaction` 객체가 커넥션에서 분리된다. 그 뒤의 `commit()`은 `skon_test`에 실제로 기록되고, teardown의 `transaction.rollback()`은 `SAWarning: transaction already deassociated from connection`만 남기고 아무것도 되돌리지 못한다. 멱등 시드(Task 9)나 중복 계정 처리(Task 11)처럼 `rollback()`을 쓰는 코드가 테스트에 들어오는 순간 테스트 간 데이터 누수가 조용히 생긴다. `create_savepoint`를 지정하면 커밋·롤백 모두 SAVEPOINT 안에 갇힌다.

- [ ] **Step 5: test_health.py를 client 픽스처로 전환**

`backend/tests/test_health.py` 전체 교체:

```python
async def test_health_returns_ok(client):
    response = await client.get("/api/v1/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
```

- [ ] **Step 6: 테스트 통과 확인**

Run: `cd backend && uv run pytest -v`
Expected: PASS — 실패 0 (누적 테스트 수는 진행에 따라 늘어난다) — DB 컨테이너가 떠 있어야 함

- [ ] **Step 7: 커밋**

```bash
git add backend/
git commit -m "feat(backend): add async db session and rollback test fixtures"
```

---

## Task 4: Enum + 통일 에러 처리

**Files:**
- Create: `backend/app/enums.py`, `backend/app/errors.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_errors.py`

- [ ] **Step 1: 실패하는 테스트 작성**

`backend/tests/test_errors.py`:

```python
import pytest
from fastapi import FastAPI
import httpx

from app.errors import (
    AppError,
    ConflictError,
    NotFoundError,
    ValidationError,
    register_error_handlers,
)


def test_app_error_carries_code_and_status():
    error = ConflictError("TRIP_NOT_SUBMITTABLE", "이미 상신된 출장입니다")

    assert error.status_code == 409
    assert error.code == "TRIP_NOT_SUBMITTABLE"
    assert error.field is None


def test_not_found_is_404():
    assert NotFoundError("TRIP_NOT_FOUND", "없음").status_code == 404


def test_validation_error_keeps_field():
    error = ValidationError("INVALID_CODE", "잘못된 코드", field="transport_code")

    assert error.status_code == 400
    assert error.field == "transport_code"


async def test_handler_returns_unified_body():
    test_app = FastAPI()
    register_error_handlers(test_app)

    @test_app.get("/boom")
    async def boom():
        raise ConflictError("TRIP_NOT_SUBMITTABLE", "이미 상신된 출장입니다")

    transport = httpx.ASGITransport(app=test_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://t") as client:
        response = await client.get("/boom")

    assert response.status_code == 409
    assert response.json() == {
        "error": {
            "code": "TRIP_NOT_SUBMITTABLE",
            "message": "이미 상신된 출장입니다",
            "field": None,
        }
    }


def test_app_error_is_base_class():
    with pytest.raises(AppError):
        raise NotFoundError("X", "y")
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `cd backend && uv run pytest tests/test_errors.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.errors'`

- [ ] **Step 3: enums 구현**

`backend/app/enums.py`:

```python
from enum import StrEnum


class TripStatus(StrEnum):
    DRAFT = "DRAFT"
    SUBMITTED = "SUBMITTED"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    COMPLETED = "COMPLETED"
    SETTLED = "SETTLED"


class ExpenseReportStatus(StrEnum):
    DRAFT = "DRAFT"
    SUBMITTED = "SUBMITTED"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class UserRole(StrEnum):
    EMPLOYEE = "EMPLOYEE"
    MANAGER = "MANAGER"
    ADMIN = "ADMIN"


# 값이 멤버명과 다르다 (TRIPS_READ -> "trips:read"). API 스코프 문자열 그대로를 쓰기 때문.
# 저장은 ARRAY(String)으로 한다 — SAEnum으로 매핑하면 값 대신 멤버명이 저장되어 깨진다.
class ApiKeyScope(StrEnum):
    TRIPS_READ = "trips:read"
    TRIPS_WRITE = "trips:write"
    EXPENSES_READ = "expenses:read"
    EXPENSES_WRITE = "expenses:write"
    CARDS_READ = "cards:read"
    ADMIN = "admin"


class NotificationType(StrEnum):
    TRIP_SUBMITTED = "TRIP_SUBMITTED"
    TRIP_APPROVED = "TRIP_APPROVED"
    TRIP_REJECTED = "TRIP_REJECTED"
    EXPENSE_SUBMITTED = "EXPENSE_SUBMITTED"
    EXPENSE_APPROVED = "EXPENSE_APPROVED"
    EXPENSE_REJECTED = "EXPENSE_REJECTED"


class ActivityAction(StrEnum):
    CREATED = "CREATED"
    UPDATED = "UPDATED"
    SUBMITTED = "SUBMITTED"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    COMPLETED = "COMPLETED"
    SETTLED = "SETTLED"


class EntityType(StrEnum):
    TRIP = "TRIP"
    EXPENSE_REPORT = "EXPENSE_REPORT"
```

- [ ] **Step 4: errors 구현**

`backend/app/errors.py`:

```python
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

RESERVED_LOCATIONS = frozenset({"body", "query", "path", "header", "cookie"})


class AppError(Exception):
    status_code = 500
    
    def __init__(self, code: str, message: str, field: str | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.field = field


class ValidationError(AppError):
    status_code = 400


class AuthError(AppError):
    status_code = 401


class ForbiddenError(AppError):
    status_code = 403


class NotFoundError(AppError):
    status_code = 404


class ConflictError(AppError):
    status_code = 409


def _body(code: str, message: str, field: str | None) -> dict:
    return {"error": {"code": code, "message": message, "field": field}}


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def handle_app_error(_: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content=_body(exc.code, exc.message, exc.field),
        )

    @app.exception_handler(RequestValidationError)
    async def handle_request_validation(
        _: Request, exc: RequestValidationError
    ) -> JSONResponse:
        first = exc.errors()[0] if exc.errors() else {}
        parts = [part for part in (first.get("loc") or []) if isinstance(part, str)]
        field = parts[-1] if parts and parts[-1] not in RESERVED_LOCATIONS else None
        return JSONResponse(
            status_code=422,
            content=_body("SCHEMA_INVALID", first.get("msg", "요청 형식이 올바르지 않습니다"), field),
        )

    @app.exception_handler(StarletteHTTPException)
    async def handle_http_exception(_: Request, exc: StarletteHTTPException) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content=_body("HTTP_ERROR", str(exc.detail), None),
        )

    @app.exception_handler(Exception)
    async def handle_unexpected(_: Request, __: Exception) -> JSONResponse:
        return JSONResponse(
            status_code=500,
            content=_body("INTERNAL_ERROR", "서버 내부 오류가 발생했습니다", None),
        )
```

**보조 설명.** `StarletteHTTPException`을 잡아야 라우팅 404·405까지 통일 바디로 나간다 (`fastapi.HTTPException`이 이걸 상속하므로 둘 다 커버된다). `RESERVED_LOCATIONS` 필터는 깨진 JSON 본문의 `loc: ("body", 1)` 같은 문자 오프셋이 `field`에 필드명처럼 실리는 것을 막는다. `Exception` 핸들러는 Starlette `ServerErrorMiddleware`가 응답을 보낸 뒤 예외를 다시 raise하므로, 테스트에서는 `httpx.ASGITransport(app=..., raise_app_exceptions=False)`로 응답을 받아야 한다 (운영의 uvicorn은 정상적으로 JSON 500을 내려준다).

- [ ] **Step 5: main.py에 등록**

`backend/app/main.py` 전체 교체:

```python
from fastapi import FastAPI

from app.errors import register_error_handlers

app = FastAPI(title="SK온 출장시스템 API", version="1.0.0", docs_url="/docs")
register_error_handlers(app)


@app.get("/api/v1/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
```

- [ ] **Step 5b: 에러 계약 전체를 테스트로 덮기**

`backend/tests/test_errors.py`에 아래 HTTP 레벨 테스트를 추가한다. 전부 `test_handler_returns_unified_body`와 같은 방식으로 일회용 `FastAPI()` 인스턴스를 세워서 검증한다 (공용 `client` 픽스처로 바꾸지 않는다).

- 5개 서브클래스 + 베이스 `AppError`까지 파라미터라이즈해서 상태코드와 통일 바디를 각각 확인
- 본문 검증 실패: 필수 필드 누락 → 422, `code == "SCHEMA_INVALID"`, `field == "<누락 필드명>"`
- 깨진 JSON 본문 → 422, `code == "SCHEMA_INVALID"`, **`field is None`** (`RESERVED_LOCATIONS` 회귀 방지)
- 없는 경로 `GET /nonexistent` → 404, `code == "HTTP_ERROR"`, 통일 바디
- 라우트에서 처리되지 않은 예외 → 500, `code == "INTERNAL_ERROR"`. 이 케이스만 `httpx.ASGITransport(app=..., raise_app_exceptions=False)` 사용

- [ ] **Step 6: 테스트 통과 확인**

Run: `cd backend && uv run pytest -v`
Expected: PASS — 실패 0 (누적 테스트 수는 진행에 따라 늘어난다)

- [ ] **Step 7: 커밋**

```bash
git add backend/
git commit -m "feat(backend): add domain enums and unified error responses"
```

---

## Task 5: 조직 · 공통코드 · 센터 모델

**Files:**
- Create: `backend/app/models/org.py`, `backend/app/models/code.py`, `backend/app/models/center.py`
- Modify: `backend/app/models/__init__.py`
- Test: `backend/tests/test_models_master.py`

- [ ] **Step 1: 실패하는 테스트 작성**

`backend/tests/test_models_master.py`:

```python
from sqlalchemy import select

from app.enums import UserRole
from app.models import Code, CodeGroup, CostCenter, Department, FundCenter, User


async def test_can_persist_department_and_user(db_session):
    dept = Department(code="D100", name="배터리연구소")
    db_session.add(dept)
    await db_session.flush()

    manager = User(
        email="manager@skon.example",
        password_hash="x",
        name="김팀장",
        employee_no="E0001",
        department_id=dept.id,
        position_code="TEAM_LEADER",
        role=UserRole.MANAGER,
    )
    db_session.add(manager)
    await db_session.flush()

    member = User(
        email="member@skon.example",
        password_hash="x",
        name="이사원",
        employee_no="E0002",
        department_id=dept.id,
        position_code="STAFF",
        role=UserRole.EMPLOYEE,
        manager_id=manager.id,
    )
    db_session.add(member)
    await db_session.flush()

    found = (await db_session.execute(select(User).where(User.email == "member@skon.example"))).scalar_one()
    assert found.manager_id == manager.id
    assert found.role is UserRole.EMPLOYEE
    assert found.is_active is True


async def test_department_tree_links_parent(db_session):
    parent = Department(code="D000", name="본사")
    db_session.add(parent)
    await db_session.flush()

    child = Department(code="D110", name="배터리연구소 1팀", parent_id=parent.id)
    db_session.add(child)
    await db_session.flush()

    found = (await db_session.execute(select(Department).where(Department.code == "D110"))).scalar_one()
    assert found.parent_id == parent.id


async def test_code_group_holds_codes_with_extra(db_session):
    group = CodeGroup(group_code="COUNTRY", name="국가")
    db_session.add(group)
    await db_session.flush()

    db_session.add(
        Code(group_id=group.id, code="US", name="미국", sort_order=1, extra={"currency": "USD"})
    )
    await db_session.flush()

    code = (await db_session.execute(select(Code).where(Code.code == "US"))).scalar_one()
    assert code.extra["currency"] == "USD"
    assert code.is_active is True


async def test_centers_can_link_to_department(db_session):
    dept = Department(code="D200", name="구매팀")
    db_session.add(dept)
    await db_session.flush()

    db_session.add(FundCenter(code="FC1010", name="배터리연구소 비용처리", department_id=dept.id))
    db_session.add(CostCenter(code="CC2030", name="구매팀 비용사용", department_id=dept.id))
    await db_session.flush()

    fc = (await db_session.execute(select(FundCenter).where(FundCenter.code == "FC1010"))).scalar_one()
    cc = (await db_session.execute(select(CostCenter).where(CostCenter.code == "CC2030"))).scalar_one()
    assert fc.department_id == dept.id
    assert cc.is_active is True
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `cd backend && uv run pytest tests/test_models_master.py -v`
Expected: FAIL — `ImportError: cannot import name 'Department' from 'app.models'`

- [ ] **Step 3: org 모델 구현**

`backend/app/models/org.py`:

```python
from sqlalchemy import Boolean, Enum as SAEnum, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.enums import UserRole
from app.models.base import Base, TimestampMixin


class Department(Base, TimestampMixin):
    __tablename__ = "department"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    parent_id: Mapped[int | None] = mapped_column(ForeignKey("department.id"))


# 주의: PostgreSQL에서 user는 예약 의사상수다. 원시 SQL을 쓸 때 반드시 큰따옴표로
# 감싼 "user"로 써야 한다. 따옴표 없이 쓰면 에러가 아니라 현재 롤 이름이 조용히 반환된다.
class User(Base, TimestampMixin):
    __tablename__ = "user"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(120), unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String(200), nullable=False)
    name: Mapped[str] = mapped_column(String(50), nullable=False)
    employee_no: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    department_id: Mapped[int] = mapped_column(ForeignKey("department.id"), nullable=False)
    position_code: Mapped[str] = mapped_column(String(30), nullable=False)
    manager_id: Mapped[int | None] = mapped_column(ForeignKey("user.id"))
    role: Mapped[UserRole] = mapped_column(
        SAEnum(UserRole, name="user_role"), default=UserRole.EMPLOYEE, nullable=False
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
```

- [ ] **Step 4: code 모델 구현**

`backend/app/models/code.py`:

```python
from typing import Any

from sqlalchemy import Boolean, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class CodeGroup(Base, TimestampMixin):
    __tablename__ = "code_group"

    id: Mapped[int] = mapped_column(primary_key=True)
    group_code: Mapped[str] = mapped_column(String(40), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(String(255))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    codes: Mapped[list["Code"]] = relationship(
        back_populates="group", cascade="all, delete-orphan", lazy="selectin"
    )


class Code(Base, TimestampMixin):
    __tablename__ = "code"
    __table_args__ = (UniqueConstraint("group_id", "code", name="uq_code_group_code"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    group_id: Mapped[int] = mapped_column(ForeignKey("code_group.id"), nullable=False)
    code: Mapped[str] = mapped_column(String(40), nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    extra: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)

    group: Mapped[CodeGroup] = relationship(back_populates="codes", lazy="selectin")
```

- [ ] **Step 5: center 모델 구현**

`backend/app/models/center.py`:

```python
from sqlalchemy import Boolean, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class FundCenter(Base, TimestampMixin):
    """비용처리 부서."""

    __tablename__ = "fund_center"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(20), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    department_id: Mapped[int | None] = mapped_column(ForeignKey("department.id"))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class CostCenter(Base, TimestampMixin):
    """비용사용 부서."""

    __tablename__ = "cost_center"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(20), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    department_id: Mapped[int | None] = mapped_column(ForeignKey("department.id"))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
```

- [ ] **Step 6: `__init__.py` 갱신**

`backend/app/models/__init__.py`:

```python
from app.models.base import Base, TimestampMixin
from app.models.center import CostCenter, FundCenter
from app.models.code import Code, CodeGroup
from app.models.org import Department, User

__all__ = [
    "Base",
    "Code",
    "CodeGroup",
    "CostCenter",
    "Department",
    "FundCenter",
    "TimestampMixin",
    "User",
]
```

- [ ] **Step 7: 테스트 통과 확인**

Run: `cd backend && uv run pytest -v`
Expected: PASS — 실패 0 (누적 테스트 수는 진행에 따라 늘어난다)

- [ ] **Step 8: 커밋**

```bash
git add backend/
git commit -m "feat(backend): add org, common code, and center models"
```

---

## Task 6: 공통코드 검증 서비스

**Files:**
- Create: `backend/app/services/__init__.py`, `backend/app/services/codes.py`
- Test: `backend/tests/test_codes_service.py`

- [ ] **Step 1: 실패하는 테스트 작성**

`backend/tests/test_codes_service.py`:

```python
import pytest

from app.errors import ValidationError
from app.models import Code, CodeGroup
from app.services.codes import assert_valid_code, load_active_codes


def test_assert_valid_code_accepts_known_value():
    assert_valid_code("TRANSPORT", "AIR", {"AIR", "RAIL"}, field="transport_code")


def test_assert_valid_code_rejects_unknown_value():
    with pytest.raises(ValidationError) as exc_info:
        assert_valid_code("TRANSPORT", "ROCKET", {"AIR", "RAIL"}, field="transport_code")

    error = exc_info.value
    assert error.status_code == 400
    assert error.code == "INVALID_CODE"
    assert error.field == "transport_code"
    assert "TRANSPORT" in error.message


def test_assert_valid_code_rejects_none():
    with pytest.raises(ValidationError):
        assert_valid_code("TRANSPORT", None, {"AIR"}, field="transport_code")


async def test_load_active_codes_returns_only_active(db_session):
    group = CodeGroup(group_code="TRANSPORT", name="이동수단")
    db_session.add(group)
    await db_session.flush()
    db_session.add(Code(group_id=group.id, code="AIR", name="항공", sort_order=1))
    db_session.add(Code(group_id=group.id, code="SHIP", name="선박", sort_order=2, is_active=False))
    await db_session.flush()

    values = await load_active_codes(db_session, "TRANSPORT")

    assert values == {"AIR"}


async def test_load_active_codes_raises_for_unknown_group(db_session):
    with pytest.raises(ValidationError) as exc_info:
        await load_active_codes(db_session, "NOPE")

    assert exc_info.value.code == "UNKNOWN_CODE_GROUP"
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `cd backend && uv run pytest tests/test_codes_service.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.services'`

- [ ] **Step 3: 구현**

빈 파일: `backend/app/services/__init__.py`

`backend/app/services/codes.py`:

```python
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.errors import ValidationError
from app.models import Code, CodeGroup


def assert_valid_code(
    group_code: str, value: str | None, allowed: set[str], *, field: str
) -> None:
    """순수 검증 — DB 접근 없음. 허용 집합은 호출자가 주입한다."""
    if value not in allowed:
        raise ValidationError(
            "INVALID_CODE",
            f"{group_code} 그룹에 없는 코드값입니다: {value}",
            field=field,
        )


async def load_active_codes(session: AsyncSession, group_code: str) -> set[str]:
    """활성 코드그룹의 활성 코드값 집합을 돌려준다.

    엔티티가 아니라 `CodeGroup.id` 컬럼만 고르는 것은 의도적이다. 엔티티를 고르면
    ORM 객체가 만들어지면서 `lazy="selectin"`인 `CodeGroup.codes`까지 끌려와 쓸모없는
    세 번째 쿼리가 나간다. 또한 이 2쿼리 구조를 조인 한 방으로 합치면 안 된다.
    "그룹이 없거나 비활성"(`UNKNOWN_CODE_GROUP`)과 "그룹은 살아있으나 활성 코드가
    0건"(빈 `set()`)을 구분할 수 없게 되기 때문이다.
    """
    group_id = (
        await session.execute(
            select(CodeGroup.id).where(
                CodeGroup.group_code == group_code,
                CodeGroup.is_active.is_(True),
            )
        )
    ).scalar_one_or_none()
    if group_id is None:
        raise ValidationError("UNKNOWN_CODE_GROUP", f"존재하지 않는 코드그룹입니다: {group_code}")

    rows = await session.execute(
        select(Code.code).where(Code.group_id == group_id, Code.is_active.is_(True))
    )
    return set(rows.scalars().all())
```

비활성 코드그룹은 존재하지 않는 그룹과 동일하게 취급한다. 둘 다 쓰기를 막아야 하고, 별도 에러코드를 만들 이유가 없다. Admin이 코드그룹을 비활성화한 뒤에도 그 그룹의 코드로 쓰기가 통과되는 구멍을 막는다.

**왜 `select(CodeGroup)`이 아니라 `select(CodeGroup.id)`인가.** 엔티티를 가져오면 `CodeGroup.codes`가 `lazy="selectin"`이라 아무도 읽지 않는 코드 목록을 통째로 한 번 더 조회한다 (호출당 3쿼리). 컬럼만 선택하면 ORM 객체가 만들어지지 않아 그 쿼리가 사라진다 (2쿼리).

**왜 조인 한 방으로 합치지 않는가.** `select(Code.code).join(CodeGroup).where(...)` 한 문장으로 줄이면 "코드그룹이 없음"과 "코드그룹은 있으나 활성 코드가 0건"을 구분할 수 없다. 전자는 `UNKNOWN_CODE_GROUP`을 던져야 하고 후자는 정상적으로 빈 `set()`을 반환해야 하므로, 2쿼리 구조는 우연이 아니라 의도된 것이다.

- [ ] **Step 4: 테스트 통과 확인**

Run: `cd backend && uv run pytest -v`
Expected: PASS — 실패 0 (누적 테스트 수는 진행에 따라 늘어난다)

- [ ] **Step 5: 커밋**

```bash
git add backend/
git commit -m "feat(backend): add common code validation service"
```

---

## Task 7: 출장 모델 + 상태전이 규칙

> **Task 6 리뷰에서 넘어온 권고 — 이 태스크가 아니라 Phase 2에서 처리한다.** 출장 쓰기 경로는 `purpose_code` · `destination_type_code` · `country_code` · `transport_code` · `accommodation_code` 다섯 개를 한 요청에서 검증해야 하고, 현재 API로는 `load_active_codes` + `assert_valid_code` 쌍이 다섯 번 반복되어 그룹명과 `field=` 문자열을 잘못 짝지을 위험이 있다. 다만 **Task 7은 모델과 상태전이 표만 만들고 라우터·생성 엔드포인트를 만들지 않으므로 여기에도 실제 호출부가 없다.** 따라서 아래 오케스트레이터는 출장 생성 엔드포인트가 실제로 생기는 Phase 2에서 도입한다.
>
> ```python
> async def validate_codes(
>     session: AsyncSession, entries: Sequence[tuple[str, str | None, str]]
> ) -> None:
>     results = await asyncio.gather(*(load_active_codes(session, g) for g, _, _ in entries))
>     for (group_code, value, field), allowed in zip(entries, results):
>         assert_valid_code(group_code, value, allowed, field=field)
> ```
>
> 호출부가 한 줄로 줄고 다섯 번의 순차 왕복이 동시 실행된다. 측정치상 지연 자체는 문제가 아니었으므로(출장 1건 검증 ~15-19ms, 40건 시드 ~570ms), 도입 근거는 성능이 아니라 호출부 실수 방지다.

**Files:**
- Create: `backend/app/models/trip.py`, `backend/app/services/trip_status.py`
- Modify: `backend/app/models/__init__.py`
- Test: `backend/tests/test_trip_status.py`, `backend/tests/test_models_trip.py`

- [ ] **Step 1: 상태전이 실패 테스트 작성**

`backend/tests/test_trip_status.py`:

```python
import pytest

from app.enums import TripStatus
from app.errors import ConflictError
from app.services.trip_status import assert_trip_transition, can_transition


@pytest.mark.parametrize(
    ("current", "target"),
    [
        (TripStatus.DRAFT, TripStatus.SUBMITTED),
        (TripStatus.SUBMITTED, TripStatus.APPROVED),
        (TripStatus.SUBMITTED, TripStatus.REJECTED),
        (TripStatus.REJECTED, TripStatus.DRAFT),
        (TripStatus.APPROVED, TripStatus.COMPLETED),
        (TripStatus.COMPLETED, TripStatus.SETTLED),
    ],
)
def test_allowed_transitions(current, target):
    assert can_transition(current, target) is True


@pytest.mark.parametrize(
    ("current", "target"),
    [
        (TripStatus.DRAFT, TripStatus.APPROVED),
        (TripStatus.SUBMITTED, TripStatus.SUBMITTED),
        (TripStatus.APPROVED, TripStatus.SETTLED),
        (TripStatus.SETTLED, TripStatus.DRAFT),
        (TripStatus.COMPLETED, TripStatus.APPROVED),
    ],
)
def test_forbidden_transitions(current, target):
    assert can_transition(current, target) is False


def test_assert_raises_conflict_with_domain_code():
    with pytest.raises(ConflictError) as exc_info:
        assert_trip_transition(TripStatus.SUBMITTED, TripStatus.SUBMITTED)

    error = exc_info.value
    assert error.status_code == 409
    assert error.code == "TRIP_INVALID_TRANSITION"
    assert "SUBMITTED" in error.message


def test_assert_passes_on_allowed():
    assert_trip_transition(TripStatus.DRAFT, TripStatus.SUBMITTED)
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `cd backend && uv run pytest tests/test_trip_status.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.services.trip_status'`

- [ ] **Step 3: 상태전이 구현**

`backend/app/services/trip_status.py`:

```python
from app.enums import TripStatus
from app.errors import ConflictError

ALLOWED_TRANSITIONS: dict[TripStatus, frozenset[TripStatus]] = {
    TripStatus.DRAFT: frozenset({TripStatus.SUBMITTED}),
    TripStatus.SUBMITTED: frozenset({TripStatus.APPROVED, TripStatus.REJECTED}),
    TripStatus.REJECTED: frozenset({TripStatus.DRAFT}),
    TripStatus.APPROVED: frozenset({TripStatus.COMPLETED}),
    TripStatus.COMPLETED: frozenset({TripStatus.SETTLED}),
    TripStatus.SETTLED: frozenset(),
}


def can_transition(current: TripStatus, target: TripStatus) -> bool:
    return target in ALLOWED_TRANSITIONS[current]


def assert_trip_transition(current: TripStatus, target: TripStatus) -> None:
    if not can_transition(current, target):
        raise ConflictError(
            "TRIP_INVALID_TRANSITION",
            f"{current} 상태에서 {target} 로 변경할 수 없습니다",
        )
```

- [ ] **Step 4: 상태전이 테스트 통과 확인**

Run: `cd backend && uv run pytest tests/test_trip_status.py -v`
Expected: PASS (13 passed)

- [ ] **Step 5: 출장 모델 실패 테스트 작성**

`backend/tests/test_models_trip.py`:

```python
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
```

- [ ] **Step 6: 출장 모델 구현**

`backend/app/models/trip.py`:

```python
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Date, DateTime, Enum as SAEnum, ForeignKey, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.enums import TripStatus
from app.models.base import Base, TimestampMixin


class Trip(Base, TimestampMixin):
    __tablename__ = "trip"

    id: Mapped[int] = mapped_column(primary_key=True)
    trip_no: Mapped[str] = mapped_column(String(20), unique=True, nullable=False, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("user.id"), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    purpose_code: Mapped[str] = mapped_column(String(40), nullable=False)
    purpose_detail: Mapped[str] = mapped_column(Text, nullable=False)
    destination_type_code: Mapped[str] = mapped_column(String(40), nullable=False)
    country_code: Mapped[str] = mapped_column(String(40), nullable=False)
    city: Mapped[str] = mapped_column(String(80), nullable=False)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    transport_code: Mapped[str] = mapped_column(String(40), nullable=False)
    accommodation_code: Mapped[str] = mapped_column(String(40), nullable=False)
    cost_center_code: Mapped[str] = mapped_column(String(20), nullable=False)
    estimated_cost: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    status: Mapped[TripStatus] = mapped_column(
        SAEnum(TripStatus, name="trip_status"), default=TripStatus.DRAFT, nullable=False, index=True
    )
    approver_id: Mapped[int | None] = mapped_column(ForeignKey("user.id"))
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    reject_reason: Mapped[str | None] = mapped_column(Text)
```

`backend/app/models/__init__.py`에 추가 — import 줄과 `__all__` 항목:

```python
from app.models.trip import Trip
```

`__all__` 리스트에 `"Trip"` 추가 (알파벳 순 유지).

- [ ] **Step 7: 테스트 통과 확인**

Run: `cd backend && uv run pytest -v`
Expected: PASS — 실패 0 (누적 테스트 수는 진행에 따라 늘어난다)

- [ ] **Step 8: 커밋**

```bash
git add backend/
git commit -m "feat(backend): add trip model and status transition rules"
```

---

## Task 8: 카드 · 정산 · API Key · 알림 모델

**Files:**
- Create: `backend/app/models/expense.py`, `backend/app/models/apikey.py`, `backend/app/models/activity.py`
- Modify: `backend/app/models/__init__.py`
- Test: `backend/tests/test_models_expense.py`

- [ ] **Step 1: 실패하는 테스트 작성**

`backend/tests/test_models_expense.py`:

```python
from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy import select

from app.enums import (
    ActivityAction,
    EntityType,
    ExpenseReportStatus,
    NotificationType,
    TripStatus,
    UserRole,
)
from app.models import (
    ActivityLog,
    ApiKey,
    CardTransaction,
    CorporateCard,
    Department,
    ExpenseItem,
    ExpenseReport,
    Notification,
    Trip,
    User,
)


async def _fixture_trip(db_session) -> tuple[User, Trip]:
    dept = Department(code="D800", name="정산테스트부서")
    db_session.add(dept)
    await db_session.flush()
    user = User(
        email="exp@skon.example",
        password_hash="x",
        name="최정산",
        employee_no="E8001",
        department_id=dept.id,
        position_code="STAFF",
        role=UserRole.EMPLOYEE,
    )
    db_session.add(user)
    await db_session.flush()
    trip = Trip(
        trip_no="BT-2026-0800",
        user_id=user.id,
        title="서산공장 출장",
        purpose_code="SUPPORT",
        purpose_detail="설비 지원",
        destination_type_code="DOMESTIC",
        country_code="KR",
        city="서산",
        start_date=date(2026, 7, 1),
        end_date=date(2026, 7, 2),
        transport_code="CAR",
        accommodation_code="HOTEL",
        cost_center_code="CC2030",
        estimated_cost=Decimal("200000"),
        status=TripStatus.COMPLETED,
    )
    db_session.add(trip)
    await db_session.flush()
    return user, trip


async def test_card_transaction_and_expense_item_link(db_session):
    user, trip = await _fixture_trip(db_session)

    card = CorporateCard(user_id=user.id, card_no_masked="5678-****-****-1234", brand="BC")
    db_session.add(card)
    await db_session.flush()

    txn = CardTransaction(
        card_id=card.id,
        approved_at=datetime(2026, 7, 1, 12, 30, tzinfo=timezone.utc),
        merchant_name="서산식당",
        merchant_category_code="MEAL",
        amount=Decimal("32000"),
        currency_code="KRW",
        amount_krw=Decimal("32000"),
    )
    db_session.add(txn)
    await db_session.flush()

    report = ExpenseReport(
        report_no="EX-2026-0800",
        trip_id=trip.id,
        user_id=user.id,
        fund_center_code="FC1010",
        cost_center_code="CC2030",
    )
    db_session.add(report)
    await db_session.flush()

    db_session.add(
        ExpenseItem(
            report_id=report.id,
            card_transaction_id=txn.id,
            expense_category_code="MEAL",
            amount_krw=Decimal("32000"),
        )
    )
    await db_session.flush()

    saved = (
        await db_session.execute(select(ExpenseReport).where(ExpenseReport.report_no == "EX-2026-0800"))
    ).scalar_one()
    assert saved.status is ExpenseReportStatus.DRAFT
    assert saved.total_amount_krw == Decimal("0")

    item = (await db_session.execute(select(ExpenseItem))).scalars().first()
    assert item.fund_center_code is None
    assert item.cost_center_code is None
    assert item.is_excluded is False


async def test_api_key_stores_hash_and_scopes(db_session):
    user, _ = await _fixture_trip(db_session)

    db_session.add(
        ApiKey(
            user_id=user.id,
            name="agent-key",
            key_prefix="sk_live_abcd1234",
            key_hash="0" * 64,
            scopes=["trips:read", "trips:write"],
        )
    )
    await db_session.flush()

    key = (await db_session.execute(select(ApiKey))).scalar_one()
    assert key.scopes == ["trips:read", "trips:write"]
    assert key.revoked_at is None
    assert key.last_used_at is None


async def test_notification_and_activity_log(db_session):
    user, trip = await _fixture_trip(db_session)

    db_session.add(
        Notification(
            user_id=user.id,
            type=NotificationType.TRIP_SUBMITTED,
            title="결재 요청",
            body="서산공장 출장 결재 요청",
            link_url=f"/trips/{trip.id}",
        )
    )
    db_session.add(
        ActivityLog(
            entity_type=EntityType.TRIP,
            entity_id=trip.id,
            actor_id=user.id,
            action=ActivityAction.SUBMITTED,
            from_status="DRAFT",
            to_status="SUBMITTED",
        )
    )
    await db_session.flush()

    noti = (await db_session.execute(select(Notification))).scalar_one()
    log = (await db_session.execute(select(ActivityLog))).scalar_one()
    assert noti.is_read is False
    assert log.entity_type is EntityType.TRIP
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `cd backend && uv run pytest tests/test_models_expense.py -v`
Expected: FAIL — `ImportError: cannot import name 'CorporateCard' from 'app.models'`

- [ ] **Step 3: expense 모델 구현**

`backend/app/models/expense.py`:

```python
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum as SAEnum,
    ForeignKey,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.enums import ExpenseReportStatus
from app.models.base import Base, TimestampMixin


class CorporateCard(Base, TimestampMixin):
    __tablename__ = "corporate_card"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("user.id"), nullable=False, index=True)
    card_no_masked: Mapped[str] = mapped_column(String(30), nullable=False)
    brand: Mapped[str] = mapped_column(String(30), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class CardTransaction(Base, TimestampMixin):
    __tablename__ = "card_transaction"

    id: Mapped[int] = mapped_column(primary_key=True)
    card_id: Mapped[int] = mapped_column(ForeignKey("corporate_card.id"), nullable=False, index=True)
    approved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    merchant_name: Mapped[str] = mapped_column(String(120), nullable=False)
    merchant_category_code: Mapped[str] = mapped_column(String(40), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    currency_code: Mapped[str] = mapped_column(String(10), nullable=False)
    amount_krw: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    is_cancelled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)


class ExpenseReport(Base, TimestampMixin):
    __tablename__ = "expense_report"

    id: Mapped[int] = mapped_column(primary_key=True)
    report_no: Mapped[str] = mapped_column(String(20), unique=True, nullable=False, index=True)
    trip_id: Mapped[int] = mapped_column(ForeignKey("trip.id"), unique=True, nullable=False)
    user_id: Mapped[int] = mapped_column(ForeignKey("user.id"), nullable=False, index=True)
    status: Mapped[ExpenseReportStatus] = mapped_column(
        SAEnum(ExpenseReportStatus, name="expense_report_status"),
        default=ExpenseReportStatus.DRAFT,
        nullable=False,
        index=True,
    )
    fund_center_code: Mapped[str | None] = mapped_column(String(20))
    cost_center_code: Mapped[str | None] = mapped_column(String(20))
    total_amount_krw: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=Decimal("0"), nullable=False)
    approver_id: Mapped[int | None] = mapped_column(ForeignKey("user.id"))
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    reject_reason: Mapped[str | None] = mapped_column(Text)


class ExpenseItem(Base, TimestampMixin):
    __tablename__ = "expense_item"
    __table_args__ = (
        UniqueConstraint("report_id", "card_transaction_id", name="uq_expense_item_report_txn"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    report_id: Mapped[int] = mapped_column(ForeignKey("expense_report.id"), nullable=False, index=True)
    card_transaction_id: Mapped[int | None] = mapped_column(ForeignKey("card_transaction.id"))
    expense_category_code: Mapped[str] = mapped_column(String(40), nullable=False)
    amount_krw: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    memo: Mapped[str | None] = mapped_column(String(255))
    is_excluded: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    fund_center_code: Mapped[str | None] = mapped_column(String(20))
    cost_center_code: Mapped[str | None] = mapped_column(String(20))
```

- [ ] **Step 4: apikey 모델 구현**

`backend/app/models/apikey.py`:

```python
from datetime import datetime

from sqlalchemy import ARRAY, DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class ApiKey(Base, TimestampMixin):
    __tablename__ = "api_key"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("user.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    key_prefix: Mapped[str] = mapped_column(String(30), nullable=False)
    key_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    scopes: Mapped[list[str]] = mapped_column(ARRAY(String(30)), nullable=False)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
```

- [ ] **Step 5: activity 모델 구현**

`backend/app/models/activity.py`:

```python
from sqlalchemy import Boolean, Enum as SAEnum, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.enums import ActivityAction, EntityType, NotificationType
from app.models.base import Base, TimestampMixin


class Notification(Base, TimestampMixin):
    __tablename__ = "notification"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("user.id"), nullable=False, index=True)
    type: Mapped[NotificationType] = mapped_column(
        SAEnum(NotificationType, name="notification_type"), nullable=False
    )
    title: Mapped[str] = mapped_column(String(120), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    link_url: Mapped[str | None] = mapped_column(String(200))
    is_read: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)


class ActivityLog(Base, TimestampMixin):
    __tablename__ = "activity_log"

    id: Mapped[int] = mapped_column(primary_key=True)
    entity_type: Mapped[EntityType] = mapped_column(
        SAEnum(EntityType, name="entity_type"), nullable=False, index=True
    )
    entity_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    actor_id: Mapped[int] = mapped_column(ForeignKey("user.id"), nullable=False)
    action: Mapped[ActivityAction] = mapped_column(
        SAEnum(ActivityAction, name="activity_action"), nullable=False
    )
    from_status: Mapped[str | None] = mapped_column(String(30))
    to_status: Mapped[str | None] = mapped_column(String(30))
    memo: Mapped[str | None] = mapped_column(Text)
```

- [ ] **Step 6: `__init__.py` 전체 교체**

`backend/app/models/__init__.py`:

```python
from app.models.activity import ActivityLog, Notification
from app.models.apikey import ApiKey
from app.models.base import Base, TimestampMixin
from app.models.center import CostCenter, FundCenter
from app.models.code import Code, CodeGroup
from app.models.expense import CardTransaction, CorporateCard, ExpenseItem, ExpenseReport
from app.models.org import Department, User
from app.models.trip import Trip

__all__ = [
    "ActivityLog",
    "ApiKey",
    "Base",
    "CardTransaction",
    "Code",
    "CodeGroup",
    "CorporateCard",
    "CostCenter",
    "Department",
    "ExpenseItem",
    "ExpenseReport",
    "FundCenter",
    "Notification",
    "TimestampMixin",
    "Trip",
    "User",
]
```

- [ ] **Step 7: 테스트 통과 확인**

Run: `cd backend && uv run pytest -v`
Expected: PASS — 실패 0 (누적 테스트 수는 진행에 따라 늘어난다)

- [ ] **Step 8: 커밋**

```bash
git add backend/
git commit -m "feat(backend): add card, expense, api key, and activity models"
```

---

## Task 9: 시드 데이터

**Files:**
- Create: `backend/app/seed.py`
- Test: `backend/tests/test_seed.py`

> **선행 의존:** 이 태스크의 테스트는 Task 10에서 만드는 `app/security.py`의 `hash_password`가 있어야 통과한다. 코드와 테스트를 여기서 모두 작성하되, 검증과 커밋은 Task 10의 Step 5~7에서 함께 수행한다.

- [ ] **Step 1: 실패하는 테스트 작성**

`backend/tests/test_seed.py`:

```python
from sqlalchemy import func, select

from app.enums import UserRole
from app.models import (
    CardTransaction,
    Code,
    CodeGroup,
    CorporateCard,
    CostCenter,
    Department,
    ExpenseReport,
    FundCenter,
    Trip,
    User,
)
from app.seed import seed_all


async def _count(db_session, model) -> int:
    return (await db_session.execute(select(func.count()).select_from(model))).scalar_one()


async def test_seed_creates_expected_master_data(db_session):
    await seed_all(db_session)

    assert await _count(db_session, Department) == 4
    assert await _count(db_session, User) == 14
    assert await _count(db_session, CodeGroup) == 9
    assert await _count(db_session, FundCenter) == 6
    assert await _count(db_session, CostCenter) == 10
    assert await _count(db_session, CorporateCard) == 14
    assert await _count(db_session, Trip) == 40
    assert await _count(db_session, ExpenseReport) == 12
    assert await _count(db_session, CardTransaction) >= 600


async def test_seed_is_idempotent(db_session):
    await seed_all(db_session)
    first_users = await _count(db_session, User)
    first_txns = await _count(db_session, CardTransaction)

    await seed_all(db_session)

    assert await _count(db_session, User) == first_users
    assert await _count(db_session, CardTransaction) == first_txns


async def test_seed_creates_one_admin_and_three_managers(db_session):
    await seed_all(db_session)

    admins = (
        await db_session.execute(select(func.count()).select_from(User).where(User.role == UserRole.ADMIN))
    ).scalar_one()
    managers = (
        await db_session.execute(
            select(func.count()).select_from(User).where(User.role == UserRole.MANAGER)
        )
    ).scalar_one()

    assert admins == 1
    assert managers == 3


async def test_seed_country_code_carries_currency_in_extra(db_session):
    await seed_all(db_session)

    group = (
        await db_session.execute(select(CodeGroup).where(CodeGroup.group_code == "COUNTRY"))
    ).scalar_one()
    us = (
        await db_session.execute(select(Code).where(Code.group_id == group.id, Code.code == "US"))
    ).scalar_one()

    assert us.extra["currency"] == "USD"
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `cd backend && uv run pytest tests/test_seed.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.seed'`

- [ ] **Step 3: 시드 구현**

`backend/app/seed.py`:

```python
"""멱등 시드. 이미 데이터가 있으면 해당 블록을 건너뛴다."""

import random
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.enums import ExpenseReportStatus, TripStatus, UserRole
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
    existing = (await session.execute(select(Department))).scalars().all()
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
    if await _is_seeded(session, FundCenter):
        return
    for code, name, dept_code in FUND_CENTERS:
        session.add(
            FundCenter(
                code=code, name=name, department_id=depts[dept_code].id if dept_code else None
            )
        )
    for code, name, dept_code in COST_CENTERS:
        session.add(
            CostCenter(
                code=code, name=name, department_id=depts[dept_code].id if dept_code else None
            )
        )
    await session.flush()


async def _seed_users(session: AsyncSession, depts: dict[str, Department]) -> list[User]:
    existing = (await session.execute(select(User))).scalars().all()
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
            transport = "AIR"
            duration = rng.randint(3, 7)
        else:
            country, city = "KR", rng.choice(DOMESTIC_CITIES)
            transport = rng.choice(["RAIL", "CAR", "BUS"])
            duration = rng.randint(1, 3)

        start = today - timedelta(days=rng.randint(-30, 150))
        purpose = rng.choice(["CUSTOMER", "SUPPORT", "TRAINING", "CONFERENCE", "AUDIT"])
        trip = Trip(
            trip_no=f"BT-2026-{index:04d}",
            user_id=author.id,
            title=f"{city} {'해외' if overseas else '국내'}출장",
            purpose_code=purpose,
            purpose_detail=f"{city} 현장 {purpose} 목적 출장",
            destination_type_code="OVERSEAS" if overseas else "DOMESTIC",
            country_code=country,
            city=city,
            start_date=start,
            end_date=start + timedelta(days=duration),
            transport_code=transport,
            accommodation_code=rng.choice(["HOTEL", "RESIDENCE", "DORM"]),
            cost_center_code=rng.choice([c[0] for c in COST_CENTERS]),
            estimated_cost=Decimal(rng.randrange(200000, 4000000, 10000)),
            status=status,
            approver_id=author.manager_id if status != TripStatus.DRAFT else None,
            submitted_at=None if status == TripStatus.DRAFT else datetime.now(timezone.utc),
            approved_at=(
                datetime.now(timezone.utc)
                if status in {TripStatus.APPROVED, TripStatus.COMPLETED, TripStatus.SETTLED}
                else None
            ),
            reject_reason="사유 보완 필요" if status == TripStatus.REJECTED else None,
        )
        session.add(trip)
        trips.append(trip)
    await session.flush()

    settleable = [t for t in trips if t.status in {TripStatus.COMPLETED, TripStatus.SETTLED}][:12]
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
    rng = random.Random(RNG_SEED)
    await _seed_codes(session)
    depts = await _seed_org(session)
    await _seed_centers(session, depts)
    users = await _seed_users(session, depts)
    await _seed_cards(session, users, rng)
    await _seed_trips(session, users, rng)
    await session.commit()
```

- [ ] **Step 4: 테스트 통과 확인**

Task 10에서 `app.security.hash_password`를 만들기 전까지는 import 에러가 난다. Task 10 완료 후 실행한다.

Run: `cd backend && uv run pytest tests/test_seed.py -v`
Expected: 현재는 FAIL — `ModuleNotFoundError: No module named 'app.security'`. **Task 10 완료 후 재실행하여 PASS 확인.**

- [ ] **Step 5: 커밋 보류**

Task 10에서 함께 커밋한다.

---

## Task 10: 비밀번호 해싱 + JWT

**Files:**
- Create: `backend/app/security.py`
- Test: `backend/tests/test_security.py`

- [ ] **Step 1: 실패하는 테스트 작성**

`backend/tests/test_security.py`:

```python
from datetime import datetime, timedelta, timezone

import pytest

from app.errors import AuthError
from app.security import create_access_token, decode_access_token, hash_password, verify_password


def test_hash_and_verify_password():
    hashed = hash_password("skon1234!")

    assert hashed != "skon1234!"
    assert verify_password("skon1234!", hashed) is True
    assert verify_password("wrong", hashed) is False


def test_verify_password_rejects_malformed_hash():
    assert verify_password("skon1234!", "not-a-bcrypt-hash") is False


def test_token_roundtrip_carries_user_id():
    token = create_access_token(user_id=42)

    assert decode_access_token(token) == 42


def test_decode_rejects_garbage():
    with pytest.raises(AuthError) as exc_info:
        decode_access_token("garbage.token.value")

    assert exc_info.value.code == "INVALID_TOKEN"


def test_decode_rejects_expired_token():
    expired = create_access_token(
        user_id=7, expires_at=datetime.now(timezone.utc) - timedelta(minutes=1)
    )

    with pytest.raises(AuthError) as exc_info:
        decode_access_token(expired)

    assert exc_info.value.code == "TOKEN_EXPIRED"
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `cd backend && uv run pytest tests/test_security.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.security'`

- [ ] **Step 3: 구현**

`backend/app/security.py`:

```python
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt

from app.config import get_settings
from app.errors import AuthError


def hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode(), bcrypt.gensalt()).decode()


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode(), hashed.encode())
    except ValueError:
        return False


def create_access_token(*, user_id: int, expires_at: datetime | None = None) -> str:
    settings = get_settings()
    expiry = expires_at or datetime.now(timezone.utc) + timedelta(hours=settings.jwt_expire_hours)
    payload = {"sub": str(user_id), "exp": expiry}
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> int:
    settings = get_settings()
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    except jwt.ExpiredSignatureError as exc:
        raise AuthError("TOKEN_EXPIRED", "토큰이 만료되었습니다") from exc
    except jwt.PyJWTError as exc:
        raise AuthError("INVALID_TOKEN", "유효하지 않은 토큰입니다") from exc
    return int(payload["sub"])
```

- [ ] **Step 4: security 테스트 통과 확인**

Run: `cd backend && uv run pytest tests/test_security.py -v`
Expected: PASS (5 passed)

- [ ] **Step 5: 시드 테스트 통과 확인 (Task 9 검증)**

Run: `cd backend && uv run pytest tests/test_seed.py -v`
Expected: PASS (4 passed)

- [ ] **Step 6: 전체 테스트 확인**

Run: `cd backend && uv run pytest -v`
Expected: PASS — 실패 0 (누적 테스트 수는 진행에 따라 늘어난다)

- [ ] **Step 7: 커밋**

```bash
git add backend/
git commit -m "feat(backend): add password hashing, JWT, and idempotent seed data"
```

---

## Task 11: 인증 dependency + `/auth` 라우터

**Files:**
- Create: `backend/app/deps.py`, `backend/app/schemas/__init__.py`, `backend/app/schemas/auth.py`, `backend/app/routers/__init__.py`, `backend/app/routers/auth.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_auth.py`

- [ ] **Step 1: 실패하는 테스트 작성**

`backend/tests/test_auth.py`:

```python
from app.seed import seed_all


async def test_login_returns_token_and_user(client, db_session):
    await seed_all(db_session)

    response = await client.post(
        "/api/v1/auth/login",
        json={"email": "user1@skon.example", "password": "skon1234!"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["token_type"] == "bearer"
    assert payload["access_token"]
    assert payload["user"]["email"] == "user1@skon.example"
    assert payload["user"]["role"] == "EMPLOYEE"
    assert "password_hash" not in payload["user"]


async def test_login_with_wrong_password_returns_401(client, db_session):
    await seed_all(db_session)

    response = await client.post(
        "/api/v1/auth/login",
        json={"email": "user1@skon.example", "password": "nope"},
    )

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "INVALID_CREDENTIALS"


async def test_login_with_unknown_email_returns_401(client, db_session):
    await seed_all(db_session)

    response = await client.post(
        "/api/v1/auth/login",
        json={"email": "ghost@skon.example", "password": "skon1234!"},
    )

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "INVALID_CREDENTIALS"


async def test_me_requires_authentication(client, db_session):
    await seed_all(db_session)

    response = await client.get("/api/v1/auth/me")

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "MISSING_CREDENTIALS"


async def test_me_returns_current_user(client, db_session):
    await seed_all(db_session)
    login = await client.post(
        "/api/v1/auth/login",
        json={"email": "manager1@skon.example", "password": "skon1234!"},
    )
    token = login.json()["access_token"]

    response = await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    body = response.json()
    assert body["email"] == "manager1@skon.example"
    assert body["role"] == "MANAGER"
    assert body["department_name"] == "배터리연구소"


async def test_me_rejects_malformed_token(client, db_session):
    await seed_all(db_session)

    response = await client.get("/api/v1/auth/me", headers={"Authorization": "Bearer nonsense"})

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "INVALID_TOKEN"
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `cd backend && uv run pytest tests/test_auth.py -v`
Expected: FAIL — 모든 테스트가 404 (라우터 없음)

- [ ] **Step 3: 스키마 구현**

빈 파일: `backend/app/schemas/__init__.py`

`backend/app/schemas/auth.py`:

```python
from pydantic import BaseModel, EmailStr

from app.enums import UserRole


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class UserOut(BaseModel):
    id: int
    email: str
    name: str
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
```

`EmailStr`을 쓰려면 의존성 추가:

```bash
cd backend && uv add "pydantic[email]"
```

- [ ] **Step 4: dependency 구현**

`backend/app/deps.py`:

```python
from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.errors import AuthError, ForbiddenError
from app.models import User
from app.security import decode_access_token

DbSession = Annotated[AsyncSession, Depends(get_db)]


async def get_principal(request: Request, session: DbSession) -> User:
    """JWT 또는 API Key로 인증한다. Phase 1은 JWT 분기만 구현한다."""
    header = request.headers.get("Authorization")
    if not header or not header.lower().startswith("bearer "):
        raise AuthError("MISSING_CREDENTIALS", "인증 정보가 없습니다")

    user_id = decode_access_token(header.split(" ", 1)[1].strip())
    user = await session.get(User, user_id)
    if user is None or not user.is_active:
        raise AuthError("INVALID_TOKEN", "유효하지 않은 토큰입니다")

    request.state.scopes = None  # None = 전 권한 (JWT). Phase 4에서 API Key 스코프가 채운다.
    return user


CurrentUser = Annotated[User, Depends(get_principal)]


def require_role(*roles: str):
    async def checker(user: CurrentUser) -> User:
        if user.role not in roles:
            raise ForbiddenError("FORBIDDEN_ROLE", "권한이 없습니다")
        return user

    return checker
```

- [ ] **Step 5: 라우터 구현**

빈 파일: `backend/app/routers/__init__.py`

`backend/app/routers/auth.py`:

```python
from fastapi import APIRouter
from sqlalchemy import select

from app.deps import CurrentUser, DbSession
from app.errors import AuthError
from app.models import Department, User
from app.schemas.auth import LoginRequest, LoginResponse, UserOut
from app.security import create_access_token, verify_password

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


async def _to_user_out(session, user: User) -> UserOut:
    department = await session.get(Department, user.department_id)
    return UserOut(
        id=user.id,
        email=user.email,
        name=user.name,
        employee_no=user.employee_no,
        position_code=user.position_code,
        role=user.role,
        department_id=user.department_id,
        department_name=department.name if department else "",
        manager_id=user.manager_id,
    )


@router.post("/login", response_model=LoginResponse)
async def login(payload: LoginRequest, session: DbSession) -> LoginResponse:
    user = (
        await session.execute(select(User).where(User.email == payload.email))
    ).scalar_one_or_none()
    if user is None or not user.is_active or not verify_password(payload.password, user.password_hash):
        raise AuthError("INVALID_CREDENTIALS", "이메일 또는 비밀번호가 올바르지 않습니다")

    return LoginResponse(
        access_token=create_access_token(user_id=user.id),
        user=await _to_user_out(session, user),
    )


@router.get("/me", response_model=UserOut)
async def me(user: CurrentUser, session: DbSession) -> UserOut:
    return await _to_user_out(session, user)
```

- [ ] **Step 6: main.py 갱신**

`backend/app/main.py` 전체 교체:

```python
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.config import get_settings
from app.db import SessionLocal, engine
from app.errors import register_error_handlers
from app.models import Base
from app.routers import auth
from app.seed import seed_all


@asynccontextmanager
async def lifespan(_: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    if get_settings().seed_on_startup:
        async with SessionLocal() as session:
            await seed_all(session)
    yield
    await engine.dispose()


app = FastAPI(
    title="SK온 출장시스템 API",
    version="1.0.0",
    docs_url="/docs",
    lifespan=lifespan,
)
register_error_handlers(app)
app.include_router(auth.router)


@app.get("/api/v1/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
```

- [ ] **Step 7: 테스트 통과 확인**

Run: `cd backend && uv run pytest -v`
Expected: PASS — 실패 0 (누적 테스트 수는 진행에 따라 늘어난다)

- [ ] **Step 8: 백엔드 수동 확인**

```bash
cd backend && uv run uvicorn app.main:app --reload --port 8000
```
별도 터미널에서:
```bash
curl -s localhost:8000/api/v1/health
curl -s -X POST localhost:8000/api/v1/auth/login -H 'Content-Type: application/json' \
  -d '{"email":"user1@skon.example","password":"skon1234!"}'
```
Expected: `{"status":"ok"}` / `access_token`과 `user` 객체가 담긴 JSON. `http://localhost:8000/docs` 도 열릴 것.

- [ ] **Step 9: 커밋**

```bash
git add backend/
git commit -m "feat(backend): add JWT auth dependency and /auth endpoints"
```

---

## Task 12: 프론트엔드 스캐폴드 + 디자인 토큰

**Files:**
- Create: `frontend/` (SvelteKit 프로젝트), `frontend/src/app.css`, `frontend/svelte.config.js`, `frontend/vite.config.ts`, `frontend/src/routes/+layout.ts`
- Copy: `assets/skon-logo.png` → `frontend/static/skon-logo.png`

- [ ] **Step 1: SvelteKit 프로젝트 생성**

```bash
npx sv create frontend --template minimal --types ts --no-add-ons --install npm
cd frontend
npm i -D @sveltejs/adapter-static tailwindcss @tailwindcss/vite
npm i pretendard
```

- [ ] **Step 2: adapter-static 설정**

`frontend/svelte.config.js`:

```javascript
import adapter from '@sveltejs/adapter-static';
import { vitePreprocess } from '@sveltejs/vite-plugin-svelte';

export default {
	preprocess: vitePreprocess(),
	kit: {
		adapter: adapter({ fallback: 'index.html' }),
		alias: { $lib: 'src/lib' }
	}
};
```

`frontend/src/routes/+layout.ts`:

```typescript
export const ssr = false;
export const prerender = false;
```

- [ ] **Step 3: vite proxy 설정**

`frontend/vite.config.ts`:

```typescript
import { sveltekit } from '@sveltejs/kit/vite';
import tailwindcss from '@tailwindcss/vite';
import { defineConfig } from 'vite';

export default defineConfig({
	plugins: [tailwindcss(), sveltekit()],
	server: {
		port: 5173,
		proxy: {
			'/api': { target: 'http://localhost:8000', changeOrigin: true }
		}
	}
});
```

- [ ] **Step 4: DESIGN.md 토큰 이식**

`frontend/src/app.css`:

```css
@import 'tailwindcss';
@import 'pretendard/dist/web/variable/pretendardvariable.css';

@theme {
	/* DESIGN.md colors — primary만 SK온 레드로 치환 */
	--color-primary: #ea002c;
	--color-primary-active: #c40024;
	--color-primary-disabled: #f7ccd4;
	--color-error: #c13515;
	--color-error-hover: #b32505;
	--color-ink: #222222;
	--color-body: #3f3f3f;
	--color-muted: #6a6a6a;
	--color-muted-soft: #929292;
	--color-hairline: #dddddd;
	--color-hairline-soft: #ebebeb;
	--color-border-strong: #c1c1c1;
	--color-canvas: #ffffff;
	--color-surface-soft: #f7f7f7;
	--color-surface-strong: #f2f2f2;
	--color-legal-link: #428bff;

	/* DESIGN.md rounded */
	--radius-xs: 4px;
	--radius-sm: 8px;
	--radius-md: 14px;
	--radius-lg: 20px;
	--radius-xl: 32px;

	/* DESIGN.md spacing */
	--spacing-xxs: 2px;
	--spacing-xs: 4px;
	--spacing-sm: 8px;
	--spacing-md: 12px;
	--spacing-base: 16px;
	--spacing-lg: 24px;
	--spacing-xl: 32px;
	--spacing-xxl: 48px;
	--spacing-section: 64px;

	/* Cereal 대체 — 한글 지원 */
	--font-sans: 'Pretendard Variable', Pretendard, -apple-system, system-ui, sans-serif;

	/* DESIGN.md 단일 그림자 티어 */
	--shadow-float:
		rgba(0, 0, 0, 0.02) 0 0 0 1px, rgba(0, 0, 0, 0.04) 0 2px 6px 0, rgba(0, 0, 0, 0.1) 0 4px 8px 0;
}

/* DESIGN.md typography 스케일 */
@utility text-display-xl {
	font-size: 28px;
	font-weight: 700;
	line-height: 1.43;
}
@utility text-display-lg {
	font-size: 22px;
	font-weight: 500;
	line-height: 1.18;
	letter-spacing: -0.44px;
}
@utility text-display-md {
	font-size: 21px;
	font-weight: 700;
	line-height: 1.43;
}
@utility text-display-sm {
	font-size: 20px;
	font-weight: 600;
	line-height: 1.2;
	letter-spacing: -0.18px;
}
@utility text-rating {
	font-size: 64px;
	font-weight: 700;
	line-height: 1.1;
	letter-spacing: -1px;
}
@utility text-title-md {
	font-size: 16px;
	font-weight: 600;
	line-height: 1.25;
}
@utility text-title-sm {
	font-size: 16px;
	font-weight: 500;
	line-height: 1.25;
}
@utility text-body-md {
	font-size: 16px;
	font-weight: 400;
	line-height: 1.5;
}
@utility text-body-sm {
	font-size: 14px;
	font-weight: 400;
	line-height: 1.43;
}
@utility text-caption {
	font-size: 14px;
	font-weight: 500;
	line-height: 1.29;
}
@utility text-caption-sm {
	font-size: 13px;
	font-weight: 400;
	line-height: 1.23;
}
@utility text-badge {
	font-size: 11px;
	font-weight: 600;
	line-height: 1.18;
}
@utility text-nav-link {
	font-size: 16px;
	font-weight: 600;
	line-height: 1.25;
}
@utility text-button-md {
	font-size: 16px;
	font-weight: 500;
	line-height: 1.25;
}
@utility text-button-sm {
	font-size: 14px;
	font-weight: 500;
	line-height: 1.29;
}

body {
	background-color: var(--color-canvas);
	color: var(--color-ink);
	font-family: var(--font-sans);
}
```

- [ ] **Step 5: 로고 배치 및 루트 레이아웃**

```bash
cp assets/skon-logo.png frontend/static/skon-logo.png
```

`frontend/src/routes/+layout.svelte`:

```svelte
<script lang="ts">
	import '../app.css';

	let { children } = $props();
</script>

{@render children()}
```

`frontend/src/routes/+page.svelte`:

```svelte
<main class="mx-auto max-w-[1280px] px-8 py-16">
	<h1 class="text-display-xl">SK온 출장시스템</h1>
	<p class="text-body-md mt-4 text-muted">기반 골격 동작 확인용 화면입니다.</p>
	<button class="mt-6 h-12 rounded-sm bg-primary px-6 text-button-md text-white">기본 CTA</button>
</main>
```

- [ ] **Step 6: 개발 서버 확인**

```bash
cd frontend && npm run dev
```
브라우저에서 `http://localhost:5173` 열기.
Expected: Pretendard 폰트로 "SK온 출장시스템" 28px 굵게, 아래 SK 레드(#EA002C) 버튼.

- [ ] **Step 7: 커밋**

```bash
git add frontend/
git commit -m "feat(frontend): scaffold SvelteKit with DESIGN.md tokens and SK red primary"
```

---

## Task 13: 기본 UI 컴포넌트

**Files:**
- Create: `frontend/src/lib/components/Button.svelte`, `TextInput.svelte`, `Badge.svelte`, `Card.svelte`

- [ ] **Step 1: Button 구현**

`frontend/src/lib/components/Button.svelte`:

```svelte
<script lang="ts">
	import type { Snippet } from 'svelte';

	type Variant = 'primary' | 'secondary' | 'tertiary' | 'pill';

	let {
		variant = 'primary',
		type = 'button',
		disabled = false,
		full = false,
		onclick,
		children
	}: {
		variant?: Variant;
		type?: 'button' | 'submit';
		disabled?: boolean;
		full?: boolean;
		onclick?: (event: MouseEvent) => void;
		children: Snippet;
	} = $props();

	const base = 'inline-flex items-center justify-center transition-colors disabled:cursor-not-allowed';
	const variants: Record<Variant, string> = {
		primary:
			'h-12 rounded-sm bg-primary px-6 text-button-md text-white hover:bg-primary-active disabled:bg-primary-disabled',
		secondary:
			'h-12 rounded-sm border border-ink bg-canvas px-6 text-button-md text-ink hover:bg-surface-soft disabled:border-border-strong disabled:text-muted-soft',
		tertiary: 'text-button-md text-ink underline-offset-4 hover:underline disabled:text-muted-soft',
		pill: 'rounded-full bg-primary px-5 py-2.5 text-button-sm text-white hover:bg-primary-active disabled:bg-primary-disabled'
	};
</script>

<button
	{type}
	{disabled}
	{onclick}
	class="{base} {variants[variant]} {full ? 'w-full' : ''}"
>
	{@render children()}
</button>
```

- [ ] **Step 2: TextInput 구현**

`frontend/src/lib/components/TextInput.svelte`:

```svelte
<script lang="ts">
	let {
		label,
		value = $bindable(''),
		type = 'text',
		placeholder = '',
		error = '',
		id = crypto.randomUUID()
	}: {
		label: string;
		value?: string;
		type?: 'text' | 'email' | 'password' | 'date' | 'number';
		placeholder?: string;
		error?: string;
		id?: string;
	} = $props();
</script>

<div class="flex flex-col gap-2">
	<label for={id} class="text-caption text-muted">{label}</label>
	<input
		{id}
		{type}
		{placeholder}
		bind:value
		class="h-14 rounded-sm border bg-canvas px-3 text-body-md text-ink outline-none focus:border-2 focus:border-ink {error
			? 'border-error'
			: 'border-hairline'}"
	/>
	{#if error}
		<p class="text-caption-sm text-error">{error}</p>
	{/if}
</div>
```

- [ ] **Step 3: Badge 구현**

`frontend/src/lib/components/Badge.svelte`:

```svelte
<script lang="ts">
	import type { Snippet } from 'svelte';

	type Tone = 'neutral' | 'primary' | 'success' | 'danger';

	let { tone = 'neutral', children }: { tone?: Tone; children: Snippet } = $props();

	const tones: Record<Tone, string> = {
		neutral: 'bg-canvas text-ink shadow-float',
		primary: 'bg-primary text-white',
		success: 'bg-ink text-white',
		danger: 'bg-error text-white'
	};
</script>

<span class="inline-flex items-center rounded-full px-2.5 py-1 text-badge {tones[tone]}">
	{@render children()}
</span>
```

- [ ] **Step 4: Card 구현**

`frontend/src/lib/components/Card.svelte`:

```svelte
<script lang="ts">
	import type { Snippet } from 'svelte';

	let {
		padded = true,
		hoverable = false,
		children
	}: { padded?: boolean; hoverable?: boolean; children: Snippet } = $props();
</script>

<div
	class="rounded-md border border-hairline bg-canvas {padded ? 'p-6' : ''} {hoverable
		? 'transition-shadow hover:shadow-float'
		: ''}"
>
	{@render children()}
</div>
```

- [ ] **Step 5: 빌드 확인**

Run: `cd frontend && npm run check && npm run build`
Expected: 타입 에러 0, 빌드 성공

- [ ] **Step 6: 커밋**

```bash
git add frontend/
git commit -m "feat(frontend): add base UI components from DESIGN.md tokens"
```

---

## Task 14: API 클라이언트 + 인증 스토어

**Files:**
- Create: `frontend/src/lib/api/client.ts`, `frontend/src/lib/api/types.ts`, `frontend/src/lib/stores/auth.svelte.ts`
- Test: `frontend/src/lib/api/client.test.ts`

- [ ] **Step 1: vitest 설치**

```bash
cd frontend && npm i -D vitest
```

`frontend/package.json`의 `scripts`에 추가:

```json
"test": "vitest run"
```

- [ ] **Step 2: 실패하는 테스트 작성**

`frontend/src/lib/api/client.test.ts`:

```typescript
import { describe, expect, it, vi } from 'vitest';
import { ApiError, request } from './client';

function jsonResponse(body: unknown, status = 200): Response {
	return new Response(JSON.stringify(body), {
		status,
		headers: { 'Content-Type': 'application/json' }
	});
}

describe('request', () => {
	it('attaches bearer token when provided', async () => {
		const fetchMock = vi.fn().mockResolvedValue(jsonResponse({ ok: true }));

		await request('/api/v1/auth/me', { token: 'abc', fetchImpl: fetchMock });

		const [, init] = fetchMock.mock.calls[0];
		expect(init.headers.Authorization).toBe('Bearer abc');
	});

	it('omits authorization header without token', async () => {
		const fetchMock = vi.fn().mockResolvedValue(jsonResponse({ ok: true }));

		await request('/api/v1/health', { fetchImpl: fetchMock });

		const [, init] = fetchMock.mock.calls[0];
		expect(init.headers.Authorization).toBeUndefined();
	});

	it('throws ApiError carrying the unified error body', async () => {
		const fetchMock = vi.fn().mockResolvedValue(
			jsonResponse(
				{ error: { code: 'INVALID_CREDENTIALS', message: '이메일 또는 비밀번호가 올바르지 않습니다', field: null } },
				401
			)
		);

		await expect(request('/api/v1/auth/login', { fetchImpl: fetchMock })).rejects.toMatchObject({
			status: 401,
			code: 'INVALID_CREDENTIALS',
			message: '이메일 또는 비밀번호가 올바르지 않습니다'
		});
	});

	it('falls back to a generic ApiError when body is not our shape', async () => {
		const fetchMock = vi.fn().mockResolvedValue(new Response('gateway down', { status: 502 }));

		const error = await request('/api/v1/health', { fetchImpl: fetchMock }).catch((e) => e);

		expect(error).toBeInstanceOf(ApiError);
		expect(error.status).toBe(502);
		expect(error.code).toBe('UNKNOWN');
	});
});
```

- [ ] **Step 3: 테스트 실패 확인**

Run: `cd frontend && npm test`
Expected: FAIL — `Failed to resolve import "./client"`

- [ ] **Step 4: 타입 정의**

`frontend/src/lib/api/types.ts`:

```typescript
export type UserRole = 'EMPLOYEE' | 'MANAGER' | 'ADMIN';

export interface User {
	id: number;
	email: string;
	name: string;
	employee_no: string;
	position_code: string;
	role: UserRole;
	department_id: number;
	department_name: string;
	manager_id: number | null;
}

export interface LoginResponse {
	access_token: string;
	token_type: string;
	user: User;
}
```

- [ ] **Step 5: 클라이언트 구현**

`frontend/src/lib/api/client.ts`:

```typescript
export class ApiError extends Error {
	constructor(
		public status: number,
		public code: string,
		message: string,
		public field: string | null = null
	) {
		super(message);
		this.name = 'ApiError';
	}
}

interface RequestOptions {
	method?: 'GET' | 'POST' | 'PATCH' | 'DELETE';
	body?: unknown;
	token?: string | null;
	fetchImpl?: typeof fetch;
}

export async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
	const { method = 'GET', body, token, fetchImpl = fetch } = options;

	const headers: Record<string, string> = { 'Content-Type': 'application/json' };
	if (token) headers.Authorization = `Bearer ${token}`;

	const response = await fetchImpl(path, {
		method,
		headers,
		body: body === undefined ? undefined : JSON.stringify(body)
	});

	if (!response.ok) {
		let code = 'UNKNOWN';
		let message = `요청이 실패했습니다 (${response.status})`;
		let field: string | null = null;
		try {
			const parsed = await response.json();
			if (parsed?.error?.code) {
				code = parsed.error.code;
				message = parsed.error.message;
				field = parsed.error.field ?? null;
			}
		} catch {
			// 본문이 JSON이 아니면 기본 메시지를 유지한다
		}
		throw new ApiError(response.status, code, message, field);
	}

	if (response.status === 204) return undefined as T;
	return (await response.json()) as T;
}
```

- [ ] **Step 6: 인증 스토어 구현**

`frontend/src/lib/stores/auth.svelte.ts`:

```typescript
import { request } from '$lib/api/client';
import type { LoginResponse, User } from '$lib/api/types';

const TOKEN_KEY = 'skon.token';

class AuthStore {
	token = $state<string | null>(null);
	user = $state<User | null>(null);
	loading = $state(true);

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
		const result = await request<LoginResponse>('/api/v1/auth/login', {
			method: 'POST',
			body: { email, password }
		});
		this.token = result.access_token;
		this.user = result.user;
		localStorage.setItem(TOKEN_KEY, result.access_token);
	}

	clear(): void {
		this.token = null;
		this.user = null;
		localStorage.removeItem(TOKEN_KEY);
	}
}

export const auth = new AuthStore();
```

- [ ] **Step 7: 테스트 통과 확인**

Run: `cd frontend && npm test`
Expected: PASS (4 passed)

- [ ] **Step 8: 커밋**

```bash
git add frontend/
git commit -m "feat(frontend): add api client with unified error parsing and auth store"
```

---

## Task 15: 앱 셸 (top-nav)

**Files:**
- Create: `frontend/src/lib/components/AppShell.svelte`

- [ ] **Step 1: AppShell 구현**

`frontend/src/lib/components/AppShell.svelte`:

```svelte
<script lang="ts">
	import { page } from '$app/state';
	import { goto } from '$app/navigation';
	import { auth } from '$lib/stores/auth.svelte';
	import type { Snippet } from 'svelte';

	let { children }: { children: Snippet } = $props();

	const tabs = [
		{ href: '/trips', label: '출장' },
		{ href: '/expenses', label: '정산' },
		{ href: '/developers', label: '개발자' }
	];

	function isActive(href: string): boolean {
		return page.url.pathname.startsWith(href);
	}

	function signOut(): void {
		auth.clear();
		goto('/login');
	}
</script>

<div class="min-h-screen bg-canvas">
	<header class="flex h-20 items-center border-b border-hairline px-8">
		<a href="/" class="flex items-center">
			<img src="/skon-logo.png" alt="SK온 출장시스템" class="h-8 w-auto" />
		</a>

		<nav class="mx-auto flex items-center gap-8">
			{#each tabs as tab (tab.href)}
				<a
					href={tab.href}
					class="pb-1 text-nav-link {isActive(tab.href)
						? 'border-b-2 border-ink text-ink'
						: 'text-muted hover:text-ink'}"
				>
					{tab.label}
				</a>
			{/each}
		</nav>

		<div class="flex items-center gap-4">
			{#if auth.user}
				<span class="text-body-sm text-muted">{auth.user.name} · {auth.user.department_name}</span>
				<button
					onclick={signOut}
					class="h-10 rounded-full border border-hairline px-4 text-button-sm text-ink hover:shadow-float"
				>
					로그아웃
				</button>
			{/if}
		</div>
	</header>

	<main class="mx-auto max-w-[1280px] px-8 py-12">
		{@render children()}
	</main>
</div>
```

- [ ] **Step 2: 빌드 확인**

Run: `cd frontend && npm run check`
Expected: 타입 에러 0

- [ ] **Step 3: 커밋**

```bash
git add frontend/
git commit -m "feat(frontend): add app shell with top-nav and product tabs"
```

---

## Task 16: 로그인 화면 + 라우트 가드

**Files:**
- Create: `frontend/src/routes/login/+page.svelte`
- Modify: `frontend/src/routes/+layout.svelte`, `frontend/src/routes/+page.svelte`

- [ ] **Step 1: 로그인 화면 구현**

`frontend/src/routes/login/+page.svelte`:

```svelte
<script lang="ts">
	import { goto } from '$app/navigation';
	import { ApiError } from '$lib/api/client';
	import Button from '$lib/components/Button.svelte';
	import TextInput from '$lib/components/TextInput.svelte';
	import { auth } from '$lib/stores/auth.svelte';

	let email = $state('user1@skon.example');
	let password = $state('skon1234!');
	let errorMessage = $state('');
	let submitting = $state(false);

	async function handleSubmit(event: SubmitEvent): Promise<void> {
		event.preventDefault();
		errorMessage = '';
		submitting = true;
		try {
			await auth.login(email, password);
			await goto('/');
		} catch (error) {
			errorMessage =
				error instanceof ApiError ? error.message : '로그인 중 문제가 발생했습니다';
		} finally {
			submitting = false;
		}
	}
</script>

<div class="flex min-h-screen items-center justify-center bg-canvas px-6">
	<div class="w-full max-w-[400px]">
		<img src="/skon-logo.png" alt="SK온" class="mb-8 h-9 w-auto" />
		<h1 class="text-display-lg">출장시스템 로그인</h1>
		<p class="mt-2 text-body-sm text-muted">사내 계정으로 로그인하세요.</p>

		<form class="mt-8 flex flex-col gap-4" onsubmit={handleSubmit}>
			<TextInput label="이메일" type="email" bind:value={email} placeholder="name@skon.example" />
			<TextInput label="비밀번호" type="password" bind:value={password} />

			{#if errorMessage}
				<p class="text-caption-sm text-error">{errorMessage}</p>
			{/if}

			<Button type="submit" full disabled={submitting}>
				{submitting ? '로그인 중…' : '로그인'}
			</Button>
		</form>

		<p class="mt-6 text-caption-sm text-muted">
			데모 계정 — 사원 user1@skon.example / 팀장 manager1@skon.example / 관리자 admin@skon.example ·
			비밀번호 공통 skon1234!
		</p>
	</div>
</div>
```

- [ ] **Step 2: 레이아웃에 가드 적용**

`frontend/src/routes/+layout.svelte` 전체 교체:

```svelte
<script lang="ts">
	import '../app.css';
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import { page } from '$app/state';
	import AppShell from '$lib/components/AppShell.svelte';
	import { auth } from '$lib/stores/auth.svelte';

	let { children } = $props();

	const PUBLIC_PATHS = ['/login'];
	let restored = $state(false);

	// 복원은 마운트 시 한 번만. $effect 안에서 호출하면 auth 상태 변경이
	// 다시 effect를 트리거해 무한 루프가 된다.
	onMount(async () => {
		await auth.restore();
		restored = true;
	});

	$effect(() => {
		if (!restored) return;
		if (auth.user === null && !PUBLIC_PATHS.includes(page.url.pathname)) {
			goto('/login');
		}
	});
</script>

{#if !restored}
	<div class="flex min-h-screen items-center justify-center text-body-sm text-muted">
		불러오는 중…
	</div>
{:else if PUBLIC_PATHS.includes(page.url.pathname)}
	{@render children()}
{:else if auth.user}
	<AppShell>
		{@render children()}
	</AppShell>
{/if}
```

- [ ] **Step 3: 대시보드 placeholder 교체**

`frontend/src/routes/+page.svelte` 전체 교체:

```svelte
<script lang="ts">
	import Badge from '$lib/components/Badge.svelte';
	import Card from '$lib/components/Card.svelte';
	import { auth } from '$lib/stores/auth.svelte';
</script>

<h1 class="text-display-xl">안녕하세요, {auth.user?.name}님</h1>
<p class="mt-2 text-body-md text-muted">
	{auth.user?.department_name} · {auth.user?.role}
</p>

<div class="mt-8 grid grid-cols-1 gap-4 md:grid-cols-3">
	<Card>
		<p class="text-caption text-muted">진행 중 출장</p>
		<p class="mt-2 text-display-md">Phase 2에서 연결</p>
		<div class="mt-3"><Badge>준비 중</Badge></div>
	</Card>
	<Card>
		<p class="text-caption text-muted">결재 대기</p>
		<p class="mt-2 text-display-md">Phase 2에서 연결</p>
	</Card>
	<Card>
		<p class="text-caption text-muted">미정산 출장</p>
		<p class="mt-2 text-display-md">Phase 3에서 연결</p>
	</Card>
</div>
```

- [ ] **Step 4: 커밋**

```bash
git add frontend/
git commit -m "feat(frontend): add login page, route guard, and dashboard placeholder"
```

---

## Task 17: 운영 컨테이너 4종 + ingress

**Files:**
- Create: `backend/Dockerfile`, `backend/.dockerignore`, `frontend/Dockerfile`, `frontend/.dockerignore`, `frontend/nginx.conf`, `ingress/nginx.conf`, `docker-compose.yml`

- [ ] **Step 1: 백엔드 Dockerfile**

`backend/Dockerfile`:

```dockerfile
FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

COPY app ./app
RUN uv sync --frozen --no-dev

EXPOSE 8000
CMD ["uv", "run", "--no-dev", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

`backend/.dockerignore`:

```
.venv
tests
.pytest_cache
__pycache__
.env
```

- [ ] **Step 2: 프론트엔드 Dockerfile + 정적 서빙 설정**

`frontend/nginx.conf`:

```nginx
server {
    listen 80;
    root /usr/share/nginx/html;
    index index.html;

    location / {
        try_files $uri $uri/ /index.html;
    }
}
```

`frontend/Dockerfile`:

```dockerfile
FROM node:22-alpine AS build
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
RUN npm run build

FROM nginx:1.27-alpine
COPY --from=build /app/build /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
```

`frontend/.dockerignore`:

```
node_modules
build
.svelte-kit
```

- [ ] **Step 3: ingress 설정**

`ingress/nginx.conf`:

```nginx
server {
    listen 80;
    client_max_body_size 10m;

    location /api/ {
        proxy_pass http://backend:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location = /docs {
        proxy_pass http://backend:8000/docs;
    }

    location = /openapi.json {
        proxy_pass http://backend:8000/openapi.json;
    }

    location / {
        proxy_pass http://frontend:80;
        proxy_set_header Host $host;
    }
}
```

- [ ] **Step 4: 운영 compose**

`docker-compose.yml`:

```yaml
services:
  db:
    image: postgres:16-alpine
    environment:
      POSTGRES_USER: skon
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:-skon}
      POSTGRES_DB: skon
    volumes:
      - skon_pgdata:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U skon -d skon"]
      interval: 5s
      timeout: 3s
      retries: 10
    restart: unless-stopped

  backend:
    build: ./backend
    environment:
      DATABASE_URL: postgresql+asyncpg://skon:${POSTGRES_PASSWORD:-skon}@db:5432/skon
      JWT_SECRET: ${JWT_SECRET:-change-me-in-production}
      SEED_ON_STARTUP: "true"
    depends_on:
      db:
        condition: service_healthy
    healthcheck:
      test: ["CMD-SHELL", "python -c \"import urllib.request;urllib.request.urlopen('http://localhost:8000/api/v1/health')\""]
      interval: 10s
      timeout: 5s
      retries: 10
    restart: unless-stopped

  frontend:
    build: ./frontend
    depends_on:
      backend:
        condition: service_healthy
    restart: unless-stopped

  ingress:
    image: nginx:1.27-alpine
    ports:
      - "80:80"
    volumes:
      - ./ingress/nginx.conf:/etc/nginx/conf.d/default.conf:ro
    depends_on:
      - frontend
      - backend
    restart: unless-stopped

volumes:
  skon_pgdata:
```

`JWT_SECRET`은 운영에서 반드시 실제 값으로 주입해야 합니다. 기본값 `change-me-in-production`이 그대로 쓰이면 누구나 토큰을 위조할 수 있습니다. 운영 서버에는 `.env` 파일로 `JWT_SECRET`과 `POSTGRES_PASSWORD`를 지정하십시오 (이 파일은 `.gitignore`에 이미 포함되어 있습니다).

- [ ] **Step 5: 전체 스택 기동 확인**

```bash
docker compose up -d --build
docker compose ps
curl -s localhost/api/v1/health
curl -s -X POST localhost/api/v1/auth/login -H 'Content-Type: application/json' \
  -d '{"email":"user1@skon.example","password":"skon1234!"}'
```

Expected: 4개 서비스 모두 `running`(db·backend는 `healthy`), health가 `{"status":"ok"}`, 로그인이 `access_token` 반환. 브라우저에서 `http://localhost` 로그인 화면이 뜨고 로그인이 성공할 것.

- [ ] **Step 6: 정리**

```bash
docker compose down
```

- [ ] **Step 7: 커밋**

```bash
git add backend/Dockerfile backend/.dockerignore frontend/Dockerfile frontend/.dockerignore frontend/nginx.conf ingress/ docker-compose.yml
git commit -m "feat(deploy): add production Dockerfiles, nginx ingress, and 4-service compose"
```

---

## Task 18: Phase 1 통합 검증

**Files:**
- Create: `README.md`

- [ ] **Step 1: 전체 백엔드 테스트**

Run: `cd backend && uv run pytest -v`
Expected: PASS, 실패 0

- [ ] **Step 2: 전체 프론트 테스트 및 빌드**

Run: `cd frontend && npm test && npm run check && npm run build`
Expected: 테스트 PASS, 타입 에러 0, `build/` 생성

- [ ] **Step 3: 수동 시나리오 확인**

세 터미널에서:
```bash
docker compose -f docker-compose.dev.yml up -d db
cd backend && uv run uvicorn app.main:app --reload --port 8000
cd frontend && npm run dev
```

`http://localhost:5173` 에서 확인:

1. 미로그인 상태로 `/` 접근 → `/login` 으로 이동한다
2. `user1@skon.example` / `skon1234!` 로 로그인 성공 → 대시보드 이동, 상단바에 이름·부서 표시
3. 잘못된 비밀번호 → "이메일 또는 비밀번호가 올바르지 않습니다" 표시
4. 새로고침 → 로그인 상태 유지 (localStorage 복원)
5. 로그아웃 → `/login` 이동
6. 폰트가 Pretendard, 기본 CTA가 SK 레드 `#EA002C`
7. `http://localhost:8000/docs` 에서 `/auth/login`, `/auth/me` 노출

- [ ] **Step 4: README 작성**

`README.md`:

```markdown
# SK온 출장시스템

SK온 사내 출장시스템을 모사한 데모 웹 애플리케이션. 출장 신청부터 법인카드 기반 비용정산까지의 흐름을 보여주며, 동일한 API를 API Key로 외부 AI Agent가 호출할 수 있다.

- 설계: `docs/superpowers/specs/2026-08-12-skon-biztrip-web-design.md`
- 구현 계획: `docs/superpowers/plans/`

## 로컬 개발

DB만 컨테이너로 띄우고 백엔드·프론트는 호스트에서 실행한다.

```bash
docker compose -f docker-compose.dev.yml up -d db
docker exec skon-db-dev psql -U skon -d postgres -c "CREATE DATABASE skon_test OWNER skon;"  # 최초 1회

cd backend  && uv run uvicorn app.main:app --reload --port 8000
cd frontend && npm run dev   # http://localhost:5173
```

`/api` 요청은 vite proxy가 `localhost:8000` 으로 넘긴다.

## 테스트

```bash
cd backend  && uv run pytest
cd frontend && npm test && npm run check
```

## 배포

프론트엔드 · 백엔드 · DB · ingress 4개 컨테이너를 빌드해 기동한다. 노출 포트는 ingress `:80` 하나뿐이다.

```bash
docker compose up -d --build   # http://localhost
```

운영 서버에서는 `.env`로 `JWT_SECRET`과 `POSTGRES_PASSWORD`를 반드시 지정한다.

## 데모 계정

비밀번호는 모두 `skon1234!`

| 계정 | 역할 |
|---|---|
| `admin@skon.example` | ADMIN |
| `manager1@skon.example` | MANAGER |
| `user1@skon.example` | EMPLOYEE |

## 스택

SvelteKit 2 (adapter-static) · TailwindCSS v4 · FastAPI · SQLAlchemy 2.0 async · PostgreSQL 16 · nginx · Docker Compose
```

- [ ] **Step 5: 커밋**

```bash
git add README.md
git commit -m "docs: add README with local development instructions"
```

---

## Phase 1 완료 기준

- [ ] `uv run pytest` 전부 통과
- [ ] `npm test`, `npm run check`, `npm run build` 전부 통과
- [ ] Task 18 Step 3의 수동 시나리오 7개 전부 확인
- [ ] Task 17 Step 5의 4-컨테이너 기동 및 `http://localhost` 로그인 확인
- [ ] spec의 전체 테이블(16개)이 모델로 존재하고 `create_all`로 생성됨
- [ ] 시드 데이터가 spec 5.9의 수량과 일치

Phase 1이 끝나면 Phase 2(출장) plan을 작성한다.
