# CLAUDE.md

SK온 사내 출장시스템을 모사한 데모 웹. 실제 회계·전표 처리는 하지 않고, 샘플 데이터로 화면과 API가 실제처럼 동작하는 것까지가 목표다. 핵심 메시지는 **사람이 화면에서 하는 일과 동일한 일을 AI Agent가 API Key로 수행할 수 있다**는 것 — 그래서 웹 UI와 외부 Agent가 물리적으로 같은 엔드포인트를 쓴다.

- 설계: `docs/superpowers/specs/2026-08-12-skon-biztrip-web-design.md`
- 구현 계획: `docs/superpowers/plans/` — Phase별로 하나씩. **작업 전 해당 Phase plan을 읽을 것.**
- Phase 현황·이월 항목: `docs/phase-status.md` — **새 Phase를 시작하기 전에 읽을 것.**
- 디자인 규칙: `DESIGN.md`

Phase 1(기반)·Phase 2(출장)·Phase 3(정산)·Phase 4(개발자) 완료. 다음은 Phase 5(운영).

## 명령어

```bash
# 개발 (DB는 외부 운영 DB에 접속. backend/.env 필요)
cd backend && uv run uvicorn app.main:app --reload --port 8000
cd frontend && npm run dev            # :5173, /api → :8000 프록시

# 스키마·데이터 준비 (수동, 필요할 때만)
cd backend && uv run python -m app.cli check      # 접속 확인만
cd backend && uv run python -m app.cli init-db    # 스키마 + 없는 테이블 생성
cd backend && uv run python -m app.cli seed       # 데모 데이터 (멱등)

# 테스트
cd backend  && uv run pytest          # 486건
cd frontend && npm test               # 60건
cd frontend && npm run check          # 타입체크, 0 errors / 0 warnings 유지

# 배포 (3서비스 — DB는 스택 밖)
docker compose -p skon-prod up -d --build   # http://localhost
```

`uv`는 `~/.local/bin/uv`. 시스템 python3는 3.11이므로 **항상 `uv run`을 거칠 것.**

## 구조

```
backend/app/  routers/ → services/ → models/   (3계층, 라우터에 로직 두지 않음)
frontend/src/ lib/components/ · lib/api/ · lib/stores/ · routes/
ingress/      nginx.conf (운영 리버스 프록시)
```

## 반드시 지킬 것

**DB는 이 프로젝트가 띄우지 않는다.** 이미 운영 중인 PostgreSQL에 접속하며 `DB_HOST`·`DB_PORT`·`DB_USER`·`DB_PASSWORD`·`DB_NAME`·`DB_SCHEMA`만 주입한다. 접속은 매 커넥션마다 `search_path`를 `DB_SCHEMA` **하나로만** 고정한다 — `public`을 fallback으로 남기면 언퀄리파이드 DDL이 다른 스키마로 새어나가고, 특히 테스트의 `drop_all`이 운영 테이블을 지울 수 있다.

**기동 시 스키마·데이터를 절대 자동으로 건드리지 않는다.** `create_all`도 시드도 `app/cli.py`의 명령을 사람이 실행할 때만 일어난다. 운영 DB에 붙어 있으므로 자동 DDL은 남의 데이터를 위협한다. `lifespan`에 DDL을 되살리지 말 것.

**테스트는 별도 스키마에서 돈다.** `TEST_DB_SCHEMA`(기본 `skon_test`)가 `DB_SCHEMA`와 같으면 픽스처가 실행을 거부한다. 매 세션 `drop_all`을 돌리기 때문이다. 이 가드를 제거하지 말 것.

**스키마명은 DDL에 문자열 보간된다.** 바인드 파라미터로 넘길 수 없어서다. 그래서 `app/config.py`의 `assert_safe_identifier`로 평범한 식별자만 통과시킨다. 새로 스키마명을 받는 경로를 만들면 같은 검증을 통과시킬 것.

**공통코드는 문자열로 저장한다.** `trip.transport_code = 'AIR'`처럼 코드값 문자열을 쓰고 `code.id` FK를 쓰지 않는다. API가 `"transport_code": "AIR"`로 읽혀 Agent가 그대로 쓸 수 있게 하려는 의도다. 대가로 DB 무결성이 없으므로 **모든 쓰기 경로가 `app/services/codes.py`의 검증을 통과해야 한다.**

