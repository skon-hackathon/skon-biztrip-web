# SK온 출장시스템 — 설계 문서

- 작성일: 2026-08-12
- 상태: 승인됨 (브레인스토밍 완료)

## 1. 목적과 성격

SK온의 사내 출장시스템을 모사한 데모 웹 애플리케이션. 실제 회계·전표 처리는 하지 않으며, DB에 적재된 샘플 데이터를 기반으로 화면과 API가 실제처럼 동작하는 것까지가 목표다.

이 프로젝트의 핵심 메시지는 두 가지다.

1. 출장 등록부터 법인카드 기반 비용정산까지의 흐름이 화면에서 자연스럽게 이어진다.
2. **사람이 화면에서 하는 일과 동일한 일을 AI Agent가 API Key로 수행할 수 있다.** 웹 UI가 호출하는 엔드포인트와 Agent가 호출하는 엔드포인트가 물리적으로 같다.

## 2. 기술 스택

| 영역 | 선택 |
|---|---|
| 프론트엔드 | SvelteKit 2 / Svelte 5 (runes), `adapter-static` (SPA, `ssr = false`) |
| 스타일 | TailwindCSS v4 — DESIGN.md 토큰을 `@theme`에 이식 |
| 폰트 | Pretendard (로컬 번들) |
| 백엔드 | Python 3.12, FastAPI, SQLAlchemy 2.0 (async / asyncpg), Pydantic v2 |
| 패키지 관리 | 백엔드 `uv` (`pyproject.toml` + `uv.lock`), 프론트 `npm` |
| DB | PostgreSQL 16 — **이 프로젝트가 띄우지 않고 외부 운영 DB에 접속** |
| Ingress | nginx 1.27 |
| 배포 | Docker + docker-compose, 3개 서비스 (DB는 스택 밖) |

### 데이터베이스 접속 정책

**DB는 이 프로젝트의 배포 단위에 포함되지 않는다.** 이미 운영 중인 PostgreSQL에 접속하며, `DB_HOST` · `DB_PORT` · `DB_USER` · `DB_PASSWORD` · `DB_NAME` · `DB_SCHEMA`를 환경변수로 주입한다.

접속은 매 커넥션마다 `search_path`를 `DB_SCHEMA` **하나로만** 고정한다(`connect_args={"server_settings": {"search_path": ...}}`). `public`을 fallback으로 남기지 않는 것이 핵심이다 — 남기면 언퀄리파이드 DDL·질의가 의도치 않게 다른 스키마로 새어나가고, 특히 테스트의 `drop_all`이 운영 테이블을 지울 수 있다.

스키마명은 바인드 파라미터로 넘길 수 없어 DDL에 문자열로 보간되므로, `assert_safe_identifier`가 평범한 식별자(`^[A-Za-z_][A-Za-z0-9_]*$`)만 통과시킨다.

### 마이그레이션 정책

Alembic을 도입하지 않는다. 다만 **기동 시 자동 DDL·자동 시드를 하지 않는다** — 운영 DB에 붙어 있으므로 남의 데이터를 위협하기 때문이다. 스키마 생성과 데모 데이터 적재는 `app/cli.py`의 명령을 사람이 명시적으로 실행할 때만 일어난다.

```
uv run python -m app.cli check      # 접속 확인만
uv run python -m app.cli init-db    # 스키마 + 없는 테이블 생성
uv run python -m app.cli seed       # 데모 데이터 (멱등)
```

`init-db`는 없는 테이블만 만들고 기존 테이블의 컬럼 변경은 반영하지 않는다. 스키마를 바꾸면 해당 테이블을 지우고 다시 돌린다.

테스트는 같은 서버의 **별도 스키마**(`TEST_DB_SCHEMA`, 기본 `skon_test`)에서 돌며, 매 실행마다 `drop_all` 후 재생성한다. `DB_SCHEMA`와 같으면 픽스처가 실행을 거부한다.

## 3. 디자인 시스템 적용

`DESIGN.md`는 Airbnb 디자인 시스템 분석 문서다. 이 문서의 타이포·스페이싱·라운드·엘리베이션·반응형 규칙을 그대로 따르되, **primary 색만 SK온 브랜드 레드로 치환**한다.

### 색 치환

