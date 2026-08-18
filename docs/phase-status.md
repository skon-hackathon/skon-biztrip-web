# Phase 현황 — 완료분과 다음 작업

- 기준: Phase 5 (운영) 완료 시점
- 설계: [`superpowers/specs/2026-08-12-skon-biztrip-web-design.md`](superpowers/specs/2026-08-12-skon-biztrip-web-design.md)
- Phase 1 계획: [`superpowers/plans/2026-08-12-phase1-foundation.md`](superpowers/plans/2026-08-12-phase1-foundation.md)
- Phase 2 계획: [`superpowers/plans/2026-08-17-phase2-trips.md`](superpowers/plans/2026-08-17-phase2-trips.md)
- Phase 3 계획: [`superpowers/plans/2026-08-18-phase3-expenses.md`](superpowers/plans/2026-08-18-phase3-expenses.md)
- Phase 4 계획: [`superpowers/plans/2026-08-18-phase4-developers.md`](superpowers/plans/2026-08-18-phase4-developers.md)
- Phase 5 계획: [`superpowers/plans/2026-08-18-phase5-admin-ops.md`](superpowers/plans/2026-08-18-phase5-admin-ops.md)
- 브라우저 수동 시나리오: [`manual-scenarios.md`](manual-scenarios.md)

| Phase | 범위 | 상태 |
|---|---|---|
| 1 | 기반 — 스키마·인증·SPA 골격·배포 | 완료 |
| 2 | 출장 — 신청·목록·상세·수정·결재·타임라인·알림 | 완료 |
| 3 | 정산 — 카드내역·자동매칭·정산서·FC/CC | 완료 |
| 4 | 개발자 — API Key·스코프·`/developers` 가이드 | 완료 |
| 5 | 운영 — Admin CRUD, 반응형, 배포 검증 | **완료** |

**테스트**: 백엔드 569건 · 프론트 73건 · 타입체크 0 errors / 0 warnings · 빌드 성공

---

## Phase 1 — 완료

18개 태스크를 태스크마다 구현 1 + 독립 리뷰 2(사양 준수 / 코드 품질) 방식으로 진행했다.

| 영역 | 내용 |
|---|---|
| 백엔드 | FastAPI 3계층, 14테이블 스키마, 공통코드 검증, 상태전이 표, bcrypt+JWT, `/auth/login`·`/auth/me`, 통일 에러 계약, 멱등 시드 CLI, 외부 운영 DB 접속 |
| 프론트엔드 | SvelteKit 2 / Svelte 5 SPA, DESIGN.md 토큰(primary만 SK온 레드 `#EA002C`), Pretendard, 기본 컴포넌트 4종, 앱 셸, API 클라이언트·인증 스토어, 로그인·라우트가드·대시보드 |
| 배포 | Dockerfile 2종, ingress nginx, 3서비스 compose (DB는 스택 밖) |

**14테이블**: `department` `user` `code_group` `code` `fund_center` `cost_center` `trip` `corporate_card` `card_transaction` `expense_report` `expense_item` `api_key` `notification` `activity_log`

**시드 규모**: 부서 4 · 사용자 14 · 공통코드 9그룹 · FC 6 · CC 10 · 카드 14 · 카드거래 785 · 출장 40 · 정산서 12

---

## Phase 2 — 완료

29개 태스크. Task 1–4는 태스크마다 구현 1 + 독립 리뷰 2 방식으로, Task 5 이후는 인라인 구현 + 태스크별 mutation 검증으로 진행했다.

### 백엔드 — 서비스 계층

| 모듈 | 책임 |
|---|---|
| `services/codes.py` | `validate_codes` 오케스트레이터 — 코드값 여러 개를 **쿼리 2개**로 한 번에 검증. 그룹 조회 + 코드 일괄 조회. `load_code_groups`·`load_code_group` 조회 |
| `services/centers.py` | 활성 센터 코드 로드, `assert_cost_center`, `load_active_centers` |
| `services/trip_rules.py` | 순수 도메인 규칙 10종 + `TRANSITION_ACTOR` 표 + `assert_transition_allowed`. DB 접근 없음 |
| `services/numbering.py` | `BT-YYYY-NNNN` 채번 (연도별) |
| `services/history.py` | `record_transition` — `ActivityLog` + `Notification` 단일 기록 지점 |
| `services/trips.py` | 조회·목록·생성·수정·삭제·전이 5종·타임라인. 스키마를 반환한다 |
| `services/notifications.py` | 알림 목록(전체 미읽음 수 포함)·읽음 처리 |

### 백엔드 — API

```
GET|POST         /api/v1/trips
GET|PATCH|DELETE /api/v1/trips/{id}
POST             /api/v1/trips/{id}/submit | approve | reject | reopen | complete
GET              /api/v1/trips/{id}/timeline
GET              /api/v1/codes  ·  /api/v1/codes/{group_code}
GET              /api/v1/fund-centers  ·  /api/v1/cost-centers
GET              /api/v1/notifications
POST             /api/v1/notifications/{id}/read
```

목록 필터: `scope`(mine·approvals·all) · `status`(반복 파라미터) · `destination_type_code` · `country_code` · `q` · `start_date_from` · `start_date_to` · `page` · `size`

### 프론트엔드

| 항목 | 내용 |
|---|---|
| 화면 | `/trips` `/trips/new` `/trips/[id]` `/trips/[id]/edit` `/approvals` `/notifications` + 대시보드 실데이터 |
| 컴포넌트 | `Select` `Textarea` `EmptyState` `StatusBadge` `TripCard` `FilterBar` `Timeline` `TripForm` |
| 데이터 계층 | `authRequest` 래퍼 + 전역 401, `nav.ts`(딥링크·공개경로), `format.ts`, `trip-status.ts`, API 클라이언트 4종 |
| 앱 셸 | 결재함 링크(MANAGER·ADMIN 한정) + 알림 벨 뱃지. 가운데 3-탭은 DESIGN.md 규칙이라 유지 |

