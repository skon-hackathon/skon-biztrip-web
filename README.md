# SK온 출장시스템

SK온 사내 출장시스템을 모사한 데모 웹 애플리케이션. 출장 신청부터 법인카드 기반 비용정산까지의 흐름을 화면으로 보여주며, **사람이 화면에서 하는 일과 동일한 일을 AI Agent가 API Key로 수행할 수 있도록** 웹 UI와 외부 Agent가 같은 엔드포인트를 사용한다.

실제 회계·전표 처리는 하지 않는다. DB에 적재된 샘플 데이터를 기반으로 화면과 API가 실제처럼 동작하는 것까지가 목표다.

- 설계: [`docs/superpowers/specs/2026-08-12-skon-biztrip-web-design.md`](docs/superpowers/specs/2026-08-12-skon-biztrip-web-design.md)
- 구현 계획: [`docs/superpowers/plans/`](docs/superpowers/plans/)
- Phase 현황·이월 항목: [`docs/phase-status.md`](docs/phase-status.md)
- 브라우저 수동 시나리오: [`docs/manual-scenarios.md`](docs/manual-scenarios.md)
- 디자인 규칙: [`DESIGN.md`](DESIGN.md)

## 현재 상태 — Phase 5 (운영) 완료

spec 10의 5단계가 모두 끝났다.

| 영역 | 내용 |
|---|---|
| 백엔드 | FastAPI, 14테이블 스키마, JWT + API Key 이중 인증, 출장·정산·카드 API, 자동매칭, 관리자 CRUD 28개, 엔드포인트별 스코프 표, 수동 시드 CLI, 테스트 **569건** |
| 프론트엔드 | SvelteKit SPA, DESIGN.md 토큰, 출장·결재·알림·대시보드, 법인카드·정산서, API Key 발급 화면, `/developers` 가이드, 관리자 화면 5종, 744px 반응형, 테스트 **73건** |
| 배포 | Dockerfile 2종, nginx ingress, 3서비스 compose (DB는 스택 밖) |

**동작하는 흐름**: 출장 신청 → 상신 → 결재자 알림 → 결재함 → 승인/반려 → (반려 시) 재작성 → 완료 처리 → 정산서 작성 → 자동매칭 또는 카드내역 모달로 카드내역 담기 → 제출 → 결재 → 승인 시 출장이 정산완료로 자동 전이. 모든 전이가 타임라인에 남는다.

### 화면

```
/login                 로그인
/                      대시보드 (내 출장, 결재 대기, 미정산, 최근 알림)
/trips · /trips/new · /trips/[id] · /trips/[id]/edit
/approvals             결재함 (MANAGER·ADMIN)
/cards                 내 법인카드 + 사용내역
/expenses · /expenses/[id]        정산 목록 · 정산서 작성/결재
/notifications
/settings/api-keys     API Key 발급 · 조회 · 폐기
/developers            API 가이드 (curl 예제 · 스코프 표 · /docs 링크)
/admin/codes · /admin/centers · /admin/departments · /admin/users · /admin/cards   (ADMIN)
```

정산 화면은 완료된 출장 상세의 "정산서 작성"으로 진입한다. 자동매칭 후보가 사유와 함께 뜨고, 매칭 창(출장 시작 1일 전 ~ 종료 1일 후) 밖의 결제는 "법인카드 사용내역 보기" 모달에서 담는다 — 아직 어떤 정산서에도 담기지 않은 본인 거래가 모두 뜬다. 담은 항목의 부서(FC/CC)는 리포트 기본값을 상속하되 행 단위로 덮어쓸 수 있다.

관리자 화면은 마스터 데이터(공통코드·Fund/Cost Center·부서·사용자·법인카드)를 고친다. 여기서 코드를 비활성화하면 **출장 신청 드롭다운과 API 검증이 함께 바뀐다** — 화면과 Agent가 같은 마스터를 본다.

### 웹 UI와 Agent가 같은 엔드포인트를 쓴다

화면에서 하는 일을 curl로 그대로 할 수 있다.