| 토큰 | DESIGN.md 원본 | 본 프로젝트 |
|---|---|---|
| `primary` | `#ff385c` | `#EA002C` |
| `primary-active` | `#e00b41` | `#c40024` |
| `primary-disabled` | `#ffd1da` | `#f7ccd4` |

그 외 색 토큰(ink, body, muted, hairline, surface 계열, semantic)은 DESIGN.md 값을 그대로 사용한다. Luxe / Plus 서브브랜드 토큰은 사용하지 않는다.

### 폰트

Airbnb Cereal VF는 라이선스 폰트라 사용할 수 없다. DESIGN.md가 지목한 대체는 Inter이나 한글이 필요하므로 **Pretendard**를 사용한다 (Inter 메트릭 호환 + 한글 지원). 라틴·한글을 한 벌로 처리하며 웹폰트를 로컬 번들한다. 타이포 스케일(`display-xl` 28/700 ~ `uppercase-tag` 8/700)은 DESIGN.md 표를 그대로 Tailwind 유틸리티로 만든다.

### 컴포넌트 매핑

Airbnb 컴포넌트를 출장 도메인에 대응시킨다. 이것이 "DESIGN.md를 적용한다"의 실체다.

| DESIGN.md 컴포넌트 | 출장시스템 용도 |
|---|---|
| `search-bar-pill` + `search-orb` | 출장 목록 상단 필터 pill — 어디로 / 언제 / 상태, 우측 SK레드 검색 orb |
| `property-card` | 출장 카드 (목적지·기간·비용, 상태 뱃지 floating) |
| `guest-favorite-badge` | 상태 뱃지 (승인대기 · 승인 · 반려 · 정산완료) |
| `reservation-card` | 출장 상세 우측 sticky 액션 카드 (상신 / 승인 / 정산 진입) |
| `rating-display` (64px) | 정산 총액 표시 — 시스템에서 유일하게 큰 타이포 순간 |
| `date-picker-day` | 출장 기간 선택 캘린더 |
| `top-nav` 3-product tab | 출장 / 정산 / 개발자 |
| `text-input`, `button-primary` | 폼 전반 |

엘리베이션은 DESIGN.md대로 단일 그림자 티어만 사용한다. 반응형·터치타겟·붕괴 전략도 DESIGN.md 표를 따른다 (카드 1-up, sticky 우측 레일 → 하단 바).

로고는 `assets/skon-logo.png`를 top-nav 좌측에 배치한다.

## 4. 시스템 구조 및 배포

### 운영 — 3개 컨테이너

| 서비스 | 이미지 | 역할 |
|---|---|---|
| `ingress` | `nginx:1.27-alpine` | 유일한 노출 포트 `:80`. `/` → frontend, `/api/`·`/docs`·`/openapi.json` → backend |
| `frontend` | 멀티스테이지 (`node:22` 빌드 → `nginx:1.27-alpine` 서빙) | SvelteKit 정적 산출물 |
| `backend` | `python:3.12-slim` + uv | FastAPI / uvicorn, `:8000` (내부 전용) |

DB는 스택에 포함되지 않는다. 기동 순서는 `depends_on` + healthcheck로 backend → frontend → ingress. 백엔드의 DB 접속 정보는 `.env`로 주입하며, 값이 없으면 compose가 기동을 거부한다.

배포 절차: 개발 산출물을 기준으로 운영 서버에서 `docker compose up -d --build` (또는 레지스트리 push 후 `up -d`).

### 로컬 개발 — 컨테이너 없이

```bash
cp backend/.env.example backend/.env                # 접속 정보 입력
cd backend  && uv run python -m app.cli init-db && uv run python -m app.cli seed   # 최초 1회
cd backend  && uv run uvicorn app.main:app --reload --port 8000
cd frontend && npm run dev                          # :5173
```

- 로컬에서도 외부 운영 DB에 접속한다. 개발용 DB 컨테이너는 두지 않는다.
- frontend `vite.config.ts`의 proxy가 `/api` → `http://localhost:8000`으로 넘긴다. 로컬에서는 vite proxy가 ingress 역할을 대신하므로 nginx를 띄우지 않는다.
- `backend/.env.example`이 템플릿이며, 운영 값은 compose `environment`로 주입한다.
- 접속 설정 확인은 `GET /api/v1/health/db` — host·database·current_schema를 돌려준다. `/api/v1/health`는 DB에 붙지 않는 liveness 체크로 컨테이너 healthcheck가 쓴다.
- Dockerfile은 로컬과 동일한 `uv.lock`을 사용해 의존성 드리프트를 막는다.

