# SK온 출장시스템

SK온 사내 출장시스템을 모사한 데모 웹 애플리케이션. 출장 신청부터 법인카드 기반 비용정산까지의 흐름을 화면으로 보여주며, **사람이 화면에서 하는 일과 동일한 일을 AI Agent가 API Key로 수행할 수 있도록** 웹 UI와 외부 Agent가 같은 엔드포인트를 사용한다.

실제 회계·전표 처리는 하지 않는다. DB에 적재된 샘플 데이터를 기반으로 화면과 API가 실제처럼 동작하는 것까지가 목표다.

- 설계: [`docs/superpowers/specs/2026-08-12-skon-biztrip-web-design.md`](docs/superpowers/specs/2026-08-12-skon-biztrip-web-design.md)
- 구현 계획: [`docs/superpowers/plans/`](docs/superpowers/plans/)
- 디자인 규칙: [`DESIGN.md`](DESIGN.md)

## 현재 상태 — Phase 1 (기반) 완료

| 영역 | 내용 |
|---|---|
| 백엔드 | FastAPI, 14테이블 스키마, JWT 인증, 멱등 시드, 테스트 105건 |
| 프론트엔드 | SvelteKit SPA, DESIGN.md 토큰 적용, 로그인·라우트가드·대시보드, 테스트 8건 |
| 배포 | Dockerfile 2종, nginx ingress, 4서비스 compose |

출장 목록·정산·개발자 화면은 Phase 2 이후에 추가된다. 상단 내비의 해당 탭은 현재 404다.

## 로컬 개발

DB만 컨테이너로 띄우고 백엔드·프론트엔드는 호스트에서 실행한다.

```bash
# 1. DB 기동 (최초 1회 테스트 DB도 생성)
docker compose -f docker-compose.dev.yml -p skon-dev up -d db
docker exec skon-db-dev psql -U skon -d postgres -c "CREATE DATABASE skon_test OWNER skon;"

# 2. 백엔드 (터미널 1)
cd backend && uv run uvicorn app.main:app --reload --port 8000

# 3. 프론트엔드 (터미널 2)
cd frontend && npm run dev
```

브라우저에서 <http://localhost:5173> 접속. `/api` 요청은 vite proxy가 `localhost:8000`으로 넘긴다.

백엔드는 기동 시 테이블을 만들고 시드를 넣는다. 시드는 멱등이라 재기동해도 중복되지 않는다.

## 데모 계정

비밀번호는 모두 `skon1234!`

| 계정 | 역할 |
|---|---|
| `admin@skon.example` | ADMIN (관리자) |
| `manager1@skon.example` ~ `manager3@` | MANAGER (팀장, 결재자) |
| `user1@skon.example` ~ `user10@` | EMPLOYEE (사원) |

## 테스트

```bash
cd backend  && uv run pytest          # 105건
cd frontend && npm test               # 8건
cd frontend && npm run check          # 타입체크 (0 errors)
```

## 배포

프론트엔드 · 백엔드 · DB · ingress 4개 컨테이너를 빌드해 기동한다. 노출 포트는 ingress `:80` 하나뿐이고 DB는 호스트 포트를 열지 않는다.

```bash
docker compose -p skon-prod up -d --build   # http://localhost
docker compose -p skon-prod down
```

> **`-p skon-prod`를 반드시 붙일 것.** 이 저장소에는 compose 파일이 둘 있고 같은 디렉터리에 있어 기본 프로젝트명이 겹친다. 두 파일 모두 `db` 서비스를 정의하므로, `-p` 없이 실행한 `docker compose down`은 프로젝트 라벨만 보고 **개발 DB 컨테이너까지 삭제한다.** Compose v2.0.0은 최상위 `name:` 속성을 지원하지 않아 파일에 고정할 수 없으므로, 호출 시 `-p`가 유일한 방어책이다. 개발 쪽도 대칭적으로 `-p skon-dev`를 쓴다.

운영 서버에서는 `.env`로 실제 값을 지정한다. 기본값은 명백한 placeholder이며 그대로 쓰면 안 된다.

```
JWT_SECRET=<32바이트 이상의 임의 문자열>
POSTGRES_PASSWORD=<실제 비밀번호>
```

### 오래된 Docker Engine에서의 주의사항

**Docker Engine 20.10.9 이하**에서는 백엔드 컨테이너가 기동 직후 `RuntimeError: can't start new thread`로 죽고 재시작 루프에 빠진다. 원인은 해당 버전의 기본 seccomp 프로파일에 `clone3` 시스템콜이 없어 EPERM으로 거부되기 때문이다. 백엔드 베이스 이미지 `python:3.12-slim`은 Debian bookworm(glibc 2.36)이고, glibc 2.34+는 스레드 생성 시 `clone3`을 먼저 호출한다. 메모리 부족과는 무관하며, 순정 `python:3.12-slim` 컨테이너에서 `threading.Thread().start()`만 해도 재현된다.

근본 해결은 Docker Engine 업그레이드다 — 20.10.10에서 `clone3`이 기본 프로파일에 추가됐다. 당장 데모를 돌려야 한다면 오버라이드 파일을 함께 지정한다.

```bash
docker compose -p skon-prod -f docker-compose.yml -f docker-compose.old-docker.yml up -d --build
```

이 오버라이드는 백엔드 컨테이너의 seccomp를 끄므로 격리가 약해진다. 운영 배포에는 쓰지 말 것.

### 검증 상태

4컨테이너 스택을 실제로 기동해 ingress(:80) 경유로 다음을 확인했다.

| 항목 | 결과 |
|---|---|
| `GET /api/v1/health` | `{"status":"ok"}` |
| `POST /api/v1/auth/login` | 토큰 + 사용자 객체 반환 |
| `GET /` | 200, `<title>SK온 출장시스템</title>` |
| `GET /docs` | 200 |
| `GET /trips/42` (딥링크) | **200** — SPA fallback 정상 |
| 운영 DB 시드 | 사용자 14 · 출장 40 · 카드거래 785 · 정산서 12 |
| 재기동 멱등성 | 행 수 동일 |
| `db` 호스트 포트 | 미노출 (내부 5432/tcp만) |

## 스택

SvelteKit 2 / Svelte 5 (runes, `adapter-static`) · TailwindCSS v4 · Pretendard · FastAPI · SQLAlchemy 2.0 (async) · PostgreSQL 16 · nginx · Docker Compose

## 디자인

`DESIGN.md`는 Airbnb 디자인 시스템 분석 문서다. 타이포·스페이싱·라운드·엘리베이션·반응형 규칙을 따르되 **primary 색만 SK온 브랜드 레드(`#EA002C`)로 치환**했다. Airbnb Cereal VF는 라이선스 폰트라 쓸 수 없어, 한글을 지원하면서 Inter와 메트릭이 호환되는 **Pretendard**를 사용한다.