```bash
TOKEN=$(curl -s localhost:8000/api/v1/auth/login -H 'Content-Type: application/json' \
  -d '{"email":"user1@skon.example","password":"skon1234!"}' | python3 -c 'import sys,json;print(json.load(sys.stdin)["access_token"])')

# 유효한 코드값을 스스로 발견한다
curl -s localhost:8000/api/v1/codes/TRANSPORT -H "Authorization: Bearer $TOKEN"

# 출장을 만들고 상신한다
curl -s -X POST localhost:8000/api/v1/trips -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{"title":"울산공장 품질점검","purpose_code":"AUDIT","purpose_detail":"라인 3 확인",
       "destination_type_code":"DOMESTIC","country_code":"KR","city":"울산",
       "start_date":"2026-10-01","end_date":"2026-10-03"}'

curl -s -X POST localhost:8000/api/v1/trips/41/submit -H "Authorization: Bearer $TOKEN"

# 완료된 출장의 정산서를 만들고, 자동매칭 후보를 사유와 함께 받는다
curl -s -X POST localhost:8000/api/v1/expenses -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' -d '{"trip_id":30}'

curl -s localhost:8000/api/v1/expenses/13/match-candidates -H "Authorization: Bearer $TOKEN"
# [{"transaction_id":812,"merchant_name":"코레일","amount_krw":"114500.00",
#   "reasons":["출장기간 내 승인"],"suggested_category_code":"TRANSPORT","already_added":false}, ...]

# 후보를 담고, 비용처리 부서를 지정하고, 제출한다
curl -s -X POST localhost:8000/api/v1/expenses/13/items -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{"card_transaction_id":812,"expense_category_code":"TRANSPORT"}'

curl -s -X PATCH localhost:8000/api/v1/expenses/13 -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' -d '{"fund_center_code":"FC1010"}'

curl -s -X POST localhost:8000/api/v1/expenses/13/submit -H "Authorization: Bearer $TOKEN"
```

매칭 사유 문자열(`출장기간 내 승인` · `출발 전일 교통비` 등)은 화면이 보여주는 것과 **글자까지 같다** — 사람과 Agent가 같은 설명을 받는다.

에러는 항상 같은 모양이다. `code`는 기계가 읽는 도메인 코드이며, 409에서 Agent가 재시도 여부를 판단하는 근거다.

```json
{"error": {"code": "TRIP_INVALID_TRANSITION", "message": "SUBMITTED 상태에서 SUBMITTED 로 변경할 수 없습니다", "field": null}}
```

### Agent는 API Key로 같은 일을 한다

`/settings/api-keys`에서 키를 발급하면 `X-API-Key` 헤더 하나로 위 호출을 그대로 할 수 있다. 평문 키는 **발급 응답에서 한 번만** 나오고 DB에는 SHA-256만 남는다.

```bash
# 키 발급은 로그인 세션(JWT) 전용이다 — 키가 키를 낳지 못하게 막았다
KEY=$(curl -s -X POST localhost:8000/api/v1/api-keys -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{"name":"정산 자동화 Agent","scopes":["trips:read","trips:write"]}' \
  | python3 -c 'import sys,json;print(json.load(sys.stdin)["key"])')

curl -s localhost:8000/api/v1/trips -H "X-API-Key: $KEY"       # 사람과 같은 엔드포인트

curl -s localhost:8000/api/v1/cards -H "X-API-Key: $KEY"
# {"error":{"code":"SCOPE_REQUIRED","message":"이 요청에는 cards:read 스코프가 필요합니다","field":null}}
```

스코프는 `trips:read` · `trips:write` · `expenses:read` · `expenses:write` · `cards:read` · `admin` 여섯 가지다. 어떤 엔드포인트에 무엇이 필요한지는 `GET /api/v1/scopes`가 알려주고, `/developers` 화면과 `/docs`(OpenAPI)가 같은 표를 그린다 — 손으로 적은 문서가 아니라서 어긋날 수 없다.

**표에 없는 엔드포인트는 통과가 아니라 403이다.** 라우트를 추가하고 스코프 표에 적지 않으면 앱이 아예 기동하지 않는다(임포트 시점 소진 가드). 조용히 전권이 되는 엔드포인트가 생기는 것보다 못 뜨는 게 낫다는 판단이다.

