# CLAUDE.md

SK온 사내 출장시스템을 모사한 데모 웹. 실제 회계·전표 처리는 하지 않고, 샘플 데이터로 화면과 API가 실제처럼 동작하는 것까지가 목표다. 핵심 메시지는 **사람이 화면에서 하는 일과 동일한 일을 AI Agent가 API Key로 수행할 수 있다**는 것 — 그래서 웹 UI와 외부 Agent가 물리적으로 같은 엔드포인트를 쓴다.

- 설계: `docs/superpowers/specs/2026-08-12-skon-biztrip-web-design.md`
- 구현 계획: `docs/superpowers/plans/` — Phase별로 하나씩. **작업 전 해당 Phase plan을 읽을 것.**
- 디자인 규칙: `DESIGN.md`

## 명령어

```bash
# 개발 (DB만 컨테이너, 나머지는 호스트)
docker compose -f docker-compose.dev.yml -p skon-dev up -d db
cd backend && uv run uvicorn app.main:app --reload --port 8000
cd frontend && npm run dev            # :5173, /api → :8000 프록시

# 테스트
cd backend  && uv run pytest          # 105건
cd frontend && npm test               # 8건
cd frontend && npm run check          # 타입체크, 0 errors 유지

# 배포
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

**compose는 항상 `-p`를 붙인다.** 두 compose 파일이 같은 디렉터리에 있고 둘 다 `db` 서비스를 정의해서 기본 프로젝트명이 겹친다. `-p` 없이 실행한 `docker compose down`은 **개발 DB 컨테이너를 삭제한다.** 실제로 한 번 발생했다. Compose v2.0.0은 최상위 `name:`을 지원하지 않아 파일로는 막을 수 없다.

**공통코드는 문자열로 저장한다.** `trip.transport_code = 'AIR'`처럼 코드값 문자열을 쓰고 `code.id` FK를 쓰지 않는다. API가 `"transport_code": "AIR"`로 읽혀 Agent가 그대로 쓸 수 있게 하려는 의도다. 대가로 DB 무결성이 없으므로 **모든 쓰기 경로가 `app/services/codes.py`의 검증을 통과해야 한다.**

**상태·역할 enum은 DB로 빼지 않는다.** `TripStatus` · `ExpenseReportStatus` · `UserRole` · `ApiKeyScope` 등은 분기 로직에 박히므로 `app/enums.py`의 Python Enum으로 고정한다. 공통코드 테이블은 관리자가 편집하는 드롭다운 값 전용이다.

**에러는 단일 계약을 지킨다.** 모든 에러 응답이 `{"error": {"code", "message", "field"}}`다. `code`는 기계가 읽는 도메인 코드이며, 특히 409 상태전이 충돌에서 Agent가 재시도 여부를 판단하는 근거다. 새 예외는 `app/errors.py`의 `AppError` 계열로 만든다.

**ORM에 `relationship()`을 붙이지 않는다.** 의도치 않은 eager loading을 세 번 되돌린 이력이 있다. 이름 등이 필요하면 명시적 조인이나 `id.in_(...)` 일괄 조회를 쓴다. 목록 응답에서 행마다 헬퍼를 호출하면 N+1이 된다.

**`text-body` 클래스를 쓰지 않는다.** `--color-body` 때문에 Tailwind가 이걸 **색상** 유틸리티로 생성한다. 본문 타이포는 `text-body-md` / `text-body-sm`으로 명시한다. 에러가 나지 않고 조용히 틀린다.

**SecureContext 전용 API를 쓰지 않는다.** 운영은 평문 HTTP로 서빙되므로 `crypto.randomUUID()` 같은 API는 존재하지 않아 페이지 전체가 렌더에 실패한다. 로컬(localhost)에서는 멀쩡해 보여 발견이 늦다. 고유 id는 Svelte의 `$props.id()`를 쓴다.

**새 폼에는 중복 제출 가드를 넣는다.** 버튼의 `disabled`만으로는 `form.requestSubmit()` 경로를 막지 못한다. `handleSubmit` 첫 줄에 `if (submitting) return;`. 출장 신청·정산 제출은 멱등하지 않아 중복 POST가 곧 중복 레코드다.

## 테스트

- `db_session` 픽스처는 각 테스트를 외부 트랜잭션 + savepoint로 감싸 롤백한다. **`conftest.py`를 수정하지 말 것** — 루프 스코프와 `join_transaction_mode`가 리뷰를 거쳐 고정된 값이다.
- 순수 함수(코드 검증, 상태전이, 자동매칭)는 DB 없이 단위테스트한다.
- 프론트 테스트는 `client.ts`와 `auth.svelte.ts`만 다룬다. jsdom을 추가하지 말고 `vi.stubGlobal`을 쓴다.

## 마이그레이션

Alembic을 쓰지 않는다. 기동 시 `create_all` + 멱등 시드다. 스키마를 바꾸면 볼륨을 지우고 재기동한다.

## 다음 Phase로 넘어간 항목

`docs/superpowers/plans/2026-08-12-phase1-foundation.md` 말미의 "이월" 절들에 Phase 2에서 반드시 처리할 것들이 정리돼 있다. 특히 `authRequest` 래퍼와 전역 401 처리는 **첫 인증 화면을 만들 때 함께** 해야 한다.

## 환경 주의

Docker Engine 20.10.9 이하에서는 백엔드가 `can't start new thread`로 죽는다(기본 seccomp에 `clone3` 없음, 메모리와 무관). `docker-compose.old-docker.yml`을 함께 지정해 우회하거나 Docker를 업그레이드한다.
