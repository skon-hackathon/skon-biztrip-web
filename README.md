# SK온 출장시스템

SK온 사내 출장시스템을 모사한 데모 웹 애플리케이션. 출장 신청부터 법인카드 기반 비용정산까지의 흐름을 화면으로 보여주며, **사람이 화면에서 하는 일과 동일한 일을 AI Agent가 API Key로 수행할 수 있도록** 웹 UI와 외부 Agent가 같은 엔드포인트를 사용한다.

실제 회계·전표 처리는 하지 않는다. DB에 적재된 샘플 데이터를 기반으로 화면과 API가 실제처럼 동작하는 것까지가 목표다.

- 설계: [`docs/superpowers/specs/2026-08-12-skon-biztrip-web-design.md`](docs/superpowers/specs/2026-08-12-skon-biztrip-web-design.md)
- 구현 계획: [`docs/superpowers/plans/`](docs/superpowers/plans/)
- Phase 현황·이월 항목: [`docs/phase-status.md`](docs/phase-status.md)
- 디자인 규칙: [`DESIGN.md`](DESIGN.md)

## 현재 상태 — Phase 3 (정산) 완료

| 영역 | 내용 |
|---|---|
| 백엔드 | FastAPI, 14테이블 스키마, JWT 인증, 출장 CRUD·상태전이·타임라인·알림 API, 카드내역·자동매칭·정산서 API, 공통코드/센터 조회, 수동 시드 CLI, 테스트 **408건** |
| 프론트엔드 | SvelteKit SPA, DESIGN.md 토큰 적용, 로그인·라우트가드, 출장 신청/목록/상세/수정, 결재함, 알림, 대시보드, 법인카드 내역, 정산서 작성·결재, 테스트 **55건** |
| 배포 | Dockerfile 2종, nginx ingress, 3서비스 compose |

**동작하는 흐름**: 출장 신청 → 상신 → 결재자 알림 → 결재함 → 승인/반려 → (반려 시) 재작성 → 재상신 → 완료 처리 → **정산서 작성 → 자동매칭으로 카드내역 담기 → 제출 → 결재 → 승인 시 출장이 정산완료로 자동 전이**. 모든 전이가 타임라인에 남는다.

개발자(`/developers`) 화면은 Phase 4에서 추가된다. 상단 내비의 해당 탭은 현재 404다.

정산 화면은 `/expenses`(목록) · `/expenses/[id]`(작성·결재) · `/cards`(법인카드 사용내역)다. 완료된 출장 상세에서 "정산서 작성"으로 진입하면 자동매칭 후보가 사유와 함께 뜨고, 담은 항목의 부서(FC/CC)는 리포트 기본값을 상속하되 행 단위로 덮어쓸 수 있다. 정산서가 승인되면 해당 출장이 자동으로 정산완료(SETTLED)로 전이된다.

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
       "start_date":"2026-10-01","end_date":"2026-10-03","transport_code":"RAIL",
       "accommodation_code":"HOTEL","cost_center_code":"CC2030","estimated_cost":"300000"}'

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
| `admin@skon.example` | ADMIN (관리자) |
| `manager1@skon.example` ~ `manager3@` | MANAGER (팀장, 결재자) |
| `user1@skon.example` ~ `user10@` | EMPLOYEE (사원) |

## 테스트

```bash
cd backend  && uv run pytest          # 408건
cd frontend && npm test               # 55건
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