DESIGN.md 매핑: `property-card` → 출장 카드, `search-bar-pill` + `search-orb` → 목록 필터, `reservation-card` → 상세 우측 sticky 액션 카드, `guest-favorite-badge` → 상태 뱃지.

### 실서버 검증 완료

curl로 `BT-2026-0041` 생성 → 상신 → 결재자(김연구) 알림 도착 → 결재함 노출 → 승인 → 타임라인 `CREATED·SUBMITTED·APPROVED`. 웹 UI와 Agent가 물리적으로 같은 엔드포인트를 쓴다는 핵심 메시지가 실제로 성립한다.

에러 계약 실측: 중복 상신 409 `TRIP_INVALID_TRANSITION` · 잘못된 코드값 400 `INVALID_CODE`+`field` · 금액 오버플로 400 `INVALID_AMOUNT` · 타인 출장 404 `TRIP_NOT_FOUND`.

### 설계에서 벗어난 결정

- **`POST /trips/{id}/reopen` 추가.** spec 7의 엔드포인트 목록에는 없지만 spec 5.4 상태도의 `REJECTED → DRAFT`가 요구한다. 없으면 반려된 출장이 영원히 반려 상태로 남는다.
- **`validate_codes`에 `asyncio.gather`를 쓰지 않았다.** Phase 1 이월 메모가 제안했으나 `AsyncSession`은 동시 사용이 금지돼 있어 같은 세션에 `execute`를 병렬로 걸면 `InvalidRequestError`가 난다. 그룹 수와 무관하게 쿼리 2개로 끝내는 방식으로 대체했고, 이쪽이 더 빠르고 안전하다.

---

## Phase 2 리뷰가 잡아낸 결함

전부 mutation testing으로 실증했다 — 코드를 고의로 망가뜨렸는데 테스트가 전부 통과하면 그 테스트는 아무것도 지키지 않는 것이다.

| # | 결함 | 실제 영향 |
|---|---|---|
| 1 | `assert_deletable`을 뒤집어도 27건 전부 통과 | **SETTLED 출장이 삭제 가능**해지는데 아무 테스트도 안 걸림. 6개 상태 중 2개만 덮여 있었다 |
| 2 | `estimated_cost` 상한 없음 | `Numeric(14,2)` 오버플로가 flush에서 터져 **500 INTERNAL_ERROR**. Agent는 5xx를 재시도하므로 절대 성공할 수 없는 요청에 재시도 루프가 걸린다 |
| 3 | 전이 적법성과 권한이 분리 | 한쪽을 빠뜨리면 **fail-open**. `load_visible_trip`을 통과한 결재자가 신청자 전용 전이를 수행할 수 있었다 |
| 4 | `validate_codes`의 `is_active` 필터 2개 | 각각 지워도 127건 전부 통과. 관리자가 코드를 비활성화해도 그 값으로 쓰기가 통과 |
| 5 | `UNKNOWN_CODE_GROUP`이 `field`를 버림 | 코드 필드 5개 중 어디를 고쳐야 하는지 알 수 없는 400 |
| 6 | 파생 테스트 데이터가 검사 대상 상수에서 나옴 | `EDITABLE_STATUSES`를 넓히는 버그가 테스트를 통과 (45 → 44로 조용히 줄기만 함) |
| 7 | `make_trip_master_data`가 seed와 충돌 | `seeded` 세션에서 부르면 `UniqueViolation`이 savepoint 안에서 터져 세션이 오염되고 이후 모든 문장이 `PendingRollbackError`가 되어 원인이 묻힌다 |
| 8 | 팩토리 조직 모양이 seed와 다름 | 매니저와 보고자가 다른 부서에 배정 — 부서로 거르는 기능이 생기면 `seeded` 테스트만 통과 |

3번이 가장 컸다. `TRANSITION_ACTOR` 표 + import 시점 소진 가드로 닫았다 — 새 전이를 추가하고 주체를 빠뜨리면 조용히 "아무나 가능"이 되는 게 아니라 import에서 죽는다.

---

## Phase 3 — 완료

25개 태스크. Task 1–2는 구현 subagent + 독립 스펙 리뷰로, 나머지는 인라인 구현 + 태스크별 mutation 검증으로 진행했다(예산 한도로 subagent 경로 중단).

### 백엔드 — 서비스 계층

| 모듈 | 책임 |
|---|---|
| `services/matching.py` | 자동매칭 순수 함수 — 창(±1일)·취소·잠금 판정 + 매칭 사유 문자열 + 비목 추천. DB 접근 없음. 날짜는 KST 기준 |
| `services/expense_rules.py` | 정산 순수 규칙 + `EXPENSE_ALLOWED_TRANSITIONS`/`EXPENSE_TRANSITION_ACTOR` 표 + 임포트 시점 소진 가드 + `assert_expense_transition_allowed` |
| `services/expenses.py` | 정산서 조회·목록·생성·헤더수정·항목 CRUD·매칭후보·전이 4종·타임라인 |
| `services/cards.py` | 내 법인카드·카드거래 조회 (소유자 필터는 서비스가 건다) |
| `services/centers.py` | `assert_center_code` 순수 함수 추출, `assert_fund_center` 추가 |
| `services/trips.py` | `settle_trip_for_report` 추가 — commit하지 않는 시스템 전이 |
| `services/trip_rules.py` | `assert_system_transition` 추가 — 사용자 주체 전이를 거부하는 통로 |

### 백엔드 — API