**상태·역할 enum은 DB로 빼지 않는다.** `TripStatus` · `ExpenseReportStatus` · `UserRole` · `ApiKeyScope` 등은 분기 로직에 박히므로 `app/enums.py`의 Python Enum으로 고정한다. 공통코드 테이블은 관리자가 편집하는 드롭다운 값 전용이다.

**에러는 단일 계약을 지킨다.** 모든 에러 응답이 `{"error": {"code", "message", "field"}}`다. `code`는 기계가 읽는 도메인 코드이며, 특히 409 상태전이 충돌에서 Agent가 재시도 여부를 판단하는 근거다. 새 예외는 `app/errors.py`의 `AppError` 계열로 만든다.

**ORM에 `relationship()`을 붙이지 않는다.** 의도치 않은 eager loading을 세 번 되돌린 이력이 있다. 이름 등이 필요하면 명시적 조인이나 `id.in_(...)` 일괄 조회를 쓴다. 목록 응답에서 행마다 헬퍼를 호출하면 N+1이 된다. `services/trips.py`의 `build_list_items`가 그 패턴이고, 쿼리 수를 고정하는 테스트가 붙어 있다.

**상태 전이는 `assert_transition_allowed` 하나만 통과한다.** 적법성(`trip_status.py`)과 수행 주체(`trip_rules.py`의 `TRANSITION_ACTOR`)를 따로 부를 수 있게 열어두면 언젠가 한쪽만 부르고, 그 실패는 **fail-open**이다 — 출장을 볼 수 있는 결재자가 신청자 전용 전이를 통과한다. `services/trips.py`가 `assert_trip_transition`·`assert_trip_approver`를 직접 import하지 않는 것은 그래서다. 새 전이를 추가하면 `TRANSITION_ACTOR`에도 넣어야 하며, 빠뜨리면 import 시점에 `RuntimeError`로 죽는다.

**정산서 전이도 `assert_expense_transition_allowed` 하나만 통과한다.** 출장과 같은 구조이며 이유도 같다 — 적법성(`EXPENSE_ALLOWED_TRANSITIONS`)과 주체(`EXPENSE_TRANSITION_ACTOR`)를 따로 부를 수 있게 열어두면 언젠가 한쪽만 부르고 그 실패는 fail-open이다. 전이를 추가하고 주체를 빠뜨리면 임포트 시점에 `RuntimeError`로 죽는다.

**`COMPLETED → SETTLED`는 `settle_trip_for_report`만 수행한다.** 이 함수는 `assert_system_transition`(사용자 주체 전이를 거부하는 통로)을 지나고 `record_transition`을 남기며 **commit하지 않는다** — 정산서 승인과 같은 트랜잭션에서 끝나야 "정산은 승인됐는데 출장은 COMPLETED"인 상태가 생기지 않는다. 반대로 사용자 경로(`assert_transition_allowed`)는 이 전이를 계속 거부한다.

**정산 합계는 서비스가 재계산한다.** `expense_report.total_amount_krw`는 비정규화 값이고 `is_excluded` 항목은 빼고 더한다(`_recalc_total`). 항목 상한(`MAX_ITEM_AMOUNT`)만으로는 항목 여러 개로 컬럼을 넘길 수 있으므로 합계 상한(`MAX_REPORT_TOTAL`)도 함께 본다. 자릿수는 `quantize(0.01)`로 고정해 응답 문자열 모양이 갈리지 않게 한다.

**금액은 컬럼 상한까지 서비스가 막는다.** `Numeric(14, 2)`를 넘는 값을 통과시키면 flush에서 Postgres numeric overflow가 나고 catch-all 핸들러에 걸려 **500**이 된다. Agent는 5xx를 재시도하므로 절대 성공할 수 없는 요청에 재시도 루프가 걸린다. `trip_rules.MAX_ESTIMATED_COST`가 그 방어선이다.