### 레이어 경계

백엔드는 `routers/` (HTTP·인증만) → `services/` (비즈니스 규칙) → `models/` (ORM) 3계층. 라우터에 비즈니스 로직을 두지 않는다. 자동매칭·코드검증·상태전이 같은 규칙은 서비스에 고립시켜 DB 없이 단위테스트가 가능하도록 한다.

## 5. 데이터 모델

### 5.1 조직 · 사용자

| 테이블 | 핵심 컬럼 |
|---|---|
| `department` | `id`, `code`, `name`, `parent_id` (자기참조) |
| `user` | `id`, `email` (uniq), `password_hash` (bcrypt), `name`, `employee_no`, `department_id`, `position_code`, `manager_id` (→ user), `role` (EMPLOYEE\|MANAGER\|ADMIN), `is_active` |

결재자는 `user.manager_id`로 자동 결정한다. 1단계 승인이므로 별도 결재선 테이블을 두지 않는다.

### 5.2 공통코드

| 테이블 | 핵심 컬럼 |
|---|---|
| `code_group` | `id`, `group_code` (uniq), `name`, `description`, `is_active` |
| `code` | `id`, `group_id`, `code` (그룹 내 uniq), `name`, `sort_order`, `is_active`, `extra` JSONB |

초기 그룹 9개:

| group_code | 내용 |
|---|---|
| `TRIP_PURPOSE` | 출장목적 (고객미팅 / 기술지원 / 교육 / 컨퍼런스 / 감사 / 기타) |
| `DESTINATION_TYPE` | 국내 / 해외 |
| `TRANSPORT` | 항공 / 철도 / 버스 / 자가용 / 렌터카 |
| `ACCOMMODATION` | 호텔 / 레지던스 / 사택 / 기타 |
| `EXPENSE_CATEGORY` | 정산 비목 |
| `MERCHANT_CATEGORY` | 카드 가맹점 업종 |
| `POSITION` | 직급 |
| `COUNTRY` | 국가 (`extra`에 통화·지역 보유) |
| `CURRENCY` | 통화 |

**참조 방식.** 업무 테이블은 `code.id` 정수 FK가 아니라 **코드값 문자열**을 저장한다 (예: `trip.transport_code = 'AIR'`). 이유는 두 가지다.

- API/JSON이 `"transport_code": "AIR"`로 읽혀 Agent가 그대로 사용할 수 있다. 정수 id라면 Agent가 매번 조회 후 치환해야 한다.
- `GET /api/v1/codes/{group_code}`로 유효값을 스스로 발견할 수 있어 Agent 자기탐색이 가능하다.

대가로 DB 레벨 FK 무결성을 포기한다. 대신 서비스 레이어의 공용 검증기 `validate_code(group_code, value)`를 모든 쓰기 경로가 통과하도록 강제하고, 이 검증기를 단위테스트로 커버한다.

**공통코드로 관리하지 않는 값.** `TripStatus`, `ExpenseReportStatus`, `UserRole`, `ApiKeyScope`, `NotificationType`, `ActivityAction`. 모두 상태전이·인가 분기에 코드로 박히는 값이라 DB에서 변경하면 로직이 조용히 깨진다. Python `Enum` 상수로 고정한다.

### 5.3 Fund Center / Cost Center

| 테이블 | 핵심 컬럼 | 의미 |
|---|---|---|
| `fund_center` | `id`, `code` (uniq, 예 `FC1010`), `name`, `department_id` (nullable), `is_active` | 비용처리 부서 |
| `cost_center` | `id`, `code` (uniq, 예 `CC2030`), `name`, `department_id` (nullable), `is_active` | 비용사용 부서 |

공통코드 그룹에 넣지 않고 전용 마스터로 분리한 이유: `department_id`라는 실제 관계를 갖고 있어, `code.extra` JSONB에 부서 id를 문자열로 넣으면 조인도 불가능하고 무결성도 사라진다. Admin 화면에서는 공통코드 관리와 같은 위치에 나란히 배치한다.