```
GET              /api/v1/cards  ·  /api/v1/card-transactions
GET|POST         /api/v1/expenses
GET|PATCH        /api/v1/expenses/{id}
GET              /api/v1/expenses/{id}/match-candidates  ·  /timeline
POST             /api/v1/expenses/{id}/items
PATCH|DELETE     /api/v1/expense-items/{id}
POST             /api/v1/expenses/{id}/submit | approve | reject | reopen
```

정산 목록 필터: `scope`(mine·approvals·all) · `status`(반복 파라미터) · `q` · `page` · `size`
카드거래 필터: `card_id` · `approved_from` · `approved_to` · `merchant_category_code` · `q` · `include_cancelled` · `page` · `size`

### 프론트엔드

| 항목 | 내용 |
|---|---|
| 화면 | `/cards` `/expenses` `/expenses/[id]` + 출장 상세의 정산 진입 + 대시보드 미정산 카드 연결 |
| 컴포넌트 | `ExpenseStatusBadge` `CardTransactionTable` `MatchPanel` `ExpenseItemsTable` |
| 데이터 계층 | `api/query.ts`(공용 쿼리스트링 빌더, `tripQueryString`도 여기로 위임) · `api/cards.ts` · `api/expenses.ts` · `lib/expenses.ts`(상태 라벨·`resolveCenter`·`sumIncluded`) |

DESIGN.md 매핑: `reservation-card` → 정산서 우측 sticky 액션 카드, `rating-display`(64px = `text-display-xl`) → 정산 총액.

### 확정한 설계 결정

| 쟁점 | 결정 |
|---|---|
| `COMPLETED → SETTLED` 통로 | `assert_system_transition` 신설. 같은 `TRANSITION_ACTOR` 표를 읽고 양방향 fail-closed — 사용자 경로는 SYSTEM 전이를, 시스템 경로는 OWNER/APPROVER 전이를 거부 |
| 출장 이력 | `settle_trip_for_report`가 `record_transition`을 통과하고 commit하지 않는다 (정산 승인과 한 트랜잭션) |
| 반려 흐름 | `REJECTED` 후 `reopen`으로 DRAFT 복귀 (출장과 대칭). spec 5.5의 "반려 시 DRAFT" 문구보다 반려 사유 표시를 우선 |
| 제출 시 출장 상태 | 생성은 APPROVED·COMPLETED, **제출은 COMPLETED만**. 아니면 승인 시점에 전이표에 없는 `APPROVED → SETTLED`가 필요해진다 |
| `ActivityAction` | 정산 전용 멤버를 추가하지 않고 `entity_type=EXPENSE_REPORT`로 구분 |
| 승인 알림 | 정산서 쪽 `EXPENSE_APPROVED` 하나만. 출장 SETTLED는 activity_log만 남긴다 |
| 금액 상한 | 항목(`MAX_ITEM_AMOUNT`)과 합계(`MAX_REPORT_TOTAL`) 둘 다 서비스가 막는다 |
| 매칭 날짜 | `approved_at`을 KST로 변환해 비교 |

### 설계에서 벗어난 결정

- **`PATCH /expenses/{id}` 추가.** spec 7 목록에 없지만 spec 5.5가 "cost_center_code는 승계되며 수정 가능"과 "제출 시 FC/CC 필수"를 동시에 요구한다. 헤더를 고칠 경로가 없으면 FC가 빈 정산서는 영원히 제출 불가다.
- **`POST /expenses/{id}/reopen` 추가.** 출장의 reopen과 같은 이유.
- **`GET /expenses/{id}/timeline` 추가.** 쓰기만 하고 아무도 읽지 않는 `activity_log`가 되지 않도록.
- **`POST /items`·`PATCH|DELETE /expense-items/{id}`가 갱신된 정산서를 돌려준다.** 합계와 항목이 함께 바뀌므로 재조회 왕복을 없앤다.

### 시드 결함 수정

정산서를 COMPLETED 출장부터 채우던 탓에 **SETTLED 출장 일부가 정산서 없이** 남았다. SETTLED는 정산서가 승인됐다는 뜻이므로 상태 정의와 모순이고, 정산서 생성 시나리오도 막혔다. SETTLED를 먼저 채우고 남는 자리를 COMPLETED로 메우도록 고쳤다(정산서 12건은 그대로). 두 규칙을 `test_seed.py`가 지킨다.

**주의**: 이 수정은 시드 코드의 문제이므로 **이미 적재된 운영 DB에는 반영되지 않는다**(시드는 멱등이라 기존 행을 고치지 않는다). 필요하면 `expense_report`·`expense_item`·`trip`을 지우고 다시 시드해야 한다.

### 실서버 검증 완료

curl로 Agent 경로를 그대로 밟았다: `BT-2026-0020` 완료 처리 → 정산서 `EX-2026-0013` 생성(코스트센터 CC2100 승계) → 항목 추가 → FC 지정 → 제출 → 결재자(김연구) 결재함 노출 → 승인 → **출장이 SETTLED로 자동 전이** → 출장 타임라인 `COMPLETED·SETTLED`, 정산 타임라인 `CREATED·UPDATED·SUBMITTED·APPROVED`, 신청자에게 `EXPENSE_APPROVED` 알림.

자동매칭 실측(`BT-2026-0030`): 후보 6건, 사유 `출장기간 내 승인` 5건 + `종료 익일 승인` 1건, 비목 추천 `TRANSPORT`/`MEAL`/`LODGING`.

에러 계약 실측: 항목 없이 제출 409 `EXPENSE_NO_ITEMS` · FC 없이 제출 400 `CENTER_REQUIRED`+`field` · 신청자의 승인 시도 403 `NOT_EXPENSE_APPROVER` · 중복 승인 409 `EXPENSE_INVALID_TRANSITION` · 승인 후 항목 수정 409 `EXPENSE_NOT_EDITABLE` · 타인 정산서 404 `EXPENSE_NOT_FOUND`.