**스코프 검사는 `get_principal` 안 한 곳에서만 한다.** 엔드포인트마다 `Depends(require_scope(...))`를 붙이는 방식은 쓰지 않는다 — 빠뜨리면 그 엔드포인트만 조용히 전권이 되는 fail-open이다. 필요 스코프는 `app/services/api_scopes.py`의 `SCOPE_REQUIREMENTS` 표가 유일하게 선언하며, `main.py`가 임포트 시점에 `assert_scope_table_complete(app)`로 표와 실제 라우트를 **양방향** 대조한다. **새 엔드포인트를 만들면 같은 커밋에서 표에 넣어야 하고, 빠뜨리면 앱이 뜨지 않는다.** 표에 없는 경로는 통과가 아니라 403이다.

**`request.state.scopes`는 `UNRESTRICTED` 센티널과 동일성으로만 비교한다.** `if not scopes`나 `getattr(request.state, "scopes", None)`로 바꾸면 스코프가 빈 키가 전권을 얻는다. 인증 라우트가 0개로 잡히는 상황도 통과가 아니라 예외다 — 그건 "검사할 게 없다"가 아니라 라우트 탐지가 깨졌다는 뜻이고, 실제로 한 번 그렇게 됐다(fastapi 0.141은 `include_router` 라우트를 `_IncludedRouter`로 감싸므로 `iter_route_contexts`로 펼쳐야 한다).

**키 관리 API는 JWT 전용이다.** `app/deps.py`의 `JwtOnlyUser`를 쓴다. API Key로 새 키를 발급할 수 있으면 `cards:read` 키 하나로 전권 키를 찍어낼 수 있어 스코프 제한 전체가 무의미해진다. 이 의존성은 `get_principal`을 거쳐 오므로 소진 가드가 해당 라우트도 함께 검사한다.

**평문 API Key는 발급 응답에만 존재한다.** DB에는 SHA-256만 남는다(`ApiKeyOut`에는 `key` 필드가 없고 `ApiKeyCreated`에만 있다). 목록·상세 응답에 평문을 싣는 어떤 변경도 거부한다.

**`AsyncSession`을 `asyncio.gather`로 병렬 사용하지 않는다.** 같은 세션에 `execute`를 병렬로 걸면 `InvalidRequestError`가 난다. 여러 조회를 묶어야 하면 `IN` 절로 쿼리 수를 줄인다 (`services/codes.py`의 `validate_codes`가 그 예 — 그룹 수와 무관하게 쿼리 2개).

**`text-body` 클래스를 쓰지 않는다.** `--color-body` 때문에 Tailwind가 이걸 **색상** 유틸리티로 생성한다. 본문 타이포는 `text-body-md` / `text-body-sm`으로 명시한다. 에러가 나지 않고 조용히 틀린다.

**SecureContext 전용 API를 쓰지 않는다.** 운영은 평문 HTTP로 서빙되므로 `crypto.randomUUID()` 같은 API는 존재하지 않아 페이지 전체가 렌더에 실패한다. 로컬(localhost)에서는 멀쩡해 보여 발견이 늦다. 고유 id는 Svelte의 `$props.id()`를 쓴다.

**새 폼에는 중복 제출 가드를 넣는다.** 버튼의 `disabled`만으로는 `form.requestSubmit()` 경로를 막지 못한다. `handleSubmit` 첫 줄에 `if (submitting) return;`. 출장 신청·정산 제출은 멱등하지 않아 중복 POST가 곧 중복 레코드다.

**`$props.id()`는 컴포넌트당 한 번만 호출할 수 있다.** 입력이 여러 개인 컴포넌트는 베이스 id 하나를 받아 접미사를 붙인다 (`FilterBar.svelte` 참고). 두 번 부르면 컴파일 에러다.

**인증이 필요한 프론트 호출은 전부 `authRequest`를 쓴다.** raw `request`는 미인증 호출(`login`)과 토큰을 명시적으로 넘기는 곳(`restore`)뿐이다. `{ token: auth.token }`를 손으로 붙이면 하나만 빠뜨려도 조용히 미인증 요청이 나가고, 그 401은 진짜 인증 실패와 구분되지 않는다. `authRequest`가 401에서 세션을 정리하고 `auth.onUnauthorized`를 호출한다 — 이 콜백은 `+layout.svelte`가 주입한다. 스토어가 `$app/navigation`을 직접 import하면 vitest가 모듈을 못 불러온다.