### 5.4 출장

| 테이블 | 핵심 컬럼 |
|---|---|
| `trip` | `id`, `trip_no` (BT-2026-0001), `user_id`, `title`, `purpose_code`, `purpose_detail` (text), `destination_type_code`, `country_code`, `city`, `start_date`, `end_date`, `transport_code`, `accommodation_code`, `cost_center_code`, `estimated_cost`, `status`, `approver_id`, `submitted_at`, `approved_at`, `reject_reason`, `created_at`, `updated_at` |

`purpose_code`는 공통코드(`TRIP_PURPOSE`) 선택값이고 `purpose_detail`은 자유 서술이다. 둘 다 필수.

`TripStatus` 전이:

```
DRAFT → SUBMITTED → APPROVED → COMPLETED → SETTLED
              ↓
           REJECTED → DRAFT   (반려 후 재상신)
```

전이 트리거:

| 전이 | 주체 | 조건 |
|---|---|---|
| `DRAFT → SUBMITTED` | 신청자 | 필수 항목 검증 통과 |
| `SUBMITTED → APPROVED` / `REJECTED` | `approver_id` 본인 (= 신청자의 `manager_id`) | — |
| `REJECTED → DRAFT` | 신청자 | 재상신을 위한 되돌림 |
| `APPROVED → COMPLETED` | 신청자 | `end_date`가 오늘 이전일 것 |
| `COMPLETED → SETTLED` | **시스템 자동** | 해당 출장의 `expense_report`가 `APPROVED`로 전이될 때 |

`cost_center_code`는 출장 신청 시 필수 입력이다.

### 5.5 법인카드 · 정산

| 테이블 | 핵심 컬럼 |
|---|---|
| `corporate_card` | `id`, `user_id`, `card_no_masked` (`5678-****-****-1234`), `brand`, `is_active` |
| `card_transaction` | `id`, `card_id`, `approved_at` (timestamptz), `merchant_name`, `merchant_category_code`, `amount` Numeric(14,2), `currency_code`, `amount_krw`, `is_cancelled` |
| `expense_report` | `id`, `report_no`, `trip_id` (uniq), `user_id`, `status`, `fund_center_code`, `cost_center_code`, `total_amount_krw`, `approver_id`, `submitted_at`, `approved_at`, `reject_reason` |
| `expense_item` | `id`, `report_id`, `card_transaction_id` (nullable, 리포트 내 uniq), `expense_category_code`, `amount_krw`, `memo`, `is_excluded`, `fund_center_code` (nullable), `cost_center_code` (nullable) |

`ExpenseReportStatus`: `DRAFT → SUBMITTED → APPROVED | REJECTED`. 반려 시 `DRAFT`로 되돌린다. 결재자는 출장의 `approver_id`와 동일하다.

정산서는 `trip.status`가 `APPROVED` 또는 `COMPLETED`일 때만 생성할 수 있다 (`trip_id`가 uniq이므로 출장당 1건). 그 외 상태에서 생성 시도하면 409를 반환한다. 정산서가 `APPROVED`가 되면 해당 출장이 자동으로 `SETTLED`로 전이된다.

**FC/CC 계층.** `expense_report`가 기본값을 갖고, `expense_item`의 FC/CC는 nullable override다. 비어 있으면 리포트 값을 사용한다(`coalesce`). 한 출장 안에서 비용을 다른 부서로 떨구는 실무 케이스를 위해 이 계층이 필요하다. `cost_center_code`는 출장에서 정산서로 승계되며 수정 가능하다. 정산서 제출 시 FC/CC가 비어 있으면 검증 실패로 처리한다.

**출장↔거래 연결.** `card_transaction`에는 `trip_id`를 두지 않는다. 연결은 오직 `expense_item`이 담당한다. 조인 경로가 하나뿐이라 "이 거래가 어디에 붙었는가"가 모호해질 여지가 없다.

### 5.6 자동매칭 규칙

`services/matching.py`의 순수 함수로 구현한다 (DB 접근 없음, 입력은 trip + 거래 리스트).

후보 조건:

- 해당 사용자 카드의 거래일 것
- `approved_at`이 `start_date - 1일 ~ end_date + 1일` 범위 안일 것
- `is_cancelled = false`
- 다른 제출완료(`SUBMITTED` 이상) 리포트에 포함되지 않았을 것