### Phase 3에서 처리한 이월 항목

- `load_active_codes` 삭제. "그룹 부재 vs 활성 코드 0개" 규칙은 `validate_codes` 테스트가 `field`까지 포함해 지킨다.
- `assert_center_code` 순수 함수 추출 + `assert_fund_center` 추가. 멤버십 검사가 한 곳뿐이다.
- `GET /fund-centers`가 첫 소비처(정산서 헤더 FC 셀렉트)를 얻었다.
- `COMPLETED → SETTLED` 연결 완료.
- `ActivityAction`은 그대로 두기로 결정.

### 최종 리뷰가 잡아낸 것

브랜치 전체를 대상으로 한 리뷰에서 3건을 고쳤다.

| 결함 | 실제 영향 |
|---|---|
| JWT 전용 엔드포인트의 OpenAPI `security`에 `ApiKeyAuth`가 남아 있었다 | 설명 문구에만 "로그인 세션 전용"이라 적혀 있었다. **스키마를 기계로 읽는 Agent** — 이 모듈의 존재 이유인 바로 그 독자 — 는 키로 호출해도 된다고 믿고 403을 받는다. `test_jwt_only_endpoints_do_not_advertise_the_api_key_scheme`가 고정한다 |
| `pyproject.toml`이 `fastapi>=0.115`를 선언했다 | `iter_route_contexts`는 0.141에 들어왔다. 하한 버전에서는 소진 가드가 라우트를 0개로 세면서 **조용히 통과**한다 — 스코프 안전성 전체가 이 함수에 걸려 있다. `>=0.141`로 올렸다 |
| `/settings/api-keys`의 `revoke()`에 재진입 가드가 없었다 | 두 번째 요청이 409로 떨어져 "폐기에 실패했습니다"가 뜨는데 실제로는 폐기된 상태다 |

### mutation 검증 목록

가드를 넣을 때마다 그 줄을 망가뜨려 테스트가 실제로 깨지는지 확인했다.

| 가드 | 깨진 테스트 |
|---|---|
| `assert_center_code`의 멤버십 검사 | 7건 |
| `assert_system_transition`의 SYSTEM 검사 | 2건 |
| `matching`의 취소·잠금 필터, `WINDOW_DAYS` | 각 1–2건 |
| `EXPENSE_TRANSITION_ACTOR` 엔트리 삭제 | 임포트 시점 `RuntimeError` |
| `assert_report_total`, `sum_included`의 제외 처리 | 각 1건 |
| 카드거래 소유자 필터 | 1건 |
| `assert_report_creatable` · `assert_trip_owner`(정산서 생성) | 각 1건 |
| `assert_item_amount`, 거래 소유자 조건, 합계 재계산 | 각 1건 |
| 매칭 잠금 상태 집합(DRAFT 포함), 자기 리포트 제외 조건 | 각 1건 |
| `assert_trip_completed` · `assert_has_items` · `assert_centers_present` · `settle_trip_for_report` 호출 | 각 1–3건 |

---

## Phase 4 — 완료

21개 태스크. 태스크마다 구현 subagent 1 + 컨트롤러의 독립 검증(계획 원문과 diff 대조 + 직접 재현)으로 진행했다.

### 백엔드 — 서비스 계층

| 모듈 | 책임 |
|---|---|
| `services/api_scopes.py` | `SCOPE_REQUIREMENTS` 표(37항목) + `required_scope_for` + `scope_catalog` + `assert_scope_table_complete`. DB 접근 없음 |
| `services/api_keys.py` | 키 생성·SHA-256 해시(순수) + `key_state`(순수) + 인증·발급·목록·폐기 |
| `openapi.py` | securitySchemes 2종 주입 + 오퍼레이션 설명에 필요 스코프 표기 |
| `deps.py` | JWT·API Key 이중 인증, 스코프 강제 단일 지점, `JwtOnlyUser` |

### 백엔드 — API

```
GET|POST /api/v1/api-keys
POST     /api/v1/api-keys/{key_id}/revoke
GET      /api/v1/scopes
```

기존 33개 엔드포인트는 **코드 변경 없이** API Key로 열렸다. 인증과 스코프가 `get_principal` 한 곳에 있기 때문이다.

### 프론트엔드

| 항목 | 내용 |
|---|---|
| 화면 | `/settings/api-keys`(발급·조회·폐기) · `/developers`(가이드) — AppShell의 죽은 `/developers` 링크가 채워졌다 |
| 데이터 계층 | `api/api-keys.ts` · `api/meta.ts` · `lib/api-keys.ts`(라벨·상태 톤·curl 스니펫, 순수) |

### 확정한 설계 결정