### 관리자 API

`role=ADMIN`이면서 키를 쓸 경우 `admin` 스코프까지 있어야 열린다. 마스터 데이터 삭제는 참조가 남아 있으면 409다.

```bash
curl -s -X POST localhost:8000/api/v1/admin/departments -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' -d '{"code":"D500","name":"신규팀"}'

curl -s -X DELETE localhost:8000/api/v1/admin/departments/1 -H "Authorization: Bearer $TOKEN"
# {"error":{"code":"HAS_DEPENDENTS","message":"이 부서를 참조하는 사용자·센터가 있어 삭제할 수 없습니다","field":null}}
```

`user`·`department`·`code`·`fund_center`·`cost_center` 삭제는 500이 아니라 409로 돌려준다. Agent는 5xx를 재시도하므로, 절대 성공할 수 없는 요청에 재시도 루프가 걸리지 않게 하려는 것이다. 사용자는 삭제 자체가 없다(비활성화만) — 출장·정산·카드가 참조하고 감사 흔적을 지울 이유도 없다.

## 데이터베이스

**이 프로젝트는 DB를 직접 띄우지 않는다.** 이미 운영 중인 PostgreSQL에 접속하며, 접속 정보만 환경변수로 주입한다.

`backend/.env` (템플릿은 [`backend/.env.example`](backend/.env.example)):

```
DB_HOST=localhost
DB_PORT=5432
DB_USER=skon
DB_PASSWORD=skon
DB_NAME=skon
DB_SCHEMA=skon
TEST_DB_SCHEMA=skon_test
JWT_SECRET=<32바이트 이상>
```

접속은 매 커넥션마다 `search_path`를 `DB_SCHEMA` **하나로만** 고정한다. `public`을 fallback으로 남기지 않으므로 이 앱의 질의나 DDL이 다른 스키마로 새어나갈 수 없다.

### 스키마·데이터 준비는 수동이다

앱은 기동할 때 스키마나 데이터를 **건드리지 않는다.** 운영 DB에 붙기 때문에 자동 `create_all`이나 자동 시드는 남의 데이터를 위협한다. 필요할 때 사람이 명시적으로 실행한다.

```bash
cd backend
uv run python -m app.cli check      # 접속 확인만 (아무것도 바꾸지 않음)
uv run python -m app.cli init-db    # 스키마 + 없는 테이블 생성 (기존 테이블 보존)
uv run python -m app.cli seed       # 데모 데이터 적재 (멱등)
```

`init-db`는 없는 테이블만 만든다. 기존 테이블의 컬럼 변경은 반영하지 않으므로, 스키마를 바꾸면 해당 테이블을 지우고 다시 만들어야 한다 (Alembic을 쓰지 않는다).

## 로컬 개발

```bash
# 1. 접속 정보 준비
cp backend/.env.example backend/.env   # 값을 실제 DB에 맞게 수정

# 2. 최초 1회 스키마·시드
cd backend && uv run python -m app.cli init-db && uv run python -m app.cli seed

# 3. 백엔드 (터미널 1)
cd backend && uv run uvicorn app.main:app --reload --port 8000

# 4. 프론트엔드 (터미널 2)
cd frontend && npm run dev
```

브라우저에서 <http://localhost:5173> 접속. `/api` 요청은 vite proxy가 `localhost:8000`으로 넘긴다.

접속 설정이 맞는지는 <http://localhost:8000/api/v1/health/db> 로도 확인할 수 있다 (host·database·current_schema를 돌려준다).

## 데모 계정

비밀번호는 모두 `skon1234!`

| 계정 | 역할 |
|---|---|
| `admin@skon.example` | ADMIN (관리자 — `/admin/*` 화면·API 접근) |
| `manager1@skon.example` ~ `manager3@` | MANAGER (팀장, 결재자) |
| `user1@skon.example` ~ `user10@` | EMPLOYEE (사원) |

## 테스트

```bash
cd backend  && uv run pytest          # 569건
cd frontend && npm test               # 73건
cd frontend && npm run check          # 타입체크 (0 errors / 0 warnings)
```

