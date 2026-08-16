# Phase 현황 — 완료분과 다음 작업

- 기준: Phase 1 (기반) 완료 시점
- 설계: [`superpowers/specs/2026-08-12-skon-biztrip-web-design.md`](superpowers/specs/2026-08-12-skon-biztrip-web-design.md)
- Phase 1 계획: [`superpowers/plans/2026-08-12-phase1-foundation.md`](superpowers/plans/2026-08-12-phase1-foundation.md)

---

## Phase 1 — 완료

18개 태스크를 태스크마다 구현 1 + 독립 리뷰 2(사양 준수 / 코드 품질) 방식으로 진행했다.

### 백엔드

| 항목 | 상태 |
|---|---|
| FastAPI 3계층 (`routers/` → `services/` → `models/`) | 완료 |
| 14테이블 스키마 | 완료 |
| 공통코드 검증 서비스 | 완료 |
| 출장 상태전이 표 + 전수 테스트 | 완료 |
| bcrypt + JWT | 완료 |
| `/auth/login` · `/auth/me` | 완료 |
| 통일 에러 계약 `{"error": {code, message, field}}` | 완료 |
| 멱등 시드 (수동 CLI) | 완료 |
| 외부 운영 DB 접속 | 완료 |
| 테스트 | **116건** |

**14테이블**: `department` `user` `code_group` `code` `fund_center` `cost_center` `trip` `corporate_card` `card_transaction` `expense_report` `expense_item` `api_key` `notification` `activity_log`

**시드 규모**: 부서 4 · 사용자 14 · 공통코드 9그룹 · FC 6 · CC 10 · 카드 14 · 카드거래 785 · 출장 40 · 정산서 12

### 프론트엔드

| 항목 | 상태 |
|---|---|
| SvelteKit 2 / Svelte 5 SPA (`adapter-static`) | 완료 |
| DESIGN.md 토큰 이식 (primary만 SK온 레드 `#EA002C`) | 완료 |
| Pretendard 폰트 | 완료 |
| 기본 컴포넌트 4종 (Button · TextInput · Badge · Card) | 완료 |
| 앱 셸 (top-nav) | 완료 |
| API 클라이언트 + 인증 스토어 | 완료 |
| 로그인 화면 · 라우트 가드 · 대시보드 | 완료 |
| 테스트 | **8건**, 타입체크 0 errors |

### 배포

| 항목 | 상태 |
|---|---|
| 백엔드 Dockerfile (uv) | 완료 |
| 프론트 Dockerfile (멀티스테이지 → nginx) | 완료 |
| ingress nginx (`/api` → backend, 나머지 → frontend) | 완료 |
| 3서비스 compose (DB는 스택 밖) | 완료 |
| ingress 경유 전 경로 실검증 | 완료 |

### 화면으로 확인 가능한 것

로그인 → 대시보드 → 로그아웃. 상단 내비의 출장·정산·개발자 탭은 아직 404 (Phase 2 이후).

---

## 리뷰가 잡아낸 주요 결함

전부 "테스트는 통과하는데 실제로는 깨지는" 부류였다. 기록해두는 이유는 같은 함정을 다시 밟지 않기 위해서다.

| # | 결함 | 실제 영향 |
|---|---|---|
| 1 | pytest-asyncio 루프 스코프 미지정 | session 픽스처가 닫힌 루프에 묶여 두 번째 테스트부터 실패 |
| 2 | `join_transaction_mode` 누락 | 테스트가 `rollback()` 후 `commit()` 하면 실제 DB에 기록됨 |
| 3 | 에러 계약 구멍 | 라우팅 404·미처리 예외가 통일 바디 밖으로 나감 |
| 4 | `Code.group` 지연로딩 | `MissingGreenlet` — Admin 화면에서 터질 예정이었음 |
| 5 | `updated_at` expire | UPDATE → commit → 직렬화 패턴에서 `MissingGreenlet` |
| 6 | 비활성 코드그룹 우회 | 관리자가 코드그룹을 껐는데 그 값으로 쓰기가 통과 |
| 7 | 전이 표 불완전 시 `KeyError` | 409가 아니라 500으로 새어 Agent가 재시도 판단 불가 |
| 8 | 전이 행렬 커버리지 11/36 | 오타로 엣지가 추가돼도 전 테스트 통과 |
| 9 | `ActivityLog` 인덱스 | 타임라인 쿼리가 인덱스를 못 씀 (실측) |
| 10 | 이중 계상 방지 제약 미검증 | 매칭 설계의 핵심 불변식인데 회귀 테스트 없었음 |
| 11 | `decode_access_token` 계약 이탈 | 변조 토큰이 401이 아니라 500 |
| 12 | 로그인 타이밍 오라클 | 미지 이메일 2.3ms vs 기지 211ms — 92배 |
| 13 | **시드가 핵심 데모를 못 보여줌** | 완료 출장 17건 중 7건이 카드 매칭 후보 0건 |
| 14 | **`crypto.randomUUID()`** | SecureContext 전용 — 운영(평문 HTTP) 첫 화면 크래시, 로컬에선 정상 |
| 15 | 탭 중앙 정렬 | 부서명 길이에 따라 60~140px 편향 |
| 16 | 중복 제출 가드 부재 | 로그인은 무해하나 출장 신청·정산 제출에선 중복 레코드 |