| 쟁점 | 결정 | 이유 |
|---|---|---|
| 스코프 검사 위치 | `get_principal` 안 **한 곳** + 라우트 표 | 엔드포인트별 `Depends(require_scope(...))`는 빠뜨리면 그 엔드포인트만 조용히 전권이 되는 fail-open. 상태전이에서 이미 세 번 겪었다 |
| 표 정합성 | `assert_scope_table_complete(app)`를 `main.py`가 임포트 시점에 호출 | 라우트를 추가하고 표에 안 적으면 **기동 실패**. 표와 라우터는 같은 커밋에서 움직여야 한다 |
| 키 관리 API 인증 | JWT 전용(`JwtOnlyUser`) | API Key가 키를 발급하면 `cards:read` 키 하나로 전권 키를 찍어낼 수 있어 스코프가 무의미해진다 |
| 두 헤더 동시 | `X-API-Key` 우선 | 브라우저는 로그인 상태면 항상 Authorization을 보낸다. 명시적으로 얹은 키가 더 구체적인 의도이고, 무엇보다 결정적이어야 한다 |
| 평문 키 | 발급 응답 1회. DB에는 SHA-256만 | spec 5.7. `ApiKeyOut`에는 `key` 필드가 아예 없다 |
| 키 형식 | `sk_live_` + `token_hex(16)` (40자), 접두어 16자 표시 | 영숫자만이라 복사·URL·셸 인용 사고가 없다 |
| 스코프 검증 위치 | Pydantic이 아니라 서비스 | Enum으로 강제하면 오타가 422 SCHEMA_INVALID로 떨어져 "어떤 값이 유효한지"를 못 알려준다. 400 `INVALID_SCOPE`가 유효값 목록을 메시지에 싣는다 |
| 스코프 없는 엔드포인트 | `/auth/me`·`/codes`·`/fund-centers`·`/cost-centers`·`/notifications`·`/scopes`·`/api-keys` → `None` | spec이 스코프를 6종으로 고정했다. 마스터 데이터는 쓰기의 전제조건, 나머지는 본인 리소스. 단 표에 **명시적으로 `None`**을 적어야 소진 가드를 통과한다 |
| `last_used_at` | 검증 성공 시 매번 갱신 후 그 자리에서 commit | 요청이 실패해 롤백돼도 "이 키가 쓰였다"는 사실은 남아야 한다 |
| 키 개수 | 사용자당 활성 10개(`MAX_ACTIVE_KEYS`) | 폐기·만료된 키는 세지 않는다 |
| 폐기 | soft(`revoked_at`), `POST .../revoke` | `DELETE`는 하드 삭제로 읽힌다. 감사 흔적을 남긴다 |
| 시드 | 데모 키를 시드하지 않는다 | 리포지토리에 유효한 평문 키를 두지 않는다 |
| 가이드 스코프 표 | `GET /scopes`가 `SCOPE_REQUIREMENTS`에서 뽑아 내려준다 | 화면에 하드코딩하면 집행되는 표와 조용히 어긋난다 |

### 계획 자체의 결함 2건 (구현 중 발견)

계획서에 적힌 코드가 틀렸고, 구현 subagent가 실증으로 잡아냈다. 둘 다 계획 문서도 함께 고쳤다.

1. **`isinstance(route, APIRoute)`로 라우트를 훑으면 0개가 잡힌다.** fastapi 0.141에서 `include_router`로 등록한 라우트는 `app.routes`에 `_IncludedRouter`로 감싸여 있다(13개 중 `APIRoute`는 직접 등록한 헬스체크 2개뿐). `iter_route_contexts`로 펼쳐야 한다. 이걸 못 잡았으면 소진 가드가 **아무것도 검사하지 않으면서 통과**했을 것이다.
2. **probe 앱을 운영 표와 비교하면 항상 어긋난다.** 계획의 probe 테스트는 33항목짜리 운영 표와 비교하고 있어서 통과가 수학적으로 불가능했다. 첫 수정안은 "인증 라우트가 0개면 통과"였는데 **이건 1번과 정확히 같은 fail-open**이라 되돌리고, 표를 인자로 주입하도록 바꿨다(`requirements=`). 운영 호출은 인자 없이 전체 표와 비교한다. "라우트 0개 + 표 비어있지 않음"은 탐지가 깨졌다는 뜻이므로 이제 예외를 던지며, `test_guard_rejects_an_app_with_no_authenticated_routes`가 그걸 고정한다.

### 실서버 검증 완료

curl로 Agent 경로를 그대로 밟았다.

| 확인 | 결과 |
|---|---|
| JWT로 키 발급 | 201, `key`는 `sk_live_` + 32자, 접두어 `sk_live_2e39f882` |
| 키로 `/auth/me` | 소유자(이민수) 반환 — 키가 사람을 대신한다 |
| 스코프 부족 | `/cards`에 trips 전용 키 → 403 `SCOPE_REQUIRED` + "cards:read 스코프가 필요합니다" |
| 키로 쓰기 전체 | 출장 생성 `BT-2026-0042` → 상신 `SUBMITTED` → 타임라인 `CREATED`·`SUBMITTED` |
| 중복 상신 | 409 `TRIP_INVALID_TRANSITION` — 웹 경로와 같은 코드 |
| 키가 키를 발급 | 403 `API_KEY_FORBIDDEN` |
| `last_used_at` | 사용 직후 채워짐 |
| 폐기 후 사용 | 401 `API_KEY_REVOKED` |
| 없는 키 / 중복 폐기 / 잘못된 스코프 | 401 `INVALID_API_KEY` · 409 `API_KEY_ALREADY_REVOKED` · 400 `INVALID_SCOPE`(field=`scopes`) |
| OpenAPI | `BearerAuth`·`ApiKeyAuth` 노출, `POST /trips` 설명에 **필요 스코프: `trips:write`**, `/auth/login`에는 security 없음, `/api-keys`는 "로그인 세션 전용" |

### mutation 검증 목록

가드를 넣을 때마다 그 줄을 망가뜨려 테스트가 실제로 깨지는지 확인했다.