## 테스트

- `db_session` 픽스처는 각 테스트를 외부 트랜잭션 + savepoint로 감싸 롤백한다. `conftest.py`에서 **루프 스코프·`join_transaction_mode="create_savepoint"`·테스트 스키마 가드는 건드리지 말 것** — 셋 다 리뷰를 거쳐 고정된 값이고, 각각 이벤트루프 불일치·테스트 간 데이터 누수·운영 스키마 삭제를 막는다.
- 객체 생성은 `tests/factories.py`를 쓴다. `seeded`(데모 시드 적재)와 `login_as(email)`(Authorization 헤더) 픽스처도 `conftest.py`에 있다.
- 순수 함수(코드 검증, 상태전이, 자동매칭)는 DB 없이 단위테스트한다.
- 프론트 테스트는 순수 모듈(`client.ts`·`auth.svelte.ts`·`nav.ts`·`format.ts`·`trips.ts`)만 다룬다. jsdom을 추가하지 말고 `vi.stubGlobal`을 쓴다.
- **가드를 추가하면 mutation으로 확인한다.** 그 줄을 지웠을 때 테스트가 실패하지 않으면 그 테스트는 아무것도 지키지 않는 것이다. Phase 2에서 이 방식으로 세 개의 구멍을 찾았다 — 삭제 가능 상태, 금액 상한, 전이 주체. 파일을 고친 뒤 반드시 `grep`으로 편집이 실제로 반영됐는지 확인할 것: `backend/`에서 맨 `python3`는 pyenv 때문에 죽고, heredoc 안에서는 그 실패가 조용하다.
- **파생 테스트 데이터가 검사 대상 상수에서 나오면 안 된다.** `sorted(set(TripStatus) - EDITABLE_STATUSES)`처럼 쓰면 상수를 넓히는 버그와 테스트가 함께 움직여 통과한다. 리터럴에서 파생시킬 것.

## 마이그레이션

Alembic을 쓰지 않는다. `app.cli init-db`가 없는 테이블만 만들고 기존 테이블의 컬럼 변경은 반영하지 않는다. 스키마를 바꾸면 해당 테이블을 지우고 `init-db`를 다시 돌린다.

## 다음 Phase로 넘어간 항목

`docs/phase-status.md`의 "Phase 4에서 넘어온 항목" 절을 **Phase 5 착수 전에** 읽을 것. 요약하면:

- `/admin/*`을 만들면 `SCOPE_REQUIREMENTS`에 `ApiKeyScope.ADMIN`으로 등록해야 한다. 빠뜨리면 기동 실패다.
- Admin 삭제는 `IntegrityError`를 409 `HAS_DEPENDENTS`로 변환해야 한다. 안 하면 500이 되고 Agent가 재시도한다.
- 비밀번호 엔드포인트를 만들면 요청 스키마에서 72바이트를 막아야 한다(bcrypt 5.x는 자르지 않고 던지며, 한글은 24자면 넘는다).
- **브라우저 수동 시나리오 23개 미확인.** Phase 4 화면 2개(`/settings/api-keys`·`/developers`)는 렌더 확인이 전혀 안 됐다 — 타입체크·빌드·curl만 통과한 상태다.
- `last_used_at`을 API Key 요청마다 갱신(UPDATE + COMMIT)한다. 트래픽이 늘면 스로틀로 옮긴다.
- 키 발급·폐기는 `activity_log`에 남지 않는다(`EntityType`에 멤버가 없다).
- 출장 상세가 정산서 존재 여부를 목록 `size=100` 조회로 판단한다.
- 항목의 FC/CC override는 마스터 비활성화 시점에 재검증되지 않는다.

## 환경 주의

Docker Engine 20.10.9 이하에서는 백엔드가 `can't start new thread`로 죽는다(기본 seccomp에 `clone3` 없음, 메모리와 무관). `docker-compose.old-docker.yml`을 함께 지정해 우회하거나 Docker를 업그레이드한다.