13·14가 특히 컸다. 13은 자동매칭이 이 프로젝트의 핵심 데모인데 시드 데이터가 그걸 보여줄 수 없는 상태였고, 14는 로컬에서 100% 재현 불가능하면서 운영에서 100% 터지는 조합이었다.

---

## Phase 2 — 출장 기능

### 범위

출장 신청 / 목록 / 상세 / 수정, 결재함, 상태전이, 타임라인·알림.

**라우트**: `/trips` `/trips/new` `/trips/[id]` `/trips/[id]/edit` `/approvals` `/notifications`

**API**: `GET|POST /trips` · `GET|PATCH|DELETE /trips/{id}` · `POST /trips/{id}/submit|approve|reject|complete` · `GET /notifications` · `POST /notifications/{id}/read` · `GET /codes/{group_code}` · `GET /fund-centers` · `GET /cost-centers`

### 시작 전에 반드시 처리할 이월 항목

Phase 1 리뷰에서 "여기가 아니라 Phase 2에서" 판정된 것들. 계획 문서 말미의 "이월" 절들에 근거와 함께 정리돼 있다.

**데이터 계층 — 첫 인증 화면 만들 때 한 쌍으로**

- `authRequest` 래퍼: `request()`의 `token`이 선택 파라미터라 인증 호출부마다 손으로 붙여야 한다. 수십 곳 중 하나만 빠뜨려도 조용히 미인증 요청이 나가고, 호출부에서 진짜 인증 실패와 구분되지 않는다.
- 전역 401 처리: JWT 8시간 만료에 refresh가 없다. 세션 중간에 만료되면 헤더에 이름이 계속 보이는데 아무 코드도 상태를 정리하지 않는다. 위 래퍼 안에서 `status === 401` 하나로 끝난다.

**서비스 계층**

- `validate_codes` 오케스트레이터: 출장 생성은 코드 5개를 한 요청에서 검증한다. 쌍을 다섯 번 반복하면 그룹명과 `field=` 문자열을 잘못 짝지을 위험이 있다. 근거는 성능이 아니라 호출부 실수 방지다.
- 교차 필드 제약: `end_date >= start_date`, `estimated_cost >= 0`, 반려 시 `reject_reason` 필수. 모델에 `CheckConstraint`가 없으므로 **서비스가 반드시 검증해야 한다.** 모델이 막아줄 거라 가정하지 말 것.
- 전이 조건·권한: `trip_status.py`는 합법성만 판단한다. `APPROVED → COMPLETED`의 종료일 과거 조건과 "배정된 결재자만 승인"은 별도로 검사한다.
- 이력·알림: 모든 전이가 서비스의 단일 지점을 통과하고 거기서 `ActivityLog` + `Notification`을 함께 기록한다. 웹이든 API Key든 이력이 빠질 수 없어야 한다.

**직렬화**

- 요청자·결재자 이름: `Trip`에 `relationship()`이 없는 것은 의도적이다. 목록에서 행마다 헬퍼를 부르면 N+1이 된다. `select(User).where(User.id.in_(ids))`로 일괄 조회하거나 목록 쿼리에 명시적 `JOIN`을 건다.

**UI**

- 새 폼마다 중복 제출 가드 (`if (submitting) return;`). 출장 신청은 멱등하지 않다.
- 딥링크 보존: 미로그인으로 `/trips/42` 접근 시 로그인 후 `/`가 아니라 원래 경로로 돌아가야 한다. `?redirect=` 파라미터로 처리.
- `Badge` 톤을 실제 상태 6종(DRAFT·SUBMITTED·APPROVED·REJECTED·COMPLETED·SETTLED)에 맞게 확장. 현재 4종.
- `TextInput`에 `name` 전달 추가 (`autocomplete`는 완료).

### 이후 Phase

| Phase | 범위 |
|---|---|
| 3 | 정산 — 카드내역, 자동매칭, 정산서 작성·제출·결재, FC/CC |
| 4 | 개발자 — API Key 발급·폐기·스코프, `/developers` 가이드, OpenAPI 정리 |
| 5 | 운영 — Admin(공통코드·센터·사용자·부서·카드) |

### 그 외 미결

- 반응형: DESIGN.md의 744px 미만 햄버거·시트 붕괴가 미구현이다. 744px에서는 정상이나 375px에서 탭이 두 줄로 깨지고 우측 블록이 화면 밖으로 나간다. 데스크톱 데모 기준이라 의도적으로 넘겼고, 뼈대가 하나도 없으므로 해당 Phase에서 처음부터 만들어야 한다.
- 비밀번호 길이: bcrypt 5.x는 72바이트 초과 시 자르지 않고 예외를 던진다. 한글은 **24자만 넘어도** 터진다. 비밀번호 설정·변경 엔드포인트를 만들 때 요청 스키마에서 막아야 한다.
- 운영 `JWT_SECRET`: compose 기본값은 명백한 placeholder다. 배포 시 32바이트 이상 실제 값을 `.env`로 주입한다.
- `init-db`는 컬럼 변경을 반영하지 않는다. Alembic을 쓰지 않으므로 스키마를 바꾸면 해당 테이블을 지우고 다시 돌려야 한다. 실제 운영 전환이 필요해지면 마이그레이션 도구 도입을 재검토한다.