각 후보에 매칭 사유 문자열(`출장기간 내 승인`, `출발 전일 교통비` 등)을 붙여 UI와 API 양쪽에 동일하게 노출한다. 사용자(또는 Agent)가 체크박스로 포함/제외를 확정한다.

### 5.7 API Key

| 테이블 | 핵심 컬럼 |
|---|---|
| `api_key` | `id`, `user_id`, `name`, `key_prefix` (`sk_live_xxxxxxxx`, 목록 표시용), `key_hash` (SHA-256), `scopes` text[], `last_used_at`, `expires_at`, `revoked_at`, `created_at` |

**평문 키는 발급 응답에서 단 한 번만 반환하고 DB에는 저장하지 않는다.** 사용자가 그 자리에서 복사하지 않으면 복구가 불가능하며, UI에서 이 점을 명시적으로 경고한다.

### 5.8 알림 · 타임라인

| 테이블 | 핵심 컬럼 |
|---|---|
| `notification` | `id`, `user_id`, `type`, `title`, `body`, `link_url`, `is_read`, `created_at` |
| `activity_log` | `id`, `entity_type` (TRIP\|EXPENSE_REPORT), `entity_id`, `actor_id`, `action`, `from_status`, `to_status`, `memo`, `created_at` |

모든 상태 전이는 서비스 레이어의 단일 지점을 통과하며, 그 지점에서 `activity_log`와 `notification`을 함께 기록한다. 웹 경로로 들어오든 API Key 경로로 들어오든 이력이 누락될 수 없다.

### 5.9 시드 데이터

멱등 시드(이미 존재하면 skip).

- 부서 4개
- 사용자 14명 (ADMIN 1, MANAGER 3, EMPLOYEE 10)
- 공통코드 9그룹 약 60건
- Fund Center 6건, Cost Center 10건
- 법인카드 14장
- 카드거래 약 700건 (최근 6개월, 국내·해외 혼합)
- 출장 40건 (상태별 고른 분포), 그중 12건은 정산서까지 존재

## 6. 화면

```
/login
/                      대시보드 (내 출장 현황, 결재 대기, 미정산, 최근 알림)
/trips                 목록 + 필터
/trips/new             신청
/trips/[id]            상세 + 타임라인
/trips/[id]/edit
/approvals             결재함 (MANAGER)
/cards                 내 법인카드 + 거래내역
/expenses              정산 목록
/expenses/[id]         정산서 작성 (자동매칭 패널 + 항목 테이블 + FC/CC)
/notifications
/settings/api-keys     발급 · 조회 · 폐기
/developers            API 가이드 (curl 예제, 스코프 표, /docs 링크)
/admin/codes           공통코드 그룹 · 코드
/admin/centers         Fund Center / Cost Center (탭)
/admin/users
/admin/departments
/admin/cards
```

정산 화면은 리포트 헤더에 FC/CC 셀렉트 2개, 항목 테이블 각 행에 "부서 지정" 컬럼(기본은 `상속` 표시, 클릭 시 override)을 둔다.

## 7. API

베이스 경로 `/api/v1`. 단일 라우터 트리에 이중 인증을 적용한다 (웹과 Agent가 동일 엔드포인트 사용).

```
POST   /auth/login                          → {access_token}
GET    /auth/me
GET    /codes  ·  GET /codes/{group_code}
GET    /fund-centers  ·  GET /cost-centers
GET    /trips  ·  POST /trips
GET|PATCH|DELETE /trips/{id}
POST   /trips/{id}/submit | /approve | /reject | /complete
GET    /cards  ·  GET /card-transactions
GET    /expenses  ·  POST /expenses            (trip_id로 생성)
GET    /expenses/{id}
GET    /expenses/{id}/match-candidates         ← 자동매칭 후보 + 사유
POST   /expenses/{id}/items  ·  PATCH|DELETE /expense-items/{id}
POST   /expenses/{id}/submit | /approve | /reject
GET    /notifications  ·  POST /notifications/{id}/read
/admin/*                                       CRUD (role=ADMIN)
```

### 인증

단일 dependency `get_principal()`이 두 경로를 모두 처리한다.