백엔드 테스트는 같은 DB 서버의 **별도 스키마**(`TEST_DB_SCHEMA`, 기본 `skon_test`)에서 돈다. 매 실행마다 그 스키마를 `drop_all` 후 재생성하므로 **`DB_SCHEMA`와 절대 같으면 안 된다.** 같으면 픽스처가 실행 자체를 거부한다.

## 배포

프론트엔드 · 백엔드 · ingress 3개 컨테이너를 빌드해 기동한다. DB는 스택 밖에 있다. 노출 포트는 ingress `:80` 하나뿐이다.

```bash
docker compose -p skon-prod up -d --build   # http://localhost
docker compose -p skon-prod down
```

접속 정보는 저장소 루트의 `.env`로 주입한다. `DB_HOST`·`DB_USER`·`DB_PASSWORD`·`DB_NAME`·`JWT_SECRET`은 값이 없으면 compose가 기동을 거부한다.

루트 `.env` 없이 `backend/.env`를 재사용하려면 두 가지를 함께 준다. 개발용 `DB_HOST=localhost`는 컨테이너 안에서 자기 자신을 가리키므로 반드시 덮어써야 한다.

```bash
DB_HOST=host.docker.internal docker compose --env-file backend/.env -p skon-prod up -d --build
```

**이미지 빌드는 확인됐고 기동은 아직이다.** Phase 5 당시 빌드를 막았던 `ghcr.io` 조회 타임아웃(`DeadlineExceeded`)은 원인을 제거했다 — `backend/Dockerfile`이 uv를 ghcr.io에서 복사하지 않고 PyPI에서 받으므로 레지스트리 의존이 Docker Hub 하나다. `--no-cache` 전체 재빌드로 두 이미지 모두 생성되는 것까지 확인했다. 다만 **3서비스 기동·nginx 프록시·SPA fallback은 여전히 재검증되지 않았다.** 자세한 내용은 [`docs/phase-status.md`](docs/phase-status.md)의 "배포 검증" 절에 있다.

컨테이너 안에서 CLI를 쓰려면:

```bash
docker compose -p skon-prod exec backend uv run --no-dev python -m app.cli check
```

### 오래된 Docker Engine에서의 주의사항

**Docker Engine 20.10.9 이하**에서는 백엔드 컨테이너가 기동 직후 `RuntimeError: can't start new thread`로 죽고 재시작 루프에 빠진다. 원인은 해당 버전의 기본 seccomp 프로파일에 `clone3` 시스템콜이 없어 EPERM으로 거부되기 때문이다. 백엔드 베이스 이미지 `python:3.12-slim`은 Debian bookworm(glibc 2.36)이고, glibc 2.34+는 스레드 생성 시 `clone3`을 먼저 호출한다. 메모리 부족과는 무관하며, 순정 `python:3.12-slim` 컨테이너에서 `threading.Thread().start()`만 해도 재현된다.

근본 해결은 Docker Engine 업그레이드다 — 20.10.10에서 `clone3`이 기본 프로파일에 추가됐다. 당장 데모를 돌려야 한다면 오버라이드 파일을 함께 지정한다.

```bash
docker compose -p skon-prod -f docker-compose.yml -f docker-compose.old-docker.yml up -d --build
```

이 오버라이드는 백엔드 컨테이너의 seccomp를 끄므로 격리가 약해진다. 운영 배포에는 쓰지 말 것.

## 스택

SvelteKit 2 / Svelte 5 (runes, `adapter-static`) · TailwindCSS v4 · Pretendard · FastAPI · SQLAlchemy 2.0 (async) · PostgreSQL 16 · nginx · Docker Compose

## 디자인

`DESIGN.md`는 Airbnb 디자인 시스템 분석 문서다. 타이포·스페이싱·라운드·엘리베이션·반응형 규칙을 따르되 **primary 색만 SK온 브랜드 레드(`#EA002C`)로 치환**했다. Airbnb Cereal VF는 라이선스 폰트라 쓸 수 없어, 한글을 지원하면서 Inter와 메트릭이 호환되는 **Pretendard**를 사용한다.