| 가드 | 깨진 것 |
|---|---|
| `SCOPE_REQUIREMENTS`에서 항목 1개 삭제 | 임포트 시점 `RuntimeError` (앱이 뜨지 않음) |
| `scopes is UNRESTRICTED` → `if not scopes` | `test_empty_scope_key_is_not_unrestricted` (스코프 빈 키가 전권을 얻음) |
| 라우트 탐지가 0개를 반환하는 상황 | `test_guard_rejects_an_app_with_no_authenticated_routes` |
| `authenticate_key`의 REVOKED 분기 · `is_active` 검사 | 각 1건 |
| `_validate_scopes`의 미지 스코프 검사 | 1건 |
| 폐기의 소유자 조건(`key.user_id != user.id`) | 1건 |
| 활성 개수 쿼리의 `revoked_at.is_(None)` | 1건 |
| `X-API-Key` 분기 비활성화 | 신규 11건 전부 |
| `submit_trip`의 `record_transition` 생략 | 타임라인 parity 테스트 1건 |
| `TRIP_INVALID_TRANSITION` 코드 변경 | 에러계약 parity 테스트 1건 |

---

## Phase 5 — 완료

계획서 23개 태스크를 인라인으로 실행했다(서브에이전트 없음). 태스크마다 테스트 선작성 → 구현 → mutation 검증 순서를 지켰다.

### 백엔드 — 서비스 계층

| 모듈 | 책임 |
|---|---|
| `services/admin/common.py` | `assert_password_length`(순수) · `assert_unique` · `delete_entity`(IntegrityError→409 + 세션 롤백) |
| `services/admin/departments.py` | 부서 CRUD, 상위부서 검증(자기참조 금지) |
| `services/admin/codes.py` | 코드그룹·코드 CRUD, "비활성화 후 삭제" 2단계 |
| `services/admin/centers.py` | FC/CC CRUD(모델 파라미터 공유) + `_REFERENCES` 참조 검사 |
| `services/admin/users.py` | 사용자 CRUD(삭제 없음)·비밀번호 설정·자기강등 금지·이름 일괄 조회 |
| `services/admin/cards.py` | 법인카드 CRUD(실제 FK 삭제 경로) |

### 백엔드 — API (28개, 전부 `ApiKeyScope.ADMIN`)

```
GET|POST        /api/v1/admin/departments
PATCH|DELETE    /api/v1/admin/departments/{department_id}
GET|POST        /api/v1/admin/code-groups
PATCH|DELETE    /api/v1/admin/code-groups/{group_id}
POST            /api/v1/admin/code-groups/{group_id}/codes
PATCH|DELETE    /api/v1/admin/codes/{code_id}
GET|POST        /api/v1/admin/fund-centers   ·  PATCH|DELETE /api/v1/admin/fund-centers/{center_id}
GET|POST        /api/v1/admin/cost-centers   ·  PATCH|DELETE /api/v1/admin/cost-centers/{center_id}
GET|POST        /api/v1/admin/users
GET|PATCH       /api/v1/admin/users/{user_id}
POST            /api/v1/admin/users/{user_id}/password      ← JWT 전용
GET|POST        /api/v1/admin/cards  ·  PATCH|DELETE /api/v1/admin/cards/{card_id}
```

사용자 목록 필터: `q`(이름·이메일·사번) · `department_id` · `role` · `is_active` · `page` · `size`

### 프론트엔드

| 항목 | 내용 |
|---|---|
| 화면 | `/admin/codes` `/admin/centers` `/admin/departments` `/admin/users` `/admin/cards` + `/admin` 레이아웃(ADMIN 가드·서브탭) |
| 데이터 계층 | `api/admin.ts`(23개 함수, 전부 `authRequest`) · `lib/admin.ts`(순수 헬퍼) · `stores/admin-resource.svelte.ts` |
| 반응형 | `--breakpoint-tablet: 744px` 신설, AppShell 햄버거 시트, 넓은 표 5곳 가로 스크롤 |

### 확정한 설계 결정

| 쟁점 | 결정 | 이유 |
|---|---|---|
| Admin 인가 | `AdminUser`(role) + 표의 `ADMIN`(scope) **둘 다** | 역할만 보면 ADMIN이 발급한 `trips:read` 키가 열리고, 스코프만 보면 EMPLOYEE 소유의 admin 키가 통과한다 |
| 비밀번호 설정 | JWT 전용(`JwtOnlyAdmin`) | admin 스코프 키 → 남의 비밀번호 → 그 계정 로그인 → 전권 키. 키 관리 API의 JWT 전용 방어가 우회된다 |
| 비밀번호 길이 | 서비스의 `assert_password_length`(바이트) | `max_length`는 문자 수라 한글 72자(216바이트)를 통과시켜 bcrypt에서 500이 된다 |
| 사용자 삭제 | 없음. 비활성화만 | trip·expense_report·card·api_key·activity_log가 참조한다. 감사 흔적을 지우는 것도 옳지 않다 |
| 자기 강등 | 409 `CANNOT_DEMOTE_SELF` | 마지막 ADMIN이 스스로를 내리면 복구 경로가 DB 직접 수정뿐이다 |
| 코드 삭제 | 활성 코드는 409 `CODE_STILL_ACTIVE` | 업무 테이블이 코드값을 문자열로 참조해 FK가 없다. "비활성화 후 삭제"가 유일하게 값싼 방어선 |
| 코드그룹 삭제 | 코드가 남아 있으면 409 | `cascade="all, delete-orphan"`이 자식을 조용히 쓸어가는 것을 2단계로 바꾼다 |
| 센터 삭제 | `_REFERENCES` 열거로 409 | FK가 없다. 참조처가 trip·expense_report·expense_item 3곳뿐이라 셀 수 있다 |
| 유니크 위반 | 삽입 전 SELECT → 409 + `field` | `IntegrityError`로는 어느 컬럼이 겹쳤는지 몰라 `field`를 못 채운다 |
| Admin 목록 | 비활성 행 포함(전용 스키마) | 관리 화면이 비활성 값을 못 보면 되살릴 수 없다. 일반 화면은 기존 스키마 그대로 활성만 본다 |
| PATCH | `model_dump(exclude_unset=True)` | `parent_id=None`의 "안 보냄"과 "null로 지우기"를 가르는 유일한 수단 |
| 프론트 공유 | `AdminResource`가 목록·에러·중복제출 가드 소유 | 화면 5개에 같은 가드를 손으로 넣으면 하나는 빠진다 |
| 반응형 기준선 | `tablet:`(744px) 신설, `md:`(768px) 유지 | DESIGN.md 기준은 744px. `--breakpoint-md`를 덮으면 기존 13개 화면 그리드가 함께 움직인다 |