- `Authorization: Bearer <JWT>` → 해당 사용자의 전 권한 (role 범위 내). 만료 8시간, refresh token 없음(만료 시 재로그인)
- `X-API-Key: sk_live_...` → SHA-256 해시로 조회 → 키의 `scopes`로 권한 축소

스코프: `trips:read`, `trips:write`, `expenses:read`, `expenses:write`, `cards:read`, `admin`. 각 엔드포인트에 필요 스코프를 선언하며 JWT는 전부 통과한다. 키 검증 성공 시 `last_used_at`을 갱신한다. 폐기·만료된 키는 401을 반환한다.

데모 목적이므로 rate limit과 IP 제한은 구현하지 않는다.

### 에러 형식

모든 에러 응답이 동일한 바디를 갖는다.

```json
{"error": {"code": "TRIP_NOT_SUBMITTABLE", "message": "이미 상신된 출장입니다", "field": null}}
```

`app/errors.py`에 예외 클래스를 정의하고 핸들러 1개로 처리한다.

| 상태 | 의미 |
|---|---|
| 400 | 입력 검증 실패 (코드값 오류 포함) |
| 401 | 인증 실패 (토큰/키 없음·만료·폐기) |
| 403 | 권한 또는 스코프 부족 |
| 404 | 리소스 없음 (타인 리소스 접근도 404로 처리) |
| 409 | 상태전이 위반, 참조 중인 마스터 데이터 삭제 시도 |
| 422 | Pydantic 스키마 위반 |

409 응답에 도메인 코드를 실어야 Agent가 재시도 여부를 판단할 수 있다.

**마스터 데이터 삭제.** `department`, `code_group`, `fund_center`, `cost_center`, `user`의 FK에는 `ondelete`를 걸지 않는다. 참조가 남은 채 삭제를 시도하면 PostgreSQL이 거부하는 것이 옳은 동작이기 때문이다. 다만 그대로 두면 `IntegrityError`가 통일 에러 핸들러의 catch-all로 떨어져 `500 INTERNAL_ERROR`가 되므로, Admin CRUD의 삭제 엔드포인트는 `IntegrityError`를 잡아 `ConflictError("HAS_DEPENDENTS", ...)` 즉 409로 변환한다. 또한 `CodeGroup`의 `cascade="all, delete-orphan"`은 ORM 객체 삭제에만 적용되므로, 삭제는 Core의 일괄 `delete()` 문이 아니라 `session.get()` + `session.delete()`로 수행해야 한다.

## 8. 테스트

- **단위 (DB 없음)** — `matching.py` 후보 산출, `validate_code`, 상태전이 표, FC/CC coalesce 규칙. 로직 무게가 여기에 몰려 있다.
- **통합 (pytest + httpx AsyncClient)** — 로컬 dev 컨테이너의 동일 Postgres 인스턴스 안에 `skon_test` 데이터베이스를 별도로 만들어 사용하며, 트랜잭션 롤백 fixture로 격리한다. JWT 경로와 API Key 경로 **양쪽에서 동일 시나리오**를 검증하고, 스코프 부족 403, 상태전이 위반 409, 타인 리소스 접근 404를 확인한다.
- **프론트 (vitest)** — 포맷터·매칭 요약 유틸 중심. 컴포넌트 테스트는 최소한으로.
- **제외** — E2E(Playwright). 데모 규모 대비 과하다.

## 9. 범위 밖

실제 전표·ERP 연동, 영수증 파일 업로드, 이메일 발송, rate limit, i18n, 다크모드, 여비규정 한도 자동계산, 통계 대시보드.

## 10. 구현 단계

구현 계획은 이 설계 문서를 기준으로 5단계로 분할한다.

1. **기반** — compose(dev/운영), FastAPI 골격, DB 모델·시드, 인증(JWT), SvelteKit + Tailwind 토큰·레이아웃·로그인
2. **출장** — 신청/목록/상세/수정, 결재함, 상태전이, 타임라인·알림
3. **정산** — 카드내역, 자동매칭, 정산서 작성/제출/결재, FC/CC
4. **개발자** — API Key 발급·폐기·스코프, `/developers` 가이드, OpenAPI 정리
5. **운영** — Admin(공통코드·센터·사용자·부서·카드), 4-컨테이너 이미지 빌드 및 기동 검증
