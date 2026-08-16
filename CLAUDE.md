# CLAUDE.md

SK온 사내 출장시스템을 모사한 데모 웹. 실제 회계·전표 처리는 하지 않고, 샘플 데이터로 화면과 API가 실제처럼 동작하는 것까지가 목표다. 핵심 메시지는 **사람이 화면에서 하는 일과 동일한 일을 AI Agent가 API Key로 수행할 수 있다**는 것 — 그래서 웹 UI와 외부 Agent가 물리적으로 같은 엔드포인트를 쓴다.

- 설계: `docs/superpowers/specs/2026-08-12-skon-biztrip-web-design.md`
- 구현 계획: `docs/superpowers/plans/` — Phase별로 하나씩. **작업 전 해당 Phase plan을 읽을 것.**
- 디자인 규칙: `DESIGN.md`

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
cd backend  && uv run pytest          # 116건
cd frontend && npm test               # 8건
cd frontend && npm run check          # 타입체크, 0 errors 유지

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

**ORM에 `relationship()`을 붙이지 않는다.** 의도치 않은 eager loading을 세 번 되돌린 이력이 있다. 이름 등이 필요하면 명시적 조인이나 `id.in_(...)` 일괄 조회를 쓴다. 목록 응답에서 행마다 헬퍼를 호출하면 N+1이 된다.

**`text-body` 클래스를 쓰지 않는다.** `--color-body` 때문에 Tailwind가 이걸 **색상** 유틸리티로 생성한다. 본문 타이포는 `text-body-md` / `text-body-sm`으로 명시한다. 에러가 나지 않고 조용히 틀린다.

**SecureContext 전용 API를 쓰지 않는다.** 운영은 평문 HTTP로 서빙되므로 `crypto.randomUUID()` 같은 API는 존재하지 않아 페이지 전체가 렌더에 실패한다. 로컬(localhost)에서는 멀쩡해 보여 발견이 늦다. 고유 id는 Svelte의 `$props.id()`를 쓴다.

**새 폼에는 중복 제출 가드를 넣는다.** 버튼의 `disabled`만으로는 `form.requestSubmit()` 경로를 막지 못한다. `handleSubmit` 첫 줄에 `if (submitting) return;`. 출장 신청·정산 제출은 멱등하지 않아 중복 POST가 곧 중복 레코드다.

## 테스트

- `db_session` 픽스처는 각 테스트를 외부 트랜잭션 + savepoint로 감싸 롤백한다. `conftest.py`에서 **루프 스코프·`join_transaction_mode="create_savepoint"`·테스트 스키마 가드는 건드리지 말 것** — 셋 다 리뷰를 거쳐 고정된 값이고, 각각 이벤트루프 불일치·테스트 간 데이터 누수·운영 스키마 삭제를 막는다.
- 순수 함수(코드 검증, 상태전이, 자동매칭)는 DB 없이 단위테스트한다.
- 프론트 테스트는 `client.ts`와 `auth.svelte.ts`만 다룬다. jsdom을 추가하지 말고 `vi.stubGlobal`을 쓴다.

## 마이그레이션

Alembic을 쓰지 않는다. `app.cli init-db`가 없는 테이블만 만들고 기존 테이블의 컬럼 변경은 반영하지 않는다. 스키마를 바꾸면 해당 테이블을 지우고 `init-db`를 다시 돌린다.

## 다음 Phase로 넘어간 항목

`docs/superpowers/plans/2026-08-12-phase1-foundation.md` 말미의 "이월" 절들에 Phase 2에서 반드시 처리할 것들이 정리돼 있다. 특히 `authRequest` 래퍼와 전역 401 처리는 **첫 인증 화면을 만들 때 함께** 해야 한다.

## 환경 주의

Docker Engine 20.10.9 이하에서는 백엔드가 `can't start new thread`로 죽는다(기본 seccomp에 `clone3` 없음, 메모리와 무관). `docker-compose.old-docker.yml`을 함께 지정해 우회하거나 Docker를 업그레이드한다.