### mutation 검증 목록

| 가드 | 깨진 것 |
|---|---|
| `delete_entity`의 `except IntegrityError` | `test_delete_entity_turns_a_reference_into_409` |
| `MAX_PASSWORD_BYTES = 72` | `test_korean_password_over_72_bytes_is_rejected` |
| `AdminUser`에 MANAGER 추가 | `test_manager_is_rejected` |
| `SCOPE_REQUIREMENTS`에서 admin 항목 1개 삭제 | 임포트 시점 `RuntimeError`(앱이 뜨지 않음) |
| `delete_code`의 활성 검사 · `delete_code_group`의 코드 검사 | 각 1건 |
| `_REFERENCES[CostCenter]`의 `Trip.cost_center_code` | `test_center_referenced_only_by_a_trip_cannot_be_deleted` |
| `update_user`의 자기강등 블록 | 2건 |
| 비밀번호 라우트의 `JwtOnlyAdmin` → `AdminUser` | `test_password_reset_rejects_api_keys` |
| 사용자 목록의 부서 일괄 조회 → 행별 조회 | 쿼리 수 상한 테스트 |
| `delete_card`의 `delete_entity` → raw delete | 409가 500이 됨 |
| `AdminResource.run`의 `if (this.busy) return false` | 중복 제출 테스트 |

### mutation이 **못** 잡은 것 (기록)

- 결재자 이름을 행별 `session.get`으로 바꿔도 쿼리 수가 늘지 않는다. 목록 쿼리가 이미 적재한 identity map에서 나오기 때문이다. 실제로 늘어나는 것은 부서 조회이고 상한 테스트가 그것을 잡는다.
- 시드의 `CC2100`은 출장·정산서 양쪽이 참조해서, `_REFERENCES`의 Trip 항목만 지워도 정산서 항목이 대신 걸렸다. 참조처를 출장 하나로 한정한 테스트를 따로 추가해 그 구멍을 닫았다.

### Phase 5에서 처리한 이월 항목

- `/admin/*`을 `SCOPE_REQUIREMENTS`에 `ADMIN`으로 등록(28항목). 소진 가드가 실제로 동작하는 것을 mutation으로 확인했다.
- Admin 삭제의 `IntegrityError` → 409 `HAS_DEPENDENTS` 변환(`delete_entity`).
- 비밀번호 엔드포인트의 72바이트 가드.
- `admin` 스코프에 엔드포인트가 생겼다. `/scopes` 카탈로그와 `/developers` 가이드가 자동으로 따라온다.
- 반응형 744px 뼈대: 헤더 햄버거 시트 + 표 5곳 가로 스크롤.
- Phase 4의 "admin 스코프는 엔드포인트 없음" 테스트를 "카탈로그가 admin 경로 전부를 덮는다"로 교체했다.

## Phase 4에서 넘어온 항목

**UI**

- **브라우저 수동 시나리오 23개 미확인.** Phase 2 이월 8개(딥링크·중복 제출·반려 재작성·전역 401 등) + Phase 3 이월 6개(카드 필터, 정산서 생성·승계, 담기, 부서 상속 토글, FC 누락 제출, 승인 후 출장 SETTLED 확인) + Phase 4 신규 9개(발급 흐름, 평문 1회 노출, 복사 폴백, 중복 제출 가드, 스코프 미선택, 폐기 2단계, 스코프 표 동기화, 헤더 탭, 전역 401). 절차는 Phase 3 계획 Task 24와 Phase 4 계획 Task 20에 있다. **Phase 4 화면 2개는 렌더 확인이 전혀 안 됐다** — 구현·검증 모두 브라우저 도구가 없는 환경에서 이뤄졌고, 타입체크·빌드·API 경로(curl)만 통과한 상태다.
- **복사 폴백은 운영에서만 검증된다.** `/settings/api-keys`의 "복사"는 `navigator.clipboard`가 없을 때 `execCommand('copy')`로 떨어지는데, localhost는 SecureContext라 첫 경로가 항상 성공한다. 평문 HTTP 배포 후에 눌러봐야 한다.
- **출장 상세가 정산서 존재 여부를 목록 `size=100` 조회로 판단한다.** 데모 규모에서는 충분하지만 정산서가 100건을 넘으면 놓친다. `trip_id` 필터나 전용 조회가 필요하다.
- **알림 뱃지는 여전히 라우트 변경 시에만 갱신된다.** 폴링·SSE는 데모 범위 밖.
- **대시보드 집계는 여전히 목록 API 4회 호출이다.**

**백엔드**

- **항목의 FC/CC override는 제출 시 재검증되지 않는다.** 제출은 헤더 FC/CC만 마스터와 대조한다. 항목 override 후 그 센터가 비활성화되면 통과한다.
- **정산 목록의 `q`도 LIKE 와일드카드를 이스케이프하지 않는다** (출장과 같은 판단).
- **`next_report_no`도 `max() + 1`이다.** 멀티 레플리카로 가면 `next_trip_no`와 함께 시퀀스나 advisory lock으로 옮긴다.
- **매칭 후보 조회는 페이징이 없다.** 출장 기간 ±2일이라 건수가 작지만, 장기 출장에서는 커질 수 있다.
- **운영 DB의 기존 시드 데이터는 옛 배정 규칙 그대로다** (위 "시드 결함 수정" 참조).
- **`last_used_at`을 매 요청 갱신한다.** API Key 요청마다 UPDATE + COMMIT 1회. 데모 규모에서는 문제없지만 트래픽이 늘면 60초 스로틀이나 배치 갱신으로 옮긴다. 지금은 "마지막 사용"이 실시간으로 움직이는 게 데모 포인트라 그대로 뒀다.
- ~~**`admin` 스코프에 엔드포인트가 없다.**~~ → Phase 5에서 28개가 열렸다.
- **키 발급·폐기는 `activity_log`에 남지 않는다.** `EntityType`이 `TRIP|EXPENSE_REPORT`뿐이라 새 멤버가 필요하고 spec에 없다. 감사 요구가 생기면 그때 넣는다.
- **rate limit·IP 제한 없음** (spec 7이 명시적으로 범위 밖).
- **`MAX_ACTIVE_KEYS` 검사에 TOCTOU가 있다.** 동시에 두 건을 발급하면 둘 다 개수 검사를 통과할 수 있다. 상한이 한 개 넘는 것뿐이고 권한 상승이 아니라 그대로 뒀다. 엄밀히 막으려면 유니크 제약이나 advisory lock이 필요하다 (`next_trip_no`의 `max()+1`과 같은 종류의 미결).
- **검증 중 만든 데모 데이터가 운영 DB에 남아 있다.** 출장 `BT-2026-0042`(SUBMITTED)와 폐기된 API Key 2건(user1·admin). 실제 사용 흔적이라 지우지 않았다.

## Phase 5에서 넘어온 항목

**Phase 5가 새로 남긴 것**

- **부서 트리의 일반 순환(A→B→A)은 검사하지 않는다.** 자기 자신만 막는다. 데모 조직은 2단계이고 일반 순환 검출은 재귀 조회가 필요하다.
- **유니크 검사에 TOCTOU가 있다.** 삽입 전 SELECT로 보므로 동시에 같은 코드를 만들면 둘 다 통과하고 DB 제약이 500으로 잡는다 (`MAX_ACTIVE_KEYS`와 같은 종류의 미결).
- **코드·센터 삭제 가드는 참조 열거에 의존한다.** FK가 없어서다. 코드 문자열을 참조하는 테이블을 새로 만들면 `admin/centers.py`의 `_REFERENCES`와 코드 삭제 규칙을 함께 늘려야 한다.
- **DESIGN.md의 "모바일에서 reservation card → 화면 하단 sticky bar"는 미구현이다.** 현재는 좁은 화면에서 우측 카드가 아래로 쌓인다. 헤더 햄버거와 표 가로 스크롤만 넣었다.
- **Admin 화면은 낙관적 갱신을 하지 않는다.** 모든 쓰기 뒤에 목록을 통째로 다시 읽는다(`AdminResource.run`). 마스터 규모가 작아서 택한 단순함이다.
- **Admin 목록에 페이징 UI가 없다.** 사용자 목록만 서버 페이징이 있고 화면은 `size=100`으로 한 번에 읽는다.
- **키 발급·폐기는 여전히 `activity_log`에 남지 않는다.** Admin 마스터 변경도 마찬가지다 — `EntityType`에 멤버가 없다.

**Phase 4에서 그대로 넘어온 것**

- `last_used_at`을 API Key 요청마다 UPDATE + COMMIT 한다(스로틀 미적용).
- 출장 상세가 정산서 존재 여부를 목록 `size=100` 조회로 판단한다.
- 항목의 FC/CC override는 제출 시 재검증되지 않는다.
- 목록 `q`는 LIKE 와일드카드를 이스케이프하지 않는다(출장·정산·사용자 모두).
- `next_trip_no`·`next_report_no`가 `max() + 1`이다.
- 매칭 후보 조회에 페이징이 없다.
- 알림 뱃지는 라우트 변경 시에만 갱신된다. 대시보드 집계는 목록 API 4회 호출이다.
- rate limit·IP 제한 없음.
- 운영 DB의 옛 시드 데이터는 옛 배정 규칙 그대로다.

## 이후 Phase

spec 10의 5단계가 모두 끝났다. 다음 작업은 새 요구가 생길 때 정의한다. 우선순위 후보는 위 이월 목록과 아래 공통 미결이다.

## 전 Phase 공통 미결

- **반응형**: Phase 5에서 뼈대를 넣었다 — `--breakpoint-tablet: 744px`, 헤더 햄버거 시트, 넓은 표 5곳(`CardTransactionTable`·`ExpenseItemsTable`·`/settings/api-keys`·`/developers` 2곳) 가로 스크롤. 남은 것은 DESIGN.md의 모바일 sticky 하단 바(출장·정산 상세의 우측 카드)와 좁은 화면에서의 표 카드 붕괴다.
- **비밀번호 길이**: bcrypt 5.x는 72바이트 초과 시 자르지 않고 예외를 던진다. 한글은 **24자만 넘어도** 터진다. Phase 5의 `assert_password_length`가 그 가드이며, 비밀번호를 받는 경로를 새로 만들면 반드시 통과시켜야 한다.
- **운영 `JWT_SECRET`**: compose 기본값은 명백한 placeholder다. 배포 시 32바이트 이상 실제 값을 `.env`로 주입한다.
- **`init-db`는 컬럼 변경을 반영하지 않는다.** Alembic을 쓰지 않으므로 스키마를 바꾸면 해당 테이블을 지우고 다시 돌려야 한다. 실제 운영 전환이 필요해지면 마이그레이션 도구 도입을 재검토한다.
